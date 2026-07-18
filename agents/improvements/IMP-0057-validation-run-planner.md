---
id: IMP-0057
title: Validation-run planner — target real sessions at the validation debt
status: proposed
source: review-2026-07-15
affects: [imp, retro, meta]
risk: low
created: 2026-07-15
updated: 2026-07-15
commit: null
eval_type: structural
skip_validation: false
eval_id: imp_0057
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

Validation debt is now the dominant backlog item: ~22 IMPs sit at `implemented` vs 21
`validated`, and the bottleneck is no longer tooling (IMP-0052 fixed telemetry; IMP-0034
Job 2 runs backfill nightly) — it's **session shape**. The nightly-2026-07-15 report
scored 4 real sessions and returned *inconclusive* for every scorer whose feature never
fired: IMP-0020 ("no recommended:true options observed"), IMP-0039 ("no resume pre-flight
fingerprints"), IMP-0042 ("no small-task-type CP2 observed" — all 4 sessions were
new-poc-setup / full-delivery / feature-request shapes that skip the design preview).
Real runs happen ~2/week; if their shapes are left to chance, high-risk debt (IMP-0028,
gates waived, zero real evidence at `standard`) ages indefinitely.

## Proposal

Make the next real run a deliberate validation instrument:

1. **Validation debt table** (deterministic, from live IMP frontmatter — same pattern as
   `backfill --auto` target derivation): for each `implemented` non-structural IMP, emit
   the cheapest session shape that would exercise it — task type(s), autonomy level,
   features to touch, and the registered scorer that would capture it. Render in:
   (a) `imp` status mode, (b) the nightly report (Job 2 appends the table), and
   (c) the IMP-0055 morning briefing once it exists.
2. **Kickoff hint in the imp agent** (not QB — keep QB's line budget for delivery
   behavior): when the user asks "what should I run next" / invokes imp status, the
   answer includes 1–3 concrete run suggestions, e.g. "a bug-fix on PilotApp at
   `standard` discharges 0042 (design preview) + 0028 (consolidated CP2) + 0051 (ledger);
   kill and resume it once to discharge 0039."
3. **Debt burndown line in retro:** retro Phase 0 reports implemented-vs-validated count
   and the age of the oldest unvalidated high-risk IMP, so drift is visible weekly.

Explicitly NOT: fabricated/synthetic sessions dressed as real evidence (the `validated`
bar's provenance rules stand), and no new agent — this is a table + prompt lines on
existing surfaces.

## Acceptance criteria

- [ ] Debt table derives from live frontmatter (no hand-maintained list) and renders in
      imp status output + nightly report
- [ ] Each row names ≥1 concrete session shape + the scorer that would capture it
- [ ] Retro reports the burndown line
- [ ] One real run chosen via the table produces ≥1 graduation (or a recorded fail —
      either way the debt moves)

## Validation plan

Use the table to plan the IMP-0053 pilot runs (see EXECUTION-ORDER Wave 6 note): pick
pilot tasks whose shapes overlap the debt table's top rows. Success = the pilot week
graduates ≥2 IMPs that nightly backfill alone had left inconclusive.

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0057.py`) — table generation is
  deterministic given frontmatter; check derivation, rendering hooks, retro line.
- **What we measure:** table rows match `implemented` non-structural IMP set exactly;
  each row carries task-type + scorer fields.
- **Pass criteria:** all structural checks; drift check fails if a row is hand-edited.
- **Known limits:** the "cheapest session shape" mapping is judgment encoded per-IMP
  (a `validation_hint` frontmatter field or a static map in the generator) — it can be
  wrong; a run that fails to fire the scorer just yields another inconclusive, which the
  burndown line surfaces.

## Notes

- Source: 2026-07-15 review of IMP-0049–0056 (validation-debt systemic finding).
- Complements IMP-0034 Job 2 (which *scores* whatever sessions exist) by shaping *which*
  sessions come to exist. Feeds IMP-0055 (briefing section) — ship order flexible, but
  before or alongside the IMP-0053 pilot so the pilot doubles as the validation sprint.
