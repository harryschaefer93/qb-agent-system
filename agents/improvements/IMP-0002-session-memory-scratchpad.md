---
id: IMP-0002
title: Externalize QB session state to memory scratchpad
status: validated
source: review-context-window-2026-04
affects: [QB]
risk: low
created: 2026-04-27
updated: 2026-06-03
commit: 4fd9883
eval_type: structural
skip_validation: true
eval_id: imp_0002
eval_seed: 42
baseline_run: baselines/IMP-0002/20260603-141132-f051c67-baseline.json
post_run: baselines/IMP-0002/20260603-141201-f051c67-post.json
manual_evidence: []
---

## Problem

QB re-pastes context (BRIEF excerpts, QA findings, approved scope) when invoking subagents and when restating plans after approval gates. This duplicates content into the working window.

## Proposal

Use the existing `vscode/memory` tool with `/memories/session/` (already part of the user-memory convention) as QB's scratchpad. After each phase, QB writes a ≤5-line summary entry: task type, classification, scope, QA findings (3 bullets max), approval decision, iteration counts. Subsequent steps reference the scratchpad entry by name instead of re-pasting.

Do **not** introduce a new `.qb/session.md` file in the workspace — keeps the customer's repo clean and reuses an existing primitive.

## Acceptance criteria

- [x] QB.agent.md documents the scratchpad convention (file naming, what to write per phase) *(commit f051c67 + Phase 1 follow-up — Session Scratchpad subsection added under Subagent Return Discipline rule)*
- [x] At least one workflow step references "read scratchpad" instead of re-pasting prior context *(subagents are instructed to read the scratchpad keys by name; structural eval check 3 verifies the pattern is present)*
- [ ] Scratchpad entries observed in `/memories/session/` after a real pipeline run *(deferred — gather via retro evidence mode on next real POC session)*

## Validation plan

Run a `new-poc-setup` end-to-end. Confirm scratchpad entries exist and that QB's prompts to later subagents are shorter than today.

## Notes

Adapted from the original recommendation which suggested a repo-local file. Session memory is the right primitive — it's already in your tool list and matches the user-memory guidance in your top-level copilot-instructions.md.
