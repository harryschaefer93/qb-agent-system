"""
IMP-0005 evaluator - validates QB has Session Handoff Protocol section.

Tests:
  1. Session Handoff Protocol section exists
  2. Trigger conditions are explicit with turn/phase counts
  3. Handoff Brief template included
"""

from __future__ import annotations

import re
from pathlib import Path

from evaluators.custom.imp_0004 import ImpResult, ImpReport, _parse_frontmatter


def evaluate_imp_0005(agent_file: Path) -> ImpReport:
    content = agent_file.read_text(encoding="utf-8")
    _frontmatter, body = _parse_frontmatter(content)
    results: list[ImpResult] = []

    # Check 1: Session Handoff Protocol section exists
    has_section = bool(re.search(r"session handoff protocol", body, re.IGNORECASE))
    results.append(ImpResult(
        imp_id="IMP-0005",
        check_id="handoff_section",
        label="Session Handoff Protocol section exists",
        passed=has_section,
        detail="Found" if has_section else "Missing",
    ))

    # Check 2: Trigger conditions with counts
    has_triggers = bool(re.search(r"(more than \d|subagent invocation|iteration.*limit|cycle.*limit|\d.*(invocation|cycle|turn))", body, re.IGNORECASE))
    results.append(ImpResult(
        imp_id="IMP-0005",
        check_id="trigger_conditions",
        label="Trigger conditions use turn/phase counts",
        passed=has_triggers,
        detail="Found" if has_triggers else "No numeric trigger conditions detected",
    ))

    # Check 3: Handoff Brief template
    has_brief = bool(re.search(r"handoff brief", body, re.IGNORECASE))
    brief_fields = ["current task", "decisions made", "files touched", "remaining steps", "next action"]
    found_fields = [f for f in brief_fields if re.search(f, body, re.IGNORECASE)]
    has_template = has_brief and len(found_fields) >= 3
    results.append(ImpResult(
        imp_id="IMP-0005",
        check_id="handoff_template",
        label="Handoff Brief template included",
        passed=has_template,
        detail=f"Brief heading: {'yes' if has_brief else 'no'}, fields: {len(found_fields)}/{len(brief_fields)}",
    ))

    passed_count = sum(1 for r in results if r.passed)
    return ImpReport(
        imp_id="IMP-0005",
        title="Add Session Handoff Protocol to QB",
        total_checks=len(results),
        passed_checks=passed_count,
        passed=all(r.passed for r in results),
        results=results,
    )
