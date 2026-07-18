---
id: IMP-0059
title: Customer-repo delegation governance — recorded decision on cloud-agent data boundaries
status: proposed
source: review-2026-07-15
affects: [meta, QB]
risk: low
created: 2026-07-15
updated: 2026-07-15
commit: null
eval_type: manual
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

IMP-0053 excludes customer repos from cloud delegation "pending a recorded
data-governance review" — correctly. But nothing owns that review: no IMP, no criteria,
no deadline. Unowned, the exclusion silently hardens into a permanent policy nobody
actually decided, and the largest share of real work (customer POCs) stays outside the
Wave 6 throughput gain — or worse, exclusion pressure erodes ad hoc ("just this one
repo") without the review ever happening. Both failure modes are governance-by-default
instead of governance-by-decision.

## Proposal (evaluate-then-decide — mirrors IMP-0056's pattern)

Produce a **decision memo recorded in this IMP** answering, with evidence:

1. **Execution locus vs FDPO posture:** the cloud coding agent runs in GitHub's
   ephemeral Actions cloud and does not respect content-exclusion settings — map exactly
   what customer content (code, BRIEF, secrets-shaped config, README context) would
   transit/execute where, versus what the FDPO posture (`agents/partials/fdpo.md`) and
   any customer agreements permit.
2. **Control inventory:** what boundaries exist per repo — org-level Copilot policies,
   repo visibility, fine-grained PAT scoping, what AGENTS.md/dispatch templates can and
   cannot prevent. Which controls are enforced vs advisory.
3. **Consent model:** does delegating a customer repo require explicit per-customer
   sign-off? If yes, define the artifact (an email? a line in the engagement playbook
   per IMP-0046?) and where it's recorded.
4. **Allowlist entry contract:** extend the `agents/delegation-allowlist.json` schema so
   a customer-repo entry MUST carry: governance-review date, consent artifact reference,
   scope limits (e.g. docs/test-only delegations), and expiry/re-review date. Schema
   enforced by the IMP-0053 evaluator once both land.

**Outcome is one of:** (a) adopt-with-conditions — customer repos delegable under the
entry contract; (b) permanent exclusion — recorded with reasons, and IMP-0053's
allowlist comment updated from "pending review" to "by decision IMP-0059"; (c) partial —
per-customer or per-change-class carve-outs. Any outcome is a win over "pending".

## Acceptance criteria

- [ ] Decision memo in this IMP's Results: all four questions answered with sources
      (GitHub docs on cloud-agent data handling + FDPO posture + engagement terms)
- [ ] Allowlist schema extension defined (even if the decision is exclusion — the schema
      documents *why* entries are refused)
- [ ] IMP-0053's "pending data-governance review" references this IMP id
- [ ] User (as accountable operator) explicitly signs the decision — this is a judgment
      call the agent researches but does not make

## Validation plan

Manual: the deliverable is the recorded decision. If outcome (a) or (c), the first
customer-repo delegation follows the entry contract end-to-end and is reviewed against
it; if (b), the negative case in IMP-0053 (customer-repo attempt refused with the
governance reason) cites this IMP.

## Eval Plan

- **Type:** manual (decision memo). No evaluator; the IMP-0053 structural evaluator
  picks up the allowlist schema fields if adopted.
- **Known limits:** GitHub's data-handling docs for the cloud agent evolve — the memo
  pins doc versions/dates; re-review on material platform changes.

## Notes

- Source: 2026-07-15 review of IMP-0049–0056 (unowned governance dependency in IMP-0053).
- Gated on the IMP-0053 pilot completing (personal repos) — the pilot's mechanics inform
  what a customer-repo delegation would actually expose. Do the research before the
  pressure to expand arrives, not after.
