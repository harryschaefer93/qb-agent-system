---
id: IMP-0046
title: Engagement playbooks — recurring POC patterns with pre-answered scope
status: implemented
source: review-2026-07-12
affects: [QB, meta]
risk: low
created: 2026-07-15
updated: 2026-07-15
commit: 5c5f96c
eval_type: structural
skip_validation: false
eval_id: imp_0046
eval_seed: 42
baseline_run: null
post_run: baselines/IMP-0046/20260715-124316-5b00071-post.json
manual_evidence: []
---

## Problem

Every `new-poc-setup` for a recurring pattern (RAG chatbot, document intelligence,
agentic workflow) re-asks the same scope questions — data source, auth posture, region,
out-of-scope list — even though the answers are the same engagement after engagement.
That is pure ask-friction (the user's #1 complaint) with zero information gain, and the
answers occasionally drift between runs (inconsistent acceptance criteria, forgotten
out-of-scope lines).

## Proposal

`agents/playbooks/*.md`: engagement templates with frontmatter (`id`, `task_type`,
`triggers`, `stack`, `scope_defaults`, `delivery`, `acceptance_template` in EARS form)
plus body notes for ARCH/DEV/INFRA (proven pitfalls, demo script skeleton). QB, after
classification: scan triggers; on match the scope ask collapses to **"Using playbook
`<id>` — confirm/adjust"** with every default visible in the option descriptions and an
"Ignore playbook" escape. Acceptance template copies into the BRIEF. Two hard rules:
no silent adoption of defaults the user hasn't seen, and playbook `delivery.push: ask`
never pre-answers the push hard-ask.

Seeded with the three recurring FSI patterns: `rag-chatbot-poc`, `doc-intelligence-poc`,
`agent-workflow-poc` — all FDPO-compliant by construction (Entra + managed identity,
`disableLocalAuth`, no keys).

## Acceptance criteria

- [x] `agents/playbooks/` exists with README contract + 3 seed playbooks carrying all
      required frontmatter keys
- [x] QB playbook-check rule wired after classification (within IMP-0023 cap: 436/440)
- [x] All seed defaults FDPO-compliant; `delivery.push` is `ask` in every playbook
- [ ] Real run: a matching request produces the collapsed "confirm/adjust" ask and the
      EARS template lands in the BRIEF
- [ ] Retro proposes a new playbook after a repeated engagement shape (approval-gated)

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0046.py`) — playbook frontmatter contract
  (required keys, task_type valid, push=ask), QB rule presence, README contract present.
- **Known limits:** trigger matching is prompt-executed (QB reads frontmatter at run
  time); precision/recall of matching is only observable from real runs.

## Notes

- Directly serves the ask-friction complaint (with IMP-0051): 0051 stops *repeat* asks,
  0046 removes the *first* ask for known patterns.
- Wave 6 item from the supercharge plan; pulled forward 2026-07-15 by the user's
  "review latest sessions, move imps forward" + confirmation-fatigue feedback.
- Playbooks are content, not code — retro owns their growth (Phase 4c knowledge pass).
