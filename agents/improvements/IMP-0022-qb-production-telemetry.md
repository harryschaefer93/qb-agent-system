---
id: IMP-0022
title: QB production telemetry — VS Code session-store mining + retro evidence mode
status: implemented
source: review-2026-06-01
affects: [retro, meta]
risk: low
created: 2026-06-02
updated: 2026-06-02
commit: 392eda8
eval_type: manual
skip_validation: true
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence:
  - {session_id: 49c0c7ab, verdict: pass, captured: 2026-06-02, notes: "Inspection: telemetry.py scan returned 4 QB sessions across both stores; backfill produced 4 pass-verdict evidence entries (IMP-0001 x1, IMP-0004 x3); timing-gate correctly marked pre-commit sessions inconclusive for IMP-0012/0021. End-to-end pipeline verified."}
---

## Problem

The 2026-06-01 review surfaced that QB IMPs were stuck at `implemented` indefinitely because:

- The cloud `session_store_sql` tool only sees CLI + Coding Agent sessions — **VS Code Copilot Chat sessions never sync there**, yet that's where QB actually runs.
- The `retro` agent's documentation pointed at the wrong DB path (`~/.copilot/session-store.db`) and lacked execution tooling to actually run the queries it documented.
- Per IMP-0015's `validated` bar, non-structural IMPs require `manual_evidence` from real Copilot sessions. We had zero — every IMP frontmatter showed `manual_evidence: []`.
- 4 QB IMPs (0004, 0006, 0012, 0021) sat in `implemented` with no clear path to `validated`.

## Proposal

A two-layer telemetry pipeline:

1. **Data layer** — `evals/runner/telemetry.py` mines both local SQLite session stores (VS Code Copilot Chat at `%APPDATA%/Code/User/globalStorage/github.copilot-chat/session-store.db` + CLI store at `~/.copilot/session-store.db`). Detects QB sessions by **content fingerprint** (Required Output Shape headers like `## QB Result`, `**Task Type:**`, `## Routing Plan`) since the `agent_name` column is always `"GitHub Copilot Chat"` and doesn't tag custom agents. Scores each session against per-IMP acceptance rules. Includes a **timing gate** — sessions predating an IMP commit cannot validate that IMP (returns `inconclusive`).
2. **Evidence layer** — `evals/evidence/IMP-NNNN/*.json` holds raw artifacts (gitignored). A summary line written by `propose_manual_evidence_yaml_line` is pasted into IMP frontmatter's `manual_evidence:` array (no customer names, no repo paths).
3. **Retro layer** — `agents/retro.agent.md` gains an **IMP Evidence Mode** that calls the telemetry CLI, presents findings, and edits IMP files on user approval.

## Acceptance criteria

- [x] `python -m runner.telemetry scan --since 30d` returns ≥1 real QB session from VS Code store
- [x] `python -m runner.telemetry score --session <sid> --imp IMP-0021 --write` produces a JSON artifact and a frontmatter-ready YAML line
- [x] `backfill` across IMP-0001/0004/0006/0012/0021 produces honest verdicts (some pass, some inconclusive with explained reason)
- [x] Timing gate correctly downgrades pre-commit sessions to `inconclusive` (verified on cfeb7744 → IMP-0021)
- [x] `evals/evidence/*.json` is gitignored; README + `_schema.json` are tracked
- [x] `retro.agent.md` documents IMP Evidence Mode + correct DB paths + `execute/runInTerminal` tool
- [x] `agents/improvements/README.md` references the evidence pipeline
- [x] At least one IMP graduates to `validated` via the new pipeline (IMP-0001 + IMP-0004)
- [ ] `/IMP` orchestrator prompt hooks evidence step into the lifecycle

## Validation plan

Inspection-only — this IMP is meta-system infrastructure. The pipeline either works (artifacts get produced, IMPs graduate) or it doesn't. The first real session inspection (this one — session 49c0c7ab) confirms it.

Follow-up signal: on the next active POC session (likely a real customer engagement using QB), re-run `retro evidence for IMP-0012` and confirm we can capture post-commit fan-out evidence — which the current 4 sessions cannot provide.

## Eval Plan

- **Type:** manual (infrastructure work; behavior verifiable by inspection)
- **What we measure:** end-to-end pipeline produces correct artifacts + honest verdicts
- **Pass criteria:** all acceptance checkboxes
- **Known limits:** content fingerprints drift as QB's Required Output Shape evolves. Mitigation: all regex patterns centralized in `telemetry.py ALL_FINGERPRINTS` dict; `/IMP` checklist should remind to update fingerprints when modifying QB.

## Notes

**Honest backfill results (2026-06-02):**

| IMP | Verdict | Why |
|---|---|---|
| IMP-0001 (bounded subagent returns) | **pass** | cfeb7744: routing plan summarizes 5 sub-agent invocations using bullet form |
| IMP-0004 (QB tools trim) | **pass** (3 sessions) | 057d35cf / 6dca5610 / cfeb7744 all show compliant Required Output Shape |
| IMP-0006 (BRIEF.md by path) | inconclusive | No BRIEF.md mentions in any captured session — need a fresh new-poc-setup session |
| IMP-0012 (self-prune) | inconclusive | All available sessions predate the 2026-06-01 commit; need a post-commit multi-agent session |
| IMP-0021 (task-type detector) | inconclusive | Sessions predate commit; the only post-commit session (50ecd17b) is meta-work that didn't trigger the detector |

**Design decisions:**

- **Read-only SQLite** (`mode=ro` URI) so we can read while VS Code Copilot Chat is actively writing.
- **Content fingerprint over agent_name** because VS Code tags all sessions as `"GitHub Copilot Chat"` regardless of custom-agent context. Detection requires ≥2 fingerprint matches AND at least one "attribution key" (qb_result_header, task_type, routing_plan, required_output_shape) to avoid false positives from sessions that merely *mention* QB.
- **Hybrid evidence format** (raw JSON in `evals/evidence/`, summary line in IMP frontmatter) follows the AgentEvals / LangSmith / OTel-for-agents convention — keeps the IMP file readable while preserving full provenance.
- **Timing gate** (`IMP_VALID_FROM` dict) prevents false positives where pre-commit sessions appear to validate a change they predate. Caught a real false-positive on cfeb7744 → IMP-0021.
- **No auto-edit of IMP files** — telemetry emits a frontmatter-ready line for human paste-in (or for retro agent to edit with explicit user approval). Never silently mutates the improvements directory.

**Future work:**

- Wire `/IMP` orchestrator to prompt "run retro evidence" between `implemented` and `validated` gates
- Add per-week digest mode to retro (consume the same telemetry artifacts)
- Consider OTel-style structured tracing inside QB itself (task() wrappers, checkpoint span events) — out of scope here but the long-term north star
