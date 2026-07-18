---
id: IMP-0026
title: Externalize pipeline run state + artifact-by-reference subagent returns
status: validated
source: review-2026-06-10
affects: [QB, QA, DEV, INFRA, ARCH, DIAGRAM, DOCS, REPO]
risk: medium
created: 2026-06-10
updated: 2026-07-17
commit: 8f8e0ec
eval_type: tool_loop
skip_validation: false
eval_id: imp_0026
eval_seed: 42
baseline_run: null
post_run: baselines/IMP-0026/20260611-202259-cd3c040-post.json
manual_evidence:
  - {session_id: b3bf850b, verdict: pass, captured: 2026-07-14, source: real-session, notes: "Real run PilotApp-20260713-0837 (CLI): 7 sub-agent invocations, artifact-by-reference held, no full report pasted in QB window | artifact: evidence/IMP-0026/20260714T125405-b3bf850b.json"}
  - {session_id: b4171155, verdict: pass, captured: 2026-07-15, source: real-session, notes: "Real run PilotApp-webpublic-20260714 (VS Code): artifact-by-reference held across 11 subagent dispatches, run-state/report paths referenced, no full report in QB window | artifact: evidence/IMP-0026/20260715T122212-b4171155.json"}
  - {session_id: 38050b1b, verdict: pass, captured: 2026-07-15, source: real-session, notes: "Real run xml-support-test-20260612: digests-only returns, run-state referenced | artifact: evidence/IMP-0026/"}
  - {session_id: f8145812, verdict: pass, captured: 2026-07-15, source: real-session, notes: "2 sub-agent invocations, digest-sized returns held | artifact: evidence/IMP-0026/"}
---

## Problem

QB's entire context-economy discipline is **self-policed prose**, spread across five shipped IMPs: IMP-0001 (bounded returns), IMP-0002 (scratchpad), IMP-0003 (checkpoint blocks), IMP-0005 (handoff protocol), IMP-0012 (self-prune). The line "Prior tool outputs may be discarded" is a wish, not an operation — nothing actually leaves the window. Self-pruning depends on the model behaving well *precisely when the window is already degraded*, the condition under which it polices worst.

Symptoms:
- Full subagent reports persist in QB's window for the whole session regardless of the prune rules.
- The Session Handoff Protocol (IMP-0005) requires the **user** to manually copy a Handoff Brief into a fresh session.
- IMP-0012's telemetry verdicts have been inconclusive — the rules are hard to even observe firing.
- ~8KB of QB.agent.md (the IMP-0001/0002/0003/0005/0012 blocks) exists solely to ask the model to do what the harness should do mechanically.

## Proposal

Make context economy structural instead of behavioral:

1. **Run-state file per pipeline run** at `~/.copilot/session-state/<session-id>/run-state.json` (precedent: IMP-0020's `research-cache.json` already lives there). Schema: `run_id, task_type, scope, phases[] {name, agent, verdict, artifact_path, started, finished}, approvals[] {checkpoint, options_presented, option_chosen, modified}, iteration_counters, gate_bounce_counters`. QB writes it at every phase transition.
2. **Artifact-by-reference returns.** Every `runSubagent` prompt carries a standard contract (same mechanism as the existing Return Discipline directive): *write your full report to `session-state/<run-id>/reports/<phase>-<agent>.md`; return only the path + a ≤10-line digest (blocker y/n, files cited, recommended next action).* QB's window never holds a full report, so IMP-0012's no-requoting rule becomes physically guaranteed rather than requested.
3. **Resume protocol.** A fresh QB session reads `run-state.json` + the digests and continues — replacing IMP-0005's manual paste-the-brief carry. IMP-0005's trigger conditions stay; the *action* becomes "tell the user to open a fresh session; it will resume automatically."
4. **On implement:** collapse the IMP-0002/0003/0005/0012 prose blocks in QB.agent.md into one short "Run State & Artifacts" section. Mark those IMPs `superseded_by: IMP-0026` (per the IMP-0024 → IMP-0004 precedent).

### Why this is not rejected-IMP-0010 again

IMP-0010 (fleet-mode file outputs) was rejected for four reasons; each is addressed:

| IMP-0010 rejection reason | How this differs |
|---|---|
| `.qb/` directory pollutes customer repos | Files live in `~/.copilot/session-state/`, never the customer repo. Nothing to gitignore. |
| gitignore management overhead | None — outside the repo entirely. |
| Subagent prompts must specify file paths/formats | One standard contract line, identical for every invocation — same cost as the existing Return Discipline directive QB already appends verbatim. |
| Debugging becomes "where did that file go" | `run-state.json` lists every artifact path; it IS the debugging view — plus a compliance audit trail (FSI) for free. |

Also new since the April rejection: IMP-0003/0005/0012 were all shipped *because* IMP-0001 alone didn't hold the window — the "80% of savings at 5% of cost" estimate under-delivered, and we now maintain four prose mechanisms doing one mechanism's job.

## Acceptance criteria

- [ ] `run-state.json` schema documented (in this IMP or `evals/schemas/`) and written at every phase transition in a real pipeline run
- [ ] All subagent invocation templates in QB.agent.md carry the write-report-return-digest contract
- [ ] QB.agent.md's IMP-0002/0003/0005/0012 blocks replaced by a single "Run State & Artifacts" section; file shrinks ≥10%
- [ ] A fresh session resumes a deliberately-interrupted pipeline run from run-state.json with no pasted Handoff Brief
- [ ] In a post-commit multi-agent session, no full subagent report (>30 lines) appears verbatim in QB's window (telemetry-scoreable: digest-only returns)
- [ ] Escalation exception preserved: a subagent return starting `ESCALATING:` may exceed the digest cap

## Validation plan

One `new-poc-setup` or `full-delivery` run post-commit: confirm run-state written at each seam, digests-only in QB's window, and artifacts readable. Then kill the session mid-pipeline and confirm a fresh session resumes from state. Add a telemetry scorer (digest-only returns + run-state file present) for `manual_evidence`.

## Eval Plan

- **Type:** tool_loop (Tier-2 surrogate pipeline)
- **What we measure:** in the recursive `runSubagent` trace, child agents emit a file-write for their report; parent-visible returns are ≤10 lines + path; run-state mock written at phase seams. Trajectory metrics: tool_call_count, redundant_call_rate.
- **Pass criteria:** 100% of subagent returns within digest cap across all 7 task-type scenarios; ≥1 resume scenario passes.
- **Negative cases:** an `ESCALATING:` return over the cap must NOT be flagged as a violation; a scenario with no subagent invocations must not demand a run-state file.
- **Known limits:** surrogate model is gpt-5.4; production is claude-opus-4.6-1m in VS Code Copilot. Real-session check required before `validated`.

## Notes

- Source: 2026-06-10 harness review (`agents/files/reviews/qb-harness-review-2026-06-10.md`, improvement #2 — recommended starting point of the five).
- Revisits **rejected IMP-0010** with the rejection reasons addressed (see table above). Per IMP-0010's own notes: "If a future workload genuinely demands fleet mode... revisit then."
- Subsumes-on-implement the prose of IMP-0002/0003/0005/0012. Also satisfies rejected IMP-0011's goal (survive context overload) via resumability instead of token counting.
- Substrate for IMP-0027 (driver stores state here) and IMP-0030 (run records extend this file).
- **Blocks IMP-0036 Layer 3:** the goal contract is recorded in this run-state; without it, IMP-0036 has no place to persist "phases remaining" for a deterministic completion check. IMP-0036 Layer 1 (prompt-only) shipped 2026-06-11 but plateaued at ~0.91 (prompt ceiling) — full elimination of premature yield needs this.
- 2026-06-11: **implemented** (full send). Substrate shipped: `evals/schemas/run-state.schema.json`, the artifact-by-reference contract (now in QB.agent.md's "Run State & Artifacts" section), and the IMP-0026 telemetry scorer (`_imp_0026`). The `tool_loop` eval `imp_0026.py` is wired but **mock-limited**: the qb `runSubagent` mock returns a generic echo, so digest-shape scenarios score INCONCLUSIVE rather than truly exercise the rule. Meaningful runtime validation needs either Tier-2 surrogate real child returns or a real session scored by the telemetry scorer — deferred. Current evidence = structural substrate present + scorer ready. Stays `implemented` (not `validated`) until real-session evidence.
- 2026-06-11 post (`cd3c040`, n=4): overall_pass_rate 1.00 but **all 4 scenarios INCONCLUSIVE** (echo mock — rule not positively exercised). Confirms the eval runs clean and crash-free; it does NOT demonstrate digest discipline. This is a wiring smoke, not behavioral evidence.
