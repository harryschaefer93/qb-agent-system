"""
Tool execution loop — Pattern C (mock tool runtime) for multi-turn evals.

Sends a system prompt + user prompt + tool definitions to Foundry,
then resolves tool calls via mocks.yaml and loops until the model
produces a final answer or hits max_turns.

Used by tool_loop and subagent_routing eval types.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

import yaml

logger = logging.getLogger(__name__)


# --- Dataclasses ---

@dataclass
class LoopConfig:
    """Configuration for the tool execution loop."""
    max_turns: int = 6
    stop_on: list[str] = field(default_factory=lambda: ["final_answer"])
    on_unmocked: Literal["error", "echo", "skip"] = "echo"
    temperature: float = 0
    seed: int = 42
    max_tokens: int = 4000


@dataclass
class MockRule:
    """Conditional mock rule: match args, return fixed response."""
    when: dict[str, Any]
    then: Any


@dataclass
class ToolMock:
    """Mock configuration for a single tool."""
    name: str
    strategy: Literal["static", "conditional", "echo"]
    response: Any = None
    rules: list[MockRule] = field(default_factory=list)


@dataclass
class LoopTrace:
    """Complete trace of a tool-loop execution."""
    turns: list[dict] = field(default_factory=list)
    stopped_reason: str = ""  # "final_answer" | "max_turns" | "error" | "stop_tool"
    tool_call_sequence: list[str] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    wall_time_ms: int = 0


@dataclass
class LoopResult:
    """Result from running a single scenario through the tool loop."""
    scenario_id: str
    trace: LoopTrace
    final_content: str = ""
    error: Optional[str] = None


# --- Mock loading ---

def load_mocks(mocks_path: Path) -> tuple[list[ToolMock], str]:
    """Load mocks.yaml and return (mock_list, default_on_unmocked)."""
    data = yaml.safe_load(mocks_path.read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    on_unmocked = defaults.get("on_unmocked", "echo")

    mocks = []
    for m in data.get("mocks", []):
        rules = []
        for r in m.get("rules", []):
            rules.append(MockRule(when=r["when"], then=r["then"]))
        mocks.append(ToolMock(
            name=m["name"],
            strategy=m.get("strategy", "static"),
            response=m.get("response"),
            rules=rules,
        ))

    return mocks, on_unmocked


def resolve_tool_call(
    tool_name: str,
    tool_args: dict[str, Any],
    mocks: list[ToolMock],
    on_unmocked: str,
) -> Any:
    """Resolve a tool call against the mock registry.

    Returns the mock response as a JSON-serializable value.
    """
    # Find matching mock
    for mock in mocks:
        if mock.name == tool_name:
            return _apply_mock(mock, tool_args)

    # Unmocked tool
    if on_unmocked == "error":
        raise ValueError(f"Unmocked tool called: {tool_name}({tool_args})")
    elif on_unmocked == "skip":
        return {"status": "skipped", "reason": f"No mock for {tool_name}"}
    else:  # echo
        return {"tool": tool_name, "args": tool_args, "result": "echo — no mock configured"}


def _apply_mock(mock: ToolMock, tool_args: dict[str, Any]) -> Any:
    """Apply a mock's strategy to produce a response."""
    if mock.strategy == "static":
        return mock.response

    elif mock.strategy == "echo":
        return {"tool": mock.name, "args": tool_args, "result": f"mock echo for {mock.name}"}

    elif mock.strategy == "conditional":
        for rule in mock.rules:
            if _args_match(rule.when, tool_args):
                return rule.then
        # No rule matched — fall back to static response or echo
        if mock.response is not None:
            return mock.response
        return {"tool": mock.name, "args": tool_args, "result": "no conditional rule matched"}

    else:
        raise ValueError(f"Unknown mock strategy: {mock.strategy}")


def _args_match(when: dict[str, Any], args: dict[str, Any]) -> bool:
    """Check if tool args match a conditional rule's 'when' clause.

    Supports exact match and wildcard (*).
    """
    for key, expected in when.items():
        actual = args.get(key)
        if actual is None:
            return False
        if expected == "*":
            continue
        if isinstance(expected, str) and isinstance(actual, str):
            if expected.lower() != actual.lower():
                return False
        elif expected != actual:
            return False
    return True


# --- The loop ---

def run_tool_loop(
    client,  # AzureOpenAI
    deployment: str,
    system_prompt: str,
    user_prompt: str,
    tools: list[dict],
    mocks: list[ToolMock],
    config: LoopConfig,
    on_unmocked: str = "echo",
) -> LoopTrace:
    """Execute a multi-turn tool loop against Foundry with mock tool resolution.

    Algorithm:
    1. Send messages + tools to Foundry chat completions.
    2. If response has tool_calls: resolve each via mocks, append tool results, recurse.
    3. Stop when: model emits final assistant message with no tool calls,
       OR max_turns hit, OR a stop_on tool fires.
    4. Return LoopTrace.
    """
    trace = LoopTrace()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    start_time = time.monotonic()

    for turn in range(config.max_turns):
        try:
            response = client.chat.completions.create(
                model=deployment,
                messages=messages,
                tools=tools,
                max_completion_tokens=config.max_tokens,
                temperature=config.temperature,
                seed=config.seed,
            )
        except Exception as e:
            trace.stopped_reason = "error"
            trace.turns.append({"turn": turn, "error": str(e)})
            break

        msg = response.choices[0].message
        usage = response.usage

        if usage:
            trace.total_input_tokens += usage.prompt_tokens or 0
            trace.total_output_tokens += usage.completion_tokens or 0

        content = msg.content or ""

        # No tool calls — final answer
        if not msg.tool_calls:
            trace.turns.append({
                "turn": turn,
                "role": "assistant",
                "content": content,
                "tool_calls": [],
            })
            trace.stopped_reason = "final_answer"
            break

        # Process tool calls
        tool_calls_data = []
        tool_results = []
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                fn_args = {"raw": tc.function.arguments}

            trace.tool_call_sequence.append(fn_name)
            tool_calls_data.append({
                "id": tc.id,
                "name": fn_name,
                "arguments": fn_args,
            })

            # Check stop_on
            if fn_name in config.stop_on:
                tool_results.append({
                    "tool_call_id": tc.id,
                    "result": {"status": "stopped", "reason": f"stop_on trigger: {fn_name}"},
                })
                trace.turns.append({
                    "turn": turn,
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls_data,
                    "tool_results": tool_results,
                })
                trace.stopped_reason = "stop_tool"
                trace.wall_time_ms = int((time.monotonic() - start_time) * 1000)
                return trace

            # Resolve via mocks
            mock_result = resolve_tool_call(fn_name, fn_args, mocks, on_unmocked)
            tool_results.append({
                "tool_call_id": tc.id,
                "result": mock_result,
            })

        # Record this turn
        trace.turns.append({
            "turn": turn,
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls_data,
            "tool_results": tool_results,
        })

        # Append assistant message with tool_calls to messages
        assistant_msg = {"role": "assistant", "content": content}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_msg)

        # Append tool results as tool messages
        for tr in tool_results:
            result_content = json.dumps(tr["result"]) if not isinstance(tr["result"], str) else tr["result"]
            messages.append({
                "role": "tool",
                "tool_call_id": tr["tool_call_id"],
                "content": result_content,
            })

    else:
        # Exhausted max_turns
        trace.stopped_reason = "max_turns"

    trace.wall_time_ms = int((time.monotonic() - start_time) * 1000)
    return trace


# --- Metrics extraction ---

def compute_trajectory_metrics(trace: LoopTrace) -> dict[str, Any]:
    """Extract §3a trajectory metrics from a LoopTrace."""
    seq = trace.tool_call_sequence
    unique = set(seq)

    # Redundant call rate: repeated calls to the same tool / total calls
    if len(seq) > 0:
        from collections import Counter
        counts = Counter(seq)
        redundant = sum(c - 1 for c in counts.values() if c > 1)
        redundant_rate = redundant / len(seq)
    else:
        redundant_rate = 0.0

    return {
        "tool_call_count": len(seq),
        "tool_call_sequence": seq,
        "unique_tools_used": sorted(unique),
        "redundant_call_rate": round(redundant_rate, 3),
        "max_turns_hit": trace.stopped_reason == "max_turns",
        "stopped_reason": trace.stopped_reason,
        "turns_used": len(trace.turns),
    }


def compute_subagent_routing_metrics(trace: LoopTrace) -> dict[str, Any]:
    """Extract subagent routing metrics from a LoopTrace.

    Looks at runSubagent calls and extracts which agents were invoked.
    """
    agents_invoked = []
    agent_order = []

    for turn in trace.turns:
        for tc in turn.get("tool_calls", []):
            if tc["name"] == "runSubagent":
                agent_name = tc["arguments"].get("agentName", "unknown")
                agents_invoked.append(agent_name)
                agent_order.append(agent_name)

    return {
        "agents_invoked": agents_invoked,
        "unique_agents": sorted(set(agents_invoked)),
        "agent_count": len(agents_invoked),
        "agent_order": agent_order,
        "first_agent": agents_invoked[0] if agents_invoked else None,
    }


def compute_cost(trace: LoopTrace) -> dict[str, Any]:
    """Extract cost metrics from a LoopTrace."""
    return {
        "input_tokens": trace.total_input_tokens,
        "output_tokens": trace.total_output_tokens,
        "wall_time_ms": trace.wall_time_ms,
    }
