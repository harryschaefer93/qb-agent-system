"""Quick test: verify function-calling produces actual tool_calls."""
import json
import yaml
from pathlib import Path
from evaluators.foundry_client import (
    create_foundry_client, load_foundry_config, load_agent_system_prompt,
    generate_live_response_with_tools, load_tool_definitions,
)
from evaluators.behavioral import evaluate_qb_behavior, load_behavioral_dataset

config = yaml.safe_load(open("config.yaml"))
cfg = load_foundry_config(config)
client = create_foundry_client(cfg)

agents_dir = Path(config["agents"]["definitions_path"]).expanduser()
agent_path = agents_dir / "QB.agent.md"
system_prompt = load_agent_system_prompt(agent_path)
tools = load_tool_definitions(Path("datasets/qb/tools.json"))

dataset = load_behavioral_dataset(Path("datasets/qb/behavioral.json"))

# Test first 3 cases
for tc in dataset["test_cases"][:3]:
    print(f"=== {tc['id']} ({tc['category']}) ===")
    print(f"  Prompt: {tc['prompt'][:60]}...")

    tr = generate_live_response_with_tools(
        client=client, deployment=cfg.deployment,
        system_prompt=system_prompt, user_prompt=tc["prompt"], tools=tools,
    )

    content_preview = tr.content[:150] if tr.content else "(none)"
    print(f"  Content: {content_preview}")
    print(f"  Tool calls: {len(tr.tool_calls)}")
    for call in tr.tool_calls:
        args_preview = call["function"]["arguments"][:120]
        print(f"    -> {call['function']['name']}({args_preview})")

    # Also run regex behavioral check on the combined text
    full_text = tr.content or ""
    if tr.tool_calls:
        for call in tr.tool_calls:
            full_text += f"\n[tool_call: {call['function']['name']}({call['function']['arguments']})]"

    result = evaluate_qb_behavior(full_text, tc)
    status = "PASS" if result.passed else "FAIL"
    print(f"  Behavioral: {status} ({result.passed_checks}/{result.total_checks})")
    for c in result.checks:
        icon = "✓" if c.passed else "✗"
        print(f"    {icon} {c.label}: {c.evidence[:60]}")
    print()
