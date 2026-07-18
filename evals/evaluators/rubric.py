"""
Rubric evaluator — markdown rubric loader + LLM-judge scorer.

Implements the §3a contract from EVAL-SYSTEM-PLAN: every `quality` eval ships
with a weighted rubric (1-5 scale per criterion) and is scored by an LLM judge
running on Foundry. Rubrics are authored as markdown for human review and
parsed into structured dataclasses for deterministic judging.

Auth: Entra ID via the AzureOpenAI client created in foundry_client.py.
No API keys, no local-auth fallbacks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# --- Dataclasses ---

@dataclass
class Criterion:
    """One scoring dimension in a rubric (e.g. 'correctness', 'tone')."""
    name: str
    weight: float
    score_definitions: dict[int, str]
    examples: dict[int, list[str]] = field(default_factory=dict)
    description: str = ""


@dataclass
class Rubric:
    """A weighted set of criteria used to score a single response."""
    rubric_id: str
    title: str
    criteria: list[Criterion]
    overall_pass_threshold: float = 4.0
    judge_model_hint: Optional[str] = None


@dataclass
class CriterionScore:
    """One judge-assigned score for a single criterion."""
    name: str
    score: float
    weight: float
    weighted: float
    reasoning: str = ""


@dataclass
class RubricResult:
    """The full result of evaluating one (prompt, response) pair against a rubric."""
    rubric_id: str
    prompt: str
    response: str
    weighted_score: float
    passed: bool
    per_criterion: list[CriterionScore]
    raw_judge_response: str = ""


# --- Loader ---

_CRITERION_HEADER_RE = re.compile(
    r"^##\s+Criterion:\s*(?P<name>[^\(]+?)\s*\(weight:\s*(?P<weight>[0-9.]+)\)\s*$",
    re.IGNORECASE,
)
_SCORE_LINE_RE = re.compile(
    r"^\s*[-*]\s*\*\*(?P<score>[1-5])\*\*\s*:\s*(?P<text>.+?)\s*$"
)
_TITLE_RE = re.compile(r"^#\s+Rubric:\s*(?P<title>.+?)\s*$", re.IGNORECASE)


def load_rubric(rubric_path: Path) -> Rubric:
    """Load and parse a rubric from a markdown file.

    Expected markdown format (see _template.md):

        # Rubric: <title>

        ## Criterion: <name> (weight: 0.5)
        <one-line description>

        ### Score Definitions
        - **5**: <definition>
        - **4**: <definition>
        - **3**: <definition>
        - **2**: <definition>
        - **1**: <definition>

        ### Examples
        - **5**: <example response>
        - **3**: <example response>

        ## Criterion: <next>
        ...

    The rubric_id is derived from the file stem (e.g. 'imp_0014.md' -> 'imp_0014').

    Validation:
        - Sum of weights must be within 0.001 of 1.0; raises ValueError otherwise.
        - Each criterion must have score_definitions for all of {1,2,3,4,5}.
    """
    text = rubric_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    rubric_id = rubric_path.stem
    title = rubric_id

    # Parse line-by-line into criterion blocks.
    criteria: list[Criterion] = []
    current: Optional[dict] = None
    section: Optional[str] = None  # "definitions" | "examples" | None

    def _flush(cur: Optional[dict]) -> None:
        if cur is None:
            return
        criterion = Criterion(
            name=cur["name"],
            weight=cur["weight"],
            score_definitions=cur["score_definitions"],
            examples=cur["examples"],
            description=cur["description"].strip(),
        )
        criteria.append(criterion)

    for raw_line in lines:
        line = raw_line.rstrip()

        if not line.strip() or line.lstrip().startswith("<!--"):
            # Comments and blank lines are ignored for parsing structure.
            continue

        title_match = _TITLE_RE.match(line)
        if title_match:
            title = title_match.group("title").strip()
            continue

        crit_match = _CRITERION_HEADER_RE.match(line)
        if crit_match:
            _flush(current)
            current = {
                "name": crit_match.group("name").strip(),
                "weight": float(crit_match.group("weight")),
                "score_definitions": {},
                "examples": {},
                "description": "",
            }
            section = None
            continue

        if current is None:
            # Pre-criterion content (e.g. intro paragraphs) is ignored.
            continue

        lower = line.strip().lower()
        if lower.startswith("### score definitions"):
            section = "definitions"
            continue
        if lower.startswith("### examples"):
            section = "examples"
            continue
        if line.startswith("###"):
            # Unknown subsection — ignore further bullets until next known section.
            section = None
            continue

        score_match = _SCORE_LINE_RE.match(line)
        if score_match and section is not None:
            score = int(score_match.group("score"))
            text_value = score_match.group("text").strip()
            if section == "definitions":
                current["score_definitions"][score] = text_value
            elif section == "examples":
                current["examples"].setdefault(score, []).append(text_value)
            continue

        if section is None and not line.startswith("#"):
            # Free-form description text directly under the criterion header.
            if current["description"]:
                current["description"] += " " + line.strip()
            else:
                current["description"] = line.strip()

    _flush(current)

    if not criteria:
        raise ValueError(
            f"Rubric '{rubric_path}' has no criteria. "
            "Expected at least one '## Criterion: <name> (weight: x)' header."
        )

    weight_sum = sum(c.weight for c in criteria)
    if abs(weight_sum - 1.0) > 0.001:
        raise ValueError(
            f"Rubric '{rubric_path}' criterion weights sum to {weight_sum:.3f}, "
            f"expected 1.000 (±0.001)."
        )

    required_scores = {1, 2, 3, 4, 5}
    for c in criteria:
        missing = required_scores - set(c.score_definitions.keys())
        if missing:
            raise ValueError(
                f"Rubric '{rubric_path}' criterion '{c.name}' is missing "
                f"score definitions for: {sorted(missing)}. "
                "Each criterion must define all five score levels (1-5)."
            )

    return Rubric(rubric_id=rubric_id, title=title, criteria=criteria)


# --- Rendering ---

def render_rubric_for_judge(rubric: Rubric) -> str:
    """Format a rubric as a plain-text block suitable for inclusion in a judge prompt.

    Output deliberately avoids markdown styling so smaller models don't get
    tripped up by formatting tokens. Each criterion is presented with its
    weight, a scored ladder (1-5) of definitions, and any examples.
    """
    blocks: list[str] = []
    blocks.append(f"RUBRIC: {rubric.title}")
    blocks.append(f"PASS THRESHOLD (weighted): {rubric.overall_pass_threshold:.2f}")
    blocks.append("")

    for idx, c in enumerate(rubric.criteria, start=1):
        blocks.append(f"--- Criterion {idx}: {c.name} (weight {c.weight:.2f}) ---")
        if c.description:
            blocks.append(f"Description: {c.description}")
        blocks.append("Score definitions:")
        for score in sorted(c.score_definitions.keys(), reverse=True):
            blocks.append(f"  {score} = {c.score_definitions[score]}")
        if c.examples:
            blocks.append("Examples:")
            for score in sorted(c.examples.keys(), reverse=True):
                for example in c.examples[score]:
                    blocks.append(f"  [score={score}] {example}")
        blocks.append("")

    return "\n".join(blocks).rstrip() + "\n"


# --- Judge ---

_JUDGE_INSTRUCTIONS = (
    "You are an evaluation judge. Score the AGENT RESPONSE against each "
    "criterion in the rubric using the 1-5 scale defined for that criterion. "
    "Be strict and consistent. Use only integer scores (1, 2, 3, 4, or 5). "
    "Reply with a single JSON object and nothing else, in this exact shape:\n"
    '{"per_criterion": [{"name": "<criterion name>", "score": <int 1-5>, '
    '"reasoning": "<one sentence>"}, ...]}\n'
    "Include exactly one entry per criterion in the rubric, using the "
    "criterion names verbatim. Do not include any prose outside the JSON."
)


def _build_judge_messages(prompt: str, response: str, rubric: Rubric,
                          strict: bool = False) -> list[dict]:
    rubric_block = render_rubric_for_judge(rubric)
    system_content = _JUDGE_INSTRUCTIONS
    if strict:
        system_content = "RESPOND WITH JSON ONLY. " + system_content

    user_content = (
        f"{rubric_block}\n"
        "USER PROMPT (what the agent was asked to do):\n"
        f"{prompt}\n\n"
        "AGENT RESPONSE (what the agent produced — score this):\n"
        f"{response}\n"
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def _extract_json_block(text: str) -> Optional[dict]:
    """Best-effort JSON extraction from a judge response."""
    if not text:
        return None
    stripped = text.strip()
    # Strip code fences if present.
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```\s*$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    # Fall back to first {...} balanced block.
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(stripped[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _call_judge(client, deployment: str, messages: list[dict],
                temperature: float, seed: int) -> str:
    completion = client.chat.completions.create(
        model=deployment,
        messages=messages,
        temperature=temperature,
        seed=seed,
    )
    return completion.choices[0].message.content or ""


def evaluate_with_rubric(prompt: str, response: str, rubric: Rubric,
                         client, deployment: str,
                         temperature: float = 0.0, seed: int = 42) -> RubricResult:
    """Score a response using an LLM judge guided by the rubric.

    Builds a deterministic judge prompt that includes the user prompt, the
    agent response, the full rubric (rendered for an LLM judge), and an
    instruction to return strict JSON.

    Calls ``client.chat.completions.create`` (the AzureOpenAI client from
    ``foundry_client.create_foundry_client``) with ``temperature=0`` and a
    fixed ``seed`` for run-to-run reproducibility.

    Parses the JSON response, computes ``weighted_score`` as
    ``sum(score_i * weight_i)``, sets ``passed`` based on
    ``rubric.overall_pass_threshold``, and returns a :class:`RubricResult`.

    On JSON parse failure, the call is retried once with a stricter
    "RESPOND WITH JSON ONLY" prefix. On a second failure, returns a
    ``RubricResult`` with ``weighted_score=0``, ``passed=False``,
    ``per_criterion=[]``, and ``raw_judge_response`` set to the raw text.
    """
    messages = _build_judge_messages(prompt, response, rubric, strict=False)
    raw = _call_judge(client, deployment, messages, temperature, seed)
    parsed = _extract_json_block(raw)

    if parsed is None:
        strict_messages = _build_judge_messages(prompt, response, rubric, strict=True)
        raw = _call_judge(client, deployment, strict_messages, temperature, seed)
        parsed = _extract_json_block(raw)

    if parsed is None or "per_criterion" not in parsed:
        return RubricResult(
            rubric_id=rubric.rubric_id,
            prompt=prompt,
            response=response,
            weighted_score=0.0,
            passed=False,
            per_criterion=[],
            raw_judge_response=raw,
        )

    weight_by_name = {c.name: c.weight for c in rubric.criteria}
    per_criterion: list[CriterionScore] = []
    weighted_total = 0.0

    for entry in parsed.get("per_criterion", []):
        name = str(entry.get("name", "")).strip()
        weight = weight_by_name.get(name)
        if weight is None:
            # Try case-insensitive match.
            for cname, cweight in weight_by_name.items():
                if cname.lower() == name.lower():
                    name, weight = cname, cweight
                    break
        if weight is None:
            continue

        try:
            score = float(entry.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0
        score = max(1.0, min(5.0, score))

        weighted = score * weight
        weighted_total += weighted
        per_criterion.append(CriterionScore(
            name=name,
            score=score,
            weight=weight,
            weighted=weighted,
            reasoning=str(entry.get("reasoning", "")).strip(),
        ))

    passed = weighted_total >= rubric.overall_pass_threshold

    return RubricResult(
        rubric_id=rubric.rubric_id,
        prompt=prompt,
        response=response,
        weighted_score=weighted_total,
        passed=passed,
        per_criterion=per_criterion,
        raw_judge_response=raw,
    )


# --- Aggregation ---

def compute_rubric_summary(results: list[RubricResult]) -> dict:
    """Roll up multiple RubricResult objects into aggregate metrics.

    Returns a dict shaped as::

        {
            "total": N,
            "passed": int,
            "pass_rate": float,
            "mean_weighted_score": float,
            "per_criterion_means": {name: mean_score, ...},
        }

    Returns zeroed metrics when ``results`` is empty.
    """
    total = len(results)
    if total == 0:
        return {
            "total": 0,
            "passed": 0,
            "pass_rate": 0.0,
            "mean_weighted_score": 0.0,
            "per_criterion_means": {},
        }

    passed = sum(1 for r in results if r.passed)
    mean_weighted = sum(r.weighted_score for r in results) / total

    by_criterion: dict[str, list[float]] = {}
    for r in results:
        for cs in r.per_criterion:
            by_criterion.setdefault(cs.name, []).append(cs.score)

    per_criterion_means = {
        name: sum(scores) / len(scores)
        for name, scores in by_criterion.items()
    }

    return {
        "total": total,
        "passed": passed,
        "pass_rate": passed / total,
        "mean_weighted_score": mean_weighted,
        "per_criterion_means": per_criterion_means,
    }
