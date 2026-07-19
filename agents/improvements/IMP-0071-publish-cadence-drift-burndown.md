---
id: IMP-0071
title: Publish cadence — nightly-prepared mirror bundle + drift-threshold alerting
status: proposed
source: review-2026-07-19
affects: [meta]
risk: low
created: 2026-07-19
updated: 2026-07-19
commit: null
eval_type: structural
skip_validation: false
eval_id: imp_0071
eval_seed: 42
baseline_run: null
post_run: null
validation_evidence: []
manual_evidence: []
---

## Problem

IMP-0068 killed silent rot but not the cadence problem. The drift *signal* works —
nightly-2026-07-19 reported **21 canonical commits of drift one day after the last sync**
(91a1ffc -> 45e22f5). But acting on the signal still requires a human to remember to run
`scripts/publish-public-mirror.ps1` interactively, sit through stage/scrub/scan, review
the diff, and push. That is exactly the manual-chore shape that produced the original
5-week rot; the hard-ask (push) is cheap, but everything before it is not, so it gets
deferred and drift re-accumulates. The mirror was built to be a living showcase; a
permanently-stale mirror with a working drift line is only marginally better than no
mirror.

## Proposal

Make the human ask the *only* manual step; batch it, and alert when it's due:

1. **Nightly bundle prep (extends IMP-0034 Job 2):** when drift > 0, the nightly job runs
   the publish pipeline through its non-push stages — manifest stage → canon scrub →
   gitleaks → leak-lint → diff report — into the local mirror clone working tree
   (committed locally on a `pending-sync` branch or left staged; **never pushed**). The
   nightly report gains a "publish bundle ready" line with the diff-report path and the
   gate results. Reuse `scripts/publish-public-mirror.ps1` by adding a `-PrepareOnly`
   (no-prompt, no-push) mode rather than a second script; the nightly script invokes it
   where the `-DriftCheck` call already lives.
2. **Drift-threshold alert:** config (manifest or canon header, not code):
   `drift_alert_commits: 10`, `drift_alert_days: 3`. When either is exceeded, the nightly
   drift line escalates from informational to a flagged action item, and the morning
   briefing (IMP-0055, when it lands) carries it. Until 0055 exists, the nightly report
   header carries the flag.
3. **Batched approval:** the human ask becomes "review diff report at <path>, then run
   `publish-public-mirror.ps1 -PushApproved`" — one decision on an already-green bundle.
   Push remains a permanent human hard-ask (IMP-0068 posture unchanged); leak-gate
   failures during unattended prep abort the bundle and surface in the report, never
   auto-remediate.
4. **Safety invariants (unchanged from IMP-0068/0070):** allowlist manifest is the only
   stage source; full-tree fatal leak scan (IMP-0070) runs in prep; a failed gate leaves
   the mirror clone's published branch untouched.

## Acceptance criteria

- [ ] `-PrepareOnly` mode exists; nightly invokes it when drift > 0; no push path is
      reachable from the unattended run (asserted in script: `-PrepareOnly` and any
      push/approval flag are mutually exclusive)
- [ ] Nightly report renders bundle status: gates green/red, diff-report path, file count
- [ ] Threshold config present; a seeded over-threshold state renders the escalated flag
- [ ] A leak-gate failure during prep aborts the bundle, reports it, and leaves the
      mirror clone's published branch untouched
- [ ] One real cycle: nightly prepares a bundle, human approves, push lands, drift resets
      to 0 in the next nightly

## Validation plan

Deterministic: scripted prep run against the current 21-commit drift (real rehearsal at
scale), seeded leak-gate failure, seeded threshold breach. Irreducibly manual: the final
criterion's human approval — by design, it is the gate being preserved.

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0071.py`) — `-PrepareOnly` param present
  and mutually exclusive with push flags, nightly invocation present, threshold config
  parses, report render strings present.
- **What we measure:** unattended prep produces a bundle + report with zero interactive
  prompts; gate failure aborts cleanly; threshold escalation renders.
- **Pass criteria:** structural green; rehearsal shows bundle + report; seeded failure
  aborts without touching the published branch.
- **Negative cases:** unattended run with a push flag refuses; leak-gate hit blocks the
  bundle.
- **Known limits:** prep runs unattended against a moving canonical HEAD — the bundle
  records the SHA it staged so the human review is anchored; a push after further drift
  publishes the reviewed SHA, not HEAD.

## Results

<!-- Auto-populated by /Implement-Improvement and /Validate-IMP -->
<!-- Validation gate: see README.md §`validated` bar (4-point gate, IMP-0015) -->

| Metric | Baseline (mean ± σ, n) | Post (mean ± σ, n) | Delta | Regression? |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

**Quality / Speed / Cost summary** (Phase 1+ format):

- Quality: —
- Speed:   —
- Cost:    —

**Targeted evidence gate:** —

**Real-session corroboration:** —

## Notes

- Filed by the 2026-07-19 backlog review. Extends [[IMP-0068]] (pipeline) + IMP-0070
  (fatal scan) + IMP-0034 Job 2 (nightly host). Not gated behind Wave 7 — same
  user-requested "runs alongside" lane as 0068/0069/0070; implement opportunistically
  after the Wave 7 execution items.
- Evidence trail: mirror rotted 5 weeks pre-0068; drift re-accumulated to 21 commits
  within one day of the 07-18 sync (nightly-2026-07-19).
