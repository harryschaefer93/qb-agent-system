---
id: IMP-0004
title: Trim QB tool frontmatter and fix duplicate tools line
status: validated
source: review-context-window-2026-04
affects: [QB]
risk: low
created: 2026-04-27
updated: 2026-06-02
commit: 2531ab6
eval_type: structural
eval_id: imp_0004
eval_seed: 42
baseline_run: baselines/IMP-0004/20260428-142609-a0c7c93-baseline.json
post_run: baselines/IMP-0004/20260428-142609-a0c7c93-post.json
manual_evidence:
  - {session_id: 057d35cf, verdict: pass, captured: 2026-06-02, notes: "QB produced compliant Required Output Shape after tool-frontmatter trim. | artifact: evidence/IMP-0004/20260602-057d35cf.json"}
  - {session_id: 6dca5610, verdict: pass, captured: 2026-06-02, notes: "QB produced compliant Required Output Shape after tool-frontmatter trim. | artifact: evidence/IMP-0004/20260602-6dca5610.json"}
  - {session_id: cfeb7744, verdict: pass, captured: 2026-06-02, notes: "QB produced compliant Required Output Shape after tool-frontmatter trim. | artifact: evidence/IMP-0004/20260602-cfeb7744.json"}
---

## Problem

`agents/QB.agent.md` has **two `tools:` lines** in its frontmatter (latent bug — almost certainly malformed). The larger list also grants QB tools its own rules forbid it from using: `edit/*`, `execute/runInTerminal`, `execute/runTests`, notebook tools, browser tools, etc. Tool schemas are loaded into context every turn — this is unnecessary baseline cost.

## Proposal

Replace both lines with a single minimal `tools:` list scoped to orchestration:

```
tools: vscode/askQuestions, vscode/memory, agent/runSubagent, read/readFile, search/codebase, search/fileSearch, todo, web/fetch, web/githubRepo, execute/runInTerminal
```

Keep `execute/runInTerminal` only because QB legitimately runs Quality Gates (build, lint, git status). Everything else is a subagent's job.

## Acceptance criteria

- [x] Frontmatter has exactly one `tools:` line
- [x] Tool list contains only orchestration + quality-gate tools
- [x] Real bug-fix session still completes successfully *(verified across 3 real QB sessions in evidence/IMP-0004/; all produced compliant Required Output Shape)*

## Validation plan

Run one bug-fix and one new-poc-setup. If QB hits a "tool not available" error, add the specific tool back with a comment explaining why.

## Eval Plan

- **Type:** structural
- **What we measure:** single tools line, expected tool set, no forbidden tools, prompt size
- **Pass criteria:** all 4 structural checks pass
- **Known limits:** structural only — no model call. Real-session validation still required.

## Results

| Metric | Baseline | Post | Delta | Regression? |
|---|---|---|---|---|
| pass_rate | 1.0 | 1.0 | +0.00 | No |
| total_checks | 4 | 4 | +0 | No |
| passed_checks | 4 | 4 | +0 | No |

**Cost delta:** N/A (structural eval, no model calls)

**Real-session evidence:** pending — needs one bug-fix and one new-poc-setup session

## Notes

This is the only item in the batch that fixes a literal latent bug, not just a behavior tune. Worth doing first.
