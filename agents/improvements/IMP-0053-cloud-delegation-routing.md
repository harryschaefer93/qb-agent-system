---
id: IMP-0053
title: Cloud delegation routing — QB dispatches delegable work to the Copilot coding agent
status: proposed
source: user-2026-07-15
affects: [QB, REPO, meta]
risk: medium
created: 2026-07-15
updated: 2026-07-17
commit: _pending_
eval_type: structural
skip_validation: false
eval_id: imp_0053
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

Every implementation phase runs locally inside the interactive session, so the operator's
machine and attention are the throughput ceiling — overnight local DRIVE runs are a
workaround for not using the platform's native async path. The Copilot cloud coding agent
(ephemeral Actions environment, PR per task, `gh agent-task create` since gh CLI 2.80)
exists precisely for well-scoped work, and delivered repos already carry AGENTS.md
(IMP-0048) that it reads.

## Proposal

1. **Delegability assessment in classification.** After the `## Task Classification`
   block, QB scores the task against the delegation contract: single repo, well-scoped
   (concrete files/acceptance known), completable within the cloud agent's 59-minute
   session limit, task class in {bug-fix, small feature-request, test-coverage, docs,
   refactor-mechanical}, and **repo on the delegation allowlist**. Delegable → CP2 offers
   "Delegate to cloud" alongside local execution, with cost note (AI credits).
2. **Delegation contract in the dispatch.** The `gh agent-task create` body (or issue
   assigned to Copilot) carries: EARS acceptance criteria from the BRIEF/playbook, FDPO
   constraints verbatim (Entra-only, no keys — from `agents/partials/fdpo.md`), explicit
   out-of-scope list, and "do not weaken CI" (the IMP-0054 red-flag list stated as
   instructions). One task = one PR.
3. **Run-state tracking.** `delegations[]` in run-state (schema addition, additive-
   optional): `{task, repo, session_url, pr_url, dispatched, status, iterations}`.
   `pipeline status`/`resume` surface open delegations.
4. **WIP cap (single-operator rule).** Max **3** concurrent open delegations across all
   repos; QB refuses to dispatch past the cap and says which existing delegation to
   close first. Cap is config, not prompt-vibes: read from `delegation-allowlist.json`.
5. **Repo allowlist with a hard governance boundary.** `agents/delegation-allowlist.json`
   starts with personal repos only (PilotApp first). **Customer repos are excluded until
   a recorded data-governance review (owned by IMP-0059)** — the cloud agent runs in
   GitHub's cloud and does not respect content exclusions; FDPO posture extends to where
   customer context is allowed to execute, not just how code authenticates.

## Acceptance criteria

- [ ] Delegability rule + CP2 "Delegate to cloud" option in QB (within line cap)
- [ ] `delegations[]` in run-state schema + driver read/write + pytest
- [ ] `agents/delegation-allowlist.json` with WIP cap and personal-repos-only seed
- [ ] Dispatch template embeds EARS acceptance + FDPO constraints + CI-integrity rules
- [ ] Pilot: ≥2 real delegated PRs on PilotApp merged with ≤2 iteration rounds each
- [ ] Negative: a customer-repo delegation attempt is refused with the governance reason

## Eval Plan

- **Type:** structural (evaluator: QB rule present, allowlist exists w/ cap, schema field,
  dispatch template contains FDPO + EARS markers) + manual pilot evidence.
- **Known limits:** `gh agent-task` output format may drift; session steering happens in
  Agent HQ mission control (platform UI), not our tooling.

## Notes

- Wave 6 anchor IMP (plan: `docs/wave6-cloud-delegation-plan.md`). Depends on: IMP-0048
  (AGENTS.md in repos — shipped), IMP-0051 delivery contract (branch/push intent pinned
  at CP2 applies to delegations too). Feeds IMP-0054 (every delegation lands in the PR
  intake gate) and IMP-0055 (briefing lists open delegations).
- Delegation dispatch itself is reversible (close the PR/session) but spends AI credits →
  notify-and-proceed at `standard` within the WIP cap; the resulting **merge** is where
  the real gate lives (IMP-0054).
- **Addendum 2026-07-17 (sweep, CLI-native path):** the CLI now dispatches to the coding
  agent directly — `&` prompt prefix and `/delegate`; `Tab` / `--connect[=sessionId]`
  resumes local **and** remote sessions; remote sessions authenticate through corporate
  proxies (1.0.64). The pilot may use `gh agent-task` or the CLI-native path, whichever
  proves out; `--connect` provides the steering surface previously attributed only to
  Agent HQ. No criteria change.
