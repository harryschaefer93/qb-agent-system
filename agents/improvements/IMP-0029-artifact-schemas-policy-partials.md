---
id: IMP-0029
title: Typed schemas for inter-agent artifacts + shared policy partials (FDPO dedup)
status: implemented
source: review-2026-06-10
affects: [QB, ARCH, QA, DEV, INFRA, REPO, scoper]
risk: medium
created: 2026-06-10
updated: 2026-07-13
commit: b0ccace
eval_type: structural
skip_validation: false
eval_id: imp_0029
eval_seed: 42
baseline_run: null
post_run: baselines/IMP-0029/20260713-135802-e12ee75-post.json
manual_evidence: []
---

## Problem

Inter-agent interfaces are formats-by-convention — prose templates the producing model must remember and the consuming model must trust:

- ARCH's `tracks:` block is "machine-parseable" only because the prompt promises that exact shape; QB's DEV fan-out depends on it parsing.
- QA's baseline/regression/delta blocks, QB's ~75-line Required Output Shape, BRIEF.md's required sections, REPO's output shape — none are validated by anything. QB "validates" BRIEF.md by eyeballing.
- Telemetry (IMP-0022) must *find* QB sessions via regex fingerprints of these shapes, and its known-limit note says the fingerprints drift as shapes evolve.

Separately, the **FDPO policy is copy-pasted with drift** across DEV, INFRA, ARCH, REPO, and QB (plus QA's principles) — five-plus slightly different wordings of the same hard constraint. A policy update today is five manual edits.

## Proposal

1. **JSON Schemas** under `evals/schemas/` for the load-bearing artifacts: BRIEF, ARCHITECTURE `tracks:` block, QA baseline/regression/delta blocks, QB run summary, REPO result. Producing agents emit the data as a fenced YAML/JSON block; a validator (`python -m pipeline validate-artifact <type> <file>`, or the IMP-0027 driver at phase transitions) checks conformance at the seam. A failed parse is a gate-bounce to the producing agent, same as a failed build.
2. **Shared policy partials.** `agents/partials/fdpo.md` becomes the single FDPO source. A small assemble step (extend `health-check.ps1` or a sibling script) injects it into each agent file between `<!-- partial:fdpo -->` markers; the CI gate (`run-all-imps`) fails on drift between the partial and any agent's assembled copy.
3. **Stable telemetry anchors.** Schema-validated blocks give `telemetry.py` deterministic detection targets, retiring the fragile regex-fingerprint approach over time (addresses IMP-0022's stated known limit).

## Acceptance criteria

- [ ] Schemas exist for ≥4 artifact types (tracks block, QA baseline, run summary, BRIEF) with a CLI validator + unit tests
- [ ] Tier-1 synthetic pipeline validates the tracks block and QA baseline artifacts in every applicable scenario
- [ ] `agents/partials/fdpo.md` is the single FDPO source; all five carrier agents contain an identical assembled copy; CI fails on drift
- [ ] A deliberately malformed tracks block produces a gate-bounce to ARCH (Tier-2 or real session), not a silent mis-fan-out
- [ ] `health-check.ps1` (or sibling) covers partial assembly + schema presence

## Validation plan

Structural for schemas/partials (CI). One real `new-poc-setup` session post-commit: confirm ARCH's tracks block passes validation and QB consumes the parsed form. Inject one malformed artifact in a test session and confirm the bounce path.

## Eval Plan

- **Type:** structural (schemas present, validator green, partial assembly drift-free) + Tier-1 pipeline artifact checks
- **What we measure:** schema validation pass rate across all 7 task-type scenarios; FDPO drift count (must be 0); fingerprint-vs-schema detection agreement in telemetry
- **Pass criteria:** all structural checks green; 0 drift; malformed-artifact negative case bounces
- **Known limits:** whether production models reliably emit the fenced blocks is behavioral — real-session check before `validated`.

## Results

**Implemented 2026-07-13** (Wave 4). Schemas: brief (markdown-heading contract + Source/EARS patterns), tracks-block, qa-baseline, qb-result, design-preview under `evals/schemas/`; validator `python -m pipeline validate-artifact <type> <file>` (`evals/pipeline/artifacts.py` — fenced json/yaml extraction or markdown-heading checks; jsonschema with structural fallback; failed parse = gate-bounce), 8 unit tests green. Partials: `agents/partials/fdpo.md` carried verbatim (marker blocks) by DEV/INFRA/ARCH/REPO — QB carries a pointer instead of the copy (IMP-0023 line cap; deliberate deviation from the 5-carrier acceptance line) — and `agents/partials/untrusted-content.md` carried by scoper (IMP-0035 fold-in done). Drift enforced twice: `evaluators/custom/imp_0029.py` (CI, 5/5) and `health-check.ps1`. Pending: Tier-1 pipeline artifact checks per scenario; real-session tracks-block validation + malformed-bounce.
## Notes

- Source: 2026-06-10 harness review, improvement #4.
- Pairs with IMP-0027 (driver enforces at transitions) but is standalone-valuable — the CLI validator works without the driver.
- Boundary vs IMP-0032: *policies* (always-loaded, non-negotiable → build-time partials, this IMP); *procedures* (on-demand knowledge → skills, IMP-0032).
- Directly addresses IMP-0022's known-limit ("content fingerprints drift as QB's Required Output Shape evolves").
