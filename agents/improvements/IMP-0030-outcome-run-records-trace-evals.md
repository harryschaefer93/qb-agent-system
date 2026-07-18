---
id: IMP-0030
title: Outcome-grade run records + failed-trace-to-eval conversion
status: validated
source: review-2026-06-10
affects: [QB, retro, meta]
risk: low
created: 2026-06-10
updated: 2026-07-15
commit: 907f0d8
eval_type: manual
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence:
  - {session_id: run-records-3, verdict: pass, captured: 2026-07-15, notes: "3 real run records (PilotApp-20260713-0837 new-poc-setup 520min, PilotApp-webpublic-20260714 feature-request 342min, xml-support-test-20260612); `telemetry kpi` renders completion rate 1.0 + cycle time + bounces + escalation/override — acceptance boxes 1 and 3"}
  - {session_id: PilotApp-20260713-0837, verdict: pass, captured: 2026-07-15, notes: "real premature-yield failure converted via trace_to_eval.py to datasets/regressions/PilotApp-20260713-0837/case.json, privacy-scrubbed, discriminates pre-fix behavior (record-aware _imp_0036 flags it FAIL) — acceptance boxes 4 and 5"}
---

## Problem

The eval system measures **compliance** (classification block emitted? checkpoint fired? palette correct?) but not **outcomes** (tokens per delivered task, wall-time, gate-bounce rate per agent, QA cycles per fix, checkpoint-override rate, escalation frequency). A harness can be 100% rule-compliant and still slow, expensive, and annoying — and we currently can't see which.

Collection is also inverted: retro *mines* transcripts after the fact via content fingerprints (IMP-0022), which is lossy and drift-prone. IMP-0022's own notes name the fix: "Consider OTel-style structured tracing inside QB itself... the long-term north star." This IMP is that north star.

Finally, the acknowledged surrogate gap (gpt-5.4 evals vs claude-opus production, EVAL-SYSTEM-PLAN §0/§7) means synthetic mocks systematically miss real failure modes — and real failures currently teach the system nothing durable.

## Proposal

1. **Run records emitted at runtime, not mined.** The pipeline writes a structured record into IMP-0026's `run-state.json` (or a sibling `run-record.json`): phases + durations, agent invocations, gate bounces, iteration cycles, checkpoint presented/chosen/modified, escalations, final verdict, approximate token/cost figures where observable. Retro consumes records instead of fingerprints.
2. **KPI trending in retro weekly mode:** cycle time, bounces per agent, override rate per scope class, escalation rate — trended across runs. Retro files IMPs against the worst regression *with numbers* (extends the existing Phase 4b "recommendations become IMPs" loop).
3. **Failure-case routing** (EVAL-SYSTEM-PLAN §8's reframe of Phase G): any failed or user-corrected run gets its trace snapshotted to `evals/datasets/regressions/<run-id>/` and converted into a replayable eval case, privacy-scrubbed per IMP-0022's guardrails. The regression suite grows from real production failures instead of hand-curated mocks — the strongest guard against re-breaking what already broke once.

## Acceptance criteria

- [x] Run-record schema documented; a real pipeline run emits a complete record with zero retro mining
- [x] Retro weekly mode reads run records when present (fingerprint mining retained as fallback for pre-IMP sessions)
- [x] KPI summary table (≥4 of: cycle time, bounce rate, override rate, escalation rate, cost) renders in a retro report from ≥3 run records
- [x] ≥1 real failed/user-corrected run converted into a replayable eval case that demonstrably fails against the pre-fix behavior
- [x] Privacy scrub verified on the converted case (no customer names, no repo paths — IMP-0022 guardrails)

## Validation plan

Infrastructure IMP — validated by inspection like IMP-0022: records get produced, retro consumes them, one trace-derived eval case exists and discriminates. First real customer-POC session post-commit is the live check.

## Eval Plan

- **Type:** manual (meta-system infrastructure; the deliverable IS eval machinery)
- **What we measure:** end-to-end record emission → retro consumption → trace-to-eval conversion, by inspection
- **Pass criteria:** all acceptance checkboxes
- **Known limits:** token/cost figures inside VS Code Copilot are approximations (the runtime doesn't expose exact counts to the agent); record what's observable, label estimates as estimates.

## Results

**Implemented 2026-07-13** (Wave 0 of the supercharge program, alongside IMP-0039):

1. Run records: `run-state.json` extended (schema: `workspace`, `last_activity`, `status`, `final_verdict`, `escalations[]`, `gate_bounces[]`, `cost_estimates`); driver stamps activity and terminal status; `pipeline escalate` records escalations. Checkpoint outcomes were already covered by `approvals[]` (IMP-0026) — no duplicate field added.
2. KPI trending: `python -m runner.telemetry kpi [--since] [--json]` aggregates completion rate (headline), cycle time, gate bounces, iteration retries, escalation rate, override rate, cost — per run and per task type. `retro.md`/`retro.agent.md` weekly mode gained **Phase 0: Run Records First** (records primary, fingerprint mining fallback) with a KPI trend table and abandoned-run findings.
3. Failure-case routing: `evals/scripts/trace_to_eval.py` converts a failed/user-corrected session and/or run into `evals/datasets/regressions/<case-id>/case.json`, privacy-scrubbed (IMP-0022 guardrails), with an `IMP_SCORERS` expectation reference. `datasets/regressions/README.md` sets the only-real-traces rule.

**Validated 2026-07-15:** 3 real run records on disk (PilotApp-20260713-0837, PilotApp-webpublic-20260714, xml-support-test-20260612); `telemetry kpi` aggregates them (completion rate 1.0, mean cycle 290.5 min); the 0713 premature-yield failure became `datasets/regressions/PilotApp-20260713-0837/` and the record-aware `_imp_0036` scorer discriminates it (FAIL on the pre-fix record). All five acceptance boxes met with zero synthetic evidence.

## Notes

- Source: 2026-06-10 harness review, improvement #5 + gap analysis ("let telemetry adjudicate" the checkpoint tuning).
- Extends IMP-0022 (explicitly its stated north star). Depends on IMP-0026 (run-state is the emission target). Feeds IMP-0028's evidence-based gate tuning — implement before or alongside 0028.
- Lowest-risk of the 2026-06-10 batch; per README working order, a good early pick.
