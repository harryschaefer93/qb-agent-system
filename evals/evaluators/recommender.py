"""
Recommendation engine — maps eval failures to actionable agent prompt changes.

Analyzes behavioral eval results, identifies failure patterns, reads the
agent definition, and generates specific prompt recommendations with rationale.

The output is a structured recommendations file the user can approve/reject.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class Recommendation:
    """A single recommended change to an agent definition."""
    id: str
    priority: str  # P0, P1, P2
    category: str  # e.g., "checkpoint-compliance", "delegation", "architecture-decisions"
    title: str
    rationale: str  # Why this change is needed, grounded in eval data
    evidence: list[str]  # Specific test cases that triggered this
    current_behavior: str  # What the agent does now (from eval failures)
    proposed_change: str  # What to change in the agent definition
    agent_file_section: str  # Which section of the agent file to modify
    status: str = "pending"  # pending, approved, rejected, applied


@dataclass
class RecommendationReport:
    """Full recommendation report for an agent."""
    agent: str
    generated_at: str
    eval_run_id: str
    total_recommendations: int
    recommendations: list[Recommendation]
    summary: str


# --- Failure-to-recommendation mapping rules ---

# Each rule maps a behavioral check failure pattern to a recommendation template.
# Rules are ordered by priority.

RECOMMENDATION_RULES: list[dict] = [
    {
        "check_id": "asks_before_qa",
        "priority": "P0",
        "category": "checkpoint-compliance",
        "title": "Add/strengthen Checkpoint 1 (pre-QA clarification)",
        "rationale_template": (
            "The agent invoked QA without first confirming scope with the user. "
            "This was observed in {failure_count} test case(s): {test_ids}. "
            "Users lose control when the agent starts investigating before "
            "confirming what to investigate."
        ),
        "proposed_change_template": (
            "Add or strengthen a mandatory pre-investigation checkpoint. Before "
            "invoking any diagnostic or analysis agent, the agent MUST call "
            "`askQuestions` to confirm:\n"
            "  - What the user wants investigated\n"
            "  - The scope of investigation (narrow vs. broad)\n"
            "  - Any constraints or priorities\n"
            "Add phrasing: 'Before invoking [analysis agent], call askQuestions "
            "with 1-3 options to confirm scope. Do NOT proceed until the user responds.'"
        ),
        "section": "Checkpoint / Approval Gate rules",
    },
    {
        "check_id": "asks_before_impl",
        "priority": "P0",
        "category": "checkpoint-compliance",
        "title": "Add/strengthen Checkpoint 2 (pre-implementation approval)",
        "rationale_template": (
            "The agent proceeded to implementation without user approval. "
            "This was observed in {failure_count} test case(s): {test_ids}. "
            "Implementation without approval can waste time on wrong approaches "
            "and is the most common user complaint."
        ),
        "proposed_change_template": (
            "Add a HARD STOP approval gate before any implementation action. "
            "The agent MUST call `askQuestions` with:\n"
            "  - Summary of findings and proposed plan\n"
            "  - Options: Approve / Modify scope / Cancel\n"
            "  - `recommended: true` on the suggested option\n"
            "  - `allowFreeformInput: true`\n"
            "Add phrasing: 'You MUST NOT invoke any implementation agent until "
            "the user responds to this checkpoint. Presenting the plan in chat "
            "text is NOT sufficient — you must call askQuestions and wait.'"
        ),
        "section": "Checkpoint / Approval Gate rules",
    },
    {
        "check_id": "no_self_investigate",
        "priority": "P0",
        "category": "delegation",
        "title": "Enforce delegation — agent should not investigate code itself",
        "rationale_template": (
            "The agent searched/read code itself instead of delegating to the "
            "appropriate specialist agent. This was observed in {failure_count} "
            "test case(s): {test_ids}. When orchestrator agents self-investigate, "
            "they bypass checkpoints and start making decisions autonomously."
        ),
        "proposed_change_template": (
            "Add explicit anti-pattern rules:\n"
            "  - 'Do NOT search the codebase, read files, or analyze code — "
            "that is [specialist agent]'s job.'\n"
            "  - 'If you find yourself reading a file to understand the problem, "
            "STOP — invoke [specialist agent] instead.'\n"
            "Consider removing code search/read tools from the agent's tool list "
            "to eliminate the temptation."
        ),
        "section": "Role boundaries / Delegation rules",
    },
    {
        "check_id": "no_arch_decision",
        "priority": "P1",
        "category": "architecture-decisions",
        "title": "Prevent unilateral architecture decisions",
        "rationale_template": (
            "The agent made architecture or technology decisions without "
            "presenting options to the user. This was observed in {failure_count} "
            "test case(s): {test_ids}. Architecture decisions have long-term "
            "consequences and should always involve user input."
        ),
        "proposed_change_template": (
            "Add an anti-pattern section listing specific violations:\n"
            "  - 'Do NOT choose a technology (e.g., database, cache, auth provider) "
            "without presenting options via askQuestions.'\n"
            "  - 'If there are multiple valid approaches, present them as options "
            "with trade-offs described in the description field.'\n"
            "  - 'Phrases like \"I\\'ll use X\" or \"let\\'s go with Y\" without "
            "prior user approval are violations.'"
        ),
        "section": "Anti-patterns / Decision boundaries",
    },
    {
        "check_id": "uses_ask_questions",
        "priority": "P1",
        "category": "interaction-style",
        "title": "Use askQuestions tool instead of inline chat questions",
        "rationale_template": (
            "The agent asked questions as inline chat text instead of using the "
            "`askQuestions` tool. This was observed in {failure_count} test case(s): "
            "{test_ids}. Inline questions don't provide selectable options and "
            "can be missed or misinterpreted."
        ),
        "proposed_change_template": (
            "Add interaction style rules:\n"
            "  - 'Always use `askQuestions` for user input — never embed questions "
            "as inline chat text.'\n"
            "  - 'For decisions with options: present analysis in chat, then call "
            "askQuestions with selectable options.'\n"
            "  - 'Chat text is NOT a checkpoint; only askQuestions counts as a "
            "proper user input gate.'"
        ),
        "section": "User Interaction Style",
    },
]

# --- Cross-cutting pattern rules (triggered by combinations of failures) ---

PATTERN_RULES: list[dict] = [
    {
        "pattern": "all_checks_fail",
        "condition": lambda failures: any(
            f["failed_count"] == f["total_count"] for f in failures
        ),
        "priority": "P0",
        "category": "fundamental",
        "title": "Agent has no checkpoint behavior — needs full checkpoint framework",
        "rationale": (
            "Some test cases failed ALL behavioral checks, indicating the agent "
            "has no checkpoint/approval behavior at all. This requires adding a "
            "complete checkpoint framework, not just individual fixes."
        ),
        "proposed_change": (
            "Add a '⛔ BEFORE YOU DO ANYTHING' preamble at the TOP of the agent "
            "definition with self-diagnostic questions:\n"
            "  1. Have I confirmed what the user actually wants?\n"
            "  2. Am I about to make a decision the user should make?\n"
            "  3. Is there more than one valid way to do this?\n"
            "  4. Am I assuming scope that wasn't explicitly stated?\n"
            "Follow with: 'Your default state is PAUSED, waiting for input. "
            "You must earn the right to proceed by getting explicit user approval "
            "at each checkpoint.'"
        ),
        "section": "Top of agent definition (preamble)",
    },
    {
        "pattern": "category_failure",
        "condition": lambda failures: any(
            f.get("category_pass_rate", 1.0) < 0.5 for f in failures
        ),
        "priority": "P0",
        "category": "category-specific",
        "title": "Agent fails consistently for specific task categories",
        "rationale": (
            "The agent has a significantly lower pass rate for certain task "
            "categories, suggesting the checkpoint rules have category-specific "
            "gaps or escape hatches."
        ),
        "proposed_change": (
            "Review the agent's workflow section for the failing task categories. "
            "Ensure each category's workflow explicitly includes checkpoint gates. "
            "Remove any 'trivial' or 'obvious' escape hatches that let the agent "
            "skip checkpoints for that category."
        ),
        "section": "Workflow / Task-type-specific rules",
    },
]


def generate_recommendations(
    eval_results_path: Path,
    agent_definition_path: Optional[Path] = None,
) -> RecommendationReport:
    """
    Analyze eval results and generate recommendations.

    Args:
        eval_results_path: Path to a behavioral eval results JSON file.
        agent_definition_path: Optional path to the agent .md file for context.
    """
    with open(eval_results_path, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    agent_name = eval_data.get("agent", "unknown")
    run_id = eval_data.get("run_id", "unknown")
    results = eval_data.get("results", [])

    # Aggregate failures by check type
    check_failures: dict[str, dict] = {}
    for r in results:
        for check in r.get("checks", []):
            cid = check["check_id"]
            if cid not in check_failures:
                check_failures[cid] = {
                    "total": 0,
                    "failed": 0,
                    "test_ids": [],
                    "evidence": [],
                }
            check_failures[cid]["total"] += 1
            if not check["passed"]:
                check_failures[cid]["failed"] += 1
                check_failures[cid]["test_ids"].append(r["test_id"])
                check_failures[cid]["evidence"].append(check.get("evidence", ""))

    # Aggregate by category
    category_stats: dict[str, dict] = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "passed": 0}
        category_stats[cat]["total"] += 1
        if r["passed"]:
            category_stats[cat]["passed"] += 1
    for data in category_stats.values():
        data["pass_rate"] = data["passed"] / data["total"] if data["total"] > 0 else 0.0

    # Read agent definition for context
    agent_content = ""
    if agent_definition_path and agent_definition_path.exists():
        agent_content = agent_definition_path.read_text(encoding="utf-8", errors="replace")

    recommendations: list[Recommendation] = []
    rec_counter = 0

    # Generate recommendations from check-level failures
    for rule in RECOMMENDATION_RULES:
        cid = rule["check_id"]
        if cid in check_failures and check_failures[cid]["failed"] > 0:
            failure_data = check_failures[cid]
            rec_counter += 1

            rationale = rule["rationale_template"].format(
                failure_count=failure_data["failed"],
                test_ids=", ".join(failure_data["test_ids"]),
            )

            # Check if the agent definition already has relevant content
            current_behavior = _detect_existing_rules(agent_content, cid)

            recommendations.append(Recommendation(
                id=f"REC-{rec_counter:03d}",
                priority=rule["priority"],
                category=rule["category"],
                title=rule["title"],
                rationale=rationale,
                evidence=failure_data["test_ids"],
                current_behavior=current_behavior,
                proposed_change=rule["proposed_change_template"],
                agent_file_section=rule["section"],
            ))

    # Generate recommendations from cross-cutting patterns
    failure_summary = []
    for r in results:
        failed_checks = [c for c in r.get("checks", []) if not c["passed"]]
        if failed_checks:
            failure_summary.append({
                "test_id": r["test_id"],
                "category": r.get("category", "unknown"),
                "failed_count": len(failed_checks),
                "total_count": r["total_checks"],
                "category_pass_rate": category_stats.get(
                    r.get("category", "unknown"), {}
                ).get("pass_rate", 1.0),
            })

    for prule in PATTERN_RULES:
        if failure_summary and prule["condition"](failure_summary):
            rec_counter += 1
            recommendations.append(Recommendation(
                id=f"REC-{rec_counter:03d}",
                priority=prule["priority"],
                category=prule["category"],
                title=prule["title"],
                rationale=prule["rationale"],
                evidence=[f["test_id"] for f in failure_summary],
                current_behavior="See eval results for details.",
                proposed_change=prule["proposed_change"],
                agent_file_section=prule["section"],
            ))

    # Sort by priority
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    recommendations.sort(key=lambda r: priority_order.get(r.priority, 99))

    # Generate summary
    overall_pass_rate = eval_data.get("summary", {}).get("pass_rate", 0)
    if not recommendations:
        summary = (
            f"✅ No recommendations — {agent_name} passed all behavioral checks "
            f"({overall_pass_rate:.0%} compliance). The current agent definition "
            f"produces correct checkpoint behavior across all tested categories."
        )
    else:
        p0_count = sum(1 for r in recommendations if r.priority == "P0")
        p1_count = sum(1 for r in recommendations if r.priority == "P1")
        summary = (
            f"⚠️ {len(recommendations)} recommendation(s) generated for {agent_name} "
            f"({overall_pass_rate:.0%} compliance). "
            f"{p0_count} critical (P0), {p1_count} important (P1). "
            f"Review and approve/reject each recommendation, then re-run evals to verify."
        )

    return RecommendationReport(
        agent=agent_name,
        generated_at=datetime.now(timezone.utc).isoformat(),
        eval_run_id=run_id,
        total_recommendations=len(recommendations),
        recommendations=recommendations,
        summary=summary,
    )


def format_recommendations_markdown(report: RecommendationReport) -> str:
    """Format a recommendation report as markdown for user review."""
    lines = [
        f"# Agent Recommendations: {report.agent}",
        "",
        f"**Generated:** {report.generated_at}",
        f"**Eval Run:** {report.eval_run_id}",
        f"**Recommendations:** {report.total_recommendations}",
        "",
        f"## Summary",
        "",
        report.summary,
        "",
    ]

    if not report.recommendations:
        lines.append("No changes needed. 🎉")
        return "\n".join(lines)

    lines.append("## Recommendations")
    lines.append("")
    lines.append("Review each recommendation below. Mark as `approved`, `rejected`, or add feedback.")
    lines.append("")

    for rec in report.recommendations:
        lines.extend([
            f"### {rec.id}: {rec.title}",
            "",
            f"**Priority:** {rec.priority} | **Category:** {rec.category} | **Status:** `{rec.status}`",
            "",
            f"**Rationale:**",
            rec.rationale,
            "",
            f"**Evidence (failing test cases):** {', '.join(rec.evidence)}",
            "",
            f"**Current behavior in agent definition:**",
            rec.current_behavior,
            "",
            f"**Proposed change:**",
            rec.proposed_change,
            "",
            f"**Target section:** {rec.agent_file_section}",
            "",
            "---",
            "",
        ])

    lines.extend([
        "## Workflow",
        "",
        "1. Review each recommendation above",
        "2. Update the `status` field to `approved` or `rejected` (with optional notes)",
        "3. Run: `python -m runner.cli apply-recommendations <this-file>` (coming soon)",
        "4. Re-run evals: `python -m runner.cli run-behavioral` to verify changes",
        "",
    ])

    return "\n".join(lines)


def save_recommendations(report: RecommendationReport, output_path: Path) -> None:
    """Save recommendations as both markdown (for review) and JSON (for tooling)."""
    # Save markdown for human review
    md_path = output_path.with_suffix(".md")
    md_path.write_text(format_recommendations_markdown(report), encoding="utf-8")

    # Save JSON for programmatic access
    json_path = output_path.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "agent": report.agent,
            "generated_at": report.generated_at,
            "eval_run_id": report.eval_run_id,
            "total_recommendations": report.total_recommendations,
            "summary": report.summary,
            "recommendations": [
                {
                    "id": r.id,
                    "priority": r.priority,
                    "category": r.category,
                    "title": r.title,
                    "rationale": r.rationale,
                    "evidence": r.evidence,
                    "current_behavior": r.current_behavior,
                    "proposed_change": r.proposed_change,
                    "agent_file_section": r.agent_file_section,
                    "status": r.status,
                }
                for r in report.recommendations
            ],
        }, f, indent=2)


# --- Helpers ---

def _detect_existing_rules(agent_content: str, check_id: str) -> str:
    """Detect if the agent definition already has rules for a given check type."""
    if not agent_content:
        return "Agent definition not available for analysis."

    detectors = {
        "asks_before_qa": [
            r"(?i)checkpoint\s*1",
            r"(?i)pre-QA",
            r"(?i)before.*invoking.*QA",
            r"(?i)askQuestions.*before.*QA",
        ],
        "asks_before_impl": [
            r"(?i)checkpoint\s*2",
            r"(?i)approval\s*gate",
            r"(?i)HARD\s*STOP",
            r"(?i)before.*implementation",
            r"(?i)MUST NOT invoke (Dev|Infra)",
        ],
        "no_self_investigate": [
            r"(?i)do not.*search.*codebase",
            r"(?i)do not.*read.*files",
            r"(?i)do not.*analyze.*code",
            r"(?i)that is QA",
        ],
        "no_arch_decision": [
            r"(?i)do not.*make.*architecture",
            r"(?i)present.*options",
            r"(?i)anti.?pattern",
        ],
        "uses_ask_questions": [
            r"(?i)always use.*askQuestions",
            r"(?i)never.*inline.*chat.*text",
            r"(?i)chat text.*NOT.*checkpoint",
        ],
    }

    patterns = detectors.get(check_id, [])
    found_rules = []
    for pattern in patterns:
        match = re.search(pattern, agent_content)
        if match:
            # Extract surrounding context (±50 chars)
            start = max(0, match.start() - 50)
            end = min(len(agent_content), match.end() + 50)
            context = agent_content[start:end].replace("\n", " ").strip()
            found_rules.append(f"...{context}...")

    if found_rules:
        return (
            "Agent definition already contains related rules, but they may need "
            "strengthening:\n" + "\n".join(f"  - {r}" for r in found_rules[:3])
        )
    else:
        return "No existing rules found for this check in the agent definition."
