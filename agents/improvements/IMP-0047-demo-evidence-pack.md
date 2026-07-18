---
id: IMP-0047
title: Demo evidence pack — browser-verified demo flows embedded in HANDOFF.md
status: implemented
source: review-2026-07-13
affects: [QA, DOCS]
risk: low
created: 2026-07-13
updated: 2026-07-13
commit: b0ccace
eval_type: manual
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

Delivery ends with docs and a push, but nothing proves the demo *works* — the first end-to-end
drive of the deployed POC is often demo day itself. QA's Playwright palette (and the July-2026
GA of agentic browser tools) already supports driving the app; the pipeline just never demanded
evidence.

## Proposal

QA `deep-review` on `customer-handoff`/`full-delivery` additionally produces a **demo evidence
pack**: drive every demo flow end-to-end in the browser; per flow, a screenshot to
`docs/demo-evidence/<flow>.png` + pass/fail + verified timestamp; an undriveable flow is a
blocker. DOCS embeds the table + screenshots in HANDOFF.md ("Verified Demo Flows") and flags a
missing pack back to QB instead of shipping without it. `pipelines.yaml` carries the artifacts
for both task types. Extends the `demo-prep` skill's checklist.

## Acceptance criteria

- [ ] QA.agent.md carries the Demo Evidence Pack contract; pipelines.yaml requires it for both delivery task types
- [ ] DOCS embeds the evidence and refuses silent omission
- [ ] One real customer-handoff produces HANDOFF.md with embedded, timestamped screenshots
- [ ] A deliberately broken flow surfaces as a blocker before REPO packaging

## Validation plan

One real (or staged) customer-handoff run; break one flow deliberately to confirm the blocker
path. Customer-visible payoff: HANDOFF.md shows dated proof the demo works.

## Eval Plan

- **Type:** manual (browser-driven behavior; artifacts inspectable)
- **What we measure:** pack presence/completeness per delivery run; blocker discipline
- **Known limits:** flows must be enumerable from HANDOFF/demo script; free-form demos need a
  named flow list first.

## Notes

- Source: 2026-07-13 supercharge review (July platform sweep — browser tools GA). Wave 4.
