"""
Routing evaluator — scores prompt-to-agent activation accuracy.

Loads agent descriptions from ../agents/ (resolved relative to the evals/ project
root via :func:`runner.cli.resolve_agents_dir`) and evaluates whether test prompts
would route to the expected agent based on keyword matching, trigger phrase
similarity, and description relevance scoring.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AgentProfile:
    """Parsed agent definition with routing-relevant metadata."""
    name: str
    description: str
    keywords: list[str] = field(default_factory=list)
    trigger_phrases: list[str] = field(default_factory=list)
    anti_phrases: list[str] = field(default_factory=list)


@dataclass
class RoutingResult:
    """Result of a single routing evaluation."""
    test_id: str
    prompt: str
    expected_agent: str
    matched_agent: str
    scores: dict[str, float]  # agent_name -> confidence score
    passed: bool
    false_positives: list[str] = field(default_factory=list)


def load_agent_profiles(agents_dir: Path) -> dict[str, AgentProfile]:
    """Load agent profiles from .md files, parsing YAML frontmatter for descriptions."""
    profiles = {}
    for md_file in agents_dir.glob("*.md"):
        name = md_file.stem.replace(".agent", "")
        content = md_file.read_text(encoding="utf-8", errors="replace")

        # Parse YAML frontmatter description
        description = _extract_frontmatter_description(content)
        if not description:
            # Fallback: first substantial paragraph
            lines = content.split("\n")
            desc_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("---") or stripped.startswith("#"):
                    continue
                if stripped:
                    desc_lines.append(stripped)
                if len(desc_lines) > 5:
                    break
            description = " ".join(desc_lines)

        # Extract WHEN: trigger phrases from description
        when_triggers = _extract_when_triggers(description)

        # Extract DO NOT USE FOR: anti-triggers from description
        anti_triggers = _extract_anti_triggers(description)

        # Extract keywords from full content + description
        keywords = _extract_keywords(content, name)

        profiles[name] = AgentProfile(
            name=name,
            description=description,
            keywords=keywords,
            trigger_phrases=when_triggers,
            anti_phrases=anti_triggers,
        )

    return profiles


def load_trigger_dataset(dataset_path: Path) -> dict:
    """Load a triggers.json dataset file."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_routing_dataset(dataset_path: Path) -> dict:
    """Load the cross-agent routing.json dataset."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def score_prompt_agent(prompt: str, profile: AgentProfile) -> float:
    """
    Score how well a prompt matches an agent profile.
    Returns 0.0 - 1.0 confidence score.
    """
    prompt_lower = prompt.lower()
    score = 0.0
    max_possible = 0.0

    # Keyword matching (weighted 0.4)
    if profile.keywords:
        keyword_hits = sum(1 for kw in profile.keywords if kw.lower() in prompt_lower)
        keyword_score = min(keyword_hits / max(len(profile.keywords) * 0.3, 1), 1.0)
        score += keyword_score * 0.4
    max_possible += 0.4

    # Trigger phrase similarity (weighted 0.4)
    if profile.trigger_phrases:
        best_similarity = max(
            _phrase_similarity(prompt_lower, tp.lower())
            for tp in profile.trigger_phrases
        )
        score += best_similarity * 0.4
    max_possible += 0.4

    # Description relevance (weighted 0.2)
    if profile.description:
        desc_words = set(profile.description.lower().split())
        prompt_words = set(prompt_lower.split())
        overlap = len(desc_words & prompt_words)
        desc_score = min(overlap / max(len(prompt_words) * 0.5, 1), 1.0)
        score += desc_score * 0.2
    max_possible += 0.2

    # Anti-phrase penalty — match both exact and normalized (hyphens ↔ spaces)
    if profile.anti_phrases:
        prompt_normalized = re.sub(r'[-_]', ' ', prompt_lower)
        anti_hits = 0
        for ap in profile.anti_phrases:
            ap_lower = ap.lower()
            ap_normalized = re.sub(r'[-_]', ' ', ap_lower)
            if ap_lower in prompt_lower or ap_normalized in prompt_normalized:
                anti_hits += 1
            elif _phrase_similarity(prompt_lower, ap_lower) > 0.6:
                anti_hits += 0.5
        if anti_hits > 0:
            score *= max(0.0, 1.0 - (anti_hits * 0.3))

    return min(score / max_possible, 1.0) if max_possible > 0 else 0.0


def evaluate_routing(
    routing_dataset: dict,
    profiles: dict[str, AgentProfile],
    trigger_datasets: Optional[dict[str, dict]] = None,
) -> list[RoutingResult]:
    """
    Run routing evaluation across all test cases.
    
    If trigger_datasets are provided, enriches agent profiles with
    shouldTrigger/shouldNotTrigger phrases before scoring.
    """
    # Enrich profiles with trigger data — merge with parsed WHEN: triggers, don't overwrite
    if trigger_datasets:
        for agent_name, triggers in trigger_datasets.items():
            if agent_name in profiles:
                dataset_triggers = triggers.get("shouldTriggerPrompts", [])
                dataset_anti = triggers.get("shouldNotTriggerPrompts", [])
                # Merge: agent file WHEN: triggers + dataset triggers (deduplicated)
                existing_triggers = set(t.lower() for t in profiles[agent_name].trigger_phrases)
                for t in dataset_triggers:
                    if t.lower() not in existing_triggers:
                        profiles[agent_name].trigger_phrases.append(t)
                existing_anti = set(a.lower() for a in profiles[agent_name].anti_phrases)
                for a in dataset_anti:
                    if a.lower() not in existing_anti:
                        profiles[agent_name].anti_phrases.append(a)

    results = []
    for test_case in routing_dataset.get("test_cases", []):
        prompt = test_case["prompt"]
        expected = test_case["expectedAgent"]
        should_not = test_case.get("shouldNotRoute", [])

        # Score against all agents
        scores = {}
        for agent_name, profile in profiles.items():
            scores[agent_name] = score_prompt_agent(prompt, profile)

        # Pick the highest-scoring agent
        matched = max(scores, key=scores.get) if scores else ""
        passed = matched.lower() == expected.lower()

        # Check for false positives
        false_positives = [
            agent for agent in should_not
            if agent in scores and scores[agent] > scores.get(expected, 0) * 0.8
        ]

        results.append(RoutingResult(
            test_id=test_case.get("id", ""),
            prompt=prompt,
            expected_agent=expected,
            matched_agent=matched,
            scores=scores,
            passed=passed,
            false_positives=false_positives,
        ))

    return results


def compute_routing_summary(results: list[RoutingResult]) -> dict:
    """Compute aggregate routing eval metrics."""
    total = len(results)
    if total == 0:
        return {"total": 0, "passed": 0, "accuracy": 0.0}

    passed = sum(1 for r in results if r.passed)
    false_positive_count = sum(len(r.false_positives) for r in results)

    # Per-agent breakdown
    agent_results: dict[str, dict] = {}
    for r in results:
        agent = r.expected_agent
        if agent not in agent_results:
            agent_results[agent] = {"total": 0, "passed": 0}
        agent_results[agent]["total"] += 1
        if r.passed:
            agent_results[agent]["passed"] += 1

    for agent_data in agent_results.values():
        agent_data["accuracy"] = (
            agent_data["passed"] / agent_data["total"]
            if agent_data["total"] > 0 else 0.0
        )

    # Confusion matrix — which agents get confused with each other
    confusions: dict[str, dict[str, int]] = {}
    for r in results:
        if not r.passed:
            key = r.expected_agent
            if key not in confusions:
                confusions[key] = {}
            wrong = r.matched_agent
            confusions[key][wrong] = confusions[key].get(wrong, 0) + 1

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": passed / total,
        "false_positive_cases": false_positive_count,
        "per_agent": agent_results,
        "confusions": confusions,
    }


# --- Private helpers ---

def _extract_keywords(content: str, agent_name: str) -> list[str]:
    """Extract routing-relevant keywords from agent definition content."""
    # Domain-specific keyword lists per known agent type
    keyword_map = {
        "poc-scoper": [
            "scope", "brief", "engagement", "customer", "POC", "kickoff",
            "stakeholder", "scoping", "intake", "BRIEF.md",
        ],
        "qb": [
            "orchestrat", "pipeline", "bug-fix", "full-delivery", "handoff",
            "customer-handoff", "new-poc-setup", "routing", "subagent",
            "quality gates", "fix", "broken",
        ],
        "dev": [
            "build", "implement", "frontend", "backend", "API", "FastAPI",
            "React", "Blazor", "Python", "TypeScript", "C#", "Express",
            "MSAL", "authentication", "RAG", "SignalR", "WebSocket",
            "Cosmos DB", "Redis", "endpoint", "code",
        ],
        "infra": [
            "Bicep", "Terraform", "provision", "VNet", "subnet", "NSG",
            "managed identity", "RBAC", "Key Vault", "azure.yaml", "azd",
            "CI/CD", "pipeline", "ARM", "private endpoint", "networking",
            "App Service", "Container Apps", "infrastructure",
        ],
        "qa": [
            "review", "test", "validate", "security", "bug", "Playwright",
            "functional", "smoke test", "edge case", "deployment readiness",
            "hardcoded secret", "visual review", "regression",
        ],
        "diagram": [
            "diagram", "architecture", "C4", "Mermaid", "topology",
            "data flow", "sequence diagram", "icon", "visual",
            "draw", "generate diagram", "network diagram",
        ],
        "docs": [
            "README", "documentation", "deployment guide", "handoff document",
            "write", "document", "HANDOFF.md", "architecture overview",
            "troubleshooting", "configuration reference", "quick start",
        ],
    }

    return keyword_map.get(agent_name, [])


def _extract_frontmatter_description(content: str) -> str:
    """Extract the description field from YAML frontmatter."""
    # Match frontmatter block
    fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not fm_match:
        return ""

    frontmatter = fm_match.group(1)

    # Handle inline quoted description: description: "..."
    # The outermost quotes delimit the YAML string; inner \" are escaped quotes
    inline_match = re.search(r'description:\s*"(.*)"', frontmatter)
    if inline_match:
        value = inline_match.group(1)
        # Unescape YAML escaped quotes
        value = value.replace('\\"', '"').replace('\\\\', '\\')
        return value

    # Handle inline unquoted description: description: text here
    inline_match = re.search(r'description:\s*([^\n]+)', frontmatter)
    if inline_match:
        value = inline_match.group(1).strip()
        if not value.startswith('>') and not value.startswith('|'):
            return value

    # Handle folded scalar: description: > or description: >-
    folded_match = re.search(r'description:\s*>-?\s*\n((?:\s+.+\n?)+)', frontmatter)
    if folded_match:
        lines = folded_match.group(1).split('\n')
        return ' '.join(line.strip() for line in lines if line.strip())

    return ""


def _extract_when_triggers(description: str) -> list[str]:
    """Extract WHEN: trigger phrases from an agent description."""
    # Match WHEN: followed by quoted or comma-separated phrases
    when_match = re.search(r'WHEN:\s*(.+?)(?:\.\s*DO NOT|\."\s*$|\.$)', description, re.IGNORECASE)
    if not when_match:
        # Try without terminal period
        when_match = re.search(r'WHEN:\s*(.+?)(?:DO NOT|$)', description, re.IGNORECASE)
    if not when_match:
        return []

    when_text = when_match.group(1)

    # Extract quoted phrases (handle escaped quotes too)
    quoted = re.findall(r'["\u201c]([^"\u201d\\]+(?:\\.[^"\u201d\\]*)*)["\u201d]', when_text)
    if quoted:
        # Clean up any remaining escape chars
        return [p.replace('\\', '').strip() for p in quoted if p.strip()]

    # Fall back to comma-separated phrases
    phrases = [p.strip().strip('"\'').replace('\\', '') for p in when_text.split(',')]
    return [p for p in phrases if p and len(p) > 2]


def _extract_anti_triggers(description: str) -> list[str]:
    """Extract DO NOT USE FOR: anti-trigger phrases from description."""
    anti_match = re.search(
        r'DO NOT USE FOR:\s*(.+?)(?:\."?\s*$|$)',
        description,
        re.IGNORECASE | re.DOTALL,
    )
    if not anti_match:
        return []

    anti_text = anti_match.group(1)

    # Split on commas and parenthetical agent refs, extract meaningful phrases
    # Remove parenthetical refs like "(use poc-scoper)"
    cleaned = re.sub(r'\(use\s+[^)]+\)', ',', anti_text)
    phrases = [p.strip().strip('"\'').replace('\\', '') for p in cleaned.split(',')]
    result = []
    for p in phrases:
        p = p.strip()
        if p and len(p) > 2:
            result.append(p)

    return result


def _phrase_similarity(prompt: str, phrase: str) -> float:
    """Simple word-overlap similarity between prompt and trigger phrase."""
    prompt_words = set(re.findall(r'\w+', prompt))
    phrase_words = set(re.findall(r'\w+', phrase))

    if not phrase_words:
        return 0.0

    overlap = len(prompt_words & phrase_words)
    # Jaccard-ish but weighted toward phrase coverage
    return overlap / len(phrase_words)
