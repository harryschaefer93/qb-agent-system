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

CLI agents are **work assistants** — they leverage the full Agency Stack (CrmSearch, Teams, Mail, People Directory, GitHub MCP, Azure MCP, Skills).

### Fleet / POC-delivery support

Part of the QB system — they feed or support the `scoper → QB → (DEV+INFRA+QA+DIAGRAM+DOCS)` delivery workflow.

| Agent | File | Role |
|---|---|---|
| scoper | `scoper.md` | Scope customer engagements → `BRIEF.md` |
| imp | `imp.md` | IMP improvement workflow — status / orchestrate / implement / create-eval / validate (CLI port of the `prompts/` slash-commands) |
| retro | `retro.md` | Session history mining & retrospectives; **IMP Evidence Mode** for `manual_evidence` gathering |

> **IMP workflow lives in both environments.** `agents/imp.md` (CLI) is now canonical for the IMP lifecycle; the VS Code `prompts/*.prompt.md` slash-commands are a frozen fallback. Likewise, retro's **IMP Evidence Mode** now exists in both `retro.md` (CLI) and `retro.agent.md` (VS Code).

### Personal productivity

Standalone work assistants — **not** part of the QB POC-delivery system. They are siloed out of the QB system suite (`run-all`, IMP fleet rollups) and tracked/evaluated separately (`run-personal`).

| Agent | File | Role |
|---|---|---|
| mail-agent | `mail-agent.md` | Email triage, response drafting, inbox status |

## Workflow

**scoper** → `BRIEF.md` → **QB** → (DEV + INFRA + QA + DIAGRAM + DOCS)

## Maintenance

Run `pwsh health-check.ps1` to validate cross-references and catch stale naming.

Setup created: 2026-04-15 | Updated: 2026-04-22
