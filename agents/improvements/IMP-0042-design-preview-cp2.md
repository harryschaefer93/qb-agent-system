---
id: IMP-0042
title: Design preview at CP2 for small task types + deterministic repo map
status: implemented
source: review-2026-07-13
affects: [QB, QA, ARCH]
risk: medium
created: 2026-07-13
updated: 2026-07-13
commit: 5dac3a5
eval_type: structural
skip_validation: false
eval_id: imp_0042
eval_seed: 42
baseline_run: null
post_run: baselines/IMP-0042/20260713-133549-673dfce-post.json
manual_evidence: []
---

## Problem

Pain point #4 (user-reported 2026-07-13): "it doesn't show me what it's gonna design before it
builds it — it just builds it, then I look and tell it what to change after." CP2 presented a
*design artifact* only for `new-poc-setup`/`full-delivery` (ARCHITECTURE.md). For `bug-fix`,
`feature-request`, `refactor`, and `optimization` — the bulk of day-to-day tasks — CP2 approved
a **routing plan** ("QA found X, plan: DEV then QA, approve?") with no statement of what would
actually be built. Approval was uninformed, so the real review happened after the build, as
rework. Compounding it: agents re-discovered the codebase from scratch every invocation.

## Proposal

1. **Proposed Change Plan block (the design preview).** QA's pre-CP2 reports (bug-fix
   diagnosis, refactor/optimization `baseline`) MUST end with a structured block: files to
   change (`path:line`), interface/API changes, approach, before→after example, test plan,
   risks. For `feature-request`, ARCH's integration design note plays the same role. Normalized
   form: `evals/schemas/design-preview.schema.json` (mechanical validator lands with IMP-0029).
2. **QB CP2 rule:** for the four small task types, the CP2 `askQuestions` preamble MUST present
   the design preview and cite its artifact path; a missing block bounces to the producing agent
   BEFORE CP2 is presented. Encoded in `pipelines.yaml` CP2 purposes + required_artifacts.
3. **Deterministic repo map** (`scripts/repo_map.py`, Aider pattern): stdlib-only, token-budgeted
   markdown map (tree + top-level symbols with line numbers). QB generates it once per run into
   `session-state/<run-id>/reports/repo-map.md`; SCOUT consumes it; every DEV/INFRA invocation
   says "read the repo map first."

## Acceptance criteria

- [ ] QA.agent.md carries the Proposed Change Plan contract for diagnosis/baseline outputs
- [ ] QB.agent.md CP2 rule requires the preview for the 4 small task types and cites its path
- [ ] `pipelines.yaml` CP2 purposes/artifacts encode the preview for all 4 types
- [ ] `scripts/repo_map.py` produces a budgeted map deterministically; QB rule 8 wires it
- [ ] Real sessions (1 bug-fix + 1 feature-request): user sees files/interfaces/test plan at CP2
      before approving; post-approval build matches the preview
- [ ] Regression guard: IMP-0021 checkpoint-compliance scenarios stay green

## Validation plan

Structural checks by eval; repo_map smoke-tested on this repo. Behavioral: two real sessions
where CP2 visibly presents the preview. Telemetry scorer `_imp_0042` flags CP2 events lacking a
design-preview reference on small task types.

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0042.py`) + telemetry scorer
- **What we measure:** QA/QB/pipelines.yaml wiring; schema presence; repo_map existence; SCOUT
  palette contract (shared with IMP-0031)
- **Pass criteria:** all structural checks green
- **Negative cases:** trivial-scope bug-fix keeps the brief-confirmation CP2 (no forced preview
  theater for one-liners — the Proposed Change Plan for a one-line fix is one line)
- **Known limits:** whether opus-QB reliably bounces a missing preview is production behavior —
  real sessions required before `validated`.

## Results

**Surrogate regression baseline established 2026-07-13** (first live behavioral run on record — `results/behavioral-qb-20260713-152414.json`): gpt-5.4, 35 cases, pass_rate 0.571. Failure signature is uniform and surrogate-characteristic: the model pauses at the checkpoint correctly but writes plan messages that do not preview ARCH/REPO invocations (checkpoint discipline is the documented opus-vs-surrogate divergence). Future prompt changes must hold >= this baseline; the number is a guard, not graduation evidence.

**Real-session evidence:** _pending — 1 bug-fix + 1 feature-request session_

## Notes

- Source: 2026-07-13 supercharge review (pain point #4). Wave 2, paired with IMP-0031 (SCOUT) —
  recon makes the preview informed; the preview makes CP2 a real decision. Wave 5's IMP-0028
  will consolidate CP1→CP2 around this artifact; do not restructure checkpoint *placement* here.
- Deviation from the plan sketch: SCOUT does not run `repo_map.py` itself (its palette has no
  terminal, by design) — **QB** runs the script and passes the artifact path to SCOUT/DEV/INFRA.
