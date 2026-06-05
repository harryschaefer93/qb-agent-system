---
id: IMP-0017
title: Add /IMP orchestrator command for end-to-end improvement workflow
status: implemented
source: agent-status-2026-04-28
affects: [meta]
risk: low
created: 2026-04-28
updated: 2026-04-28
commit: _pending_
eval_type: manual
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

The improvement system has four discrete prompts (`/Agent-Status`, `/Create-IMP-Eval`, `/Implement-Improvement`, `/Validate-IMP`) but no orchestrator. To ship one IMP, the user has to:

1. Run `/Agent-Status` to identify the next candidate
2. Manually flip status from `proposed` → `accepted` if needed
3. Manually invoke `/Create-IMP-Eval` if no evaluator is wired
4. Manually invoke `/Implement-Improvement`
5. Manually invoke `/Validate-IMP` after a real session

Five context switches per IMP, easy to skip a step, no enforced sequencing. The system has the building blocks but no glue.

## Proposal

Add `/IMP` as a thin orchestrator that walks one IMP through the full lifecycle in a single invocation. Design choices:

- **Single IMP per invocation.** Batching across IMPs in one session re-creates the context-bloat the QB IMPs are trying to fix.
- **Delegate, don't re-implement.** `/IMP` reads and follows the existing three prompts rather than duplicating their logic.
- **Hard stops.** User approval after pick; user approval before flipping `proposed` → `accepted`; automatic stop on regression (`status: needs-review`).
- **No auto-loop.** Ends after one IMP; user re-invokes for the next.

Lives at `~/AppData/Roaming/Code/User/prompts/imp.prompt.md`.

## Acceptance criteria

- [x] `/IMP` prompt file exists with `name: IMP` and a clear description
- [x] Picks next IMP from execution order when invoked without args
- [x] Confirms with user before doing anything (HARD STOP at Step 2)
- [x] Delegates to `/Create-IMP-Eval`, `/Implement-Improvement`, `/Validate-IMP`
- [x] Stops cleanly on regression (`status: needs-review`)
- [x] Single-IMP-per-invocation rule documented
- [ ] First real run through `/IMP` completes successfully on a real backlog item

## Validation plan

Use `/IMP` to ship IMP-0016 (smallest of the meta-IMPs — prompt-only edit to `agent-status.prompt.md`). Confirm:
- Pick + confirm gate fires
- `eval_type: manual` skips eval scaffolding cleanly
- `/Implement-Improvement` runs and updates the IMP
- `/Validate-IMP` runs (or stops cleanly waiting for evidence)
- Final report is compact and accurate

## Eval Plan

- **Type:** manual
- **What we measure:** does the orchestrator successfully ship a real IMP without manual intervention beyond the documented hard stops?
- **Pass criteria:** at least one IMP ships end-to-end via `/IMP` with no manual step outside the gates
- **Known limits:** orchestrator-only; correctness depends on the delegated prompts. If a delegated prompt has a bug, `/IMP` inherits it.

## Notes

Built ad-hoc on 2026-04-28 during the same session that produced IMP-0014/0015/0016 — filed retroactively as `implemented` rather than going through the normal `proposed → accepted` flow because the orchestrator itself didn't yet exist to ship it. Future meta-system changes should go through `/IMP`.

Closely related to `agent-status.prompt.md`: that prompt's "Recommended Next" section should reference `/IMP` as the action verb. Worth a small follow-up.
