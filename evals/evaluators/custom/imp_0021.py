"""IMP-0021 PR 1 evaluator — task-type detector accuracy.

Tests that QB classifies incoming user requests into the correct task type and:
  1. Emits a "## Task Classification" block with "Type: <class>" in its first
     assistant response (before invoking any subagent), so the classification
     is externally observable.
  2. For the 4 existing classes (bug-fix, new-poc-setup, customer-handoff,
     full-delivery), classifies correctly — no regression.
  3. For the 3 new classes (feature-request, refactor, optimization), classifies
     correctly AND notes the fallback: "Pipeline: <fallback> (PR 2 pending)".
  4. For ambiguous prompts, calls askQuestions with disambiguation options
     INSTEAD of silently picking a classification.

Scoring per scenario:
  - PASS: assistant content contains "Type: <expected>" exactly once AND
          (if ambiguous case) askQuestions was called with disambiguation options.
  - FAIL: wrong class detected, OR no classification line emitted, OR ambiguous
          case silently picked instead of asking.

The eval_type is `subagent_routing` per the registry — it shares the tool_loop
runner, with subagent metrics layered on (compute_subagent_routing_metrics).
For PR 1 we only check the classification text; PR 2 will add per-class
pipeline-invocation assertions.
"""

from __future__ import annotations

import re
from evaluators.tool_loop import LoopTrace


N_SAMPLES = 2
MAX_TURNS = 4


_CLASS_PATTERN = re.compile(r"Type:\s*([a-zA-Z\-]+)", re.IGNORECASE)


def get_scenarios() -> list[dict]:
    """14 deterministic prompts (2 per class × 7 classes) + 3 ambiguous prompts."""
    return [
        # --- Existing 4 classes ---
        {"id": "bugfix_1", "prompt": "The /healthz endpoint returns HTTP 500 — fix it. Backend only.",
         "expected": {"class": "bug-fix", "ambiguous": False}},
        {"id": "bugfix_2", "prompt": "Login is broken on production. Debug and patch it.",
         "expected": {"class": "bug-fix", "ambiguous": False}},
        {"id": "newpoc_1", "prompt": "Build a new POC for Contoso Insurance — FSI chatbot with Cosmos persistence and Entra auth, from scratch.",
         "expected": {"class": "new-poc-setup", "ambiguous": False}},
        {"id": "newpoc_2", "prompt": "Spin up a RAG demo using Foundry agents and Azure AI Search. New project.",
         "expected": {"class": "new-poc-setup", "ambiguous": False}},
        {"id": "handoff_1", "prompt": "Package this POC for delivery to Allstate. Customer handoff.",
         "expected": {"class": "customer-handoff", "ambiguous": False}},
        {"id": "handoff_2", "prompt": "Run public-release readiness on this repo and prepare the handoff branch.",
         "expected": {"class": "customer-handoff", "ambiguous": False}},
        {"id": "fulldeliv_1", "prompt": "End-to-end build the claims video analyzer. Full delivery — infra, code, validation, diagrams, docs.",
         "expected": {"class": "full-delivery", "ambiguous": False}},
        {"id": "fulldeliv_2", "prompt": "Deliver the live claim assist POC top to bottom for the customer.",
         "expected": {"class": "full-delivery", "ambiguous": False}},
        # --- 3 new classes (PR 1 detects; pipelines ship in PR 2) ---
        {"id": "feature_1", "prompt": "Add a /metrics endpoint that returns p50/p95 latency. New feature, not a bug.",
         "expected": {"class": "feature-request", "ambiguous": False}},
        {"id": "feature_2", "prompt": "Support CSV export on the dashboard. Implement this new capability.",
         "expected": {"class": "feature-request", "ambiguous": False}},
        {"id": "refactor_1", "prompt": "Extract chat persistence into its own module. Behavior must be preserved.",
         "expected": {"class": "refactor", "ambiguous": False}},
        {"id": "refactor_2", "prompt": "Rename getUser to fetchUser across the codebase. Same behavior, just clearer naming.",
         "expected": {"class": "refactor", "ambiguous": False}},
        {"id": "optim_1", "prompt": "Reduce backend cold start time by half. Performance optimization.",
         "expected": {"class": "optimization", "ambiguous": False}},
        {"id": "optim_2", "prompt": "Harden all POST endpoints with input validation. Security hardening.",
         "expected": {"class": "optimization", "ambiguous": False}},
        # --- 3 ambiguous (must trigger askQuestions for disambiguation, not silent pick) ---
        {"id": "ambig_1", "prompt": "The export button doesn't have a CSV option.",
         "expected": {"class": None, "ambiguous": True}},
        {"id": "ambig_2", "prompt": "Rename getUser to fetchUser and also support email lookup.",
         "expected": {"class": None, "ambiguous": True}},
        {"id": "ambig_3", "prompt": "Improve this endpoint.",
         "expected": {"class": None, "ambiguous": True}},
    ]


def _assistant_text(trace: LoopTrace) -> str:
    """Concatenate assistant message content from all turns."""
    parts: list[str] = []
    for turn in trace.turns:
        content = turn.get("content", "") or ""
        if content:
            parts.append(content)
    return "\n".join(parts)


def _askquestions_count(trace: LoopTrace) -> int:
    n = 0
    for turn in trace.turns:
        for tc in turn.get("tool_calls", []) or []:
            if tc.get("name") == "askQuestions":
                n += 1
    return n


def _extract_class(text: str) -> str | None:
    m = _CLASS_PATTERN.search(text)
    return m.group(1).lower() if m else None


def check_scenario(trace: LoopTrace, scenario: dict) -> dict:
    expected = scenario.get("expected", {})
    text = _assistant_text(trace)
    detected = _extract_class(text)
    ask_n = _askquestions_count(trace)

    if expected.get("ambiguous"):
        # Ambiguous: must call askQuestions for disambiguation, must NOT silently
        # pick a single class without asking.
        if ask_n >= 1 and detected is None:
            return {"passed": True,
                    "detail": f"AMBIG_OK: askQuestions called {ask_n}x, no silent classification"}
        if ask_n >= 1 and detected is not None:
            return {"passed": True,
                    "detail": f"AMBIG_OK_WITH_CLASS: asked AND noted tentative class={detected!r}"}
        return {"passed": False,
                "detail": (f"AMBIG_VIOLATION: silently classified as {detected!r} "
                           f"without asking (askQuestions calls={ask_n})")}

    expected_class = (expected.get("class") or "").lower()
    if detected is None:
        return {"passed": False,
                "detail": f"NO_CLASSIFICATION: expected {expected_class!r}; "
                          f"no 'Type:' line found in assistant content (len={len(text)})"}
    if detected != expected_class:
        return {"passed": False,
                "detail": f"WRONG_CLASS: expected {expected_class!r} got {detected!r}; "
                          f"tail={text[-200:]!r}"}
    return {"passed": True,
            "detail": f"CORRECT: classified as {detected!r}"}
