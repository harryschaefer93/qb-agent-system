---
id: IMP-0045
title: ORACLE — cross-family second-opinion advisor (breaks the Claude monoculture)
status: implemented
source: review-2026-07-14
affects: [QB, ORACLE]
risk: medium
created: 2026-07-14
updated: 2026-07-14
commit: aa4ff74
eval_type: structural
skip_validation: false
eval_id: imp_0045
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

The entire fleet runs one model family (Claude) — correlated blind spots on exactly the
decisions that are expensive to get wrong: contested architecture calls, twice-failed fixes,
conflicting subagent recommendations. Amp's "oracle" pattern (2026-06-11 harness research,
candidate #3): a *different frontier model* as senior advisor, invoked at decision points, never
as a doer. EVAL-SYSTEM-PLAN §0a already prescribes cross-model sanity checks for evals;
production had none.

## Proposal

`agents/ORACLE.agent.md` — `model: gpt-5.5` (deliberately non-Claude; documented 1M-class GA in
Copilot; swap up to a GPT-5.6 variant if/when its picker id is confirmed), advisory-only palette
(read + search + web + context7 — no edit/terminal/azure/subagents), ≤300-token bounded return
(`Verdict / Position / Grounds / Would check`), three invocation shapes: `conflict`,
`pre-escalation`, `risky-cp2`. QB wiring: roster entry + one rule — invoke at (a) conflicting
recommendations, (b) 2-cycle failure before user escalation, (c) risky CP2 (large scope / new
Azure resources); present ORACLE's verdict alongside QB's own; never adopt silently; never a
pipeline phase. Paid for under the QB line cap by executing IMP-0027 Phase 3 (per-task phase
table deleted; `pipelines.yaml` + driver are the sequence authority — exercised end-to-end in
the real run PilotApp-20260713-0837).

## Acceptance criteria

- [ ] ORACLE.agent.md on a non-Claude model; palette contract green (CONTRACTS entry)
- [ ] QB invokes ORACLE at ≥1 real decision point; the checkpoint/escalation presents both views
- [ ] Negative case: ORACLE never appears as a pipeline phase in any run record
- [ ] ORACLE dissent demonstrably changes ≥1 real decision (or its concurrence is cited at a risky CP2) within the first weeks
- [ ] gpt-5.5 resolves in the picker on first invocation (else record the working id and update)

## Validation plan

Structural now (imp_0045). Behavioral: first real conflict/escalation/risky-CP2 — check the
run record + transcript show both opinions presented. Retro tracks whether ORACLE verdicts
correlate with better outcomes (KPIs: gate bounces, escalations reaching the user).

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0045.py`) + routing triggers seeded (`datasets/oracle/triggers.json`)
- **Pass criteria:** cross-family model, palette contract, prompt contract, QB wiring — all green
- **Known limits:** advisory *quality* is only observable in real contested decisions; picker id resolution is runtime-verifiable only.

## Notes

- Source: 2026-06-11 harness research candidate #3; scheduled Wave 6; pulled forward 2026-07-14
  under the user's improve-aggressively directive.
- FDPO guard embedded in ORACLE's own prompt — a second opinion is never a license to recommend
  key-based auth.
- Complements IMP-0043 best-of-N (parallel attempts) — ORACLE is cheap single-shot dissent;
  best-of-N is expensive parallel search; both fire at the same escalation seam.
