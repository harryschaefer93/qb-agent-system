---
id: IMP-0060
title: Synthetic-first graduation gate with typed provenance and runtime confidence
status: implemented
source: user-approved-validation-debt-plan
affects: [imp, retro, meta]
class: fleet
risk: high
created: 2026-07-16
updated: 2026-07-17
commit: c244f1f
eval_type: structural
skip_validation: false
eval_id: imp_0060
eval_seed: 42
baseline_run: null
post_run: null
validation_evidence: []
manual_evidence: []
---

## Problem

The documented validated bar permits deterministic, synthetic, and surrogate evidence, but the
runner, confidence math, evidence schema, telemetry targeting, CLI, and agent workflows did not
enforce one consistent contract. Inconclusive runtime samples could appear green, 3/3 or 15/15
results could be treated as sufficient without the exact Wilson bound, provenance could not be
checked for drift, and several prompts still made chance real-session coverage mandatory.

## Proposal

Make synthetic-first graduation mechanical and backward compatible:

1. Normalize runtime assertions to `{passed, conclusive, detail}` and centrally enforce at least
   15 conclusive observations plus a Wilson 95% lower bound of 0.80, with zero conclusive failures.
2. Add canonical `validation_evidence` records with explicit source and artifact/commit/hash
   provenance while continuing to read legacy real-session `manual_evidence`.
3. Add `graduation-check` as the single mechanical four-bar and provenance/ancestry/staleness
   check for future automation.
4. Separate targeted runtime/post graduation gates from the structural-only `run-all-imps` gate.
5. Exclude superseded IMPs through parsed frontmatter rather than brittle text matching.

## Acceptance criteria

- [x] Runtime result normalization gives explicit `conclusive` priority, maps legacy
      `INCONCLUSIVE:` details to non-conclusive, and treats reported violations as conclusive.
- [x] Wilson 95% lower-bound aggregation uses hard defaults of 15 conclusive observations and
      0.80, with all-inconclusive, 14/14, 15/15, and any conclusive failure blocked; 16/16 passes.
- [x] Tool-loop and subagent-routing snapshots retain per-sample `conclusive` and publish
      conclusive count, passing count, Wilson lower bound, confidence verdict, and a hard
      confidence-aware `all_passed`.
- [x] Runtime confidence also requires every declared scenario to have at least one conclusive
      observation and zero conclusive failures, with durable coverage metrics recomputed by
      graduation.
- [x] Runtime snapshots persist the complete evaluator-declared scenario ID set; graduation
      reimports `get_scenarios()` and rejects missing, unknown, or duplicate IDs before confidence
      aggregation.
- [x] Snapshot comparison returns blocking `FAIL` for insufficient runtime confidence while
      preserving `REGRESSION` for actual quality/execution regressions; `run-imp --compare`
      exits nonzero for either.
- [x] `validation_evidence` accepts only deterministic, synthetic, surrogate, real_session, or
      inspection sources with explicit provenance; legacy real-session `manual_evidence` remains
      readable and qualifying without historical rewrites.
- [x] Evaluator and dataset/fixture SHA-256 helpers hash path plus content in deterministic
      ordering, and new snapshots record their artifact lists and hashes.
- [x] `graduation-check <IMP-ID>` plus `--all`, `--json`, and `--markdown` mechanically reports
      the four validated-bar points, commit validity/ancestry, hash staleness, and supersession.
- [x] Graduation checks respect structural/manual inspection rules, rubric calibration and score,
      composite verdicts, runtime confidence, typed evidence, and legacy real-session evidence.
- [x] Baseline/post snapshots and committed typed evidence are tracked and byte-identical to
      current HEAD; committed evidence records distinguish implementation, evaluated, and later
      first-containing artifact commits with evaluated → artifact → HEAD ancestry. Raw
      real-session artifacts remain ignored/untracked and omit artifact commits.
- [x] Composite rubric contribution requires passing calibration and score, including optional
      rubric sub-evals.
- [x] Composite specs reject duplicate sub-eval snapshot keys before a dict overwrite can erase a
      must-pass failure.
- [x] Behavioral IMPs can produce targeted `run-imp` snapshots through a custom single-turn
      Foundry evaluator convention with per-sample confidence metrics.
- [x] `ImpFrontmatter` safely parses validation, lifecycle, class/risk/date, and supersession
      fields without unsafe casts.
- [x] Telemetry auto-targeting excludes parsed `superseded_by` IMPs, including IMP-0004.
- [x] README, governing plan, template, CLI agents, and VS Code fallback prompts consistently say
      targeted evidence gates graduation, `run-all-imps` is structural-only, and real sessions
      are opportunistic corroboration unless a criterion is irreducibly manual.
- [x] Skip-validation workflows still commit bookkeeping, run authoritative graduation, and only
      flip status on PASS in a later validation commit.
- [x] Graduation requires the IMP and CHANGELOG files themselves to be tracked and byte-identical
      to HEAD; workflows rerun after the status commit and immediately correct failed validation
      status.
- [x] `execution_metrics` graduation requires a committed declared baseline and an exact passing
      baseline/post comparison.
- [x] Focused pytest coverage exercises confidence boundaries, normalization, all four graduation
      bars, legacy and typed evidence, stale hashes, Git ancestry, and superseded filtering.

## Validation plan

Run the focused pytest files for the shared confidence/graduation contract, then run the
structural fleet gate. After the implementation is reviewed and committed, capture the IMP-0060
post snapshot and run `graduation-check IMP-0060`; do not mark validated until that committed
snapshot, CHANGELOG SHA, and implementation-commit ancestry all pass.

## Eval Plan

- **Type:** structural
- **What we measure:** durable runner/CLI symbols, exact Wilson boundary behavior, frontmatter
  contract, telemetry supersession parsing, and aligned policy surfaces.
- **Pass criteria:** all structural checks pass; focused pytest and structural fleet gate green.
- **Negative cases:** 15/15 must remain below 0.80; inconclusive samples never count as passes;
  stale evidence hashes, wrong artifact commits, and invalid evaluated/artifact ancestry block
  graduation.
- **Known limits:** structural evaluation proves the mechanism and policy surfaces, not a future
  IMP's behavioral claim. Each non-structural IMP still needs its own targeted evidence gate.

## Results

Implementation complete in the working tree. Post snapshot intentionally deferred until the
implementation commit exists, so provenance can reference a real implementation SHA.

## Notes

- The user explicitly approved a synthetic-first graduation process and blanket source-tagged
  evidence/status updates. The rationale is throughput with integrity: use the cheapest evidence
  that exercises the same rule, retain explicit provenance, and reserve mandatory real sessions
  for production-only behavior, elapsed operation, physical interaction, picker availability, or
  genuine user judgment.
- This IMP does not weaken any existing acceptance criterion, alter any existing
  `skip_validation` value, rewrite historical evidence, or implement IMP-0061/IMP-0057 scope.
