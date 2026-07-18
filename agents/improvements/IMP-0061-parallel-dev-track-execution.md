---
id: IMP-0061
title: Parallel DEV track execution — dependency waves over worktrees, not serial runSubagent
status: proposed
source: review-2026-07-16
affects: [QB, DEV, REPO, meta]
risk: medium
created: 2026-07-16
updated: 2026-07-17
commit: null
eval_type: structural
skip_validation: false
eval_id: imp_0061
eval_seed: 42
baseline_run: null
post_run: null
validation_evidence: []
manual_evidence: []
---

## Problem

DEV is 80–97% of run wall clock, and its tracks execute **serially** even when they are
independent. Evidence (report-file mtimes, run `PilotApp-20260713-0837`, 8.9h total):

```
ARCH done        09:13
foundation-dev   11:48   (2h35m)
dev-core-dev     12:58   (1h10m)  ← depends on foundation
dev-ai-dev       14:01   (1h03m)  ← depends on foundation
dev-web-dev      15:19   (1h18m)  ← depends on foundation
```

DEV segment ≈ 6h05m of serial track time. Core/AI/Web are mutually independent (each has
its own worktree + owned paths per IMP-0033); run as a wave after Foundation the critical
path is ~3h53m — **a ~36% cycle-time cut on identical work, before any scope change**.
The second July run (`PilotApp-webpublic-20260714`) was one DEV segment of ~5h32m = 97%
of the run. Root cause: `agent/runSubagent` inside a single interactive session is
one-at-a-time by construction. IMP-0033 shipped physical isolation (worktrees, attributed
merges) but nothing dispatches tracks concurrently — "task-DAG wave execution" has been
parked in EXECUTION-ORDER's Wave 6 with no IMP number. This numbers it.

## Proposal

1. **Wave computation in the driver.** `tracks:` in ARCHITECTURE.md already declares
   per-track owned paths; add an optional `depends_on:` per track. Driver computes
   topological waves (wave 0 = no deps, wave 1 = deps satisfied, …) and exposes them via
   `pipeline status`. Missing `depends_on` ⇒ conservative default (single serial wave, so
   existing runs are unchanged).
2. **Parallel dispatch backend (local).** `scripts/fanout-dispatch.ps1`: for each track in
   the current wave, launch a headless `copilot` CLI worker (`copilot -p … --agent DEV`)
   pinned to that track's worktree, with the friction-doc `--allow-tool` allowlist (build/
   test/read-only auto-approved; push/deploy/destructive denied — REPO still owns git).
   Concurrency cap **3** (mirrors the Wave-6 WIP cap; config not prompt). QB dispatches a
   wave, waits on all workers, reads per-track report artifacts, then proceeds — the QB
   session itself stays the single control point.
3. **Real per-track timing in run-state.** Each track phase records genuine
   `started`/`finished` (today both are stamped at completion — see IMP-0058 addendum), so
   the serial-vs-wave saving is measurable, not vibes.
4. **Merge gate unchanged.** `fanout-merge` stays sequential with per-track conflict
   attribution (IMP-0033). One failed track bounces that track only; completed tracks'
   worktrees are untouched.
5. **Cloud backend later.** Once IMP-0053 lands, delegable tracks can run as cloud
   sessions instead of local workers — same wave abstraction, different executor.

## Addendum (2026-07-17): dispatch backend — native /fleet vs hand-rolled pool

2026-07-17 sweep facts (installed CLI **1.0.72-0**; `experimental: true` set, no
`subagents` block in settings.json as of today): **`/fleet` is GA** — the orchestrator
decomposes a prompt/plan into dependency-ordered work items, dispatches independent items
as parallel background subagents in waves, polls, verifies, and synthesizes; custom agents
serve as workers via `@AGENT-NAME`; non-interactive form `copilot -p "/fleet <task>"
--no-ask-user`. **Subagent concurrency + nesting depth are configurable in `/settings`
since 1.0.66** (usage-based-billing account tier — verify); default depth 4 (1.0.71).
Docs warn fleet subagents **share the filesystem** and recommend file partitioning — which
is exactly what IMP-0033 worktrees already solve.

- **Option 1 — fleet-native (recommended):** one headless CLI session per wave runs
  `/fleet` with the driver's pre-computed wave plan as explicit work items; each work item
  names `@DEV` as the worker and pins the track's IMP-0033 worktree as its working root.
  Polling/verification/synthesis: native. `fanout-dispatch.ps1` shrinks to a thin renderer
  of wave-plan → fleet prompt.
- **Option 2 — hand-rolled pool (original Proposal item 2):** full per-worker control of
  `--allow-tool`/cwd, but we own polling, timeout, failure attribution, and synthesis.
- **Rule:** wave computation stays in the driver regardless (deterministic, pytest).
  Choose Option 1 iff the implementation-time verification below passes; else Option 2.
- **Implementation-time verification (record results here):** (a) `/fleet` present and
  functional on this install; (b) `/settings` exposes subagent concurrency on this account
  tier — set ≤3 to mirror the WIP cap (depth 4 suffices; we need 2); (c) a stub 2-track
  fleet run in a scratch repo confirms work items respect worktree pinning and ≥2 workers
  overlap.
- Native `/worktree <task>` (creates worktree + branch, runs the sentence as first prompt)
  is noted as a fallback simplification only — `fanout-setup.ps1` remains canonical for
  naming + the integration branch.
- **Safety wiring:** the worker deny layer moves to IMP-0065 preToolUse hooks (mechanical,
  audited); interim = per-worker `--deny-tool` flags.

## Acceptance criteria

- [ ] Driver computes waves from `tracks:` + `depends_on:`; pytest covers diamond, serial,
      and no-deps track graphs
- [ ] The dispatch step (fleet-native or `fanout-dispatch.ps1` pool) launches ≤3
      concurrent headless workers, each confined to its worktree, deny layer enforced
      (IMP-0065 hooks, or `--deny-tool` interim); worker failure surfaces as a track
      bounce, not a run abort
- [ ] One real ≥2-independent-track run executes a wave concurrently; measured DEV segment
      < serial sum of its track durations (per-track timing from run-state)
- [ ] Merge gate attributes conflicts per track exactly as in the IMP-0033 rehearsal tests
- [ ] Negative: driver refuses to dispatch a track whose `depends_on` is unfinished
- [ ] Backend decision (fleet-native / pool / hybrid) recorded in the addendum with the
      account-tier verification evidence (concurrency setting visible, stub-run overlap
      observed)

## Validation plan

Deterministic: driver wave-computation pytest + a scripted 2-track scratch-repo rehearsal
(extend the IMP-0033 rehearsal suite with a dispatch step using a stub worker). Real-run:
the next multi-track `new-poc-setup` — which simultaneously discharges IMP-0033's owed
"one real 2-track fan-out" validation evidence. Irreducibly manual: none.

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0061.py`) — wave computation present +
  dispatch script exists + concurrency cap in config + QB fan-out section references wave
  dispatch, within QB line cap.
- **What we measure:** wave correctness (unit), concurrent worker count (rehearsal log),
  DEV-segment wall time vs per-track sum (real run, via IMP-0058 phase timing).
- **Pass criteria:** structural green; rehearsal shows ≥2 overlapping workers; real-run
  DEV segment ≤ 0.75 × serial sum for a 3-independent-track shape.
- **Negative cases:** unfinished-dependency dispatch refused; deny-listed command in a
  worker is blocked.
- **Known limits:** local machine contention (3 opus workers) may erode the speedup —
  record worker wall times so the cap can be tuned; API rate limits shared across workers.

## Notes

- Filed by the 2026-07-16 review ("dev is taking sooo long — focus on making dev faster").
  Companion: IMP-0062 (right-size rigor — cuts the work itself), IMP-0058 addendum
  (phase timing — makes the cut measurable), IMP-0053 (cloud backend for the same waves).
- Depends on IMP-0033 (shipped). Does NOT wait for IMP-0053; local workers are the v1 backend.
- Distinct from IMP-0043 (best-of-N = same task N times for quality; this = different
  tracks once each for speed).
- **2026-07-17:** dispatch-backend addendum added (native `/fleet` preferred, pool as
  fallback). IMP-0065 (hook deny layer + worker telemetry) is the safety prerequisite for
  the first real dispatched wave. Rehearsal may use a stub fleet run with no-op tracks.
