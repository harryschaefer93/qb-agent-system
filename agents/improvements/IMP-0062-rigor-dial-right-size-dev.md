---
id: IMP-0062
title: Rigor dial — right-size ARCH/DEV/QA output to the deliverable class
status: proposed
source: review-2026-07-16
affects: [QB, ARCH, DEV, QA]
risk: medium
created: 2026-07-16
updated: 2026-07-16
commit: null
eval_type: structural
skip_validation: false
eval_id: imp_0062
eval_seed: 42
baseline_run: null
post_run: null
validation_evidence: []
manual_evidence: []
---

## Problem

The fleet builds everything at production rigor regardless of what was asked. Evidence:
run `PilotApp-20260713-0837`, scope literally "**Personal V1**; public sources only…" —
delivered as a 4-track monorepo with **~576 .NET tests + 53 frontend tests**, warning-as-
error builds, Durable Functions, evidence gates. That rigor consumed the bulk of a ~6h
DEV segment (and a QA deep-review after it) on a personal-use POC. DEV.agent.md says
"Working > Perfect — ship it" and "POCs need to impress, not be perfect", but nothing
operationalizes it: ARCH sizes structure and DEV sizes test suites by habit, and QA
treats maximal coverage as unconditionally good. Gold-plating is invisible because no
artifact records what rigor was *intended*.

## Proposal

1. **`rigor: poc | hardened | production` pinned at CP2.** One token added to the
   IMP-0051 CP2 Delivery line (branch/push/deploy/**rigor**). Defaults: `poc` for
   personal/demo repos, `hardened` for customer-facing POCs (FDPO + error handling +
   happy-path tests), `production` only on explicit request. BRIEF template gains a
   `Rigor:` field; playbooks (IMP-0046) carry per-playbook defaults. Recorded in
   run-state so retro/KPIs can segment cycle time by rigor.
2. **ARCH sizes to rigor.** At `poc`: smallest structure that demos (single track unless
   size forces fan-out; no monorepo ceremony), and the `tracks:` block carries a
   **per-track test budget** (e.g. `poc`: smoke + critical-path only, order-of-10s not
   100s). `hardened`/`production` scale up explicitly.
3. **DEV honors the budget.** At `poc`: happy path + budgeted smoke tests, no
   warning-as-error, no exhaustive matrix. FDPO and secret rules are rigor-independent
   (never relaxed).
4. **QA scales review depth and polices over-delivery.** `poc` → fast-check;
   `hardened`+ → deep-review. Output materially exceeding the test budget is reported as
   a **finding** ("over-delivered vs rigor=poc: 576 tests vs budget ~30"), not a virtue.

## Acceptance criteria

- [ ] CP2 Delivery line carries `rigor`; run-state records it; QB within line cap
- [ ] ARCH `tracks:` block includes per-track test budget derived from rigor; BRIEF
      template + 3 playbooks carry rigor defaults
- [ ] DEV + QA prompt sections implement budget/depth scaling; FDPO explicitly exempted
      from the dial
- [ ] Behavioral scenario: a "personal V1" prompt yields a plan with single/few tracks and
      a budgeted test plan (no warning-as-error, no 3-digit test counts)
- [ ] Negative: `rigor: poc` never weakens FDPO/auth/secret constraints in the plan
- [ ] One real `poc`-rigor run records a materially shorter DEV segment than the 07-13
      baseline shape (needs IMP-0058 phase timing)

## Validation plan

Structural checks + one behavioral scenario pair (poc vs production prompt → plans differ
on structure/test language, agree on FDPO). Real-run corroboration: next personal-repo
run at `rigor: poc`. Irreducibly manual: judging that the poc build still "demos well" —
user verdict at handoff.

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0062.py`) + behavioral scenario pair.
- **What we measure:** presence/wiring of the dial across QB/ARCH/DEV/QA + BRIEF/playbooks;
  behavioral: plan-shape divergence by rigor; FDPO invariance.
- **Pass criteria:** structural green; behavioral pair discriminates (poc plan omits
  production-rigor markers, production plan retains them); FDPO markers present in both.
- **Negative cases:** rigor=poc prompt containing "skip auth" still refuses key-based auth.
- **Known limits:** budget compliance in a real run is judged from artifacts (test counts
  in track reports), not enforced mechanically in v1.

## Notes

- Filed by the 2026-07-16 review. Companion to IMP-0061 (parallelize the work) — this IMP
  shrinks the work itself; together they attack the 80–97%-of-wall-clock DEV segment.
- Touches 4 agent prompts → ship alone per working-order rule, after IMP-0058 addendum
  (measurement first) and around the IMP-0053 pilot (pilot tasks can run at `poc`).
