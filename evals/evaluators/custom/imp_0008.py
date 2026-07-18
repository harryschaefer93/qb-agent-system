"""
IMP-0008 evaluator - validates QB has compact output shape for clean runs.

Tests:
  1. Compact output form documented
  2. Trigger condition for compact form explicit (clean run definition)
"""

from __future__ import annotations

import re
from pathlib import Path

from evaluators.custom.imp_0004 import ImpResult, ImpReport, _parse_frontmatter


def evaluate_imp_0008(agent_file: Path) -> ImpReport:
    content = agent_file.read_text(encoding="utf-8")
    _frontmatter, body = _parse_frontmatter(content)
    results: list[ImpResult] = []

    # Check 1: Compact output form documented
    has_compact = bool(re.search(r"compact.*(form|output|shape)", body, re.IGNORECASE))
    results.append(ImpResult(
        imp_id="IMP-0008",
        check_id="compact_form",
        label="Compact output form documented",
        passed=has_compact,
        detail="Found" if has_compact else "Missing",
    ))

    # Check 2: Trigger condition explicit (clean run = no escalations, no gate bounces, 0 iterations)
    clean_run_terms = ["clean run", "no escalation", "no gate bounce", "0 iteration", "no iteration"]
    found_terms = [t for t in clean_run_terms if re.search(t, body, re.IGNORECASE)]
    has_trigger = len(found_terms) >= 1
    results.append(ImpResult(
        imp_id="IMP-0008",
        check_id="trigger_condition",
        label="Clean-run trigger condition defined",
        passed=has_trigger,
        detail=f"Found terms: {found_terms}" if found_terms else "No clean-run trigger language detected",
    ))

    passed_count = sum(1 for r in results if r.passed)
    return ImpReport(
        imp_id="IMP-0008",
        title="Compact Required Output Shape on fully-clean runs",
        total_checks=len(results),
        passed_checks=passed_count,
        passed=all(r.passed for r in results),
        results=results,
    )
