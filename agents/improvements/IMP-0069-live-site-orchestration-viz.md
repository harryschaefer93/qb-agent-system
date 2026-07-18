---
id: IMP-0069
title: Data-driven public-site orchestration viz + fleet roster (generated fleet-data.json)
status: implemented
source: ad-hoc
affects: [meta, QB]
risk: low
created: 2026-07-17
updated: 2026-07-17
commit: 2baac37
eval_type: structural
skip_validation: false
eval_id: imp_0069
eval_seed: 42
baseline_run: null
post_run: null
validation_evidence: []
manual_evidence: []
---

## Problem

The public mirror site's "Orchestration flow" is a hand-drawn ASCII `<pre>` block and the
13 fleet cards are hand-authored HTML. Both rot the moment the system moves — IMP-0068
fixed **transport** rot (the mirror now syncs mechanically), but the site's *content*
about how the agents work is still maintained by hand, and it isn't engaging: a wall of
box-drawing characters doesn't show how agents actually interact. User ask (2026-07-17,
looking at the live #flow section): make it "way better and engaging so folks can
understand how all the agents are working and interacting", and because the fleet changes
over time, "we need a process to update and make it dynamic".

The dynamic process half-exists already: `evals/pipelines.yaml` is the authoritative
machine-readable pipeline spec (IMP-0027) and ships byte-identical in the mirror; agent
frontmatter carries models/descriptions; QB's frontmatter carries the `agents:` +
`handoffs:` edge list. Nothing renders any of it.

## Proposal

1. **Deterministic generator** `scripts/generate_fleet_data.py`: pipelines.yaml + the
   13-agent frontmatter roster → `evals/fleet-data.json` (committed, lockfile semantics).
   No timestamps/SHAs — a sha256 `source_fingerprint` instead, so unchanged inputs give
   byte-identical output. CP1/CP2 positions derived mechanically (CP2 = first DEV/INFRA
   index); per-phase artifacts zipped by occurrence (handles bug-fix's repeated QA);
   `multi_track` derived from ARCH's "parallelization tracks" artifact; blurbs =
   description first sentences with WHEN/DO-NOT-USE routing clauses stripped;
   `ensure_ascii` output. Fan-out example is generic/illustrative — run-state and real
   track data are private and never published.
2. **Publish-pipeline integration (extends IMP-0068, gates unchanged):** the publish
   script regenerates the dataset every run, stages it through the redaction canon
   (`evals/fleet-data.json` → `docs/fleet-data.json`, transform: scrub → fatal leak-lint
   + gitleaks), and **inlines the scrubbed JSON into `docs/index.html`** between fixed
   `<script type="application/json" id="fleet-data">` markers (index-based replacement;
   missing/duplicated marker or unsafe JSON ⇒ run fails non-zero). Inlining precedes the
   gates so the post-injection HTML is scanned; it also makes the page work from
   `file://` with no fetch.
3. **Self-contained interactive viz** `docs/fleet-viz.js` (vanilla JS + SVG, no external
   libraries): task-type selector chips re-render the real pipeline per type; animated
   QB→agent→QB dispatch pulse (runSubagent semantics; disabled under
   `prefers-reduced-motion` → static numbered sequence); CP1/CP2 gate glyphs with their
   spec `purpose` text; quality-gate-before-REPO glyph; iteration-cap badge + bounce
   hint; DEV worktree fan-out inset only for `multi_track` types; SCOUT/ORACLE
   satellites from QB's handoff list; hover/click detail cards (role, model tier,
   per-occurrence artifacts, GitHub link). The ASCII diagram stays as a collapsible
   text fallback + `<noscript>` path.
4. **Data-driven fleet roster:** the 13 cards render from the same JSON (existing static
   cards remain as the no-JS fallback).

## Acceptance criteria

- [x] Generator deterministic: two runs byte-identical; `--check` mode exits non-zero on
      staleness
- [x] Committed `evals/fleet-data.json` byte-equals regeneration (nightly rot signal via
      the structural eval)
- [x] Scrubbed dataset has 0 deny-term hits; blurbs contain no WHEN/DO-NOT-USE clauses
- [x] Reordering phases in a scratch copy of pipelines.yaml changes the emitted pipeline
      data (spec-driven, nothing hardcoded)
- [x] Viz renders all 7 task types with gates, iteration-cap badge, bounce hint, and the
      fan-out inset exactly for multi-track types; SCOUT/ORACLE satellites from QB's
      handoff list; 13 fleet cards render from data
- [x] `prefers-reduced-motion`, `<noscript>`, and collapsible-ASCII fallbacks present;
      page works from `file://` (inline JSON)
- [x] Publish run refreshes JSON + inline block with zero hand edits and fails non-zero
      on marker corruption
- [x] Visual browser check (desktop + narrow width) performed before the human-approved
      mirror push

## Validation plan

Fully deterministic (structural eval + generator `--check` + scripted publish run) except
one irreducibly manual criterion: the visual browser check before the human-approved
push — same posture as IMP-0068's human diff review.

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0069.py`).
- **What we measure:** generator parses + builds; schema shape (task_types ==
  pipelines.yaml keys, 13 agents, checkpoint indices in range, satellites present,
  fan-out tracks carry the tracks-block required keys, multi_track == spec-derived set);
  determinism (two in-memory serializations identical); committed freshness; spec-
  drivenness (scratch-copy phase reorder reflected); scrub-cleanliness (canon
  substitutions then 0 deny hits) + blurb cleanliness; QB frontmatter `agents:` ==
  published `orchestrator.subagents` (uses the runner-passed agent file); publish wiring
  tokens (generator step, inline marker, `$inlineOk` gate, manifest target + regenerate
  entry).
- **Pass criteria:** all checks green (currently 9/9).
- **Negative cases:** reordered-phases scratch copy must change the output (spec_driven
  check fails if hardcoded); a deny-term in any blurb fails scrub_clean.
- **Known limits:** rendering fidelity is browser-judged — the eval verifies data +
  wiring, not pixels; the manual visual check covers that.

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

- User-requested 2026-07-17 ("make the flow way better and engaging… and a process to
  update / make it dynamic"). Extends IMP-0068 — reuses its manifest/canon/gates
  untouched except one scrub target + one regenerate entry + the inline step. Runs
  alongside; not gated behind Wave 7.
- `affects: [meta, QB]` — QB is listed because the structural evaluator receives and
  parses QB.agent.md (its `agents:`/`handoffs:` blocks are published data sources);
  `run-all-imps` skips the pseudo-target `meta`, so a meta-only IMP would never invoke
  its evaluator.
- run-state.json / live run data remains private; the viz is spec-level only and the
  fan-out inset is a labeled illustrative example.
