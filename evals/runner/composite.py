"""
Composite eval module — roll-up of multiple sub-evaluators into a single verdict.

Design: dependency-injection. This module owns the *math* of composite evals
(score normalisation, weighted aggregation, must_pass enforcement, regression
diffing) but knows nothing about how to actually run a structural / tool_loop /
rubric / etc. sub-evaluator. Callers (typically `runner.imp_runner`) provide a
`sub_runner` callback that takes a `SubEvalSpec` and returns a sub-snapshot
dict in the standard `{meta, metrics, raw_results}` shape. This indirection
keeps `composite.py` free of imports back into `imp_runner.py`, avoiding a
circular dependency while still letting `imp_runner.py` reuse all of its
existing dispatch logic.

Public surface:
  - Dataclasses: SubEvalSpec, CompositeSpec, SubVerdict, CompositeResult
  - parse_composite_spec(frontmatter)   — frontmatter -> CompositeSpec
  - normalise_score(eval_type, metrics) — sub-eval metrics -> 0.0-1.0
  - determine_sub_passed(eval_type, metrics) — sub-eval metrics -> bool
  - run_composite(spec, sub_runner)     — execute and roll up
  - compare_composites(pre, post)       — diff two composite snapshots
  - to_snapshot_dict(result)            — CompositeResult -> metrics block
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# Sub-evaluator types recognised inside a composite spec. Mirrors the
# eval_type values supported by imp_runner.capture_snapshot() plus the
# additional model-graded / metrics-only types Phase 2/3 introduce.
KNOWN_EVAL_TYPES: frozenset[str] = frozenset({
    "structural",
    "tool_loop",
    "subagent_routing",
    "behavioral",
    "rubric",
    "execution_metrics",
})

# eval_types whose normalised score comes from a pass-rate metric (0.0-1.0).
_PASS_RATE_TYPES: frozenset[str] = frozenset({
    "structural",
    "tool_loop",
    "subagent_routing",
    "behavioral",
})

# Weight-sum tolerance for CompositeSpec.validate().
_WEIGHT_SUM_TOLERANCE: float = 0.001


# --- Dataclasses ---


@dataclass
class SubEvalSpec:
    """One sub-evaluator within a composite eval.

    Attributes:
        eval_type: Which evaluator family this sub-eval uses. Must be one of
            KNOWN_EVAL_TYPES.
        eval_id: Optional evaluator id (e.g. "imp_0014_loop") that the caller
            uses to load a custom evaluator module. Some eval_types
            (notably execution_metrics) do not need an eval_id.
        weight: Contribution weight in the composite roll-up. Must be in
            [0.0, 1.0]; weights across all sub_evals in a CompositeSpec must
            sum to 1.0 (within _WEIGHT_SUM_TOLERANCE).
        must_pass: If True, a failure of this sub-eval forces the composite
            verdict to "fail" regardless of the weighted score.
        extra: Optional sub-eval-specific config (e.g. {"rubric_path": "..."}).
    """

    eval_type: str
    eval_id: Optional[str] = None
    weight: float = 0.0
    must_pass: bool = True
    extra: dict = field(default_factory=dict)


@dataclass
class CompositeSpec:
    """Composite eval specification parsed from IMP frontmatter.

    Attributes:
        sub_evals: Ordered list of sub-evaluators to run.
        overall_pass_threshold: Minimum weighted_score (0.0-1.0) required for
            the composite verdict to be "pass" (assuming no must_pass
            sub-eval failed).
    """

    sub_evals: list[SubEvalSpec]
    overall_pass_threshold: float = 0.7

    def validate(self) -> None:
        """Validate the spec.

        Raises:
            ValueError: If sub_evals is empty, any sub_eval has an unknown
                eval_type, any weight is outside [0.0, 1.0], the weights do
                not sum to 1.0 (within _WEIGHT_SUM_TOLERANCE), or
                overall_pass_threshold is outside [0.0, 1.0].
        """
        if not self.sub_evals:
            raise ValueError("CompositeSpec must declare at least one sub_eval")

        if not (0.0 <= self.overall_pass_threshold <= 1.0):
            raise ValueError(
                f"overall_pass_threshold must be in [0.0, 1.0], "
                f"got {self.overall_pass_threshold}"
            )

        for idx, sub in enumerate(self.sub_evals):
            if sub.eval_type not in KNOWN_EVAL_TYPES:
                raise ValueError(
                    f"sub_evals[{idx}] has unknown eval_type "
                    f"{sub.eval_type!r}; expected one of "
                    f"{sorted(KNOWN_EVAL_TYPES)}"
                )
            if not (0.0 <= sub.weight <= 1.0):
                raise ValueError(
                    f"sub_evals[{idx}] weight must be in [0.0, 1.0], "
                    f"got {sub.weight}"
                )

        total = sum(sub.weight for sub in self.sub_evals)
        if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
            raise ValueError(
                f"sub_eval weights must sum to 1.0 "
                f"(±{_WEIGHT_SUM_TOLERANCE}); got {total}"
            )


@dataclass
class SubVerdict:
    """Verdict for one sub-eval within a composite.

    Attributes:
        eval_type: Mirrors SubEvalSpec.eval_type.
        eval_id: Mirrors SubEvalSpec.eval_id.
        weight: Mirrors SubEvalSpec.weight.
        must_pass: Mirrors SubEvalSpec.must_pass.
        passed: Result of determine_sub_passed() for this sub-eval.
        normalised_score: Result of normalise_score() — 0.0 to 1.0.
        weighted_contribution: normalised_score * weight, or 0.0 if a
            must_pass sub-eval failed (so it cannot contribute even partial
            credit to the rollup).
        raw_metrics: The sub-snapshot's metrics dict, kept for provenance.
        note: Human-readable summary of the sub-eval outcome.
    """

    eval_type: str
    eval_id: Optional[str]
    weight: float
    must_pass: bool
    passed: bool
    normalised_score: float
    weighted_contribution: float
    raw_metrics: dict
    note: str = ""


@dataclass
class CompositeResult:
    """Result of running a composite eval.

    Attributes:
        weighted_score: Sum of all SubVerdict.weighted_contribution values
            (0.0 to 1.0).
        verdict: One of "pass" | "fail" | "partial".
            - "fail": at least one must_pass sub-eval failed.
            - "pass": all must_pass sub-evals passed AND
              weighted_score >= overall_pass_threshold.
            - "partial": all must_pass sub-evals passed but
              weighted_score < overall_pass_threshold.
        sub_verdicts: Per-sub-eval SubVerdict in spec order.
        sub_snapshots: Full sub-snapshot dicts keyed by
            f"{eval_type}:{eval_id or 'default'}" for downstream embedding.
    """

    weighted_score: float
    verdict: str
    sub_verdicts: list[SubVerdict]
    sub_snapshots: dict


# --- Frontmatter parsing ---


def parse_composite_spec(frontmatter: dict) -> CompositeSpec:
    """Parse a CompositeSpec from IMP frontmatter.

    Expected frontmatter shape (the `eval_type: composite` field is set on
    the IMP itself; this function only reads the sub-eval list):

        sub_evals:
          - eval_type: tool_loop
            eval_id: imp_0014_loop
            weight: 0.6
            must_pass: true
          - eval_type: rubric
            eval_id: imp_0014
            rubric_path: evaluators/rubrics/imp_0014.md
            weight: 0.3
            must_pass: true
          - eval_type: execution_metrics
            weight: 0.1
            must_pass: false
        composite_pass_threshold: 0.7   # optional, defaults to 0.7

    Any sub_eval keys other than {eval_type, eval_id, weight, must_pass} are
    captured into SubEvalSpec.extra so sub-eval-specific config (e.g.
    rubric_path) survives round-trips.

    Args:
        frontmatter: Parsed YAML frontmatter dict.

    Returns:
        A validated CompositeSpec.

    Raises:
        ValueError: If sub_evals is missing, malformed, or fails validation.
    """
    raw_sub_evals = frontmatter.get("sub_evals")
    if not isinstance(raw_sub_evals, list) or not raw_sub_evals:
        raise ValueError(
            "Composite frontmatter must contain a non-empty 'sub_evals' list"
        )

    known_keys = {"eval_type", "eval_id", "weight", "must_pass"}
    sub_evals: list[SubEvalSpec] = []
    for idx, raw in enumerate(raw_sub_evals):
        if not isinstance(raw, dict):
            raise ValueError(
                f"sub_evals[{idx}] must be a mapping, got {type(raw).__name__}"
            )
        if "eval_type" not in raw:
            raise ValueError(f"sub_evals[{idx}] missing required 'eval_type'")
        if "weight" not in raw:
            raise ValueError(f"sub_evals[{idx}] missing required 'weight'")

        extra = {k: v for k, v in raw.items() if k not in known_keys}
        sub_evals.append(
            SubEvalSpec(
                eval_type=str(raw["eval_type"]),
                eval_id=raw.get("eval_id"),
                weight=float(raw["weight"]),
                must_pass=bool(raw.get("must_pass", True)),
                extra=extra,
            )
        )

    threshold = float(frontmatter.get("composite_pass_threshold", 0.7))
    spec = CompositeSpec(sub_evals=sub_evals, overall_pass_threshold=threshold)
    spec.validate()
    return spec


# --- Score normalisation & pass detection ---


def normalise_score(eval_type: str, sub_metrics: dict) -> float:
    """Convert a sub-eval's metrics dict to a 0.0-1.0 normalised score.

    Mapping:
      - structural / tool_loop / subagent_routing / behavioral:
          read sub_metrics['pass_rate'] or sub_metrics['overall_pass_rate']
          (whichever exists). Already 0.0-1.0.
      - rubric:
          read sub_metrics['weighted_score'] on the 1-5 Likert scale and
          normalise via (score - 1) / 4 -> 0.0-1.0. The result is clamped to
          [0.0, 1.0] in case the rubric reports a score slightly outside the
          expected range.
      - execution_metrics:
          1.0 if no regressions, 0.0 if any 'fail'-severity regression,
          0.5 otherwise (warn-only regressions present).

    Args:
        eval_type: One of KNOWN_EVAL_TYPES.
        sub_metrics: The sub-snapshot's metrics dict.

    Returns:
        A normalised score in [0.0, 1.0].

    Raises:
        ValueError: If eval_type is not in KNOWN_EVAL_TYPES.
    """
    if eval_type in _PASS_RATE_TYPES:
        if "pass_rate" in sub_metrics:
            return float(sub_metrics["pass_rate"])
        if "overall_pass_rate" in sub_metrics:
            return float(sub_metrics["overall_pass_rate"])
        return 0.0

    if eval_type == "rubric":
        score = float(sub_metrics.get("weighted_score", 1.0))
        normalised = (score - 1.0) / 4.0
        return max(0.0, min(1.0, normalised))

    if eval_type == "execution_metrics":
        regressions = sub_metrics.get("regressions", []) or []
        if not regressions:
            return 1.0
        if any(
            isinstance(r, dict) and r.get("severity") == "fail"
            for r in regressions
        ):
            return 0.0
        return 0.5

    raise ValueError(
        f"Unknown eval_type {eval_type!r}; expected one of "
        f"{sorted(KNOWN_EVAL_TYPES)}"
    )


def determine_sub_passed(eval_type: str, sub_metrics: dict) -> bool:
    """Decide whether a sub-eval passed, using sub-eval-specific rules.

    Rules:
      - structural / tool_loop / subagent_routing / behavioral:
          sub_metrics['all_passed'] if present, else
          sub_metrics.get('pass_rate', 0) >= 0.95.
      - rubric:
          sub_metrics.get('passed', False) OR weighted_score >= 4.0.
      - execution_metrics:
          True iff no regressions of severity 'fail'.

    Args:
        eval_type: One of KNOWN_EVAL_TYPES.
        sub_metrics: The sub-snapshot's metrics dict.

    Returns:
        True if the sub-eval passed, else False.

    Raises:
        ValueError: If eval_type is not in KNOWN_EVAL_TYPES.
    """
    if eval_type in _PASS_RATE_TYPES:
        if "all_passed" in sub_metrics:
            return bool(sub_metrics["all_passed"])
        return float(sub_metrics.get("pass_rate", 0.0)) >= 0.95

    if eval_type == "rubric":
        if sub_metrics.get("passed", False):
            return True
        return float(sub_metrics.get("weighted_score", 0.0)) >= 4.0

    if eval_type == "execution_metrics":
        regressions = sub_metrics.get("regressions", []) or []
        return not any(
            isinstance(r, dict) and r.get("severity") == "fail"
            for r in regressions
        )

    raise ValueError(
        f"Unknown eval_type {eval_type!r}; expected one of "
        f"{sorted(KNOWN_EVAL_TYPES)}"
    )


# --- Composite execution ---


def _sub_snapshot_key(sub: SubEvalSpec) -> str:
    """Stable dict key for a sub-snapshot: '{eval_type}:{eval_id or default}'."""
    return f"{sub.eval_type}:{sub.eval_id or 'default'}"


def _build_note(
    sub: SubEvalSpec,
    passed: bool,
    normalised: float,
    must_pass_failed: bool,
) -> str:
    """Build a short human-readable summary for a sub-verdict."""
    status = "PASS" if passed else "FAIL"
    suffix = " (must_pass override → 0 contribution)" if must_pass_failed else ""
    return (
        f"{sub.eval_type}"
        f"{':' + sub.eval_id if sub.eval_id else ''}"
        f" {status} score={normalised:.3f} weight={sub.weight}{suffix}"
    )


def run_composite(
    spec: CompositeSpec,
    sub_runner: Callable[[SubEvalSpec], dict],
) -> CompositeResult:
    """Execute every sub-eval and roll up into a single CompositeResult.

    The `sub_runner` callback is provided by the caller (typically
    `runner.imp_runner`). It takes a SubEvalSpec and returns a full
    sub-snapshot dict in the shape ``{meta, metrics, raw_results}``. This
    indirection keeps composite.py free of imports back into imp_runner.py
    (avoiding circular imports) while still letting the caller reuse all
    existing per-eval-type dispatch logic.

    Algorithm:
      1. For each sub_eval in spec.sub_evals:
         - Call sub_runner(sub_eval) to obtain the sub-snapshot.
         - Compute normalised_score and passed via the helpers above.
         - If sub_eval.must_pass and not passed: weighted_contribution = 0,
           else: weighted_contribution = normalised_score * weight.
         - Record a SubVerdict.
      2. weighted_score = sum of weighted_contributions (in [0, 1]).
      3. verdict:
         - "fail" if any must_pass sub-eval failed.
         - "pass" if weighted_score >= spec.overall_pass_threshold.
         - "partial" otherwise.
      4. Build sub_snapshots dict keyed by `_sub_snapshot_key(sub)`.

    Args:
        spec: The validated CompositeSpec to execute.
        sub_runner: Callback that runs a single sub-eval.

    Returns:
        A populated CompositeResult.
    """
    sub_verdicts: list[SubVerdict] = []
    sub_snapshots: dict = {}
    any_must_pass_failed = False

    for sub in spec.sub_evals:
        snapshot = sub_runner(sub)
        sub_metrics = snapshot.get("metrics", {}) if isinstance(snapshot, dict) else {}

        passed = determine_sub_passed(sub.eval_type, sub_metrics)
        normalised = normalise_score(sub.eval_type, sub_metrics)

        must_pass_failed = sub.must_pass and not passed
        if must_pass_failed:
            contribution = 0.0
            any_must_pass_failed = True
        else:
            contribution = normalised * sub.weight

        sub_verdicts.append(
            SubVerdict(
                eval_type=sub.eval_type,
                eval_id=sub.eval_id,
                weight=sub.weight,
                must_pass=sub.must_pass,
                passed=passed,
                normalised_score=normalised,
                weighted_contribution=contribution,
                raw_metrics=sub_metrics,
                note=_build_note(sub, passed, normalised, must_pass_failed),
            )
        )
        sub_snapshots[_sub_snapshot_key(sub)] = snapshot

    weighted_score = sum(v.weighted_contribution for v in sub_verdicts)

    if any_must_pass_failed:
        verdict = "fail"
    elif weighted_score >= spec.overall_pass_threshold:
        verdict = "pass"
    else:
        verdict = "partial"

    return CompositeResult(
        weighted_score=weighted_score,
        verdict=verdict,
        sub_verdicts=sub_verdicts,
        sub_snapshots=sub_snapshots,
    )


# --- Snapshot serialisation ---


def to_snapshot_dict(result: CompositeResult) -> dict:
    """Serialise a CompositeResult to the metrics block of a Snapshot.

    The returned dict is intended to be assigned to ``Snapshot.metrics``.
    The full sub_snapshots dict is deliberately kept SEPARATE — the caller
    (imp_runner.py) places it at the top level of the saved snapshot file
    alongside ``meta``, ``metrics``, and ``raw_results`` so each sub-snapshot
    retains its own provenance block intact.

    Args:
        result: A CompositeResult from run_composite().

    Returns:
        A metrics dict with shape::

            {
              "weighted_score": float,
              "verdict": str,
              "sub_verdicts": {
                "<eval_type>:<eval_id|default>": {
                  "passed": bool,
                  "normalised_score": float,
                  "weighted_contribution": float,
                  "weight": float,
                  "must_pass": bool,
                  "note": str,
                },
                ...
              },
            }
    """
    sub_verdicts: dict[str, dict[str, Any]] = {}
    for v in result.sub_verdicts:
        key = f"{v.eval_type}:{v.eval_id or 'default'}"
        sub_verdicts[key] = {
            "passed": v.passed,
            "normalised_score": v.normalised_score,
            "weighted_contribution": v.weighted_contribution,
            "weight": v.weight,
            "must_pass": v.must_pass,
            "note": v.note,
        }

    return {
        "weighted_score": result.weighted_score,
        "verdict": result.verdict,
        "sub_verdicts": sub_verdicts,
    }


# --- Comparison ---


def compare_composites(pre: dict, post: dict) -> dict:
    """Compare two composite snapshots and return a structured diff.

    `pre` and `post` are full snapshot dicts in the saved-on-disk shape::

        {"meta": {...}, "metrics": {...}, "raw_results": [...],
         "sub_snapshots": {...}}

    Only the ``metrics`` block is needed for the rollup diff; sub_snapshots
    are referenced for per-sub-eval drill-down via the keys recorded on
    ``metrics.sub_verdicts``.

    A composite is considered regressed when either:
      - the post weighted_score is strictly less than the baseline, OR
      - the post verdict is "fail" while the baseline verdict was "pass".

    Args:
        pre: Baseline composite snapshot dict.
        post: Post composite snapshot dict.

    Returns:
        Diff dict with shape::

            {
              "weighted_score": {"baseline": float, "post": float, "delta": float},
              "verdict": {"baseline": str, "post": str},
              "regressed": bool,
              "per_sub_eval": {
                "<eval_type>:<eval_id|default>": {
                  "baseline_passed": bool,
                  "post_passed": bool,
                  "baseline_score": float,
                  "post_score": float,
                  "delta": float,
                  "regressed": bool,
                },
                ...
              },
            }
    """
    pre_metrics = pre.get("metrics", {}) if isinstance(pre, dict) else {}
    post_metrics = post.get("metrics", {}) if isinstance(post, dict) else {}

    pre_score = float(pre_metrics.get("weighted_score", 0.0))
    post_score = float(post_metrics.get("weighted_score", 0.0))
    pre_verdict = str(pre_metrics.get("verdict", "fail"))
    post_verdict = str(post_metrics.get("verdict", "fail"))

    overall_regressed = (
        post_score < pre_score
        or (post_verdict == "fail" and pre_verdict == "pass")
    )

    pre_subs = pre_metrics.get("sub_verdicts", {}) or {}
    post_subs = post_metrics.get("sub_verdicts", {}) or {}

    per_sub_eval: dict[str, dict[str, Any]] = {}
    for key in sorted(set(pre_subs) | set(post_subs)):
        pre_sub = pre_subs.get(key, {}) or {}
        post_sub = post_subs.get(key, {}) or {}

        baseline_passed = bool(pre_sub.get("passed", False))
        post_passed = bool(post_sub.get("passed", False))
        baseline_score = float(pre_sub.get("normalised_score", 0.0))
        post_sub_score = float(post_sub.get("normalised_score", 0.0))
        delta = post_sub_score - baseline_score

        per_sub_eval[key] = {
            "baseline_passed": baseline_passed,
            "post_passed": post_passed,
            "baseline_score": baseline_score,
            "post_score": post_sub_score,
            "delta": delta,
            "regressed": (
                post_sub_score < baseline_score
                or (baseline_passed and not post_passed)
            ),
        }

    return {
        "weighted_score": {
            "baseline": pre_score,
            "post": post_score,
            "delta": post_score - pre_score,
        },
        "verdict": {"baseline": pre_verdict, "post": post_verdict},
        "regressed": overall_regressed,
        "per_sub_eval": per_sub_eval,
    }
