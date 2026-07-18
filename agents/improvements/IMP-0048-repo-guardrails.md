---
id: IMP-0048
title: Deterministic repo guardrails — pre-commit gitleaks hook + AGENTS.md emission
status: implemented
source: review-2026-07-13
affects: [REPO, DEV]
risk: low
created: 2026-07-13
updated: 2026-07-13
commit: b0ccace
eval_type: manual
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

Secret hygiene in customer repos was prompt-driven and delivery-time only: REPO's mandatory
gitleaks scan fires at the end of the pipeline, so a secret committed mid-build lives in history
until then (and requires history rewriting to purge). Harness best practice (2026): enforce
hygiene with machinery at the earliest seam — the commit — not with prose at the last one.
Separately, delivered repos carried only `.github/copilot-instructions.md`; AGENTS.md is now the
cross-tool standard and customers don't all run Copilot.

## Proposal

`scripts/install-repo-guardrails.ps1` (run by REPO during setup/hygiene; poc-scaffold flow):

1. Installs `.git/hooks/pre-commit` running `gitleaks protect --staged` on every commit —
   blocks the commit on findings; warns-and-passes when gitleaks is absent (REPO's delivery
   scan remains the hard gate). LF endings; sh-portable.
2. Emits `AGENTS.md` at repo root when missing (never clobbers): ground rules (FDPO auth,
   secrets, structure, validation) mirroring copilot-instructions; REPO keeps the two in sync.

## Acceptance criteria

- [ ] Installer emits hook + AGENTS.md on a scratch repo (smoke-tested 2026-07-13: both true)
- [ ] REPO.agent.md carries the Deterministic Repo Guardrails section
- [ ] Real repo: a staged fake secret blocks the commit with the guardrail message
- [ ] Delivered repo contains AGENTS.md consistent with copilot-instructions.md

## Validation plan

Scratch-repo smoke (done); then one real repo-setup pass and one seeded-secret commit attempt.

## Eval Plan

- **Type:** manual (installer is deterministic; the seeded-secret check needs gitleaks installed)
- **Known limits:** hook enforcement requires gitleaks on PATH; absence degrades to
  delivery-time-only scanning by design, never a hard failure.

## Notes

- Source: 2026-07-13 supercharge review (July harness-practice sweep: deterministic gates at the
  earliest seam; AGENTS.md as cross-tool standard). Wave 4. Checkpoint commits (IMP-0033) run
  through this hook too — a checkpoint that trips gitleaks is a finding, not friction.
