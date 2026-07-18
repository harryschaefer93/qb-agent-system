---
id: IMP-0034
title: Headless & scheduled fleet operation (nightly hygiene, evidence backfill, PR review pilot)
status: implemented
source: review-2026-06-10
affects: [REPO, QA, retro, meta]
risk: low
created: 2026-06-10
updated: 2026-07-15
commit: aa4ff74
eval_type: manual
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

Production agents only run attended, inside VS Code, with a human driving. The only headless thing in the system is the eval harness. Gold-standard harnesses run the same agent attended *and* unattended (scheduled jobs, CI triggers, PR events). Concrete costs today:

- Secret/dependency hygiene on active POC repos happens only when someone remembers to invoke REPO.
- Retro evidence backfill (IMP-0022) is manual, so IMPs sit at `implemented` waiting for someone to run the CLI.
- PR review on POC repos has no agent in the loop at all.

## Proposal

Start with three unattended jobs, all read-only-plus-filing (no unattended job may push, change visibility, or mutate resources — those stay behind IMP-0028's hard asks):

1. **Nightly hygiene sweep:** gitleaks + dependency audit (Dependabot config check / `npm audit` / `pip-audit`) across active POC repos, via GitHub Actions or a local scheduled task running REPO's existing logic as scripts. Findings auto-filed as repo issues (or a local triage file), never auto-fixed.
2. **Scheduled evidence backfill:** `python -m runner.telemetry backfill` for all `implemented` non-structural IMPs, weekly, via scheduled task. Output lands as a findings file the retro agent (or the user) reviews — frontmatter edits still require explicit approval per IMP-0022's no-silent-edit rule.
3. **PR review pilot:** enable the GitHub Copilot coding agent (or an Actions-triggered review script using QA's checklist: FDPO violations, secret-shaped strings, managed-identity drift) as a PR reviewer on ONE active POC repo. Findings as PR comments only.

## Acceptance criteria

- [ ] Job 1 runs unattended on a schedule for 2 consecutive weeks, producing dated artifacts/issues, zero pushes
- [ ] Job 2 produces a weekly backfill findings file; at least one finding flows through retro review into an IMP's `manual_evidence`
- [ ] Job 3 live on one repo; ≥1 PR receives agent review comments
- [ ] Guardrail verified: no unattended job has credentials/permissions for push, visibility change, or Azure mutation
- [ ] Runbook documented (where jobs live, how to pause them, where findings land)

## Validation plan

Inspection over a 2-week soak: artifacts appear on schedule, findings are actionable, nothing wrote where it shouldn't. The PR pilot's value check: did the review comments catch anything QA-attended would have (FDPO drift is the likeliest win)?

## Eval Plan

- **Type:** manual (operational infrastructure; the deliverable is scheduled jobs + guardrails)
- **What we measure:** schedule adherence, artifact production, guardrail compliance, ≥1 useful finding per job over the soak
- **Pass criteria:** all acceptance checkboxes after the 2-week soak
- **Known limits:** the PR-review pilot's model/runtime differs from the VS Code fleet — treat its behavior as its own track, not as QB-fleet evidence.

## Results (partial — Jobs 1+2 shipped)

**Job 1 (nightly hygiene sweep) implemented 2026-07-14** as `scripts/nightly-hygiene-sweep.ps1`:
per git repo under repos/clients + repos/general (bounded, read-only) — gitleaks working-tree
scan, Dependabot-config presence, `npm audit` prod-dep highs/criticals; findings filed to
`agents/files/nightly/hygiene-<date>.md`, toast on findings, never auto-fixed. First smoke run:
6 repos, 9 real findings. Registration one-liner in the script header (8:45 AM daily,
StartWhenAvailable).

**Job 2 (scheduled evidence backfill) implemented** as `scripts/nightly-evidence-backfill.ps1`:
runs the structural CI gate, `telemetry kpi --since 7d --json`, `pipeline list --incomplete`
(abandoned-run surfacing), and `telemetry backfill` for the scorer-backed implemented IMPs
(0004/0020/0026/0036/0039/0042); files a dated report to `agents/files/nightly/` and fires
`notify.ps1` when the gate fails, incomplete runs exist, or evidence candidates await review.
Guardrail honored: read-only + filing; no pushes, no frontmatter edits (findings require human
approval per IMP-0022). Smoke-tested 2026-07-13: gate PASS, 1 incomplete run surfaced, toast fired.

**Runbook:** register (one-time, user-run — the harness classifier blocks agents creating
scheduled tasks). Use the sleep-robust form (`StartWhenAvailable` = a 09:00 firing missed
because the laptop was asleep/off runs as soon as you're back; plain `schtasks /create` would
silently skip the day):

```powershell
$action   = New-ScheduledTaskAction -Execute 'pwsh' -Argument '-NoProfile -ExecutionPolicy Bypass -File ~\.copilot\scripts\nightly-evidence-backfill.ps1'
$trigger  = New-ScheduledTaskTrigger -Daily -At 9:00AM
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName 'QB Nightly Evidence Backfill' -Action $action -Trigger $trigger -Settings $settings -Description 'IMP-0034 Job 2 - read-only fleet health + evidence backfill'
```

Test now: `Start-ScheduledTask -TaskName 'QB Nightly Evidence Backfill'` · pause:
`Disable-ScheduledTask -TaskName 'QB Nightly Evidence Backfill'` · remove:
`Unregister-ScheduledTask -TaskName 'QB Nightly Evidence Backfill' -Confirm:$false` ·
findings: `agents/files/nightly/nightly-<date>.md`.

**Job 3 absorbed 2026-07-15:** the PR-review pilot is superseded by IMP-0054 (PR intake
pipeline — full 10-minute framework, rulesets, iterate loop) per the Wave 6 plan; do not
implement separately. Original text follows for the record.

Hygiene sweep registration is in the Job-1 script header (8:45 AM daily). The 2-week
unattended soak starts when the user registers both tasks.

## Notes

- Source: 2026-06-10 gap analysis, gap #4.
- **Bookkeeping fix 2026-07-15 (review session):** frontmatter was stale at
  `proposed`/`commit: null` while Jobs 1+2 had shipped. Re-scoped to Jobs 1+2 and set
  `implemented` — Job 1 = commit aa4ff74 (`nightly-hygiene-sweep.ps1`), Job 2 = commit
  1f62410 (`nightly-evidence-backfill.ps1`), sleep-robust registration runbook = 20637c4.
  Job 3 absorbed into IMP-0054 (Wave 6) — do not implement separately. Acceptance
  checkboxes stay unticked until the 2-week soak completes (validation gate unchanged).
- Deliberately starts with jobs that reuse existing assets (REPO's scan logic, telemetry CLI, QA's checklist) — no new agent definitions required.
- Future (not this IMP): unattended QA deep-review runs; scheduled retro weekly reports.
