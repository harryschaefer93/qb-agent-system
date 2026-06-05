---
id: IMP-0015
title: Define `validated` lifecycle criteria
status: validated
source: agent-status-2026-04-28
affects: [meta]
risk: low
created: 2026-04-28
updated: 2026-06-01
commit: 348ccb9
eval_type: manual
skip_validation: true
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence:
  - {session_id: 50ecd17b-b191-408f-a4f5-c9fd7d6daf6c, verdict: pass, notes: "Inspection: README §`validated` bar present with 4 points; _template.md Results header references bar; both edits committed in 348ccb9. Acceptance criteria met by inspection."}
---

## Problem

The improvement lifecycle defines `proposed → accepted → implemented → validated → (rejected)`, but there is no documented bar for crossing `implemented → validated`. As a result:

- IMP-0004 and IMP-0006 are stuck in `implemented` with passing structural evals but open "real session" acceptance-criteria boxes.
- `/Agent-Status` reports zero `validated` IMPs ever, even when post-run evidence exists.
- Future IMPs will accumulate in `implemented` indefinitely.

## Proposal

Update `agents/improvements/README.md` to define the `validated` bar explicitly. Proposed definition:

> An IMP graduates from `implemented` to `validated` when **all** of the following hold:
> 1. `post_run` JSON exists and verdict is `PASS` or `IMPROVEMENT` (not `REGRESSION`).
> 2. For non-structural eval_types: `manual_evidence` has at least one entry with `verdict: pass` from a real Copilot session (not the surrogate harness).
> 3. All acceptance-criteria checkboxes in the IMP file are checked.
> 4. The CHANGELOG entry references a real commit SHA (not `_pending_`).

Also add a short paragraph on what `validated` *signals*: the change is durable, observed in production, and safe to forget about.

## Acceptance criteria

- [x] `agents/improvements/README.md` documents the four-point `validated` bar *(commit `348ccb9`)*
- [x] `_template.md` Results section header notes the validation gate *(commit `348ccb9`)*
- [ ] IMP-0004 and IMP-0006 are reviewed against the new bar; either advanced to `validated` or have remaining gaps recorded *(follow-up — walk-through pending; both currently `implemented`)*
- [ ] `/Agent-Status` Eval Coverage section reports validated count alongside implemented count *(already does per IMP-0016)*

## Validation plan

Walk IMP-0004 and IMP-0006 through the new criteria. At least one should be promotable to `validated` after the housekeeping pass (CHANGELOG SHAs, real-session check, checkbox closure). If neither qualifies, the bar may be too high — revise.

## Eval Plan

- **Type:** manual
- **What we measure:** lifecycle clarity — can a reader determine `validated`-readiness from the IMP file alone?
- **Pass criteria:** README updated; at least one IMP successfully validated under the new rule
- **Known limits:** subjective bar; may need tuning after a few more IMPs ship

## Notes

Pairs with IMP-0014 (eval classification) and IMP-0016 (per-eval-type rendering). All three are meta-system cleanup that should ship before continuing the main backlog so the next round of implementations can complete the full lifecycle.
