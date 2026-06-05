"""
IMP-0002 evaluator - validates QB documents session memory scratchpad convention.

Tests:
  1. Scratchpad convention section exists in QB
  2. References /memories/session/ or scratchpad naming
  3. At least one workflow step references reading scratchpad
"""

from __future__ import annotations

import re
from pathlib import Path

from evaluators.custom.imp_0004 import ImpResult, ImpReport, _parse_frontmatter


def evaluate_imp_0002(agent_file: Path) -> ImpReport:
    content = agent_file.read_text(encoding="utf-8")
    _frontmatter, body = _parse_frontmatter(content)
    results: list[ImpResult] = []

    # Check 1: Scratchpad convention documented
    has_scratchpad = bool(re.search(r"scratchpad", body, re.IGNORECASE))
    results.append(ImpResult(
        imp_id="IMP-0002",
        check_id="scratchpad_convention",
        label="Scratchpad convention documented",
        passed=has_scratchpad,
        detail="Found" if has_scratchpad else "Missing",
    ))

    # Check 2: References session memory path
    has_session_ref = bool(re.search(r"/memories/session/", body))
    results.append(ImpResult(
        imp_id="IMP-0002",
        check_id="session_memory_path",
        label="References /memories/session/ path",
        passed=has_session_ref,
        detail="Found" if has_session_ref else "Missing",
    ))

    # Check 3: Workflow step references reading scratchpad
    has_read_ref = bool(re.search(r"read.*(scratchpad|session.?memory)|scratchpad.*read", body, re.IGNORECASE))
    results.append(ImpResult(
        imp_id="IMP-0002",
        check_id="read_scratchpad_ref",
        label="Workflow references reading scratchpad instead of re-pasting",
        passed=has_read_ref,
        detail="Found" if has_read_ref else "No read-scratchpad reference detected",
    ))

    passed_count = sum(1 for r in results if r.passed)
    return ImpReport(
        imp_id="IMP-0002",
        title="Externalize QB session state to memory scratchpad",
        total_checks=len(results),
        passed_checks=passed_count,
        passed=all(r.passed for r in results),
        results=results,
    )
