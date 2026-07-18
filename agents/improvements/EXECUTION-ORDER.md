# IMP Execution Order

Canonical recommended-order doc for the agent-improvement backlog. **This file replaces
the VS Code-only `/memories/repo/agent-improvements.md` lookup** so the Copilot CLI `imp`
agent (`agents/imp.md`) can read the recommended order directly.

**Ordering rule** (from `README.md` → "Working order"): sort by `risk: low` first, then by
impact. Don't batch high-risk prompt changes — ship one, run a few real sessions, then move
on. Keep this file updated when an IMP changes status.

> Regenerated 2026-07-13 after the supercharge review. **Deliberate re-sort: the backlog is
> now grouped into pain-point waves** (plan: `~/.claude/plans/my-quarterback-agent-harness-unified-garden.md`)
> instead of pure risk-first — every dependency edge is preserved (0031 → 0030 → 0028;
> 0028 ships alone, last; best-of-N after 0033), but order within constraints follows the
> user's reported pain: completion → customer context → design preview → isolation →
> best practices → checkpoint restructure. IMP-0034/0037 defer to the backlog wave (they
> solve none of the five pain points).

## Wave 0 — Completion evidence + resume (pain #1) — DONE 2026-07-13; VALIDATED 2026-07-15 (except 0039)

- **IMP-0039** — Run resume + abandoned-run surfacing + notifications · `implemented` · risk low · QB/meta — still needs one real kill-and-resume
- **IMP-0030** — Outcome-grade run records + failed-trace-to-eval conversion · `validated 2026-07-15` (3 real records, KPI renders, regression case discriminates)
- IMP-0026/0027/0036 graduated `validated` 2026-07-15 on real-session evidence via the IMP-0052 telemetry source (see below).

## Wave 5.5 — Session forensics + ask discipline (pain #1, friction side) — DONE 2026-07-15

- **IMP-0052** — VS Code JSONL transcript telemetry source (Copilot Chat >=0.52) · `validated 2026-07-15` · risk low · meta — unblocked ALL VS Code-session validation evidence (60 scoreable sessions vs 14); subagent dispatch sessions excluded from QB scoring; 4-point bar met (real-session pass b4171155, nightly Job 2 exercises it unattended)
- **IMP-0051** — Ask discipline: clarification ledger (`pipeline clarify`, never re-ask, resume honors it), CP2 delivery contract (branch/push/deploy pinned up front), delegation-fatigue `--set-autonomy trusted`, harness-friction runbook (`docs/vscode-agent-friction.md`) · `implemented` · risk medium · QB/meta — validation: next real run shows zero re-asked decisions + wrap-up with no new non-hard-ask decisions; user applies runbook settings

## Wave 1 — Briefs that know the customer (pain #2) — DONE 2026-07-13, awaiting validation

- **IMP-0035** — Untrusted-content hardening for scoper · `implemented` · risk low · scoper (protocol + summarize-then-use quarantine; behavioral scenarios pending)
- **IMP-0040** — Scoper customer-context tool expansion (crm-mcp/vault-mcp, ordered research, Source: lines, brief-template skill w/ EARS) · `implemented` · risk low · scoper/QB (sharepoint deferred — tool names unconfirmed)
- **IMP-0041** — Knowledge base + retro auto-capture (`agents/knowledge/`) · `implemented` · risk low · retro/scoper/QB
- Validation: one real scoping session (CRM/vault citations in BRIEF), IMP-0018 rubric re-run, injection scenarios.

## Wave 2 — Design before build (pain #4) — DONE 2026-07-13, awaiting validation

- **IMP-0031** — SCOUT agent (sonnet, read-only; QA survey removed; routing dataset seeded) · `implemented` · risk medium · QB/QA — prerequisite for IMP-0028
- **IMP-0042** — Design preview at CP2 for the 4 small task types + deterministic repo map · `implemented` · risk medium · QB/QA/ARCH
- Validation: routing confusion matrix (IMP-0021 set) + 2 real sessions (bug-fix, feature-request) where CP2 presents the Proposed Change Plan.

## Wave 3 — Physical isolation (pain #3) — DONE 2026-07-13, awaiting validation

- **IMP-0033** — Git worktree isolation + checkpoint/rewind scripts · `implemented` · risk medium · REPO/QB/DEV (6 deterministic rehearsal tests green)
- **IMP-0043** — Best-of-N parallel DEV attempts · `proposed` — DO NOT implement until IMP-0033 is validated
- Validation: one real 2-track `new-poc-setup`; zero `checkpoint:` commits in pushed history.

## Wave 4 — Best practices loaded (pain #5) — DONE 2026-07-13, awaiting validation

- **IMP-0032** — Skill layer via native Agent Skills (DIAGRAM 40.8KB→12.8KB + 29.9KB trigger-loaded skill; orphaned skills wired) · `implemented` · risk medium
- **IMP-0029** — Artifact schemas (5) + `validate-artifact` CLI + fdpo/untrusted-content partials w/ drift CI · `implemented` · risk medium (QB carries a pointer, not the copy — line cap)
- **IMP-0047** — Demo evidence pack (browser-verified flows embedded in HANDOFF.md) · `implemented` · risk low · QA/DOCS
- **IMP-0048** — Deterministic repo guardrails (pre-commit gitleaks hook + AGENTS.md emission) · `implemented` · risk low · REPO
- Validation: DIAGRAM behavioral parity (regenerate an existing POC's diagrams); real tracks-block validation + malformed bounce; one handoff with embedded demo evidence; seeded-secret commit blocked.

## Wave 5 — Checkpoint restructure (pain #1 friction side) — DONE 2026-07-14 (gates waived by user directive)

- **IMP-0028** — Risk-tiered checkpoint policy + autonomy dial (guided|standard|trusted) · `implemented` · risk high · QB — preconditions (0030/0031/0033 validated) explicitly waived by the user; deviation recorded in the IMP Results. Shipped alone. `guided` = exact pre-0028 behavior (fallback dial position).
- Validation: 2–3 real sessions at `standard`; hard-ask negatives at `trusted`; override-rate table before any matrix tuning.

## Wave 6 — Cloud-async delegation (RESEARCHED + PLANNED 2026-07-15 — `docs/wave6-cloud-delegation-plan.md`)

Goal: QB becomes editor-in-chief of a mixed local + cloud fleet. Sequenced with gates —
each step must hold before the next; the single-operator rules (one intake funnel, WIP
cap 3, evidence-first review, batched attention, delegation-earned-per-repo) are binding.

1. **IMP-0053** — Cloud delegation routing (`gh agent-task` dispatch, delegable classification, delegation contract w/ EARS+FDPO, `delegations[]`, WIP cap, personal-repos-only allowlist — **customer repos excluded pending data-governance review**) · `proposed` · risk medium — gate: ≥2 real delegated PRs merged on PilotApp, ≤2 iteration rounds each
2. **IMP-0054** — PR intake pipeline (REPO `pr-review` mode: GitHub's 10-min framework, CI-integrity-first, red-flag auto-reject; Copilot code review as mechanical pre-layer; rulesets; @copilot iterate loop; **absorbs IMP-0034 Job 3**) · `proposed` · risk medium — gate: seeded CI-weakening PR auto-rejected
3. **IMP-0055** — Single-operator control plane (morning briefing script, notification routing policy, delegation KPIs in kpi/retro; Agent HQ mission control is the live console — integrate, don't build) · `proposed` · risk low — ship before exceeding 3 concurrent delegations
4. **IMP-0056** — gh-aw evaluation (hardened markdown→Actions workflows, safe outputs; spike + decision memo, adopt only if PAT/injection/cost criteria hold) · `proposed` · risk medium — gated on 1–3 live
5. **IMP-0043** — Best-of-N · `proposed` · **reframed**: parallel cloud sessions → N PRs → intake gate picks; needs 0033 `validated` + 0053/0054 live
6. **IMP-0044** — Single-source agent compilation · `proposed` · **extended**: third compile target `.github/agents/` so cloud sessions run the same agent definitions + FDPO partials as local

Still parked in Wave 6: task-DAG wave execution (driver dependency edges — after 0033 validates in production).

**Pilot doubles as the validation sprint (review 2026-07-15):** the IMP-0053 pilot's
local QB sessions are real runs — pick pilot tasks so they exercise the unvalidated
backlog: bug-fix/feature-request shapes at `standard` fire 0042 (design preview) +
0028 (consolidated CP2) + 0051 (ledger/delivery contract) + 0046 (playbook match);
deliberately kill-and-resume one session to discharge 0039. Use the IMP-0057 debt
table to plan the shapes.

### Wave 6 support (filed by the 2026-07-15 review)

- **IMP-0057** — Validation-run planner: debt table from live frontmatter + run-shape suggestions in imp status/nightly/briefing · `proposed` · risk low — ship before/alongside the 0053 pilot (it shapes the pilot)
- **IMP-0058** — Cost telemetry: populate `cost_estimate_total` from transcript request counts × tier weights; delegation credit spend once 0053 lands · `proposed` · risk low — ship alongside 0055 (briefing gets a cost column); first consumer = IMP-0049's one-week retro compare (~2026-07-21)
- **IMP-0059** — Customer-repo delegation governance: decision memo + allowlist entry contract for the boundary IMP-0053 parks as "pending review" · `proposed` · risk low — gated on the 0053 pilot completing; user signs the decision

## Wave 7 — DEV throughput (pain: cycle time — filed by the 2026-07-16 review; 2026-07-17 sweep slotted 0065/0066 in + 0061 dispatch addendum)

Evidence: DEV segment = 80–97% of run wall clock (6h05m serial tracks in
`PilotApp-20260713-0837`, 5h32m single segment in `PilotApp-webpublic-20260714`);
mean cycle time 430.9 min (nightly 2026-07-16) — **and that undercounts**: three further
run-shaped efforts (repo-20260714, deploy-20260715, fanout-20260715 — the last one ~40
reports over 25+h with track A iterating A2→A8 on live auth) have no run records at all;
the 3-day deploy/auth tail dwarfs the 1-day build. Zero prior IMPs target DEV duration.
**Priority call: nothing meta ships ahead of this wave + the IMP-0053 pilot.**

1. **IMP-0063** — Run-record coverage (canonical root, QB active-run-id rule, untracked-work KPI, July backfill) — see the work at all · `proposed` · risk low
2. **IMP-0058 addendum** — per-phase/per-track wall time in run-state + kpi/nightly (DEV segment becomes the headline KPI) · `proposed` · risk low
3. **IMP-0064** — Governed-tenant deploy preflight + live-auth smoke + landmine knowledge capture — kills the 8-iteration auth tail · `proposed` · risk low
4. **IMP-0062** — Rigor dial (`poc|hardened|production` at CP2; ARCH test budgets; DEV honors; QA polices over-delivery) — shrinks the work · `proposed` · risk medium
5. **IMP-0065** — CLI hook guardrails + worker telemetry (preToolUse exit-2 deny for headless workers; sessionStart/End run-record + timing stamps) — the seatbelt for 0061's workers; validation fully deterministic · `proposed` · risk low — gate: before or with 0061's first dispatched wave
6. **IMP-0061** — Parallel DEV track execution (driver dependency waves + ≤3 headless workers over IMP-0033 worktrees; ~36% projected cut on the 07-13 shape) — overlaps the work · `proposed` · risk medium — its real run doubles as IMP-0033's owed 2-track validation. Dispatch backend per 2026-07-17 addendum: native `/fleet` preferred, `fanout-dispatch.ps1` pool fallback; worktrees kept; verify account-tier subagent concurrency first — depends on 0065 for the worker deny layer
7. **IMP-0066** — PR-native DEV→QA handoff (draft PR per track; Copilot code review + `/security-review` as free mechanical pre-layer; QA narrows to acceptance + demo evidence + 0062 rigor policing) · `proposed` · risk medium — after 0062, alongside/after 0061; multi-prompt change, ships alone
8. **IMP-0053** (Wave 6 step 1) is the remaining lever: move delegable work off the local session entirely — pilot unchanged, runs alongside this wave

### Gated behind Wave 7 + the IMP-0053 pilot (filed 2026-07-17, deliberately last)

- **IMP-0067** — Same-runtime eval spike: replay 1–2 behavioral evals through Copilot SDK sessions (real prompts, real models), verdict agreement vs the Foundry gpt-5.4 surrogate, decision memo (IMP-0056 shape) · `proposed` · risk low — the sweep's only meta filing; do not start before Wave 7 items 1–7 and the 0053 pilot complete

### User-requested, runs alongside (2026-07-17)

- **IMP-0068** — Public-mirror graduation pipeline (allowlist manifest → scrub canon → gitleaks + leak-lint → diff report; push always a human hard-ask; drift line in nightly/retro) · `proposed` · risk medium — public site 5 weeks stale; first sanitized sync runs 2026-07-17
- **IMP-0069** — Data-driven site orchestration viz + fleet roster (deterministic `fleet-data.json` from pipelines.yaml + agent frontmatter → 0068 scrub path → inlined into index.html; interactive SVG w/ task-type chips + dispatch animation; ASCII kept as fallback) · `proposed` · risk low — extends IMP-0068; regenerated every publish run so site content can't rot

## Wave 6 predecessors already shipped

- **IMP-0045** — ORACLE second-opinion advisor (gpt-5.5, advisory-only) · `implemented 2026-07-14`
- **IMP-0046** — Engagement playbooks (3 FSI seeds; QB collapse-to-confirm rule) · `implemented 2026-07-15` — validation: one real matching run
- **IMP-0034** — Headless & scheduled fleet operation · Jobs 1+2 shipped; **Job 3 absorbed into IMP-0054**
- **IMP-0037** — Untrusted-content hardening for mail-agent · `implemented 2026-07-14` (injection scenarios pending)

## Fleet model refresh — DONE 2026-07-14

- **IMP-0049** — Three-tier model economy: Opus 4.8(-1m) judgment / Sonnet 5 volume / Haiku 4.5 recon across all 14 agents · `implemented` · risk medium — model-only commit; 0.571 behavioral baseline is the regression guard; per-agent one-line rollback. First invocation per agent verifies picker id resolution.

## Implemented — awaiting validation evidence

These shipped but haven't graduated to `validated` (need a real-session `manual_evidence`
entry or a passing post-eval per the `validated` bar in `README.md`). Run `imp` validate
mode (or retro IMP Evidence Mode) when a qualifying session exists.

- **IMP-0038** — Port the IMP improvement workflow to the Copilot CLI · manual · meta
- **IMP-0039** — Run resume + notifications · structural · QB/meta — 4/4 structural + 18 pytest; needs one real kill-and-resume session
- **IMP-0017** — /IMP orchestrator command · manual · meta
- **IMP-0020** — Evidence-backed recommended option at QB checkpoints · rubric · QB

## Closed

- **Validated:** IMP-0001, 0002, 0003, 0005, 0006, 0012, 0013, 0014, 0015, 0016, 0018, 0019, 0021, 0022, 0023, 0024, 0025, **0026, 0027, 0030, 0036** (2026-07-15, real-session evidence via IMP-0052), **0052** (2026-07-15)
- **Superseded:** IMP-0004 → IMP-0024 (validated). Criterion 2 permanently reverted by `d77b918`; can never meet the 4-point bar — removed from the awaiting-validation queue 2026-07-15, evidence retained in the file.
- **Rejected:** IMP-0007, 0008, 0009, 0010, 0011 (see each file's verdict for the reason)
