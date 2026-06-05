"""
IMP-0006 evaluator — validates QB references BRIEF.md by path, not by content.

Tests:
  1. No "paste BRIEF content" anti-pattern in the Project Context section
  2. Subagent instructions reference BRIEF.md sections by name
  3. Prompt size (informational — for before/after comparison)
"""

from __future__ import annotations

import re
from pathlib import Path

from evaluators.custom.imp_0004 import ImpResult, ImpReport, _parse_frontmatter


# Anti-patterns: lines that tell QB to paste/embed BRIEF content into subagent prompts
# These match affirmative instructions to inline content, NOT prohibitions ("do not paste")
ANTI_PATTERNS = [
    r"(?<!not )reference BRIEF\.md context in your prompts",
    r"(?<!not )(?<!don't )paste BRIEF",
    r"(?<!not )(?<!don't )include BRIEF.*content",
    r"(?<!not )(?<!don't )embed BRIEF",
    r"(?<!not )(?<!don't )copy BRIEF",
]

# Expected pattern: instruct subagents to read BRIEF.md themselves
EXPECTED_PATTERNS = [
    r"(read|cite|reference).*BRIEF\.md.*(section|themselves|directly)",
    r"instruct.*to read.*BRIEF",
    r"do not paste BRIEF content",
]


def evaluate_imp_0006(agent_file: Path) -> ImpReport:
    """
    Run all IMP-0006 acceptance criteria checks against a QB agent file.
    """
    content = agent_file.read_text(encoding="utf-8")
    _frontmatter, body = _parse_frontmatter(content)
    results: list[ImpResult] = []

    # --- Check 1: No anti-pattern in Project Context section ---
    # Extract the "Project Context (BRIEF.md)" section
    context_section = _extract_section(body, "Project Context")
    anti_found = []
    for pattern in ANTI_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            anti_found.extend(matches)

    check1_passed = len(anti_found) == 0
    results.append(ImpResult(
        imp_id="IMP-0006",
        check_id="no_paste_brief_antipattern",
        label="No 'paste BRIEF content into prompts' anti-pattern",
        passed=check1_passed,
        detail=f"Anti-patterns found: {anti_found}" if anti_found else "Clean — no anti-patterns detected",
    ))

    # --- Check 2: Subagent instructions reference sections by name ---
    expected_found = []
    for pattern in EXPECTED_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            expected_found.extend(matches)

    check2_passed = len(expected_found) > 0
    results.append(ImpResult(
        imp_id="IMP-0006",
        check_id="brief_by_reference_present",
        label="Subagent instructions say 'read BRIEF.md themselves'",
        passed=check2_passed,
        detail=f"Found {len(expected_found)} reference-by-path pattern(s)" if expected_found
               else "No reference-by-path patterns found — expected at least one",
    ))

    # --- Check 3: Project Context section updated ---
    has_context_section = context_section is not None and len(context_section.strip()) > 0
    results.append(ImpResult(
        imp_id="IMP-0006",
        check_id="context_section_exists",
        label="Project Context (BRIEF.md) section exists",
        passed=has_context_section,
        detail=f"Section length: {len(context_section)} chars" if has_context_section
               else "Section not found",
    ))

    # --- Check 4: Prompt size (informational) ---
    char_count = len(content)
    results.append(ImpResult(
        imp_id="IMP-0006",
        check_id="prompt_size",
        label=f"Prompt size: {char_count} chars",
        passed=True,  # informational — comparison done externally
        detail=f"total={char_count}",
    ))

    passed_count = sum(1 for r in results if r.passed)
    return ImpReport(
        imp_id="IMP-0006",
        title="Reference BRIEF.md by path, not by content",
        total_checks=len(results),
        passed_checks=passed_count,
        passed=all(r.passed for r in results),
        results=results,
    )


def _extract_section(body: str, heading_prefix: str) -> str | None:
    """Extract a markdown section by heading prefix. Returns content until next ## heading."""
    pattern = rf"^##\s+.*{re.escape(heading_prefix)}.*$"
    match = re.search(pattern, body, re.MULTILINE | re.IGNORECASE)
    if not match:
        return None
    start = match.end()
    # Find next ## heading
    next_heading = re.search(r"^## ", body[start:], re.MULTILINE)
    if next_heading:
        return body[start:start + next_heading.start()]
    return body[start:]
