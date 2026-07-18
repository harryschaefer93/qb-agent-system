"""IMP-0012 evaluator — tool_loop (reclassified from structural 2026-06-01).

Tests that QB, after receiving a subagent return at runtime, summarizes it
into bullets (or scratchpad reference) in the next assistant turn instead of
re-quoting the original report.

The rule (from QB.agent.md Self-Prune section, IMP-0012):
> After reading a subagent report, immediately summarize it into 3–5 bullets
> in your next turn (or in the scratchpad). Treat the original report as
> discardable; do not re-quote it in subsequent turns.

Scoring per scenario:
  - PASS: at least one runSubagent call observed AND every post-runSubagent
          turn contains either:
            (a) a bullet-list summary (>=3 bullet markers), OR
            (b) a scratchpad/memory reference (memory tool call), OR
            (c) explicit summary header ("Subagent Summary", "QA Summary", etc.)
          AND none of those post-turns repeats >100 contiguous chars from the
          original mock return.
  - FAIL: post-runSubagent turn re-quotes >100 contiguous chars from the
          mock return, with no summary structure present.
  - PASS-with-note (inconclusive): no runSubagent calls within budget. Same
          IMP-0001 precedent.
"""

from __future__ import annotations

import re
from evaluators.tool_loop import LoopTrace


N_SAMPLES = 3
MAX_TURNS = 8


_BULLET_RE = re.compile(r"^\s*[\-\*\u2022]\s+", re.MULTILINE)
_SUMMARY_HEADERS = (
    "summary", "subagent summary", "qa summary", "qa findings",
    "key findings", "recap", "scratchpad",
)


def get_scenarios() -> list[dict]:
    return [
        {
            "id": "bugfix_post_qa",
            "prompt": (
                "The /api/orders endpoint returns 500 on payloads >2MB with a "
                "ValueError. Backend only. Quick patch. No broader audit. "
                "Scope approved. Proceed with the standard QA -> Dev pipeline."
            ),
            "expected": {"must_summarize": True},
        },
        {
            "id": "newpoc_post_arch",
            "prompt": (
                "Kick off a new POC for Northwind Insurance - claims intake portal "
                "with FastAPI + React + Azure SQL + Entra ID. Scope approved as-is. "
                "Proceed with the standard new-poc-setup pipeline."
            ),
            "expected": {"must_summarize": True},
        },
    ]


def _turns_after_runsubagent(trace: LoopTrace) -> list[dict]:
    post_turns = []
    saw_runsubagent = False
    for turn in trace.turns:
        if saw_runsubagent:
            post_turns.append(turn)
            saw_runsubagent = False
        for tc in (turn.get("tool_calls") or []):
            if tc.get("name") == "runSubagent":
                saw_runsubagent = True
                break
    return post_turns


def _has_summary_structure(content: str) -> bool:
    if not content:
        return False
    bullets = len(_BULLET_RE.findall(content))
    if bullets >= 3:
        return True
    lower = content.lower()
    return any(h in lower for h in _SUMMARY_HEADERS)


def _references_memory_tool(turn: dict) -> bool:
    for tc in (turn.get("tool_calls") or []):
        if tc.get("name") in ("memory", "resolveMemoryFileUri"):
            return True
    return False


def _runsubagent_returns(trace: LoopTrace) -> list[str]:
    returns: list[str] = []
    for turn in trace.turns:
        for tr in (turn.get("tool_results") or []):
            for tc in (turn.get("tool_calls") or []):
                if tc.get("name") == "runSubagent":
                    result = tr.get("result")
                    if result:
                        returns.append(str(result)[:1000])
    return returns


def _contains_long_quote(content: str, returns: list[str], min_len: int = 100) -> bool:
    if not content or not returns:
        return False
    for ret in returns:
        for i in range(0, max(1, len(ret) - min_len), 50):
            window = ret[i : i + min_len].strip()
            if len(window) >= min_len and window in content:
                return True
    return False


def check_scenario(trace: LoopTrace, scenario: dict) -> dict:
    expected = scenario.get("expected", {})
    if not expected.get("must_summarize"):
        return {"passed": True, "detail": "no summary check requested"}

    post_turns = _turns_after_runsubagent(trace)
    runsub_count = sum(
        1
        for turn in trace.turns
        for tc in (turn.get("tool_calls") or [])
        if tc.get("name") == "runSubagent"
    )

    if runsub_count == 0:
        return {
            "passed": True,
            "detail": (
                f"INCONCLUSIVE: QB never invoked a subagent within "
                f"{len(trace.turns)} turn(s); self-prune rule was not exercised. "
                f"tool_call_sequence={trace.tool_call_sequence}"
            ),
        }

    if not post_turns:
        return {
            "passed": True,
            "detail": (
                f"INCONCLUSIVE: {runsub_count} runSubagent call(s) observed but no "
                f"post-return assistant turn captured within budget"
            ),
        }

    returns = _runsubagent_returns(trace)

    failures = []
    for idx, turn in enumerate(post_turns):
        content = turn.get("content", "") or ""
        has_summary = _has_summary_structure(content) or _references_memory_tool(turn)
        has_long_quote = _contains_long_quote(content, returns)
        if not has_summary:
            failures.append(
                f"post-turn#{idx}: missing summary structure (no bullets/headers/memory)"
            )
        if has_long_quote:
            failures.append(
                f"post-turn#{idx}: contains long quote (>100 chars) from subagent return"
            )

    if failures:
        return {
            "passed": False,
            "detail": (
                f"VIOLATION ({runsub_count} runSubagent calls, "
                f"{len(post_turns)} post-turns): {failures[0]}"
            ),
        }
    return {
        "passed": True,
        "detail": (
            f"COMPLIANT: {runsub_count} runSubagent calls, "
            f"{len(post_turns)} post-turns all summarized"
        ),
    }
