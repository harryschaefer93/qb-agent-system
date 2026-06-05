"""
Structure evaluators — validate agent output conforms to expected shapes.

Each evaluator checks structural compliance for a specific agent's output
format. Returns pass/fail with details on which sections are present/missing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class StructureResult:
    """Result of a structure evaluation."""
    agent: str
    evaluator: str
    passed: bool
    total_checks: int
    passed_checks: int
    details: list[dict] = field(default_factory=list)  # {check, passed, note}


def evaluate_brief_structure(content: str) -> StructureResult:
    """
    POC-scoper: Validate BRIEF.md contains all 9 required sections.
    """
    required_sections = [
        ("Executive Summary", r"(?i)##?\s*executive\s+summary"),
        ("Customer Context", r"(?i)##?\s*customer\s+context"),
        ("POC Scope", r"(?i)##?\s*poc\s+scope"),
        ("Objectives", r"(?i)##?\s*objectives"),
        ("Success Criteria", r"(?i)##?\s*success\s+criteria"),
        ("Acceptance Criteria", r"(?i)##?\s*acceptance\s+criteria"),
        ("Architecture Guidance", r"(?i)##?\s*architecture\s+guidance"),
        ("Risks & Mitigations", r"(?i)##?\s*risks?\s*[&and]+\s*mitigations?"),
        ("Next Steps", r"(?i)##?\s*next\s+steps"),
    ]

    details = []
    passed_count = 0

    for section_name, pattern in required_sections:
        found = bool(re.search(pattern, content))
        if found:
            passed_count += 1
        details.append({
            "check": f"Section: {section_name}",
            "passed": found,
            "note": "present" if found else "MISSING",
        })

    # Additional checks
    # Has IN scope / OUT of scope in POC Scope section
    has_in_scope = bool(re.search(r"(?i)(in\s+scope|in-scope)", content))
    has_out_scope = bool(re.search(r"(?i)(out\s+of\s+scope|out-of-scope)", content))
    scope_detail = has_in_scope and has_out_scope
    if scope_detail:
        passed_count += 1
    details.append({
        "check": "POC Scope has IN/OUT scope delineation",
        "passed": scope_detail,
        "note": "present" if scope_detail else "MISSING — should have explicit IN scope and OUT of scope",
    })

    total = len(details)
    return StructureResult(
        agent="poc-scoper",
        evaluator="brief_structure",
        passed=passed_count == total,
        total_checks=total,
        passed_checks=passed_count,
        details=details,
    )


def evaluate_qb_output_structure(content: str) -> StructureResult:
    """
    QB: Validate output matches the required QB Result format.
    """
    required_fields = [
        ("QB Result header", r"(?i)##?\s*QB\s+Result"),
        ("Task Type", r"(?i)Task\s+Type:\s*(bug-fix|new-poc-setup|customer-handoff|full-delivery)"),
        ("Classification", r"(?i)Classification:\s*(app-code|infra|mixed|n/a)"),
        ("Scope", r"(?i)Scope:\s*(trivial|small|medium|large|n/a)"),
        ("Root Cause section", r"(?i)##?\s*Root\s+Cause"),
        ("Routing Plan section", r"(?i)##?\s*Routing\s+Plan"),
        ("Quality Gates section", r"(?i)##?\s*Quality\s+Gates"),
        ("Validation section", r"(?i)##?\s*Validation"),
        ("Diagrams section", r"(?i)##?\s*Diagrams"),
        ("Documentation section", r"(?i)##?\s*Documentation"),
        ("Escalation section", r"(?i)##?\s*Escalation"),
        ("Risks section", r"(?i)##?\s*Risks"),
    ]

    details = []
    passed_count = 0

    for field_name, pattern in required_fields:
        found = bool(re.search(pattern, content))
        if found:
            passed_count += 1
        details.append({
            "check": field_name,
            "passed": found,
            "note": "present" if found else "MISSING",
        })

    total = len(details)
    return StructureResult(
        agent="qb",
        evaluator="qb_output_structure",
        passed=passed_count == total,
        total_checks=total,
        passed_checks=passed_count,
        details=details,
    )


def evaluate_triage_categorization(content: str) -> StructureResult:
    """
    Inbox-triage: Validate triage output has proper categorization.
    """
    expected_categories = [
        ("DELETE category", r"(?i)(🗑️|DELETE|delete)"),
        ("ARCHIVE category", r"(?i)(📁|ARCHIVE|archive)"),
        ("NEEDS RESPONSE category", r"(?i)(📬|NEEDS\s+RESPONSE|needs\s+response)"),
    ]

    priority_indicators = [
        ("Has priority indicators", r"(🔴|🟡|🟢|HIGH|MEDIUM|LOW)"),
    ]

    details = []
    passed_count = 0

    for check_name, pattern in expected_categories + priority_indicators:
        found = bool(re.search(pattern, content))
        if found:
            passed_count += 1
        details.append({
            "check": check_name,
            "passed": found,
            "note": "present" if found else "MISSING",
        })

    # Check for confirmation prompt (should never auto-execute)
    has_confirmation = bool(re.search(
        r"(?i)(confirm|approve|proceed|go ahead|shall I|ready to)",
        content
    ))
    if has_confirmation:
        passed_count += 1
    details.append({
        "check": "Asks for confirmation before executing",
        "passed": has_confirmation,
        "note": "present" if has_confirmation else "MISSING — should ask before deleting/archiving",
    })

    total = len(details)
    return StructureResult(
        agent="inbox-triage",
        evaluator="triage_categorization",
        passed=passed_count == total,
        total_checks=total,
        passed_checks=passed_count,
        details=details,
    )


def evaluate_iac_structure(content: str, iac_type: str = "bicep") -> StructureResult:
    """
    Infra: Validate IaC output has required patterns.
    """
    if iac_type == "bicep":
        checks = [
            ("Has param decorator or param keyword", r"(?i)(param\s+\w+|@description)"),
            ("Has resource declarations", r"(?i)resource\s+\w+"),
            ("Has output declarations", r"(?i)output\s+\w+"),
            ("Uses managed identity pattern", r"(?i)(managedIdentit|identity|systemAssigned|userAssigned)"),
            ("Has resource tags", r"(?i)tags:\s*\{"),
            ("Parameterizes location", r"(?i)param\s+location"),
        ]
    else:  # terraform
        checks = [
            ("Has variable blocks", r'(?i)variable\s+"'),
            ("Has resource blocks", r'(?i)resource\s+"'),
            ("Has output blocks", r'(?i)output\s+"'),
            ("Uses managed identity", r"(?i)(identity\s*\{|managed_identity)"),
            ("Has tags", r'(?i)tags\s*=\s*\{'),
            ("Parameterizes location", r'(?i)variable\s+"location"'),
        ]

    details = []
    passed_count = 0

    for check_name, pattern in checks:
        found = bool(re.search(pattern, content))
        if found:
            passed_count += 1
        details.append({
            "check": check_name,
            "passed": found,
            "note": "present" if found else "MISSING",
        })

    total = len(details)
    return StructureResult(
        agent="infra",
        evaluator=f"iac_structure_{iac_type}",
        passed=passed_count == total,
        total_checks=total,
        passed_checks=passed_count,
        details=details,
    )
