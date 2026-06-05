"""
IMP-0001 evaluator — tool_loop eval (reclassified from structural 2026-04-28).

Tests that QB actually appends the Subagent Return Discipline directive to
EVERY runSubagent prompt at runtime, not just that the rule text exists in
the agent definition file.

The rule (from QB.agent.md Critical Rule #7):
> Every prompt you issue to a subagent MUST end with the following directive
> (verbatim or near-verbatim):
>     Return only the Required Output Shape. Do not include code dumps, full
>     file contents, or step-by-step reasoning. Cite files by `path:line`.
>     Cap your response at ~400 tokens unless escalating a blocker.

Scoring:
  - PASS: at least one runSubagent call observed AND every observed call's
          prompt contains >= MIN_MARKER_HITS distinctive directive markers.
  - FAIL: at least one observed runSubagent call's prompt is missing the
          directive (a real violation of the IMP rule).
  - PASS-with-note ("inconclusive"): zero runSubagent calls within the
          6-turn budget. The IMP governs prompt CONTENT, not whether QB
          ever invokes a subagent. Mocked askQuestions returns a single
          static "Approve" answer that does not always drive QB through
          Checkpoint 1 -> Checkpoint 2 -> subagent invocation. Counting
          this as a failure would make the eval flaky for reasons unrelated
          to the rule under test. Treated as PASS with the detail string
          flagging it as inconclusive.
"""

from __future__ import annotations

from evaluators.tool_loop import LoopTrace


# Distinctive markers from the bounded-return directive. The rule allows
# "verbatim or near-verbatim", so we require >= 2 marker hits per prompt.
DIRECTIVE_MARKERS = [
    "required output shape",
    "400 token",          # matches "~400 tokens" / "400 tokens"
    "code dump",          # "no code dumps" / "do not include code dumps"
    "path:line",          # citation convention
    "cite files by",
    "step-by-step reasoning",
]
MIN_MARKER_HITS = 2

# Per-IMP runner overrides (consumed by run_tool_loop_eval).
# Bumped above the §3a defaults to reduce the inconclusive-sample rate while
# proving runtime compliance for the bounded-return directive.
N_SAMPLES = 5
MAX_TURNS = 8


def get_scenarios() -> list[dict]:
    """Return the scenario set for this evaluator.

    Two scenarios cover the two main paths that drive QB to invoke a subagent:
      - bug-fix          -> QA after Checkpoint 1
      - new-poc-setup    -> ARCH after Checkpoint 1

    The rule applies regardless of task type, so checking both confirms
    coverage isn't accidentally workflow-specific.
    """
    return [
        {
            # Bugfix prompt with scope baked in to minimize Checkpoint 1
            # clarification loops under mocked askQuestions. We need QB to
            # reach QA invocation reliably so the directive can be inspected.
            "id": "bugfix_qa_invocation",
            "prompt": (
                "The /api/claims endpoint returns HTTP 500 with a ValueError "
                "when payload size exceeds 1MB. Backend only \u2014 do not "
                "investigate the frontend. Just patch this single endpoint, "
                "no broader audit. Quick patch is fine; root-cause investigation "
                "is not needed. The error logs already point to "
                "`api/claims_handler.py:42` where payload is parsed. Proceed "
                "directly with the standard QA \u2192 Dev pipeline."
            ),
            "expected": {
                "must_include_directive": True,
            },
        },
        {
            "id": "new_poc_arch_invocation",
            "prompt": (
                "Kick off a new POC for Contoso Insurance \u2014 claims submission portal "
                "with FastAPI backend, React frontend, Azure SQL, and Entra ID auth. "
                "Scope is approved as-is, no further clarification needed. "
                "Proceed directly with the standard new-poc-setup pipeline."
            ),
            "expected": {
                "must_include_directive": True,
            },
        },
    ]


def check_scenario(trace: LoopTrace, scenario: dict) -> dict:
    """Inspect every runSubagent call in the trace and verify its prompt
    contains the bounded-return directive (>= MIN_MARKER_HITS markers).
    """
    expected = scenario.get("expected", {})

    subagent_calls = []  # list of dicts: turn, agent, prompt
    for turn in trace.turns:
        for tc in turn.get("tool_calls", []):
            if tc.get("name") == "runSubagent":
                args = tc.get("arguments", {}) or {}
                subagent_calls.append({
                    "turn": turn.get("turn"),
                    "agent": args.get("agentName", "unknown"),
                    "prompt": args.get("prompt", "") or "",
                })

    if not expected.get("must_include_directive"):
        return {
            "passed": True,
            "detail": f"No directive check requested; {len(subagent_calls)} subagent call(s)",
        }

    # No subagent calls observed. The IMP governs prompt content, not whether
    # QB ever invokes a subagent. Mark inconclusive (passed=True with note).
    if not subagent_calls:
        return {
            "passed": True,
            "detail": (
                f"INCONCLUSIVE: QB never invoked a subagent within "
                f"{len(trace.turns)} turn(s); rule was not exercised. "
                f"tool_call_sequence={trace.tool_call_sequence}"
            ),
        }

    failures = []
    for idx, call in enumerate(subagent_calls):
        hits = _count_marker_hits(call["prompt"])
        if hits < MIN_MARKER_HITS:
            tail = call["prompt"][-240:] if len(call["prompt"]) > 240 else call["prompt"]
            failures.append(
                f"call#{idx}(agent={call['agent']}, turn={call['turn']}): "
                f"only {hits}/{len(DIRECTIVE_MARKERS)} markers hit; tail={tail!r}"
            )

    if failures:
        return {
            "passed": False,
            "detail": (
                f"VIOLATION: {len(failures)}/{len(subagent_calls)} subagent prompt(s) "
                f"missing bounded-return directive. {failures[0]}"
            ),
        }

    return {
        "passed": True,
        "detail": (
            f"COMPLIANT: all {len(subagent_calls)} subagent prompt(s) include the "
            f"directive (>= {MIN_MARKER_HITS} markers each)"
        ),
    }


def _count_marker_hits(prompt: str) -> int:
    """Count how many distinctive directive markers appear in a prompt."""
    p = (prompt or "").lower()
    return sum(1 for m in DIRECTIVE_MARKERS if m in p)
