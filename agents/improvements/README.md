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
- **validated** — change has been observed in real sessions and confirmed to do what was claimed. References the validating session(s).

## `validated` bar (4-point gate, IMP-0015)

An IMP graduates from `implemented` to `validated` when **all** of the following hold:

1. **Eval verdict is green.** `post_run` JSON exists and `verdict` is `PASS` or `IMPROVEMENT` (not `REGRESSION`). For `eval_type: manual` this requirement is satisfied by inspection-only acceptance per the IMP's own acceptance criteria.
2. **Real-session evidence for non-structural eval types.** For `tool_loop` / `subagent_routing` / `behavioral` / `quality` / `rubric` / `composite`, the `manual_evidence` array must have at least one entry with `verdict: pass` from a real Copilot session (VS Code or CLI — NOT the surrogate harness alone). Exception: an IMP with `skip_validation: true` AND eval_type `structural` or `manual` whose acceptance criteria are all verifiable by file inspection may auto-validate.
3. **Acceptance criteria checked.** All `## Acceptance criteria` checkboxes in the IMP file are ticked.
4. **CHANGELOG entry references a real commit SHA** (not `_pending_` or `null`).

What `validated` *signals*: the change is durable, observed in production, and safe to forget about. New IMPs should not duplicate work from a validated IMP unless they explicitly extend or revisit it.

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
risk: low | medium | high
created: YYYY-MM-DD
updated: YYYY-MM-DD
commit: <sha or null>
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

## Manual evidence pipeline (real-session telemetry)

Non-structural IMPs require `manual_evidence` from real Copilot sessions to graduate from `implemented` to `validated` (see `validated` bar above). The pipeline that gathers it:

- **Data layer:** `~/.copilot/evals/runner/telemetry.py` mines both local session stores (VS Code Copilot Chat + Copilot CLI), detects QB sessions by content fingerprint (the `agent_name` column doesn't tag custom agents), and scores them against per-IMP acceptance rules. Includes a **timing gate** — sessions predating an IMP commit cannot validate it.
- **Evidence layer:** raw JSON artifacts land in `~/.copilot/evals/evidence/IMP-NNNN/` (gitignored). A privacy-scrubbed summary line is emitted for paste into the IMP frontmatter's `manual_evidence:` array (session_id prefix, verdict, capture date, scorer note, relative artifact path — no customer names or repo paths).
- **Retro layer:** the `retro` agent's "IMP Evidence Mode" runs the telemetry CLI, presents findings, and edits IMP files on user approval. Trigger phrases: `evidence for IMP-XXXX`, `validate IMP-XXXX`, `evidence backfill`.

To gather evidence for one or more IMPs, invoke the retro agent in IMP Evidence Mode rather than editing `manual_evidence:` by hand. The retro agent enforces the privacy guardrails and the timing gate, and refuses to write silently. See `agents/retro.agent.md` for the full workflow.

Tracked under IMP-0022.

## Working order

When picking what to work on next, sort by: `risk: low` first, then by impact (your judgement). Don't batch high-risk prompt changes — ship one, run a few real sessions, then move on.
