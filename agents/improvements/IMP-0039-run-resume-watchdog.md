---
id: IMP-0039
title: Run resume + abandoned-run surfacing + checkpoint notifications
status: implemented
source: review-2026-07-13
affects: [QB, meta]
risk: low
created: 2026-07-13
updated: 2026-07-13
commit: 907f0d8
eval_type: structural
skip_validation: false
eval_id: imp_0039
eval_seed: 42
baseline_run: null
post_run: baselines/IMP-0039/20260713-131259-8fae71c-post.json
manual_evidence: []
---

## Problem

Pain point #1 (user-reported 2026-07-13): "I'll give it a task and it doesn't actually finish." IMP-0036 (goal contract + DRIVE mode) attacks in-session premature yield, but a whole class of non-completion is invisible to it: **the session ends** — VS Code closes, the window dies, the user walks away from an unanswered CP2 — and the run is simply gone. Three concrete gaps:

1. **Abandoned runs are not surfaced.** `run-state.json` (IMP-0026) persists everything needed to resume, but nothing lists incomplete runs. A fresh QB session starts from zero; the half-finished run rots in `session-state/` unseen. The IMP-0005 resume prose ("open a fresh session; it will auto-resume") has no mechanical path.
2. **No rehydration bundle.** Even if QB knew a run existed, reconstructing "where was I" means re-reading full reports — exactly the context spend IMP-0026 exists to avoid.
3. **Checkpoint waits and stalls are silent.** A CP2 `askQuestions` that the user never sees (attention elsewhere) becomes an abandoned run with no signal to anyone. Nothing distinguishes "working" from "stuck" from "waiting on you."

## Proposal

Driver-side (deterministic, `evals/pipeline/`):

1. **`python -m pipeline list [--incomplete] [--workspace <path>]`** — scans `session-state/*/run-state.json`; returns run_id, task_type, workspace, current phase, phases_remaining, last_activity, age, and effective status (`active` | `complete` | `abandoned`). A stored-active run with `phases_remaining > 0` and `last_activity` older than 24h reports as `abandoned`.
2. **`python -m pipeline resume --run-id <id>`** — read-only rehydration bundle: state summary, approvals on file, per-phase ledger, `allowed_next_actions`, and the first ≤10 lines (the digest header) of each phase report. No state mutation.
3. **`python -m pipeline abandon --run-id <id>`** — marks a run `abandoned` (terminal) so it stops appearing in `--incomplete`.
4. **Activity stamping** — `start`/`advance`/`escalate`/`abandon` write `last_activity`; `status` (a read) does NOT, and instead reports `minutes_since_last_activity` — the stall signal.
5. **Schema extensions** (`run-state.schema.json`, all optional for back-compat): `workspace`, `last_activity`, `status`, `final_verdict`, `escalations[]`, `gate_bounces[]`, `cost_estimates`. Checkpoint outcomes need no new field — `approvals[]` (IMP-0026) already records presented/chosen/modified.

QB-side (`agents/QB.agent.md`, two surgical edits):

6. **Kickoff pre-flight:** before the BRIEF preflight, run `pipeline list --incomplete --workspace <workspace root>`. If a match: `askQuestions` — Resume `<id>` at phase `<P>` (N remaining) / Start fresh / Abandon old run. On resume: call `pipeline resume`, rebuild the todo goal contract from `phases_remaining`, and re-enter DRIVE directly — CP2 approval is already in `approvals[]`; do not re-ask.
7. Replace the IMP-0005 auto-resume sentence with the concrete resume command.

Notification-side:

8. **`scripts/notify.ps1`** — Windows toast (BurntToast if present, else a msg/console fallback) with title + message. QB invokes it when (a) posting a CP2 `askQuestions` and entering a wait, (b) emitting `## QB Result`, (c) a resume pre-flight finds an abandoned run. Long DRIVE runs stop requiring babysitting; unanswered checkpoints stop silently becoming abandoned runs.

## Acceptance criteria

- [ ] `pipeline list/resume/abandon` exist with unit tests; `list --incomplete` excludes complete and abandoned runs; staleness >24h reports `abandoned`
- [ ] `resume` returns approvals + digests without mutating state; digests are ≤10 lines per report
- [ ] `start`/`advance` stamp `last_activity`; `status` reports `minutes_since_last_activity` without writing
- [ ] Schema round-trips: driver-written state validates under the extended schema; a pre-IMP run-state (no new fields) still validates
- [ ] QB.agent.md contains the pre-flight `pipeline list --incomplete` step and the resume-without-re-asking-CP2 rule
- [ ] `scripts/notify.ps1` exists; QB.agent.md names the three invocation points
- [ ] Real-session: kill a session mid-pipeline; a fresh session offers resume and the run completes

## Validation plan

Deterministic parts by pytest + structural eval. The behavioral half: deliberately kill one real session mid-pipeline (post-CP2), open a fresh session, confirm QB's pre-flight offers the run, resumes without re-asking CP2, and drives to `## QB Result`. That trace is the manual_evidence; if QB fails to offer resume, convert the trace via IMP-0030's trace-to-eval into a regression case.

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0039.py`) + driver pytest
- **What we measure:** subcommands present and behaving (list/resume/abandon round-trip in a temp state dir); schema fields present; QB prompt contains pre-flight command + resume rule + notify invocation points; notify.ps1 exists
- **Pass criteria:** all structural checks green; pytest 100%
- **Negative cases:** `resume` on unknown run refuses with `unknown_run_id`; `list --incomplete` omits a completed run; `abandon` twice refuses second time (`already_terminal`)
- **Known limits:** whether opus-QB reliably runs the pre-flight and offers resume is production behavior — real-session evidence required before `validated`.

## Results

<!-- Auto-populated by /Implement-Improvement and /Validate-IMP -->

| Metric | Baseline (mean ± σ, n) | Post (mean ± σ, n) | Delta | Regression? |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

**Real-session evidence:** _pending — kill-and-resume session required_

## Notes

- Source: 2026-07-13 supercharge review (pain point #1, completion). Complements IMP-0036: DRIVE mode governs *in-session* completion; this governs *cross-session* completion. Both feed IMP-0030's completion-rate KPI.
- Depends on IMP-0026 (run-state substrate) and IMP-0027 (driver). Feeds IMP-0028 (a resumable, notify-capable pipeline makes relaxed autonomy safer).
- Deliberate deviation from the plan sketch: `status` does not stamp `last_activity` (stamping on reads would defeat stall detection); `checkpoint_outcomes[]` not added (redundant with `approvals[]`).
