---
id: IMP-0063
title: Run-record coverage — pipeline-bypass work becomes visible to KPIs
status: proposed
source: review-2026-07-16
affects: [QB, meta]
risk: low
created: 2026-07-16
updated: 2026-07-16
commit: null
eval_type: structural
skip_validation: false
eval_id: imp_0063
eval_seed: 42
baseline_run: null
post_run: null
validation_evidence: []
manual_evidence: []
---

## Problem

The KPI system saw 2 runs in the last 7 days (completion 1.0, mean cycle 430.9 min).
Reality: **5 run-shaped efforts** on PilotApp. Three wrote reports into the *workspace's*
`session-state/` with **no run-state.json anywhere**, so nightly/KPI/retro never saw them:

- `PilotApp-repo-20260714` — deploy attempts, RBAC/OIDC, VNet fix, MI resilience (~12:35–16:08)
- `PilotApp-deploy-20260715` — provision/deploy/teardown, Option D pivot, config fixes (~08:43–12:10)
- `PilotApp-fanout-20260715` — 5-track fan-out (A auth / B fail-closed / C portal / D preview /
  E playwright+CI); ~40 reports spanning **25+ hours** (7/15 12:33 → 7/16 13:17, still active);
  track A iterated A2→A8 on live auth

Additionally the one tracked run (`PilotApp-webpublic-20260714`) stores run-state in the
home store (`~/.copilot/session-state/`) while its `artifact_path` values are
workspace-relative — they dangle from where KPI reads. Net effect: **the KPI page reports
a healthy minority while the majority of DEV time (the multi-day deploy/auth tail) is
invisible** — completion 1.0 is survivorship bias. Git corroborates: 29 commits across
7/14–7/16 vs zero recorded runs in that span.

## Proposal

1. **One canonical run root.** Driver always writes run-state.json to the home store;
   artifact paths stored resolvable (absolute, or `{workspace}/`-prefixed and resolved via
   the record's `workspace` field). Workspace `session-state/<run-id>/` keeps the reports
   (already gitignored there) — the record points at them.
2. **QB rule: implementation work requires an active run id.** Fan-out, deploy iteration,
   and post-delivery fixes either `pipeline resume` the parent run or
   `pipeline start --task-type bug-fix` a cheap child run (one line; autonomy dial
   unaffected). No run id → no DEV/INFRA dispatch. Pays for itself: these sessions already
   write per-agent reports by convention, they just skip the 2-second driver call.
3. **Coverage metric in telemetry.** `kpi` scans both roots for report-bearing run dirs
   without run-state.json + sessions carrying `run_state_artifact` fingerprints with no
   matching record → renders **"untracked work"** (dirs, report count, span) and a
   coverage % line in nightly. Untracked ≠ silently dropped.
4. **Backfill the three July dirs** as reconstructed records (`reconstructed: true`,
   timings from report mtimes) so this week's history is queryable.

## Acceptance criteria

- [ ] Driver writes home-store record with resolvable artifact paths; existing
      relative-path records resolve via `workspace` (webpublic-20260714 paths resolve)
- [ ] QB prompt carries the active-run-id rule (within line cap)
- [ ] `kpi`/nightly render untracked-work + coverage %; the three July dirs show up
      before backfill, zero untracked after backfill
- [x] Backfilled records exist for repo-20260714 / deploy-20260715 / fanout-20260715
      with `reconstructed: true` (done 2026-07-16, same-day as filing — see Notes)
- [ ] Negative: a report-bearing dir with no record is never counted in completion_rate

## Validation plan

Deterministic: pytest on path resolution + coverage scan against a fixture tree mirroring
the July layout. Real: next nightly renders coverage; next post-delivery fix session
creates/resumes a run record. Irreducibly manual: none.

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0063.py`) — driver path logic, QB rule
  present, kpi coverage fields, backfilled records exist.
- **What we measure:** coverage % (target 100% on new work), dangling-path count (0).
- **Pass criteria:** structural green; fixture scan finds seeded untracked dir; July
  backfill present.
- **Negative cases:** seeded record with dangling artifact path flagged; untracked dir
  excluded from completion_rate.
- **Known limits:** reconstructed timings are mtime-derived (no per-phase start).

## Notes

- Filed by the 2026-07-16 review, second finding ("we only have 7/13? did the other days
  not run?" — they ran; they were invisible). Measurement-integrity prerequisite for the
  Wave 7 speed IMPs: IMP-0058 addendum gives phase timing, this gives *complete* runs.
- The fanout-20260715 dir doubles as the evidence base for IMP-0064 (deploy/auth tail).
- **2026-07-16 — partial ship, same session as filing (user: "fix those missed ones
  retroactively"):**
  - **Backfill done** (criterion 4): 3 reconstructed records written with real report-mtime
    phase timings + `reconstruction` caveat blocks. Verified: `kpi --since 7d` now shows
    5 runs (was 2), and `pipeline list --incomplete` surfaces fanout-20260715 as `active`
    (track A still iterating at last observation) so QB's resume pre-flight offers it.
    Timings are conservative — repo-20260714's true span is likely ~8h (git evidence) vs
    the 3.5h recorded from batch-stamped mtimes.
  - **Detection half done**: untracked-work scan added to
    `scripts/nightly-evidence-backfill.ps1` (scans home store + every recorded workspace's
    `session-state/` for report-bearing dirs without a home-store record; report section +
    toast alert). Tested: found the 3 missed runs pre-backfill, 0 after; both report
    branches render; script parses clean.
  - **Still open (the prevention half + polish):** driver canonical-root/artifact-path
    resolution (criterion 1), QB active-run-id rule (criterion 2), coverage % in `kpi`
    itself + negative test (criteria 3/5), evaluator `imp_0063.py`. Detection-only means a
    bypassed run is caught next morning, not prevented — status stays `proposed` until the
    QB rule + driver change ship via the imp workflow.
