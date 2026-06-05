---
id: IMP-0008
title: Compact Required Output Shape on fully-clean runs
status: rejected
source: review-context-window-2026-04
affects: [QB]
risk: low
created: 2026-04-27
updated: 2026-06-01
commit: null
eval_type: structural
eval_id: imp_0008
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

QB's Required Output Shape is verbose (audit-grade). On a fully-clean pipeline run with no escalations, most fields are noise.

## Proposal

Add a compact form for clean runs:

```
Task / Classification / Scope / Files Changed / Gates / QA Status
```

Use the full shape only when escalations, blockers, gate bounces, or scope creep occurred.

## Verdict — REJECTED (2026-06-01)

Self-flagged in original draft as "mild value, opportunistic only, don't make a dedicated commit." The output shape emits once per pipeline so token savings are negligible vs. the cost of a dedicated IMP cycle (baseline + implement + post-eval + validate).

**Disposition:** If a future edit to QB (e.g., IMP-0003 context-checkpoints or IMP-0005 session-handoff) is already touching the Required Output Shape section, the compact-form rider can ride along as a one-line addition. No standalone implementation.

## Acceptance criteria

- [ ] Compact form documented in QB
- [ ] Trigger condition explicit ("clean run" = no escalations + no gate bounces + 0 iteration cycles)

## Validation plan

Just check that next clean run uses the compact form.
