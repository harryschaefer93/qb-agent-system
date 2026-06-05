---
id: IMP-0003
title: Add Context Checkpoints to QB pipeline
status: validated
source: review-context-window-2026-04
affects: [QB]
risk: low
created: 2026-04-27
updated: 2026-06-03
commit: 4fd9883
eval_type: structural
skip_validation: true
eval_id: imp_0003
eval_seed: 42
baseline_run: baselines/IMP-0003/20260603-141212-f051c67-baseline.json
post_run: baselines/IMP-0003/20260603-141243-f051c67-post.json
manual_evidence: []
---

## Problem

There is no signal — to QB itself or to the user — that prior tool outputs are no longer needed. Long pipelines drift toward context overload silently.

## Proposal

Add a "Context Checkpoints" section to QB. After each of these events, QB emits a `## Checkpoint` block (≤200 tokens) summarizing pipeline state, then explicitly states "Prior tool outputs may be discarded":

- QA Phase complete (before approval gate)
- All quality gates passed
- Iteration cycle complete
- Diagram phase complete
- Merge gate passed (after DEV fan-out)

Mirrors Claude Code's `/compact` semantics, adapted to the orchestrator pattern.

## Acceptance criteria

- [x] New "Context Checkpoints" section in `agents/QB.agent.md` *(Phase 1 commit — section added under Subagent Return Discipline, after Session Scratchpad)*
- [x] Checkpoint block format is templated (so QB emits consistent shape) *(template + `Prior tool outputs may be discarded.` discard line specified verbatim)*
- [ ] At least one real session where checkpoints fire at expected seams *(deferred — gather via retro evidence mode on next real POC session)*

## Validation plan

Run a `bug-fix` with one iteration cycle. Verify checkpoints appear at QA-complete, gates-pass, and post-iteration. Run a `new-poc-setup` and verify diagram + merge-gate checkpoints fire.

## Notes

Pairs with IMP-0005 (Session Handoff Protocol) — checkpoints are the lighter-weight cousin that fires more often.
