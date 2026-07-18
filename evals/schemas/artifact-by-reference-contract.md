# Artifact-by-Reference Subagent Return Contract

Paste the following contract verbatim into every `runSubagent` prompt:

```text
Artifact-by-reference contract: Write your full report to `session-state/<run-id>/reports/<phase>-<agent>.md`. Return ONLY:
1. The report path.
2. A digest of 10 lines or fewer containing:
   - Blocker: yes/no.
   - Files cited by `path:line`.
   - Recommended next action.

Do not return the full report body, code dumps, full file contents, or step-by-step reasoning in the parent-visible response. Exception: if you must escalate a blocker, begin the response with `ESCALATING:`; an `ESCALATING:` response may exceed the 10-line digest cap when needed to explain the blocker.
```
