# Copilot Agents Directory

## Dual-Environment Setup

This directory contains agent definitions for **two separate environments**:

| File Pattern | Environment | Focus |
|---|---|---|
| `*.agent.md` | VS Code Copilot Chat | Code-focused, editor-first |
| `*.md` (no `.agent`) | GitHub Copilot CLI | Work-context-aware, agency-mode |

The two sets are **independent** — they share roles but have different system prompts, tool references, and capabilities.

## VS Code Agents (*.agent.md)

These use VS Code tool references (`vscode/*`, `execute/*`, `agent/runSubagent`) and are optimized for the IDE workflow.

| Agent | File |
|---|---|
| QB (Orchestrator) | `QB.agent.md` |
| DEV | `DEV.agent.md` |
| INFRA | `INFRA.agent.md` |
| QA | `QA.agent.md` |
| DIAGRAM | `DIAGRAM.agent.md` |
| DOCS | `DOCS.agent.md` |
| Retro | `retro.agent.md` |

## CLI Agents (*.md)

CLI agents are **work assistants** — they leverage the full Agency Stack (WorkIQ, Teams, Mail, People Directory, GitHub MCP, Azure MCP, Skills).

| Agent | File | Role |
|---|---|---|
| scoper | `scoper.md` | Scope customer engagements → `BRIEF.md` |
| inbox-triage | `inbox-triage.md` | Email triage, response drafting, inbox status |
| retro | `retro.md` | Session history mining & retrospectives |

## Workflow

**scoper** → `BRIEF.md` → **QB** → (DEV + INFRA + QA + DIAGRAM + DOCS)

## Maintenance

Run `pwsh health-check.ps1` to validate cross-references and catch stale naming.

Setup created: 2026-04-15 | Updated: 2026-04-22
