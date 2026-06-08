# Agent Eval Harness

Systematic evaluation framework for Copilot CLI agents. Tests routing accuracy, output quality, and structural compliance — all while agents run locally with full MCP/WorkIQ/Graph tool access.

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run all evals
python -m runner.cli run-all

# Run evals for a single agent
python -m runner.cli run-agent poc-scoper

# Compare two eval runs
python -m runner.cli compare results/run-001.json results/run-002.json
```

## Eval Layers

### Layer 1: Routing Evals
Does the right agent activate for a given prompt? Tests prompt-to-agent matching against trigger phrases and descriptions extracted from agent definitions.

- **No API calls needed** — pure local description matching
- Inspired by [Sensei](https://skills.sh/microsoft/github-copilot-for-azure/sensei) `shouldTriggerPrompts` / `shouldNotTriggerPrompts` pattern

### Layer 2: Output Quality Evals
Does each agent produce correct, high-quality responses? Scores agent outputs using Azure AI Foundry evaluator APIs.

- **Evaluators:** fluency, coherence, task adherence, groundedness, safety
- **Agents stay local** — full tool access preserved, only scoring goes to Foundry

### Layer 3: Structure Evals
Does agent output conform to expected shapes? Custom validators per agent.

- `poc-scoper` — BRIEF.md contains all 9 required sections
- `qb` — QB Result output matches required format
- `inbox-triage` — correct mode detection and categorization
- `infra` — IaC templates compile

## Project Structure

```
evals/
├── datasets/           # Test cases organized by agent
│   ├── routing/        # Cross-agent routing test cases
│   └── {agent}/        # Per-agent trigger + quality datasets
├── evaluators/         # Scoring logic
│   ├── routing.py      # Prompt → agent activation scoring
│   ├── quality.py      # Foundry evaluator API wrapper
│   ├── structure.py    # Output shape validators
│   └── custom/         # Agent-specific evaluators
├── runner/             # Test execution engine
│   ├── cli.py          # CLI entry point
│   ├── scorer.py       # Score aggregation
│   └── reporter.py     # Report generation
├── results/            # Eval run outputs (gitignored)
├── reports/            # Committed summary reports
└── scripts/            # Convenience scripts
```

## Configuration

Edit `config.yaml` to set your Foundry endpoint and eval preferences:

```yaml
foundry:
  endpoint: "<your-foundry-project-endpoint>"
  deployment: "<your-eval-model-deployment>"

agents:
  definitions_path: "../agents/"   # relative to evals/, resolves to .copilot/agents/

thresholds:
  routing_accuracy: 0.90
  fluency_min: 4.0
  coherence_min: 4.0
  task_adherence_min: 4.0
```

## Adding Test Cases

### Routing test case
```json
{
  "prompt": "set up VNets and private endpoints for the POC",
  "expectedAgent": "infra",
  "shouldNotRoute": ["dev", "docs"]
}
```

### Quality test case
```json
{
  "prompt": "scope a new POC for Allstate on claims automation",
  "evaluators": ["fluency", "task_adherence", "coherence"],
  "groundTruth": "Should produce structured BRIEF.md with customer context"
}
```
