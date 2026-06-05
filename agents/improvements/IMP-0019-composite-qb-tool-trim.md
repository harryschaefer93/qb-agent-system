---
id: IMP-0019
title: Composite-score QB tool trim (composite backfill reference)
status: accepted
source: eval-harness-phase-3
affects: [QB]
risk: low
created: 2026-05-08
updated: 2026-06-01
commit: null
eval_type: composite
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
rubric_path: null
calibration_path: null
calibration_min_agreement: 0.80
thresholds:
  speed_regression_pct: 50
sub_evals:
  - eval_type: structural
    eval_id: imp_0004
    weight: 0.7
    must_pass: true
  - eval_type: execution_metrics
    weight: 0.3
    must_pass: false
composite_pass_threshold: 0.7
---

## Problem

[IMP-0004](IMP-0004-trim-qb-tools.md) trimmed QB's tool list using a structural eval — presence/absence of expected tools in the frontmatter. That signal is necessary but not sufficient: a trim that breaks behaviour at runtime, or one that balloons cost via more turns / larger context, would still show as 4/4 structural checks passing. The harness ships a composite eval_type for exactly this case, but no IMP exercises it end-to-end.

## Proposal

Re-score the QB tool-trim work as a **composite** eval that rolls up two existing eval types:

| Sub-eval | Type | Weight | must_pass | Notes |
|---|---|---|---|---|
| `imp_0004` | structural | 0.70 | true | Presence/absence of expected tools (the original IMP-0004 checks). |
| (default) | execution_metrics | 0.30 | false | Cost/wall-time telemetry, advisory only — captures speed/cost as a signal without gating. |

The composite passes when `weighted_score ≥ 0.7` AND the structural sub-eval passes (its `must_pass=true` makes it a hard gate regardless of the weighted roll-up). The execution_metrics sub-eval is advisory: it appears in the rolled-up score but does not by itself fail the composite. Its regression gating still runs at the composite level via `compare_snapshots()`.

Per-IMP override: `speed_regression_pct: 50` instead of the default 25%. Structural sub-evals run in milliseconds and the default 25% threshold trips on harness-noise variance between runs; 50% is a defensible compromise that still catches real harness-level slowdowns.

This deliberately omits a rubric sub-eval to keep the scaffold runnable end-to-end without depending on IMP-0018's calibration set being finalised. Once IMP-0018 is validated, add a rubric sub-eval (e.g. weight 0.3) and rebalance.

## Acceptance criteria

- [ ] `evals run-imp IMP-0019 --baseline` captures a composite snapshot with `sub_snapshots` populated for both sub_evals
- [ ] `evals run-imp IMP-0019 --post` captures a comparable composite snapshot
- [ ] Composite verdict (`pass` / `partial` / `fail`) computes correctly from the weighted sub-scores and the `must_pass` flag on `structural`
- [ ] `evals run-imp IMP-0019 --compare` renders the Composite roll-up + Sub-evaluators table from the Phase 3 dashboard renderer

## Validation plan

Run `--baseline` on the current QB.agent.md, then `--post` after a no-op edit (touch the file). The composite verdict should be `pass`, `weighted_score` should be 1.0 (4/4 structural checks) × 0.7 + execution_metrics-passed × 0.3, and the Sub-evaluators table should show two rows.

## Eval Plan

- **Type:** composite
- **What we measure:** weighted_score (0–1), composite verdict (`pass` / `partial` / `fail`), per-sub-eval verdicts and scores. Cost roll-up at the composite level is the sum of sub-snapshot costs.
- **Pass criteria:** `weighted_score ≥ 0.7` AND the `structural:imp_0004` sub-eval passes (`must_pass=true`). Speed regressions > 50% on the composite cost block flip the comparison verdict to REGRESSION even when the per-snapshot metric block says `pass`.
- **Negative cases:** if the structural sub-eval fails (e.g. a forbidden tool is reintroduced into QB's frontmatter), the composite verdict must be `fail` regardless of how the execution_metrics sub-eval scores. The `must_pass=true` flag is what enforces this.
- **Rubric:** N/A (no rubric sub-eval in the scaffold).
- **Sub-evals:** `structural:imp_0004` (weight 0.7, must_pass) + `execution_metrics:default` (weight 0.3, advisory). The composite math lives in `runner/composite.py`; sub-eval execution is dispatched via `evaluators.dispatch()` in `runner/imp_runner.py::_run_composite`.
- **Known limits:** structural sub-eval is model-free; execution_metrics sub-eval (with no `eval_id` on the sub-spec) takes the model-free measurement path in `_run_execution_metrics`, so this composite runs without Foundry connectivity. Once a tool_loop or rubric sub-eval is added, Foundry auth becomes required.

## Results

<!-- Auto-populated by /Implement-Improvement and /Validate-IMP -->

| Metric | Baseline (mean ± σ, n) | Post (mean ± σ, n) | Delta | Regression? |
|---|---|---|---|---|
| weighted_score | ... | ... | ... | ... |
| verdict | ... | ... | ... | ... |
| structural:imp_0004 score | ... | ... | ... | ... |
| execution_metrics score | ... | ... | ... | ... |

**Quality / Speed / Cost summary** (Phase 1+ format):

- Quality: <weighted_score baseline → post (composite roll-up)>
- Speed:   <wall_time_ms baseline → post (Δ%, gated by speed_regression_pct=50)>
- Cost:    <cost_usd baseline → post (Δ%, advisory unless cost_regression_pct set)>

**Real-session evidence:** N/A for this scaffold (composite reuses IMP-0004's structural checks; real-session evidence lives on IMP-0004).

## Notes

**Accepted 2026-06-01.** Baseline this composite *against the post-9c90516 QB state* (the May/June MCP tool-palette expansion). The IMP-0004 structural sub-eval may need a refresh to reflect the current expected tool set before running `--baseline`, since QB's surface has grown since IMP-0004 was authored.

This is the canonical **composite** reference IMP. The sub-eval set is deliberately minimal so the harness can run it end-to-end without external dependencies:

- `structural:imp_0004` — reuses the existing evaluator at `evaluators/custom/imp_0004.py`. No new code path.
- `execution_metrics:default` — sub-spec omits `eval_id`, which routes through the model-free measurement branch in `_run_execution_metrics` (just records harness wall time + zero cost).

Once IMP-0018 is validated and its rubric calibration is finalised, extend `sub_evals` here with a rubric sub-eval (e.g. `eval_type: rubric, eval_id: imp_0018, weight: 0.3, must_pass: false`) and rebalance the structural + execution_metrics weights down. That will exercise the full three-way composite path (structural + rubric + execution_metrics).

The 50% `speed_regression_pct` override is intentional: with structural sub-evals running in milliseconds and execution_metrics-without-eval_id capturing only harness wall time, run-to-run variance in the harness itself can push the default 25% threshold over the line. 50% is a defensible compromise that still catches real harness-level slowdowns. Tighten this back to the global default when a model-calling sub-eval is added — at that point the wall-time signal becomes dominated by the model call and the threshold is meaningful again.
