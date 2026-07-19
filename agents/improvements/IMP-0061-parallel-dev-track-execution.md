---
id: IMP-0061
title: Parallel DEV track execution — dependency waves over worktrees, not serial runSubagent
status: implemented
source: review-2026-07-16
affects: [QB, DEV, REPO, meta]
risk: medium
created: 2026-07-16
updated: 2026-07-19
commit: 312b131
eval_type: structural
skip_validation: false
eval_id: imp_0061
eval_seed: 42
baseline_run: null
post_run: baselines/IMP-0061/20260719-173835-312b131-post.json
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
- **VERIFICATION RESULTS (2026-07-19, CLI 1.0.72-1, from the installed bundle + live CLI):**
  - (a) `/fleet` present — GA in the bundle (`"/fleet"` command string in app.js;
    `session.fleet.start` RPC in schemas/api.schema.json; changelog "Autopilot mode and
    /fleet command now available to all users"). **BUT** the fleet API contract takes only
    `{sessionId, prompt?}` — no work-item list, no per-item working root, no per-worker
    env or tool flags. Worktree pinning would be prose-only and unenforceable; the
    per-worker `--deny-tool` layer (mandatory per IMP-0065) cannot be expressed at all.
  - (b) **FAIL** — the full settings schema was enumerated from the installed bundle
    (app.js zod config schema + the `writeKey` set): **no subagent-concurrency or
    nesting-depth key exists on 1.0.72-1**, and no CLI flag either
    (`--max-autopilot-continues` counts continuation messages, not workers). The 07-17
    sweep's "configurable since 1.0.66" claim did not materialize as a config surface on
    this build.
  - (c) Re-scoped to the chosen backend: the deterministic pool rehearsal
    (`evals/pipeline/tests/test_dispatch_rehearsal.py`, stub workers, no model) proves
    ≥2 overlapping workers (marker timestamps: every worker started before the first
    finished), per-process cwd pinning to each worktree, deny flags + `--no-ask-user` on
    every worker argv, worktree hook install, and `track_parallel_savings_minutes > 0`.
  - **DECISION: Option 2 — `fanout-dispatch.ps1` pool** (per this addendum's own rule:
    Option 1 iff (a)(b)(c) all pass; (b) failed and (a)'s API gap is disqualifying).
    Revisit fleet-native when a CLI update exposes work-item pinning + a concurrency
    setting. Bonus finding: `--max-ai-credits <n>` exists on 1.0.72-1 — wired into the
    dispatcher config as an optional per-worker spend cap.
- Native `/worktree <task>` (creates worktree + branch, runs the sentence as first prompt)
  is noted as a fallback simplification only — `fanout-setup.ps1` remains canonical for
  naming + the integration branch.
- **Safety wiring:** the worker deny layer moves to IMP-0065 preToolUse hooks (mechanical,
  audited); interim = per-worker `--deny-tool` flags.

## Acceptance criteria

- [x] Driver computes waves from `tracks:` + `depends_on:`; pytest covers diamond, serial,
      and no-deps track graphs (`test_waves.py`, 19 cases: diamond/serial/explicit-no-deps/
      conservative-default + cycle/unknown-dep/duplicate refusals + ledger/status wiring +
      ARCH YAML-block parse)
- [x] The dispatch step (`fanout-dispatch.ps1` pool) launches ≤3 concurrent headless
      workers, each confined to its worktree, deny layer enforced (`--deny-tool` interim
      from the canon's `cli_deny_tools` — mandatory while preToolUse is dead in `-p` mode —
      plus the worktree hook config for defense in depth); worker failure surfaces as a
      track bounce, not a run abort (`test_dispatch_rehearsal.py::test_worker_failure_is_a_track_bounce_not_a_run_abort`)
- [ ] One real ≥2-independent-track run executes a wave concurrently; measured DEV segment
      < serial sum of its track durations (per-track timing from run-state) — **owed: the
      next multi-track `new-poc-setup`; doubles as IMP-0033's owed 2-track validation**
- [x] Merge gate attributes conflicts per track exactly as in the IMP-0033 rehearsal tests
      (merge path untouched; `test_worktree_scripts.py` unchanged and green)
- [x] Negative: driver refuses to dispatch a track whose `depends_on` is unfinished
      (`track_dependency_unfinished`, wave-order gate — subsumes named deps and enforces
      the conservative serial default; covered in both suites)
- [x] Backend decision (pool) recorded in the addendum with the verification evidence
      (concurrency setting does NOT exist on 1.0.72-1; stub-run overlap observed via
      rehearsal markers)

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
- **2026-07-19 — IMPLEMENTED (pool backend).** Shipped: `compute_waves`/`set_tracks` +
  track routing in `dispatch`/`advance` + `pipeline tracks` verb + run-state `tracks`
  ledger (schema extension) + status/resume wave exposure; `scripts/fanout-dispatch.ps1`
  (+ config + stub worker) with the canon-sourced `--deny-tool` layer, per-worktree hook
  install, `QB_RUN_ID`/`QB_TRACK_PHASE` env, driver-gated launches, and per-track
  advance recording; telemetry `track_serial_sum/track_wall/track_parallel_savings`
  KPIs (kpi + nightly safe outputs); QB DEV Fan-Out rewired to wave dispatch (438/440
  lines); `fanout-setup.ps1` now installs worker hooks per worktree (closes the 0065
  install hand-off). Bug found + fixed in passing: ARCH's §8 tracks template had drifted
  from the IMP-0029 `tracks-block` schema (`owns:`/`depends_on_env:` vs the schema's
  `owned_paths`/`env_contract`) — every real ARCH block would have gate-bounced at
  `pipeline tracks`. Template now schema-conformant and documents `depends_on` +
  wave semantics; YAML-block parse covered in `test_waves.py`. CLI version re-checked this session: still 1.0.72-1, so the
  IMP-0065 preToolUse retest was not triggered and `--deny-tool` remains the mandatory
  enforcement layer. Known interim gaps (recorded in the canon's `cli_deny_tools.source`):
  prefix flags can't express `git -C <path> push` or argument-content secret reads —
  mitigated by worktree isolation, REPO owning the only push, and the hook layer arming
  on a fixed CLI. Deterministic evidence: 22 new pytest cases green (19 wave incl.
  YAML-block parse + 3 rehearsal); structural eval 9/9. Remaining acceptance box = the
  first real ≥2-track wave (discharges IMP-0033's owed validation too).
