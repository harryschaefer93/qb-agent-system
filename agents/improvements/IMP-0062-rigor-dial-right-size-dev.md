---
id: IMP-0062
title: Rigor dial — right-size ARCH/DEV/QA output to the deliverable class
status: implemented
source: review-2026-07-16
affects: [QB, ARCH, DEV, QA]
risk: medium
created: 2026-07-16
updated: 2026-07-19
commit: 1b30ae0
eval_type: structural
skip_validation: false
eval_id: imp_0062
eval_seed: 42
baseline_run: null
post_run: baselines/IMP-0062/20260719-175521-1b30ae0-post.json
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

- [x] CP2 Delivery line carries `rigor`; run-state records it (`pipeline start --rigor`,
      schema enum, status/resume exposure, `by_rigor` KPI segmentation); QB 438/440 lines
- [x] ARCH `tracks:` block includes per-track `test_budget` derived from rigor (tracks-block
      schema + run-state ledger both accept it; `set_tracks` carries it to worker prompts);
      BRIEF template + 3 playbooks carry rigor defaults
- [x] DEV + QA prompt sections implement budget/depth scaling; FDPO explicitly exempted
      from the dial ("rigor-independent" stated on every dial surface)
- [ ] Behavioral scenario: a "personal V1" prompt yields a plan with single/few tracks and
      a budgeted test plan (no warning-as-error, no 3-digit test counts) — **pending: the
      behavioral evaluator's expected_behavior vocabulary has no budget key; add the
      scenario pair with a rigor scorer at the next behavioral-eval run**
- [x] Negative: `rigor: poc` never weakens FDPO/auth/secret constraints in the plan
      (structural `fdpo_never_dialed` check; prompt text pins the exemption)
- [ ] One real `poc`-rigor run records a materially shorter DEV segment than the 07-13
      baseline shape (needs IMP-0058 phase timing) — elapsed-time criterion

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
- **2026-07-19 — IMPLEMENTED** (same session as IMP-0061, separate commit per ship-alone
  rule). Dial surfaces: QB CP2 Delivery line (`rigor:` token + defaults + FDPO exemption),
  ARCH §8 (`test_budget` per track + rigor sizing rules), DEV (Principle 2b honors the
  budget; no warning-as-error at `poc`), QA (depth scaling + over-delivery as a 🟡 finding),
  BRIEF §3 `Rigor:` field, 3 playbooks + README (`scope_defaults.rigor: hardened`).
  Plumbing: `pipeline start --rigor` (enum-refused), run-state `rigor` property,
  status/resume exposure, tracks-block + run-state schemas accept `test_budget`,
  `set_tracks` carries budgets into the ledger, `by_rigor` KPI segmentation
  (cycle time + DEV segment means; `dev_segment_minutes` from IMP-0058/0061 is the
  baseline metric). 4 new pytest cases; structural eval 9/9. Remaining: behavioral
  scenario pair (needs a rigor scorer key) + the first real `poc`-rigor run.
