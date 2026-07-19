---
id: IMP-0064
title: Kill the deploy/auth tail — governed-tenant preflight, live-auth smoke, landmine knowledge capture
status: implemented
source: review-2026-07-16
affects: [INFRA, QA, DEV, retro, REPO]
risk: low
created: 2026-07-16
updated: 2026-07-18
commit: 7f09d14
eval_type: structural
skip_validation: false
eval_id: imp_0064
eval_seed: 42
baseline_run: baselines/IMP-0064/20260718-150543-63107b4-baseline.json
post_run: baselines/IMP-0064/20260718-153623-7f09d14-post.json
validation_evidence:
  - evidence_id: deterministic-imp-0064-2026-07-18
    source: deterministic
    verdict: pass
    captured: 2026-07-18
    artifact: evals/baselines/IMP-0064/20260718-153623-7f09d14-post.json
    artifact_sha256: 20caab71c68d2f03774c9ac8006cc43bc8e49db6017cda444747ecac044b6653
    implementation_commit: 7f09d14cf6b12b72c5318fce179b808431aa4176
    evaluated_commit: 7f09d14
    artifact_commit: 8cc3941214eadf9f9088a99bab30a3cc0bd28f86
    evaluator_artifacts: [evals/evaluators/custom/imp_0064.py]
    evaluator_sha256: b4b1eae86eaefd1f6848dcf9bbb17d7975ccb9c0c56e534790f3e1b22a95ee21
    dataset_artifacts: []
    dataset_sha256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    subject_artifacts: [agents/DEV.agent.md, agents/INFRA.agent.md, agents/QA.agent.md, agents/REPO.agent.md, agents/knowledge/global/azure-governed-tenant.md, agents/retro.agent.md, agents/retro.md, scripts/deploy-preflight.ps1, scripts/smoke-auth.ps1, skills/deploy-preflight/SKILL.md]
    subject_sha256: a82898fb969cc5529cab677a9c1f95b8fb44d220367be41ba4090db27eadfb97
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
   401/403 fail-closed for bad/absent tokens and 200 for good. QA runs it immediately after
   every deploy phase; DEV gets its output verbatim. Track A's eight iterations were
   this loop performed manually and diagnostically blind.
3. **Landmine knowledge capture is mandatory after deploy fights.** `agents/knowledge/`
   (IMP-0041) gains `global/azure-governed-tenant.md`, seeded NOW from this week's evidence
   (private-link policy → Option D recipe; Easy Auth v2 audience forms; in-worker JWT
   fail-closed pattern; principal-ID GUID vs oid resolution; MSAL readiness gating;
   deployer storage RBAC + OIDC workflow). Retro's knowledge pass + REPO's final-hygiene
   step both prompt capture when a run's reports contain deploy/auth iteration.
4. **Preflight consumes the knowledge file** — new landmines become new checks, so the
   tail shrinks monotonically per engagement instead of resetting.

## Acceptance criteria

- [x] `skills/deploy-preflight/SKILL.md` + script exist; INFRA prompt references them;
      checks cover the six seeded landmines
- [x] `scripts/smoke-auth.ps1` exists; QA runs it post-deploy in deploy-bearing pipelines;
      fail-closed negative included
- [x] `agents/knowledge/global/azure-governed-tenant.md` seeded with ≥6 facts from the 7/14–16
      evidence, each with `Source:` provenance to a report path
- [x] Retro/REPO knowledge-capture hook present for deploy/auth-iterating runs
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
- **2026-07-18 implementation:** deterministic fixture preflight and local auth stub pass.
  Read-only PilotApp preflight returns `warn` only for the detected private-link/public-
  network policy risk; storage tag bypass, local auth, OIDC/RBAC, dual audiences, and
  managed-identity IDs pass. Live valid-token smoke remains blocked by Azure CLI consent;
  no interactive login or Azure mutation was attempted.
- **2026-07-18 corrective review:** the first anonymous probe bound `$null` to a PowerShell
  `[string]`, which emitted an empty `Authorization: Bearer` header instead of omitting the
  header. Commit `7f09d14` added an explicit omit-header path; the local wire-level
  regression now requires anonymous `401`, malformed bearer `403`, and valid bearer `200`.

## Results

| Metric | Baseline (mean ± σ, n) | Post (mean ± σ, n) | Delta | Regression? |
|---|---|---|---|---|
| pass_rate | 0.200 | 1.000 | +0.800 | No |
| all_passed | false | true | +1 | No |
| passed_checks | 5/25 | 25/25 | +20 | No |
| total_checks | 25 | 25 | 0 | No |

**Quality / Speed / Cost summary:**

- Quality: 0.200 → 1.000 (+0.800) ✓
- Speed:   30 ms → 50 ms (+67%) ✓
- Cost:    $0.0000 → $0.0000 (no signal) ✓

**Targeted evidence gate:** structural evaluator passes 25/25. Deterministic pytest
passes script parsing, all-six-check fixture success, mixed pass/warn/fail output,
wire-level no-header `401`, malformed-bearer `403`, valid-token `200`, token redaction,
and six-source knowledge provenance.

**Read-only Azure check:** existing PilotApp deployment returns five passes plus one
policy warning; no Azure resource was changed. Live valid-token smoke could not acquire
Azure CLI consent and remains open.

**Real-run validation debt:** the next qualifying deploy-bearing run must record no more
than two auth iterations before this IMP can graduate.
