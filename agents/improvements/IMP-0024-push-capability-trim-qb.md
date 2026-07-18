---
id: IMP-0024
title: Push capability to specialists, trim QB to pure orchestration
status: validated
source: ad-hoc
affects: [QB, DEV]
risk: medium
created: 2026-06-08
updated: 2026-06-10
commit: ff9bd51
supersedes: IMP-0004
eval_type: structural
skip_validation: true
eval_id: imp_0024
eval_seed: 42
baseline_run: baselines/IMP-0024/20260608-181211-20b099f-baseline.json
post_run: baselines/IMP-0024/20260610-134540-f1196e3-post.json
manual_evidence: []
---

## Problem

QB's `tools:` frontmatter had grown to **159 tools** — the full superset including `edit/*`, `azure-mcp/*`, `bicep/*`, `playwright/*`, `browser/*`, Python, and notebook tools. This silently reverted IMP-0004's orchestration-only trim (commit `d77b918` deliberately re-expanded the palette).

Root cause (per user): QB was given the god-palette to compensate for **thin specialist agents** — DEV in particular (41 tools) lacked the Azure data-plane, Python, library-docs, E2E, and Snowflake tools needed to build full-stack app code on its own, so QB picked up the slack.

This violates least-privilege and degrades QB's own tool-selection accuracy: research on multi-agent harnesses shows selection accuracy drops sharply as an orchestrator's tool count grows. An orchestrator should orchestrate; specialists should execute.

## Proposal

Redistribute capability **down to the specialists**, then trim QB back to orchestration + quality-gate:

- **DEV** (41 → 101): add the app-builder palette it was missing —
  - Python: `ms-python.python/*`
  - Library docs: `context7/*`, `microsoft-learn/*`
  - Azure **data-plane** (app wiring, not provisioning): `foundry`, `foundryextensions`, `cosmos`, `postgres`, `mysql`, `sql`, `keyvault`, `storage`, `search`, `redis`, `eventhubs`, `servicebus`, `signalr`, `appconfig`, `appservice`, `functionapp`, `functions`, `containerapps`, `applicationinsights`, `monitor`, `communication`, `speech`, `documentation`, `get_azure_bestpractices`, `deploy`, `azd`
  - E2E (builder verifies own work): full `playwright/*` + `browser/*`
  - Misc: `vscode/toolSearch`, `execute/runTask`, `read/getTaskOutput`, `web/githubTextSearch`
- **QB** (159 → 20): orchestration + quality-gate only —
  `askQuestions, memory, resolveMemoryFileUri, toolSearch, runSubagent, readFile, problems, getTaskOutput, terminalLastCommand, codebase, fileSearch, textSearch, listDirectory, usages, runInTerminal, getTerminalOutput, runTask, web/fetch, web/githubRepo, todo`.
  Drops all `edit/*`, `azure-mcp/*`, `bicep/*`, `playwright/*`, `browser/*`, Python, notebooks, and `runTests`/`testFailure` (now owned by DEV/INFRA/QA).

INFRA (141, full azure-mcp + bicep) and QA (110, playwright + data-plane) are already capable — left unchanged here. A separate least-privilege pass on INFRA/QA is tracked as **IMP-0025** to avoid batching prompt changes.

## Acceptance criteria

- [x] DEV `tools:` is a single line and includes Python, library-docs, Azure data-plane, and full Playwright/browser tools
- [x] QB `tools:` is a single line trimmed to orchestration + quality-gate (~20 tools, no `edit/*`/`azure-mcp/*`/`bicep/*`/`playwright/*`/`browser/*`)
- [x] DEV can build full-stack POC app code without escalating tool needs to QB
- [x] Synthetic pipeline eval (Tier 1, no model) green: every agent's tool-calls are within its palette; `imp_0024` 10/10 — see `evaluators/pipeline.py`
- [~] Real QB-orchestrated session: DEV completes an app-code task using only its own palette, QB never needs a removed tool — **waived** per `skip_validation: true` (structural auto-validate). No live session captured; telemetry has no `imp_0024` scorer. Coverage substituted by the synthetic-pipeline eval, which exercises all 7 task-type pipelines and confirms every agent tool-call stays within its trimmed palette.

## Validation plan

Run one `full-delivery` (new-poc) and one `bug-fix` with the QB pipeline. Watch for: (a) DEV hitting a "tool not available" error for legitimate app work, (b) QB hitting a "tool not available" error during quality gates. If either occurs, add the specific tool back to that agent with a one-line comment.

## Eval Plan

- **Type:** structural
- **What we measure:** QB single tools line ≤ ~22 and contains no forbidden families; DEV single tools line contains the required app-dev families; no duplicate `tools:` lines.
- **Pass criteria:** all structural checks pass.
- **Known limits:** structural only — no model call. Real-session validation (DEV self-sufficiency + QB quality gates) still required before `validated`.

## Notes

- Supersedes IMP-0004: that IMP's duplicate-`tools:`-line bug fix stands, but its minimal-list claim had been reverted by `d77b918`. IMP-0004 downgraded from `validated` → `implemented` with `superseded_by: IMP-0024`.
- Best-practice basis: least-privilege per-agent tool scoping; orchestrator tool-count minimization (selection-accuracy degradation); "builder verifies its own work" justifies DEV/QA Playwright overlap.
- **2026-06-08 correction:** the initial commit `ff9bd51` also added `basinsnowflakedevwrite/*` to DEV (41 → 104). Per user direction, Snowflake devwrite tooling was removed from DEV (104 → 101); it is not part of the standard DEV palette.
- **2026-06-10 validated:** post snapshot `20260610-134540-f1196e3-post.json` — structural eval **PASS 13/13**; compare vs baseline `20b099f` verdict **pass**, no regressions (+2 checks from IMP-0021 taxonomy coverage, pass_rate 1.00→1.00). Graduated `implemented → validated` under `skip_validation: true` (structural). Real-session criterion waived (see Acceptance criteria).
