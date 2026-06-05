---
id: IMP-XXXX
title: <short title>
status: proposed
source: ad-hoc
affects: []
risk: low
created: 2026-04-27
updated: 2026-04-27
commit: null
# Eval wiring (see ~/.copilot/EVAL-SYSTEM-PLAN.md). Missing fields default to eval_type: manual.
eval_type: structural          # structural | tool_loop | subagent_routing | behavioral | quality | rubric | execution_metrics | composite | manual
skip_validation: false         # true = prompt-only / deterministic change verifiable by file inspection; auto-validates after implement
eval_id: null                  # slug matching evaluators/custom/imp_XXXX.py
eval_seed: 42                  # fixed per IMP for determinism (non-structural only)
baseline_run: null             # most recent baselines/IMP-XXXX/<ts>-<sha>.json
post_run: null                 # most recent post snapshot
manual_evidence: []            # required for manual; recommended for any non-structural to confirm in real Copilot
                               # shape: [{session_id, url, verdict: pass|fail|mixed, notes}]

# --- Phase 2: Rubric (only when eval_type is rubric or quality+rubric) ---
rubric_path: null              # e.g. evaluators/rubrics/imp_XXXX.md (markdown rubric per §3b)
calibration_path: null         # e.g. evaluators/rubrics/imp_XXXX.calibration.jsonl (5+ hand-graded examples)
calibration_min_agreement: 0.80  # snapshot rejected if judge agreement below this

# --- Phase 1: Execution-metrics overrides (optional; defaults from config.yaml) ---
thresholds: {}                 # e.g. {speed_regression_pct: 25, cost_regression_pct: 50}
                               # cost_regression_pct: null = warn-only (default)

# --- Phase 3: Composite (only when eval_type is composite) ---
sub_evals: []                  # list of {eval_type, eval_id, weight, must_pass, ...} entries
                               # weights must sum to 1.0; see §3c for full schema
composite_pass_threshold: 0.7  # weighted score must be >= this for verdict=pass
---

## Problem

<what hurts, how you noticed>

## Proposal

<concrete change>

## Acceptance criteria

- [ ] <observable outcome 1>
- [ ] <observable outcome 2>

## Validation plan

<which real sessions / scenarios will tell you it worked>

## Eval Plan

- **Type:** <eval_type>
- **What we measure:** <metric list — for tool_loop include trajectory metrics: tool_call_count, sequence, redundant_call_rate>
- **Pass criteria:** <thresholds; remember regression = delta_mean > 2*stddev>
- **Negative cases:** <required for tool_loop / subagent_routing — list at least one>
- **Rubric (if eval_type=rubric or quality):** <link to evaluators/rubrics/imp_XXXX.md, criteria + weights summary, calibration agreement target>
- **Sub-evals (if eval_type=composite):** <list each sub_eval with weight + must_pass; explain the roll-up>
- **Known limits:** surrogate model is gpt-5.4; production is claude-opus-4.6-1m in VS Code Copilot. Real-session check required before `validated`.

## Results

<!-- Auto-populated by /Implement-Improvement and /Validate-IMP -->
<!-- Validation gate: see README.md §`validated` bar (4-point gate, IMP-0015) -->

| Metric | Baseline (mean ± σ, n) | Post (mean ± σ, n) | Delta | Regression? |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

**Quality / Speed / Cost summary** (Phase 1+ format):

- Quality: <pass_rate or weighted_score baseline → post>
- Speed:   <wall_time_ms baseline → post (Δ%, gated by speed_regression_pct)>
- Cost:    <cost_usd baseline → post (Δ%, advisory unless cost_regression_pct set)>

**Real-session evidence:** <link to session-state/<id>/ — required for non-structural>

## Notes
