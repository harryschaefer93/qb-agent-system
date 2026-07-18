"""
Execution metrics — first-class Quality/Speed/Cost tracking for eval snapshots.

Owns the data model for per-run execution metrics (tokens, wall time, USD cost),
USD computation from a pricing table, and pre/post comparison with severity
classification used by `--compare` to surface Quality/Speed/Cost regressions.

All functions are pure: rendering helpers return strings rather than printing,
so callers (CLI, snapshot writers, comparison reports) compose output as needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


# --- Dataclasses ---

@dataclass
class PricingEntry:
    """Per-deployment USD pricing per 1M tokens."""
    deployment: str
    input_per_million_usd: float
    output_per_million_usd: float


@dataclass
class ExecMetrics:
    """Execution metrics for a single eval run (or aggregate)."""
    input_tokens: int = 0
    output_tokens: int = 0
    wall_time_ms: int = 0
    cost_usd: float = 0.0
    pricing_source: Optional[str] = None  # e.g. "config.yaml@v1"


@dataclass
class MetricRegression:
    """A single regression finding with severity."""
    metric: str          # "wall_time_ms", "input_tokens", "output_tokens", "cost_usd"
    baseline: float
    post: float
    delta: float
    delta_pct: float
    severity: Literal["fail", "warn", "info"]
    threshold_pct: Optional[float]
    note: str


# --- Pricing table ---

def load_pricing_table(config: dict) -> dict[str, PricingEntry]:
    """Load pricing entries from config['pricing'] dict.

    Expected config shape:
      pricing:
        version: v1
        deployments:
          gpt-5.4:
            input_per_million_usd: 1.25
            output_per_million_usd: 10.00
          gpt-4.1-mini:
            input_per_million_usd: 0.40
            output_per_million_usd: 1.60

    Returns dict keyed by deployment name. Returns empty dict (no warning) if
    config has no 'pricing' key — callers can compute zero-cost gracefully.
    """
    pricing_section = (config or {}).get("pricing")
    if not pricing_section:
        return {}

    deployments = pricing_section.get("deployments") or {}
    table: dict[str, PricingEntry] = {}
    for name, entry in deployments.items():
        if not isinstance(entry, dict):
            continue
        table[name] = PricingEntry(
            deployment=name,
            input_per_million_usd=float(entry.get("input_per_million_usd", 0.0)),
            output_per_million_usd=float(entry.get("output_per_million_usd", 0.0)),
        )
    return table


def compute_cost_usd(
    input_tokens: int,
    output_tokens: int,
    deployment: str,
    pricing: dict[str, PricingEntry],
) -> float:
    """Return USD cost; 0.0 if deployment not in pricing table."""
    entry = pricing.get(deployment) if deployment else None
    if entry is None:
        return 0.0
    input_cost = (input_tokens / 1_000_000) * entry.input_per_million_usd
    output_cost = (output_tokens / 1_000_000) * entry.output_per_million_usd
    return input_cost + output_cost


def compute_exec_metrics(
    input_tokens: int,
    output_tokens: int,
    wall_time_ms: int,
    deployment: Optional[str],
    pricing: dict[str, PricingEntry],
    pricing_version: Optional[str] = None,
) -> ExecMetrics:
    """Build an ExecMetrics with USD computed from the pricing table.

    deployment may be None (e.g., structural evals) — in that case cost_usd=0.0.
    pricing_source is set to f'config.yaml@{pricing_version}' when version given.
    """
    cost = 0.0
    if deployment:
        cost = compute_cost_usd(input_tokens, output_tokens, deployment, pricing)

    pricing_source: Optional[str] = None
    if pricing_version:
        pricing_source = f"config.yaml@{pricing_version}"

    return ExecMetrics(
        input_tokens=int(input_tokens or 0),
        output_tokens=int(output_tokens or 0),
        wall_time_ms=int(wall_time_ms or 0),
        cost_usd=float(cost),
        pricing_source=pricing_source,
    )


# --- Serialisation ---

def to_dict(metrics: ExecMetrics) -> dict:
    """Serialise an ExecMetrics to the snapshot 'cost' dict shape:
    {input_tokens, output_tokens, wall_time_ms, cost_usd, pricing_source}."""
    return {
        "input_tokens": metrics.input_tokens,
        "output_tokens": metrics.output_tokens,
        "wall_time_ms": metrics.wall_time_ms,
        "cost_usd": metrics.cost_usd,
        "pricing_source": metrics.pricing_source,
    }


def from_dict(d: dict) -> ExecMetrics:
    """Inverse of to_dict — tolerates missing keys (defaults to 0)."""
    d = d or {}
    return ExecMetrics(
        input_tokens=int(d.get("input_tokens", 0) or 0),
        output_tokens=int(d.get("output_tokens", 0) or 0),
        wall_time_ms=int(d.get("wall_time_ms", 0) or 0),
        cost_usd=float(d.get("cost_usd", 0.0) or 0.0),
        pricing_source=d.get("pricing_source"),
    )


# --- Comparison ---

_SEVERITY_ORDER = {"fail": 0, "warn": 1, "info": 2}
_METRIC_ORDER = ["wall_time_ms", "cost_usd", "input_tokens", "output_tokens"]


def _delta_pct(baseline: float, post: float) -> float:
    """Compute percentage delta. Returns inf when baseline == 0 and post > 0."""
    if baseline == 0:
        if post == 0:
            return 0.0
        return float("inf")
    return ((post - baseline) / baseline) * 100.0


def compare_exec_metrics(
    pre: ExecMetrics,
    post: ExecMetrics,
    thresholds: dict,
) -> list[MetricRegression]:
    """Compare pre/post and return regression findings.

    thresholds dict shape:
      {
        "speed_regression_pct": 25,        # wall_time delta > 25% => fail
        "cost_regression_pct": null,       # null => warn-only (no fail)
        "wall_time_max_ms": 30000,         # absolute cap, fail if exceeded
        "token_regression_pct": 30,        # input+output growth > 30% => warn
      }

    Severity rules:
      - wall_time_ms: severity='fail' if delta_pct > speed_regression_pct
                      OR post > wall_time_max_ms; otherwise 'info' if delta<=0,
                      'warn' if 0 < delta_pct <= speed_regression_pct
      - cost_usd: severity='fail' iff cost_regression_pct is set AND delta_pct > it;
                  otherwise 'warn' if delta_pct > 0; 'info' if delta_pct <= 0
      - input_tokens / output_tokens: 'warn' if delta_pct > token_regression_pct;
                                       'info' otherwise

    Skip metrics where baseline is 0 and post is 0 (no signal).
    delta_pct = ((post - baseline) / baseline) * 100; if baseline == 0 and post > 0
    use float('inf') and severity='warn' for cost/tokens, 'fail' for wall_time.

    Return list ordered by severity (fail first), then by metric.
    """
    thresholds = thresholds or {}
    speed_pct = thresholds.get("speed_regression_pct")
    cost_pct = thresholds.get("cost_regression_pct")
    wall_max = thresholds.get("wall_time_max_ms")
    token_pct = thresholds.get("token_regression_pct")

    findings: list[MetricRegression] = []

    # --- wall_time_ms ---
    if not (pre.wall_time_ms == 0 and post.wall_time_ms == 0):
        baseline = float(pre.wall_time_ms)
        post_v = float(post.wall_time_ms)
        delta = post_v - baseline
        dpct = _delta_pct(baseline, post_v)

        severity: Literal["fail", "warn", "info"]
        note_parts: list[str] = []

        exceeds_cap = wall_max is not None and post_v > float(wall_max)
        exceeds_pct = speed_pct is not None and dpct > float(speed_pct)

        if exceeds_cap or exceeds_pct or (baseline == 0 and post_v > 0):
            severity = "fail"
            if exceeds_cap:
                note_parts.append(
                    f"post {int(post_v)}ms exceeds wall_time_max_ms cap {int(wall_max)}ms"
                )
            if exceeds_pct:
                note_parts.append(
                    f"delta {dpct:+.1f}% exceeds speed_regression_pct {speed_pct}%"
                )
            if baseline == 0 and post_v > 0 and not (exceeds_cap or exceeds_pct):
                note_parts.append("baseline was 0ms; any post time is a fail")
        elif dpct <= 0:
            severity = "info"
            note_parts.append(f"wall time improved or unchanged ({dpct:+.1f}%)")
        else:
            severity = "warn"
            note_parts.append(
                f"wall time grew {dpct:+.1f}% (under {speed_pct}% threshold)"
                if speed_pct is not None
                else f"wall time grew {dpct:+.1f}% (no speed threshold set)"
            )

        findings.append(MetricRegression(
            metric="wall_time_ms",
            baseline=baseline,
            post=post_v,
            delta=delta,
            delta_pct=dpct,
            severity=severity,
            threshold_pct=float(speed_pct) if speed_pct is not None else None,
            note="; ".join(note_parts),
        ))

    # --- cost_usd ---
    if not (pre.cost_usd == 0 and post.cost_usd == 0):
        baseline = float(pre.cost_usd)
        post_v = float(post.cost_usd)
        delta = post_v - baseline
        dpct = _delta_pct(baseline, post_v)

        if cost_pct is not None and dpct > float(cost_pct):
            severity = "fail"
            note = f"cost grew {dpct:+.1f}% exceeding cost_regression_pct {cost_pct}%"
        elif dpct > 0:
            severity = "warn"
            if cost_pct is None:
                note = f"cost grew {dpct:+.1f}% (advisory — no cost gate set)"
            else:
                note = f"cost grew {dpct:+.1f}% (under {cost_pct}% threshold)"
        else:
            severity = "info"
            note = f"cost improved or unchanged ({dpct:+.1f}%)"

        findings.append(MetricRegression(
            metric="cost_usd",
            baseline=baseline,
            post=post_v,
            delta=delta,
            delta_pct=dpct,
            severity=severity,
            threshold_pct=float(cost_pct) if cost_pct is not None else None,
            note=note,
        ))

    # --- input_tokens / output_tokens ---
    for token_metric, pre_v_int, post_v_int in (
        ("input_tokens", pre.input_tokens, post.input_tokens),
        ("output_tokens", pre.output_tokens, post.output_tokens),
    ):
        if pre_v_int == 0 and post_v_int == 0:
            continue
        baseline = float(pre_v_int)
        post_v = float(post_v_int)
        delta = post_v - baseline
        dpct = _delta_pct(baseline, post_v)

        if token_pct is not None and dpct > float(token_pct):
            severity = "warn"
            note = (
                f"{token_metric} grew {dpct:+.1f}% exceeding "
                f"token_regression_pct {token_pct}%"
            )
        else:
            severity = "info"
            if dpct <= 0:
                note = f"{token_metric} improved or unchanged ({dpct:+.1f}%)"
            else:
                note = f"{token_metric} grew {dpct:+.1f}% (within tolerance)"

        findings.append(MetricRegression(
            metric=token_metric,
            baseline=baseline,
            post=post_v,
            delta=delta,
            delta_pct=dpct,
            severity=severity,
            threshold_pct=float(token_pct) if token_pct is not None else None,
            note=note,
        ))

    findings.sort(key=lambda f: (
        _SEVERITY_ORDER.get(f.severity, 99),
        _METRIC_ORDER.index(f.metric) if f.metric in _METRIC_ORDER else 99,
    ))
    return findings


# --- Rendering ---

def _fmt_pct(dpct: float) -> str:
    """Format a percentage delta, handling inf gracefully."""
    if dpct == float("inf"):
        return "+∞%"
    if dpct == float("-inf"):
        return "-∞%"
    return f"{dpct:+.0f}%"


def render_three_pillar_summary(
    quality_pass: bool,
    quality_baseline: float,
    quality_post: float,
    exec_pre: ExecMetrics,
    exec_post: ExecMetrics,
    thresholds: dict,
) -> list[str]:
    """Return a list of rich-markup lines for the Quality/Speed/Cost summary block.

    Format:
      "Quality:  ✓ pass_rate 0.95 -> 0.98 (+0.03)"
      "Speed:    ✗ wall_time 4200ms -> 5800ms (+38%)  REGRESSION (>25% threshold)"
      "Cost:     ⚠ cost_usd $0.0042 -> $0.0061 (+45%)  ADVISORY"

    Use rich tags: [green] / [yellow] / [red] for the icon + label.
    Speed icon: green ✓ if delta<=0, yellow ⚠ if warn, red ✗ if fail.
    Cost icon: same mapping but warn shows 'ADVISORY' suffix when not gated.
    Quality icon: green ✓ if quality_pass else red ✗.
    """
    thresholds = thresholds or {}
    lines: list[str] = []

    # --- Quality line ---
    q_delta = quality_post - quality_baseline
    if quality_pass:
        q_icon = "[green]✓[/green]"
    else:
        q_icon = "[red]✗[/red]"
    lines.append(
        f"Quality:  {q_icon} pass_rate {quality_baseline:.2f} -> "
        f"{quality_post:.2f} ({q_delta:+.2f})"
    )

    # --- Speed line ---
    findings = compare_exec_metrics(exec_pre, exec_post, thresholds)
    speed = next((f for f in findings if f.metric == "wall_time_ms"), None)
    speed_threshold = thresholds.get("speed_regression_pct")

    if speed is None:
        lines.append(
            f"Speed:    [green]✓[/green] wall_time "
            f"{exec_pre.wall_time_ms}ms -> {exec_post.wall_time_ms}ms (no signal)"
        )
    else:
        if speed.severity == "fail":
            icon = "[red]✗[/red]"
            suffix = (
                f"  REGRESSION (>{int(speed_threshold)}% threshold)"
                if speed_threshold is not None
                else "  REGRESSION"
            )
        elif speed.severity == "warn":
            icon = "[yellow]⚠[/yellow]"
            suffix = (
                f"  ADVISORY (under {int(speed_threshold)}% threshold)"
                if speed_threshold is not None
                else "  ADVISORY"
            )
        else:
            icon = "[green]✓[/green]"
            suffix = ""
        lines.append(
            f"Speed:    {icon} wall_time {int(speed.baseline)}ms -> "
            f"{int(speed.post)}ms ({_fmt_pct(speed.delta_pct)}){suffix}"
        )

    # --- Cost line ---
    cost = next((f for f in findings if f.metric == "cost_usd"), None)
    cost_threshold = thresholds.get("cost_regression_pct")

    if cost is None:
        lines.append(
            f"Cost:     [green]✓[/green] cost_usd "
            f"${exec_pre.cost_usd:.4f} -> ${exec_post.cost_usd:.4f} (no signal)"
        )
    else:
        if cost.severity == "fail":
            icon = "[red]✗[/red]"
            suffix = (
                f"  REGRESSION (>{int(cost_threshold)}% threshold)"
                if cost_threshold is not None
                else "  REGRESSION"
            )
        elif cost.severity == "warn":
            icon = "[yellow]⚠[/yellow]"
            suffix = "  ADVISORY" if cost_threshold is None else (
                f"  ADVISORY (under {int(cost_threshold)}% threshold)"
            )
        else:
            icon = "[green]✓[/green]"
            suffix = ""
        lines.append(
            f"Cost:     {icon} cost_usd ${cost.baseline:.4f} -> "
            f"${cost.post:.4f} ({_fmt_pct(cost.delta_pct)}){suffix}"
        )

    return lines
