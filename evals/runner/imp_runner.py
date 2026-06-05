"""
IMP runner — baseline/post snapshot capture and comparison for IMP evaluations.

Supports eval_type: structural (model-free), tool_loop, subagent_routing (Foundry).

Snapshots are stored in baselines/IMP-XXXX/{timestamp}-{commit_sha}.json
as a rolling history (not single overwrite).
"""

from __future__ import annotations

import importlib
import json
import statistics
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from evaluators.execution_metrics import (
    ExecMetrics,
    compute_exec_metrics,
    load_pricing_table,
    to_dict as exec_metrics_to_dict,
    from_dict as exec_metrics_from_dict,
    compare_exec_metrics,
)


@dataclass
class ImpFrontmatter:
    """Parsed IMP frontmatter fields."""
    id: str
    title: str
    status: str
    affects: list[str]
    eval_type: str = "manual"
    eval_id: Optional[str] = None
    eval_seed: int = 42
    commit: Optional[str] = None
    baseline_run: Optional[str] = None
    post_run: Optional[str] = None
    thresholds: dict = field(default_factory=dict)
    # Phase 2/3 fields — only used by rubric / composite eval_types.
    rubric_path: Optional[str] = None
    calibration_path: Optional[str] = None
    calibration_min_agreement: float = 0.80
    sub_evals: list = field(default_factory=list)
    composite_pass_threshold: float = 0.7


@dataclass
class SnapshotMeta:
    """§3a measurement contract fields for every snapshot."""
    imp_id: str
    eval_type: str
    eval_id: Optional[str]
    commit_sha: Optional[str]
    timestamp: str
    phase: str  # "baseline" or "post"
    model: Optional[str] = None  # null for structural
    temperature: Optional[float] = None
    seed: Optional[int] = None
    n_samples: int = 1
    cost: dict = field(default_factory=dict)        # {input_tokens, output_tokens, wall_time_ms, cost_usd, pricing_source}
    trajectory: dict = field(default_factory=dict)
    thresholds: dict = field(default_factory=dict)  # IMP-specific overrides for execution_metrics gating


@dataclass
class Snapshot:
    """Full snapshot combining meta + metrics + raw results."""
    meta: SnapshotMeta
    metrics: dict = field(default_factory=dict)
    raw_results: list[dict] = field(default_factory=list)
    sub_snapshots: dict = field(default_factory=dict)  # composite-only


# --- IMP file discovery ---

# evals/runner/imp_runner.py -> evals/runner -> evals/ -> .copilot/ -> agents/improvements
IMPROVEMENTS_DIR = Path(__file__).resolve().parent.parent.parent / "agents" / "improvements"


def _load_pricing(foundry_config: Optional[dict]) -> tuple[dict, Optional[str]]:
    """Return (pricing_table, pricing_version) from a loaded config dict.

    Caller is expected to pass the same `foundry_config` dict it already loads
    in capture_snapshot(). Returns ({}, None) if no pricing block.
    """
    if not foundry_config:
        return {}, None
    table = load_pricing_table(foundry_config)
    version = (foundry_config.get("pricing") or {}).get("version")
    return table, version


def find_imp_file(imp_id: str) -> Path:
    """Find the IMP file by ID (e.g., IMP-0004)."""
    for f in IMPROVEMENTS_DIR.iterdir():
        if f.name.startswith(imp_id) and f.suffix == ".md" and not f.name.startswith("_"):
            return f
    raise FileNotFoundError(f"No IMP file found for {imp_id} in {IMPROVEMENTS_DIR}")


def parse_imp_frontmatter(imp_path: Path) -> ImpFrontmatter:
    """Parse YAML frontmatter from an IMP file."""
    text = imp_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{imp_path} has no YAML frontmatter")
    end = text.find("---", 3)
    if end == -1:
        raise ValueError(f"{imp_path} has malformed frontmatter (no closing ---)")
    fm = yaml.safe_load(text[3:end])
    return ImpFrontmatter(
        id=fm.get("id", ""),
        title=fm.get("title", ""),
        status=fm.get("status", ""),
        affects=fm.get("affects", []),
        eval_type=fm.get("eval_type", "manual"),
        eval_id=fm.get("eval_id"),
        eval_seed=fm.get("eval_seed", 42),
        commit=fm.get("commit"),
        baseline_run=fm.get("baseline_run"),
        post_run=fm.get("post_run"),
        thresholds=fm.get("thresholds") or {},
        rubric_path=fm.get("rubric_path"),
        calibration_path=fm.get("calibration_path"),
        calibration_min_agreement=float(fm.get("calibration_min_agreement", 0.80)),
        sub_evals=fm.get("sub_evals") or [],
        composite_pass_threshold=float(fm.get("composite_pass_threshold", 0.7)),
    )


def get_current_commit(repo_dir: Path) -> Optional[str]:
    """Get the current HEAD short SHA for a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


# --- Evaluator dispatch ---

def load_evaluator(eval_id: str):
    """Dynamically load an IMP evaluator module from evaluators/custom/."""
    module_name = f"evaluators.custom.{eval_id}"
    return importlib.import_module(module_name)


def run_structural_eval(fm: ImpFrontmatter, agents_dir: Path) -> list[dict]:
    """Run a structural eval and return results as dicts."""
    mod = load_evaluator(fm.eval_id)

    # Convention: evaluator exposes evaluate_imp_XXXX(agent_file: Path) -> ImpReport
    func_name = f"evaluate_{fm.eval_id}"
    evaluate_fn = getattr(mod, func_name, None)
    if evaluate_fn is None:
        raise AttributeError(
            f"Evaluator {fm.eval_id} has no function {func_name}()"
        )

    # Resolve the agent file(s) to evaluate
    # For structural evals, we need the affected agent files
    results = []
    for agent_name in fm.affects:
        agent_file = _resolve_agent_file(agent_name, agents_dir)
        if agent_file is None:
            results.append({
                "check_id": f"agent_file_{agent_name}",
                "label": f"Agent file for {agent_name}",
                "passed": False,
                "detail": f"Could not find agent file for {agent_name}",
            })
            continue

        report = evaluate_fn(agent_file)
        for r in report.results:
            results.append({
                "check_id": r.check_id,
                "label": r.label,
                "passed": r.passed,
                "detail": r.detail,
            })

    return results


def _resolve_agent_file(agent_name: str, agents_dir: Path) -> Optional[Path]:
    """Find the agent definition file by name."""
    # Try common patterns
    candidates = [
        agents_dir / f"{agent_name}.agent.md",
        agents_dir / f"{agent_name.upper()}.agent.md",
        agents_dir / f"{agent_name.lower()}.agent.md",
        agents_dir / f"{agent_name}.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# --- Snapshot I/O ---

def snapshot_path(baselines_dir: Path, imp_id: str, commit_sha: Optional[str], phase: str) -> Path:
    """Generate a snapshot file path: baselines/IMP-XXXX/{timestamp}-{sha}-{phase}.json."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    sha_part = commit_sha or "unknown"
    imp_dir = baselines_dir / imp_id
    imp_dir.mkdir(parents=True, exist_ok=True)
    return imp_dir / f"{ts}-{sha_part}-{phase}.json"


def save_snapshot(path: Path, snapshot: Snapshot) -> None:
    """Serialize and write a snapshot to disk."""
    data = {
        "meta": asdict(snapshot.meta),
        "metrics": snapshot.metrics,
        "raw_results": snapshot.raw_results,
    }
    if snapshot.sub_snapshots:
        data["sub_snapshots"] = snapshot.sub_snapshots
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_snapshot(path: Path) -> dict:
    """Load a snapshot JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def find_latest_snapshot(baselines_dir: Path, imp_id: str, phase: str) -> Optional[Path]:
    """Find the most recent snapshot for a given IMP and phase."""
    imp_dir = baselines_dir / imp_id
    if not imp_dir.exists():
        return None
    # Match files ending with -{phase}.json
    snapshots = sorted(imp_dir.glob(f"*-{phase}.json"), reverse=True)
    if snapshots:
        return snapshots[0]
    # Fallback: check phase field inside the JSON (for older snapshots)
    for sp in sorted(imp_dir.glob("*.json"), reverse=True):
        data = load_snapshot(sp)
        if data.get("meta", {}).get("phase") == phase:
            return sp
    return None


# --- Core operations ---

def capture_snapshot(
    fm: ImpFrontmatter,
    phase: str,
    agents_dir: Path,
    baselines_dir: Path,
    copilot_repo_dir: Path,
    evals_project_root: Optional[Path] = None,
    foundry_config: Optional[dict] = None,
) -> tuple[Path, Snapshot]:
    """Capture a baseline or post snapshot for an IMP.

    Dispatches to a registered runner function via evaluators.dispatch().
    Each runner returns a fully-built Snapshot (meta + metrics + raw_results
    [+ sub_snapshots]).

    Returns (snapshot_path, snapshot).
    """
    if fm.eval_type == "manual":
        raise ValueError(
            f"{fm.id} has eval_type=manual — no automated eval to run. "
            "Use manual_evidence field instead."
        )

    # Lazy import to avoid circular imports (evaluators/__init__.py -> registry).
    from evaluators import dispatch

    try:
        runner_fn = dispatch(fm.eval_type)
    except KeyError as e:
        raise NotImplementedError(str(e))

    if evals_project_root is None:
        evals_project_root = Path(__file__).parent.parent

    # Load config once, up-front, so every runner can reuse pricing/threshold
    # tables (cost_usd / pricing_source on every snapshot).
    if foundry_config is None:
        cfg_path = evals_project_root / "config.yaml"
        if cfg_path.exists():
            with open(cfg_path) as f:
                foundry_config = yaml.safe_load(f) or {}
        else:
            foundry_config = {}

    commit_sha = get_current_commit(copilot_repo_dir)
    pricing_table, pricing_version = _load_pricing(foundry_config)

    ctx = {
        "phase": phase,
        "commit_sha": commit_sha,
        "agents_dir": agents_dir,
        "baselines_dir": baselines_dir,
        "copilot_repo_dir": copilot_repo_dir,
        "evals_project_root": evals_project_root,
        "foundry_config": foundry_config,
        "pricing_table": pricing_table,
        "pricing_version": pricing_version,
    }

    snapshot = runner_fn(fm, ctx)
    sp = snapshot_path(baselines_dir, fm.id, snapshot.meta.commit_sha, phase)
    save_snapshot(sp, snapshot)

    return sp, snapshot


# --- Per-eval-type runner functions ---
# Each runner has signature (fm, ctx) -> Snapshot and is responsible for
# building its own SnapshotMeta with cost/thresholds populated via the
# shared pricing table on ctx.


def _run_structural(fm: ImpFrontmatter, ctx: dict) -> Snapshot:
    """Structural eval — model-free check of agent definition file(s).

    Records eval-harness wall time so cost regressions in the harness logic
    itself are visible. No model is called, so cost_usd is always 0.
    """
    if not fm.eval_id:
        raise ValueError(f"{fm.id} has eval_type=structural but no eval_id set")

    struct_start = time.monotonic()
    results = run_structural_eval(fm, ctx["agents_dir"])
    struct_wall_ms = int((time.monotonic() - struct_start) * 1000)

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    metrics = {
        "total_checks": total,
        "passed_checks": passed,
        "pass_rate": passed / total if total > 0 else 0.0,
        "all_passed": passed == total,
    }

    exec_metrics = compute_exec_metrics(
        input_tokens=0,
        output_tokens=0,
        wall_time_ms=struct_wall_ms,
        deployment=None,
        pricing=ctx["pricing_table"],
        pricing_version=ctx["pricing_version"],
    )
    meta = SnapshotMeta(
        imp_id=fm.id, eval_type=fm.eval_type, eval_id=fm.eval_id,
        commit_sha=ctx["commit_sha"],
        timestamp=datetime.now(timezone.utc).isoformat(),
        phase=ctx["phase"], model=None, temperature=None, seed=None,
        n_samples=1,
        cost=exec_metrics_to_dict(exec_metrics),
        trajectory={},
        thresholds=fm.thresholds,
    )
    return Snapshot(meta=meta, metrics=metrics, raw_results=results)


def _run_tool_loop(fm: ImpFrontmatter, ctx: dict) -> Snapshot:
    """Tool-loop / subagent-routing eval — runs a Foundry-backed agent loop.

    Wraps run_tool_loop_eval() (which returns a tuple) into a uniform Snapshot.
    Used for both ``tool_loop`` and ``subagent_routing`` eval_types — the
    underlying loop function inspects fm.eval_type to pick the right metrics.
    """
    if not fm.eval_id:
        raise ValueError(
            f"{fm.id} has eval_type={fm.eval_type} but no eval_id set"
        )

    metrics, results, cost, trajectory, model_name = run_tool_loop_eval(
        fm, ctx["agents_dir"], ctx["evals_project_root"], ctx["foundry_config"],
    )
    exec_metrics = compute_exec_metrics(
        input_tokens=cost["input_tokens"],
        output_tokens=cost["output_tokens"],
        wall_time_ms=cost["wall_time_ms"],
        deployment=model_name,
        pricing=ctx["pricing_table"],
        pricing_version=ctx["pricing_version"],
    )
    meta = SnapshotMeta(
        imp_id=fm.id, eval_type=fm.eval_type, eval_id=fm.eval_id,
        commit_sha=ctx["commit_sha"],
        timestamp=datetime.now(timezone.utc).isoformat(),
        phase=ctx["phase"],
        model=model_name,
        temperature=0,
        seed=fm.eval_seed,
        n_samples=metrics.get("n_samples", 1),
        cost=exec_metrics_to_dict(exec_metrics),
        trajectory=trajectory,
        thresholds=fm.thresholds,
    )
    return Snapshot(meta=meta, metrics=metrics, raw_results=results)


def run_tool_loop_eval(
    fm: ImpFrontmatter,
    agents_dir: Path,
    evals_project_root: Path,
    foundry_config: Optional[dict] = None,
) -> tuple[dict, list[dict], dict, dict, str]:
    """Run a tool_loop or subagent_routing eval.

    Returns (metrics, raw_results, cost, trajectory, model_name).
    """
    from evaluators.tool_loop import (
        LoopConfig, load_mocks, run_tool_loop,
        compute_trajectory_metrics, compute_subagent_routing_metrics, compute_cost,
    )
    from evaluators.foundry_client import (
        create_foundry_client, load_foundry_config, load_agent_system_prompt,
        load_tool_definitions,
    )

    # Load config
    if foundry_config is None:
        config_path = evals_project_root / "config.yaml"
        with open(config_path) as f:
            foundry_config = yaml.safe_load(f)

    fc = load_foundry_config(foundry_config)
    client = create_foundry_client(fc)

    # Load agent system prompt
    agent_name = fm.affects[0] if fm.affects else "qb"
    agent_file = _resolve_agent_file(agent_name, agents_dir)
    if agent_file is None:
        raise FileNotFoundError(f"Agent file not found for {agent_name}")
    system_prompt = load_agent_system_prompt(agent_file)

    # Load tools
    datasets_dir = evals_project_root / "datasets" / agent_name.lower()
    tools_path = datasets_dir / "tools.json"
    if not tools_path.exists():
        raise FileNotFoundError(f"No tools.json at {tools_path}")
    tools = load_tool_definitions(tools_path)

    # Load mocks
    mocks_path = datasets_dir / "mocks.yaml"
    if not mocks_path.exists():
        raise FileNotFoundError(f"No mocks.yaml at {mocks_path}")
    mocks, on_unmocked = load_mocks(mocks_path)

    # Load scenarios from the custom evaluator
    mod = load_evaluator(fm.eval_id)
    scenarios_fn = getattr(mod, "get_scenarios", None)
    if scenarios_fn is None:
        raise AttributeError(
            f"Evaluator {fm.eval_id} has no get_scenarios() function. "
            "Tool_loop evaluators must expose get_scenarios() -> list[dict] "
            "with keys: id, prompt, expected (dict of check functions)."
        )
    scenarios = scenarios_fn()

    # Per-IMP overrides: evaluator may expose N_SAMPLES / MAX_TURNS constants.
    # Defaults preserve the §3a contract (3 samples, 6 turns).
    n_samples = getattr(mod, "N_SAMPLES", 3)
    max_turns = getattr(mod, "MAX_TURNS", 6)

    loop_config = LoopConfig(
        max_turns=max_turns,
        stop_on=[],
        on_unmocked=on_unmocked,
        temperature=0,
        seed=fm.eval_seed,
    )

    all_results = []
    all_trajectories = []
    total_cost = {"input_tokens": 0, "output_tokens": 0, "wall_time_ms": 0}

    for scenario in scenarios:
        scenario_scores = []
        scenario_results = []

        for sample_idx in range(n_samples):
            # Vary seed slightly per sample for §3a stddev measurement
            loop_config.seed = fm.eval_seed + sample_idx
            trace = run_tool_loop(
                client=client,
                deployment=fc.deployment,
                system_prompt=system_prompt,
                user_prompt=scenario["prompt"],
                tools=tools,
                mocks=mocks,
                config=loop_config,
                on_unmocked=on_unmocked,
            )

            # Run scenario-specific checks
            check_fn = getattr(mod, f"check_{scenario['id']}", None)
            if check_fn is None:
                check_fn = getattr(mod, "check_scenario", None)

            if check_fn:
                check_result = check_fn(trace, scenario)
            else:
                # Default: just record trajectory
                check_result = {"passed": True, "detail": "no check function — trajectory only"}

            traj = compute_trajectory_metrics(trace)
            if fm.eval_type == "subagent_routing":
                traj.update(compute_subagent_routing_metrics(trace))

            cost = compute_cost(trace)
            total_cost["input_tokens"] += cost["input_tokens"]
            total_cost["output_tokens"] += cost["output_tokens"]
            total_cost["wall_time_ms"] += cost["wall_time_ms"]

            passed = check_result.get("passed", False)
            scenario_scores.append(1.0 if passed else 0.0)

            scenario_results.append({
                "sample": sample_idx,
                "passed": passed,
                "detail": check_result.get("detail", ""),
                "trajectory": traj,
            })

        # Aggregate per-scenario
        mean_score = statistics.mean(scenario_scores) if scenario_scores else 0.0
        stddev = statistics.stdev(scenario_scores) if len(scenario_scores) > 1 else 0.0

        all_results.append({
            "scenario_id": scenario["id"],
            "prompt": scenario["prompt"],
            "mean_pass_rate": round(mean_score, 3),
            "stddev": round(stddev, 3),
            "n_samples": n_samples,
            "per_sample": scenario_results,
        })
        all_trajectories.extend(scenario_results)

    # Aggregate metrics across all scenarios
    scenario_pass_rates = [r["mean_pass_rate"] for r in all_results]
    overall_pass = statistics.mean(scenario_pass_rates) if scenario_pass_rates else 0.0

    metrics = {
        "total_scenarios": len(scenarios),
        "overall_pass_rate": round(overall_pass, 3),
        "all_passed": all(r["mean_pass_rate"] == 1.0 for r in all_results),
        "n_samples": n_samples,
        "per_scenario": {r["scenario_id"]: r["mean_pass_rate"] for r in all_results},
    }

    # Aggregate trajectory from last run of first scenario as representative
    rep_traj = {}
    if all_trajectories:
        rep_traj = all_trajectories[0].get("trajectory", {})

    return metrics, all_results, total_cost, rep_traj, fc.deployment


def _run_execution_metrics(fm: ImpFrontmatter, ctx: dict) -> Snapshot:
    """Standalone execution_metrics eval — captures cost/speed in isolation.

    Conservative scope:
      - If `eval_id` is set, the IMP's affected agent is run through one
        short tool_loop scenario (single sample, max_turns capped at 2)
        purely to measure cost and wall time.
      - If no `eval_id`, this is a model-free measurement: only the
        eval-harness wall time is captured, with zero token spend.

    The metrics dict is intentionally light (no behavioural pass/fail) — the
    actual regression gating happens later in compare_snapshots() via
    compare_exec_metrics(). `all_passed` is always True here so the standalone
    snapshot has a stable shape (verdict comes from cost regressions, not the
    per-snapshot metric block).
    """
    if not fm.eval_id:
        # Model-free measurement — capture only harness wall time.
        start = time.monotonic()
        wall_ms = int((time.monotonic() - start) * 1000)
        exec_metrics = compute_exec_metrics(
            input_tokens=0,
            output_tokens=0,
            wall_time_ms=wall_ms,
            deployment=None,
            pricing=ctx["pricing_table"],
            pricing_version=ctx["pricing_version"],
        )
        metrics = {
            "all_passed": True,
            "wall_time_ms": wall_ms,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        }
        meta = SnapshotMeta(
            imp_id=fm.id, eval_type=fm.eval_type, eval_id=None,
            commit_sha=ctx["commit_sha"],
            timestamp=datetime.now(timezone.utc).isoformat(),
            phase=ctx["phase"], model=None, temperature=None, seed=None,
            n_samples=1,
            cost=exec_metrics_to_dict(exec_metrics),
            trajectory={},
            thresholds=fm.thresholds,
        )
        return Snapshot(meta=meta, metrics=metrics, raw_results=[])

    # Run a single short scenario through the existing tool_loop pipeline,
    # but cap turns/samples to keep cost bounded — this runner exists for
    # cost telemetry, not behavioural assertions.
    from evaluators.tool_loop import (
        LoopConfig, load_mocks, run_tool_loop, compute_cost,
    )
    from evaluators.foundry_client import (
        create_foundry_client, load_foundry_config,
        load_agent_system_prompt, load_tool_definitions,
    )

    fc = load_foundry_config(ctx["foundry_config"])
    client = create_foundry_client(fc)

    agent_name = fm.affects[0] if fm.affects else "qb"
    agent_file = _resolve_agent_file(agent_name, ctx["agents_dir"])
    if agent_file is None:
        raise FileNotFoundError(f"Agent file not found for {agent_name}")
    system_prompt = load_agent_system_prompt(agent_file)

    datasets_dir = ctx["evals_project_root"] / "datasets" / agent_name.lower()
    tools = load_tool_definitions(datasets_dir / "tools.json")
    mocks, on_unmocked = load_mocks(datasets_dir / "mocks.yaml")

    mod = load_evaluator(fm.eval_id)
    scenarios_fn = getattr(mod, "get_scenarios", None)
    if scenarios_fn is None:
        raise AttributeError(
            f"Evaluator {fm.eval_id} has no get_scenarios() function"
        )
    scenarios = scenarios_fn()
    if not scenarios:
        raise ValueError(f"Evaluator {fm.eval_id} returned no scenarios")

    scenario = scenarios[0]
    loop_config = LoopConfig(
        max_turns=2,
        stop_on=[],
        on_unmocked=on_unmocked,
        temperature=0,
        seed=fm.eval_seed,
    )
    trace = run_tool_loop(
        client=client,
        deployment=fc.deployment,
        system_prompt=system_prompt,
        user_prompt=scenario["prompt"],
        tools=tools,
        mocks=mocks,
        config=loop_config,
        on_unmocked=on_unmocked,
    )
    cost = compute_cost(trace)
    exec_metrics = compute_exec_metrics(
        input_tokens=cost["input_tokens"],
        output_tokens=cost["output_tokens"],
        wall_time_ms=cost["wall_time_ms"],
        deployment=fc.deployment,
        pricing=ctx["pricing_table"],
        pricing_version=ctx["pricing_version"],
    )
    metrics = {
        "all_passed": True,
        "wall_time_ms": cost["wall_time_ms"],
        "input_tokens": cost["input_tokens"],
        "output_tokens": cost["output_tokens"],
        "cost_usd": exec_metrics.cost_usd,
    }
    meta = SnapshotMeta(
        imp_id=fm.id, eval_type=fm.eval_type, eval_id=fm.eval_id,
        commit_sha=ctx["commit_sha"],
        timestamp=datetime.now(timezone.utc).isoformat(),
        phase=ctx["phase"],
        model=fc.deployment,
        temperature=0,
        seed=fm.eval_seed,
        n_samples=1,
        cost=exec_metrics_to_dict(exec_metrics),
        trajectory={},
        thresholds=fm.thresholds,
    )
    return Snapshot(meta=meta, metrics=metrics, raw_results=[])


def _run_rubric(fm: ImpFrontmatter, ctx: dict) -> Snapshot:
    """Standalone rubric eval — score agent responses with an LLM judge.

    Required IMP frontmatter:
      - rubric_path: relative path to evaluators/rubrics/<id>.md
      - eval_id: a tool_loop-style module exposing get_scenarios() (each
        scenario is run through the loop to obtain a response, which is then
        scored by the rubric judge).

    Optional:
      - calibration_path: relative path to *.calibration.jsonl. When set,
        run_calibration() is run first; if the agreement gate fails, scoring
        is skipped and a calibration-failure snapshot is returned.

    Aggregated metrics shape:
        {
          "weighted_score": float,            # mean across scenarios
          "pass_rate": float,                 # fraction of scenarios passed
          "all_passed": bool,                 # all scenarios + calibration
          "calibration_agreement": float|None,
          "calibration_passed": bool,
          "per_criterion_means": {...},
        }
    """
    from evaluators.rubric import (
        load_rubric, evaluate_with_rubric, compute_rubric_summary,
    )
    from evaluators.calibration import load_calibration_set, run_calibration
    from evaluators.tool_loop import (
        LoopConfig, load_mocks, run_tool_loop, compute_cost,
    )
    from evaluators.foundry_client import (
        create_foundry_client, load_foundry_config,
        load_agent_system_prompt, load_tool_definitions,
    )

    if not fm.rubric_path:
        raise ValueError(
            f"{fm.id} has eval_type=rubric but no rubric_path set"
        )
    if not fm.eval_id:
        raise ValueError(
            f"{fm.id} has eval_type=rubric but no eval_id set"
        )

    evals_root: Path = ctx["evals_project_root"]
    rubric_file = (evals_root / fm.rubric_path).resolve()
    if not rubric_file.exists():
        raise FileNotFoundError(f"Rubric file not found: {rubric_file}")
    rubric = load_rubric(rubric_file)

    fc = load_foundry_config(ctx["foundry_config"])
    client = create_foundry_client(fc)

    total_cost = {"input_tokens": 0, "output_tokens": 0, "wall_time_ms": 0}
    raw_results: list[dict] = []
    calibration_passed = True
    calibration_agreement: Optional[float] = None

    # --- Calibration gate ---
    if fm.calibration_path:
        calib_file = (evals_root / fm.calibration_path).resolve()
        if not calib_file.exists():
            raise FileNotFoundError(f"Calibration file not found: {calib_file}")
        examples = load_calibration_set(calib_file)
        report = run_calibration(
            rubric, examples, client, fc.deployment,
            min_agreement=fm.calibration_min_agreement,
        )
        calibration_passed = report.passed
        calibration_agreement = report.agreement_rate
        if not report.passed:
            metrics = {
                "calibration_passed": False,
                "calibration_agreement": report.agreement_rate,
                "weighted_score": 0.0,
                "pass_rate": 0.0,
                "all_passed": False,
                "per_criterion_means": {},
            }
            raw_results = [
                {
                    "example_id": r.example_id,
                    "expected": r.expected_scores,
                    "judge": r.judge_scores,
                    "fully_agreed": r.fully_agreed,
                }
                for r in report.results
            ]
            exec_metrics = compute_exec_metrics(
                input_tokens=0, output_tokens=0, wall_time_ms=0,
                deployment=fc.deployment,
                pricing=ctx["pricing_table"],
                pricing_version=ctx["pricing_version"],
            )
            meta = SnapshotMeta(
                imp_id=fm.id, eval_type=fm.eval_type, eval_id=fm.eval_id,
                commit_sha=ctx["commit_sha"],
                timestamp=datetime.now(timezone.utc).isoformat(),
                phase=ctx["phase"], model=fc.deployment,
                temperature=0, seed=fm.eval_seed, n_samples=0,
                cost=exec_metrics_to_dict(exec_metrics),
                trajectory={},
                thresholds=fm.thresholds,
            )
            return Snapshot(meta=meta, metrics=metrics, raw_results=raw_results)

    # --- Per-scenario tool_loop + judge ---
    agent_name = fm.affects[0] if fm.affects else "qb"
    agent_file = _resolve_agent_file(agent_name, ctx["agents_dir"])
    if agent_file is None:
        raise FileNotFoundError(f"Agent file not found for {agent_name}")
    system_prompt = load_agent_system_prompt(agent_file)

    datasets_dir = evals_root / "datasets" / agent_name.lower()
    tools = load_tool_definitions(datasets_dir / "tools.json")
    mocks, on_unmocked = load_mocks(datasets_dir / "mocks.yaml")

    mod = load_evaluator(fm.eval_id)
    scenarios_fn = getattr(mod, "get_scenarios", None)
    if scenarios_fn is None:
        raise AttributeError(
            f"Evaluator {fm.eval_id} has no get_scenarios() function"
        )
    scenarios = scenarios_fn()

    rubric_results = []
    for scenario in scenarios:
        loop_config = LoopConfig(
            max_turns=getattr(mod, "MAX_TURNS", 6),
            stop_on=[],
            on_unmocked=on_unmocked,
            temperature=0,
            seed=fm.eval_seed,
        )
        trace = run_tool_loop(
            client=client,
            deployment=fc.deployment,
            system_prompt=system_prompt,
            user_prompt=scenario["prompt"],
            tools=tools,
            mocks=mocks,
            config=loop_config,
            on_unmocked=on_unmocked,
        )
        cost = compute_cost(trace)
        total_cost["input_tokens"] += cost["input_tokens"]
        total_cost["output_tokens"] += cost["output_tokens"]
        total_cost["wall_time_ms"] += cost["wall_time_ms"]

        # Extract the final assistant response from the trace turns.
        # (Note: LoopTrace stores assistant turns in .turns, not .messages.)
        response_text = ""
        for turn_msg in reversed(getattr(trace, "turns", []) or []):
            role = turn_msg.get("role") if isinstance(turn_msg, dict) else None
            content = turn_msg.get("content") if isinstance(turn_msg, dict) else None
            if role == "assistant" and isinstance(content, str) and content.strip():
                response_text = content
                break

        rubric_result = evaluate_with_rubric(
            prompt=scenario["prompt"],
            response=response_text,
            rubric=rubric,
            client=client,
            deployment=fc.deployment,
            seed=fm.eval_seed,
        )
        rubric_results.append(rubric_result)
        raw_results.append({
            "scenario_id": scenario.get("id"),
            "prompt": scenario["prompt"],
            "response": response_text,
            "weighted_score": rubric_result.weighted_score,
            "passed": rubric_result.passed,
            "per_criterion": [
                {"name": cs.name, "score": cs.score, "weight": cs.weight}
                for cs in rubric_result.per_criterion
            ],
        })

    summary = compute_rubric_summary(rubric_results)
    pass_rate = summary["pass_rate"]
    metrics = {
        "weighted_score": summary["mean_weighted_score"],
        "pass_rate": pass_rate,
        "all_passed": (pass_rate == 1.0) and calibration_passed,
        "calibration_agreement": calibration_agreement,
        "calibration_passed": calibration_passed,
        "per_criterion_means": summary["per_criterion_means"],
    }
    exec_metrics = compute_exec_metrics(
        input_tokens=total_cost["input_tokens"],
        output_tokens=total_cost["output_tokens"],
        wall_time_ms=total_cost["wall_time_ms"],
        deployment=fc.deployment,
        pricing=ctx["pricing_table"],
        pricing_version=ctx["pricing_version"],
    )
    meta = SnapshotMeta(
        imp_id=fm.id, eval_type=fm.eval_type, eval_id=fm.eval_id,
        commit_sha=ctx["commit_sha"],
        timestamp=datetime.now(timezone.utc).isoformat(),
        phase=ctx["phase"], model=fc.deployment,
        temperature=0, seed=fm.eval_seed,
        n_samples=len(scenarios),
        cost=exec_metrics_to_dict(exec_metrics),
        trajectory={},
        thresholds=fm.thresholds,
    )
    return Snapshot(meta=meta, metrics=metrics, raw_results=raw_results)


def _run_composite(fm: ImpFrontmatter, ctx: dict) -> Snapshot:
    """Composite eval — dispatches each sub_eval via the registry.

    Builds a synthetic per-sub-eval ImpFrontmatter (copying the parent's
    fields plus the SubEvalSpec's eval_type/eval_id and any extras such as
    rubric_path), then calls evaluators.dispatch(sub.eval_type)(sub_fm, ctx)
    to obtain a sub-snapshot. The sub-snapshots are embedded inline on the
    composite Snapshot's `sub_snapshots` field, and the per-sub verdict
    rollup is stored in `metrics` via runner.composite.to_snapshot_dict().

    Cost on the composite snapshot is the SUM of sub-snapshot costs, so the
    standard exec_metrics regression check still applies to the composite as
    a whole.
    """
    from runner.composite import (
        parse_composite_spec, run_composite, to_snapshot_dict,
        SubEvalSpec,
    )
    from evaluators import dispatch as dispatch_eval
    from dataclasses import replace as _dc_replace

    if not fm.sub_evals:
        raise ValueError(
            f"{fm.id} has eval_type=composite but no sub_evals declared"
        )

    spec = parse_composite_spec({
        "sub_evals": fm.sub_evals,
        "composite_pass_threshold": fm.composite_pass_threshold,
    })

    def _sub_runner(sub: SubEvalSpec) -> dict:
        # Build a synthetic sub-frontmatter — inherit parent context and
        # override eval_type/eval_id, then layer SubEvalSpec.extra so
        # sub-eval-specific config (rubric_path, calibration_path, …) is
        # honoured exactly as if the sub-eval were a standalone IMP.
        sub_fm = _dc_replace(
            fm,
            eval_type=sub.eval_type,
            eval_id=sub.eval_id,
        )
        for key, value in (sub.extra or {}).items():
            if hasattr(sub_fm, key):
                setattr(sub_fm, key, value)

        sub_runner_fn = dispatch_eval(sub.eval_type)
        sub_snapshot = sub_runner_fn(sub_fm, ctx)
        return {
            "meta": asdict(sub_snapshot.meta),
            "metrics": sub_snapshot.metrics,
            "raw_results": sub_snapshot.raw_results,
        }

    result = run_composite(spec, _sub_runner)

    metrics = to_snapshot_dict(result)

    # Sum sub-snapshot costs so the composite-level exec_metrics block still
    # reflects total spend (and gates on the composite as a whole).
    total_in = total_out = total_wall = 0
    deployment_seen: Optional[str] = None
    for snap in result.sub_snapshots.values():
        cost = ((snap or {}).get("meta") or {}).get("cost") or {}
        total_in += int(cost.get("input_tokens", 0) or 0)
        total_out += int(cost.get("output_tokens", 0) or 0)
        total_wall += int(cost.get("wall_time_ms", 0) or 0)
        m = ((snap or {}).get("meta") or {}).get("model")
        if m and not deployment_seen:
            deployment_seen = m

    exec_metrics = compute_exec_metrics(
        input_tokens=total_in,
        output_tokens=total_out,
        wall_time_ms=total_wall,
        deployment=deployment_seen,
        pricing=ctx["pricing_table"],
        pricing_version=ctx["pricing_version"],
    )
    meta = SnapshotMeta(
        imp_id=fm.id, eval_type=fm.eval_type, eval_id=fm.eval_id,
        commit_sha=ctx["commit_sha"],
        timestamp=datetime.now(timezone.utc).isoformat(),
        phase=ctx["phase"],
        model=deployment_seen,
        temperature=0 if deployment_seen else None,
        seed=fm.eval_seed if deployment_seen else None,
        n_samples=len(result.sub_verdicts),
        cost=exec_metrics_to_dict(exec_metrics),
        trajectory={},
        thresholds=fm.thresholds,
    )
    return Snapshot(
        meta=meta,
        metrics=metrics,
        raw_results=[],
        sub_snapshots=result.sub_snapshots,
    )


# --- Registry wiring ---
# Imported lazily to avoid the runner -> evaluators -> runner cycle that would
# trip an `import evaluators` at top-of-module.
def _register_runners() -> None:
    from evaluators import register
    register("structural", _run_structural)
    register("tool_loop", _run_tool_loop)
    register("subagent_routing", _run_tool_loop)
    register("execution_metrics", _run_execution_metrics)
    register("rubric", _run_rubric)
    register("composite", _run_composite)


_register_runners()


def compare_snapshots(
    baselines_dir: Path,
    imp_id: str,
    evals_project_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Compare the latest baseline and post snapshots for an IMP.

    Returns a comparison dict with quality / exec_metrics / verdict.
    """
    pre_path = find_latest_snapshot(baselines_dir, imp_id, "baseline")
    post_path = find_latest_snapshot(baselines_dir, imp_id, "post")

    if pre_path is None:
        raise FileNotFoundError(
            f"No baseline snapshot for {imp_id}. Run: evals run-imp {imp_id} --baseline"
        )
    if post_path is None:
        raise FileNotFoundError(
            f"No post snapshot for {imp_id}. Run: evals run-imp {imp_id} --post"
        )

    pre = load_snapshot(pre_path)
    post = load_snapshot(post_path)

    pre_metrics = pre.get("metrics", {})
    post_metrics = post.get("metrics", {})
    pre_meta = pre.get("meta", {}) or {}
    post_meta = post.get("meta", {}) or {}

    # Build base comparison
    comparison: dict[str, Any] = {
        "imp_id": imp_id,
        "baseline_file": str(pre_path),
        "post_file": str(post_path),
        "baseline_commit": pre_meta.get("commit_sha"),
        "post_commit": post_meta.get("commit_sha"),
        "metrics": {},
        "regressed": False,
        "verdict": "pass",
    }

    # Compare each metric
    for key in set(list(pre_metrics.keys()) + list(post_metrics.keys())):
        pre_val = pre_metrics.get(key)
        post_val = post_metrics.get(key)
        delta = None
        if isinstance(pre_val, (int, float)) and isinstance(post_val, (int, float)):
            delta = post_val - pre_val

        comparison["metrics"][key] = {
            "baseline": pre_val,
            "post": post_val,
            "delta": delta,
        }

    # --- Execution metrics: load config thresholds, merge IMP overrides ---
    if evals_project_root is None:
        evals_project_root = Path(__file__).parent.parent
    cfg_path = evals_project_root / "config.yaml"
    if cfg_path.exists():
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}
    default_thresholds = (cfg.get("execution_metrics") or {}).copy()
    imp_overrides = (post_meta.get("thresholds") or {}) or {}
    merged_thresholds = {**default_thresholds, **imp_overrides}

    pre_exec = exec_metrics_from_dict(pre_meta.get("cost") or {})
    post_exec = exec_metrics_from_dict(post_meta.get("cost") or {})
    regressions = compare_exec_metrics(pre_exec, post_exec, merged_thresholds)

    comparison["exec_metrics"] = {
        "baseline": exec_metrics_to_dict(pre_exec),
        "post": exec_metrics_to_dict(post_exec),
        "regressions": [
            {
                "metric": r.metric,
                "baseline": r.baseline,
                "post": r.post,
                "delta": r.delta,
                "delta_pct": r.delta_pct,
                "severity": r.severity,
                "threshold_pct": r.threshold_pct,
                "note": r.note,
            }
            for r in regressions
        ],
        "thresholds_used": merged_thresholds,
    }

    # --- Quality block ---
    def _read_pass_rate(m: dict) -> Optional[float]:
        if "pass_rate" in m and isinstance(m["pass_rate"], (int, float)):
            return float(m["pass_rate"])
        if "overall_pass_rate" in m and isinstance(m["overall_pass_rate"], (int, float)):
            return float(m["overall_pass_rate"])
        return None

    pre_q = _read_pass_rate(pre_metrics)
    post_q = _read_pass_rate(post_metrics)
    if pre_q is None or post_q is None:
        quality_passed = True  # no signal => no regression
    else:
        quality_passed = post_q >= pre_q

    comparison["quality"] = {
        "baseline_pass_rate": pre_q,
        "post_pass_rate": post_q,
        "passed": quality_passed,
    }

    # --- Verdict logic ---
    has_fail = any(r.severity == "fail" for r in regressions)
    has_warn = any(r.severity == "warn" for r in regressions)

    if not quality_passed:
        comparison["verdict"] = "REGRESSION"
    elif has_fail:
        comparison["verdict"] = "REGRESSION"
    elif has_warn or post_metrics.get("all_passed") is False:
        comparison["verdict"] = "PARTIAL"
    else:
        comparison["verdict"] = "pass"

    comparison["regressed"] = comparison["verdict"] == "REGRESSION"

    # --- Warnings (advisory severity='warn' findings) ---
    warnings: list[str] = []
    for r in regressions:
        if r.severity != "warn":
            continue
        # Special-case cost when cost gating is disabled (cost_regression_pct is None)
        if r.metric == "cost_usd" and merged_thresholds.get("cost_regression_pct") is None:
            warnings.append(
                f"cost_usd grew {r.delta_pct:+.1f}% (advisory — cost gating disabled)"
            )
        else:
            warnings.append(f"{r.metric}: {r.note}")
    comparison["warnings"] = warnings

    # --- Composite handling ---
    # When the snapshot is a composite, layer in the per-sub-eval rollup diff
    # and let the composite verdict override `quality` (the sub-evals are the
    # truth-of-record for behavioural pass/fail; weighted_score plays the
    # `quality` role at the composite level).
    if pre_meta.get("eval_type") == "composite":
        from runner.composite import compare_composites
        composite_diff = compare_composites(pre, post)
        comparison["composite"] = composite_diff
        if composite_diff.get("regressed"):
            comparison["regressed"] = True
            comparison["verdict"] = "REGRESSION"
        else:
            # Treat composite verdict as the quality signal.
            post_verdict = composite_diff.get("verdict", {}).get("post")
            if post_verdict == "fail":
                comparison["regressed"] = True
                comparison["verdict"] = "REGRESSION"
            elif post_verdict == "partial" and comparison["verdict"] == "pass":
                comparison["verdict"] = "PARTIAL"

    return comparison
