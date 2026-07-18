# Agent Improvements

Proposed, accepted, implemented, and rejected changes to the agent fleet. One file per improvement.

## Lifecycle

```
proposed -> accepted -> implemented -> validated
         \-> rejected
```

- **proposed** — captured (by you, by `retro`, by customer feedback). Not yet triaged.
- **accepted** — triaged, you've decided to do it. Has acceptance criteria.
- **rejected** — triaged, you've decided not to. Has a one-line reason. Keep the file so future-you doesn't re-litigate.
- **implemented** — change is merged. References the commit SHA.
- **validated** — change passed its targeted evidence gate and the mechanical four-point graduation
  check. Real sessions are strong corroboration, but are mandatory only when a criterion is
  irreducibly manual.
- *Superseded* is not a status: a superseded IMP keeps its terminal status and carries
  `superseded_by:` in frontmatter (reference case: IMP-0004 → IMP-0024). The runner treats
  `superseded_by` as authoritative and excludes the IMP from gates and queues.

## Driving the workflow

The IMP lifecycle is driven from the **Copilot CLI `imp` agent** (`agents/imp.md`) — now canonical. It has five modes: status (dashboard), orchestrate (default, end-to-end), implement, create-eval, and validate. The recommended execution order it reads lives in [`EXECUTION-ORDER.md`](EXECUTION-ORDER.md). The VS Code `prompts/*.prompt.md` slash-commands (`/Agent-Status`, `/IMP`, `/Implement-Improvement`, `/Create-IMP-Eval`, `/Validate-IMP`) remain as a frozen fallback for VS Code Copilot Chat. Opportunistic real-session `manual_evidence` is gathered via the retro agent's IMP Evidence Mode (`agents/retro.md` in CLI, `agents/retro.agent.md` in VS Code).

## `validated` bar (4-point gate, IMP-0015)

An IMP graduates from `implemented` to `validated` when **all** of the following hold:

1. **Applicable targeted evidence gate is green.** Use `run-imp --post/--compare`,
   `run-behavioral`, `run-personal`, or the IMP's deterministic rehearsal. Runtime
   `tool_loop` / `subagent_routing` / `behavioral` snapshots must have no conclusive failures,
   at least 15 conclusive observations, Wilson 95% lower bound >= 0.80, and at least one
   conclusive pass with zero conclusive failures in every declared scenario. Snapshots persist
   `declared_scenario_ids`; graduation reimports evaluator `get_scenarios()` and requires exact
   ID-set equality with no duplicates before aggregation. Rubric calibration and score,
   composite verdict, and manual inspection rules remain hard gates. `execution_metrics` requires
   a committed declared baseline and an exact passing baseline/post comparison.
2. **Evidence for non-structural eval types.** For `tool_loop` / `subagent_routing` / `behavioral` / `quality` / `rubric` / `composite`, validation needs runtime evidence the rule actually fires — satisfied by **either** of:
   - **(a) Typed validation evidence** — a passing `validation_evidence` record with
     `source: deterministic | synthetic | surrogate | real_session | inspection`, explicit
     artifact/commit provenance, and evaluator/dataset/subject hashes bound to
     `evaluated_commit`. For a committed artifact, `artifact_commit` is the later commit that
     first contains those exact bytes; `evaluated_commit` must precede it, it must precede current
     HEAD, and the artifact must be unchanged at HEAD.
     Typed `real_session` records additionally require a pseudonymous `session_id`, the raw
     regular-file artifact under `evals/evidence/<IMP-ID>/`, its content `artifact_sha256`, and
     proof that the artifact remains Git-ignored and untracked. They do not use
     `artifact_commit`.
   - **(b) Legacy real-session evidence** — an existing `manual_evidence` pass from a real
     Copilot session remains valid. Historical IMPs do not need to be rewritten.

   Prefer the cheapest qualifying evidence that exercises the same rule. Backfill real-session
   evidence opportunistically; require it only for production-only behavior, elapsed operation,
   physical interaction, picker availability, or genuine user judgment.

   Exception: an IMP with `skip_validation: true` AND eval_type `structural` or `manual` whose acceptance criteria are all verifiable by file inspection may auto-validate.
3. **Acceptance criteria checked.** All `## Acceptance criteria` checkboxes in the IMP file are ticked.
4. **CHANGELOG entry references a real commit SHA** (not `_pending_` or `null`).

Run `python -m runner.cli graduation-check IMP-NNNN` for the authoritative result. `--all`,
`--json`, and `--markdown` provide stable fleet/planner output. The command also checks
implementation-commit validity, evaluated/artifact-commit ancestry, artifact hash staleness, and
supersession. Before running it, commit the declared baseline/post snapshots, selected typed
evidence artifacts, `post_run`, and CHANGELOG SHA bookkeeping while status remains
`implemented`; capture that commit as `artifact_commit`. Then add the typed evidence record in a
separate bookkeeping commit that references the already-known SHA. Evidence cannot name the same
commit that creates it. The later status flip is a separate validation commit. Snapshot and
committed typed-evidence bytes must match current HEAD. The IMP file and CHANGELOG must themselves be
Git-tracked and byte-identical to current HEAD before the gate runs. After committing the status flip,
rerun `graduation-check`; on failure, immediately commit a correction back to `implemented` or
`needs-review` and never report validated from dirty state. Raw legacy/real-session artifacts may
remain gitignored.

What `validated` *signals*: the change is durable, demonstrated to work (in production **or** via a runtime/synthetic eval that exercises the rule), and safe to forget about. New IMPs should not duplicate work from a validated IMP unless they explicitly extend or revisit it.

## File naming

`IMP-NNNN-short-kebab-slug.md` — zero-padded sequential id, never reused, never renumbered.

## Frontmatter schema

```yaml
---
id: IMP-0001
title: Short human-readable title
status: proposed | accepted | implemented | validated | rejected
source: ad-hoc | retro-<session-id> | customer-<name> | review-<short-tag>
affects: [QB, DEV, ...]
class: fleet | personal      # default fleet; personal = not part of the QB system
risk: low | medium | high
created: YYYY-MM-DD
updated: YYYY-MM-DD
commit: <sha or null>
validation_evidence: []       # canonical typed evidence; see _template.md
manual_evidence: []           # legacy real-session evidence remains supported
---
```

## Body sections

- **Problem** — what hurts and how you noticed
- **Proposal** — concrete change
- **Acceptance criteria** — how you'll know it's done
- **Validation plan** — how you'll know it actually helped (sessions to watch, metrics, etc.)
- **Notes / decisions** — running log

See `_template.md` for a fillable starting point.

## Eval integration

IMPs are wired to the eval harness at `~/.copilot/evals/` so each one ships with a measurable before/after. The canonical plan lives at [`../../EVAL-SYSTEM-PLAN.md`](../../EVAL-SYSTEM-PLAN.md). Read it before adding eval fields to an IMP, capturing baselines, or modifying `/implement-improvement`. IMP-0004 is the reference example for a `structural` eval.

### Tool-palette / least-privilege IMPs — use the generic evaluator

For any IMP that changes an agent's `tools:` palette, you do **not** need a bespoke `imp_XXXX.py`. Set in the frontmatter:

```yaml
eval_type: structural
eval_id: tool_palette
affects: [<AGENTS>]
```

`evaluators/custom/tool_palette.py` then runs, per affected agent: single-`tools:`-line check, the agent's capability contract, and the synthetic-pipeline tool-availability check across every task-type scenario (model-free). The canonical per-agent role-tool spec is `evaluators/pipeline.py::CONTRACTS` — to cover a new agent, add an entry there (required tools + forbidden families/tools). IMP-0024/IMP-0025 are reference implementations (`imp_0024.py`/`imp_0025.py`); new tool IMPs should prefer `eval_id: tool_palette`. Run the whole suite with `python -m runner.cli run-all-imps` (the **structural fleet gate**).
It detects prompt/file regressions only; it never substitutes for a non-structural IMP's
**targeted evidence gate**.


## Real-session evidence backfill (opportunistic telemetry)

Real Copilot sessions are the strongest corroborating signal and are mandatory when an IMP
criterion cannot be reproduced synthetically. They are otherwise opportunistic backfill, not a
default graduation blocker. The legacy pipeline that gathers them remains supported:

- **Data layer:** `~/.copilot/evals/runner/telemetry.py` mines both local session stores (VS Code Copilot Chat + Copilot CLI), detects QB sessions by content fingerprint (the `agent_name` column doesn't tag custom agents), and scores them against per-IMP acceptance rules. Includes a **timing gate** — sessions predating an IMP commit cannot validate it.
- **Evidence layer:** raw JSON artifacts land in `~/.copilot/evals/evidence/IMP-NNNN/`
  (gitignored). Telemetry computes the artifact SHA-256 and emits a complete typed
  `validation_evidence` record with a pseudonymous session ID, current IMP frontmatter `commit`
  as `implementation_commit`, and selected snapshot `meta.commit_sha` as `evaluated_commit`.
  Raw notes, customer names, and repo paths never enter the tracked record.
- **Retro layer:** the `retro` agent's "IMP Evidence Mode" runs the telemetry CLI, presents findings, and edits IMP files on user approval. Trigger phrases: `evidence for IMP-XXXX`, `validate IMP-XXXX`, `evidence backfill`.

To gather real-session evidence for one or more IMPs, invoke the retro agent in IMP Evidence Mode
rather than editing `manual_evidence:` by hand. New non-session evidence belongs in
`validation_evidence`. The full workflow lives in `agents/retro.md`.

For `eval_type: behavioral`, the custom evaluator follows the runtime convention:
`get_scenarios() -> list[{id, prompt}]`, optional `N_SAMPLES`, and either
`check_<scenario_id>(response, scenario)` or `check_scenario(response, scenario)`. Checks return
`{passed, conclusive, detail}`. `run-imp --post` is the authoritative targeted snapshot used by
graduation. `run-personal` remains the broader personal-agent regression suite, not a substitute
for that IMP snapshot.

Tracked under IMP-0022.

## Working order

When picking what to work on next, sort by: `risk: low` first, then by impact (your judgement). Don't batch high-risk prompt changes — ship one, run a few real sessions, then move on.

## Fleet vs. personal IMPs

`class: fleet` (default) marks an IMP against the QB POC-delivery system (QB/DEV/INFRA/QA/DIAGRAM/DOCS plus workflow agents scoper, retro). `class: personal` marks an IMP against a standalone personal-productivity agent (e.g. mail-agent) that is **not** part of the QB system. Personal IMPs are siloed out of QB-system rollups and evaluated via the personal-agent suite (`python -m runner.cli run-personal`), not the QB gate. Agent classification is defined in `evals/config.yaml` under `agents.classification`.
