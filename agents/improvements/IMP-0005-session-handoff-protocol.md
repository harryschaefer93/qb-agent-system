---
id: IMP-0005
title: Add Session Handoff Protocol to QB
status: validated
source: review-context-window-2026-04
affects: [QB]
risk: medium
created: 2026-04-27
updated: 2026-06-03
commit: 4fd9883
eval_type: structural
skip_validation: true
eval_id: imp_0005
eval_seed: 42
baseline_run: baselines/IMP-0005/20260603-141253-f051c67-baseline.json
post_run: baselines/IMP-0005/20260603-141318-f051c67-post.json
manual_evidence: []
---

## Problem

QB has no escape hatch when a pipeline runs long. Today it tries to push through context overload instead of cleanly checkpointing and restarting.

## Proposal

Add a "Session Handoff Protocol" section. Trigger conditions (any of):

- More than 3 subagent invocations in the current session
- Any iteration cycle hits the 2-cycle limit (escalation already required, this just structures it)
- QB notices it's repeating itself or losing track of decisions

When triggered, QB STOPS and produces a `## Handoff Brief`:

```
Current task: <one line>
Task type / scope: <...>
Decisions made: <bullets>
Files touched: <list>
Remaining steps: <ordered list>
Open blockers: <list or "none">
Next action for fresh session: <one paragraph>
```

Then instructs the user: "Open a new QB session and paste this Handoff Brief as the first message."

## Acceptance criteria

- [x] New "Session Handoff Protocol" section in QB *(Phase 1 commit — added under context-economy discipline rules)*
- [x] Trigger conditions are explicit and use turn/phase counts (not token estimates — see Notes) *(>3 subagent invocations OR 2-cycle iteration limit OR 5+ Checkpoint blocks OR self-observed confusion)*
- [x] Handoff Brief template included *(7-field template specified verbatim; eval verifies all required fields present)*
- [ ] Tested in a deliberately long pipeline *(deferred — gather via retro evidence mode on next long-running session)*

## Validation plan

Run a `full-delivery` and watch whether handoff fires at the right seam. If it never fires on real workloads, the trigger is too loose; if it fires every session, too tight.

## Notes

Risk is medium because this is user-visible behavior change — the user will be told to start a new session. Worth the friction; the alternative is silent degradation.

Deliberately uses turn/phase counts instead of token estimates. Programmatic token counting inside the agent is unreliable and the original review (section 6) flagged this too.

Subsumes IMP-0011 (auto-compact at 60% window) — same pattern, more robust trigger.
