---
id: IMP-0032
title: Skill layer — progressive disclosure for procedural knowledge (DIAGRAM first)
status: implemented
source: review-2026-06-10
affects: [DIAGRAM, QB, DEV, INFRA, DOCS, scoper]
risk: medium
created: 2026-06-10
updated: 2026-07-13
commit: b0ccace
eval_type: structural
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

The system has no skill layer — every piece of knowledge is either an agent system prompt (always fully loaded) or inline prose. Gold-standard harnesses use **progressive disclosure**: a skill's name + one-line description is always loaded (~dozens of tokens), the full body loads only on trigger, and bundled scripts are *executed, not read*.

The tell is `DIAGRAM.agent.md`: **40KB** that is almost entirely reference material — icon taxonomies, diagram-type tables, `diagrams`-library usage, discovery procedures — loaded in full whether or not a diagram is in play. That's a skill wearing an agent costume. The pattern already exists in this repo for the *improvement* workflow (`prompts/*.prompt.md` are command-skills); the *delivery* workflow has none.

## Proposal

1. **Convention:** `agents/skills/<name>/SKILL.md` (+ optional `scripts/`). Header = name + one-line trigger description; body = the procedure. Agents are instructed to read the skill file by path when the trigger applies — the same read-by-reference move IMP-0006 validated for BRIEF.md.
2. **First conversion — diagram-generation:** DIAGRAM.agent.md keeps decision logic (diagram-type selection, review-loop behavior, fleet coordination) at ≤8KB; the icon taxonomy, library reference, and `generate.py` templates move to `agents/skills/diagram-generation/`. Behavior parity gated by the existing QA diagram review loop.
3. **Next extractions (separate commits):**
   - `azd-deploy-golden-path` (DEV/INFRA share — deploy + URL-surfacing procedure)
   - `customer-handoff-package` (DOCS/REPO share — the handoff checklist + release-notes procedure)
   - `brief-validation` (scoper + QB share — required sections + quality bar)
4. **Boundary vs IMP-0029:** *policies* (always-loaded, non-negotiable — FDPO) stay as build-time partials per IMP-0029; *procedures* (conditionally relevant) become skills. A skill is the right home exactly when the knowledge is only sometimes needed.

## Acceptance criteria

- [ ] Skill convention documented in `agents/README.md` (location, header format, read-by-path trigger instruction)
- [ ] DIAGRAM.agent.md ≤8KB; `agents/skills/diagram-generation/` carries the reference + script templates
- [ ] Parity check: regenerating an existing project's diagrams post-conversion passes the QA diagram review loop with no new blockers
- [ ] ≥2 further skills extracted and referenced by their owning agents
- [ ] `health-check.ps1` validates skill references (no dangling skill paths)

## Validation plan

Structural for the file moves (CI). Behavioral parity via one real diagram regeneration on an existing POC, QA-reviewed. Watch for the failure mode where the agent doesn't read the skill file when it should — if observed, strengthen the trigger line in the agent prompt (the IMP-0006 lesson).

## Eval Plan

- **Type:** structural
- **What we measure:** DIAGRAM file size budget; skill files present; agent prompts contain skill-trigger references; no dangling paths; aggregate always-loaded prompt bytes across the fleet (before/after)
- **Pass criteria:** all checks green; fleet always-loaded total shrinks ≥15%
- **Known limits:** whether agents actually read skills at the right moments is behavioral — the parity run + one real session required before `validated`.

## Results

**Implemented 2026-07-13** (Wave 4) — retargeted at the NATIVE Agent Skills standard (SKILL.md, progressive disclosure, GA across VS Code agent mode + Copilot CLI since Dec 2025), so no hand-rolled read-by-path convention was built. DIAGRAM extraction: 40.8KB -> 12.8KB agent (69% cut; ~2.5KB of the remainder is the tools frontmatter line — the original <=8KB target was set before accounting for that floor) + `skills/diagram-generation/SKILL.md` (29.9KB reference: style guide, Graphviz tuning, labeling/legend standards, layout scoring, icon catalogs, code templates, self-review checklist), byte-faithful mechanical split; agent keeps decision logic (type choice, discovery, non-negotiables digest) and points to the skill. Orphaned skills wired: DEV -> poc-scaffold, DOCS -> customer-handoff, QA -> demo-prep (their WHEN-trigger frontmatter was already native-compliant). Wave 1 already added skills/brief-template. health-check.ps1 gains a dangling-skill-reference check. Pending: behavioral parity check (regenerate an existing POC's diagrams through the QA review loop) + trigger-load confirmation in both hosts.
## Notes

- Source: 2026-06-10 gap analysis, gap #1 (biggest structural miss).
- Precedent: IMP-0006 (BRIEF-by-reference) validated the read-by-path mechanism this relies on; `prompts/*.prompt.md` proves the command-skill pattern works in this environment.
- Convert DIAGRAM first because it's the largest win and has an existing objective parity gate (the QA diagram review loop).
