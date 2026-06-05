---
id: IMP-0016
title: Per-eval-type headline-metric rendering in /Agent-Status
status: validated
source: agent-status-2026-04-28
affects: [agent-status.prompt.md]
risk: low
created: 2026-04-28
updated: 2026-04-28
commit: d81adc3
eval_type: manual
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

`agent-status.prompt.md` instructs the dashboard to render the headline metric as a σ-style delta (`+0.12σ`, `-0.05σ`) by reading `metrics[].delta_mean`. But structural-eval JSONs (the only eval_type wired today) emit `pass_rate` as a plain fraction with no `delta_mean` or `stddev` field. As more eval_types come online (`tool_loop`, `behavioral`, `quality`), each will produce a different metrics shape, and the prompt will silently render `—` or fabricate values.

## Proposal

Update `agent-status.prompt.md` step 3 with a per-eval-type rendering table:

| eval_type | Headline metric | Delta format |
|---|---|---|
| structural | `pass_rate` | `+0.25` (fraction) |
| tool_loop | `tool_call_count` mean | `+0.12σ` (z-score) |
| subagent_routing | `correct_route_rate` | `+0.10` (fraction) |
| behavioral | first metric with largest `|delta_mean|` | `+0.12σ` |
| quality | first metric with largest `|delta_mean|` | `+0.12σ` |
| manual | `manual_evidence[-1].verdict` | `pass` / `fail` / `mixed` |

Verdict derivation also needs per-type rules:
- structural: `IMPROVEMENT` if pass_rate increased, `PASS` if equal, `REGRESSION` if decreased
- non-structural: existing σ-based rule

## Acceptance criteria

- [x] `agent-status.prompt.md` step 3 includes the per-eval-type rendering table
- [x] Verdict derivation rules are explicit per eval_type
- [x] Next `/Agent-Status` run renders correct headline metrics for all wired evals (structural today; more as IMP-0014 progresses)

## Validation plan

Run `/Agent-Status` after the prompt update. Confirm IMP-0004 and IMP-0006 render correct deltas (`+0.00 pass_rate` PASS and `+0.25 pass_rate` IMPROVEMENT respectively, matching the manually-computed values from this session).

## Eval Plan

- **Type:** manual
- **What we measure:** dashboard correctness — headline metrics match the underlying JSON
- **Pass criteria:** dashboard verdicts/deltas match a hand-check of the JSON files
- **Known limits:** prompt-only change; no automated eval

## Notes

Discovered during the 2026-04-28 `/Agent-Status` run. The current prompt assumes all evals produce surrogate-model σ deltas; structural evals don't. Should ship before IMP-0014 produces a flood of new eval_types or the dashboard quality will degrade.
