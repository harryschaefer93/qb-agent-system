# QB Agent System

A multi-agent orchestration system for delivering Microsoft-first proof-of-concept (POC)
engineering work end-to-end — from architecture through code, infrastructure, validation,
diagrams, docs, and a clean repo handoff.

**🔗 [Overview site](https://harryschaefer93.github.io/qb-agent-system/)** — a visual, at-a-glance guide to the fleet, flow, and getting started.

At the center is **QB** (the "Quarterback"), an orchestrator that classifies a request,
gates it behind explicit human approval, and routes the work to specialist sub-agents —
with **SCOUT** running cheap read-only recon before planning, **ORACLE** offering an
advisory-only cross-family second opinion at conflicts, and a deterministic Python
**pipeline driver** (`evals/pipelines.yaml` + externalized `run-state.json`) enforcing
phase order so QB cannot skip a gate. A **retro** agent mines session history to measure
how the fleet performs, and an **imp** agent drives the improvement lifecycle those
findings feed.

> **Note on examples:** All customer names, contacts, and identifiers in this repo are
> fictional placeholders (Contoso, Fabrikam, Woodgrove, Adatum, …). Nothing here contains
> real customer data.

---

## Getting started (try it out)

These are **agent definitions**, not a standalone app — they run inside GitHub Copilot
(VS Code Copilot Chat and/or the Copilot CLI). To try them:

### Prerequisites

- **GitHub Copilot** access (Enterprise or a plan that exposes custom agents).
- Models for a **three-tier economy**: judgment agents declare an Opus-class model
  (`claude-opus-4.8-1m`), volume agents a Sonnet-class model, SCOUT a Haiku-class model,
  and ORACLE a cross-family model. If those exact ids aren't available to you, change the
  `model:` field in each agent's frontmatter (see *Adapt before you run* below).
- For the **build pipeline's full power** (optional to start): the MCP servers the agents
  reference — `azure-mcp`, `microsoft-learn`, `bicep`, `context7`, `playwright`. Missing MCP
  servers degrade gracefully; the orchestration still works without them.
- For the **eval harness**: Python ≥ 3.10.

### Install the agents

```bash
git clone https://github.com/harryschaefer93/qb-agent-system
cd qb-agent-system
```

- **Copilot CLI:** copy the CLI agents (`scoper.md`, `retro.md`, `imp.md`) into your
  `~/.copilot/agents/` directory.
- **VS Code Copilot Chat:** copy the `*.agent.md` files into your Copilot custom-agents
  directory, then pick the agent (e.g. **QB**) from the agent selector in Copilot Chat.

> Tip: start with just `QB.agent.md` + its specialists (`SCOUT`, `ARCH`, `QA`, `DEV`,
> `INFRA`, `DIAGRAM`, `DOCS`, `REPO`) to exercise the core pipeline.

### Run the pipeline

1. (Optional) Drop a `BRIEF.md` at your workspace root describing the POC — or let `scoper`
   generate one.
2. Invoke **QB** with a request, e.g. *"Build a POC for a RAG chatbot on Azure."*
3. QB classifies the task, asks you to confirm scope (**Checkpoint 1**), sends SCOUT on
   recon, runs QA, presents a **design preview** for approval (**Checkpoint 2**, which also
   pins the delivery contract — branch/push/deploy intent), then routes the work to the
   specialists. A session **autonomy dial** (`guided` · `standard` · `trusted`) tunes how
   chatty the run is; hard gates (new Azure cost, auth changes, push, destructive ops) hold
   at every level.

### Run the eval harness (optional)

```bash
cd evals
pip install -e .
python -m runner.cli run-behavioral qb --dry-run   # see QB's behavioral test cases
```

### Adapt before you run

This system was extracted from one engineer's environment. A few things assume that setup —
adjust them for yours:

- **Model IDs** — agents declare a three-tier model economy (Opus-class judgment,
  Sonnet-class volume, Haiku-class recon, cross-family ORACLE). Swap the `model:` fields
  for models your Copilot license exposes if needed.
- **`~/.copilot` paths** — the `retro` agent and parts of `evals/` assume the standard
  `~/.copilot/` location for the local Copilot session store. This is the default install
  path, so it works as-is on most setups (paths use `~` / `Path.home()` and are OS-agnostic).
- **MCP server names** — the VS Code agents list specific MCP tools in frontmatter. Any you
  don't have are simply ignored; trim the `tools:` list if you prefer a clean set.
- **FDPO / Microsoft-first conventions** — agents enforce Entra ID + RBAC (no API keys),
  `disableLocalAuth: true`, and a Microsoft-first stack. These align with FDPO tenants, so
  **no change is needed for FDPO environments** — they're the intended target.

---

## Two runtimes, one fleet

Every role ships in **two independent variants** because the two host environments expose
different tools and capabilities:

| File pattern | Runtime | Focus |
|---|---|---|
| `*.agent.md` | **VS Code Copilot Chat** | Editor-first, code-focused, uses `vscode/*`, `execute/*`, `agent/runSubagent` tool references |
| `*.md` (no `.agent`) | **GitHub Copilot CLI** | Work-context-aware assistants: `scoper`, `retro`, `imp` |
| `evals/pipelines.yaml` | **Python driver** | Deterministic pipeline state machine — phase order, iteration caps, checkpoint gating, externalized `run-state.json` |

The two agent sets share role names but have different system prompts and tool wiring. QB
and its build pipeline live in the VS Code variant; `scoper`, `retro`, and `imp` live in
the CLI variant. The driver is the piece that does the runtime's job in a runtime instead
of asking the model to self-police.

---

## How it works

### 1. Scope → Brief

[`agents/scoper.md`](agents/scoper.md) intakes a free-form customer brief, researches the
customer, and produces a `BRIEF.md` — the shared project context every downstream agent reads.

### 2. QB orchestrates the build

[`agents/QB.agent.md`](agents/QB.agent.md) is the orchestrator. It never writes code or
diagnoses issues itself — it **classifies, gates, and routes**:

1. **Classify** the request into a task type (`bug-fix`, `feature-request`, `refactor`,
   `optimization`, `new-poc-setup`, `full-delivery`, `customer-handoff`, …).
2. **Checkpoint 1 — scope clarification** (mandatory): QB asks the user to confirm scope
   *before* doing anything.
3. **SCOUT recon, then QA first**: cheap read-only reconnaissance feeds a QA assessment of
   the current state.
4. **Checkpoint 2 — design preview approval** (hard stop): QB presents the proposed change
   plan with evidence-backed recommendations, pins the delivery contract
   (branch/push/deploy), and waits for explicit approval.
5. **Execute** the scope-appropriate pipeline, fanning out to specialists — the phase order
   enforced by the driver, multi-track work isolated in worktrees.
6. **Validate, diagram, document, and hand off** — with a demo evidence pack in
   `HANDOFF.md`.

Both checkpoints are enforced through structured `askQuestions` calls — chat text never
counts as a checkpoint.

### 3. Specialists do the work

| Agent | Role | Owns / Produces |
|---|---|---|
| **SCOUT** — [`agents/SCOUT.agent.md`](agents/SCOUT.agent.md) | Recon (cheap, read-only) | Fast repo/pattern/constraint reconnaissance feeding the Checkpoint 2 design preview |
| **ARCH** — [`agents/ARCH.agent.md`](agents/ARCH.agent.md) | Solution architect | `ARCHITECTURE.md`: stack, trade-offs, identity plan, cost, parallelization tracks with owned paths |
| **QA** — [`agents/QA.agent.md`](agents/QA.agent.md) | Quality assurance (always first **and** last) | Diagnosis, baselines, validation, security review |
| **DEV** — [`agents/DEV.agent.md`](agents/DEV.agent.md) | Full-stack developer | Application code (Python/TS/C#/Java), tests, Dockerfiles |
| **INFRA** — [`agents/INFRA.agent.md`](agents/INFRA.agent.md) | Azure infrastructure | Bicep/Terraform IaC, networking, identity/RBAC, CI/CD |
| **DIAGRAM** — [`agents/DIAGRAM.agent.md`](agents/DIAGRAM.agent.md) | Diagram specialist | Architecture / sequence / data-flow / C4 diagrams with real cloud icons |
| **DOCS** — [`agents/DOCS.agent.md`](agents/DOCS.agent.md) | Technical writer | README, deployment guides, handoff docs (runs last) |
| **REPO** — [`agents/REPO.agent.md`](agents/REPO.agent.md) | Git/GitHub hygiene | Secret scanning, gitignore audit, OIDC CI/CD, commit + push |
| **ORACLE** — [`agents/ORACLE.agent.md`](agents/ORACLE.agent.md) | Cross-family second opinion | Advisory-only review at conflicts, pre-escalation, and risky approvals |

Multi-track builds (≥2 declared tracks) run in **isolated git worktrees** with attributed
merges and checkpoint/rewind — one failed track bounces alone, it never aborts the run.

### 4. Retro measures, imp improves

[`agents/retro.agent.md`](agents/retro.agent.md) (VS Code) and
[`agents/retro.md`](agents/retro.md) (CLI) mine the Copilot session history and run records
to score agent performance, surface friction, and file improvements; **Evidence Mode**
turns real sessions into validation proof. [`agents/imp.md`](agents/imp.md) (CLI) then
drives each improvement through its lifecycle — implement, create-eval, validate — with
hard human stops at every gate.

---

## Orchestration flow

```
                 ┌──────────┐
  scoper ──BRIEF─▶│   USER   │
                 └────┬─────┘
                      │ request
                      ▼
        ┌─────────────────────────────┐
        │             QB              │      pipeline driver
        │  classify → CHECKPOINT 1 ───┼──▶ askQuestions (scope)   ◀── waits
        └──────────────┬──────────────┘      (phase order enforced
                       ▼                       by pipelines.yaml +
                  ┌─────────┐                  run-state.json)
                  │  SCOUT  │ cheap read-only recon
                  └───┬─────┘
                      ▼ (always before build)
                  ┌────────┐
                  │   QA   │ diagnose / baseline
                  └───┬────┘
                      ▼
        ┌─────────────────────────────┐
        │  QB: design preview         │
        │  CHECKPOINT 2 ──────────────┼──▶ askQuestions (plan +   ◀── HARD STOP
        └──────────────┬──────────────┘      delivery contract)
            on approval │ route by task type
        ┌───────────────┼───────────────────────────┐
        ▼ (new-poc)     ▼ (any build)                │
    ┌──────┐       ┌──────┐   ┌───────┐  merge +     │
    │ ARCH │──────▶│ DEV  │   │ INFRA │  quality ◀───┤ bounce on fail
    └──────┘ tracks└──┬───┘   └───┬───┘  gates       │
       (≥2 tracks ⇒ isolated git worktrees,          │
        attributed merges, checkpoint/rewind)        │
                      └─────┬─────┘                   │
                            ▼                          │
                      ┌──────────┐                     │
                      │    QA    │ re-validate         │
                      └────┬─────┘                     │
                           ▼                            │
                     ┌──────────┐                       │
                     │ DIAGRAM  │──▶ QA diagram review  │
                     └────┬─────┘                       │
                          ▼                              │
                     ┌──────────┐                        │
                     │   DOCS   │ (runs last)            │
                     └────┬─────┘                        │
                          ▼                               │
                     ┌──────────┐                         │
                     │   REPO   │ secret scan → push      │
                     └──────────┘  (blocks on secrets)────┘
```

QA + both checkpoints are **universal**; ARCH / DIAGRAM / DOCS / REPO are conditional on the
task type and scope. The full per-task-type pipelines are defined in
[`agents/QB.agent.md`](agents/QB.agent.md).

---

## The improvement system

The fleet evolves through tracked **improvements (IMPs)** — one file per proposal, moving
through a `proposed → accepted → implemented → validated` lifecycle. 60+ have been filed
to date, shipped in pain-point waves (run-state + driver, customer context, recon + design
preview, worktree isolation, risk-tiered autonomy, model economy, synthetic-first
graduation — with DEV throughput and cloud delegation in flight).

Graduation to `validated` is **mechanical**, not vibes: typed, source-tagged evidence
(deterministic · synthetic · surrogate · real-session · inspection) with commit
provenance, Wilson-bound runtime confidence for behavioral claims, every acceptance
criterion ticked, and a real CHANGELOG SHA — enforced by a `graduation-check` CLI.

- **All improvements:** [`agents/improvements/`](agents/improvements/)
- **Conventions, lifecycle & the validated bar:** [`agents/improvements/README.md`](agents/improvements/README.md)
- **Execution order (pain-point waves):** [`agents/improvements/EXECUTION-ORDER.md`](agents/improvements/EXECUTION-ORDER.md)
- **Template:** [`agents/improvements/_template.md`](agents/improvements/_template.md)
- **Shipped changes log:** [`agents/CHANGELOG.md`](agents/CHANGELOG.md)

The loop is closed by retro: **retro discovers → IMP files capture → evals measure →
changes ship → next retro verifies impact.**

---

## The eval harness

[`evals/`](evals/) is a Python harness with nine eval types (structural, tool-loop,
subagent-routing, behavioral, quality, rubric-judged, execution-metrics, composite,
manual). A structural fleet gate runs nightly; telemetry mining scores real sessions from
both runtimes; run records feed completion / cycle-time / bounce KPIs.

- **The full design:** [`EVAL-SYSTEM-PLAN.md`](EVAL-SYSTEM-PLAN.md)
- **Overview:** [`evals/README.md`](evals/README.md)
- **CLI entry point:** [`evals/runner/cli.py`](evals/runner/cli.py)
- **Telemetry / evidence mining:** [`evals/runner/telemetry.py`](evals/runner/telemetry.py)
- **Artifact schemas (run-state, brief, design preview…):** [`evals/schemas/`](evals/schemas/)
- **Test datasets:** [`evals/datasets/`](evals/datasets/)
- **Evaluators:** [`evals/evaluators/`](evals/evaluators/)

```bash
cd evals
# Dry-run an agent's behavioral test cases
python -m runner.cli run-behavioral qb --dry-run
# Mine session telemetry for IMP validation evidence
python -m runner.telemetry scan --since 30d
```

---

## Repository layout

```
.
├── agents/
│   ├── QB.agent.md              # Orchestrator
│   ├── SCOUT / ARCH / QA / DEV / INFRA / DIAGRAM / DOCS / REPO / ORACLE (*.agent.md)
│   ├── retro.agent.md           # Retro (VS Code)
│   ├── retro.md                 # Retro (CLI)
│   ├── scoper.md                # Brief intake (CLI)
│   ├── imp.md                   # Improvement lifecycle (CLI)
│   ├── partials/                # Shared policy partials (FDPO, untrusted content)
│   ├── improvements/            # IMP backlog + lifecycle docs
│   ├── CHANGELOG.md             # Shipped changes
│   └── README.md                # Agent directory guide
├── evals/                       # Eval harness: runner, schemas, datasets, pipelines.yaml
├── EVAL-SYSTEM-PLAN.md          # The eval system's full design
└── README.md                    # You are here
```

See [`agents/README.md`](agents/README.md) for the full agent directory guide.

---

## Conventions

- **FDPO / passwordless first.** Agents enforce Entra ID + RBAC, managed identity, and
  `disableLocalAuth: true` — never API keys, connection strings with embedded keys, or SAS
  tokens as primary auth.
- **Microsoft-first stack.** Azure services, modern Microsoft Foundry for AI workloads,
  Fluent UI, MSAL.
- **`BRIEF.md` by reference.** Agents read shared context from `BRIEF.md` rather than having
  it pasted into every prompt.
- **Human-in-the-loop.** QB stops at two mandatory checkpoints; no implementation happens
  without explicit approval.
