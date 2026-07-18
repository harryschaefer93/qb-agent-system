---
id: IMP-0011
title: Auto-compact at 60% of context window
status: rejected
source: review-context-window-2026-04
affects: [QB]
risk: medium
created: 2026-04-27
updated: 2026-04-27
commit: null
---

## Problem

When context approaches the model's limit, behavior degrades silently.

## Proposal

When estimated context exceeds 60% of model window, QB produces a Handoff Brief and refuses further subagent invocations until a new session starts.

## Verdict — rejected (subsumed by IMP-0005)

Programmatic token counting inside an agent is unreliable — the original review's own section 6 flagged this. The reliable substitute is turn/phase-count heuristics, which is exactly what IMP-0005 (Session Handoff Protocol) does.

Don't add a separate mechanism that overlaps. One trigger, one protocol, easier to reason about.

## Notes

If the runtime ever exposes accurate residual-token info to the agent, revisit and possibly fold into IMP-0005's trigger conditions.
