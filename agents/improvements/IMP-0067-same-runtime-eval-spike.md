---
id: IMP-0067
title: Same-runtime eval spike — replay behavioral evals through Copilot SDK sessions
status: proposed
source: review-2026-07-17
affects: [meta]
risk: low
created: 2026-07-17
updated: 2026-07-17
commit: null
eval_type: manual
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
validation_evidence: []
manual_evidence: []
---

## Problem

The harness's central caveat is the two-runtime gap (EVAL-SYSTEM-PLAN §0): production runs
in Copilot (VS Code / CLI) with the real models (Opus 4.8-1m / Sonnet 5 fleet; Fable 5,
Opus 4.8 Fast, and GPT-5.6 now in the CLI picker), while the eval runtime is an Azure
Foundry `gpt-5.4` chat-completions surrogate — "a green eval ≠ green in Copilot." That gap
is a root cause of the validation debt (24 IMPs sitting at `implemented`): surrogate
evidence is directional only, and real sessions (~2/week) rarely exercise the governed
behaviors — the 07-15/07-16 nightlies returned **all rows inconclusive** because the
features never fired.

2026-07-17 sweep fact: the Copilot SDK (TypeScript/Python/Go/.NET/Rust) exposes
programmatic sessions — `createSession({customAgents: [{name, description, tools,
prompt, …}]})`, subagent lifecycle events, fleet RPC — i.e., **scripted sessions in the
real runtime with the real agent prompts and real models**. The `experimental: true`
setting it requires is already on in settings.json.

## Proposal

Timeboxed spike (≤2 days), decision memo as the deliverable — the IMP-0056 shape, NOT a
harness rewrite:

1. Wrap 1–2 registered behavioral evals (pick from the QB behavioral set behind the
   0.571→0.629 baseline; single-turn, low tool dependence) as SDK sessions using the
   production prompt as a `customAgents` entry.
2. Score with the **same** evaluator check functions (`get_scenarios()` / `check_*`
   convention) — only the transport changes.
3. Measure verdict agreement SDK-real-model vs Foundry-gpt-5.4 on identical scenarios,
   with ≥15 conclusive observations so the comparison is decision-grade (matches the
   Wilson-gate minimum).
4. Record cost (premium requests), latency, determinism, and scriptability. The memo
   decides **adopt / partial / reject**, including where SDK evidence sits in the typed
   evidence taxonomy (likely `source: synthetic` with the real `model`/`deployment`
   recorded — the schema already carries those fields).

## Acceptance criteria

- [ ] Headless scenario replay works with the production prompt + a production model via
      the SDK
- [ ] Agreement measured on ≥15 conclusive observations per replayed eval
- [ ] Cost per scenario recorded and within the nightly budget envelope
- [ ] Decision memo recorded in this IMP (adopt / partial / reject with reasons)
- [ ] If adopt: one implemented-awaiting IMP re-validated via SDK evidence as the pilot
      burndown proof

## Validation plan

The deliverable is the memo (manual). Evidence = `inspection`-source
`validation_evidence` pointing at the committed memo + agreement table. No real-session
requirement.

## Eval Plan

- **Type:** manual (spike/decision memo — same shape as IMP-0056).
- **What we measure:** verdict agreement rate, cost/scenario, latency/scenario,
  scriptability notes.
- **Pass criteria:** memo exists with the agreement table; adoption criteria checkboxes
  answered.
- **Negative cases:** n/a (manual).
- **Known limits:** the SDK is new — pin the SDK version in the memo; model ids must
  resolve in SDK sessions the same way they do in the picker (IMP-0049's verification
  pattern); prompts written for VS Code tool surfaces constrain scenario choice to
  behavior, not tool-loops.

## Results

<!-- Auto-populated by /Implement-Improvement and /Validate-IMP -->
<!-- Validation gate: see README.md §`validated` bar (4-point gate, IMP-0015) -->

| Metric | Baseline (mean ± σ, n) | Post (mean ± σ, n) | Delta | Regression? |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

**Quality / Speed / Cost summary** (Phase 1+ format):

- Quality: —
- Speed:   —
- Cost:    —

**Targeted evidence gate:** —

**Real-session corroboration:** —

## Notes

- Filed by the 2026-07-17 tech sweep. **Explicitly gated behind Wave 7 + the IMP-0053
  pilot** — the 2026-07-16 priority call ("nothing meta ships ahead") stands; filing ≠
  starting. This is the sweep's only meta filing and it waits.
- Why file it at all: it is the only structural attack on the validation-debt root cause —
  if SDK replay agrees with the surrogate, confidence in existing synthetic evidence
  rises; if SDK sessions are cheap and scriptable, the §0 gap shrinks for every future
  IMP rather than IMP-by-IMP.
- Synergy: IMP-0057's debt table selects which IMPs to replay first.
