"""Evaluator registry — central dispatch for eval_type -> runner function.

Used by runner.imp_runner.capture_snapshot() to dispatch eval execution and by
runner.composite.run_composite() to invoke sub-evaluators uniformly.

Each runner function has the signature:
    (fm: ImpFrontmatter, ctx: dict) -> Snapshot
returning a fully-built Snapshot (meta + metrics + raw_results [+ sub_snapshots]).

The registry is populated lazily by runner.imp_runner at import time to avoid
circular imports between this package and the runner package.
"""

from typing import Callable

_REGISTRY: dict[str, Callable] = {}


def register(eval_type: str, fn: Callable) -> None:
    """Register a runner function for an eval_type."""
    _REGISTRY[eval_type] = fn


def dispatch(eval_type: str) -> Callable:
    """Look up a runner function. Raises KeyError if eval_type unknown."""
    if eval_type not in _REGISTRY:
        raise KeyError(
            f"Unknown eval_type: {eval_type!r}. "
            f"Registered: {sorted(_REGISTRY.keys())}"
        )
    return _REGISTRY[eval_type]


def known_eval_types() -> list[str]:
    """Return all registered eval_types."""
    return sorted(_REGISTRY.keys())
