---
id: IMP-0065
title: CLI hook layer — mechanical deny guardrails + session telemetry for headless workers
status: proposed
source: review-2026-07-17
affects: [DEV, REPO, meta]
risk: low
created: 2026-07-17
updated: 2026-07-17
commit: null
eval_type: structural
skip_validation: false
eval_id: imp_0065
eval_seed: 42
baseline_run: null
post_run: null
validation_evidence: []
manual_evidence: []
---

## Problem

IMP-0061 puts ≤3 headless `copilot` CLI workers inside repos with broad tool allowances.
Today the guardrails for that layer are prompt prose ("REPO owns git — do not push",
DEV.agent.md) plus per-invocation `--allow-tool`/`--deny-tool` flag lists — nothing
mechanical, nothing audited. And a headless session is invisible to run records unless the
driver wraps it: IMP-0063's prevention half covers the driver path only. Evidence for the
risk case: `PilotApp-fanout-20260715` — ~40 report files over 25+ hours, track A iterating
A2→A8 against **live auth**, with no run record anywhere; a headless worker doing that
unsupervised is exactly what must be mechanically fenced and mechanically visible.

Separately, the IMP-0058 addendum fixes phase timing driver-side for VS Code runs
(`started` stamped at dispatch), but CLI worker sessions have no equivalent timing or
run-id linkage surface.

2026-07-17 sweep facts (installed CLI 1.0.72-0): the hooks system is GA — JSON hook
configs; events `sessionStart` / `sessionEnd` / `preToolUse` / `postToolUse` /
`userPromptSubmitted` / `agentStop` / `subagentStop` / `errorOccurred`; **preToolUse
rejecting with exit code 2 denies the tool call** (1.0.71); postToolUse can inject
`additionalContext` as system messages (1.0.49) with matchers honored (1.0.64). The
enforcement layer the prose has been simulating now exists as configuration.

## Proposal

1. **preToolUse deny hook** (`scripts/hooks/pretool-guard.ps1` + hook config JSON):
   exit-code-2 denies for headless workers on the hard-gated set — `git push` and force
   variants, `az deployment|group create|resource delete`, `rm -rf` / `Remove-Item
   -Recurse -Force`, `git reset --hard`, secret-file reads (`*.enc`, `.env`, key/token
   paths). Deny patterns live in **one JSON canon** (`scripts/hooks/deny-canon.json`)
   shared with the `docs/vscode-agent-friction.md` list — same patterns, now enforced
   rather than advisory. Every deny appends an audit line to `logs/hook-denies.log`.
   A denied call must surface to the worker as a refusal it reports (track-bounce
   semantics for IMP-0061), not a session abort.
2. **sessionStart/sessionEnd hooks** (`scripts/hooks/session-telemetry.ps1`): if the
   dispatch environment carries a run id (IMP-0061's dispatcher sets it), append
   session→run-id linkage plus real `started`/`finished` stamps to the home-store run
   record — the IMP-0063 prevention half for the CLI path, and the IMP-0058-addendum
   timing surface for workers. A worker session with **no** run id gets logged for the
   nightly untracked-work scan (detect, don't block).
3. **subagentStop** stamps per-worker completion into the track's phase entry.
4. **v2, explicitly out of scope for v1:** postToolUse `additionalContext` injection of
   artifact digests at handoff seams (mechanizes part of IMP-0026's protocol).
5. **Scope: Copilot CLI only.** Config-not-prompt; zero agent-prompt line changes except a
   one-line REPO note that the deny canon exists.

## Acceptance criteria

- [ ] Hook config + `pretool-guard.ps1` + `session-telemetry.ps1` exist; deny canon JSON
      is the single source shared with the friction doc
- [ ] Scripted headless session: a seeded `git push` is denied (exit-2 observed, audit
      line written) and the worker continues, reporting the refusal
- [ ] Same session: an allow-listed build/test command passes with negligible added latency
- [ ] A dispatched worker carrying a run id lands real `started`/`finished` stamps in
      run-state; `runner.telemetry kpi` renders them per track
- [ ] Hook-config location for user-level scope verified (docs show repo-level
      `.github/hooks/*.json`; confirm whether `~/.copilot` supports a global hooks dir —
      if not, `fanout-setup.ps1` installs the config into each worktree) and VS Code
      Copilot Chat applicability verified (expected: CLI-only; the VS Code path stays
      driver-side per the IMP-0058 addendum) — result recorded in Notes
- [ ] Negative: an alternate-spelling bypass attempt (e.g. `git -C <path> push`) is caught
      by the canon

## Validation plan

Fully deterministic — a scripted headless `copilot -p` session in a scratch repo exercises
the deny path, the allow path, and the telemetry path; file inspection covers the wiring.
No real-session requirement; irreducibly manual: none. This IMP adds zero validation debt
by construction.

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0065.py`) — hook config exists and parses,
  canon matches the friction-doc set, both scripts parse, REPO one-liner present.
- **What we measure:** deny correctness (seeded rehearsal), audit-line emission, run-state
  timing stamps landing from a worker session.
- **Pass criteria:** structural green; rehearsal shows deny + continue + audit for the
  seeded push, pass-through for the allow-listed command, stamps present in run-state.
- **Negative cases:** alternate-spelling push caught; a deny that would abort the session
  (must bounce, not abort).
- **Known limits:** regex denies are best-effort against novel spellings — defense in
  depth is that workers operate in IMP-0033 worktrees and REPO owns the only push from the
  main tree, so a missed deny lands on an unpushed track branch. Hook events/exit-code
  contract is version-gated (≥1.0.71) — pin the CLI version in the config header.

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

- Filed by the 2026-07-17 tech sweep. **Wave-7 enabler, not meta**: this is the seatbelt
  for IMP-0061's headless workers (safety prerequisite for the first real dispatched
  wave), the CLI-side complement to IMP-0063's prevention half, and the worker-side
  complement to the IMP-0058 addendum's phase timing.
- Companion sweep facts referenced by siblings: `/review` + `/security-review` GA (1.0.62)
  → IMP-0066; `/fleet` + `/settings` subagent concurrency → IMP-0061 addendum.
