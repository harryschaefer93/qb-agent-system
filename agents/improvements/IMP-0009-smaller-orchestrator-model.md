---
id: IMP-0009
title: Move QB orchestration to a smaller model
status: rejected
source: review-context-window-2026-04
affects: [QB]
risk: high
created: 2026-04-27
updated: 2026-04-27
commit: null
---

## Problem

Opus is overkill for routing decisions ("QA said X, route to Dev"). Other systems (Cursor, Copilot Cloud Agent) use smaller models for orchestration.

## Proposal

Switch QB from `claude-opus-4.6-1m` to Sonnet/Haiku; keep subagents on Opus.

## Verdict — rejected

QB is on `claude-opus-4.6-1m` specifically for the **1M context window**, not the reasoning ceiling. Downgrading to Sonnet/Haiku surrenders the very window headroom this whole batch of improvements is trying to preserve.

QB's logic (scope classification, gate-bounce tracking, iteration accounting, fan-out coordination, approval-gate state) is also more complex than the orchestrators those other systems use — they got away with smaller models because their orchestration is dumber.

Not worth the risk.

## Notes

Reconsider only if Anthropic ships a Sonnet-class model with comparable window size *and* you've validated reasoning quality on real QB sessions.
