---
id: IMP-0055
title: Single-operator control plane — morning briefing, notification routing, delegation KPIs
status: proposed
source: user-2026-07-15
affects: [retro, meta]
risk: low
created: 2026-07-15
updated: 2026-07-17
commit: _pending_
eval_type: structural
skip_validation: false
eval_id: imp_0055
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

User (2026-07-15): "the need to be able to manage all this without it becoming a single
operator nightmare is key." A mixed local + cloud fleet multiplies surfaces: local runs,
cloud sessions, PRs awaiting review, nightly job findings, KPI drift. Unbatched, that is
N notification streams competing for one person's attention — the failure mode that kills
solo agent fleets. GitHub's Agent HQ mission control already provides the live fleet view
(assign, steer, session logs, PR jump-off); what's missing is the **daily batched digest**
and the **attention policy**.

## Proposal

**Integrate, don't build.** Agent HQ mission control is the real-time console — we add
only the thin layers it doesn't do:

1. **Morning briefing** (`scripts/morning-briefing.ps1`, scheduled ~8:30 AM, read-only,
   same pattern as the nightly jobs): one markdown report + one toast —
   (a) PRs awaiting verdict (gh CLI: agent PRs + REPO verdict digests from IMP-0054);
   (b) open delegations vs WIP cap (run-state `delegations[]`);
   (c) incomplete/stale local runs (`pipeline list --incomplete`);
   (d) last night's evidence-backfill + hygiene-sweep findings (existing reports);
   (e) KPI snapshot (completion rate, delegation success rate, iterations/PR,
       human-minutes/PR trend).
2. **Notification routing policy (the attention contract), enforced in prompts + scripts:**
   - **Toast immediately:** blocking checkpoint waits, hard-asks, failed delegation
     sessions, security findings. Nothing else.
   - **Morning briefing:** everything above (PRs ready for review, completions, KPI drift).
   - **Weekly retro:** trends, playbook/allowlist growth proposals, matrix tuning.
   QB/REPO/scripts must not toast outside this policy (extends the IMP-0039 three-point
   notification rule to the fleet).
3. **Delegation KPIs in telemetry + retro.** Extend `runner.telemetry kpi` and retro
   Phase 0 with: delegation success rate (merged / dispatched), iterations per PR,
   human minutes per PR (verdict-to-merge timestamps), WIP-cap hits. Retro recommends
   allowlist/cap changes as IMPs — never silently.
4. **Agent HQ usage notes** in `docs/wave6-cloud-delegation-plan.md` companion runbook:
   where to steer sessions, read logs, and stop runaway sessions — so the operator's
   muscle memory is one console + one briefing.

## Acceptance criteria

- [ ] `morning-briefing.ps1` produces the 5-section report from real data; registration
      one-liner in header (user registers — scheduled-task classifier rule)
- [ ] Notification policy encoded (QB/REPO prompt lines + scripts honor toast list)
- [ ] `kpi` + retro render delegation metrics once ≥1 delegation exists
- [ ] Two weeks of use: user reports the briefing replaced ad-hoc checking (judgment)

## Eval Plan

- **Type:** structural (script exists + sections; policy lines present; kpi fields) +
  manual operator judgment after live use.
- **Known limits:** human-minutes/PR is approximated from timestamps; Agent HQ is a
  moving preview surface — our layer deliberately reads only gh CLI + local state, so
  UI changes can't break us.

## Notes

- Third leg of Wave 6 (`docs/wave6-cloud-delegation-plan.md`): 0053 creates flow, 0054
  gates it, 0055 makes it survivable for one person. Ship before exceeding 3 concurrent
  delegations.
- Deliberately NOT a dashboard/web app: one scheduled read-only script + existing toast
  plumbing (IMP-0034 pattern) + the platform's own console. Zero new infrastructure to
  babysit — the control plane must not itself become an operand.
- **Addendum 2026-07-17 (sweep):** the **GitHub Copilot app** (announced Build
  2026-06-02, technical preview) is a desktop mission control running parallel agent
  sessions each in its own isolated worktree; **agent finder** (2026-06-17) auto-discovers
  the right MCP server/skill/agent per task. Both strengthen "integrate, don't build" —
  the briefing layer here stays unchanged; evaluate the app vs the Agent HQ web console
  as the surface once it stabilizes.
