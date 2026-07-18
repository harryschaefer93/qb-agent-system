---
id: IMP-0056
title: gh-aw evaluation — hardened agentic workflows for scheduled repo automation
status: proposed
source: research-2026-07-15
affects: [meta]
risk: medium
created: 2026-07-15
updated: 2026-07-17
commit: _pending_
eval_type: manual
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

Our scheduled automation (nightly evidence backfill, hygiene sweep, morning briefing) is
local PowerShell on one laptop — it dies when the machine is off and can't act on repos
directly. GitHub Agentic Workflows (gh-aw) compiles markdown workflow definitions into
hardened GitHub Actions (`.lock.yml`) that run agents (Copilot/Claude/Codex engines) on
schedules/issues/PRs/slash-commands with **safe outputs** (constrained, audited actions:
create-issue, assign-to-agent, create-agent-session) — potentially the right substrate
for repo-side automation like issue triage, continuous small improvements, and eventually
hosting the IMP-0054 intake checks.

## Proposal (evaluate-then-adopt — NOT a commitment)

1. **Spike on one personal repo:** install `gh aw`, compile two workflows —
   (a) scheduled weekly "repo health report" (read-only, creates one issue);
   (b) issue-triage labeler with safe outputs limited to labels/comments.
2. **Security review against our posture:** fine-grained PAT scoping (GitHub App tokens
   rejected by the assignment API — where does the PAT live, what can it reach), safe-
   output constraint model, prompt-injection surface of event-triggered agents (issue
   bodies are untrusted input — our `untrusted-content` partial rules must hold), and
   cost per run.
3. **Decision memo** recorded in this IMP: adopt (which workflows move), partial
   (personal repos only), or reject (stay on local scheduled scripts + IMP-0053 direct
   `gh agent-task` dispatch). Explicit criteria below.

## Adoption criteria (all must hold)

- [ ] PAT can be scoped to allowlisted repos only, stored in repo/org secrets — never in
      workflow markdown
- [ ] Safe outputs demonstrably block an out-of-contract action in a test
- [ ] Injection test: a malicious issue body cannot steer the triage workflow into an
      unapproved safe output
- [ ] Cost per scheduled run is within AI-credit budget (measure, don't guess)
- [ ] The two spike workflows run 2 weeks without operator intervention

## Eval Plan

- **Type:** manual (spike + decision memo). The deliverable is a recorded decision with
  evidence, not shipped automation.
- **Known limits:** gh-aw is an evolving framework — pin the CLI version in the spike;
  re-evaluate on breaking releases.

## Notes

- Wave 6 step 4 (`docs/wave6-cloud-delegation-plan.md`) — gated on IMP-0053/0054/0055
  being live first: prove the delegation loop manually before automating dispatch.
- Not a replacement for the local driver/pipeline — this is repo-side automation only.
  The QB orchestrator remains the local brain.
- **Addendum 2026-07-17 (sweep):** gh-aw remains a very active technical preview (since
  2026-02-13; 50+ PRs/week; safe-outputs security model; engines now include Copilot /
  Claude / Codex / OpenCode). **Releases 0.68.4–0.71.3 were retired for a billing bug —
  the spike must pin a newer, non-retired release and re-check the retired list at spike
  time.**
