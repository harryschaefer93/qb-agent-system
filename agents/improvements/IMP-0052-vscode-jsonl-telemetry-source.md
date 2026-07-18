---
id: IMP-0052
title: VS Code JSONL transcript source for telemetry (Copilot Chat >=0.52)
status: validated
source: session-2026-07-15
affects: [meta]
risk: low
created: 2026-07-15
updated: 2026-07-15
commit: adc8026
eval_type: manual
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence:
  - {session_id: b4171155, verdict: pass, captured: 2026-07-15, source: real-session, notes: "First previously-invisible VS Code session made scoreable: PilotApp-webpublic-20260714 orchestrator + 12 subagent sub-sessions parsed; produced the IMP-0036 real PASS and IMP-0026 pass evidence | artifact: evidence/IMP-0036/20260715T121948-b4171155.json"}
---

## Problem

VS Code Copilot Chat stopped writing `session-store.db` (last write 2026-06-02) —
Copilot Chat >=0.52 emits per-workspace JSONL transcripts at
`%APPDATA%/Code/User/workspaceStorage/<hash>/GitHub.copilot-chat/transcripts/<session>.jsonl`
instead. Telemetry (`evals/runner/telemetry.py`) only read the two sqlite stores, so
**every VS Code QB session since June was invisible** to scan/backfill/score — the user's
primary surface. The PilotApp-webpublic-20260714 run (a real IMP-0036 pass) could not be
scored; nightly evidence backfill was starving.

## Proposal

1. Add the workspaceStorage JSONL glob as a third session source, parsed into the same
   `{id, created_at, summary, turns[]}` shape the sqlite stores yield.
2. **Subagent splitting:** VS Code records `runSubagent` executions inline (prompt as
   `user.message`, output as `assistant.message`, bracketed by
   `tool.execution_start/complete`). Split those segments into separate `<id>-subN`
   sessions so orchestrator sessions keep the CLI shape and QB scorers stay
   semantically correct.
3. Render `toolRequests` as `[tool:<name>]` lines inside `assistant_response` so existing
   regex fingerprints (askQuestions, runSubagent) fire with zero scorer changes — the
   JSONL source is actually *richer* than sqlite (tool calls were never stored there).
4. **Subagent session exclusion in backfill:** dispatch sessions (summary starting
   `[subagent:` or `You are the <AGENT> agent`) anchor to the same run id as the
   orchestrator and were producing false PREMATURE-YIELD fails against QB-behavior IMPs
   in *both* stores. `_is_subagent_session` now excludes them from scoring.

## Acceptance criteria

- [x] `scan` finds VS Code >=0.52 sessions (60 candidates vs 14 before, orchestrator + subs)
- [x] `backfill --auto` scores a previously-invisible session end-to-end (b4171155 →
      IMP-0036 real PASS on record PilotApp-webpublic-20260714)
- [x] Subagent dispatch sessions excluded from QB-behavior scoring (70 excluded; the 11
      false IMP-0036 fails from sub-sessions are gone)
- [x] sqlite paths untouched — pre-July history still scores identically

## Eval Plan

- **Type:** manual (telemetry infrastructure; deterministic parse verified against a real
  transcript). Nightly evidence backfill exercises it unattended from here on.
- **Known limits:** VS Code >=0.52 transcripts don't record tool-approval prompts, so
  Continue-button friction is still not directly measurable. If Copilot changes the JSONL
  event schema again, `_parse_vscode_jsonl` is the single point of update.

## Notes

- Found while investigating why record-aware scorers couldn't see the
  PilotApp-webpublic-20260714 session. The same investigation quantified QB ask behavior
  for IMP-0051 (2 formal asks across an 11-dispatch overnight run).
- The initial user prompt is not recorded as a `user.message` event in these transcripts
  (first event after `session.start` is QB's classification message); summaries fall back
  to the first recorded user message.
- **Graduated to `validated` 2026-07-15** (review session): 4-point bar checked — (1)
  `eval_type: manual` satisfied by inspection-only acceptance, all 4 criteria verified
  against the real PilotApp-webpublic-20260714 transcript; (2) real-session
  `manual_evidence` pass (b4171155) on file; (3) all acceptance boxes ticked; (4)
  CHANGELOG references real commit adc8026. Nightly evidence backfill has since
  exercised the source unattended (nightly-2026-07-15 scored 4 candidate sessions
  through it).
