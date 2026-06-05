---
id: IMP-0014
title: Classify eval_type and wire evaluators for unclassified IMPs
status: implemented
source: agent-status-2026-04-28
affects: [meta]
risk: low
created: 2026-04-28
updated: 2026-04-28
commit: 1df2811
eval_type: manual
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

Seven non-rejected IMPs (IMP-0001, 0002, 0003, 0005, 0008, 0012, 0013) have no `eval_type` assigned and no evaluator wired. Per `~/.copilot/EVAL-SYSTEM-PLAN.md`, IMPs cannot be shipped under the new flow without an eval_type — they have no baseline/post snapshot path, so `/Implement-Improvement` and `/Validate-IMP` can't operate on them. The execution-order backlog (IMP-0001+0012 next) is blocked behind this classification work.

## Proposal

Triage each unclassified IMP, set `eval_type` and `eval_id` in its frontmatter, and create the evaluator stub at `evaluators/custom/imp_XXXX.py` per the plan. Initial classification proposal:

- IMP-0001 (bounded subagent returns) → `tool_loop` — measure subagent return token sizes
- IMP-0002 (session memory scratchpad) → `behavioral` — confirm scratchpad writes appear and prompts shrink
- IMP-0003 (context checkpoints) → `structural` (presence of checkpoint blocks) + `behavioral` (fire at expected seams)
- IMP-0005 (session handoff protocol) → `behavioral` — trigger conditions fire and Handoff Brief shape is correct
- IMP-0008 (compact output shape) → `structural` — clean-run output matches compact form
- IMP-0012 (self-prune after reports) → `behavioral` — no re-quoting of prior reports in subsequent turns
- IMP-0013 (retro outputs IMP files) → `manual` — run a retro, observe IMP files appear

Confirm or adjust during the classification pass; the proposed types above are starting points, not commitments.

## Acceptance criteria

- [x] Each of IMP-0001, 0002, 0003, 0005, 0008, 0012, 0013 has `eval_type` and `eval_id` set in frontmatter
- [x] Non-manual IMPs have a stub at `evaluators/custom/imp_XXXX.py` that runs (even if checks are minimal at first)
- [ ] `/Agent-Status` shows zero IMPs in "needing evaluator setup"

## Validation plan

Re-run `/Agent-Status`; the "needing evaluator setup" line should report `none`. Spot-check by running the harness against one newly-wired evaluator to confirm it produces a baseline JSON.

## Eval Plan

- **Type:** manual
- **What we measure:** completeness — every IMP has eval_type set and (where non-manual) an evaluator stub that executes
- **Pass criteria:** all 7 IMPs classified; all non-manual stubs return a valid result JSON
- **Known limits:** classification choices may need revision once we attempt the actual implementation of each IMP

## Notes

This is a prerequisite for IMP-0001+0012 (next in execution order) and for the rest of the backlog. Closely related to IMP-0015 (define `validated` lifecycle criteria).
