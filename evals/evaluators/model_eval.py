"""
Model comparison evaluator — runs the same agent prompts across multiple Foundry
model deployments using the Foundry Evaluation API, then compares quality scores.

Uses `client.evals.create()` + `client.evals.runs.create()` with
`azure_ai_target_completions` data source. Each model gets its own eval run
with identical test data + agent system prompt, then results are compared
using `evaluation_comparison_create` for statistical significance.

Config is loaded from config.yaml under the `model_compare` key.
Auth: DefaultAzureCredential (Entra ID — FDPO compliant, no API keys).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

logger = logging.getLogger(__name__)

_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"


@dataclass
class ModelConfig:
    """A model deployment available for comparison."""
    deployment: str
    display_name: Optional[str] = None

    @property
    def name(self) -> str:
        return self.display_name or self.deployment


@dataclass
class RunResult:
    """Result of a single model's eval run."""
    model: str
    run_id: str
    status: str
    scores: dict[str, float] = field(default_factory=dict)
    per_item: list[dict] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class ComparisonResult:
    """Statistical comparison between baseline and treatment models."""
    baseline_model: str
    comparisons: list[dict] = field(default_factory=list)


@dataclass
class ModelCompareReport:
    """Full model comparison report."""
    agent: str
    eval_id: str
    dataset_size: int
    evaluators: list[str]
    models: list[str]
    runs: list[RunResult] = field(default_factory=list)
    comparison: Optional[ComparisonResult] = None
    recommendation: Optional[str] = None


def load_model_compare_config(config: dict) -> dict:
    """Load model comparison config from eval harness config dict."""
    mc = config.get("model_compare", {})
    if not mc:
        raise ValueError(
            "model_compare config missing. Add to config.yaml:\n"
            "  model_compare:\n"
            "    models:\n"
            "      - deployment: gpt-5.4\n"
            "      - deployment: gpt-4.1-mini\n"
            "    evaluators:\n"
            "      - builtin.coherence\n"
            "      - builtin.fluency\n"
            "      - builtin.task_adherence\n"
        )
    return mc


def get_models(config: dict) -> list[ModelConfig]:
    """Parse model configs from config dict."""
    mc = config.get("model_compare", {})
    models = []
    for m in mc.get("models", []):
        if isinstance(m, str):
            models.append(ModelConfig(deployment=m))
        elif isinstance(m, dict):
            models.append(ModelConfig(
                deployment=m["deployment"],
                display_name=m.get("display_name"),
            ))
    return models


def get_evaluators(config: dict) -> list[str]:
    """Get evaluator names from config."""
    mc = config.get("model_compare", {})
    return mc.get("evaluators", [
        "builtin.coherence",
        "builtin.fluency",
        "builtin.task_adherence",
        "builtin.response_completeness",
        "builtin.intent_resolution",
    ])


def get_judge_deployment(config: dict) -> str:
    """Get the model deployment used as the LLM judge for evaluators."""
    mc = config.get("model_compare", {})
    judge = mc.get("judge_deployment")
    if judge:
        return judge
    # Fall back to foundry config deployment
    fc = config.get("foundry", {})
    return fc.get("deployment", "gpt-5.4")


def get_project_endpoint(config: dict) -> str:
    """Get the Foundry project endpoint."""
    mc = config.get("model_compare", {})
    endpoint = mc.get("project_endpoint")
    if endpoint:
        return endpoint
    # Construct from foundry config
    fc = config.get("foundry", {})
    base = fc.get("endpoint", "").rstrip("/")
    project = mc.get("project", "eval-harness")
    if base:
        # Convert OpenAI endpoint to services endpoint
        account = base.replace("https://", "").replace(".openai.azure.com", "")
        return f"https://{account}.services.ai.azure.com/api/projects/{project}"
    raise ValueError("Cannot determine project endpoint. Set model_compare.project_endpoint in config.yaml")


def create_eval_client(project_endpoint: str):
    """Create an authenticated client for the OpenAI Evals API.
    
    Uses the Azure OpenAI endpoint (*.openai.azure.com), not the 
    Foundry project services endpoint, since evals go through the OpenAI API path.
    """
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, _TOKEN_SCOPE)

    # Convert project endpoint to OpenAI endpoint
    # From: https://{account}.services.ai.azure.com/api/projects/{project}
    # To: https://{account}.openai.azure.com/
    account = project_endpoint.split("//")[1].split(".")[0]
    openai_endpoint = f"https://{account}.openai.azure.com/"

    return AzureOpenAI(
        azure_endpoint=openai_endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2025-04-01-preview",
    )


def build_testing_criteria(
    evaluator_names: list[str],
    judge_deployment: str,
) -> list[dict]:
    """Build testing_criteria using OpenAI Evals API label_model type.
    
    The OpenAI SDK evals API uses label_model for model-as-judge evaluation.
    We define custom grading prompts that mirror Foundry's built-in evaluators.
    """
    # Grading prompts for each evaluator dimension
    grading_prompts = {
        "coherence": (
            "You are an expert evaluator. Rate the coherence of the following response "
            "to the given query. Coherence measures whether the response is well-organized, "
            "logically structured, and flows naturally.\n\n"
            "Query: {{item.query}}\n\nResponse: {{sample.output_text}}\n\n"
            "Rate on a scale of 1-5 where 1=incoherent, 2=poor, 3=acceptable, 4=good, 5=excellent.\n"
            "Respond with ONLY the number."
        ),
        "fluency": (
            "You are an expert evaluator. Rate the fluency of the following response. "
            "Fluency measures whether the text is grammatically correct, well-written, "
            "and reads naturally without awkward phrasing.\n\n"
            "Response: {{sample.output_text}}\n\n"
            "Rate on a scale of 1-5 where 1=not fluent, 2=poor, 3=acceptable, 4=good, 5=excellent.\n"
            "Respond with ONLY the number."
        ),
        "task_adherence": (
            "You are an expert evaluator. Rate how well the following response adheres to "
            "the task described in the query. Task adherence measures whether the response "
            "actually addresses what was asked, follows instructions, and completes the task.\n\n"
            "Query: {{item.query}}\n\nResponse: {{sample.output_text}}\n\n"
            "Rate on a scale of 1-5 where 1=ignores task, 2=poor, 3=partially addresses, 4=good, 5=fully addresses.\n"
            "Respond with ONLY the number."
        ),
        "response_completeness": (
            "You are an expert evaluator. Rate the completeness of the following response "
            "to the given query. Completeness measures whether all aspects of the query "
            "are addressed and no important information is missing.\n\n"
            "Query: {{item.query}}\n\nResponse: {{sample.output_text}}\n\n"
            "Rate on a scale of 1-5 where 1=incomplete, 2=mostly missing, 3=partial, 4=mostly complete, 5=fully complete.\n"
            "Respond with ONLY the number."
        ),
        "intent_resolution": (
            "You are an expert evaluator. Rate how well the following response resolves "
            "the user's intent. Intent resolution measures whether the response correctly "
            "understood what the user wanted and provided an appropriate answer or action.\n\n"
            "Query: {{item.query}}\n\nResponse: {{sample.output_text}}\n\n"
            "Rate on a scale of 1-5 where 1=misunderstood, 2=poor, 3=partially resolved, 4=good, 5=fully resolved.\n"
            "Respond with ONLY the number."
        ),
    }

    criteria = []
    for name in evaluator_names:
        short_name = name.replace("builtin.", "")
        prompt_text = grading_prompts.get(short_name)
        if not prompt_text:
            logger.warning("No grading prompt for evaluator %s, skipping", name)
            continue

        criteria.append({
            "type": "label_model",
            "name": short_name,
            "model": judge_deployment,
            "input": [
                {
                    "role": "system",
                    "content": "You are a strict quality evaluator. Respond with ONLY a single number 1-5.",
                },
                {
                    "role": "user",
                    "content": prompt_text,
                },
            ],
            "labels": ["1", "2", "3", "4", "5"],
            "passing_labels": ["4", "5"],
        })

    return criteria


def build_input_messages(system_prompt: str) -> dict:
    """Build input_messages template that injects the agent system prompt."""
    return {
        "type": "template",
        "template": [
            {
                "type": "message",
                "role": "developer",
                "content": {
                    "type": "input_text",
                    "text": system_prompt,
                },
            },
            {
                "type": "message",
                "role": "user",
                "content": {
                    "type": "input_text",
                    "text": "{{item.query}}",
                },
            },
        ],
    }


def upload_dataset(client: AzureOpenAI, dataset_path: Path) -> str:
    """Upload a JSONL dataset file to Foundry and return the file ID."""
    with open(dataset_path, "rb") as f:
        file_obj = client.files.create(file=f, purpose="evals")
    logger.info("Uploaded dataset %s → file ID: %s", dataset_path.name, file_obj.id)
    return file_obj.id


def create_eval(
    client: AzureOpenAI,
    name: str,
    testing_criteria: list[dict],
) -> str:
    """Create an evaluation definition and return its ID."""
    eval_obj = client.evals.create(
        name=name,
        data_source_config={
            "type": "custom",
            "item_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
            "include_sample_schema": True,
        },
        testing_criteria=testing_criteria,
    )
    logger.info("Created eval: %s (ID: %s)", name, eval_obj.id)
    return eval_obj.id


def create_model_run(
    client: AzureOpenAI,
    eval_id: str,
    run_name: str,
    file_id: str,
    model_deployment: str,
    input_messages: dict,
    max_tokens: int = 2048,
) -> str:
    """Create an eval run targeting a specific model deployment."""
    data_source = {
        "type": "completions",
        "source": {
            "type": "file_id",
            "id": file_id,
        },
        "input_messages": input_messages,
        "model": model_deployment,
        "sampling_params": {
            "max_completions_tokens": max_tokens,
            "temperature": 0.3,
        },
    }

    run = client.evals.runs.create(
        eval_id=eval_id,
        name=run_name,
        data_source=data_source,
    )
    logger.info("Created run: %s (ID: %s) targeting %s", run_name, run.id, model_deployment)
    return run.id


def poll_run(
    client: AzureOpenAI,
    eval_id: str,
    run_id: str,
    poll_interval: int = 10,
    timeout: int = 600,
) -> dict:
    """Poll an eval run until completion. Returns the run object."""
    elapsed = 0
    while elapsed < timeout:
        run = client.evals.runs.retrieve(eval_id=eval_id, run_id=run_id)
        status = run.status
        if status in ("completed", "failed", "cancelled"):
            return run
        time.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(f"Run {run_id} did not complete within {timeout}s")


def extract_run_scores(run) -> dict[str, float]:
    """Extract per-evaluator pass rates from a completed eval run.
    
    The OpenAI evals API returns per_testing_criteria_results with passed/failed
    counts per evaluator. Criteria names have UUID suffixes like 
    'coherence-9543a9ad-...'. We strip the UUID to get the clean evaluator name.
    """
    scores = {}
    if hasattr(run, "per_testing_criteria_results") and run.per_testing_criteria_results:
        for cr in run.per_testing_criteria_results:
            # Handle both dict and object access
            if isinstance(cr, dict):
                raw_name = cr.get("testing_criteria", "unknown")
                passed = cr.get("passed", 0)
                failed = cr.get("failed", 0)
            else:
                raw_name = getattr(cr, "testing_criteria", "unknown")
                passed = getattr(cr, "passed", 0)
                failed = getattr(cr, "failed", 0)
            
            # Strip UUID suffix: "coherence-9543a9ad-4571-..." → "coherence"
            # Pattern: name-{8hex}-{4hex}-{4hex}-{4hex}-{12hex}
            parts = raw_name.split("-")
            # Find where the UUID starts (8-char hex segment)
            clean_name = raw_name
            for i, part in enumerate(parts):
                if len(part) == 8 and all(c in "0123456789abcdef" for c in part):
                    clean_name = "-".join(parts[:i])
                    break
            
            total = passed + failed
            if total > 0:
                # Store as pass rate (0.0 to 1.0) — percentage rated 4 or 5
                scores[clean_name] = round(passed / total, 2)
    
    return scores


def run_model_comparison(
    config: dict,
    agent_name: str,
    agent_system_prompt: str,
    dataset_path: Path,
    models: list[ModelConfig] | None = None,
    evaluators: list[str] | None = None,
    on_status=None,
) -> ModelCompareReport:
    """
    Run a full model comparison pipeline:
    1. Upload dataset
    2. Create eval with testing criteria
    3. Create a run per model
    4. Poll all runs to completion
    5. Extract and compare scores

    on_status: optional callback(msg: str) for progress updates.
    """
    def status(msg: str):
        if on_status:
            on_status(msg)
        logger.info(msg)

    project_endpoint = get_project_endpoint(config)
    judge_deployment = get_judge_deployment(config)
    models = models or get_models(config)
    evaluators = evaluators or get_evaluators(config)

    if not models:
        raise ValueError("No models configured for comparison")

    status(f"Project: {project_endpoint}")
    status(f"Judge model: {judge_deployment}")
    status(f"Models to compare: {[m.name for m in models]}")
    status(f"Evaluators: {evaluators}")

    # Create client
    client = create_eval_client(project_endpoint)

    # Count dataset items
    with open(dataset_path) as f:
        dataset_size = sum(1 for line in f if line.strip())

    status(f"Dataset: {dataset_path.name} ({dataset_size} items)")

    # Upload dataset
    status("Uploading dataset...")
    file_id = upload_dataset(client, dataset_path)

    # Build testing criteria
    testing_criteria = build_testing_criteria(evaluators, judge_deployment)

    # Create eval definition
    eval_name = f"model-compare-{agent_name}"
    status(f"Creating eval: {eval_name}")
    eval_id = create_eval(client, eval_name, testing_criteria)

    # Build input messages with agent system prompt
    input_messages = build_input_messages(agent_system_prompt)

    # Create runs for each model
    run_ids: dict[str, str] = {}
    for model in models:
        run_name = f"{agent_name}-{model.deployment}"
        status(f"Creating run: {run_name}")
        run_id = create_model_run(
            client, eval_id, run_name, file_id,
            model.deployment, input_messages,
        )
        run_ids[model.deployment] = run_id

    # Poll all runs
    status("Polling runs for completion...")
    run_results: list[RunResult] = []
    for model in models:
        deployment = model.deployment
        run_id = run_ids[deployment]
        status(f"  Waiting for {deployment}...")
        try:
            run = poll_run(client, eval_id, run_id)
            scores = extract_run_scores(run)
            run_results.append(RunResult(
                model=deployment,
                run_id=run_id,
                status=run.status,
                scores=scores,
            ))
            status(f"  {deployment}: {run.status} — scores: {scores}")
        except Exception as e:
            run_results.append(RunResult(
                model=deployment,
                run_id=run_id,
                status="error",
                error=str(e),
            ))
            status(f"  {deployment}: ERROR — {e}")

    # Build report
    report = ModelCompareReport(
        agent=agent_name,
        eval_id=eval_id,
        dataset_size=dataset_size,
        evaluators=evaluators,
        models=[m.name for m in models],
        runs=run_results,
    )

    # Generate recommendation
    report.recommendation = _generate_recommendation(run_results, evaluators)

    return report


def _generate_recommendation(runs: list[RunResult], evaluators: list[str]) -> str:
    """Generate a plain-text recommendation from comparison results."""
    successful = [r for r in runs if r.status == "completed" and r.scores]
    if len(successful) < 2:
        return "Insufficient data — need at least 2 successful runs to compare."

    # Find best model per evaluator (highest pass rate)
    best_per_eval: dict[str, tuple[str, float]] = {}
    for eval_name in evaluators:
        short_name = eval_name.replace("builtin.", "")
        best_model = None
        best_score = -1.0
        for run in successful:
            score = run.scores.get(short_name, -1.0)
            if score > best_score:
                best_score = score
                best_model = run.model
        if best_model and best_score >= 0:
            best_per_eval[short_name] = (best_model, best_score)

    lines = ["Model comparison summary (pass rate = % of responses rated 4-5 by judge):"]
    for eval_name, (model, score) in best_per_eval.items():
        lines.append(f"  Best {eval_name}: {model} ({int(score*100)}%)")

    # Overall winner
    from collections import Counter
    wins = Counter(model for model, _ in best_per_eval.values())
    overall_winner = wins.most_common(1)[0] if wins else None
    if overall_winner:
        lines.append(f"\nOverall best: {overall_winner[0]} (won {overall_winner[1]}/{len(best_per_eval)} evaluators)")

    # Check for close scores (within 10%) where cheaper model could substitute
    close_calls = []
    for eval_name, (best_model, best_score) in best_per_eval.items():
        for run in successful:
            if run.model != best_model:
                other_score = run.scores.get(eval_name, -1.0)
                if other_score >= 0 and (best_score - other_score) <= 0.10:
                    close_calls.append((eval_name, run.model, other_score, best_model, best_score))

    if close_calls:
        lines.append("\nClose calls (within 10% — potential drop-in replacements):")
        for eval_name, alt_model, alt_score, best_model, best_score in close_calls:
            delta = int((best_score - alt_score) * 100)
            lines.append(f"  {eval_name}: {alt_model} ({int(alt_score*100)}%) vs {best_model} ({int(best_score*100)}%) — delta {delta}pp")

    # Identify if cheaper model is viable
    model_names = [r.model for r in successful]
    if any("mini" in m.lower() for m in model_names):
        mini_models = [r for r in successful if "mini" in r.model.lower()]
        full_models = [r for r in successful if "mini" not in r.model.lower()]
        if mini_models and full_models:
            mini = mini_models[0]
            full = full_models[0]
            avg_mini = sum(mini.scores.values()) / len(mini.scores) if mini.scores else 0
            avg_full = sum(full.scores.values()) / len(full.scores) if full.scores else 0
            if avg_mini >= 0.7 and (avg_full - avg_mini) <= 0.15:
                lines.append(f"\n✅ RECOMMENDATION: {mini.model} is a viable drop-in replacement "
                           f"(avg {int(avg_mini*100)}% vs {int(avg_full*100)}%). "
                           f"Consider switching for cost/speed savings.")
            elif avg_mini < 0.5:
                lines.append(f"\n❌ RECOMMENDATION: {mini.model} quality too low "
                           f"(avg {int(avg_mini*100)}% vs {int(avg_full*100)}%). "
                           f"Stick with {full.model}.")
            else:
                lines.append(f"\n⚠️  RECOMMENDATION: {mini.model} shows mixed results "
                           f"(avg {int(avg_mini*100)}% vs {int(avg_full*100)}%). "
                           f"Test on real tasks before switching.")

    return "\n".join(lines)


def serialize_report(report: ModelCompareReport) -> dict:
    """Serialize a ModelCompareReport to a JSON-serializable dict."""
    return {
        "agent": report.agent,
        "eval_id": report.eval_id,
        "dataset_size": report.dataset_size,
        "evaluators": report.evaluators,
        "models": report.models,
        "runs": [
            {
                "model": r.model,
                "run_id": r.run_id,
                "status": r.status,
                "scores": r.scores,
                "error": r.error,
            }
            for r in report.runs
        ],
        "recommendation": report.recommendation,
    }
