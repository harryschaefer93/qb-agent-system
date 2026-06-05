"""
Foundry agent evaluators — wraps Azure AI Evaluation SDK built-in evaluators
for scoring agent tool-call accuracy, task adherence, and intent resolution.

These evaluators use an LLM judge (via Foundry) to score agent responses,
providing higher-confidence results than regex pattern matching.

Requires: azure-ai-evaluation SDK
Auth: Entra ID (DefaultAzureCredential) — no API keys.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FoundryEvalResult:
    """Result from a single Foundry evaluator for one test case."""
    test_id: str
    evaluator: str
    score: float
    passed: bool
    reason: str = ""
    details: Optional[dict] = None


@dataclass
class FoundryEvalSummary:
    """Aggregate results across all test cases for one evaluator."""
    evaluator: str
    total: int
    passed: int
    pass_rate: float
    avg_score: float
    results: list[FoundryEvalResult] = field(default_factory=list)


def _build_model_config(config: dict) -> dict:
    """Build AzureOpenAIModelConfiguration from eval harness config."""
    from azure.ai.evaluation import AzureOpenAIModelConfiguration

    fc = config.get("foundry", {})
    mc = config.get("model_compare", {})
    # Use judge_deployment if available, otherwise foundry deployment
    deployment = mc.get("judge_deployment", fc.get("deployment", "gpt-5.4"))
    endpoint = fc.get("endpoint", "")

    return AzureOpenAIModelConfiguration(
        azure_endpoint=endpoint,
        azure_deployment=deployment,
    )


def evaluate_tool_call_accuracy(
    test_cases: list[dict],
    tool_responses: list[dict],
    tool_definitions: list[dict],
    config: dict,
    threshold: float = 3.0,
) -> FoundryEvalSummary:
    """
    Score tool call accuracy using Foundry's ToolCallAccuracyEvaluator.

    Args:
        test_cases: List of behavioral test cases with 'id' and 'prompt'.
        tool_responses: List of dicts with 'test_id', 'tool_calls', and 'raw_message'.
        tool_definitions: OpenAI function-calling tool definitions.
        config: Eval harness config dict.
        threshold: Minimum score (1-5) to consider a pass.

    Returns:
        FoundryEvalSummary with per-case and aggregate scores.
    """
    from azure.ai.evaluation import ToolCallAccuracyEvaluator

    model_config = _build_model_config(config)
    evaluator = ToolCallAccuracyEvaluator(
        model_config=model_config,
        threshold=int(threshold),
    )

    results = []
    for tc, tr in zip(test_cases, tool_responses):
        test_id = tc.get("id", "unknown")
        try:
            # Build query as conversation history
            query = [
                {"role": "user", "content": tc["prompt"]},
            ]

            # Build response with tool calls
            response = [tr["raw_message"]] if tr.get("raw_message") else []

            result = evaluator(
                query=query,
                tool_definitions=tool_definitions,
                tool_calls=tr.get("tool_calls", []),
                response=response,
            )

            score = result.get("tool_call_accuracy", 0.0)
            reason = result.get("tool_call_accuracy_reason", "")
            passed = score >= threshold

            results.append(FoundryEvalResult(
                test_id=test_id,
                evaluator="tool_call_accuracy",
                score=score,
                passed=passed,
                reason=reason,
                details=result,
            ))

        except Exception as e:
            logger.warning("ToolCallAccuracy failed for %s: %s", test_id, e)
            results.append(FoundryEvalResult(
                test_id=test_id,
                evaluator="tool_call_accuracy",
                score=0.0,
                passed=False,
                reason=f"Error: {e}",
            ))

    passed = sum(1 for r in results if r.passed)
    avg = sum(r.score for r in results) / len(results) if results else 0.0
    return FoundryEvalSummary(
        evaluator="tool_call_accuracy",
        total=len(results),
        passed=passed,
        pass_rate=passed / len(results) if results else 0.0,
        avg_score=avg,
        results=results,
    )


def evaluate_task_adherence(
    test_cases: list[dict],
    tool_responses: list[dict],
    tool_definitions: list[dict],
    config: dict,
    threshold: float = 4.0,
) -> FoundryEvalSummary:
    """
    Score task adherence using Foundry's TaskAdherenceEvaluator.

    Tests whether the agent's actions align with the user's intent,
    follow rules (checkpoints, delegation), and present information correctly.
    """
    from azure.ai.evaluation import TaskAdherenceEvaluator

    model_config = _build_model_config(config)
    evaluator = TaskAdherenceEvaluator(model_config=model_config)

    results = []
    for tc, tr in zip(test_cases, tool_responses):
        test_id = tc.get("id", "unknown")
        try:
            # Query: system prompt context + user message
            query = [
                {"role": "user", "content": tc["prompt"]},
            ]

            # Response: full assistant message with tool calls
            response = [tr["raw_message"]] if tr.get("raw_message") else [
                {"role": "assistant", "content": tr.get("content", "")}
            ]

            result = evaluator(
                query=query,
                response=response,
                tool_definitions=tool_definitions,
            )

            score = result.get("task_adherence", 0.0)
            reason = result.get("task_adherence_reason", "")
            passed = score >= threshold

            results.append(FoundryEvalResult(
                test_id=test_id,
                evaluator="task_adherence",
                score=score,
                passed=passed,
                reason=reason,
                details=result,
            ))

        except Exception as e:
            logger.warning("TaskAdherence failed for %s: %s", test_id, e)
            results.append(FoundryEvalResult(
                test_id=test_id,
                evaluator="task_adherence",
                score=0.0,
                passed=False,
                reason=f"Error: {e}",
            ))

    passed = sum(1 for r in results if r.passed)
    avg = sum(r.score for r in results) / len(results) if results else 0.0
    return FoundryEvalSummary(
        evaluator="task_adherence",
        total=len(results),
        passed=passed,
        pass_rate=passed / len(results) if results else 0.0,
        avg_score=avg,
        results=results,
    )


def evaluate_intent_resolution(
    test_cases: list[dict],
    tool_responses: list[dict],
    config: dict,
    threshold: float = 4.0,
) -> FoundryEvalSummary:
    """
    Score intent resolution using Foundry's IntentResolutionEvaluator.

    Tests whether the agent correctly identified and resolved the user's intent.
    """
    from azure.ai.evaluation import IntentResolutionEvaluator

    model_config = _build_model_config(config)
    evaluator = IntentResolutionEvaluator(model_config=model_config)

    results = []
    for tc, tr in zip(test_cases, tool_responses):
        test_id = tc.get("id", "unknown")
        try:
            query = tc["prompt"]
            response = [tr["raw_message"]] if tr.get("raw_message") else tr.get("content", "")

            result = evaluator(
                query=query,
                response=response,
            )

            score = result.get("intent_resolution", 0.0)
            reason = result.get("intent_resolution_reason", "")
            passed = score >= threshold

            results.append(FoundryEvalResult(
                test_id=test_id,
                evaluator="intent_resolution",
                score=score,
                passed=passed,
                reason=reason,
                details=result,
            ))

        except Exception as e:
            logger.warning("IntentResolution failed for %s: %s", test_id, e)
            results.append(FoundryEvalResult(
                test_id=test_id,
                evaluator="intent_resolution",
                score=0.0,
                passed=False,
                reason=f"Error: {e}",
            ))

    passed = sum(1 for r in results if r.passed)
    avg = sum(r.score for r in results) / len(results) if results else 0.0
    return FoundryEvalSummary(
        evaluator="intent_resolution",
        total=len(results),
        passed=passed,
        pass_rate=passed / len(results) if results else 0.0,
        avg_score=avg,
        results=results,
    )
