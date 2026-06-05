# Agents Directory

Agent definitions for the QB system. See the [top-level README](../README.md) for how the
whole system fits together.

## Dual-Environment Setup

Each role ships in **two independent variants**:

| File Pattern | Environment | Focus |
|---|---|---|
| `*.agent.md` | VS Code Copilot Chat | Code-focused, editor-first |
| `*.md` (no `.agent`) | GitHub Copilot CLI | Work-context-aware, agency-mode |

The two sets share roles but have different system prompts, tool references, and capabilities.

## VS Code Agents (`*.agent.md`)

These use VS Code tool references (`vscode/*`, `execute/*`, `agent/runSubagent`) and are
optimized for the IDE workflow.

| Agent | File | Role |
|---|---|---|
| QB (Orchestrator) | [`QB.agent.md`](QB.agent.md) | Classifies, gates, and routes POC work |
| ARCH | [`ARCH.agent.md`](ARCH.agent.md) | Solution architecture → `ARCHITECTURE.md` |
| QA | [`QA.agent.md`](QA.agent.md) | Validation, testing, security review |
| DEV | [`DEV.agent.md`](DEV.agent.md) | Application code |
| INFRA | [`INFRA.agent.md`](INFRA.agent.md) | Bicep/Terraform IaC, Azure provisioning |
| DIAGRAM | [`DIAGRAM.agent.md`](DIAGRAM.agent.md) | Architecture diagrams with real cloud icons |
| DOCS | [`DOCS.agent.md`](DOCS.agent.md) | README, deployment guides, handoff docs |
| REPO | [`REPO.agent.md`](REPO.agent.md) | Git/GitHub hygiene, secret scanning, CI/CD |
| Retro | [`retro.agent.md`](retro.agent.md) | Session mining, scorecards, IMP evidence |

## CLI Agents (`*.md`)

CLI agents are **work assistants** leveraging the full Agency Stack (WorkIQ, Teams, Mail,
People Directory, GitHub MCP, Azure MCP, Skills).

| Agent | File | Role |
|---|---|---|
| scoper | [`scoper.md`](scoper.md) | Scope customer engagements → `BRIEF.md` |
| retro | [`retro.md`](retro.md) | Session history mining & retrospectives |

## Workflow

**scoper** → `BRIEF.md` → **QB** → (ARCH + DEV + INFRA + QA + DIAGRAM + DOCS + REPO)

## Improvement Tracking

Agent changes are tracked as IMPs under [`improvements/`](improvements/), with shipped
changes logged in [`CHANGELOG.md`](CHANGELOG.md). See
[`improvements/README.md`](improvements/README.md) for the lifecycle and conventions.
