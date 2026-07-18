---
id: IMP-0043
title: Best-of-N parallel DEV attempts on contested fixes
status: proposed
source: review-2026-07-13
affects: [QB, DEV, QA, REPO]
risk: medium
created: 2026-07-13
updated: 2026-07-13
commit: null
eval_type: manual
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

The 2-cycle iteration limit's failure mode is an escalation that dumps the problem back on the
user. Codex cloud's `--attempts` shows the alternative: on a contested fix, spend test-time
compute — several independent solution attempts, pick the best. QB's most painful failure mode
(grind → escalate → manual surgery) becomes its strength. (2026-06-11 harness research
candidate #2.)

## Proposal

**Trigger:** a fix fails its 2nd fix-validate cycle (the existing escalation point). Instead of
escalating immediately, QB offers "try N parallel attempts" at the escalation `askQuestions`:

1. REPO runs `fanout-setup.ps1` with attempt tracks (`attempt/1..N`, N ≤ 3) — IMP-0033
   machinery reused verbatim.
2. Each attempt's DEV prompt carries a *different approach hint* (from QA's blocker analysis:
   e.g. "fix at the caller", "fix in the middleware", "replace the dependency").
3. QA compares attempts against the baseline/invariants (refactor/optimization) or the blocker
   list (bug-fix) and ranks them.
4. QB presents the winner (or the comparison when it's close) at an `askQuestions`; losing
   attempt branches are discarded via `rewind.ps1 -DiscardTrack`.

**Cost bounds:** only fires on contested fixes (never first-pass), N ≤ 3, user opts in at the
escalation, attempts are time-boxed by the existing iteration protocol.

## Acceptance criteria

- [ ] Escalation `askQuestions` offers best-of-N when a 2nd cycle fails; user opt-in required
- [ ] N parallel attempts run in isolated worktrees with distinct approach hints
- [ ] QA comparison report ranks attempts against baseline/blockers with evidence
- [ ] Losing branches discarded; winner merges through the standard merge gate + quality gates
- [ ] Run record captures attempts, hints, winner, and cost estimates (IMP-0030)

## Validation plan

One real contested fix (or a rehearsed one with a seeded stubborn bug): confirm opt-in,
isolation, comparison quality, and cleanup. Cost per best-of-N run reviewed in retro KPIs.

## Eval Plan

- **Type:** manual (orchestration behavior; the git machinery is already covered by IMP-0033's
  deterministic tests)
- **What we measure:** trigger discipline (never fires pre-escalation), attempt isolation,
  winner quality vs the escalate-to-user baseline
- **Known limits:** value depends on approach-hint diversity — needs real cases to tune.

## Notes

- Source: 2026-06-11 harness research candidate #2, scheduled by the 2026-07-13 supercharge
  review (Wave 6 backlog).
- **HARD DEPENDENCY: implement only after IMP-0033 is `validated`** (one real multi-track
  fan-out session) — this IMP is pure reuse of that machinery.
- **Reframed 2026-07-15 (Wave 6, `docs/wave6-cloud-delegation-plan.md`):** the natural
  best-of-N substrate is now **parallel Copilot cloud-agent sessions** (N sessions on the
  same delegation contract → N PRs → REPO `pr-review` mode picks; losers closed unmerged)
  rather than local worktrees — zero local resource contention and the intake gate
  (IMP-0054) already scores candidates. Local-worktree best-of-N remains the fallback for
  non-delegable tasks. Adds dependencies: IMP-0053 (dispatch) + IMP-0054 (intake) live.
