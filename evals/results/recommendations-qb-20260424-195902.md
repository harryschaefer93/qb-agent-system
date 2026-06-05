# Agent Recommendations: qb

**Generated:** 2026-04-24T19:32:59.024674+00:00
**Eval Run:** 20260424-191312
**Recommendations:** 3

## Summary

⚠️ 3 recommendation(s) generated for qb (18% compliance). 2 critical (P0), 1 important (P1). Review and approve/reject each recommendation, then re-run evals to verify.

## Recommendations

Review each recommendation below. Mark as `approved`, `rejected`, or add feedback.

### REC-001: Add/strengthen Checkpoint 1 (pre-QA clarification)

**Priority:** P0 | **Category:** checkpoint-compliance | **Status:** `approved`

**Rationale:**
The agent invoked QA without first confirming scope with the user. This was observed in 18 test case(s): bugfix-api-500, bugfix-auth-broken, feature-add-caching, feature-new-endpoint, feature-add-auth, feature-add-search, architecture-db-choice, architecture-refactor-api, architecture-migrate-db, handoff-package-for-customer, handoff-demo-prep, delivery-full-pipeline, delivery-new-poc-setup, urgency-demo-tomorrow, compound-review-and-fix, compound-new-feature-plus-deploy, compound-refactor-and-migrate, compound-scope-creep-oh-also. Users lose control when the agent starts investigating before confirming what to investigate.

**Evidence (failing test cases):** bugfix-api-500, bugfix-auth-broken, feature-add-caching, feature-new-endpoint, feature-add-auth, feature-add-search, architecture-db-choice, architecture-refactor-api, architecture-migrate-db, handoff-package-for-customer, handoff-demo-prep, delivery-full-pipeline, delivery-new-poc-setup, urgency-demo-tomorrow, compound-review-and-fix, compound-new-feature-plus-deploy, compound-refactor-and-migrate, compound-scope-creep-oh-also

**Current behavior in agent definition:**
Agent definition already contains related rules, but they may need strengthening:
  - ...kpoints — you MUST stop and wait at both.**     **Checkpoint 1 — Pre-QA clarification:** For every task that is...
  - ...UST stop and wait at both.**     **Checkpoint 1 — Pre-QA clarification:** For every task that is not obvio...
  - ...w through tasks without asking the user first.**  Before EVERY action — before invoking QA, before reading files, before searching code, bef...

**Proposed change:**
Add or strengthen a mandatory pre-investigation checkpoint. Before invoking any diagnostic or analysis agent, the agent MUST call `askQuestions` to confirm:
  - What the user wants investigated
  - The scope of investigation (narrow vs. broad)
  - Any constraints or priorities
Add phrasing: 'Before invoking [analysis agent], call askQuestions with 1-3 options to confirm scope. Do NOT proceed until the user responds.'

**Target section:** Checkpoint / Approval Gate rules

---

### REC-003: Agent fails consistently for specific task categories

**Priority:** P0 | **Category:** category-specific | **Status:** `approved`

**Rationale:**
The agent has a significantly lower pass rate for certain task categories, suggesting the checkpoint rules have category-specific gaps or escape hatches.

**Evidence (failing test cases):** bugfix-api-500, bugfix-auth-broken, feature-add-caching, feature-new-endpoint, feature-add-auth, feature-add-search, architecture-db-choice, architecture-refactor-api, architecture-migrate-db, handoff-package-for-customer, handoff-demo-prep, delivery-full-pipeline, delivery-new-poc-setup, urgency-demo-tomorrow, compound-review-and-fix, compound-new-feature-plus-deploy, compound-refactor-and-migrate, compound-scope-creep-oh-also

**Current behavior in agent definition:**
See eval results for details.

**Proposed change:**
Review the agent's workflow section for the failing task categories. Ensure each category's workflow explicitly includes checkpoint gates. Remove any 'trivial' or 'obvious' escape hatches that let the agent skip checkpoints for that category.

**Target section:** Workflow / Task-type-specific rules

---

### REC-002: Use askQuestions tool instead of inline chat questions

**Priority:** P1 | **Category:** interaction-style | **Status:** `approved`

**Rationale:**
The agent asked questions as inline chat text instead of using the `askQuestions` tool. This was observed in 5 test case(s): bugfix-auth-broken, feature-add-auth, architecture-migrate-db, handoff-package-for-customer, compound-refactor-and-migrate. Inline questions don't provide selectable options and can be missed or misinterpreted.

**Evidence (failing test cases):** bugfix-auth-broken, feature-add-auth, architecture-migrate-db, handoff-package-for-customer, compound-refactor-and-migrate

**Current behavior in agent definition:**
Agent definition already contains related rules, but they may need strengthening:
  - ...(steps 1-9 above).  ## User Interaction Style  **Always use `vscode/askQuestions`** for user input — never embed questions as inli...
  - ...ways use `vscode/askQuestions`** for user input — never embed questions as inline chat text.  - **Decisions with options**: Present analysis...
  - ...ceed to implementation after presenting a plan in chat text — chat text is NOT a checkpoint; only `askQuestions` counts  **If you recognize a...

**Proposed change:**
Add interaction style rules:
  - 'Always use `askQuestions` for user input — never embed questions as inline chat text.'
  - 'For decisions with options: present analysis in chat, then call askQuestions with selectable options.'
  - 'Chat text is NOT a checkpoint; only askQuestions counts as a proper user input gate.'

**Target section:** User Interaction Style

---

## Workflow

1. Review each recommendation above
2. Update the `status` field to `approved` or `rejected` (with optional notes)
3. Run: `python -m runner.cli apply-recommendations <this-file>` (coming soon)
4. Re-run evals: `python -m runner.cli run-behavioral` to verify changes
