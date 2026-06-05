# Agent Recommendations: qb

**Generated:** 2026-04-24T18:10:50.618087+00:00
**Eval Run:** 20260424-180453
**Recommendations:** 1

## Summary

⚠️ 1 recommendation(s) generated for qb (86% compliance). 1 critical (P0), 0 important (P1). Review and approve/reject each recommendation, then re-run evals to verify.

## Recommendations

Review each recommendation below. Mark as `approved`, `rejected`, or add feedback.

### REC-001: Add/strengthen Checkpoint 2 (pre-implementation approval)

**Priority:** P0 | **Category:** checkpoint-compliance | **Status:** `pending`

**Rationale:**
The agent proceeded to implementation without user approval. This was observed in 2 test case(s): feature-add-caching, feature-add-search. Implementation without approval can waste time on wrong approaches and is the most common user complaint.

**Evidence (failing test cases):** feature-add-caching, feature-add-search

**Current behavior in agent definition:**
Agent definition already contains related rules, but they may need strengthening:
  - ...Do NOT invoke QA until the user responds.**     **Checkpoint 2 — Post-QA approval gate (HARD STOP):** After QA r...
  - ...owever, this rule does NOT override the mandatory approval gate in rule 5 — you MUST stop there.  5. **Two mandat...
  - ...ds.**     **Checkpoint 2 — Post-QA approval gate (HARD STOP):** After QA reports back and you have classified...

**Proposed change:**
Add a HARD STOP approval gate before any implementation action. The agent MUST call `askQuestions` with:
  - Summary of findings and proposed plan
  - Options: Approve / Modify scope / Cancel
  - `recommended: true` on the suggested option
  - `allowFreeformInput: true`
Add phrasing: 'You MUST NOT invoke any implementation agent until the user responds to this checkpoint. Presenting the plan in chat text is NOT sufficient — you must call askQuestions and wait.'

**Target section:** Checkpoint / Approval Gate rules

---

## Workflow

1. Review each recommendation above
2. Update the `status` field to `approved` or `rejected` (with optional notes)
3. Run: `python -m runner.cli apply-recommendations <this-file>` (coming soon)
4. Re-run evals: `python -m runner.cli run-behavioral` to verify changes
