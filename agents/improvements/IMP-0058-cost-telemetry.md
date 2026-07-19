---
id: IMP-0058
title: Cost telemetry — populate run-record cost estimates + delegation credit spend
status: implemented
source: review-2026-07-15
affects: [meta, retro]
risk: low
created: 2026-07-15
updated: 2026-07-19
commit: a977df5
eval_type: structural
skip_validation: false
eval_id: imp_0058
eval_seed: 42
baseline_run: null
post_run: baselines/IMP-0058/20260719-152938-a977df5-post.json
manual_evidence: []
---

## Problem

`cost_estimate_total: null` on every run record and in every KPI rollup (evidence:
nightly-2026-07-15 — both real runs, and the 7d KPI aggregate). Meanwhile the system
keeps making cost-motivated decisions with no measurement behind them: IMP-0049's
three-tier model economy claims volume-agent savings ("cost a secondary factor" — but a
factor), IMP-0053's CP2 delegation option is supposed to carry a "cost note (AI
credits)", and IMP-0055's KPI section wants delegation economics. Every one of those is
currently a guess. IMP-0056's adoption criteria even say "measure, don't guess" — there
is nothing to measure with.

## Proposal

Cheapest credible proxy first, refine later:

1. **Request-count proxy per session:** the IMP-0052 JSONL source already yields
   per-session model requests (orchestrator + `-subN` splits carry the dispatching
   agent). Count requests × tier weight (judgment/volume/recon multipliers from the
   IMP-0049 assignment table, weights in `evals/config.yaml` — config, not code) →
   `cost_estimate_total` on the run record at run completion / backfill time.
2. **Delegation credit spend:** when `delegations[]` (IMP-0053) exists, record premium
   request / AI-credit usage per delegation — from `gh` billing/usage API if it exposes
   per-session figures, else a per-dispatch flat estimate from the plan's published
   credit model, marked `estimated: true`.
3. **Render everywhere KPIs already render:** `runner.telemetry kpi` (per-run + 7d
   aggregate + by-task-type), nightly report, morning briefing (IMP-0055), retro Phase 0.
4. **First consumer, recorded in this IMP's Results:** the IMP-0049 one-week retro
   compare (~2026-07-21) reports old-vs-new fleet cost alongside cycle time — the model
   refresh's economy claim gets a number.

Explicitly NOT: exact dollar accounting (Copilot billing doesn't expose per-request
dollars) — the field name stays `cost_estimate_*` and units are documented as weighted
request counts unless/until a real billing source exists.

## Addendum (2026-07-16): per-phase wall time rides along

Run-state phase entries stamp `started == finished` (both written at phase completion),
so cycle time cannot be decomposed — the 2026-07-16 review had to reconstruct DEV-segment
durations from report-file mtimes to discover DEV is 80–97% of wall clock (6h05m serial
tracks in `PilotApp-20260713-0837`; 5h32m in `PilotApp-webpublic-20260714`). Same
telemetry surface, same consumers, so it lands here: the driver records real `started`
at phase dispatch; `kpi`/nightly render **per-phase and per-track wall time** (DEV
segment is the headline number). This is the measurement prerequisite for IMP-0061
(parallel tracks) and IMP-0062 (rigor dial) to prove their savings.

## Acceptance criteria

- [x] Phase entries record real `started` at dispatch (not completion); per-track phases
      included; `kpi` + nightly render per-phase wall time with DEV segment called out
- [x] New/backfilled run records carry non-null `cost_estimate_total` derived from
      transcript request counts × config tier weights
- [x] `kpi` renders cost per run, 7d total, and by-task-type; nightly report shows it
- [x] Units + methodology documented where the field is defined (schema comment + EVAL-SYSTEM-PLAN)
- [ ] Delegation rows get a spend figure (real or `estimated: true`) once IMP-0053 lands
- [ ] One week of KPIs with non-null cost; IMP-0049 retro compare cites them

## Validation plan

Backfill the two July real runs (PilotApp-20260713-0837, PilotApp-webpublic-20260714)
as the first non-null records; sanity-check the tier split against the known 11-dispatch
overnight run (486 tool executions, mixed QB/DEV/QA traffic). Then let nightly Job 2
carry it forward unattended.

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0058.py`) — schema field populated,
  config weights present, kpi/nightly render paths emit the fields.
- **What we measure:** non-null rate on new run records; presence of units doc.
- **Pass criteria:** structural checks green; backfilled July runs non-null.
- **Known limits:** proxy, not dollars — good for *relative* comparisons (old vs new
  fleet, local vs delegated, task-type mix), not invoices. Subagent attribution depends
  on the IMP-0052 `-subN` split remaining accurate.

## Notes

- Source: 2026-07-15 review of IMP-0049–0056 (cost blind spot across 0049/0053/0055/0056).
- Sequencing: independent of Wave 6 steps 1–2; ship alongside IMP-0055 so the briefing's
  KPI section is born with a cost column. The delegation-spend part (item 2) activates
  only after IMP-0053.
- **Implemented 2026-07-19** (backlog-review session): `pipeline dispatch` verb stamps real
  phase starts (idempotent; `already_dispatched` refusal protects the true start across
  retries; legacy completion-stamp fallback unchanged, 6 new driver tests). `runner.telemetry
  cost` derives per-agent weighted request counts from IMP-0052 sessions (`-subN` summary
  prefix → agent; main-session anchor claims its subs) against the `config.yaml cost_model:`
  block; `--write` persists the additive `cost_estimates` key; nightly runs it before kpi.
  `phase_durations` + `dev_segment_minutes` (+ `_mean`) render in kpi/safe outputs — null for
  legacy `started == finished` stamps, never fabricated zeros. Schema also gained the
  IMP-0063 `reconstructed`/`reconstruction` provenance fields it had been missing.
- **Backfill evidence 2026-07-19:** PilotApp-20260713-0837 → cost 96.0 (14 sessions, qb tier),
  phase starts reconstructed from prior-phase finishes + repo-map mtime (caveats recorded in
  the run record's `reconstruction` block; DEV segment 419.4 min ≈ the review's ~7h estimate);
  PilotApp-webpublic-20260714 → cost 51.25 with a realistic 7-agent split (qb 24 / dev 21 /
  infra 3 / qa 1 / repo 1 / docs 1 / scout 0.25). 7d KPI now shows cost 147.25 and
  DEV-segment means. Remaining open boxes: delegation spend (gated on IMP-0053) and the
  one-week-of-KPIs / IMP-0049 retro citation (elapsed-time criterion, ~2026-07-21).
