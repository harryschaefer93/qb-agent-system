# Eval Evidence Store

Raw, structured artifacts from real Copilot sessions, scored against per-IMP acceptance rules by `runner/telemetry.py`.

## Layout

```
evals/evidence/
├── README.md              # this file
├── _schema.json           # JSON Schema for EvidenceEntry
└── IMP-NNNN/
    └── YYYYMMDDTHHMMSS-<sid>.json     # one artifact per (IMP, session, capture)
```

## Where artifacts come from

```
python -m runner.telemetry scan --since 30d
python -m runner.telemetry score --session <sid> --imp IMP-0021 --write
python -m runner.telemetry backfill --imp IMP-0001 --imp IMP-0021 --since 90d
```

The `retro` agent runs these commands in "IMP Evidence Mode" — see `agents/retro.agent.md`.

## Privacy

- Raw artifacts may contain customer names, repo paths, or BRIEF.md excerpts from active POC sessions.
- `evals/evidence/*.json` is **gitignored** — never commit raw artifacts.
- Only the summary line emitted by `propose_manual_evidence_yaml_line` lands in IMP frontmatter; it carries session_id, verdict, capture date, scorer note, and the relative artifact path. No customer names or repo paths.

## Retention

- No automatic pruning. Artifacts are cheap (few KB each).
- If you delete an artifact, the IMP `manual_evidence:` entry that references it becomes a dangling pointer. Either re-run `telemetry score --write` to regenerate, or remove the IMP entry.

## Schema

See `_schema.json`. Every artifact has:

- `imp_id` — the IMP this evidence is scored against
- `session_id` — full session UUID from the Copilot session-store
- `captured_at` — ISO-8601 timestamp when telemetry ran
- `verdict` — `pass | fail | inconclusive` (see scorer logic in `runner/telemetry.py`)
- `fingerprint_matches` — which QB content patterns appeared in the session
- `observations` — full structured observation set from `extract_qb_observations`
- `notes` — human-readable scorer explanation
- `redactions_applied` — list of redaction kinds applied (currently always empty; redaction happens at the YAML line emit step, not in the artifact)

## Validated lifecycle integration

Per `agents/improvements/README.md` §`validated` bar, an IMP graduates from `implemented` to `validated` only when `manual_evidence:` contains at least one `verdict: pass` entry from a real Copilot session (not the surrogate harness). Evidence artifacts in this directory are the source of those entries.
