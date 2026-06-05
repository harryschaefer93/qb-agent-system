---
id: IMP-0018
title: Rubric-score poc-scoper BRIEF.md output quality (rubric backfill reference)
status: accepted
source: eval-harness-phase-2
affects: [scoper]
risk: low
created: 2026-05-08
updated: 2026-06-01
commit: null
eval_type: rubric
skip_validation: false
eval_id: imp_0018
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
rubric_path: evaluators/rubrics/imp_0018.md
calibration_path: evaluators/rubrics/imp_0018.calibration.jsonl
calibration_min_agreement: 0.80
thresholds: {}
sub_evals: []
composite_pass_threshold: 0.7
---

## Problem

`poc-scoper` produces `BRIEF.md` outputs that are structurally correct (the existing structural eval verifies the headings + frontmatter shape) but vary in quality on the dimensions that actually matter to FSI customer engagements:

1. **Completeness of customer context** — does the BRIEF identify the customer's industry, top-level business pain, and decision-maker context, or is it generic boilerplate?
2. **Clarity of acceptance criteria** — are the criteria phrased as observable, testable outcomes, or as aspirations like "delight the user"?
3. **Alignment with FSI domain conventions** — does the BRIEF reference the FDPO / Entra-only / Microsoft-first stack constraints that downstream agents (INFRA, DEV, ARCH) need to know about?

Without a rubric-scored signal, prompt iterations on `scoper.md` are vibes-checked and silently regress these qualities while passing structural gates. We want a numerical, calibratable signal so prompt changes can be measured.

## Proposal

Introduce a 3-criterion rubric scored 1–5 by an LLM judge running on Foundry, with weights:

| Criterion | Weight | What it measures |
|---|---|---|
| `customer_context` | 0.40 | Industry + business pain + named persona/priority |
| `acceptance_clarity` | 0.40 | Observable, testable acceptance criteria |
| `fsi_domain_fit` | 0.20 | FDPO / Entra-only / Microsoft-first / regulatory framing |

Author at least 5 hand-graded calibration examples (one strong, three middle-mixed, one deliberately weak) under `evaluators/rubrics/imp_0018.calibration.jsonl`. Run them through the calibration gate before trusting the rubric for scoring; require ≥ 0.80 agreement.

For ongoing eval, run a small set of captured customer scoping prompts through the `scoper` agent on every IMP that touches `scoper.md`. Require `weighted_score ≥ 4.0` AND `calibration_passed = true` before flipping IMP status to `validated`.

## Acceptance criteria

- [ ] Rubric file `evaluators/rubrics/imp_0018.md` exists with 3 criteria summing to weight 1.0
- [ ] Calibration set `evaluators/rubrics/imp_0018.calibration.jsonl` has ≥ 5 hand-graded examples
- [ ] `evals run-imp IMP-0018 --baseline` captures a snapshot with rubric metrics populated (`weighted_score`, `per_criterion_means`, `calibration_passed`)
- [ ] Calibration agreement ≥ 0.80 against the hand-graded set after the maintainer's refinement pass
- [ ] At least one prompt in the scenario set deliberately produces a low-quality BRIEF so the judge has to distinguish quality (negative case)

## Validation plan

Capture a baseline against the current `scoper.md` prompt. Iterate on `scoper.md` (e.g. tighten the acceptance-criteria language) and capture a post snapshot. Confirm `weighted_score` moves in the expected direction and that `per_criterion_means` shows the change in the criterion targeted by the prompt edit.

## Eval Plan

- **Type:** rubric
- **What we measure:** `weighted_score` (1–5) across 3 criteria + `calibration_agreement` and `calibration_passed`. Per-criterion means are surfaced for diagnostic use.
- **Pass criteria:** `weighted_score ≥ 4.0` AND `calibration_passed = true`. A weighted score under 4.0 or a failing calibration gate blocks the IMP from `validated`.
- **Negative cases:** Calibration set includes one deliberately thin BRIEF (missing customer context, vague acceptance criteria, no FSI framing) — the judge must score it ≤ 2 on the affected criteria for the calibration gate to be meaningful.
- **Rubric:** [evaluators/rubrics/imp_0018.md](../../evals/evaluators/rubrics/imp_0018.md), 3 criteria (customer_context 0.4, acceptance_clarity 0.4, fsi_domain_fit 0.2), calibration agreement target 0.80.
- **Sub-evals:** N/A (standalone rubric).
- **Known limits:** surrogate judge model is `gpt-5.4`; production scorer must remain stable across prompt iterations. Real-session evidence required before `validated`.

## Results

<!-- Auto-populated by /Implement-Improvement and /Validate-IMP -->

| Metric | Baseline (mean ± σ, n) | Post (mean ± σ, n) | Delta | Regression? |
|---|---|---|---|---|
| weighted_score | ... | ... | ... | ... |
| pass_rate | ... | ... | ... | ... |
| calibration_agreement | ... | ... | ... | ... |
| customer_context (mean) | ... | ... | ... | ... |
| acceptance_clarity (mean) | ... | ... | ... | ... |
| fsi_domain_fit (mean) | ... | ... | ... | ... |

**Quality / Speed / Cost summary** (Phase 1+ format):

- Quality: <weighted_score baseline → post>
- Speed:   <wall_time_ms baseline → post (Δ%, gated by speed_regression_pct)>
- Cost:    <cost_usd baseline → post (Δ%, advisory unless cost_regression_pct set)>

**Real-session evidence:** <link to session-state/<id>/ — required before `validated`>

## Notes

**PLACEHOLDER calibration grades.** The 5 examples in `imp_0018.calibration.jsonl` are scaffolded with fabricated `response` text and approximate `expected_scores`. Every entry is marked `"notes": "PLACEHOLDER — the maintainer to refine"`.

Before this rubric can be used to gate an IMP, the maintainer must:

1. Replace each fabricated `response` with a real BRIEF.md excerpt drawn from past customer scoping work (or hand-author representative examples that match the score level).
2. Re-grade `expected_scores` against those real responses.
3. Run `evals run-imp IMP-0018 --baseline` and confirm `calibration_passed: true`. If agreement is below 0.80, either tighten the rubric definitions or refine the calibration grades until the judge and human agree.

Until that work is done, baseline snapshots will likely show `calibration_passed: false`. That is expected for the scaffold and does not indicate a runner bug.
