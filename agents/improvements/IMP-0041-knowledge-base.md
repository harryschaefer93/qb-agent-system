---
id: IMP-0041
title: Knowledge base + retro auto-capture — durable facts alongside the IMP loop
status: implemented
source: review-2026-07-13
affects: [retro, scoper, QB]
risk: low
created: 2026-07-13
updated: 2026-07-13
commit: 3195476
eval_type: manual
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

The IMP loop improves *prompts*; there is nowhere for *facts* to accumulate — customer tenant
quirks, FDPO edge cases, SKU gotchas, regional model availability, "the customer's SME is only
available Tuesdays." Each engagement re-learns them. Gold standards (Devin Knowledge, Cursor
BugBot learned rules, Cline memory bank) all pair a process-improvement loop with a fact store.
(2026-06-11 harness research, candidate #1 — the biggest learning-loop gap.)

## Proposal

1. **Substrate:** `agents/knowledge/` — `global/` + `<customer>/` directories; one fact per
   note; frontmatter `scope`, `triggers`, `confirmed`, `source` (see `knowledge/README.md`).
   Seeded with `global/fdpo-auth-defaults.md`.
2. **Readers:** scoper Phase 2 step 0 and QB pre-flight check `knowledge/<customer>/` +
   `global/`, reading matching notes **by path** (IMP-0006 discipline).
3. **Writer:** retro gains a knowledge-suggestion pass (retro.agent.md Phase 4c; retro.md report
   section): sessions surfacing a durable fact yield a *drafted* note presented for approval —
   **never silently written**. Distinction rule: facts change what the next engagement does →
   knowledge; changes to how an agent works → IMP.

## Acceptance criteria

- [ ] `agents/knowledge/README.md` conventions + ≥1 seed note exist
- [ ] scoper and QB prompts reference the knowledge check
- [ ] retro (both variants) carries the approval-gated suggestion pass
- [ ] A real retro produces ≥1 approved knowledge note from a real session
- [ ] A later scoping session demonstrably uses a note (cited in BRIEF research summary)

## Validation plan

Inspection for the substrate; the last two acceptance boxes accumulate from real retro +
scoping sessions.

## Eval Plan

- **Type:** manual (substrate + prompt wiring; the payoff is cross-session)
- **What we measure:** end-to-end fact lifecycle: session → retro suggestion → approval → note →
  next session consumption
- **Known limits:** value grows with note count; empty at birth by design.

## Notes

- Source: 2026-06-11 harness research candidate #1, scheduled by the 2026-07-13 supercharge
  review (Wave 1). Pairs with IMP-0030 (run records are raw material for suggestions).
- Notes are data, not instructions — a note quoting external content stays subject to scoper's
  Untrusted Content Protocol (IMP-0035).
