"""
IMP-0013 evaluator - validates retro agent wires output into IMP file creation.

Tests:
  1. Retro agent instructions reference IMP file creation
  2. Report format updated: 'Improvements Filed' section replaces 'Action Items'
  3. References _template.md or improvements/README.md for schema
"""

from __future__ import annotations

import re
from pathlib import Path

from evaluators.custom.imp_0004 import ImpResult, ImpReport, _parse_frontmatter


def evaluate_imp_0013(agent_file: Path) -> ImpReport:
    content = agent_file.read_text(encoding="utf-8")
    _frontmatter, body = _parse_frontmatter(content)
    results: list[ImpResult] = []

    # Check 1: IMP file creation rule
    has_imp_creation = bool(re.search(r"(create|generate|produce).*(IMP|improvement).*(file|agents/improvements)", body, re.IGNORECASE))
    results.append(ImpResult(
        imp_id="IMP-0013",
        check_id="imp_creation_rule",
        label="IMP file creation rule in retro instructions",
        passed=has_imp_creation,
        detail="Found" if has_imp_creation else "Missing",
    ))

    # Check 2: Improvements Filed section replaces Action Items
    has_improvements_filed = bool(re.search(r"improvements filed", body, re.IGNORECASE))
    has_action_items = bool(re.search(r"action items", body, re.IGNORECASE))
    # Action Items can appear as context ("replaces Action Items") so just check Improvements Filed exists
    results.append(ImpResult(
        imp_id="IMP-0013",
        check_id="improvements_filed_section",
        label="Report format includes 'Improvements Filed' section",
        passed=has_improvements_filed,
        detail=f"Improvements Filed: {'yes' if has_improvements_filed else 'no'}, Action Items still present: {'yes' if has_action_items else 'no'}",
    ))

    # Check 3: References template or README for schema
    has_template_ref = bool(re.search(r"_template\.md|improvements/README", body, re.IGNORECASE))
    results.append(ImpResult(
        imp_id="IMP-0013",
        check_id="template_reference",
        label="References _template.md or improvements/README.md",
        passed=has_template_ref,
        detail="Found" if has_template_ref else "Missing",
    ))

    passed_count = sum(1 for r in results if r.passed)
    return ImpReport(
        imp_id="IMP-0013",
        title="Wire retro agent output into IMP file creation",
        total_checks=len(results),
        passed_checks=passed_count,
        passed=all(r.passed for r in results),
        results=results,
    )
