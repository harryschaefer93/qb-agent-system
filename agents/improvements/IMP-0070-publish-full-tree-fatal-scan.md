---
id: IMP-0070
title: Public-mirror publish — fatal full-tree leak scan closes the staging-allowlist bypass
status: implemented
source: ad-hoc
affects: [meta, REPO]
risk: low
created: 2026-07-18
updated: 2026-07-18
commit: 87a268a
eval_type: structural
skip_validation: false
eval_id: imp_0070
eval_seed: 42
baseline_run: null
post_run: null
validation_evidence: []
manual_evidence: []
---

## Problem

A security review of the public mirror (2026-07-18) found that IMP-0068's manifest is a
**staging allowlist, not a tree allowlist**: the publish script scrubs and stages the
files the manifest lists, but never re-scrubs or removes files already in the mirror from
earlier (pre-IMP-0068) manual syncs. 68 of 175 tracked mirror files — the whole legacy
`evals/` harness — therefore bypassed the redaction canon entirely.

Concrete leak this hid: `evals/evaluators/rubrics/imp_0018.md` carried a stale eval-rubric
example with a named sponsor persona and engagement financials ("Sponsor: the sponsor, VP
Claims Automation, reporting to the COO… $3B annual claims spend…"). The private canonical
version had since been cleaned, but the mirror copy never updated because the file was
never a scrub target, and the canon had no person-name coverage. The gitleaks + staged
leak-lint gates both passed because the file wasn't staged and "the sponsor" wasn't a deny
term. (No credentials were ever exposed — gitleaks was clean across all history.)

## Proposal

1. **Fatal full-tree leak scan.** The publish script now runs the deny-term leak-lint over
   **every tracked mirror file** (`git ls-files`), not just freshly-staged ones, and any
   hit is **fatal** (was: advisory for non-staged files). Tracked-only, so gitignored
   local build artifacts (e.g. `__pycache__/*.pyc`, which can embed pre-scrub strings in
   bytecode) cannot false-fail the run. This is the structural guarantee: no tracked file,
   staged or legacy, can carry a deny term past publish.
2. **Person-name coverage in the canon.** Added the known sponsor persona ("the sponsor")
   as a deny term + substitution, with a note to append new engagement personas as they
   appear (the same maintenance contract as customer names).
3. **Bring the stale rubric docs under management.** Added `imp_0018.md`, `imp_0020.md`,
   and `imp_0020.calibration.jsonl` as scrub targets so the clean private versions
   propagate and stay scrubbed instead of rotting as legacy copies.
4. **Prune cruft.** Removed committed `*.structural.bak` backups from the mirror.

## Acceptance criteria

- [x] Publish script scans all tracked mirror files and fails non-zero on any deny-term
      hit in a non-staged file (verified: planting "Woodgrove"/"the sponsor" in a non-target
      tracked dataset file blocks the run with `tree_lint_hits=2`)
- [x] Tracked-only scan — gitignored `__pycache__/*.pyc` build artifacts do not fail the run
- [x] Canon covers the "the sponsor" persona (deny + substitution)
- [x] Stale `imp_0018.md` scrubbed clean via propagation from the clean private source
- [x] Full mirror tree passes: 0 real exposures across all tracked files, gitleaks clean
- [x] `.bak` cruft removed from the mirror

## Validation plan

Fully deterministic: the planted-leak negative test (bypass file blocks the publish) + the
full-tree sweep + gitleaks. No real-session requirement.

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0070.py`) — publish script contains the
  `git ls-files` tracked-tree scan, `$treeHits` is in the fatal `$failed` condition, and
  the canon carries person-name deny coverage.
- **Negative cases:** a deny term in a non-target tracked file must make `$failed` true.
- **Known limits:** the scan is deny-term-driven — a *novel* sensitive term with no canon
  entry still passes (same residual as IMP-0068; the human diff review before push is the
  backstop). Freshness of non-target legacy files is not guaranteed by this IMP — the scan
  guarantees they're leak-free, not up to date.

## Results

<!-- Auto-populated by /Implement-Improvement and /Validate-IMP -->
<!-- Validation gate: see README.md §`validated` bar (4-point gate, IMP-0015) -->

**Targeted evidence gate:** planted-leak negative test blocks publish; full-tree sweep + gitleaks clean.

## Notes

- `affects: [meta, REPO]` — REPO (git/push hygiene) is the nearest agent, so the
  structural evaluator runs in the fleet gate rather than being skipped as meta-only.
- Filed by the 2026-07-18 public-repo security review. Hardens IMP-0068 (the publish
  pipeline); companion to IMP-0069 (which rides the same pipeline). The review also found
  the pre-June commits in the public history still carry the real customer list + real
  maintainer name — remediated separately by recreating the repo with a clean single-commit
  history (git history rewrite, not a content change).
