---
id: IMP-0023
title: QB Workflow consolidation — compress without behavior change
status: validated
source: review-2026-06-03 (post-PR2 audit)
affects: [QB]
risk: low
created: 2026-06-03
updated: 2026-06-03
commit: 11428eb
eval_type: structural
skip_validation: true
eval_id: imp_0023
eval_seed: 42
baseline_run: baselines/IMP-0023/20260603-182515-d9a3f8e-baseline.json
post_run: baselines/IMP-0023/20260603-182517-d9a3f8e-post.json
manual_evidence: []
---

## Problem

After Phase 2A (IMP-0021 PR 2), `agents/QB.agent.md` grew from ~660 lines to **696 lines**, with the `Workflow` section accounting for a large share (all 7 task-type pipelines, including the 3 new ones from PR 2). The PR 2 ship took 4 prompt-tuning iterations to reach 17/17 stable — direct evidence that prompt growth diluted the ambiguity discipline in the surrogate eval.

Production (Claude Opus 4.6 1M context) handles 696 lines fine. The surrogate eval (gpt-5.4) is the bottleneck. As we plan IMP-0020 (Evidence-Backed Recommendations) which will add another ~50-80 lines to QB, we risk repeating the PR 2 tuning iteration unless we first buy headroom.

## Proposal

Compress QB.agent.md by **redundant-language reduction**, not structural rewrite. Each pipeline has ~5 repeated phrases that can be tightened without losing meaning:

| Verbose phrase | Tight phrase |
|---|---|
| `**CHECKPOINT 1 (mandatory — see rule 5).** Call \`askQuestions\` to clarify ...` | `**CHECKPOINT 1** (rule 5). \`askQuestions\` for ...` |
| `**Do NOT proceed to step 2 until the user responds.**` | `Stop until user answers.` |
| `**Run quality gates** (build / lint / typecheck / tests).` | `**Quality gates.**` |
| `**Invoke REPO for commit + push.**` | `**REPO**: commit + push.` |
| `**Invoke QA** in **deep-review** mode ...` | `**QA deep-review**: ...` |

Target: **30-50 line reduction** (531 → ~480). No behavior change. Same pipelines, same gates, same eval scores.

## Acceptance criteria

- [x] QB.agent.md reduced from 696 → ≤680 lines (actual: **671 lines, -25 reduction, -3.6%**)
- [x] IMP-0021 post-eval still 17/17 stable (across re-runs — one transient surrogate-API error caught + verified non-regression on re-run)
- [x] All 7 pipelines + 6 QA modes still functional (structural eval 5/5 PASS)
- [x] No public-facing prompt content removed (only redundant language)
- [x] Structural eval `imp_0023` PASSES 5/5
- [ ] Committed + pushed *(pending — finalize after eval green)*

## Validation plan

Composite verification:
1. **Structural eval** (`imp_0023`) — 5 file-shape checks: line count, 7 pipeline names, 6 QA mode names, CP1/CP2 references in each pipeline, REPO references
2. **Behavior eval** (`imp_0021` re-run) — 17/17 stable across 2 consecutive runs

Both must pass for IMP-0023 to ship. If IMP-0021 regresses, roll back the last consolidation chunk and try a different tightening.

## Eval Plan

- **Type:** structural (file-shape verification only)
- **What we measure:** byte-shaving achieved + surface invariants preserved
- **Pass criteria:** all 5 structural checks PASS; IMP-0021 routing eval stays at 17/17
- **Negative case:** any consolidation chunk that drops a CP gate, removes a pipeline reference, or accidentally renames a sub-mode → eval FAILs and chunk rolled back
- **Known limits:** "no behavior change" is a *claim* — only the IMP-0021 17/17 verification proves it. Real-session evidence (via IMP-0022 telemetry on next POC session) is the durable check.

## Notes

Companion to the planned IMP-0020 (Evidence-Backed Recommendations) — by consolidating first, IMP-0020's ~50-80 line addition lands without pushing QB.agent.md back to its pre-consolidation size.

Approach learned from IMP-0021 PR 2 tuning iteration: never batch QB prompt changes; one section at a time with eval verification between each.

## Results (2026-06-03)

| Metric | Baseline (HEAD pre-consolidation) | Post | Delta |
|---|---|---|---|
| QB.agent.md line count | 696 | 671 | **-25 lines (-3.6%)** |
| Structural eval (5 checks) | 4/5 PASS (line count FAIL) | **5/5 PASS** | +1 |
| IMP-0021 routing eval (behavior gate) | 17/17 stable | **17/17 stable (across re-runs)** | No regression |

**What was consolidated:** all 7 task-type pipeline definitions in the Workflow section + the task classification step 2a/2b sections. Compression patterns applied:

- `**CHECKPOINT 1 (mandatory — see rule 5).** Call \`askQuestions\` to ...` → `**CHECKPOINT 1** (rule 5). \`askQuestions\` for ...`
- `**Do NOT proceed to step N until the user responds.**` → `Stop until user answers.`
- `**Run quality gates** (build / lint / typecheck / tests).` → `**Quality gates.**`
- `**Invoke REPO for commit + push.**` → `**REPO** for commit + push.`
- `**Invoke QA** in **<mode>** mode ...` → `**QA <mode>** ...`
- Removed redundant PR1 fallback note ("Pipeline status (post PR 2)") that became stale after PR 2 shipped
- Removed verbose pipeline-preview phrasing in step 2c table (kept the actual rule, dropped redundant repetition)

**What was NOT changed:**
- Sequence of operations in any pipeline
- Gate placement (CP1 / CP2)
- QA sub-mode invocations
- REPO step in each pipeline
- The Ambiguity-first Keywords rule (load-bearing per PR2 tuning iteration history)
- Required Output Shape
- DEV Fan-Out / Merge Gate / Two-Tier QA / Iteration Protocol / Diagram Review Loop sections

**Verification methodology:** ran IMP-0021 routing eval after the consolidation pass. Caught one transient surrogate-API error (bugfix_1 sample 0 returned len=0 with stopped_reason=error); re-ran and confirmed 17/17 stable. No real behavior regression.
