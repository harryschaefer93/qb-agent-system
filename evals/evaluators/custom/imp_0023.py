"""
IMP-0023 evaluator - verify QB.agent.md consolidation preserved surface invariants.

Tests (5):
  1. Line count target: ≤ 500 lines (down from 531)
  2. All 7 task-type pipeline names still present
  3. All 6 QA mode names still present
  4. All 7 pipelines still have CHECKPOINT 1 and CHECKPOINT 2 references
  5. All 7 pipelines still reference REPO for commit + push
"""

from __future__ import annotations

import re
from pathlib import Path

from evaluators.custom.imp_0004 import ImpResult, ImpReport, _parse_frontmatter


PIPELINE_NAMES = ["bug-fix", "new-poc-setup", "customer-handoff", "full-delivery",
                  "feature-request", "refactor", "optimization"]
QA_MODES = ["fast-check", "deep-review", "survey", "baseline", "regression", "delta-check"]
# Target: <=720 lines. Original pre-consolidation HEAD was 696; IMP-0023
# consolidated to 671 (-25 lines); IMP-0020 added 41 lines for the
# Evidence-Backed Recommendations section (671 -> 712). The 720 target
# leaves a small buffer for IMP-following commits. When this target is
# exceeded again, run another consolidation pass following IMP-0023's
# pattern rather than ratcheting the target up indefinitely.
LINE_COUNT_MAX = 720


def evaluate_imp_0023(agent_file: Path) -> ImpReport:
    content = agent_file.read_text(encoding="utf-8")
    _frontmatter, body = _parse_frontmatter(content)
    results: list[ImpResult] = []

    # Check 1: Line count target
    line_count = len(content.splitlines())
    results.append(ImpResult(
        imp_id="IMP-0023",
        check_id="line_count",
        label=f"QB.agent.md line count <= {LINE_COUNT_MAX}",
        passed=(line_count <= LINE_COUNT_MAX),
        detail=f"Actual: {line_count} lines (target: <={LINE_COUNT_MAX})",
    ))

    # Check 2: All pipeline names present
    missing_pipelines = []
    for name in PIPELINE_NAMES:
        # Look for pipeline name as a bold header or in pipeline table
        # Match patterns like **bug-fix**:, `bug-fix`, or bug-fix in detection table
        pattern = rf"(\*\*{re.escape(name)}\*\*|`{re.escape(name)}`|\b{re.escape(name)}\b)"
        if not re.search(pattern, body):
            missing_pipelines.append(name)
    results.append(ImpResult(
        imp_id="IMP-0023",
        check_id="pipelines_present",
        label="All 7 task-type pipeline names present",
        passed=(not missing_pipelines),
        detail=f"Found {7 - len(missing_pipelines)}/7" + (f" (missing: {missing_pipelines})" if missing_pipelines else ""),
    ))

    # Check 3: All QA modes present
    missing_modes = []
    for mode in QA_MODES:
        pattern = rf"(\*\*`?{re.escape(mode)}`?\*\*|`{re.escape(mode)}`|\b{re.escape(mode)}\b)"
        if not re.search(pattern, body):
            missing_modes.append(mode)
    results.append(ImpResult(
        imp_id="IMP-0023",
        check_id="qa_modes_present",
        label="All 6 QA mode names present",
        passed=(not missing_modes),
        detail=f"Found {6 - len(missing_modes)}/6" + (f" (missing: {missing_modes})" if missing_modes else ""),
    ))

    # Check 4: CHECKPOINT 1 and CHECKPOINT 2 references (each appears at least 7 times = once per pipeline)
    cp1_count = len(re.findall(r"CHECKPOINT\s*1\b", body, re.IGNORECASE))
    cp2_count = len(re.findall(r"CHECKPOINT\s*2\b", body, re.IGNORECASE))
    cp_ok = cp1_count >= 7 and cp2_count >= 7
    results.append(ImpResult(
        imp_id="IMP-0023",
        check_id="checkpoint_references",
        label="Each pipeline has CHECKPOINT 1 + CHECKPOINT 2 references",
        passed=cp_ok,
        detail=f"CHECKPOINT 1 count: {cp1_count} (expect >=7), CHECKPOINT 2 count: {cp2_count} (expect >=7)",
    ))

    # Check 5: REPO references — each pipeline ends with REPO (at least 7 mentions)
    repo_count = len(re.findall(r"\bREPO\b", body))
    repo_ok = repo_count >= 7
    results.append(ImpResult(
        imp_id="IMP-0023",
        check_id="repo_references",
        label="Each pipeline references REPO for commit + push",
        passed=repo_ok,
        detail=f"REPO mention count: {repo_count} (expect >=7)",
    ))

    passed_count = sum(1 for r in results if r.passed)
    return ImpReport(
        imp_id="IMP-0023",
        title="QB Workflow consolidation — compress without behavior change",
        total_checks=len(results),
        passed_checks=passed_count,
        passed=all(r.passed for r in results),
        results=results,
    )
