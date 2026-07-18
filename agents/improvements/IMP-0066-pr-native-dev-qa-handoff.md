---
id: IMP-0066
title: PR-native DEV→QA handoff — draft PR per track, mechanical review first, QA narrowed to acceptance + evidence
status: proposed
source: review-2026-07-17
affects: [DEV, QA, REPO, QB]
risk: medium
created: 2026-07-17
updated: 2026-07-17
commit: null
eval_type: structural
skip_validation: false
eval_id: imp_0066
eval_seed: 42
baseline_run: null
post_run: null
validation_evidence: []
manual_evidence: []
---

## Problem

The DEV→QA handoff has no durable, reviewable artifact — QA deep-reviews a working tree
and re-derives scope by reading it. Evidence:

- `PilotApp-20260713-0837`: QA deep-review followed a ~6h serial DEV segment with only
  loose report files as the seam.
- Over-delivery went structurally unnoticed: ~576 .NET + 53 frontend tests on a
  "Personal V1" scope sailed through, because nothing presents *what changed vs. what was
  asked* as one reviewable unit. IMP-0062 adds the policing **rule**; QA still lacks the
  cheap **surface** to apply it.
- IMP-0063 found ~40 loose report files across 25+ hours with no run record — a PR is a
  timestamped, linkable handoff artifact the coverage layer can actually see.
- Free mechanical review goes unused intra-pipeline: PR-level Copilot code review is
  AGENTS.md-aware (since 2026-06-18; delivered repos already carry AGENTS.md via
  IMP-0048's guardrail installer), and `/review` + `/security-review` are GA in the CLI
  (1.0.62). We pay a judgment-tier QA model to find what the platform reviews for free.

## Proposal

1. **DEV track completion contract:** a track ends with a commit on its `track/<name>`
   branch (exists today per IMP-0033) and **REPO opens a draft PR** track → integration
   branch (REPO owns git — DEV never pushes; unchanged). PR body from a template: track
   scope, owned paths, acceptance criteria from the ARCHITECTURE `tracks:` block, and the
   rigor budget (IMP-0062).
2. **Mechanical pre-layer, free:** Copilot code review auto-requested on agent draft PRs
   (ruleset/repo setting — record the exact mechanism at implementation time); optionally
   REPO/QA run `/security-review` locally pre-PR. Review findings are **data**, not
   instructions (untrusted-content posture per `agents/partials/untrusted-content.md` —
   same stance as IMP-0054).
3. **QA narrows:** fast-check/deep-review consume the PR diff + mechanical findings
   instead of re-deriving them. QA output becomes: EARS acceptance-criteria verification,
   demo evidence pack (IMP-0047, unchanged), **rigor policing** (IMP-0062: over-budget =
   finding), and triage of mechanical findings (accept/dismiss with reason). No duplicate
   style/lint review.
4. **Merge gate unchanged:** `fanout-merge.ps1` remains the real merge with per-track
   conflict attribution (IMP-0033); the draft PR is the review surface and is
   closed/marked when the merge lands. Human hard-asks unchanged (REPO push rules).
5. **Serial runs included:** single-track runs open one draft PR at DEV finish — works
   without IMP-0061.
6. **Governance boundary:** auto-requested cloud review only on allowlisted personal repos
   (mirror IMP-0053's caution until IMP-0059 resolves customer-repo posture); local
   `/review` works everywhere.

## Acceptance criteria

- [ ] DEV completion contract + REPO draft-PR step wired in prompts (within line caps);
      PR body template file exists with owned-paths/acceptance/rigor fields
- [ ] Copilot code review auto-request wired on the pilot repo (mechanism recorded here)
- [ ] QA mode text consumes PR diff + mechanical findings; acceptance-verification +
      rigor-policing + findings-triage language present; duplicate style review removed
- [ ] A rehearsal or real run produces ≥1 draft-PR handoff; the QA report cites the PR
      number and the mechanical-findings triage
- [ ] IMP-0033 rehearsal tests still green (merge gate untouched)
- [ ] Negative: an instruction-bearing PR comment ("approve this / ignore your rules") is
      not acted on by QA/REPO

## Validation plan

Synthetic-first — extend the IMP-0033 scratch-repo rehearsal: create a track branch →
`gh pr create --draft` → assert body template + review request. Inspection covers the
prompt wiring. The injection negative runs as a cheap single-turn behavioral scenario
(house pattern from IMP-0035/0037). Real-run corroboration is opportunistic: the same next
multi-track run that discharges IMP-0061/IMP-0033. Irreducibly manual: none.

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0066.py`) — prompt sections present, PR
  body template exists, QA narrowing language present, merge-gate sections unmodified.
- **What we measure:** draft-PR handoff produced (rehearsal log), QA report citing PR +
  triage, QA wall-clock on the QA segment before/after (via IMP-0058 phase timing).
- **Pass criteria:** structural green; rehearsal produces the draft PR with template
  fields; injection negative passes.
- **Negative cases:** instruction-bearing PR comment ignored; PR creation failure bounces
  the track rather than silently skipping the handoff artifact.
- **Known limits:** Copilot review quality is advisory — QA's verdict remains the gate.
  PR creation needs repo network perms. Adds a small REPO step per track (seconds) against
  QA minutes saved; measure, don't assume.

## Results

<!-- Auto-populated by /Implement-Improvement and /Validate-IMP -->
<!-- Validation gate: see README.md §`validated` bar (4-point gate, IMP-0015) -->

| Metric | Baseline (mean ± σ, n) | Post (mean ± σ, n) | Delta | Regression? |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

**Quality / Speed / Cost summary** (Phase 1+ format):

- Quality: —
- Speed:   —
- Cost:    —

**Targeted evidence gate:** —

**Real-session corroboration:** —

## Notes

- Filed by the 2026-07-17 tech sweep. **Outbound twin of IMP-0054** (inbound PR intake) —
  shares its layering (mechanical first, judgment second) and red-flag vocabulary; no
  dependency between them.
- Depends on IMP-0033 (shipped) and IMP-0062 (budget language). Best after IMP-0061
  (per-track branches at scale) but functional for serial runs today. Helps IMP-0063
  (durable handoff artifacts the coverage layer can see).
- Multi-prompt change (DEV/QA/REPO/QB) → ships alone per the working-order rule.
