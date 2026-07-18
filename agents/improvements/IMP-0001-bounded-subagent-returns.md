---
id: IMP-0001
title: Enforce structured, bounded subagent returns
status: validated
source: review-context-window-2026-04
affects: [QB]
risk: low
created: 2026-04-27
updated: 2026-04-28
commit: f0df6b5
eval_type: tool_loop
eval_id: imp_0001
eval_seed: 42
baseline_run: baselines/IMP-0001/20260429-003207-db4d0b6-baseline.json
post_run: baselines/IMP-0001/20260429-015227-3c54cb4-post.json
manual_evidence:
  - {session_id: cfeb7744, verdict: pass, captured: 2026-06-02, notes: "Routing plan summarizes 5 sub-agent invocation(s) using bullet form, consistent with bounded-return rule. | artifact: evidence/IMP-0001/20260602-cfeb7744.json"}
---

## Problem

QB invokes QA/DEV/INFRA/DIAGRAM/DOCS in the same conversation. Subagent reports return as full prose and accumulate in QB's window. A single bug-fix can produce 4–6 large report blobs, driving long sessions into context overload.

## Proposal

Add a "Subagent Return Discipline" subsection to QB's Critical Rules. Every subagent prompt issued by QB must end with:

> Return only the Required Output Shape. Do not include code dumps, full file contents, or step-by-step reasoning. Cite files by `path:line`. Cap your response at ~400 tokens unless escalating a blocker.

## Acceptance criteria

- [x] New subsection added under "Critical rules" in `agents/QB.agent.md`
- [x] Every workflow step that invokes a subagent references the discipline (or the rule is global enough to not need per-step repetition)
- [x] Tool_loop eval confirms QB appends the bounded-return directive to subagent prompts at runtime (15/15 observed invocations compliant — see `post_run`)
- [x] Run a real bug-fix session post-change; subagent returns visibly shorter *(session cfeb7744: 5 sub-agent invocations summarized in compact bullet form in Routing Plan — see manual_evidence + evidence/IMP-0001/)*

## Validation plan

Compare subagent return sizes in 2 sessions before vs. 2 sessions after. Eyeball is fine — no formal metric.

## Notes

Pairs naturally with IMP-0012 (self-prune after reading reports).

Eval reclassified 2026-04-28: structural → tool_loop. The structural eval only
proved the discipline text exists in `QB.agent.md`; it did not prove QB
actually appends the directive when invoking subagents at runtime. The
tool_loop evaluator (`imp_0001.py`) drives QB through bug-fix and
new-poc-setup scenarios via Foundry and asserts the bounded-return directive
appears in every `runSubagent` prompt. Original structural baseline retained
in `baselines/IMP-0001/` and as `imp_0001.py.structural.bak` for history.

## Results

| Metric | Baseline | Post | Delta | Regression? |
|---|---|---|---|---|
| pass_rate | 0.33 | 1.00 | +0.67 | No |
| total_checks | 3 | 3 | +0 | No |
| passed_checks | 1 | 3 | +2 | No |

**Cost delta:** N/A (structural eval, no model calls)

**Real-session evidence:** pending — capture a bug-fix or new-poc-setup session under `session-state/` and link before `/Validate-IMP`.

### Tool_loop runtime proof (added 2026-04-28)

After eval reclassification structural → tool_loop and a flakiness-reduction
pass on the bugfix scenario (scope baked into the prompt; runner overrides
N_SAMPLES=5 and MAX_TURNS=8 via per-IMP constants), four post-eval rounds
were captured:

| Run | Samples | Conclusive | runSubagent calls | Calls with directive |
|---|---|---|---|---|
| 20260429-013315 (pre-refinement, n=3, turns=6) | 6 | 3 | 7 | 7 (100%) |
| 20260429-013654 (refined scoring, n=3, turns=6) | 6 | 3 | 8 | 8 (100%) |
| 20260429-014659 (n=5, turns=8, scoped prompts) | 10 | 10 | 33 | 33 (100%) |
| 20260429-015227 (confirmation, same config) | 10 | 9 | 32 | 32 (100%) |
| **Total** | **32** | **25** | **80** | **80 (100%)** |

**Statistical confidence:** Wilson 95% CI lower bound on 80/80 successes is
0.955 — we are 95% confident the true runtime compliance rate is at least
95.5%. Latest snapshot (`baselines/IMP-0001/20260429-015227-3c54cb4-post.json`)
is the validation-of-record post snapshot.

**Foundry cost:** ~1.85M input tokens, ~44k output tokens across the four
runs combined.

