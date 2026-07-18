---
id: IMP-0051
title: Ask discipline — clarification ledger, CP2 delivery contract, harness-friction runbook
status: implemented
source: user-2026-07-15
affects: [QB, meta]
risk: medium
created: 2026-07-15
updated: 2026-07-15
commit: 5b00071
eval_type: structural
skip_validation: false
eval_id: imp_0051
eval_seed: 42
baseline_run: null
post_run: baselines/IMP-0051/20260715-130225-7fc11c3-post.json
manual_evidence: []
---

## Problem

User (2026-07-15): "I am a bit frustrated by how many confirmations QB keeps coming back
with over and over after I make it pretty clear what I want to accomplish. It needs more
goal-seeking iteration after I've clarified the task."

Transcript forensics on the named example run (PilotApp-webpublic-20260714, via the new
IMP-0052 source) localized the friction to three distinct layers:

1. **Harness approvals, not QB asks** — QB made only 2 formal `askQuestions` calls across
   an 11-dispatch overnight run, but the session had **486 tool executions**, each subject
   to VS Code's approval buttons and the `chat.agent.maxRequests` "Continue to iterate?"
   cap. No prompt edit can fix this layer; it is user configuration.
2. **Wrong-guess delivery defaults** — QB delivered on a new feature branch; the user had
   to correct it ("this should be on main not a separate branch"). Every wrong guess at
   wrap-up is one more round trip that *feels* like another confirmation.
3. **No durable memory of clarifications** — decisions given mid-run (or before a session
   died) had no recorded home, so nothing structurally prevented re-asking them, and a
   resumed session started blind.

## Proposal

1. **Clarification ledger (driver + schema):** `pipeline clarify --run-id <id> -q "..."
   -a "..." [--set-autonomy trusted]` appends to a new optional `clarifications[]` in
   run-state; `pipeline resume` returns it. QB rule: before ANY non-hard-ask
   `askQuestions`, check BRIEF + goal contract + ledger — derivable answers are used and
   stated as assumptions, not re-asked. Resume honors the ledger explicitly.
2. **CP2 delivery contract (QB):** the consolidated-CP2 preamble must pin the end-of-run
   parameters QB would otherwise guess later — target branch (default: the user's current
   branch, never a new feature branch), merge/push intent, deploy-or-code-only — so the
   final wrap-up contains zero new decisions except hard asks.
3. **Delegation-fatigue escalation (QB):** "stop asking / you decide / just make it work"
   is recorded via `--set-autonomy trusted` and the run continues at trusted. Hard asks
   are level-independent and unaffected.
3b. **Hard-ask batching (added 2026-07-15 from 0713 transcript evidence):** the
   PilotApp-20260713 session served deployment hard-asks serially across four turns
   ("answer these and say go" → more questions → "OK? say provision" → "approved and
   confirmed both"). New rule: every hard-ask decision pending at one seam goes into ONE
   `askQuestions` call — one question per decision. Hard asks stay blocking; they stop
   being a ladder.
4. **Harness-friction runbook (`docs/vscode-agent-friction.md`):** one-time user config —
   `chat.agent.maxRequests` raise, `chat.tools.terminal.autoApprove` allowlist for the
   recurring safe commands with an explicit deny-list (git push, az deployment, rm -rf,
   npm publish stay manual), per-workspace tool allows for runSubagent. FDPO and hard
   asks explicitly out of scope of any auto-approval.

## Acceptance criteria

- [x] Driver `record_clarification` + CLI `clarify` + schema `clarifications[]` + resume
      returns ledger (3 new pytest cases; 21 driver tests green)
- [x] QB: ledger rule, delivery-contract line at CP2, fatigue escalation, resume honors
      ledger, anti-pattern list extended (within IMP-0023 line cap: 434/440)
- [x] Runbook exists with maxRequests + autoApprove guidance and intact deny-list
- [ ] Real run: zero re-asked decisions; wrap-up contains no new non-hard-ask decisions
- [ ] User-felt confirmation count drops after runbook settings applied (user judgment)

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0051.py`, 7 checks) — CI-gates the prompt
  rules, driver command, schema, and runbook.
- **Behavioral evidence:** re-ask rate is observable from run records + transcripts
  (askQuestions whose subject matches an existing `clarifications[]` entry) — candidate
  for a `_imp_0051` telemetry scorer once ledger-bearing runs exist.
- **Known limits:** the runbook layer requires the user to apply settings — the harness
  cannot (and must not) change VS Code settings itself.

## Notes

- Complements IMP-0028 (fewer gates) and IMP-0036 (persistence after approval): 0028 cut
  checkpoint *count*, 0036 cut premature yields, 0051 cuts *repeat* asks and wrong-guess
  round trips — the remaining ask-friction after both.
- The branch-guess correction from PilotApp-webpublic-20260714 is the canonical delivery-
  contract failure case; the CP2 Delivery line pins exactly the parameters it got wrong.
- Setting keys in the runbook drift with VS Code releases; the doc says to verify via the
  Settings UI search ("auto approve") if a key is unrecognized.
