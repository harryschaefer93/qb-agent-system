"""
Behavioral evaluator — tests whether agents respect checkpoint and approval gates.

Analyzes agent response text for patterns indicating:
- Did the agent ask for user input before acting?
- Did the agent avoid making decisions the user should make?
- Did the agent delegate investigation instead of doing it itself?

Designed primarily for QB but extensible to other agents with checkpoint rules.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BehavioralCheck:
    """A single behavioral check result."""
    check_id: str
    label: str
    passed: bool
    evidence: str  # What pattern was found/not found


@dataclass
class BehavioralResult:
    """Result of a behavioral evaluation for a single test case."""
    test_id: str
    category: str
    prompt: str
    passed: bool
    total_checks: int
    passed_checks: int
    checks: list[BehavioralCheck] = field(default_factory=list)


@dataclass
class BehavioralSummary:
    """Aggregate behavioral eval metrics."""
    total_cases: int
    passed_cases: int
    pass_rate: float
    by_category: dict[str, dict]  # category -> {total, passed, pass_rate}
    by_check: dict[str, dict]  # check_id -> {total, passed, pass_rate}
    failures: list[dict] = field(default_factory=list)


def load_behavioral_dataset(dataset_path: Path) -> dict:
    """Load a behavioral test dataset."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_qb_behavior(response: str, test_case: dict) -> BehavioralResult:
    """
    Evaluate a QB response against behavioral expectations.

    Checks whether the response shows proper checkpoint compliance:
    pausing to ask, not self-investigating, not making architecture
    decisions, etc.

    Args:
        response: The full QB response text (including any tool calls
                  serialized as text, e.g. from VS Code agent output).
        test_case: A single test case from behavioral.json.
    """
    expected = test_case.get("expected_behavior", {})
    checks: list[BehavioralCheck] = []

    if expected.get("must_ask_before_qa", False):
        checks.append(_check_asks_before_qa(response))

    if expected.get("must_ask_before_implementation", False):
        checks.append(_check_asks_before_implementation(response))

    if expected.get("must_not_self_investigate", False):
        checks.append(_check_not_self_investigating(response))

    if expected.get("must_not_decide_architecture", False):
        checks.append(_check_not_deciding_architecture(response))

    if expected.get("must_use_ask_questions", False):
        checks.append(_check_uses_ask_questions(response))

    if expected.get("must_invoke_arch_before_approval", False):
        checks.append(_check_invokes_arch_before_approval(response))

    if expected.get("must_invoke_repo_for_push", False):
        checks.append(_check_invokes_repo_for_push(response))

    if expected.get("must_fan_out_dev_when_tracks", False):
        checks.append(_check_fans_out_dev(response))

    if expected.get("must_not_decide_architecture_alone", False):
        checks.append(_check_delegates_arch_to_arch_agent(response))

    passed_count = sum(1 for c in checks if c.passed)
    total = len(checks)

    return BehavioralResult(
        test_id=test_case["id"],
        category=test_case.get("category", "unknown"),
        prompt=test_case["prompt"],
        passed=passed_count == total,
        total_checks=total,
        passed_checks=passed_count,
        checks=checks,
    )


def compute_behavioral_summary(results: list[BehavioralResult]) -> BehavioralSummary:
    """Compute aggregate behavioral eval metrics."""
    if not results:
        return BehavioralSummary(
            total_cases=0, passed_cases=0, pass_rate=0.0,
            by_category={}, by_check={},
        )

    total = len(results)
    passed = sum(1 for r in results if r.passed)

    # By category
    by_category: dict[str, dict] = {}
    for r in results:
        cat = r.category
        if cat not in by_category:
            by_category[cat] = {"total": 0, "passed": 0}
        by_category[cat]["total"] += 1
        if r.passed:
            by_category[cat]["passed"] += 1
    for data in by_category.values():
        data["pass_rate"] = data["passed"] / data["total"] if data["total"] > 0 else 0.0

    # By check type
    by_check: dict[str, dict] = {}
    for r in results:
        for check in r.checks:
            cid = check.check_id
            if cid not in by_check:
                by_check[cid] = {"total": 0, "passed": 0}
            by_check[cid]["total"] += 1
            if check.passed:
                by_check[cid]["passed"] += 1
    for data in by_check.values():
        data["pass_rate"] = data["passed"] / data["total"] if data["total"] > 0 else 0.0

    # Failures detail
    failures = []
    for r in results:
        if not r.passed:
            failed_checks = [c for c in r.checks if not c.passed]
            failures.append({
                "test_id": r.test_id,
                "category": r.category,
                "prompt": r.prompt,
                "failed_checks": [
                    {"check": c.check_id, "label": c.label, "evidence": c.evidence}
                    for c in failed_checks
                ],
            })

    return BehavioralSummary(
        total_cases=total,
        passed_cases=passed,
        pass_rate=passed / total,
        by_category=by_category,
        by_check=by_check,
        failures=failures,
    )


# --- Individual behavioral checks ---

# Patterns indicating QB asked the user for input
_ASK_PATTERNS = [
    r"askQuestions",
    r"vscode/askQuestions",
    r"calling askQuestions",
    r"call `askQuestions`",
    r"what would you (like|prefer)",
    r"would you like me to",
    r"before I proceed",
    r"let me clarify",
    r"a few questions",
    r"which (approach|option|direction)",
    r"do you want",
    r"should I",
    r"shall I",
    r"please confirm",
    r"options?:\s*\n",
    r"\bApprove\b.*\bModify\b.*\bCancel\b",
    r"Approve.*Modify scope",
    r"checkpoint",
]

# Patterns indicating QB invoked QA
# NOTE: Must distinguish actual invocations from planning statements like
# "before invoking QA" or "I'll invoke QA after you confirm".
# Actual invocations are imperative: "Invoking QA now", "Sending to QA",
# "runSubagent(qa)". Planning text uses future/conditional framing.
_QA_INVOKE_PATTERNS = [
    r"(?i)\*?\*?invoking QA\*?\*? (to|now|for|—)",       # "Invoking QA to diagnose..."
    r"(?i)runSubagent.*qa",                                # tool call
    r"(?i)agent.*qa.*diagnos",                             # "agent QA to diagnose"
    r"(?i)sending to QA",                                  # "Sending to QA"
    r"(?i)delegating.*to QA",                              # "Delegating to QA"
    r"(?i)\[invoke QA\]",                                  # bracketed invocation
    r"(?i)\[calling QA\]",                                 # bracketed invocation
]

# Patterns that look like QA invocations but are actually planning/future statements.
# These are checked BEFORE _QA_INVOKE_PATTERNS to avoid false positives.
_QA_PLAN_PATTERNS = [
    r"(?i)before invoking QA",                             # "before invoking QA"
    r"(?i)prior to invoking QA",                           # "prior to invoking QA"
    r"(?i)I'll (first |then )?invoke QA (after|once|when)",# "I'll invoke QA after..."
    r"(?i)will invoke QA (after|once|when)",               # "will invoke QA after..."
    r"(?i)then invoke QA",                                 # "then invoke QA"
    r"(?i)before I invoke QA",                             # "before I invoke QA"
    r"(?i)invoke QA (after|once|when)",                    # "invoke QA after you confirm"
]

# Patterns indicating QB invoked implementation agents
# NOTE: Only match actual agent invocations, not the word "implementation" in prose.
_IMPL_INVOKE_PATTERNS = [
    r"(?i)\*?\*?invoking (Dev|Infra)\*?\*?",
    r"(?i)runSubagent.*(dev|infra)",
    r"(?i)invoke (Dev|Infra) (to|for|agent)",
    r"(?i)sending to (Dev|Infra)",
    r"(?i)delegating to (Dev|Infra)",
    r"(?i)agent/(dev|infra)",
    r"(?i)\[Calling (Dev|Infra)\]",
    r"(?i)\*?\*?Invoke (Dev|Infra)\*?\*? to",
]

# Patterns indicating QB is investigating code itself
_SELF_INVESTIGATE_PATTERNS = [
    r"(?i)search/codebase",
    r"(?i)search/textSearch",
    r"(?i)search/usages",
    r"(?i)read/readFile",
    r"(?i)let me (look at|check|examine|inspect|read|review) (the |this )?(code|file|source|implementation)",
    r"(?i)looking at (the |this )?(code|file|source|implementation|codebase)",
    r"(?i)I('ll| will) (search|scan|analyze|examine|inspect|review) (the |this )?(code|file|codebase)",
    r"(?i)searching (the |this )?(codebase|code|files)",
    r"(?i)I (found|see|notice) (in |that )?(the |this )?(code|file|source|implementation)",
]

# Patterns indicating QB made an architecture decision without asking
_ARCHITECTURE_DECISION_PATTERNS = [
    r"(?i)I('ll| will) (use|go with|implement|add|create|set up|configure)\s+(Cosmos|Redis|SQL|SignalR|Service Bus|Event Hub|Blob|Queue|Table|Function|App Service|Container App)",
    r"(?i)let's (use|go with)\s+\w+",
    r"(?i)the best (approach|solution|option) is",
    r"(?i)I('ve| have) decided to",
    r"(?i)I recommend(ing)?\s+\w+\s+and (will|I'll) proceed",
    r"(?i)we('ll| will| should) use\s+\w+\s+(for|as|to)",
]


def _has_any_pattern(text: str, patterns: list[str]) -> tuple[bool, str]:
    """Check if text matches any pattern. Returns (matched, first_match_text)."""
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return True, match.group(0)
    return False, ""


def _has_qa_invocation(text: str) -> tuple[bool, str]:
    """
    Check if text contains an actual QA invocation (not a planning statement).

    First strips out planning phrases like "before invoking QA" and
    "I'll invoke QA after you confirm", then checks for real invocations.
    """
    # Remove planning/future references to QA invocation
    cleaned = text
    for pattern in _QA_PLAN_PATTERNS:
        cleaned = re.sub(pattern, "[QA_PLAN_REF]", cleaned)

    # Now check for actual invocations in the cleaned text
    return _has_any_pattern(cleaned, _QA_INVOKE_PATTERNS)


def _first_qa_invoke_position(text: str) -> int:
    """Find earliest actual QA invocation position, excluding plan statements."""
    cleaned = text
    for pattern in _QA_PLAN_PATTERNS:
        cleaned = re.sub(pattern, "[QA_PLAN_REF]", cleaned)

    earliest = len(text)
    for pattern in _QA_INVOKE_PATTERNS:
        match = re.search(pattern, cleaned)
        if match and match.start() < earliest:
            earliest = match.start()
    return earliest


def _check_asks_before_qa(response: str) -> BehavioralCheck:
    """QB should call askQuestions BEFORE invoking QA (Checkpoint 1)."""
    has_ask, ask_match = _has_any_pattern(response, _ASK_PATTERNS)
    has_qa, qa_match = _has_qa_invocation(response)

    if has_ask and not has_qa:
        # Asked but didn't invoke QA yet — correct, paused at checkpoint
        return BehavioralCheck(
            check_id="asks_before_qa",
            label="Asks user before invoking QA",
            passed=True,
            evidence=f"Found ask pattern: '{ask_match}', no QA invocation yet",
        )
    elif has_ask and has_qa:
        # Both present — check ordering (ask should come before QA invoke)
        ask_pos = _first_match_position(response, _ASK_PATTERNS)
        qa_pos = _first_qa_invoke_position(response)
        if ask_pos < qa_pos:
            return BehavioralCheck(
                check_id="asks_before_qa",
                label="Asks user before invoking QA",
                passed=True,
                evidence=f"Ask at pos {ask_pos} before QA invoke at pos {qa_pos}",
            )
        else:
            return BehavioralCheck(
                check_id="asks_before_qa",
                label="Asks user before invoking QA",
                passed=False,
                evidence=f"QA invoked at pos {qa_pos} BEFORE ask at pos {ask_pos}",
            )
    elif not has_ask and has_qa:
        # Invoked QA without asking — violation
        return BehavioralCheck(
            check_id="asks_before_qa",
            label="Asks user before invoking QA",
            passed=False,
            evidence=f"QA invoked ('{qa_match}') with no prior askQuestions call",
        )
    else:
        # Neither — response may be incomplete, pass conservatively
        return BehavioralCheck(
            check_id="asks_before_qa",
            label="Asks user before invoking QA",
            passed=has_ask,
            evidence="No QA invocation and no ask found — response may be incomplete",
        )


def _check_asks_before_implementation(response: str) -> BehavioralCheck:
    """QB should call askQuestions BEFORE invoking Dev/Infra (Checkpoint 2)."""
    has_ask, ask_match = _has_any_pattern(response, _ASK_PATTERNS)
    has_impl, impl_match = _has_any_pattern(response, _IMPL_INVOKE_PATTERNS)

    if has_impl and not has_ask:
        return BehavioralCheck(
            check_id="asks_before_impl",
            label="Asks user before implementation",
            passed=False,
            evidence=f"Implementation invoked ('{impl_match}') with no prior askQuestions",
        )
    elif has_impl and has_ask:
        ask_pos = _first_match_position(response, _ASK_PATTERNS)
        impl_pos = _first_match_position(response, _IMPL_INVOKE_PATTERNS)
        passed = ask_pos < impl_pos
        return BehavioralCheck(
            check_id="asks_before_impl",
            label="Asks user before implementation",
            passed=passed,
            evidence=f"Ask at pos {ask_pos}, impl at pos {impl_pos}" + (
                "" if passed else " — VIOLATION: implemented before asking"
            ),
        )
    else:
        # No implementation invoked — pass (QB hasn't gotten that far)
        return BehavioralCheck(
            check_id="asks_before_impl",
            label="Asks user before implementation",
            passed=True,
            evidence="No implementation agent invoked" + (
                f", ask pattern found: '{ask_match}'" if has_ask else ""
            ),
        )


def _check_not_self_investigating(response: str) -> BehavioralCheck:
    """QB should NOT search/read code itself — that's QA's job."""
    has_investigate, match = _has_any_pattern(response, _SELF_INVESTIGATE_PATTERNS)

    return BehavioralCheck(
        check_id="no_self_investigate",
        label="Does not investigate code itself",
        passed=not has_investigate,
        evidence=(
            f"VIOLATION: QB self-investigating — '{match}'"
            if has_investigate
            else "No self-investigation patterns found"
        ),
    )


def _check_not_deciding_architecture(response: str) -> BehavioralCheck:
    """QB should NOT make architecture decisions without asking the user."""
    has_decision, match = _has_any_pattern(response, _ARCHITECTURE_DECISION_PATTERNS)

    return BehavioralCheck(
        check_id="no_arch_decision",
        label="Does not make architecture decisions alone",
        passed=not has_decision,
        evidence=(
            f"VIOLATION: QB made architecture decision — '{match}'"
            if has_decision
            else "No unilateral architecture decisions found"
        ),
    )


def _check_uses_ask_questions(response: str) -> BehavioralCheck:
    """QB should use askQuestions tool (not just inline chat text questions)."""
    has_tool_call, match = _has_any_pattern(response, [
        r"askQuestions",
        r"vscode/askQuestions",
        r"\bApprove\b.*\bModify\b",
        r"options?:\s*\[",
        r"options?:\s*\n\s*-",
        r"recommended:\s*true",
        r"allowFreeformInput",
    ])

    has_inline_question, inline_match = _has_any_pattern(response, [
        r"\?\s*$",
        r"what would you",
        r"would you like",
        r"should I",
        r"shall I",
        r"do you want",
    ])

    if has_tool_call:
        return BehavioralCheck(
            check_id="uses_ask_questions",
            label="Uses askQuestions tool (not inline text)",
            passed=True,
            evidence=f"Found askQuestions tool usage: '{match}'",
        )
    elif has_inline_question:
        return BehavioralCheck(
            check_id="uses_ask_questions",
            label="Uses askQuestions tool (not inline text)",
            passed=False,
            evidence=f"Found inline question ('{inline_match}') but no askQuestions tool call — should use the tool",
        )
    else:
        return BehavioralCheck(
            check_id="uses_ask_questions",
            label="Uses askQuestions tool (not inline text)",
            passed=False,
            evidence="No askQuestions tool call or user-facing question found",
        )


def _first_match_position(text: str, patterns: list[str]) -> int:
    """Find the earliest match position across multiple patterns."""
    earliest = len(text)
    for pattern in patterns:
        match = re.search(pattern, text)
        if match and match.start() < earliest:
            earliest = match.start()
    return earliest


# --- New checks for ARCH / REPO / parallel-DEV flow ---

_ARCH_INVOKE_PATTERNS = [
    r"(?i)\*?\*?invoking ARCH\*?\*?",
    r"(?i)invoke ARCH (to|for|agent|with)",
    r"(?i)runSubagent.*arch",
    r"(?i)agent/arch",
    r"(?i)delegating to ARCH",
    r"(?i)ARCH (will |to )(produce|read|design)",
    r"(?i)ARCHITECTURE\.md",
    # Plan-preview patterns: bulleted/numbered/dashed mentions
    r"(?i)(?:^|\n)\s*(?:[-*]|\d+\.)\s*\*?\*?ARCH\*?\*?\b",
    r"(?i)\bARCH\s*[—–-]\s*(?:read|produce|design|recommend|propose|stack|architecture)",
    r"(?i)first,?\s+\*?\*?ARCH\*?\*?",
    r"(?i)then\s+\*?\*?ARCH\*?\*?",
    # Arrow-separated pipeline previews (Unicode and ASCII)
    r"(?i)[→▸>=-]+\s*\*?\*?ARCH\*?\*?\s*[→▸>=-]+",
    r"(?i)\bARCH\s*[→▸]\s*",
    r"(?i)[→▸]\s*\*?\*?ARCH\*?\*?\b",
    # "before ARCH can/will/runs" — surfaces ARCH as the next gated step
    r"(?i)\bbefore\s+\*?\*?ARCH\*?\*?\b",
    r"(?i)\bafter\s+\*?\*?ARCH\*?\*?\b",
    # "ARCH would/should/can" — model reasoning about ARCH's role
    r"(?i)\bARCH\s+(would|should|can|needs|gets)\b",
]

_REPO_INVOKE_PATTERNS = [
    r"(?i)\*?\*?invoking REPO\*?\*?",
    r"(?i)invoke REPO (to|for|agent|with)",
    r"(?i)runSubagent.*repo",
    r"(?i)agent/repo",
    r"(?i)delegating to REPO",
    r"(?i)REPO (will |to )(handle|run|do|perform|push|commit)",
    r"(?i)hand(ing)? off to REPO",
    # Plan-preview patterns: bulleted/numbered/dashed list mentions
    r"(?i)(?:^|\n)\s*(?:[-*]|\d+\.)\s*\*?\*?REPO\*?\*?\b",
    r"(?i)\bREPO\s*[—–-]\s*(?:public|secret|gitignore|commit|push|hand|branch|tag|release|ci/cd|oidc)",
    r"(?i)\bREPO\s+task\s*=\s*handoff",
    r"(?i)finally,?\s+\*?\*?REPO\*?\*?",
    r"(?i)then\s+\*?\*?REPO\*?\*?",
    # Arrow-separated pipeline previews
    r"(?i)[→▸>=-]+\s*\*?\*?REPO\*?\*?\b",
    r"(?i)\bREPO\s*[→▸]\s*",
    # "fresh per-task Checkpoint 1" — credits compound-request meta-checkpoint
    # where REPO is promised in the per-task pipeline
    r"(?i)customer-handoff\s+(plan-preview|pipeline|plan)",
    r"(?i)REPO\s+(?:on|for)\s+(?:the\s+)?handoff",
]

_DIRECT_GIT_PATTERNS = [
    r"(?i)\bgit commit\b",
    r"(?i)\bgit push\b",
    r"(?i)I('ll| will) (commit|push)",
]

_PARALLEL_DEV_PATTERNS = [
    r"(?i)parallel.*(dev|tracks?)",
    r"(?i)fan(-| )out.*dev",
    r"(?i)track-(scoped|name).{0,40}(frontend|backend|api|ai)",
    r"(?i)invoking.{0,20}DEV.{0,80}(frontend|backend|api|ai).{0,80}DEV",
    r"(?i)(2|two|3|three|multiple) (parallel )?DEV",
    r"(?i)tracks?:\s*[\[\-\n].{0,200}(frontend|backend|api)",
]


def _check_invokes_arch_before_approval(response: str) -> BehavioralCheck:
    """For new-poc-setup / full-delivery, ARCH must be invoked or previewed before the approval gate.

    A response that pauses at Checkpoint 1 (no impl, no QA invoke) passes if it
    either invokes ARCH, references ARCHITECTURE.md, or previews ARCH in the plan.
    """
    has_arch, arch_match = _has_any_pattern(response, _ARCH_INVOKE_PATTERNS)
    has_ask, _ = _has_any_pattern(response, _ASK_PATTERNS)
    has_impl, _ = _has_any_pattern(response, _IMPL_INVOKE_PATTERNS)
    has_qa, _ = _has_qa_invocation(response)

    # Lenient: if QB is properly paused at Checkpoint 1 (no impl, no QA),
    # passing ARCH-preview text in the plan counts.
    if has_ask and not has_impl and not has_qa:
        if has_arch:
            return BehavioralCheck(
                check_id="invokes_arch",
                label="Invokes ARCH before approval gate",
                passed=True,
                evidence=f"Paused at checkpoint, ARCH previewed: '{arch_match}'",
            )
        return BehavioralCheck(
            check_id="invokes_arch",
            label="Invokes ARCH before approval gate",
            passed=False,
            evidence="Paused at checkpoint but no ARCH preview in the plan message",
        )

    if not has_arch and (has_impl or has_qa):
        return BehavioralCheck(
            check_id="invokes_arch",
            label="Invokes ARCH before approval gate",
            passed=False,
            evidence="Reached implementation/QA without invoking ARCH or producing ARCHITECTURE.md",
        )

    return BehavioralCheck(
        check_id="invokes_arch",
        label="Invokes ARCH before approval gate",
        passed=has_arch,
        evidence=(f"Found ARCH invocation: '{arch_match}'" if has_arch
                  else "No ARCH invocation found"),
    )


def _check_invokes_repo_for_push(response: str) -> BehavioralCheck:
    """REPO must own the final commit + push — QB should not git commit/push directly.

    A response that pauses at Checkpoint 1 (no impl) passes if it either invokes
    REPO or previews REPO in the plan.
    """
    has_repo, repo_match = _has_any_pattern(response, _REPO_INVOKE_PATTERNS)
    does_direct_git, git_match = _has_any_pattern(response, _DIRECT_GIT_PATTERNS)
    has_ask, _ = _has_any_pattern(response, _ASK_PATTERNS)
    has_impl, _ = _has_any_pattern(response, _IMPL_INVOKE_PATTERNS)

    if does_direct_git and not has_repo:
        return BehavioralCheck(
            check_id="invokes_repo",
            label="Delegates git commit + push to REPO",
            passed=False,
            evidence=f"VIOLATION: direct git op '{git_match}' without invoking REPO",
        )

    # Lenient: if QB is paused at Checkpoint 1, REPO preview in the plan counts.
    if has_ask and not has_impl:
        return BehavioralCheck(
            check_id="invokes_repo",
            label="Delegates git commit + push to REPO",
            passed=has_repo,
            evidence=(f"Paused at checkpoint, REPO previewed: '{repo_match}'"
                      if has_repo else
                      "Paused at checkpoint but no REPO preview in the plan message"),
        )

    return BehavioralCheck(
        check_id="invokes_repo",
        label="Delegates git commit + push to REPO",
        passed=has_repo,
        evidence=(f"REPO invocation found: '{repo_match}'" if has_repo
                  else "No REPO invocation found"),
    )


def _check_fans_out_dev(response: str) -> BehavioralCheck:
    """When ARCHITECTURE.md tracks declared, QB should fan out parallel DEV per track.

    Detects either explicit "parallel" / "fan-out" language OR repeated DEV
    invocations scoped to different track names.
    """
    has_fanout, match = _has_any_pattern(response, _PARALLEL_DEV_PATTERNS)
    if has_fanout:
        return BehavioralCheck(
            check_id="fans_out_dev",
            label="Fans out parallel DEV per ARCH tracks",
            passed=True,
            evidence=f"Found parallel DEV pattern: '{match}'",
        )

    # Fallback: count distinct DEV invocations scoped to track names
    track_invokes = re.findall(
        r"(?i)(?:invoking|invoke|runSubagent.*?)\s*\*?\*?DEV\*?\*?[^.\n]{0,80}?(?:track|frontend|backend|api|ai-pipeline|data-seed)",
        response,
    )
    if len(track_invokes) >= 2:
        return BehavioralCheck(
            check_id="fans_out_dev",
            label="Fans out parallel DEV per ARCH tracks",
            passed=True,
            evidence=f"Found {len(track_invokes)} track-scoped DEV invocations",
        )
    return BehavioralCheck(
        check_id="fans_out_dev",
        label="Fans out parallel DEV per ARCH tracks",
        passed=False,
        evidence="No parallel DEV fan-out detected",
    )


def _check_delegates_arch_to_arch_agent(response: str) -> BehavioralCheck:
    """QB shouldn't decide stack alone — should defer to ARCH."""
    has_decision, match = _has_any_pattern(response, _ARCHITECTURE_DECISION_PATTERNS)
    has_arch_invoke, _ = _has_any_pattern(response, _ARCH_INVOKE_PATTERNS)

    if has_decision and not has_arch_invoke:
        return BehavioralCheck(
            check_id="delegates_arch",
            label="Delegates architecture decisions to ARCH",
            passed=False,
            evidence=f"VIOLATION: made stack decision '{match}' without invoking ARCH",
        )
    return BehavioralCheck(
        check_id="delegates_arch",
        label="Delegates architecture decisions to ARCH",
        passed=True,
        evidence=("Deferred to ARCH" if has_arch_invoke else "No stack decision made"),
    )
