---
id: IMP-0010
title: Adopt fleet mode with file-based subagent outputs
status: rejected
source: review-context-window-2026-04
affects: [QB, DEV, INFRA, QA]
risk: high
created: 2026-04-27
updated: 2026-04-27
commit: null
---

## Problem

Subagents return long strings into the parent's window. Forcing them to write to files (e.g., `.qb/qa-report.md`, `.qb/dev-changes.md`) and have QB read only a summary line would isolate context further.

## Proposal

Make fleet mode the default for medium/large scope. Subagents write structured outputs to repo files; QB reads only summaries.

## Verdict — rejected

Overengineering for a solo POC workflow. Adds friction the customer will inherit:
- New `.qb/` directory polluting customer repos
- gitignore management overhead
- Subagent prompts now have to specify file paths and formats
- Debugging becomes "where did that file go" instead of "scroll up"

IMP-0001 (bounded returns) gets ~80% of the context savings at ~5% of the cost. IMP-0002 (session-memory scratchpad) covers the durable-state need without touching the customer's repo.

## Notes

If a future workload genuinely demands fleet mode (e.g., a 6-track DEV fan-out where summaries are still too big), revisit then. Not on speculation.
