---
id: IMP-0038
title: Port the IMP improvement workflow from VS Code to GitHub Copilot CLI
status: implemented
source: ad-hoc
affects: [meta, retro]
class: fleet
risk: low
created: 2026-06-11
updated: 2026-06-11
commit: _pending_
eval_type: manual
skip_validation: true
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

The IMP meta-workflow (triage → create-eval → implement → validate, plus the status
dashboard) lives entirely in VS Code slash-command prompts under `prompts/`
(`agent-status`, `imp`, `implement-improvement`, `create-imp-eval`, `validate-imp`).
Those prompts depend on VS Code-only seams the Copilot CLI cannot use:

- `vscode/memory` reads `/memories/repo/agent-improvements.md` — invisible to the CLI.
- `vscode/askQuestions` for hard-stop gates.
- A stale shell path: every prompt runs `cd ~/repos/evals`, but the eval harness now
  lives at `~/.copilot/evals/` (the old path no longer exists).

Additionally, the CLI `retro` agent (`agents/retro.md`) lacks the "IMP Evidence Mode"
that exists in the VS Code `retro.agent.md`, so real-session evidence gathering can't be
driven from the CLI either.

The goal is to run the whole IMP meta-workflow from the Copilot CLI. The QB POC-delivery
system itself stays in VS Code untouched — IMP work edits `.agent.md` files but never
runs them. The Python eval harness, telemetry mining, and Foundry surrogate pipeline are
environment-neutral and are NOT modified.

## Proposal

1. **Relocate the execution-order memory into the repo.** Create
   `agents/improvements/EXECUTION-ORDER.md` as the canonical recommended-order doc that
   the CLI can read directly (replacing the `vscode/memory` lookup of
   `/memories/repo/agent-improvements.md`).
2. **Create the CLI agent `agents/imp.md`** by merging the five `prompts/` files into one
   moded CLI agent (status / orchestrate / implement / create-eval / validate). Port every
   gate, baseline/post-eval step, verdict-flip rule, CHANGELOG/commit format, and the
   "do NOT auto-push" rule verbatim. Apply only the tool mapping:
   `vscode/askQuestions` → ask in plain conversation and STOP; `vscode/memory` →
   read `EXECUTION-ORDER.md`; `execute/runInTerminal` → CLI shell; normalize all eval-harness
   shell commands from `~/repos/evals` to `~/.copilot/evals/`.
3. **Port IMP Evidence Mode** from `retro.agent.md` into `retro.md` with the same tool
   mapping, preserving the privacy guardrails and timing gate verbatim.
4. **Update docs** — `agents/README.md` (add `imp` to the CLI agents table; note retro
   evidence mode in both environments), `prompts/README.md` (banner: CLI `agents/imp.md`
   is now canonical; VS Code prompts are a frozen fallback, do not delete), and
   `agents/improvements/README.md` (mention CLI equivalents for the prompt invocations).

## Acceptance criteria

- [x] `agents/improvements/EXECUTION-ORDER.md` exists and is referenced by `agents/imp.md`
      instead of the `vscode/memory` path.
- [x] `agents/imp.md` exists with five modes covering all five source prompts; no
      `vscode/*` tool references remain; every eval-harness command uses `~/.copilot/evals/`.
- [x] All hard-stop gates, verdict-flip rules, CHANGELOG/commit formats, and the
      "do NOT auto-push" rule are preserved from the source prompts.
- [x] `agents/retro.md` contains an "IMP Evidence Mode" section ported from
      `retro.agent.md`, with privacy guardrails and the timing gate intact.
- [x] `agents/README.md`, `prompts/README.md`, and `agents/improvements/README.md` are
      updated per the proposal.
- [x] `pwsh agents/health-check.ps1` passes.
- [x] `python -m runner.cli run-all-imps` still passes (harness untouched).

## Validation plan

All acceptance criteria are file-inspectable, so this IMP is `skip_validation: true`.
After implementation: confirm health-check and `run-all-imps` are green, and dry-run the
new `imp` agent's status mode to confirm it reads `EXECUTION-ORDER.md` and renders the
dashboard without calling any `vscode/*` tool.

## Eval Plan

- **Type:** manual (workflow/lifecycle change with no runtime tool-call seam; the change
  is a set of prompt/doc ports verifiable by file inspection).
- **What we measure:** presence and fidelity of the ported content; absence of `vscode/*`
  references and `~/repos/evals` paths; green health-check and `run-all-imps`.
- **Pass criteria:** all acceptance criteria checkboxes ticked by inspection.
- **Known limits:** faithful-port fidelity is checked by inspection, not by a live IMP
  run through the CLI; first real CLI IMP run will confirm end-to-end behavior.

## Notes

- Tool mapping is mechanical; the substance of each gate is preserved verbatim.
- `~/repos/evals` confirmed missing at port time — the canonical harness path is
  `~/.copilot/evals/`.
