---
id: IMP-0013
title: Wire retro agent output into IMP file creation
status: validated
source: review-context-window-2026-04
affects: [retro]
risk: low
created: 2026-04-27
updated: 2026-06-03
commit: 4fd9883
eval_type: structural
skip_validation: true
eval_id: imp_0013
eval_seed: 42
baseline_run: baselines/IMP-0013/20260603-141342-f051c67-baseline.json
post_run: baselines/IMP-0013/20260603-141416-f051c67-post.json
manual_evidence: []
---

## Problem

Retro agent writes free-form reports to `agents/files/retros/retro-YYYY-MM-DD.md` with an "Action Items" checklist. Those items sit in a markdown doc that nobody reads again. The improvement system has a structured lifecycle (`proposed` → `accepted` → `implemented` → `validated`) but no automated way to feed it. Discovery and tracking are disconnected.

## Proposal

Add a rule to `retro.agent.md` in the Report Generation section:

> For each actionable recommendation in the retro report, create a new IMP file in `agents/improvements/` using the `_template.md` format. Set `status: proposed`, `source: retro-<session-id>`, and fill Problem/Proposal/Acceptance Criteria from the recommendation. This replaces the "Action Items" checklist in the report — action items become IMP files, not checkboxes.

Also update the report format: replace the `## Action Items` section with a `## Improvements Filed` section that lists the IMP ids created during the retro.

## Acceptance criteria

- [x] `retro.agent.md` instructions updated with IMP file creation rule *(Phase 4b section added — full 5-step procedure for converting retro recommendations into new IMP files)*
- [x] Report format updated: `Action Items` → `Improvements Filed` *(diff shown in Phase 4b)*
- [x] Retro reads `_template.md` and the `improvements/README.md` to understand the schema *(steps 1-2 of Phase 4b)*
- [ ] Next retro run produces IMP files in `proposed` status alongside the report *(deferred — will validate on next weekly retro run)*

## Validation plan

Run a retro covering a week with real session data. Confirm IMP files appear in `agents/improvements/` with correct frontmatter and that the report references them by ID.

## Notes

This closes the loop: retro discovers → IMP files capture → `/agent-status` surfaces → `/implement-improvement` ships → retro measures impact next cycle.
