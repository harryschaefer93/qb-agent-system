"""
IMP-0003 evaluator - validates QB has Context Checkpoints section.

Tests:
  1. Context Checkpoints section exists
  2. Checkpoint block format is templated
  3. Lists specific checkpoint events (QA phase, gates, iteration, etc.)
"""

from __future__ import annotations

import re
from pathlib import Path

from evaluators.custom.imp_0004 import ImpResult, ImpReport, _parse_frontmatter


def evaluate_imp_0003(agent_file: Path) -> ImpReport:
    content = agent_file.read_text(encoding="utf-8")
    _frontmatter, body = _parse_frontmatter(content)
    results: list[ImpResult] = []

    # Check 1: Context Checkpoints section exists
    has_section = bool(re.search(r"context checkpoint", body, re.IGNORECASE))
    results.append(ImpResult(
        imp_id="IMP-0003",
        check_id="checkpoint_section",
        label="Context Checkpoints section exists",
        passed=has_section,
        detail="Found" if has_section else "Missing",
    ))

    # Check 2: Checkpoint block format templated
    has_template = bool(re.search(r"(checkpoint|##\s*checkpoint)", body, re.IGNORECASE))
    results.append(ImpResult(
        imp_id="IMP-0003",
        check_id="checkpoint_template",
        label="Checkpoint block format defined",
        passed=has_template,
        detail="Found" if has_template else "Missing",
    ))

    # Check 3: Lists checkpoint trigger events
    events = ["qa.*complete", "quality.*gate", "iteration.*complete", "diagram.*complete", "merge.*gate"]
    found_events = [e for e in events if re.search(e, body, re.IGNORECASE)]
    has_events = len(found_events) >= 3
    results.append(ImpResult(
        imp_id="IMP-0003",
        check_id="checkpoint_events",
        label="Lists checkpoint trigger events",
        passed=has_events,
        detail=f"Found {len(found_events)}/{len(events)} expected events",
    ))

    passed_count = sum(1 for r in results if r.passed)
    return ImpReport(
        imp_id="IMP-0003",
        title="Add Context Checkpoints to QB pipeline",
        total_checks=len(results),
        passed_checks=passed_count,
        passed=all(r.passed for r in results),
        results=results,
    )
