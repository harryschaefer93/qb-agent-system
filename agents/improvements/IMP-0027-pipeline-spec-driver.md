---
id: IMP-0027
title: Pipeline as machine-readable spec + advisory driver CLI (harness-as-tool)
status: validated
source: review-2026-06-10
affects: [QB, meta]
risk: high
created: 2026-06-10
updated: 2026-07-17
commit: 8f8e0ec
eval_type: structural
skip_validation: false
eval_id: imp_0027
eval_seed: 42
baseline_run: null
post_run: baselines/IMP-0027/20260611-194422-e8e5465-post.json
manual_evidence:
  - {session_id: run-records-3, verdict: pass, captured: 2026-07-15, source: real-session, notes: "Driver produced and gated all 3 real run records (PilotApp-20260713-0837, PilotApp-webpublic-20260714, xml-support-test-20260612): CP2 recorded via --approve-checkpoint before DEV, phase order enforced, 0 gate bounces, states schema-valid; structural 4/4 + 21 driver pytest green"}
---

## Problem

The seven task-type pipelines are deterministic flowcharts written in English (QB.agent.md, Workflow step 3) that the model must re-derive every turn. Meanwhile the eval harness holds a **second, machine-readable copy** of the same logic (`evaluators/pipeline.py::TASK_DISPATCH`), guarded by `check_scenario_taxonomy_sync()` — an explicit admission that there are two sources of truth and the canonical one is prose.

Costs of prose-as-state-machine, visible in the file today:
- Accretion drift: duplicated `### 2c` header (~line 307–309) and duplicated `**bug-fix**:` label (~line 330–331).
- Enforcement-by-shouting: four "MANDATORY / NO EXCEPTIONS" blocks, "This rule has caused regressions before (IMP-0021 ambig_3 history). Load-bearing. Re-read before classifying."
- Every behavioral IMP adds more prose, which makes the next behavior less reliable (QB.agent.md is 57KB).
- Sequencing/caps (iteration limits, gate-bounce limits, checkpoint ordering) are enforced only by the model remembering them late in a loaded window.

## Proposal

One canonical spec, consumed by both the evals and QB, with enforcement moving into code. **Phased — do not batch (per README working order):**

**Phase 1 (low risk, evals-only):** Extract `evals/pipelines.yaml` — task types, phase sequences, gate definitions, iteration caps, checkpoint placement, required artifacts per phase. Generate `TASK_DISPATCH` from it. The taxonomy sync check now validates QB prose against the YAML instead of against hand-maintained Python.

**Phase 2 (medium risk, advisory driver):** `python -m pipeline` CLI — `start --task-type X`, `advance --phase qa --verdict pass`, `status` — reading/writing IMP-0026's `run-state.json`. The driver **refuses illegal transitions** (e.g., recording a DEV invocation with no CP2 approval on file; a 3rd iteration cycle) and returns the current phase + allowed next actions. QB is instructed to call it at every seam; QB stops holding the state machine in its head.

**Phase 3 (high risk, prose deletion):** Remove the per-task-type step lists from QB.agent.md, leaving classification judgment, routing judgment, synthesis, and the driver contract. Delete prose only as the driver proves itself in real sessions.

## Acceptance criteria

- [ ] Phase 1: `pipelines.yaml` exists; `TASK_DISPATCH` generated from it; `check_scenario_taxonomy_sync` green; `run-all-imps` CI gate covers spec↔evals consistency
- [ ] Phase 2: driver CLI with transition validation + unit tests; illegal-transition attempts return structured refusals (machine-readable reason)
- [ ] Phase 2: QB.agent.md instructs driver calls at every pipeline seam
- [ ] Phase 3: task-type step lists removed from QB prose; QB.agent.md shrinks ≥25% from its pre-IMP size
- [ ] One session (real or Tier-2 surrogate) where the driver blocks an out-of-order transition and QB recovers correctly

## Validation plan

Phase 1 validates structurally (CI). Phase 2: run one `bug-fix` and one `feature-request` with the driver advisory — confirm QB calls it at seams and respects a deliberate refusal (attempt DEV-before-CP2 in a test session). Phase 3 only after ≥2 clean real sessions on Phase 2.

## Eval Plan

- **Type:** structural (Phase 1/3: spec presence, generation wiring, sync check, prompt references, size budget) + driver unit tests (pytest, deterministic) + Tier-2 surrogate for end-to-end sequencing
- **What we measure:** spec↔evals↔prose consistency; driver transition-matrix coverage; QB prompt size delta
- **Pass criteria:** all structural checks green; driver unit tests 100%; Tier-2 trace shows driver called at every seam
- **Known limits:** whether claude-opus QB reliably *calls* the driver at seams is a production-behavior question — real-session evidence required before `validated`.

## Notes

- Source: 2026-06-10 harness review, improvement #1.
- Depends on IMP-0026 (run-state is the driver's store). Builds on IMP-0021 (the taxonomy being encoded) and the IMP-0017 precedent (harness-as-prompt-command for the IMP lifecycle; this is the same move for the delivery pipeline).
- The standing evidence for "two sources of truth" is that `check_scenario_taxonomy_sync()` had to be written at all.
- Relationship to rejected IMP-0009: this does NOT change QB's model. It reduces what the model must hold, which is the alternative path to the same goal IMP-0009 chased.
- **Enables IMP-0036 Layer 3:** the driver's `pipeline status` ("phases remaining: N, no blocking checkpoint") is the deterministic equivalent of Claude Code /goal's small-model completion evaluator — called before QB ends any DRIVE-mode turn. IMP-0036 Layer 1 (prompt-only) shipped 2026-06-11 but hit a ~0.91 ceiling; this driver is what reliably forces the close-out the prompt cannot.
