---
id: IMP-0044
title: Single-source agent definitions compiled per host (VS Code + CLI)
status: proposed
source: review-2026-07-13
affects: [meta]
risk: medium
created: 2026-07-13
updated: 2026-07-13
commit: null
eval_type: structural
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

The same roles are maintained twice — `*.agent.md` (VS Code) and `*.md` (CLI, e.g. retro's two
variants) — drift guaranteed; README documents the split as a known cost. BMAD v6's pattern:
one definition, compiled per host. IMP-0029's partial mechanism (markers + drift CI) is the
seed of the build step this needs.

## Proposal

`agents/src/<role>/` single-source definitions + a compile step (extends the IMP-0029 partial
assembly) emitting both `.agent.md` and `.md` targets; CI gate asserts compiled outputs are
fresh (recompile == committed bytes). Start with retro (the only currently-duplicated role);
expand only if more dual-host roles appear.

## Acceptance criteria

- [ ] `agents/src/retro/` compiles to both retro.agent.md and retro.md byte-identically with committed files
- [ ] CI fails when a compiled output is stale
- [ ] Partial injection (fdpo/untrusted-content) happens at compile time, replacing hand-synced marker blocks

## Notes

- Source: 2026-06-11 harness research candidate #6, scheduled by the 2026-07-13 supercharge
  review (Wave 6 backlog). Implement after Wave 4's partial mechanism has settled — the compile
  step subsumes the marker-sync discipline.
- **Extended 2026-07-15 (Wave 6):** the compile step gains a third target —
  `.github/agents/*.agent.md` **custom agents for the Copilot cloud coding agent** (the
  cloud environment supports custom agents/skills/hooks). One source definition then
  serves VS Code, the CLI, and cloud sessions, so a delegated DEV task runs under the
  same FDPO partials and conventions as a local one. Raises this IMP's value materially
  once IMP-0053 delegation is live.
