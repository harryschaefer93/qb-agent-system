"""IMP-0018 rubric backfill — poc-scoper BRIEF.md output quality scenarios.

The rubric runner (runner.imp_runner._run_rubric) drives each scenario through
a tool_loop against the scoper agent's system prompt, captures the final
assistant response, and feeds it to the rubric judge defined in
evaluators/rubrics/imp_0018.md.

Scenarios are intentionally small (N_SAMPLES=1) for the scaffold so a baseline
runs in a single judge call. Harry should expand this set when the rubric
calibration is finalised.
"""
from __future__ import annotations

N_SAMPLES = 1
MAX_TURNS = 4


def get_scenarios() -> list[dict]:
    return [
        {
            "id": "scope-woodgrove-claims",
            "prompt": (
                "Scope a new POC for Woodgrove on claims automation. "
                "Customer has 80M policies and a $3B annual claims spend. "
                "Produce a BRIEF.md with sections: Customer Context, "
                "Acceptance Criteria, Constraints."
            ),
        },
    ]
