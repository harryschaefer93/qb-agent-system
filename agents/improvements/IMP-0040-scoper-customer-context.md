---
id: IMP-0040
title: Scoper customer-context expansion — the CRM + field vault, ordered research, provenance
status: implemented
source: review-2026-07-13
affects: [scoper, QB]
risk: low
created: 2026-07-13
updated: 2026-07-13
commit: 3195476
eval_type: structural
skip_validation: false
eval_id: imp_0040
eval_seed: 42
baseline_run: null
post_run: baselines/IMP-0040/20260713-132134-23c4f04-post.json
manual_evidence: []
---

## Problem

Pain point #2 (user-reported 2026-07-13): "the brief is not always great at grabbing context
from the actual customer things that are actually happening." Root cause: scoper's only
customer-context source was CrmSearch. The **the CRM** MCP server (opportunities, milestones,
accounts) and the **field-Vault** `vault-mcp` server (curated engagement notes) were configured in
`mcp-config.json` and permission-approved elsewhere — but absent from scoper's tool palette.
Briefs were built from a verbal dump plus whatever CrmSearch happened to surface, with no
provenance, so nobody could tell a researched fact from a guess. The BRIEF template lived only
as inline prose in scoper.md while QB validated briefs against its own hardcoded four-section
list — two divergent definitions of "a valid BRIEF".

## Proposal

1. **Tool expansion (read-only):** add to scoper — `crm-mcp/crm_whoami, crm_query,
   list_opportunities, get_my_active_opportunities, list_accounts_by_tpid, get_milestones` and
   `vault-mcp/get_customer_context, prepare_crm_prefetch, search_vault, read_note_section,
   get_note_metadata`. Root-scope read-only approvals added to `permissions-config.json`.
   SharePoint deferred: the Agent365 `sharepoint` server's tool names are not recorded anywhere
   in this repo — confirm them (toolSearch in a live session) before adding.
2. **Ordered research procedure** (Phase 2): knowledge base → vault-mcp vault → the CRM → CrmSearch →
   Teams/mail → web (last, least trusted). Every kept fact carries a `Source:` line (vault note
   path, opportunity ID, message subject/date, URL). "Don't stall on empty results" retained.
3. **Template extraction:** the 9-section BRIEF template moves to
   `skills/brief-template/SKILL.md` (native Agent Skills format) — scoper Phase 3 and QB's BRIEF
   preflight both consume it; one source of truth. Acceptance Criteria upgraded to **EARS
   notation** so QA can mechanically map criteria to tests (IMP-0018 `acceptance_clarity` 0.50).

## Acceptance criteria

- [ ] scoper frontmatter carries the crm-mcp/vault-mcp read-only tools; no write-capable CRM/vault tools
- [ ] Phase 2 orders sources vault → CRM → CrmSearch → web and requires `Source:` lines
- [ ] `skills/brief-template/SKILL.md` exists; scoper Phase 3 and QB Project Context both reference it
- [ ] Template's Acceptance Criteria section specifies EARS notation with examples
- [ ] Real scoping session: BRIEF.md Customer Context contains ≥1 CRM opportunity ID or vault
      citation as a `Source:` line (the "actually happening" signal)
- [ ] IMP-0018 rubric: `customer_context` score does not regress; expected to improve

## Validation plan

Structural checks by eval. Behavioral: one real scoping session on a live customer — old-vs-new
BRIEF side by side; pass = CRM opportunity IDs / vault citations appearing in Customer Context.
Re-run the IMP-0018 rubric (customer_context weight 0.40) with real-recorded, scrubbed crm-mcp/vault-mcp
fixtures.

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0040.py`)
- **What we measure:** tool palette (present + read-only); research-order phrasing; provenance
  rule; template existence + dual reference (scoper, QB); EARS section; knowledge-base step
- **Pass criteria:** all checks green
- **Negative cases:** no crm-mcp/vault-mcp write tools (create/update) in the palette
- **Known limits:** whether opus-scoper actually mines CRM/vault well is only observable in a
  real session — required before `validated`.

## Results

**Real-session evidence:** _pending — one live scoping session_

## Notes

- Source: 2026-07-13 supercharge review (pain point #2). Ships in the same wave as IMP-0035
  (hardening lands before the ingestion surface widens) and IMP-0041 (knowledge base is step 0
  of the research order).
- All crm-mcp/vault-mcp access is read-only research; scoper's Guidelines state CRM records and vault
  notes are never created or modified.
