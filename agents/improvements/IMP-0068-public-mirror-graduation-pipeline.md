---
id: IMP-0068
title: Public-mirror graduation pipeline — manifest-driven sanitized publish of the QB system
status: proposed
source: review-2026-07-17
affects: [meta]
risk: medium
created: 2026-07-17
updated: 2026-07-17
commit: null
eval_type: structural
skip_validation: false
eval_id: imp_0068
eval_seed: 42
baseline_run: null
post_run: null
validation_evidence: []
manual_evidence: []
---

## Problem

The public mirror (`harryschaefer93/qb-agent-system` + its GitHub Pages site) rotted 5+
weeks (last push 2026-06-08 — the site still shows the pre-supercharge system: 10 agents,
old model roster, no SCOUT/ORACLE, no driver, no waves, no graduation gate). Root cause:
syncing is **manual sanitization with no tooling, no drift signal, and no mechanical leak
gate** — evidenced by the mirror's own commit history ("Replace real customer names and
personal name with fictional placeholders", "Remove all mail-agent references",
"Sync agent fleet + evals from canonical (sanitized)") and by 2 stray eval-baseline JSONs
currently sitting untracked in the mirror clone. Updates to the private system have no
path to graduate publicly without a human hand-scrubbing everything — so it doesn't
happen, and every future manual sync is one tired evening away from leaking a customer
name, an internal URL, or a session artifact.

## Proposal

Allowlist-first, defense in depth:

1. **`publish-manifest.json`** (private repo root): explicit **allowlist** of publishable
   paths + per-path transform rules (`copy` | `scrub` | `regenerate`). Nothing outside
   the manifest ever stages. Categorically excluded and asserted absent:
   `agents/knowledge/`, `session-state/`, `evals/evidence/`, `evals/baselines/`,
   `agents/files/` (nightly/hygiene reports), settings/permissions files, logs, anything
   matching the private-runtime state patterns (`m-*`, `data.db*`, …).
2. **`scripts/publish-public-mirror.ps1`**: reads the manifest → stages into the local
   mirror clone → applies **`scripts/publish-redaction-canon.json`** (single source:
   customer names → the established fictional placeholders from the June sync, personal
   name, internal tools/domains, tenant/resource ids + internal URLs, emails, run/session
   ids → hash (reuse the nightly `--safe-output` hashing pattern), local paths) → runs
   **gitleaks** over the staged tree (IMP-0048 machinery) → runs a **leak-lint** deny-scan
   (canon terms must have 0 hits post-scrub; unexpected binary/JSON files flagged) →
   emits a diff report → **stops**. Push is a human hard-ask, always.
3. **Drift signal:** a nightly/retro line comparing canonical HEAD vs the mirror's
   `last-sync` SHA (pattern: IMP-0029 partials drift check) so staleness surfaces instead
   of rotting silently.
4. **Site content is a `regenerate` target:** `docs/index.html` sections (How / Fleet /
   Flow / Improvements / Get started) are refreshed from curated source text, never
   auto-copied prose.

## Acceptance criteria

- [ ] Manifest + canon + script exist; manifest paths all resolve in canonical; excluded
      categories asserted absent from the manifest
- [ ] Rehearsal: a seeded fake secret AND a seeded customer name in staged content are
      BOTH blocked (gitleaks + leak-lint) with non-zero exit
- [ ] Scrub of a real IMP file that references customer-adjacent material (e.g. IMP-0053)
      produces 0 canon hits post-scrub
- [ ] Diff report generated per run; push happens only after explicit human approval
- [ ] Drift line renders in nightly/retro output
- [ ] First sync resolves the mirror clone's stray files (2 baseline JSONs deleted — not
      in manifest)

## Validation plan

Fully deterministic: the seeded-leak rehearsal + file inspection. The first real sync
doubles as the rehearsal-at-scale. Irreducibly manual: the human diff review before push
(by design — that is the last gate).

## Eval Plan

- **Type:** structural (`evaluators/custom/imp_0068.py`) — manifest parses, every manifest
  path exists in canonical, canon non-empty, script parses, excluded-category paths absent
  from manifest.
- **What we measure:** seeded-leak block (rehearsal), post-scrub canon-hit count (must be
  0), drift-line presence.
- **Pass criteria:** structural green; both seeded leaks blocked; 0 canon hits on the real
  staged tree.
- **Negative cases:** seeded secret passes gitleaks but matches leak-lint (and vice
  versa) — each layer must independently block; a manifest entry pointing at an excluded
  category fails the eval.
- **Known limits:** scrubbing is canon-driven — new sensitive terms must be added when new
  customers/engagements appear (retro checklist line). Leak-lint cannot catch semantic
  leaks (novel unlisted names) — the human diff review remains the last gate, which is
  why push stays a hard-ask forever.

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

- User-requested 2026-07-17 ("we need a way for updates to graduate into the published
  version without leaking secrets, customer info, or context"). **Not gated behind
  Wave 7** — direct user ask; runs alongside. First sync scheduled the same day.
- Mirror facts: public repo `harryschaefer93/qb-agent-system` (Pages serves from
  `docs/`), local clone at `~/qb-agent-system`; private canonical `dot-copilot` confirmed
  private. June sync precedent: fictional placeholders, mail-agent excluded.
