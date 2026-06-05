---
id: IMP-0006
title: Reference BRIEF.md by path, not by content
status: implemented
source: review-context-window-2026-04
affects: [QB]
risk: low
created: 2026-04-27
updated: 2026-04-28
commit: 7d2f8a3
eval_type: structural
eval_id: imp_0006
eval_seed: 42
baseline_run: baselines/IMP-0006/20260428-143545-12cf30f-baseline.json
post_run: baselines/IMP-0006/20260428-143531-12cf30f-post.json
manual_evidence: []
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
- [ ] Subagent prompts in real sessions are visibly shorter

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
