"""
CLI entry point for the agent eval harness.

Usage:
    python -m runner.cli run-all
    python -m runner.cli run-agent poc-scoper
    python -m runner.cli run-routing
    python -m runner.cli compare results/run-001.json results/run-002.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from evaluators.routing import (
    compute_routing_summary,
    evaluate_routing,
    load_agent_profiles,
    load_routing_dataset,
    load_trigger_dataset,
)
from evaluators.structure import (
    evaluate_brief_structure,
    evaluate_qb_output_structure,
)
from evaluators.behavioral import (
    compute_behavioral_summary,
    evaluate_qb_behavior,
    load_behavioral_dataset,
)
from evaluators.foundry_client import (
    create_foundry_client,
    generate_live_response,
    generate_live_response_with_tools,
    load_agent_system_prompt,
    load_foundry_config,
    load_tool_definitions,
)
from evaluators.recommender import (
    generate_recommendations,
    save_recommendations,
)
from evaluators.execution_metrics import (
    from_dict as exec_metrics_from_dict,
    render_three_pillar_summary,
)
from runner.reporter import (
    print_routing_report,
    print_comparison_report,
    print_behavioral_report,
)

console = Console()

# Resolve paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
DATASETS_DIR = PROJECT_ROOT / "datasets"
RESULTS_DIR = PROJECT_ROOT / "results"
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def load_config() -> dict:
    """Load config.yaml."""
    import yaml
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def resolve_agents_dir(config: dict) -> Path:
    """Resolve the agents definition directory from config.

    Supports three forms:
      - Absolute path: used as-is.
      - ``~``-prefixed: expanded via ``expanduser`` (back-compat for old configs).
      - Relative path: resolved against ``PROJECT_ROOT`` (the evals/ directory).
        With the harness co-located inside .copilot/, the default ``../agents/``
        resolves to ``.copilot/agents/``.
    """
    raw = config.get("agents", {}).get("definitions_path", "../agents/")
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = (PROJECT_ROOT / p).resolve()
    return p


def _majority_vote_result(per_run_results: list):
    """Combine N BehavioralResult objects (same test case) into one by per-check majority vote.

    A check passes if it passed in >= ceil(N/2) of the runs. The combined result keeps
    the first run's metadata (test_id, category, prompt) and rebuilds checks/passed counts.
    """
    from evaluators.behavioral import BehavioralResult, BehavioralCheck
    if not per_run_results:
        return None
    if len(per_run_results) == 1:
        return per_run_results[0]

    base = per_run_results[0]
    n = len(per_run_results)
    threshold = (n // 2) + 1  # strict majority

    # Gather check_ids in order from first run
    check_ids = [c.check_id for c in base.checks]
    combined_checks = []
    for cid in check_ids:
        pass_count = 0
        labels = []
        evidences = []
        for r in per_run_results:
            for c in r.checks:
                if c.check_id == cid:
                    if c.passed:
                        pass_count += 1
                    labels.append(c.label)
                    evidences.append(c.evidence)
                    break
        passed = pass_count >= threshold
        combined_checks.append(BehavioralCheck(
            check_id=cid,
            label=labels[0] if labels else cid,
            passed=passed,
            evidence=f"majority {pass_count}/{n} | " + (evidences[0] if evidences else ""),
        ))

    passed_checks = sum(1 for c in combined_checks if c.passed)
    total = len(combined_checks)
    return BehavioralResult(
        test_id=base.test_id,
        category=base.category,
        prompt=base.prompt,
        passed=(passed_checks == total),
        total_checks=total,
        passed_checks=passed_checks,
        checks=combined_checks,
    )


@click.group()
def main():
    """Agent Eval Harness — evaluate your Copilot CLI agents."""
    pass


@main.command("run-routing")
def run_routing():
    """Run routing evaluations only (no API calls needed)."""
    config = load_config()
    agents_dir = resolve_agents_dir(config)

    console.print("\n[bold blue]🎯 Running Routing Evaluations[/bold blue]\n")

    # Load agent profiles from definitions
    console.print(f"  Loading agents from [cyan]{agents_dir}[/cyan]")
    profiles = load_agent_profiles(agents_dir)
    console.print(f"  Found [green]{len(profiles)}[/green] agent profiles\n")

    # Load trigger datasets to enrich profiles
    trigger_datasets = {}
    for agent_dir in DATASETS_DIR.iterdir():
        if agent_dir.is_dir() and agent_dir.name != "routing":
            trigger_file = agent_dir / "triggers.json"
            if trigger_file.exists():
                trigger_datasets[agent_dir.name] = load_trigger_dataset(trigger_file)

    console.print(f"  Loaded [green]{len(trigger_datasets)}[/green] trigger datasets\n")

    # Load and run routing dataset
    routing_path = DATASETS_DIR / "routing" / "routing.json"
    if not routing_path.exists():
        console.print("[red]Error: routing.json not found[/red]")
        sys.exit(1)

    routing_data = load_routing_dataset(routing_path)
    results = evaluate_routing(routing_data, profiles, trigger_datasets)
    summary = compute_routing_summary(results)

    # Print report
    print_routing_report(results, summary, console)

    # Save results
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_path = RESULTS_DIR / f"routing-{run_id}.json"
    RESULTS_DIR.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "run_id": run_id,
            "type": "routing",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "results": [
                {
                    "test_id": r.test_id,
                    "prompt": r.prompt,
                    "expected": r.expected_agent,
                    "matched": r.matched_agent,
                    "passed": r.passed,
                    "scores": r.scores,
                    "false_positives": r.false_positives,
                }
                for r in results
            ],
        }, f, indent=2)

    console.print(f"\n  Results saved to [cyan]{output_path}[/cyan]")


@main.command("run-agent")
@click.argument("agent_name")
def run_agent(agent_name: str):
    """Run all evaluations for a specific agent."""
    config = load_config()
    agents_dir = resolve_agents_dir(config)

    console.print(f"\n[bold blue]🔍 Evaluating Agent: {agent_name}[/bold blue]\n")

    # Check trigger dataset exists
    trigger_path = DATASETS_DIR / agent_name / "triggers.json"
    if not trigger_path.exists():
        console.print(f"[red]No trigger dataset found for {agent_name}[/red]")
        sys.exit(1)

    triggers = load_trigger_dataset(trigger_path)

    # Load all profiles for routing context
    profiles = load_agent_profiles(agents_dir)

    # Load all trigger datasets
    trigger_datasets = {}
    for agent_dir in DATASETS_DIR.iterdir():
        if agent_dir.is_dir() and agent_dir.name != "routing":
            tf = agent_dir / "triggers.json"
            if tf.exists():
                trigger_datasets[agent_dir.name] = load_trigger_dataset(tf)

    # Run trigger eval for this specific agent
    console.print("  [bold]Trigger Evaluation:[/bold]")
    should_trigger = triggers.get("shouldTriggerPrompts", [])
    should_not = triggers.get("shouldNotTriggerPrompts", [])

    # Enrich profiles
    for an, td in trigger_datasets.items():
        if an in profiles:
            profiles[an].trigger_phrases = td.get("shouldTriggerPrompts", [])
            profiles[an].anti_phrases = td.get("shouldNotTriggerPrompts", [])

    from evaluators.routing import score_prompt_agent

    # Test shouldTrigger prompts
    trigger_pass = 0
    trigger_total = len(should_trigger)
    for prompt in should_trigger:
        scores = {name: score_prompt_agent(prompt, p) for name, p in profiles.items()}
        best = max(scores, key=scores.get) if scores else ""
        passed = best == agent_name
        if passed:
            trigger_pass += 1
        status = "[green]✓[/green]" if passed else f"[red]✗ → {best}[/red]"
        console.print(f"    {status} {prompt[:60]}...")

    console.print(f"\n  Should trigger: [{'green' if trigger_pass == trigger_total else 'yellow'}]{trigger_pass}/{trigger_total}[/{'green' if trigger_pass == trigger_total else 'yellow'}]")

    # Test shouldNotTrigger prompts
    not_trigger_pass = 0
    not_trigger_total = len(should_not)
    for prompt in should_not:
        scores = {name: score_prompt_agent(prompt, p) for name, p in profiles.items()}
        best = max(scores, key=scores.get) if scores else ""
        passed = best != agent_name
        if passed:
            not_trigger_pass += 1
        status = "[green]✓[/green]" if passed else "[red]✗ (wrongly triggered)[/red]"
        console.print(f"    {status} {prompt[:60]}...")

    console.print(f"\n  Should NOT trigger: [{'green' if not_trigger_pass == not_trigger_total else 'yellow'}]{not_trigger_pass}/{not_trigger_total}[/{'green' if not_trigger_pass == not_trigger_total else 'yellow'}]")

    console.print()


@main.command("run-all")
def run_all():
    """Run all evaluation suites."""
    config = load_config()
    agents_dir = resolve_agents_dir(config)

    console.print("\n[bold blue]🚀 Running Full Evaluation Suite[/bold blue]\n")
    console.print("=" * 60)

    # 1. Routing evals
    console.print("\n[bold]Phase 1: Routing Evaluations[/bold]")
    from click.testing import CliRunner
    runner = CliRunner()
    runner.invoke(run_routing, standalone_mode=False)

    # 2. Per-agent trigger evals
    console.print("\n[bold]Phase 2: Per-Agent Trigger Evaluations[/bold]")
    for agent_dir in sorted(DATASETS_DIR.iterdir()):
        if agent_dir.is_dir() and agent_dir.name != "routing":
            if (agent_dir / "triggers.json").exists():
                console.print(f"\n{'─' * 40}")
                runner.invoke(run_agent, [agent_dir.name], standalone_mode=False)

    console.print("\n" + "=" * 60)
    console.print("[bold green]✅ Full evaluation suite complete[/bold green]\n")


@main.command("run-behavioral")
@click.argument("agent_name", default="qb")
@click.option("--response-dir", type=click.Path(exists=True), default=None,
              help="Directory containing response .txt files named by test case ID")
@click.option("--response-file", type=click.Path(exists=True), default=None,
              help="Single response file to evaluate against all test cases")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show test cases and expected checks without evaluating responses")
@click.option("--live", is_flag=True, default=False,
              help="Generate real model responses via Foundry (Entra auth) instead of using saved files")
@click.option("--save-responses", is_flag=True, default=False,
              help="When using --live, save generated responses to response dir for future use")
@click.option("--runs", type=int, default=1,
              help="When using --live, run each test case N times and pass each check by majority vote (suppresses Foundry stochasticity). Default 1.")
@click.option("--with-tools", is_flag=True, default=False,
              help="When using --live, pass tool definitions so the model produces real tool_calls instead of text narration.")
@click.option("--foundry-eval", is_flag=True, default=False,
              help="After behavioral scoring, also run Foundry LLM-judge evaluators (ToolCallAccuracy, TaskAdherence, IntentResolution).")
def run_behavioral(agent_name: str, response_dir: str | None, response_file: str | None,
                   dry_run: bool, live: bool, save_responses: bool, runs: int,
                   with_tools: bool, foundry_eval: bool):
    """Run behavioral evaluations — test checkpoint compliance.

    Modes:
      --dry-run         List all test cases and expected checks (no responses needed)
      --response-dir    Directory of response .txt files (one per test case, named {test_id}.txt)
      --response-file   Single response file evaluated against all test cases
      --live            Generate real responses from Foundry model (uses Entra auth from config.yaml)
      --live --save-responses   Also save live responses to results/{agent}-responses/ for reuse

    Without any mode flag, runs in dry-run mode automatically.
    """
    console.print(f"\n[bold blue]🧠 Running Behavioral Evaluations: {agent_name}[/bold blue]\n")

    # Load dataset
    dataset_path = DATASETS_DIR / agent_name / "behavioral.json"
    if not dataset_path.exists():
        console.print(f"[red]No behavioral dataset found at {dataset_path}[/red]")
        sys.exit(1)

    dataset = load_behavioral_dataset(dataset_path)
    test_cases = dataset.get("test_cases", [])
    console.print(f"  Loaded [green]{len(test_cases)}[/green] behavioral test cases\n")

    if dry_run or (response_dir is None and response_file is None and not live):
        # Dry run — show test cases
        console.print("  [bold yellow]DRY RUN[/bold yellow] — showing test cases and expected checks:\n")
        for tc in test_cases:
            checks = tc.get("expected_behavior", {})
            active_checks = [k for k, v in checks.items() if v]
            console.print(f"  [cyan]{tc['id']}[/cyan] ({tc['category']})")
            console.print(f"    Prompt: \"{tc['prompt']}\"")
            console.print(f"    Checks: {', '.join(active_checks)}")
            console.print(f"    Note: {tc.get('description', '')}\n")

        console.print("  [dim]To evaluate responses, use --response-dir or --response-file[/dim]")
        console.print("  [dim]Response files should be agent output captured from VS Code.[/dim]")
        console.print(f"  [dim]Example: python -m runner.cli run-behavioral {agent_name} --response-dir results/qb-responses/[/dim]\n")
        return

    # Live mode — generate responses from Foundry
    if live:
        config = load_config()
        try:
            foundry_cfg = load_foundry_config(config)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)

        # Load agent system prompt
        agents_dir = resolve_agents_dir(config)
        agent_files = config.get("agents", {}).get("agent_files", {})
        agent_filename = agent_files.get(agent_name, f"{agent_name}.agent.md")
        agent_def_path = agents_dir / agent_filename

        if not agent_def_path.exists():
            # Try uppercase variant
            for variant in [agent_name.upper(), agent_name.capitalize()]:
                alt = agents_dir / f"{variant}.agent.md"
                if alt.exists():
                    agent_def_path = alt
                    break

        if not agent_def_path.exists():
            console.print(f"[red]Agent definition not found: {agent_def_path}[/red]")
            sys.exit(1)

        system_prompt = load_agent_system_prompt(agent_def_path)
        console.print(f"  Agent prompt: [cyan]{agent_def_path.name}[/cyan] ({len(system_prompt)} chars)")
        console.print(f"  Foundry endpoint: [cyan]{foundry_cfg.endpoint}[/cyan]")
        console.print(f"  Model: [cyan]{foundry_cfg.deployment}[/cyan]")
        console.print(f"  Auth: [cyan]Entra ID (DefaultAzureCredential)[/cyan]")

        # Load tool definitions if --with-tools
        tools = None
        if with_tools:
            tools_path = DATASETS_DIR / agent_name / "tools.json"
            if tools_path.exists():
                tools = load_tool_definitions(tools_path)
                console.print(f"  Tools: [cyan]{len(tools)} definitions loaded[/cyan] (function-calling mode)")
            else:
                console.print(f"  [yellow]⚠ --with-tools: no tools.json at {tools_path}, falling back to text mode[/yellow]")
                with_tools = False
        console.print()

        client = create_foundry_client(foundry_cfg)

        # Prepare save dir if requested
        live_response_dir = None
        if save_responses:
            live_response_dir = RESULTS_DIR / f"{agent_name}-live-responses"
            live_response_dir.mkdir(parents=True, exist_ok=True)
            console.print(f"  Saving responses to: [cyan]{live_response_dir}[/cyan]\n")

        results = []
        tool_responses = []  # Collect structured responses for Foundry evals
        if runs > 1:
            console.print(f"  [bold]Majority-vote mode: {runs} runs per case[/bold]\n")

        for i, tc in enumerate(test_cases, 1):
            console.print(f"  [{i}/{len(test_cases)}] [cyan]{tc['id']}[/cyan] ({tc['category']}) ", end="")
            per_run_results = []
            last_tool_response = None
            try:
                for run_idx in range(runs):
                    if with_tools and tools:
                        tr = generate_live_response_with_tools(
                            client=client,
                            deployment=foundry_cfg.deployment,
                            system_prompt=system_prompt,
                            user_prompt=tc["prompt"],
                            tools=tools,
                        )
                        resp = tr.content
                        # Build full text including tool calls for regex scoring
                        if tr.tool_calls:
                            tool_names = [t["function"]["name"] for t in tr.tool_calls]
                            tool_text = "\n".join(
                                f"[tool_call: {t['function']['name']}({t['function']['arguments']})]"
                                for t in tr.tool_calls
                            )
                            resp = f"{resp}\n{tool_text}" if resp else tool_text
                        last_tool_response = {
                            "test_id": tc["id"],
                            "content": tr.content,
                            "tool_calls": tr.tool_calls,
                            "raw_message": tr.raw_message,
                        }
                        if runs > 1:
                            tc_info = f"r{run_idx+1}={len(resp)}c+{len(tr.tool_calls)}tc"
                            console.print(f"[dim]{tc_info}[/dim] ", end="")
                        else:
                            console.print(f"[green]{len(resp)} chars + {len(tr.tool_calls)} tool calls[/green]", end="")
                    else:
                        resp = generate_live_response(
                            client=client,
                            deployment=foundry_cfg.deployment,
                            system_prompt=system_prompt,
                            user_prompt=tc["prompt"],
                        )
                        last_tool_response = {
                            "test_id": tc["id"],
                            "content": resp,
                            "tool_calls": [],
                            "raw_message": {"role": "assistant", "content": resp},
                        }
                        if runs > 1:
                            console.print(f"[dim]r{run_idx+1}={len(resp)}c[/dim] ", end="")
                        else:
                            console.print(f"[green]{len(resp)} chars[/green]", end="")

                    if live_response_dir:
                        suffix = f".run{run_idx+1}" if runs > 1 else ""
                        resp_path = live_response_dir / f"{tc['id']}{suffix}.txt"
                        resp_path.write_text(resp, encoding="utf-8")
                        # Also save structured response as JSON for tool-call evals
                        if with_tools and last_tool_response:
                            json_path = live_response_dir / f"{tc['id']}{suffix}.json"
                            json_path.write_text(
                                json.dumps(last_tool_response, indent=2),
                                encoding="utf-8",
                            )

                    per_run_results.append(evaluate_qb_behavior(resp, tc))

                if runs > 1:
                    result = _majority_vote_result(per_run_results)
                    label = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
                    console.print(f"-> {label} ({result.passed_checks}/{result.total_checks})")
                else:
                    result = per_run_results[0]
                    console.print()
                results.append(result)
                if last_tool_response:
                    tool_responses.append(last_tool_response)
            except Exception as e:
                console.print(f"[red]ERROR: {e}[/red]")
                continue

        console.print()
    else:
        # File-based mode — load responses from disk
        results = []
        tool_responses = []
        response_text = None

        if response_file:
            with open(response_file, "r", encoding="utf-8") as f:
                response_text = f.read()

        for tc in test_cases:
            if response_dir:
                resp_path = Path(response_dir) / f"{tc['id']}.txt"
                if not resp_path.exists():
                    console.print(f"  [yellow]⚠ Skipping {tc['id']} — no response file at {resp_path}[/yellow]")
                    continue
                with open(resp_path, "r", encoding="utf-8") as f:
                    resp = f.read()
            elif response_text:
                resp = response_text
            else:
                continue

            result = evaluate_qb_behavior(resp, tc)
            results.append(result)

    if not results:
        console.print("  [red]No test cases evaluated. Check your response files.[/red]")
        sys.exit(1)

    summary = compute_behavioral_summary(results)
    print_behavioral_report(results, summary, console)

    # Save results
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_path = RESULTS_DIR / f"behavioral-{agent_name}-{run_id}.json"
    RESULTS_DIR.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "run_id": run_id,
            "type": "behavioral",
            "agent": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_cases": summary.total_cases,
                "passed_cases": summary.passed_cases,
                "pass_rate": summary.pass_rate,
                "by_category": summary.by_category,
                "by_check": summary.by_check,
            },
            "results": [
                {
                    "test_id": r.test_id,
                    "category": r.category,
                    "prompt": r.prompt,
                    "passed": r.passed,
                    "total_checks": r.total_checks,
                    "passed_checks": r.passed_checks,
                    "checks": [
                        {"check_id": c.check_id, "label": c.label, "passed": c.passed, "evidence": c.evidence}
                        for c in r.checks
                    ],
                }
                for r in results
            ],
        }, f, indent=2)

    console.print(f"\n  Results saved to [cyan]{output_path}[/cyan]")

    # --- Foundry LLM-judge evaluators (optional) ---
    if foundry_eval and tool_responses:
        console.print(f"\n[bold blue]🔬 Running Foundry LLM-Judge Evaluators[/bold blue]\n")

        from evaluators.foundry_agents import (
            evaluate_tool_call_accuracy,
            evaluate_task_adherence,
            evaluate_intent_resolution,
        )

        config = load_config()
        tools_path = DATASETS_DIR / agent_name / "tools.json"
        tool_defs = load_tool_definitions(tools_path) if tools_path.exists() else []

        # Match tool_responses to test_cases by test_id
        tr_by_id = {tr["test_id"]: tr for tr in tool_responses}
        matched_cases = []
        matched_responses = []
        for tc in test_cases:
            if tc["id"] in tr_by_id:
                matched_cases.append(tc)
                matched_responses.append(tr_by_id[tc["id"]])

        console.print(f"  Scoring {len(matched_cases)} test cases with Foundry evaluators...\n")

        foundry_results = {}

        # Tool Call Accuracy
        if tool_defs:
            console.print("  [bold]Tool Call Accuracy[/bold] (1-5 scale, threshold: 3.0)")
            tca = evaluate_tool_call_accuracy(matched_cases, matched_responses, tool_defs, config)
            foundry_results["tool_call_accuracy"] = tca
            for r in tca.results:
                icon = "[green]✓[/green]" if r.passed else "[red]✗[/red]"
                console.print(f"    {icon} {r.test_id}: {r.score}/5 — {r.reason[:80]}")
            console.print(f"  → Pass rate: {tca.pass_rate:.0%} | Avg score: {tca.avg_score:.1f}/5\n")

        # Task Adherence
        console.print("  [bold]Task Adherence[/bold] (1-5 scale, threshold: 4.0)")
        ta = evaluate_task_adherence(matched_cases, matched_responses, tool_defs, config)
        foundry_results["task_adherence"] = ta
        for r in ta.results:
            icon = "[green]✓[/green]" if r.passed else "[red]✗[/red]"
            console.print(f"    {icon} {r.test_id}: {r.score}/5 — {r.reason[:80]}")
        console.print(f"  → Pass rate: {ta.pass_rate:.0%} | Avg score: {ta.avg_score:.1f}/5\n")

        # Intent Resolution
        console.print("  [bold]Intent Resolution[/bold] (1-5 scale, threshold: 4.0)")
        ir = evaluate_intent_resolution(matched_cases, matched_responses, config)
        foundry_results["intent_resolution"] = ir
        for r in ir.results:
            icon = "[green]✓[/green]" if r.passed else "[red]✗[/red]"
            console.print(f"    {icon} {r.test_id}: {r.score}/5 — {r.reason[:80]}")
        console.print(f"  → Pass rate: {ir.pass_rate:.0%} | Avg score: {ir.avg_score:.1f}/5\n")

        # Save Foundry eval results alongside behavioral results
        foundry_output_path = RESULTS_DIR / f"foundry-{agent_name}-{run_id}.json"
        with open(foundry_output_path, "w") as f:
            json.dump({
                "run_id": run_id,
                "type": "foundry_eval",
                "agent": agent_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "evaluators": {
                    name: {
                        "total": s.total,
                        "passed": s.passed,
                        "pass_rate": s.pass_rate,
                        "avg_score": s.avg_score,
                        "results": [
                            {"test_id": r.test_id, "score": r.score, "passed": r.passed, "reason": r.reason}
                            for r in s.results
                        ],
                    }
                    for name, s in foundry_results.items()
                },
            }, f, indent=2)
        console.print(f"  Foundry results saved to [cyan]{foundry_output_path}[/cyan]")

    elif foundry_eval and not tool_responses:
        console.print("\n  [yellow]⚠ --foundry-eval requires --live mode to generate responses.[/yellow]")
        console.print("  [dim]Run with: --live --with-tools --foundry-eval[/dim]")


@main.command("compare")
@click.argument("file_a", type=click.Path(exists=True))
@click.argument("file_b", type=click.Path(exists=True))
def compare(file_a: str, file_b: str):
    """Compare two evaluation runs."""
    with open(file_a) as f:
        run_a = json.load(f)
    with open(file_b) as f:
        run_b = json.load(f)

    print_comparison_report(run_a, run_b, console)


@main.command("recommend")
@click.argument("agent_name")
@click.option("--eval-results", type=click.Path(exists=True), default=None,
              help="Path to behavioral eval results JSON. If not provided, uses the latest.")
@click.option("--no-interactive", is_flag=True, default=False,
              help="Skip interactive approve/reject prompts — just print and save.")
def recommend(agent_name: str, eval_results: str | None, no_interactive: bool):
    """Generate recommendations from behavioral eval results.

    Shows each recommendation with its proposed fix, then interactively
    asks you to approve or reject each one (with optional feedback).

    The workflow:
      1. Run behavioral evals:  run-behavioral <agent>
      2. Generate recommendations:  recommend <agent>
      3. Review and approve/reject inline
      4. Approved changes are saved for application
      5. Re-run evals to verify
    """
    config = load_config()
    agents_dir = resolve_agents_dir(config)

    console.print(f"\n[bold blue]💡 Generating Recommendations: {agent_name}[/bold blue]\n")

    # Find eval results
    if eval_results:
        eval_path = Path(eval_results)
    else:
        # Find latest behavioral eval for this agent
        pattern = f"behavioral-{agent_name}-*.json"
        result_files = sorted(RESULTS_DIR.glob(pattern), reverse=True)
        if not result_files:
            console.print(f"[red]No behavioral eval results found for {agent_name}.[/red]")
            console.print(f"[dim]Run: python -m runner.cli run-behavioral {agent_name}[/dim]")
            sys.exit(1)
        eval_path = result_files[0]
        console.print(f"  Using latest eval: [cyan]{eval_path.name}[/cyan]")

    # Find agent definition
    agent_files = config.get("agents", {}).get("agent_files", {})
    agent_filename = agent_files.get(agent_name, f"{agent_name}.agent.md")
    agent_def_path = agents_dir / agent_filename

    if agent_def_path.exists():
        console.print(f"  Agent definition: [cyan]{agent_def_path}[/cyan]")
    else:
        console.print(f"  [yellow]Agent definition not found at {agent_def_path} — recommendations will be generic[/yellow]")
        agent_def_path = None

    # Generate recommendations
    report = generate_recommendations(eval_path, agent_def_path)

    console.print(f"\n  [bold]Summary:[/bold] {report.summary}\n")

    if not report.recommendations:
        console.print("  [green]✅ No recommendations needed — all checks passed![/green]\n")
        return

    # Display each recommendation with full detail
    from rich.panel import Panel
    from rich.text import Text

    for i, rec in enumerate(report.recommendations, 1):
        p_color = {"P0": "red", "P1": "yellow", "P2": "white"}.get(rec.priority, "white")

        # Build recommendation detail
        detail = Text()
        detail.append(f"Priority: ", style="bold")
        detail.append(f"{rec.priority}\n", style=p_color)
        detail.append(f"Category: ", style="bold")
        detail.append(f"{rec.category}\n\n")
        detail.append(f"Issue: ", style="bold")
        detail.append(f"{rec.rationale}\n\n")
        detail.append(f"Failing cases: ", style="bold")
        evidence_str = ", ".join(rec.evidence[:5])
        if len(rec.evidence) > 5:
            evidence_str += f" (+{len(rec.evidence) - 5} more)"
        detail.append(f"{evidence_str}\n\n")
        detail.append(f"Target section: ", style="bold")
        detail.append(f"{rec.agent_file_section}\n\n")
        detail.append("Proposed fix:\n", style="bold green")
        detail.append(f"{rec.proposed_change}\n")

        console.print(Panel(
            detail,
            title=f"[{p_color}]REC-{i:03d}: {rec.title}[/{p_color}]",
            border_style=p_color,
            padding=(1, 2),
        ))

    # Interactive approve/reject
    if no_interactive:
        console.print("  [dim]Skipping interactive review (--no-interactive)[/dim]\n")
    else:
        console.print(f"\n[bold]Review each recommendation:[/bold]")
        console.print(f"[dim]  Format: approve / reject / reject with feedback[/dim]")
        console.print(f"[dim]  Example: 'reject - I think we should add a harder gate instead'[/dim]\n")

        for i, rec in enumerate(report.recommendations, 1):
            p_color = {"P0": "red", "P1": "yellow", "P2": "white"}.get(rec.priority, "white")
            console.print(f"  [{p_color}]REC-{i:03d}[/{p_color}]: {rec.title}")

            response = click.prompt(
                f"    [{i}/{len(report.recommendations)}] approve/reject",
                default="approve",
            )

            response_lower = response.strip().lower()
            if response_lower.startswith("approve") or response_lower.startswith("yes") or response_lower == "y":
                rec.status = "approved"
                console.print(f"    [green]✓ Approved[/green]\n")
            elif response_lower.startswith("reject") or response_lower.startswith("no") or response_lower == "n":
                rec.status = "rejected"
                # Extract feedback after the reject keyword or dash
                feedback = ""
                for sep in [" - ", " — ", ": ", "reject ", "no "]:
                    if sep in response_lower:
                        feedback = response[response_lower.index(sep) + len(sep):].strip()
                        break
                if feedback:
                    rec.rationale += f"\n\n**User feedback:** {feedback}"
                    console.print(f"    [red]✗ Rejected[/red] — feedback: {feedback}\n")
                else:
                    console.print(f"    [red]✗ Rejected[/red]\n")
            else:
                # Treat as feedback on an approval
                rec.status = "approved"
                rec.rationale += f"\n\n**User feedback:** {response}"
                console.print(f"    [green]✓ Approved with feedback[/green]\n")

        # Print summary
        approved = [r for r in report.recommendations if r.status == "approved"]
        rejected = [r for r in report.recommendations if r.status == "rejected"]
        console.print(f"\n  [bold]Decision summary:[/bold]")
        console.print(f"    [green]Approved: {len(approved)}[/green]")
        console.print(f"    [red]Rejected: {len(rejected)}[/red]")

    # Save recommendations
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_base = RESULTS_DIR / f"recommendations-{agent_name}-{run_id}"
    RESULTS_DIR.mkdir(exist_ok=True)
    save_recommendations(report, output_base)

    console.print(f"\n  📄 Report: [cyan]{output_base.with_suffix('.md')}[/cyan]")
    console.print(f"  📊 Machine-readable: [cyan]{output_base.with_suffix('.json')}[/cyan]")

    approved = [r for r in report.recommendations if r.status == "approved"]
    if approved:
        console.print(f"\n  [bold]Next steps:[/bold]")
        console.print(f"    1. Apply {len(approved)} approved change(s) to [cyan]{agent_def_path or 'agent definition'}[/cyan]")
        console.print(f"    2. Re-run: [dim]python -m runner.cli run-behavioral {agent_name} --live[/dim]")
    console.print()


@main.command("model-compare")
@click.argument("agent_name")
@click.option("--models", default=None, help="Comma-separated model deployments to compare (overrides config)")
@click.option("--dataset", type=click.Path(exists=True), default=None,
              help="Path to JSONL dataset. Default: datasets/{agent}/model-eval.jsonl")
@click.option("--evaluators", default=None, help="Comma-separated evaluator names (overrides config)")
@click.option("--dry-run", is_flag=True, default=False, help="Show config and dataset without running")
def model_compare(agent_name: str, models: str | None, dataset: str | None,
                  evaluators: str | None, dry_run: bool):
    """Compare model quality for an agent across Foundry-deployed models.

    Runs the same agent prompts through multiple model deployments using
    Foundry's evaluation API, then compares quality scores (coherence,
    fluency, task adherence, etc.) to find the best model for the job.

    Examples:
      python -m runner.cli model-compare poc-scoper
      python -m runner.cli model-compare qb --models gpt-5.4,gpt-4.1-mini
    """
    from evaluators.model_eval import (
        ModelConfig,
        get_evaluators as get_eval_list,
        get_models as get_model_list,
        get_project_endpoint,
        get_judge_deployment,
        run_model_comparison,
        serialize_report,
    )
    from evaluators.foundry_client import load_agent_system_prompt

    config = load_config()
    agents_dir = resolve_agents_dir(config)

    console.print(f"\n[bold blue]⚖️  Model Comparison: {agent_name}[/bold blue]\n")

    # Resolve dataset
    if dataset:
        dataset_path = Path(dataset)
    else:
        dataset_path = DATASETS_DIR / agent_name / "model-eval.jsonl"

    if not dataset_path.exists():
        console.print(f"[red]No eval dataset found at {dataset_path}[/red]")
        console.print(f"[dim]Create a JSONL file with one {{\"query\": \"...\"}} per line.[/dim]")
        sys.exit(1)

    with open(dataset_path) as f:
        dataset_size = sum(1 for line in f if line.strip())

    console.print(f"  Dataset: [cyan]{dataset_path}[/cyan] ({dataset_size} queries)")

    # Resolve models
    if models:
        model_list = [ModelConfig(deployment=m.strip()) for m in models.split(",")]
    else:
        model_list = get_model_list(config)

    console.print(f"  Models: [cyan]{', '.join(m.name for m in model_list)}[/cyan]")

    # Resolve evaluators
    if evaluators:
        eval_list = [e.strip() for e in evaluators.split(",")]
    else:
        eval_list = get_eval_list(config)

    console.print(f"  Evaluators: [cyan]{', '.join(eval_list)}[/cyan]")

    # Load agent system prompt
    agent_files = config.get("agents", {}).get("agent_files", {})
    agent_filename = agent_files.get(agent_name, f"{agent_name}.agent.md")
    agent_def_path = agents_dir / agent_filename

    # Try common variants
    if not agent_def_path.exists():
        for variant in [f"{agent_name}.md", f"{agent_name}.agent.md"]:
            alt = agents_dir / variant
            if alt.exists():
                agent_def_path = alt
                break

    if not agent_def_path.exists():
        console.print(f"[red]Agent definition not found: {agent_def_path}[/red]")
        console.print(f"[dim]Checked: {agents_dir / agent_filename}[/dim]")
        sys.exit(1)

    system_prompt = load_agent_system_prompt(agent_def_path)
    prompt_preview = system_prompt[:200].replace("\n", " ")
    console.print(f"  Agent prompt: [cyan]{agent_def_path.name}[/cyan] ({len(system_prompt)} chars)")
    console.print(f"  Prompt preview: [dim]{prompt_preview}...[/dim]")

    try:
        project_endpoint = get_project_endpoint(config)
        judge = get_judge_deployment(config)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    console.print(f"  Project: [cyan]{project_endpoint}[/cyan]")
    console.print(f"  Judge model: [cyan]{judge}[/cyan]")
    console.print(f"  Auth: [cyan]Entra ID (DefaultAzureCredential)[/cyan]")

    if dry_run:
        console.print(f"\n  [bold yellow]DRY RUN[/bold yellow] — config validated, no eval runs created.\n")
        console.print(f"  To run for real: [dim]python -m runner.cli model-compare {agent_name}[/dim]\n")
        return

    console.print(f"\n  [bold]Starting evaluation runs...[/bold]\n")

    def on_status(msg: str):
        console.print(f"  {msg}")

    try:
        report = run_model_comparison(
            config=config,
            agent_name=agent_name,
            agent_system_prompt=system_prompt,
            dataset_path=dataset_path,
            models=model_list,
            evaluators=eval_list,
            on_status=on_status,
        )
    except Exception as e:
        console.print(f"\n[red]Error during evaluation: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)

    # Print results table
    console.print(f"\n[bold]Results:[/bold]\n")

    from rich.table import Table as RichTable

    table = RichTable(title=f"Model Comparison — {agent_name}")
    table.add_column("Model", style="cyan")
    table.add_column("Status", style="white")

    # Add evaluator columns
    eval_short_names = [e.replace("builtin.", "") for e in eval_list]
    for name in eval_short_names:
        table.add_column(name.replace("_", " ").title(), justify="center")

    for run in report.runs:
        row = [run.model, run.status]
        for name in eval_short_names:
            score = run.scores.get(name, run.scores.get(f"builtin.{name}"))
            if score is not None:
                pct = int(score * 100)
                # Color code: green >= 80%, yellow >= 50%, red < 50%
                if pct >= 80:
                    row.append(f"[green]{pct}%[/green]")
                elif pct >= 50:
                    row.append(f"[yellow]{pct}%[/yellow]")
                else:
                    row.append(f"[red]{pct}%[/red]")
            else:
                row.append("[dim]—[/dim]")
        table.add_row(*row)

    console.print(table)

    # Print recommendation
    if report.recommendation:
        console.print(f"\n[bold]Recommendation:[/bold]")
        for line in report.recommendation.split("\n"):
            console.print(f"  {line}")

    # Save results
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_path = RESULTS_DIR / f"model-compare-{agent_name}-{run_id}.json"
    RESULTS_DIR.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "run_id": run_id,
            "type": "model-compare",
            "agent": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "report": serialize_report(report),
        }, f, indent=2)

    console.print(f"\n  Results saved to [cyan]{output_path}[/cyan]\n")


def _format_result_line(m: dict, eval_type: str) -> str:
    """Build a one-line summary of a snapshot's metrics for display."""
    if "passed_checks" in m and "total_checks" in m:
        return f"({m['passed_checks']}/{m['total_checks']} checks)"
    if eval_type == "composite" and "weighted_score" in m and "verdict" in m:
        return f"(weighted_score={m['weighted_score']:.2f}, verdict={m['verdict']})"
    if eval_type == "rubric" and "weighted_score" in m:
        return f"(weighted_score={m['weighted_score']:.2f}/5)"
    if eval_type == "execution_metrics":
        return f"(wall_time={m.get('wall_time_ms', 0)}ms, cost_usd=${m.get('cost_usd', 0):.4f})"
    if "overall_pass_rate" in m:  # tool_loop / subagent_routing
        return f"(overall_pass_rate={m['overall_pass_rate']:.2f})"
    if "pass_rate" in m:
        return f"(pass_rate={m['pass_rate']:.2f})"
    return ""


def _verdict_style(snapshot_metrics: dict, eval_type: str) -> tuple[str, str]:
    """Return (text, rich_color) for the result status line."""
    if eval_type == "composite":
        v = snapshot_metrics.get("verdict", "unknown")
        color = {"pass": "green", "partial": "yellow", "fail": "red"}.get(v, "white")
        return v.upper(), color
    if eval_type == "execution_metrics":
        return "CAPTURED", "cyan"
    if eval_type == "rubric":
        passed = snapshot_metrics.get("all_passed") or snapshot_metrics.get("weighted_score", 0) >= 4.0
        return ("PASS", "green") if passed else ("FAIL", "red")
    if snapshot_metrics.get("all_passed"):
        return "PASS", "green"
    return "FAIL", "red"


def _format_raw_result(r: dict) -> tuple[str, str]:
    """Return (icon, label) for a single raw_result row across any eval_type.

    Structural / behavioral rows have {label, passed}; rubric rows have
    {scenario_id, prompt, weighted_score, passed}; tool_loop rows have
    {scenario_id, prompt, mean_pass_rate}; etc. This helper picks the right
    fields without crashing on missing keys.
    """
    passed_val = r.get("passed")
    if passed_val is None:
        # tool_loop: derive from mean_pass_rate
        mpr = r.get("mean_pass_rate")
        if mpr is not None:
            passed_val = mpr >= 1.0
    if passed_val is True:
        icon = "[green]✓[/green]"
    elif passed_val is False:
        icon = "[red]✗[/red]"
    else:
        icon = "[dim]·[/dim]"

    if "label" in r:
        label = r["label"]
    elif "scenario_id" in r:
        score_part = ""
        if "weighted_score" in r:
            score_part = f" (score {r['weighted_score']:.2f})"
        elif "mean_pass_rate" in r:
            score_part = f" (pass_rate {r['mean_pass_rate']:.2f})"
        label = f"{r['scenario_id']}{score_part}"
    elif "check_id" in r:
        label = r["check_id"]
    else:
        label = str(r)[:80]
    return icon, label


@main.command("run-imp")
@click.argument("imp_id")
@click.option("--baseline", "phase", flag_value="baseline", help="Capture a pre-implementation baseline snapshot")
@click.option("--post", "phase", flag_value="post", help="Capture a post-implementation snapshot")
@click.option("--compare", "phase", flag_value="compare", help="Compare baseline vs post snapshots")
@click.option("--full", "phase", flag_value="full", help="Baseline + post + compare (for retroactive backfills)")
def run_imp(imp_id: str, phase: str | None):
    """Run eval snapshots for an IMP improvement.

    Captures baseline (pre-implementation) and post (after change) snapshots,
    then compares them to detect regressions.

    Currently supports eval_type: structural. Tool_loop/behavioral coming in Phase 3.

    Examples:
      python -m runner.cli run-imp IMP-0004 --baseline
      python -m runner.cli run-imp IMP-0004 --post
      python -m runner.cli run-imp IMP-0004 --compare
      python -m runner.cli run-imp IMP-0004 --full
    """
    from runner.imp_runner import (
        capture_snapshot,
        compare_snapshots,
        find_imp_file,
        parse_imp_frontmatter,
    )

    if phase is None:
        console.print("[red]Specify one of: --baseline, --post, --compare, --full[/red]")
        sys.exit(1)

    # Resolve paths
    config = load_config()
    agents_dir = resolve_agents_dir(config)
    baselines_dir = PROJECT_ROOT / "baselines"

    # Resolve the .copilot repo dir (for git SHA) — parent of PROJECT_ROOT (evals/)
    copilot_repo_dir = PROJECT_ROOT.parent

    console.print(f"\n[bold blue]📊 IMP Eval: {imp_id}[/bold blue]\n")

    # Load IMP frontmatter
    try:
        imp_path = find_imp_file(imp_id)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    fm = parse_imp_frontmatter(imp_path)
    console.print(f"  IMP: [cyan]{fm.id}[/cyan] — {fm.title}")
    console.print(f"  Status: [cyan]{fm.status}[/cyan]")
    console.print(f"  Eval type: [cyan]{fm.eval_type}[/cyan]")
    console.print(f"  Eval ID: [cyan]{fm.eval_id or 'none'}[/cyan]")
    console.print(f"  Affects: [cyan]{', '.join(fm.affects)}[/cyan]\n")

    if fm.eval_type == "manual":
        console.print("[yellow]This IMP uses manual evaluation — no automated eval to run.[/yellow]")
        console.print("[dim]Add manual_evidence entries to the IMP file instead.[/dim]")
        sys.exit(0)

    if phase in ("baseline", "full"):
        console.print("[bold]Capturing baseline snapshot...[/bold]")
        try:
            sp, snapshot = capture_snapshot(fm, "baseline", agents_dir, baselines_dir, copilot_repo_dir)
            m = snapshot.metrics
            status_text, status_color = _verdict_style(m, fm.eval_type)
            summary = _format_result_line(m, fm.eval_type)
            console.print(f"  Result: [{status_color}]{status_text}[/{status_color}] {summary}".rstrip())
            if snapshot.raw_results:
                for r in snapshot.raw_results:
                    icon, label = _format_raw_result(r)
                    console.print(f"    {icon} {label}")
            if snapshot.sub_snapshots:
                console.print("    [dim]Sub-evaluators:[/dim]")
                for key, sub in snapshot.sub_snapshots.items():
                    sub_metrics = sub.get('metrics', {})
                    sub_summary = _format_result_line(sub_metrics, key.split(':', 1)[0])
                    console.print(f"      [cyan]{key}[/cyan] {sub_summary}")
            console.print(f"  Saved: [cyan]{sp}[/cyan]\n")
        except (ValueError, NotImplementedError) as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)

    if phase in ("post", "full"):
        console.print("[bold]Capturing post snapshot...[/bold]")
        try:
            sp, snapshot = capture_snapshot(fm, "post", agents_dir, baselines_dir, copilot_repo_dir)
            m = snapshot.metrics
            status_text, status_color = _verdict_style(m, fm.eval_type)
            summary = _format_result_line(m, fm.eval_type)
            console.print(f"  Result: [{status_color}]{status_text}[/{status_color}] {summary}".rstrip())
            if snapshot.raw_results:
                for r in snapshot.raw_results:
                    icon, label = _format_raw_result(r)
                    console.print(f"    {icon} {label}")
            if snapshot.sub_snapshots:
                console.print("    [dim]Sub-evaluators:[/dim]")
                for key, sub in snapshot.sub_snapshots.items():
                    sub_metrics = sub.get('metrics', {})
                    sub_summary = _format_result_line(sub_metrics, key.split(':', 1)[0])
                    console.print(f"      [cyan]{key}[/cyan] {sub_summary}")
            console.print(f"  Saved: [cyan]{sp}[/cyan]\n")
        except (ValueError, NotImplementedError) as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)

    if phase in ("compare", "full"):
        console.print("[bold]Comparing baseline vs post...[/bold]")
        try:
            cmp = compare_snapshots(baselines_dir, imp_id)
            verdict_color = {
                "pass": "green",
                "REGRESSION": "red",
                "PARTIAL": "yellow",
            }.get(cmp["verdict"], "white")

            console.print(f"  Verdict: [{verdict_color}]{cmp['verdict']}[/{verdict_color}]")
            console.print(f"  Baseline commit: [cyan]{cmp['baseline_commit']}[/cyan]")
            console.print(f"  Post commit: [cyan]{cmp['post_commit']}[/cyan]")

            # Three-pillar Quality / Speed / Cost summary
            q = cmp.get("quality", {}) or {}
            quality_pass = bool(q.get("passed", True))
            quality_baseline = q.get("baseline_pass_rate")
            quality_post = q.get("post_pass_rate")
            # Use 0.0 placeholders when no quality signal exists so the line still renders
            qb = float(quality_baseline) if quality_baseline is not None else 0.0
            qp = float(quality_post) if quality_post is not None else 0.0

            exec_block = cmp.get("exec_metrics", {}) or {}
            pre_exec = exec_metrics_from_dict(exec_block.get("baseline") or {})
            post_exec = exec_metrics_from_dict(exec_block.get("post") or {})
            thresholds_used = exec_block.get("thresholds_used") or {}

            for line in render_three_pillar_summary(
                quality_pass=quality_pass,
                quality_baseline=qb,
                quality_post=qp,
                exec_pre=pre_exec,
                exec_post=post_exec,
                thresholds=thresholds_used,
            ):
                console.print(f"  {line}")

            for w in cmp.get("warnings", []) or []:
                console.print(f"  [yellow]⚠[/yellow] {w}")

            # --- Rubric per-criterion deltas / Composite verdict tree ---
            pre_data = json.loads(Path(cmp['baseline_file']).read_text(encoding='utf-8'))
            post_data = json.loads(Path(cmp['post_file']).read_text(encoding='utf-8'))
            pre_eval_type = pre_data.get('meta', {}).get('eval_type')

            if pre_eval_type == 'rubric':
                pre_means = pre_data.get('metrics', {}).get('per_criterion_means', {})
                post_means = post_data.get('metrics', {}).get('per_criterion_means', {})
                if pre_means or post_means:
                    rubric_table = Table(title="Rubric criteria")
                    rubric_table.add_column("Criterion", style="cyan")
                    rubric_table.add_column("Baseline", justify="right")
                    rubric_table.add_column("Post", justify="right")
                    rubric_table.add_column("Delta", justify="right")
                    all_keys = sorted(set(pre_means) | set(post_means))
                    for key in all_keys:
                        b = pre_means.get(key)
                        p = post_means.get(key)
                        delta_str = ""
                        if isinstance(b, (int, float)) and isinstance(p, (int, float)):
                            d = p - b
                            color = "green" if d >= 0 else "red"
                            delta_str = f"[{color}]{d:+.2f}[/{color}]"
                        rubric_table.add_row(
                            key,
                            f"{b:.2f}" if isinstance(b, (int, float)) else "-",
                            f"{p:.2f}" if isinstance(p, (int, float)) else "-",
                            delta_str,
                        )
                    cal_b = pre_data.get('metrics', {}).get('calibration_agreement')
                    cal_p = post_data.get('metrics', {}).get('calibration_agreement')
                    if cal_b is not None or cal_p is not None:
                        rubric_table.add_row(
                            "[dim]calibration_agreement[/dim]",
                            f"{cal_b:.0%}" if cal_b is not None else "-",
                            f"{cal_p:.0%}" if cal_p is not None else "-",
                            "",
                        )
                    console.print(rubric_table)

            if pre_eval_type == 'composite' and 'composite' in cmp:
                comp = cmp['composite']
                ws = comp.get('weighted_score', {}) or {}
                vd = comp.get('verdict', {}) or {}
                overall_color = "red" if comp.get('regressed') else "green"
                console.print(f"\n  [bold]Composite roll-up:[/bold]")
                console.print(
                    f"    Weighted score: {ws.get('baseline', 0):.3f} -> {ws.get('post', 0):.3f}  "
                    f"([{overall_color}]Δ {ws.get('delta', 0):+.3f}[/{overall_color}])"
                )
                console.print(f"    Verdict: {vd.get('baseline', '?')} -> {vd.get('post', '?')}")

                per_sub = comp.get('per_sub_eval', {}) or {}
                if per_sub:
                    sub_table = Table(title="Sub-evaluators")
                    sub_table.add_column("Sub-eval", style="cyan")
                    sub_table.add_column("Baseline", justify="right")
                    sub_table.add_column("Post", justify="right")
                    sub_table.add_column("Delta", justify="right")
                    sub_table.add_column("Regressed", justify="center")
                    for key, sub in per_sub.items():
                        b_score = sub.get('baseline_score', 0.0)
                        p_score = sub.get('post_score', 0.0)
                        delta = sub.get('delta', 0.0)
                        d_color = "red" if sub.get('regressed') else ("green" if delta >= 0 else "yellow")
                        regressed_marker = "[red]⚠[/red]" if sub.get('regressed') else "[green]✓[/green]"
                        sub_table.add_row(
                            key,
                            f"{b_score:.2f}",
                            f"{p_score:.2f}",
                            f"[{d_color}]{delta:+.2f}[/{d_color}]",
                            regressed_marker,
                        )
                    console.print(sub_table)

            # Print metrics table
            table = Table(title=f"{imp_id} Comparison")
            table.add_column("Metric", style="cyan")
            table.add_column("Baseline", justify="right")
            table.add_column("Post", justify="right")
            table.add_column("Delta", justify="right")

            for key, vals in cmp["metrics"].items():
                delta_str = ""
                if vals["delta"] is not None:
                    delta_str = f"{vals['delta']:+.2f}" if isinstance(vals['delta'], float) else f"{vals['delta']:+d}"
                table.add_row(
                    key,
                    str(vals["baseline"]),
                    str(vals["post"]),
                    delta_str,
                )
            console.print(table)

            if cmp["regressed"]:
                console.print("\n  [bold red]⚠ REGRESSION DETECTED[/bold red]")
                console.print("  [dim]Review the post snapshot results and consider reverting.[/dim]")
                sys.exit(1)
            else:
                console.print(f"\n  [green]✅ No regressions[/green]")

        except FileNotFoundError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)

    console.print()


if __name__ == "__main__":
    main()
