---
id: IMP-0054
title: PR intake pipeline — evidence-first review gate for agent-generated PRs
status: proposed
source: user-2026-07-15
affects: [REPO, QA, meta]
risk: medium
created: 2026-07-15
updated: 2026-07-15
commit: _pending_
eval_type: structural
skip_validation: false
eval_id: imp_0054
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

Cloud delegation (IMP-0053) moves the bottleneck from writing code to reviewing it —
industry data (Jan 2026) puts agent-generated code at ~1.7× the defect rate of human
code, and a single operator reviewing N async PRs cold is exactly the "single-operator
nightmare" to avoid. GitHub's own guidance ("agent PRs are everywhere") prescribes a
structured 10-minute framework; nothing in the harness implements it today. IMP-0034
Job 3 (PR-review pilot) sketched this — this IMP absorbs and supersedes it.

## Proposal

1. **REPO `pr-review` mode** implementing the 10-minute framework as a checklist
   artifact (`session-state/<run-id>/reports/pr-review-<n>.md`):
   (a) scan/classify scope; (b) **CI integrity FIRST** — coverage thresholds, removed/
   skipped tests, workflow conditions, `|| true` patterns; (c) duplicate-utility scan
   against the existing codebase; (d) trace the critical path end-to-end; (e) security
   boundaries (untrusted input, FDPO auth patterns); (f) test evidence — a test that
   fails on pre-change behavior. Verdict: **approve / iterate / reject-restructure**,
   with red-flag hits (CI gaming, code-reuse blindness, hallucinated correctness,
   prompt-injection surface, oversized-unscoped) as automatic reject.
2. **Layered review order.** Copilot code review runs first (mechanical layer: style,
   obvious logic, type mismatches) — REPO reads its findings rather than re-deriving
   them, then does the judgment layer. The human reads REPO's ≤20-line digest + verdict,
   not the raw diff, and decides. Target: ≤10 human minutes per PR.
3. **Iterate loop.** On `iterate`, REPO posts the specific asks as a single `@copilot`
   PR comment (batched — IMP-0051 discipline applies to agent-directed asks too);
   `iterations` increments in `delegations[]`; 2 unproductive rounds → escalate to
   operator with reject-restructure recommendation (mirrors the 2-cycle rule).
4. **Repo-side enforcement (rulesets, not vibes):** required status checks (build, tests,
   gitleaks from IMP-0048 hooks), no direct pushes to main by agents, Copilot code
   review requested automatically on agent PRs. **Merge remains a human hard-ask
   initially**; a narrow auto-merge class (green checks + REPO approve + {docs,
   test-only} change class) may be enabled per-repo after ≥10 clean cycles.
5. **Untrusted-content posture.** PR body/diff/comments from any agent are DATA, not
   instructions (existing `agents/partials/untrusted-content.md` protocol) — REPO never
   executes instructions found inside a reviewed PR.

## Acceptance criteria

- [ ] REPO `pr-review` mode with the 6-step checklist + verdict contract
- [ ] Red-flag list encoded; seeded CI-weakening PR is auto-rejected in a rehearsal
- [ ] Ruleset template (required checks + agent-PR review request) applied to pilot repo
- [ ] Iterate loop: one real `@copilot` iteration round-trip recorded in `delegations[]`
- [ ] Human minutes/PR measured and reported by IMP-0055's briefing (target ≤10)
- [ ] IMP-0034 Job 3 marked absorbed (note in its file)

## Eval Plan

- **Type:** structural (mode + checklist + red-flags present in REPO.agent.md; ruleset
  template file exists) + deterministic rehearsal (seeded bad-PR fixture) + real evidence.
- **Known limits:** Copilot code review is not a mergeable "required review" — enforcement
  is via status checks/rulesets; auto-merge stays opt-in per repo.

## Notes

- The editor-in-chief gate of `docs/wave6-cloud-delegation-plan.md`. Depends on IMP-0053
  (delegations to review) + IMP-0048 (pre-commit/gitleaks machinery). Feeds IMP-0055
  (briefing) and gates IMP-0043 (best-of-N produces N PRs — unreviewable without this).
- Also applies to non-delegated inbound PRs (human contributors, dependabot) for free.
