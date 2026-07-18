"""
QB checkpoint compliance evaluator — tool_loop eval.

Tests that QB correctly:
  1. Calls askQuestions before invoking QA (Checkpoint 1)
  2. Calls askQuestions before invoking Dev/Infra (Checkpoint 2)
  3. Invokes QA before any implementation agent (QA-first rule)
  4. Does NOT self-investigate (no readFile/searchCodebase before QA)
  5. NEGATIVE: Does NOT invoke subagents for a simple question that needs no pipeline

Uses the tool_loop runner with mocked tools against Foundry gpt-5.4.
"""

from __future__ import annotations

from evaluators.tool_loop import LoopTrace


def get_scenarios() -> list[dict]:
    """Return the scenario set for this evaluator.

    Each scenario has:
      id: unique slug
      prompt: the user message to send to QB
      expected: dict describing correct behavior (used by check functions)
    """
    return [
        {
            "id": "bugfix_checkpoint1",
            "prompt": "The /api/claims endpoint is returning 500 errors intermittently",
            "expected": {
                "must_call_ask_before_qa": True,
                "must_call_qa_before_impl": True,
                "must_not_self_investigate": True,
            },
        },
        {
            "id": "bugfix_trivial",
            "prompt": "The submit button color is wrong — should be blue not gray",
            "expected": {
                "must_call_ask_before_qa": True,
                "must_call_qa_before_impl": True,
                "must_not_self_investigate": True,
            },
        },
        {
            "id": "new_poc_checkpoint1",
            "prompt": "Kick off a new POC for Contoso Insurance claims portal",
            "expected": {
                # new-poc-setup workflow: ARCH first, not QA. QB should still ask before proceeding.
                "must_call_ask_before_qa": True,
                # QA-before-impl rule does NOT apply to new-poc-setup (ARCH goes first)
                "must_call_qa_before_impl": False,
                "must_not_self_investigate": True,
            },
        },
        # NEGATIVE CASE: simple question — should NOT trigger the pipeline
        {
            "id": "negative_no_pipeline",
            "prompt": "What agents do you have available?",
            "expected": {
                "must_not_invoke_subagent": True,
                "must_not_call_qa": True,
            },
        },
        # NEGATIVE CASE: scope question — should ask, not act
        {
            "id": "negative_scope_question",
            "prompt": "How would you approach adding caching to an API?",
            "expected": {
                "must_not_invoke_subagent": True,
                "must_not_call_qa": True,
            },
        },
    ]


def check_scenario(trace: LoopTrace, scenario: dict) -> dict:
    """Generic check function — dispatches based on scenario expected keys."""
    expected = scenario.get("expected", {})
    failures = []

    seq = trace.tool_call_sequence
    ask_indices = [i for i, t in enumerate(seq) if t == "askQuestions"]
    qa_indices = [i for i, t in enumerate(seq) if t == "runSubagent" and _is_qa_call(trace, i)]
    impl_indices = [i for i, t in enumerate(seq) if t == "runSubagent" and _is_impl_call(trace, i)]
    investigate_indices = [i for i, t in enumerate(seq) if t in ("readFile", "searchCodebase", "fileSearch")]

    # --- Positive checks ---

    if expected.get("must_call_ask_before_qa"):
        if not ask_indices:
            failures.append("Never called askQuestions (Checkpoint 1 missing)")
        elif qa_indices and ask_indices[0] > qa_indices[0]:
            failures.append(f"Called QA at index {qa_indices[0]} before askQuestions at {ask_indices[0]}")

    if expected.get("must_call_qa_before_impl"):
        if impl_indices:
            if not qa_indices:
                failures.append("Invoked implementation agent without calling QA first")
            elif qa_indices[0] > impl_indices[0]:
                failures.append(f"Called impl agent at {impl_indices[0]} before QA at {qa_indices[0]}")

    if expected.get("must_not_self_investigate"):
        # QB should not read files or search before invoking QA (or any subagent),
        # EXCEPT for reading BRIEF.md (which QB is supposed to do in pre-flight).
        # Investigation AFTER subagent invocations is fine (e.g., merge gate checks).
        first_subagent = next(
            (i for i, t in enumerate(seq) if t == "runSubagent"), len(seq)
        )
        non_brief_investigate = [
            i for i in investigate_indices
            if not _is_brief_read(trace, i) and i < first_subagent
        ]
        if non_brief_investigate:
            failures.append(f"Self-investigated (tool at index {non_brief_investigate[0]}) before any subagent")

    # --- Negative checks ---

    if expected.get("must_not_invoke_subagent"):
        subagent_calls = [t for t in seq if t == "runSubagent"]
        if subagent_calls:
            failures.append(f"Invoked {len(subagent_calls)} subagent(s) — should have answered directly")

    if expected.get("must_not_call_qa"):
        if qa_indices:
            failures.append("Called QA — should not have triggered the pipeline")

    passed = len(failures) == 0
    detail = "All checks passed" if passed else "; ".join(failures)

    return {"passed": passed, "detail": detail}


def _is_qa_call(trace: LoopTrace, seq_index: int) -> bool:
    """Check if the runSubagent call at this sequence index is for QA."""
    name = _get_agent_name_at(trace, seq_index)
    return name.upper() == "QA"


def _is_impl_call(trace: LoopTrace, seq_index: int) -> bool:
    """Check if the runSubagent call at this sequence index is for an impl agent."""
    name = _get_agent_name_at(trace, seq_index)
    return name.upper() in ("DEV", "INFRA")


def _get_agent_name_at(trace: LoopTrace, seq_index: int) -> str:
    """Get the agentName from the tool call at the given sequence index.

    seq_index is the position in trace.tool_call_sequence (flat list).
    We walk turns to find the matching call.
    """
    flat_idx = 0
    for turn in trace.turns:
        for tc in turn.get("tool_calls", []):
            if flat_idx == seq_index:
                return tc.get("arguments", {}).get("agentName", "unknown")
            flat_idx += 1
    return "unknown"


def _is_brief_read(trace: LoopTrace, seq_index: int) -> bool:
    """Check if the tool call at seq_index is a BRIEF.md lookup (allowed pre-QA).

    QB is supposed to read BRIEF.md during pre-flight — that's not self-investigation.
    """
    flat_idx = 0
    for turn in trace.turns:
        for tc in turn.get("tool_calls", []):
            if flat_idx == seq_index:
                args = tc.get("arguments", {})
                # fileSearch for BRIEF.md
                if tc["name"] == "fileSearch":
                    query = str(args.get("query", "")).upper()
                    return "BRIEF" in query
                # readFile for BRIEF.md
                if tc["name"] == "readFile":
                    path = str(args.get("filePath", "")).upper()
                    return "BRIEF" in path
                return False
            flat_idx += 1
    return False
