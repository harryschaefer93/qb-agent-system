"""IMP-0020 rubric — Evidence-Backed Recommendation quality.

The rubric runner drives each scenario through a tool_loop against QB's
system prompt, captures the final assistant response (where QB presents a
CHECKPOINT 2 recommendation), and feeds it to the rubric judge defined in
evaluators/rubrics/imp_0020.md.

Scenarios pose realistic FSI-Azure technical decisions that should trigger
QB's Evidence-Backed Recommendations behavior (per IMP-0020): cited Source:
on recommended options, FDPO compliance respected, alternatives surfaced.

Calibration set (imp_0020.calibration.jsonl) gates whether the judge is
trusted: if judge-vs-human agreement < 0.80, scoring is skipped and the
snapshot is marked calibration-failure (per IMP-0015 hard-fail signal).
"""
from __future__ import annotations

N_SAMPLES = 1
MAX_TURNS = 6


def get_scenarios() -> list[dict]:
    return [
        {
            "id": "cosmos-vs-postgres-chat-history",
            "prompt": (
                "You are at CHECKPOINT 2 for an Azure AI Foundry FSI chat application. "
                "We need to pick a database for storing multi-turn chat history — "
                "Azure Cosmos DB for NoSQL vs Azure Database for PostgreSQL. "
                "Customer is on a FDPO tenant, needs multi-region availability.\n\n"
                "BEFORE you call askQuestions, render your full `## Why recommended` "
                "chat preamble inline in this response: show the recommended option name, "
                "the cited Source: URL, verbatim quoted excerpts from the source supporting "
                "your claims, the trade-offs vs the alternative, and FDPO compliance notes. "
                "Then describe (but do not call) the askQuestions options you would present. "
                "Do NOT call any tool — render the recommendation content as text only so "
                "I can review it before you proceed."
            ),
        },
        {
            "id": "managed-identity-flavor",
            "prompt": (
                "You are at CHECKPOINT 2 for the Foundry Agent Service connecting to "
                "Azure Key Vault on a FDPO tenant. Decide between System-Assigned Managed "
                "Identity, User-Assigned Managed Identity, and Workload Identity Federation.\n\n"
                "BEFORE you call askQuestions, render your full `## Why recommended` chat "
                "preamble inline in this response: recommended option name, cited Source: "
                "URL, verbatim quoted excerpts supporting your claims, alternatives "
                "considered, and FDPO compliance notes. Then describe (but do not call) "
                "the askQuestions options. Do NOT call any tool — render as text only."
            ),
        },
        {
            "id": "bicep-vs-terraform",
            "prompt": (
                "You are at CHECKPOINT 2 for the IaC layer of a greenfield Foundry POC. "
                "Customer is Azure-only (no multi-cloud requirement). Decide between "
                "Azure Bicep and Terraform.\n\n"
                "BEFORE you call askQuestions, render your full `## Why recommended` "
                "chat preamble inline in this response: recommended option name, cited "
                "Source: URL, verbatim quoted excerpts supporting your claims, the "
                "trade-offs vs the alternative. Then describe (but do not call) the "
                "askQuestions options. Do NOT call any tool — render as text only."
            ),
        },
    ]
