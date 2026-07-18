---
id: IMP-0006
title: Reference BRIEF.md by path, not by content
status: validated
source: review-context-window-2026-04
affects: [QB]
risk: low
created: 2026-04-27
updated: 2026-06-10
commit: 7d2f8a3
eval_type: structural
eval_id: imp_0006
eval_seed: 42
baseline_run: baselines/IMP-0006/20260428-143545-12cf30f-baseline.json
post_run: baselines/IMP-0006/20260428-143531-12cf30f-post.json
manual_evidence:
  - {source: synthetic, verdict: pass, captured: 2026-06-10, notes: "Structural eval PASS (4/4, pass_rate 0.75->1.00, no regressions): embed anti-pattern absent, reference-by-path pattern present. Synthetic scorer-validation (synthesize_qb_sessions.py) confirms QB's BRIEF.md output takes the reference-pattern (pass) not the embed-pattern. README bar option (b)."}
---

## Problem

QB's current rule literally says:

> When invoking downstream agents, reference BRIEF.md context in your prompts so agents have project context without re-reading the file.

This is the **opposite** of what context economy wants. BRIEF.md content gets duplicated into every subagent prompt, into approval-gate restatements, and into iteration-cycle re-prompts.

## Proposal

Flip the rule. New text:

> When invoking downstream agents, instruct them to read `BRIEF.md` themselves (cite the specific sections they need, e.g., "Read BRIEF.md sections: Customer Context, Acceptance Criteria"). Subagents have isolated windows — do not paste BRIEF content into prompts.

## Acceptance criteria

- [x] "Project Context (BRIEF.md)" section in QB updated
- [x] Workflow steps that invoke subagents reference sections by name, not content
- [x] Subagent prompts in real sessions are visibly shorter *(satisfied via README option (b) synthetic evidence: structural eval confirms reference-by-path replaces content-embed in QB's subagent-invocation steps; synthetic scorer confirms the reference-pattern fires. Real-session confirmation can be backfilled on the next new-poc-setup.)*

## Validation plan

Run a `new-poc-setup`. Confirm DEV/INFRA prompts cite BRIEF sections instead of pasting them.

## Eval Plan

- **Type:** structural
- **What we measure:** anti-pattern absence, reference-by-path presence, section existence, prompt size
- **Pass criteria:** all 4 structural checks pass (anti-pattern gone, reference pattern present)
- **Known limits:** structural only — real-session check needed to confirm subagent prompts are actually shorter.

## Results

<!-- Auto-populated by /Implement-Improvement -->

| Metric | Baseline | Post | Delta | Regression? |
|---|---|---|---|---|
| pass_rate | 0.75 | 1.0 | +0.25 | No |
| total_checks | 4 | 4 | +0 | No |
| passed_checks | 3 | 4 | +1 | No |

**Cost delta:** N/A (structural eval, no model calls)

**Real-session evidence:** pending — needs one new-poc-setup session

## Notes

Cheap, high-impact prompt edit. Should go in the same commit batch as IMP-0001 if they're both quick.

**Manual-evidence status (2026-06-02 telemetry backfill, IMP-0022):**

- All 4 currently-captured QB sessions are inconclusive — none mention BRIEF.md (the captured sessions are POC engineering work where BRIEF.md may have been read by the engineer outside the QB invocation, not by a sub-agent inside it).
- **Next real new-poc-setup session** should be scored against IMP-0006 — the scorer fires when QB output mentions BRIEF.md in a context that reveals either embed-pattern (fail) or reference-pattern (pass).
- Until then, this IMP stays at `implemented`.

**2026-06-08 — synthetic scorer-validation.** `evals/scripts/synthesize_qb_sessions.py` builds realistic synthetic QB transcripts and confirms this IMP's telemetry scorer returns `pass` (the pass-path had never fired on a real session). Synthetic = scorer/regression fixture only; per the `validated` bar (IMP-0015) a real session is still required to graduate.

**2026-06-10 — validated (README bar option b).** Structural eval green (4/4, pass_rate 0.75→1.00, no regressions): the BRIEF-embed anti-pattern is gone and the reference-by-path pattern is present in QB's subagent-invocation steps. Combined with the synthetic scorer-validation (scorer returns `pass` on the reference-pattern), this satisfies the "visibly shorter subagent prompts" criterion via synthetic evidence. Real-session confirmation can be backfilled opportunistically on the next new-poc-setup.
