---
id: IMP-0064
title: Kill the deploy/auth tail — governed-tenant preflight, live-auth smoke, landmine knowledge capture
status: proposed
source: review-2026-07-16
affects: [INFRA, QA, DEV, retro]
risk: low
created: 2026-07-16
updated: 2026-07-16
commit: null
eval_type: structural
skip_validation: false
eval_id: imp_0064
eval_seed: 42
baseline_run: null
post_run: null
validation_evidence: []
manual_evidence: []
---

## Problem

The build was one day; the deploy/auth tail was **three** — and it is the real "dev takes
forever". PilotApp timeline: 7/13 build (~9h, tracked) → 7/14 deploy blocked by tenant
private-link policy, Option B VNet built, MI resilience fixes → 7/15 provision/teardown,
**Option D storage-tag-bypass pivot**, Easy Auth v2 bare-clientId audience mismatch,
in-worker JWT validation replacing header injection, MSAL token-readiness gating →
7/15–16 fan-out track A iterated **A2→A8 (eight live-auth loops over ~25h)**. Every loop
is deploy → probe → read logs → patch → redeploy at ~30–60 min each. None of these
landmines was new-in-principle: they are properties of *our* governed tenant (FDPO, no
keys, private-link policy, Easy Auth v2 quirks) that get rediscovered per engagement
because nothing captures them and nothing checks them before provisioning.

## Proposal

1. **Governed-tenant deploy preflight** (`skills/deploy-preflight/SKILL.md` + a
   deterministic `scripts/deploy-preflight.ps1`): run BEFORE provisioning. Checks the
   known policy landmines — private-link/tag policy posture of the target subscription/RG,
   Easy Auth v2 audience form (bare clientId vs api://), local-auth-disabled flags,
   required RBAC for the deployer OIDC identity, storage tag-bypass availability. INFRA
   references the skill; failing preflight items surface at CP2 as risks, not at deploy
   time as fires.
2. **Live-auth smoke, first loop not eighth.** One script (`scripts/smoke-auth.ps1`):
   acquire a token as the owner identity, probe the deployed endpoint(s), assert
   401-fail-closed for bad/absent tokens and 200 for good. QA runs it immediately after
   every deploy phase; DEV gets its output verbatim. Track A's eight iterations were
   this loop performed manually and diagnostically blind.
3. **Landmine knowledge capture is mandatory after deploy fights.** `agents/knowledge/`
   (IMP-0041) gains `azure-governed-tenant.md`, seeded NOW from this week's evidence
   (private-link policy → Option D recipe; Easy Auth v2 audience forms; in-worker JWT
   fail-closed pattern; principal-ID GUID vs oid resolution; MSAL readiness gating;
   deployer storage RBAC + OIDC workflow). Retro's knowledge pass + REPO's final-hygiene
   step both prompt capture when a run's reports contain deploy/auth iteration.
4. **Preflight consumes the knowledge file** — new landmines become new checks, so the
   tail shrinks monotonically per engagement instead of resetting.

## Acceptance criteria

- [ ] `skills/deploy-preflight/SKILL.md` + script exist; INFRA prompt references them;
      checks cover the six seeded landmines
- [ ] `scripts/smoke-auth.ps1` exists; QA runs it post-deploy in deploy-bearing pipelines;
      fail-closed negative included
- [ ] `agents/knowledge/azure-governed-tenant.md` seeded with ≥6 facts from the 7/14–16
      evidence, each with `Source:` provenance to a report path
- [ ] Retro/REPO knowledge-capture hook present for deploy/auth-iterating runs
- [ ] Next deploy-bearing run records ≤2 auth iterations (measured via IMP-0058 phase
      timing + IMP-0063 coverage)

## Validation plan

Deterministic: preflight + smoke scripts run against the existing PilotApp deployment
(read-only checks pass/fail sensibly; smoke asserts current live behavior). Structural:
skill/knowledge/prompt wiring. Real-run: the next provision-and-deploy engagement's
iteration count — irreducibly real, but cheap to read once 0063 records it.

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0064.py`) — files exist, INFRA/QA wiring
  present, knowledge facts carry provenance, smoke script has fail-closed assertion.
- **What we measure:** seeded-fact count, wiring presence; later: auth iterations per
  deploy run (KPI, target ≤2 vs 8 baseline).
- **Pass criteria:** structural green; smoke script exercises 401+200 paths against a
  local stub in CI.
- **Negative cases:** smoke flags an endpoint that accepts an unauthenticated request.
- **Known limits:** policy checks are best-effort reads of ARM state — some tenant
  policies only reveal themselves at apply time; the knowledge loop exists precisely to
  absorb those.

## Notes

- Filed by the 2026-07-16 review, third finding. Companion to IMP-0061/0062 (build-phase
  speed): this one targets the *tail*, which this week was 3× the build. Evidence base:
  `PilotApp-fanout-20260715/reports/qa-A2..A8*`, `PilotApp-deploy-20260715/reports/*`,
  PilotApp commits 9b3ba99..53907a2.
- Low risk: scripts + skill + knowledge file + small INFRA/QA prompt touches; no QB change.
