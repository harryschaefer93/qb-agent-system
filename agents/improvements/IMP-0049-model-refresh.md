---
id: IMP-0049
title: Fleet model refresh — three-tier economy (Opus 4.8 / Sonnet 5 / Haiku 4.5)
status: implemented
source: review-2026-07-14
affects: [QB, ARCH, DEV, INFRA, QA, DIAGRAM, DOCS, REPO, SCOUT, scoper, imp, retro, mail-agent]
risk: medium
created: 2026-07-14
updated: 2026-07-17
commit: 2f734e1
eval_type: structural
skip_validation: false
eval_id: imp_0049
eval_seed: 42
baseline_run: null
post_run: baselines/IMP-0049/20260714-145838-48fb2ce-post.json
manual_evidence: []
---

## Problem

The fleet ran two-generation-old models nearly everywhere (Opus 4.6/4.7-era), uniformly
expensive: opus-class on volume agents (QA runs 2–3× per pipeline; DOCS/REPO are structured
output from finished artifacts) and sonnet on SCOUT despite IMP-0031 wanting haiku-class (none
existed in the picker at the time — Haiku 4.5 and Sonnet 5 have since shipped to Copilot;
Sonnet 5 GA 2026-06-30). User directive 2026-07-14: optimize for quality and speed; cost a
secondary factor.

## Proposal — assignment table (enforced by `evaluators/custom/imp_0049.py`)

| Tier | Model | Agents | Rationale |
|---|---|---|---|
| Judgment | `claude-opus-4.8-1m` | QB, ARCH, DEV, INFRA, imp, retro (both variants) | newest frontier on checkpoint discipline/completion/code+IaC correctness; 1M kept (IMP-0009) |
| Judgment (non-1M) | `claude-opus-4.8` | scoper | the BRIEF is the product |
| Volume | `claude-sonnet-5` | QA, DIAGRAM, DOCS, REPO, mail-agent | new-generation mid-tier; faster than opus on checklist verification and structured writing; review loops + hard gates catch quality |
| Recon | `claude-haiku-4.5` | SCOUT | locate-don't-review; the haiku-class IMP-0031 originally specified |

## Acceptance criteria

- [ ] All 14 agent files carry the assigned `model:` (structural eval green)
- [ ] Every model id resolves in the VS Code / Copilot CLI picker (first invocation per agent — model-not-found = flip that one line back)
- [ ] Behavioral regression guard holds: live behavioral run ≥ 0.571 baseline (results/behavioral-qb-20260713-152414.json)
- [ ] One real pipeline run end-to-end on the new fleet with no model-attributable failure
- [ ] Retro compares cycle time + quality signals old-vs-new fleet after ~1 week of run records

## Validation plan

Structural eval now; the picker-resolution check happens on each agent's first real invocation
(cannot be verified outside the Copilot runtime — known limit). Rollback is per-agent and
one-line: `git log -p agents/<AGENT>.agent.md` shows the prior id; `guided`-dial sessions plus
run records give the before/after comparison.

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0049.py` — frontmatter assignment table)
- **Pass criteria:** 14/14 assignments exact
- **Known limits:** availability of `claude-opus-4.8-1m` / exact 1M variant ids for custom
  agents is runtime-verifiable only; `-internal` staff variants (DEV/QA previously on
  4.7-internal) may re-appear as 4.8-internal — swap in if exposed and preferred.

## Notes

- Source: 2026-07-14 model research (GitHub Copilot supported-models + Sonnet 5 GA changelog)
  + user directive ("be ambitious; quality, speed over cost — though cost is a factor").
- Ships as a model-only commit: zero prompt changes, so the 0.571 behavioral baseline and all
  structural evals isolate model effects from prompt effects.
- SCOUT's "bump one notch" escape hatch (IMP-0031) now means haiku→sonnet-5.
- **Addendum 2026-07-17 (sweep):** new CLI picker entries to consider in the ~07-21
  one-week retro compare (criterion 5): **Claude Fable 5** (CLI 1.0.61), **Opus 4.8 Fast**
  (1.0.66; replaces deprecated 4.6 Fast), **GPT-5.6** (1.0.70). Fable 5 / Opus 4.8 Fast
  are judgment-tier candidates; note any VS Code vs CLI picker-id differences before
  swapping (same first-invocation verification as the original rollout).
