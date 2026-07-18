"""
Calibration agreement gate — verifies the LLM judge agrees with humans.

Implements the second half of the §3a contract: every quality rubric ships
with at least 5 hand-graded calibration examples. The judge is run against
each example and must agree with the human scores on >=80% of examples
(per-criterion agreement = within one score point on the 1-5 scale).

When the gate fails, the rubric is not trusted for scoring agent runs and
must be either rewritten, re-graded, or paired with a stronger judge model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .rubric import Rubric, evaluate_with_rubric


# --- Dataclasses ---

@dataclass
class CalibrationExample:
    """One hand-graded example used to verify the judge agrees with humans."""
    example_id: str
    prompt: str
    response: str
    expected_scores: dict[str, int]
    notes: str = ""


@dataclass
class CalibrationResult:
    """Per-example outcome of comparing judge scores to human-expected scores."""
    example_id: str
    judge_scores: dict[str, int]
    expected_scores: dict[str, int]
    agreement_per_criterion: dict[str, bool]
    fully_agreed: bool


@dataclass
class CalibrationReport:
    """Aggregate report covering an entire calibration set for one rubric."""
    rubric_id: str
    n_examples: int
    n_full_agreement: int
    agreement_rate: float
    per_criterion_agreement: dict[str, float]
    passed: bool
    min_agreement: float
    results: list[CalibrationResult] = field(default_factory=list)


# --- Loader ---

def load_calibration_set(calibration_path: Path) -> list[CalibrationExample]:
    """Load examples from a JSONL file (one example per line).

    Each line must be a JSON object shaped like::

        {
            "example_id": "ex1",
            "prompt": "...",
            "response": "...",
            "expected_scores": {"correctness": 5, "tone": 4},
            "notes": "..."
        }

    Blank lines and lines starting with ``#`` are skipped to allow inline
    comments while authoring the calibration set.
    """
    examples: list[CalibrationExample] = []
    with calibration_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            obj = json.loads(line)
            examples.append(CalibrationExample(
                example_id=str(obj["example_id"]),
                prompt=str(obj["prompt"]),
                response=str(obj["response"]),
                expected_scores={
                    str(k): int(v) for k, v in obj["expected_scores"].items()
                },
                notes=str(obj.get("notes", "")),
            ))
    return examples


# --- Runner ---

def run_calibration(rubric: Rubric, examples: list[CalibrationExample],
                    client, deployment: str,
                    min_agreement: float = 0.80) -> CalibrationReport:
    """Run the judge against each example and compare to expected scores.

    Per-criterion agreement is defined as ``|judge - expected| <= 1`` on the
    1-5 scale (the judge is allowed to be off by at most one score point).
    An example is ``fully_agreed`` only when every criterion the human graded
    is in agreement with the judge.

    ``agreement_rate = fully_agreed_count / n_examples`` and the report is
    marked ``passed`` when ``agreement_rate >= min_agreement``.

    Per-criterion agreement rates are also reported so authors can see which
    dimension is causing a failure (typically tone/style, occasionally
    correctness on edge cases).
    """
    results: list[CalibrationResult] = []
    per_criterion_totals: dict[str, list[bool]] = {}

    for ex in examples:
        rubric_result = evaluate_with_rubric(
            prompt=ex.prompt,
            response=ex.response,
            rubric=rubric,
            client=client,
            deployment=deployment,
        )

        judge_scores: dict[str, int] = {
            cs.name: int(round(cs.score)) for cs in rubric_result.per_criterion
        }

        agreement_per_criterion: dict[str, bool] = {}
        for criterion_name, expected in ex.expected_scores.items():
            judge_value = judge_scores.get(criterion_name)
            if judge_value is None:
                agreed = False
            else:
                agreed = abs(judge_value - expected) <= 1
            agreement_per_criterion[criterion_name] = agreed
            per_criterion_totals.setdefault(criterion_name, []).append(agreed)

        fully_agreed = (
            bool(agreement_per_criterion)
            and all(agreement_per_criterion.values())
        )

        results.append(CalibrationResult(
            example_id=ex.example_id,
            judge_scores=judge_scores,
            expected_scores=dict(ex.expected_scores),
            agreement_per_criterion=agreement_per_criterion,
            fully_agreed=fully_agreed,
        ))

    n_examples = len(examples)
    n_full_agreement = sum(1 for r in results if r.fully_agreed)
    agreement_rate = (n_full_agreement / n_examples) if n_examples else 0.0

    per_criterion_agreement = {
        name: (sum(1 for v in flags if v) / len(flags)) if flags else 0.0
        for name, flags in per_criterion_totals.items()
    }

    return CalibrationReport(
        rubric_id=rubric.rubric_id,
        n_examples=n_examples,
        n_full_agreement=n_full_agreement,
        agreement_rate=agreement_rate,
        per_criterion_agreement=per_criterion_agreement,
        passed=(agreement_rate >= min_agreement),
        min_agreement=min_agreement,
        results=results,
    )
