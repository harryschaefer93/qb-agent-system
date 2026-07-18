---
id: IMP-0031
title: SCOUT agent — cheap read-only reconnaissance tier
status: implemented
source: review-2026-06-10
affects: [QB, QA]
risk: medium
created: 2026-06-10
updated: 2026-07-13
commit: 5dac3a5
eval_type: subagent_routing
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

Every fleet agent runs an opus-class 1M model; there is no cheap tier. Gold-standard harnesses run a two-tier economy — expensive models for judgment, cheap read-only scouts for context gathering (Claude Code's Explore subagent: "locates code, doesn't review it"). The gap shows up in three places:

1. QB is forbidden from reading files, so CP1/CP2 questions are composed from total ignorance of the codebase — generic instead of informed.
2. QA's `survey` mode is reconnaissance mis-homed inside the most expensive validation agent (full QA palette + opus for a read-only inventory).
3. DEV and INFRA each re-discover the same codebase at the start of every invocation.

## Proposal

New `agents/SCOUT.agent.md` — deliberately the opposite of every existing agent: cheap, read-only, disposable.

- **Tools:** `read/readFile, read/problems, search/codebase, search/fileSearch, search/textSearch, search/listDirectory, search/usages, todo` — nothing else. No edit, no terminal, no web, no azure-mcp, no subagents.
- **Model:** smallest capable model the VS Code agent picker exposes (haiku/mini-class). Explicitly NOT changing QB's model — IMP-0009's rejection (QB needs the 1M window) stands untouched.
- **Return contract:** ≤400 tokens, `path:line` citations, no code dumps — IMP-0001's directive is its entire output personality.
- **Used by:**
  - **QB** — pre-checkpoint triage so the consolidated checkpoint (IMP-0028) presents informed options ("the endpoint is `api/routes/export.py:41`, single file, no auth implications") instead of generic ones.
  - **Replaces QA `survey` mode** — QA drops from 6 modes to 5 and stays a verifier; the feature-request pipeline step 2 invokes SCOUT instead.
  - **Optional warm-start brief** for DEV/INFRA invocations (path map + integration points), cutting their re-discovery turns.
- **Wiring:** add to QB's `agents:` list + a handoff entry; add a `CONTRACTS` entry in `evaluators/pipeline.py` (required: read/search; forbidden: edit/execute/web/azure families) so the generic `tool_palette` evaluator and Tier-1 pipeline cover it.

## Acceptance criteria

- [ ] `SCOUT.agent.md` exists: single `tools:` line, read-only palette, return cap in prompt
- [ ] `pipeline.py::CONTRACTS` entry for SCOUT; generic `tool_palette` eval green; Tier-1 scenarios updated where survey was used
- [ ] QA.agent.md `survey` mode removed; QB's feature-request pipeline step 2 routes to SCOUT
- [ ] QB invokes SCOUT before the checkpoint in ≥1 real session, and the checkpoint options cite SCOUT findings (`path:line`)
- [ ] SCOUT returns stay within cap across all eval scenarios
- [ ] Negative case: QB does NOT invoke SCOUT for meta/IMP work or pure scope-only questions with no codebase component

## Validation plan

One real `feature-request` session post-commit: SCOUT survey replaces QA survey, checkpoint is observably more specific. Watch for the failure mode where SCOUT's small model misreads the codebase and misleads the checkpoint — if observed, gate which task types use SCOUT or bump its model one notch.

## Eval Plan

- **Type:** subagent_routing (does QB route recon to SCOUT, not QA, for survey-shaped needs?) + structural `tool_palette` for the palette
- **What we measure:** routing confusion matrix (SCOUT vs QA-survey vs none) across the IMP-0021 scenario set; SCOUT return length distribution; trajectory tool_call_count
- **Pass criteria:** ≥90% correct routing on survey-shaped scenarios; 100% palette compliance; 0 SCOUT invocations on negative-case scenarios
- **Negative cases:** meta/IMP-work prompt → no SCOUT; pure scope question ("production-quality or quick demo?") → no SCOUT
- **Known limits:** surrogate gap as usual; small-model recon *quality* is only observable in real sessions.

## Results

**Implemented 2026-07-13** (Wave 2, alongside IMP-0042). `agents/SCOUT.agent.md` created:
`model: claude-sonnet-4.6` (cheapest capable in the picker — no haiku/mini class exposed; the
"bump one notch" escape hatch stands), exact proposed read-only palette, ≤400-token return
contract, three invocation shapes (`recon` / `map` / `warm-start`). QA `survey` mode removed
(6→5 modes); QB rule 2 refined (recon→SCOUT, QA stays first *validation*), rule 8 added (SCOUT
before checkpoints, repo-map wiring), roster + handoff entries added; `pipelines.yaml`
feature-request checkpoints reference SCOUT recon; `evaluators/pipeline.py` gains the SCOUT
CONTRACTS entry + AGENT_FILE_MAP; `datasets/scout/triggers.json` seeds the routing eval.
Note: SCOUT does not run the repo-map script (no terminal by design) — QB generates the map and
passes the path.

Validation pending: routing confusion matrix on the IMP-0021 set + one real feature-request
session with observably more specific checkpoint options.

## Notes

- Source: 2026-06-10 gap analysis, gap #2 — the one roster addition recommended (vs SECURITY/DATA agents, recommended against).
- Consistent with rejected IMP-0009: QB keeps opus-1M; the cheap model is an additive subagent, not an orchestrator downgrade.
- Enabler for IMP-0028 (informed consolidated checkpoints) — implement this first.
