"""
IMP-0004 evaluator — validates QB tool frontmatter is trimmed and correct.

Tests:
  1. Exactly one `tools:` line in frontmatter
  2. Tool list matches expected minimal orchestration set
  3. No forbidden tools (edit/*, browser/*, notebook/*, etc.)
  4. Prompt token cost reduction vs baseline
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ImpResult:
    """Result of an IMP-specific evaluation."""
    imp_id: str
    check_id: str
    label: str
    passed: bool
    detail: str


@dataclass
class ImpReport:
    """Full evaluation report for a single IMP."""
    imp_id: str
    title: str
    total_checks: int
    passed_checks: int
    passed: bool
    results: list[ImpResult] = field(default_factory=list)


# The expected minimal tool set from IMP-0004 proposal
EXPECTED_TOOLS = {
    "vscode/askQuestions",
    "vscode/memory",
    "agent/runSubagent",
    "read/readFile",
    "search/codebase",
    "search/fileSearch",
    "todo",
    "web/fetch",
    "web/githubRepo",
    "execute/runInTerminal",
}

# Tools that QB's own rules forbid it from using
FORBIDDEN_TOOL_PREFIXES = [
    "edit/",
    "browser/",
    "execute/runNotebookCell",
    "execute/runTests",
    "read/readNotebookCellOutput",
    "read/getNotebookSummary",
    "edit/createJupyterNotebook",
    "edit/editNotebook",
]


def _parse_frontmatter(content: str) -> tuple[str, str]:
    """Split file into frontmatter and body. Returns (frontmatter, body)."""
    if not content.startswith("---"):
        return "", content
    end = content.find("---", 3)
    if end == -1:
        return "", content
    return content[3:end].strip(), content[end + 3:].strip()


def _find_tools_lines(frontmatter: str) -> list[str]:
    """Find all lines that look like tool declarations in frontmatter."""
    tools_lines = []
    for line in frontmatter.splitlines():
        stripped = line.strip()
        # Match `tools:` key or bare bracket list that looks like tools
        if stripped.startswith("tools:") or stripped.startswith("tools :"):
            tools_lines.append(stripped)
        elif stripped.startswith("[") and "/" in stripped and not stripped.startswith("[//"):
            # Bare bracket list with slash-separated tool names (the old duplicate line)
            tools_lines.append(stripped)
    return tools_lines


def _extract_tools(tools_line: str) -> set[str]:
    """Extract tool names from a tools: line."""
    # Remove the `tools:` prefix
    value = re.sub(r"^tools:\s*", "", tools_line)
    # Handle bracket notation or comma-separated
    value = value.strip("[] ")
    tools = {t.strip() for t in value.split(",") if t.strip()}
    return tools


def evaluate_imp_0004(agent_file: Path) -> ImpReport:
    """
    Run all IMP-0004 acceptance criteria checks against a QB agent file.
    """
    content = agent_file.read_text(encoding="utf-8")
    frontmatter, _body = _parse_frontmatter(content)
    results: list[ImpResult] = []

    # --- Check 1: Exactly one tools: line ---
    tools_lines = _find_tools_lines(frontmatter)
    check1_passed = len(tools_lines) == 1
    results.append(ImpResult(
        imp_id="IMP-0004",
        check_id="single_tools_line",
        label="Frontmatter has exactly one tools: line",
        passed=check1_passed,
        detail=f"Found {len(tools_lines)} tools line(s)" + (
            f": {tools_lines}" if not check1_passed else ""
        ),
    ))

    # --- Check 2: Tool list matches expected set ---
    if tools_lines:
        actual_tools = _extract_tools(tools_lines[0])
    else:
        actual_tools = set()

    missing = EXPECTED_TOOLS - actual_tools
    extra = actual_tools - EXPECTED_TOOLS
    check2_passed = missing == set() and extra == set()
    detail_parts = []
    if missing:
        detail_parts.append(f"Missing: {sorted(missing)}")
    if extra:
        detail_parts.append(f"Extra: {sorted(extra)}")
    if not detail_parts:
        detail_parts.append(f"{len(actual_tools)} tools, all expected")

    results.append(ImpResult(
        imp_id="IMP-0004",
        check_id="expected_tool_set",
        label="Tool list contains only orchestration + quality-gate tools",
        passed=check2_passed,
        detail="; ".join(detail_parts),
    ))

    # --- Check 3: No forbidden tools ---
    forbidden_found = []
    for tool in actual_tools:
        for prefix in FORBIDDEN_TOOL_PREFIXES:
            if tool.startswith(prefix):
                forbidden_found.append(tool)
    check3_passed = len(forbidden_found) == 0
    results.append(ImpResult(
        imp_id="IMP-0004",
        check_id="no_forbidden_tools",
        label="No tools QB rules forbid (edit/*, browser/*, notebook/*)",
        passed=check3_passed,
        detail=f"Forbidden tools present: {forbidden_found}" if forbidden_found else "Clean",
    ))

    # --- Check 4: Prompt size (chars as proxy) ---
    # We report the size; the runner script compares pre/post
    char_count = len(content)
    frontmatter_chars = len(frontmatter)
    results.append(ImpResult(
        imp_id="IMP-0004",
        check_id="prompt_size",
        label=f"Prompt size: {char_count} chars (frontmatter: {frontmatter_chars})",
        passed=True,  # informational — comparison done externally
        detail=f"total={char_count}, frontmatter={frontmatter_chars}",
    ))

    passed_count = sum(1 for r in results if r.passed)
    return ImpReport(
        imp_id="IMP-0004",
        title="Trim QB tool frontmatter and fix duplicate tools line",
        total_checks=len(results),
        passed_checks=passed_count,
        passed=all(r.passed for r in results),
        results=results,
    )


def evaluate_imp_0004_baseline(pre_file: Path, post_file: Path) -> ImpReport:
    """
    Compare pre/post QB agent files for IMP-0004 token cost reduction.
    """
    pre_content = pre_file.read_text(encoding="utf-8")
    post_content = post_file.read_text(encoding="utf-8")

    pre_fm, _ = _parse_frontmatter(pre_content)
    post_fm, _ = _parse_frontmatter(post_content)

    pre_tools = _find_tools_lines(pre_fm)
    post_tools = _find_tools_lines(post_fm)

    results: list[ImpResult] = []

    # Tools line count reduction
    results.append(ImpResult(
        imp_id="IMP-0004",
        check_id="tools_line_reduction",
        label="Tools line count reduced",
        passed=len(post_tools) < len(pre_tools),
        detail=f"{len(pre_tools)} -> {len(post_tools)}",
    ))

    # Total char reduction
    delta = len(pre_content) - len(post_content)
    pct = (delta / len(pre_content)) * 100 if pre_content else 0
    results.append(ImpResult(
        imp_id="IMP-0004",
        check_id="char_reduction",
        label=f"Prompt reduced by {delta} chars ({pct:.1f}%)",
        passed=delta > 0,
        detail=f"pre={len(pre_content)}, post={len(post_content)}, delta={delta}",
    ))

    # Frontmatter char reduction
    fm_delta = len(pre_fm) - len(post_fm)
    fm_pct = (fm_delta / len(pre_fm)) * 100 if pre_fm else 0
    results.append(ImpResult(
        imp_id="IMP-0004",
        check_id="frontmatter_reduction",
        label=f"Frontmatter reduced by {fm_delta} chars ({fm_pct:.1f}%)",
        passed=fm_delta > 0,
        detail=f"pre={len(pre_fm)}, post={len(post_fm)}, delta={fm_delta}",
    ))

    # Tool count reduction
    pre_tool_count = sum(len(_extract_tools(t)) for t in pre_tools)
    post_tool_count = sum(len(_extract_tools(t)) for t in post_tools)
    results.append(ImpResult(
        imp_id="IMP-0004",
        check_id="tool_count_reduction",
        label=f"Tool count: {pre_tool_count} -> {post_tool_count}",
        passed=post_tool_count < pre_tool_count,
        detail=f"Removed {pre_tool_count - post_tool_count} tools",
    ))

    passed_count = sum(1 for r in results if r.passed)
    return ImpReport(
        imp_id="IMP-0004",
        title="IMP-0004 pre/post comparison",
        total_checks=len(results),
        passed_checks=passed_count,
        passed=all(r.passed for r in results),
        results=results,
    )
