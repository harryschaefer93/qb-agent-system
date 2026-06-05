"""
Quality evaluator — scores agent outputs using Azure AI Foundry evaluator APIs.

Wraps the azure-ai-evaluation SDK to call built-in evaluators (fluency,
coherence, task adherence, groundedness, safety) against agent responses.
Falls back to local heuristic scoring when Foundry is not configured.

Optionally supports custom rubric scoring via ``evaluators.rubric`` with
calibration gating via ``evaluators.calibration``: when ``rubric_path`` is
supplied to :func:`evaluate_with_foundry`, an LLM judge scores the response
against the rubric criteria, and an optional ``calibration_path`` gates that
scoring on a minimum judge/human agreement rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class QualityResult:
    """Result of a quality evaluation for a single response."""
    agent: str
    prompt: str
    evaluator: str
    score: float  # 1-5 scale for most evaluators
    passed: bool
    details: Optional[str] = None


@dataclass
class QualityReport:
    """Aggregate quality report for an agent."""
    agent: str
    total_evals: int
    results: list[QualityResult] = field(default_factory=list)
    averages: dict[str, float] = field(default_factory=dict)


def evaluate_with_foundry(
    agent_name: str,
    prompt: str,
    response: str,
    evaluators: list[str],
    endpoint: str,
    deployment: str,
    ground_truth: Optional[str] = None,
    rubric_path: Optional[Path] = None,
    calibration_path: Optional[Path] = None,
    calibration_min_agreement: float = 0.80,
    rubric_judge_client=None,
) -> list[QualityResult]:
    """
    Score a response using Azure AI Foundry evaluator APIs.

    Requires azure-ai-evaluation SDK and configured Foundry endpoint.
    Install with: pip install agent-evals[foundry]

    Optional rubric scoring:
        If ``rubric_path`` is provided, an LLM judge also scores the response
        against the rubric criteria using ``evaluators.rubric``. When
        ``calibration_path`` is also provided, a calibration run (judge vs.
        human-labelled examples) gates the scoring: if the agreement rate
        falls below ``calibration_min_agreement`` (default 0.80), only a
        single ``rubric_calibration`` failure result is appended and rubric
        scoring is skipped. Pass ``rubric_judge_client`` to reuse an existing
        ``AzureOpenAI`` client; otherwise one is built from ``endpoint`` and
        ``deployment`` via ``evaluators.foundry_client``.
    """
    results = []

    try:
        from azure.ai.evaluation import (
            FluencyEvaluator,
            CoherenceEvaluator,
            RelevanceEvaluator,
            GroundednessEvaluator,
        )
        from azure.ai.evaluation import AzureOpenAIModelConfiguration

        model_config = AzureOpenAIModelConfiguration(
            azure_endpoint=endpoint,
            azure_deployment=deployment,
        )

        evaluator_map = {
            "fluency": FluencyEvaluator(model_config=model_config),
            "coherence": CoherenceEvaluator(model_config=model_config),
            "relevance": RelevanceEvaluator(model_config=model_config),
            "groundedness": GroundednessEvaluator(model_config=model_config),
        }

        for eval_name in evaluators:
            if eval_name in evaluator_map:
                evaluator = evaluator_map[eval_name]
                eval_input = {"query": prompt, "response": response}
                if ground_truth and eval_name == "groundedness":
                    eval_input["context"] = ground_truth

                result = evaluator(**eval_input)
                score = result.get(f"gpt_{eval_name}", result.get(eval_name, 0))
                results.append(QualityResult(
                    agent=agent_name,
                    prompt=prompt,
                    evaluator=eval_name,
                    score=float(score),
                    passed=float(score) >= 4.0,
                    details=str(result),
                ))

    except ImportError:
        # Fall back to local heuristic scoring
        for eval_name in evaluators:
            score = _heuristic_score(eval_name, prompt, response)
            results.append(QualityResult(
                agent=agent_name,
                prompt=prompt,
                evaluator=f"{eval_name}_heuristic",
                score=score,
                passed=score >= 3.5,
                details="Heuristic scoring (Foundry SDK not installed)",
            ))

    if rubric_path is not None:
        results.extend(_score_with_rubric(
            agent_name=agent_name,
            prompt=prompt,
            response=response,
            endpoint=endpoint,
            deployment=deployment,
            rubric_path=rubric_path,
            calibration_path=calibration_path,
            calibration_min_agreement=calibration_min_agreement,
            rubric_judge_client=rubric_judge_client,
        ))

    return results


def _score_with_rubric(
    agent_name: str,
    prompt: str,
    response: str,
    endpoint: str,
    deployment: str,
    rubric_path: Path,
    calibration_path: Optional[Path],
    calibration_min_agreement: float,
    rubric_judge_client,
) -> list[QualityResult]:
    """Score one (prompt, response) pair against a rubric, with optional calibration gating.

    Lazy imports keep the rubric/calibration/foundry-client dependencies
    optional so the module still loads in environments without the Foundry SDK.
    """
    from evaluators.rubric import (
        load_rubric,
        evaluate_with_rubric,
    )

    rubric = load_rubric(rubric_path)

    client = rubric_judge_client
    if client is None:
        from evaluators.foundry_client import (
            create_foundry_client,
            load_foundry_config,
        )
        cfg = load_foundry_config({
            "foundry": {"endpoint": endpoint, "deployment": deployment}
        })
        client = create_foundry_client(cfg)

    rubric_results: list[QualityResult] = []

    if calibration_path is not None:
        from evaluators.calibration import (
            load_calibration_set,
            run_calibration,
        )
        examples = load_calibration_set(calibration_path)
        report = run_calibration(
            rubric, examples, client, deployment,
            min_agreement=calibration_min_agreement,
        )
        if not report.passed:
            rubric_results.append(QualityResult(
                agent=agent_name,
                prompt=prompt,
                evaluator="rubric_calibration",
                score=0.0,
                passed=False,
                details=(
                    f"Calibration failed: agreement "
                    f"{report.agreement_rate:.0%} < "
                    f"{calibration_min_agreement:.0%}"
                ),
            ))
            return rubric_results

    rubric_result = evaluate_with_rubric(
        prompt, response, rubric, client, deployment,
    )

    rubric_results.append(QualityResult(
        agent=agent_name,
        prompt=prompt,
        evaluator="rubric_overall",
        score=rubric_result.weighted_score,
        passed=rubric_result.passed,
        details=(
            f"Weighted score {rubric_result.weighted_score:.2f} / "
            f"{rubric.overall_pass_threshold:.2f} threshold"
        ),
    ))

    for c in rubric_result.per_criterion:
        rubric_results.append(QualityResult(
            agent=agent_name,
            prompt=prompt,
            evaluator=f"rubric_criterion_{c.name}",
            score=c.score,
            passed=c.score >= 4.0,
            details=(
                f"weight={c.weight:.2f}, weighted={c.weighted:.2f}: "
                f"{c.reasoning[:200]}"
            ),
        ))

    return rubric_results


def evaluate_local(
    agent_name: str,
    prompt: str,
    response: str,
    evaluators: list[str],
) -> list[QualityResult]:
    """
    Score a response using local heuristic evaluators (no API calls).
    Useful for quick iteration without Foundry access.
    """
    results = []
    for eval_name in evaluators:
        score = _heuristic_score(eval_name, prompt, response)
        results.append(QualityResult(
            agent=agent_name,
            prompt=prompt,
            evaluator=f"{eval_name}_local",
            score=score,
            passed=score >= 3.5,
            details="Local heuristic scoring",
        ))
    return results


def compute_quality_summary(results: list[QualityResult]) -> dict:
    """Compute aggregate quality metrics."""
    if not results:
        return {"total": 0, "averages": {}}

    by_evaluator: dict[str, list[float]] = {}
    for r in results:
        # Strip heuristic/local suffixes so they bucket alongside their Foundry
        # equivalents. Rubric entries (rubric_overall, rubric_criterion_*,
        # rubric_calibration) bucket under their own keys as-is so the
        # per-criterion breakdown shows up naturally in the averages.
        base_name = (
            r.evaluator
            .replace("_heuristic", "")
            .replace("_local", "")
        )
        if base_name not in by_evaluator:
            by_evaluator[base_name] = []
        by_evaluator[base_name].append(r.score)

    averages = {
        name: sum(scores) / len(scores)
        for name, scores in by_evaluator.items()
    }

    total_passed = sum(1 for r in results if r.passed)

    rubric_overall_scores = [
        r.score for r in results if r.evaluator == "rubric_overall"
    ]
    has_rubric = bool(rubric_overall_scores)
    calibration_passed = not any(
        r.evaluator == "rubric_calibration" and not r.passed
        for r in results
    )

    summary = {
        "total": len(results),
        "passed": total_passed,
        "pass_rate": total_passed / len(results),
        "averages": averages,
        "rubric_summary": {
            "mean_weighted_score": (
                sum(rubric_overall_scores) / len(rubric_overall_scores)
            ),
            "n_runs": len(rubric_overall_scores),
            "calibration_passed": calibration_passed,
        } if has_rubric else None,
    }
    return summary


# --- Local heuristic scorers ---

def _heuristic_score(evaluator: str, prompt: str, response: str) -> float:
    """Simple heuristic scoring without API calls. Returns 1-5 scale."""
    if not response or not response.strip():
        return 1.0

    scores = {
        "fluency": _score_fluency(response),
        "coherence": _score_coherence(prompt, response),
        "task_adherence": _score_task_adherence(prompt, response),
        "relevance": _score_relevance(prompt, response),
        "groundedness": _score_relevance(prompt, response),  # Simplified
    }

    return scores.get(evaluator, 3.0)


def _score_fluency(response: str) -> float:
    """Heuristic fluency: length, sentence structure, no truncation."""
    words = response.split()
    word_count = len(words)

    if word_count < 10:
        return 2.0
    if word_count < 50:
        score = 3.0
    elif word_count < 500:
        score = 4.5
    else:
        score = 4.0  # Very long responses might be verbose

    # Penalize if response ends mid-sentence
    if response.strip() and response.strip()[-1] not in ".!?`\n":
        score -= 0.5

    return min(max(score, 1.0), 5.0)


def _score_coherence(prompt: str, response: str) -> float:
    """Heuristic coherence: does response relate to prompt?"""
    prompt_words = set(prompt.lower().split())
    response_words = set(response.lower().split())

    # Remove common stop words
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                  "to", "of", "in", "for", "on", "with", "at", "by", "from",
                  "it", "this", "that", "and", "or", "but", "not", "i", "my"}
    prompt_words -= stop_words
    response_words -= stop_words

    if not prompt_words:
        return 3.0

    overlap = len(prompt_words & response_words)
    ratio = overlap / len(prompt_words)

    if ratio > 0.5:
        return 4.5
    elif ratio > 0.3:
        return 4.0
    elif ratio > 0.1:
        return 3.0
    else:
        return 2.0


def _score_task_adherence(prompt: str, response: str) -> float:
    """Heuristic task adherence: does response attempt to fulfill the request?"""
    # Check for action indicators
    action_indicators = ["```", "def ", "class ", "import ", "function ",
                         "step", "1.", "2.", "##", "created", "updated",
                         "deployed", "configured", "installed"]

    indicator_count = sum(1 for ind in action_indicators if ind in response)

    if indicator_count >= 3:
        return 4.5
    elif indicator_count >= 1:
        return 3.5
    elif len(response.split()) > 50:
        return 3.0
    else:
        return 2.0


def _score_relevance(prompt: str, response: str) -> float:
    """Heuristic relevance scoring."""
    return _score_coherence(prompt, response)
