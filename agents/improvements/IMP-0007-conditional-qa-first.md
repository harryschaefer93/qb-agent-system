---
id: IMP-0007
title: Make QA-first conditional for explicit trivial config changes
status: rejected
source: review-context-window-2026-04
affects: [QB]
risk: high
created: 2026-04-27
updated: 2026-04-27
commit: null
---

## Problem

"Always invoke QA first, no exceptions" burns 5–20K tokens before any decision, even on trivially specified changes ("change timeout from 30 to 60 in `config.json`").

## Proposal

Add a narrow exception: when the user request is fully specified (file:line + exact value change), skip QA-pre and go straight to the responsible agent + quality gates + QA fast-check.

## Verdict — rejected

The "always QA first" rule exists in QB precisely because skipping QA was a previously documented failure mode. The loud "NO EXCEPTIONS" framing is intentional behavioral conditioning. Loosening it risks regression.

The bigger context cost is actually **Checkpoint 1's `askQuestions` round-trip**, not the QA invocation itself — and that's a quality lever worth keeping.

If we revisit later, only do so after IMP-0001 (bounded returns) and IMP-0006 (BRIEF by reference) have shipped — they may shrink QA-pre cost enough that this rule change isn't needed.

## Notes

Keep this file as a record of the considered-and-rejected decision so future-you (or a future retro) doesn't re-litigate.
