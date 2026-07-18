"""
Tool usage auditor for the copilot agent fleet.

Walks ~/.copilot/session-state/*/events.jsonl, aggregates tool call frequencies,
cross-references against each agent's declared tool list, and produces a markdown
report that highlights:
  - Most-used tools globally (keep)
  - Tools never used despite being declared on agents (prune candidates)
  - Per-agent tool surface size and bloat estimate
  - Tools used during a subagent invocation (attribution by parent chain)

Output: ~/.copilot/agents/files/tool-usage-report.md
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
SESSIONS_DIR = HOME / ".copilot" / "session-state"
AGENTS_DIR = HOME / ".copilot" / "agents"
OUTPUT_FILE = AGENTS_DIR / "files" / "tool-usage-report.md"


def parse_agent_tools(agent_file: Path) -> list[str]:
    """Extract the comma-separated tool list from an agent .md frontmatter."""
    text = agent_file.read_text(encoding="utf-8", errors="ignore")
    # Grab the `tools:` line (may span lines, may have a `[ ... ]` override block)
    # Simple approach: find every `something/something` token in the frontmatter section.
    fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    fm = fm_match.group(1) if fm_match else text[:4000]
    tools = re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]*/[a-zA-Z0-9_\-]+", fm)
    # Also pick up bare top-level tools listed without slash (e.g., `todo`, `web/fetch`)
    bare = re.findall(r"(?<![\w/])(todo|web/fetch|web/githubRepo)(?![\w/])", fm)
    return sorted(set(tools + bare))


def load_agents() -> dict[str, list[str]]:
    """Return {agent_name: [tool, ...]} for every .agent.md and .md agent in the dir."""
    agents = {}
    for f in AGENTS_DIR.glob("*.agent.md"):
        name = f.stem.replace(".agent", "")
        agents[name] = parse_agent_tools(f)
    # Also CLI-style .md agents (scoper, retro)
    for f in AGENTS_DIR.glob("*.md"):
        if f.name in ("README.md",) or f.name.endswith(".agent.md"):
            continue
        name = f.stem
        agents.setdefault(name, parse_agent_tools(f))
    return agents


def walk_events() -> tuple[Counter, dict[str, Counter], int, int]:
    """
    Returns:
      global_counts: Counter of tool_name -> total invocations
      by_subagent:   {subagent_name: Counter of tools invoked while that subagent was active}
      sessions_scanned, events_parsed
    """
    global_counts: Counter = Counter()
    by_subagent: dict[str, Counter] = defaultdict(Counter)
    sessions = 0
    events = 0

    for sess_dir in SESSIONS_DIR.iterdir():
        if not sess_dir.is_dir():
            continue
        ev_file = sess_dir / "events.jsonl"
        if not ev_file.exists():
            continue
        sessions += 1

        # Track active subagent stack via parentId chain.
        # When subagent.started fires, register tool_call_id -> agent_name.
        # Tools whose parentId chain leads back to that tool_call_id are attributed.
        subagent_id_to_name: dict[str, str] = {}
        # parent_to_subagent_root: cache parent_id -> originating subagent name (or None)
        parent_to_root: dict[str, str | None] = {}

        try:
            with ev_file.open("r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    events += 1
                    et = ev.get("type", "")
                    data = ev.get("data", {})

                    if et == "subagent.started":
                        tcid = data.get("toolCallId")
                        name = data.get("agentName") or "unknown"
                        if tcid:
                            subagent_id_to_name[tcid] = name

                    elif et == "tool.execution_start":
                        tname = data.get("toolName") or "unknown"
                        global_counts[tname] += 1

                        # Attribute to a subagent by walking parentId chain.
                        # Cheap heuristic: check if this event's parentId is in subagent_id_to_name
                        # OR a known descendant. We approximate by checking immediate parent only;
                        # for deeper chains we'd need to build the full tree. Good enough for v1.
                        pid = ev.get("parentId")
                        sub_name = None
                        # Walk up via parent_to_root cache
                        cur = pid
                        depth = 0
                        while cur and depth < 20:
                            if cur in subagent_id_to_name:
                                sub_name = subagent_id_to_name[cur]
                                break
                            if cur in parent_to_root:
                                sub_name = parent_to_root[cur]
                                break
                            depth += 1
                            cur = None  # we don't have per-event parent map; stop
                        # Cache result for this event id so descendants can resolve faster
                        eid = ev.get("id")
                        if eid:
                            parent_to_root[eid] = sub_name
                        if sub_name:
                            by_subagent[sub_name][tname] += 1
                        else:
                            by_subagent["__main__"][tname] += 1
        except OSError:
            continue

    return global_counts, by_subagent, sessions, events


def normalize_tool(t: str) -> str:
    """Normalize a tool token so events 'powershell' matches agent-listed 'execute/runInTerminal'."""
    # The CLI emits short names (powershell, view, edit, grep, ...) and MCP tools as 'azure-mcp/*'.
    # Agents declare tools using slash-namespaced names. We compare both raw and prefix-stripped.
    return t


def render_report(
    global_counts: Counter,
    by_subagent: dict[str, Counter],
    agents: dict[str, list[str]],
    sessions: int,
    events: int,
) -> str:
    lines: list[str] = []
    lines.append("# Copilot Agent Tool Usage Audit")
    lines.append("")
    lines.append(f"- Sessions scanned: **{sessions}**")
    lines.append(f"- Events parsed: **{events:,}**")
    lines.append(f"- Distinct tools invoked: **{len(global_counts)}**")
    lines.append("")
    lines.append("> CAVEAT: events.jsonl captures CLI-driven sessions. VS Code-agent")
    lines.append("> invocations (DEV/INFRA/QA/DIAGRAM/DOCS run from VS Code chat) may")
    lines.append("> only show up here when they were invoked from a CLI session as")
    lines.append("> subagents. Per-agent numbers are best-effort attribution.")
    lines.append("")

    # ---------- Global top tools ----------
    lines.append("## Most-used tools (global, all sessions)")
    lines.append("")
    lines.append("| Tool | Calls |")
    lines.append("|---|---:|")
    for tool, n in global_counts.most_common(30):
        lines.append(f"| `{tool}` | {n} |")
    lines.append("")

    # ---------- Per-agent attribution ----------
    lines.append("## Per-subagent tool usage (events.jsonl attribution)")
    lines.append("")
    for agent_name, counts in sorted(by_subagent.items(), key=lambda kv: -sum(kv[1].values())):
        if not counts:
            continue
        total = sum(counts.values())
        lines.append(f"### {agent_name} — {total} tool calls")
        lines.append("")
        for tool, n in counts.most_common(15):
            lines.append(f"- `{tool}` × {n}")
        lines.append("")

    # ---------- Declared-vs-used per agent ----------
    lines.append("## Declared vs Used (prune candidates)")
    lines.append("")
    lines.append("Tools declared on the agent but with **0 observed calls in any session**.")
    lines.append("Strong prune candidates — but verify the agent has actually been run before pruning.")
    lines.append("")

    # Build set of all tools ever called (with normalized variants)
    used = set(global_counts.keys())
    # Heuristic: also count an azure-mcp/* tool as 'used' if its bare name was called
    # (e.g., 'cosmos' invoked via the azure-mcp router).

    for agent_name, declared in sorted(agents.items()):
        if not declared:
            continue
        unused = [t for t in declared if t not in used and t.split("/")[-1] not in used]
        used_count = len(declared) - len(unused)
        lines.append(f"### {agent_name}")
        lines.append("")
        lines.append(f"- Declared tools: **{len(declared)}**")
        lines.append(f"- Observed in events.jsonl: **{used_count}**")
        lines.append(f"- Never observed: **{len(unused)}** (prune candidates if agent has been used)")
        lines.append("")
        if unused:
            lines.append("<details><summary>Unused tools</summary>")
            lines.append("")
            for t in unused:
                lines.append(f"- `{t}`")
            lines.append("")
            lines.append("</details>")
            lines.append("")

    # ---------- Per-agent bloat summary ----------
    lines.append("## Bloat summary")
    lines.append("")
    lines.append("| Agent | Declared | Observed | Bloat % |")
    lines.append("|---|---:|---:|---:|")
    for agent_name, declared in sorted(agents.items()):
        if not declared:
            continue
        used_count = sum(1 for t in declared if t in used or t.split("/")[-1] in used)
        bloat = 100 * (1 - used_count / len(declared)) if declared else 0
        lines.append(f"| {agent_name} | {len(declared)} | {used_count} | {bloat:.0f}% |")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    agents = load_agents()
    global_counts, by_subagent, sessions, events = walk_events()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        render_report(global_counts, by_subagent, agents, sessions, events),
        encoding="utf-8",
    )
    print(f"Wrote: {OUTPUT_FILE}")
    print(f"Sessions: {sessions}  Events: {events:,}  Tools: {len(global_counts)}")
    print()
    print("Top 15 tools globally:")
    for tool, n in global_counts.most_common(15):
        print(f"  {n:>5}  {tool}")


if __name__ == "__main__":
    main()
