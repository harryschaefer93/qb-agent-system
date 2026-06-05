"""
Foundry client for live behavioral evals.

Sends agent system prompts + test case prompts to a Foundry model endpoint
using Entra ID auth (DefaultAzureCredential). No API keys.

Config is loaded from config.yaml under the `foundry` key:
  foundry:
    endpoint: https://foundry-agent-evals.openai.azure.com/
    deployment: gpt-4.1-mini
    api_version: 2024-12-01-preview
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

logger = logging.getLogger(__name__)

_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"


@dataclass
class FoundryConfig:
    endpoint: str
    deployment: str
    api_version: str = "2024-12-01-preview"


def load_foundry_config(config: dict) -> FoundryConfig:
    """Load Foundry config from the eval harness config dict."""
    fc = config.get("foundry", {})
    endpoint = fc.get("endpoint")
    deployment = fc.get("deployment")
    if not endpoint or not deployment:
        raise ValueError(
            "Foundry config missing. Add to config.yaml:\n"
            "  foundry:\n"
            "    endpoint: https://<your-resource>.openai.azure.com/\n"
            "    deployment: <deployment-name>\n"
        )
    return FoundryConfig(
        endpoint=endpoint,
        deployment=deployment,
        api_version=fc.get("api_version", "2024-12-01-preview"),
    )


def create_foundry_client(cfg: FoundryConfig) -> AzureOpenAI:
    """Create an AzureOpenAI client using Entra ID (DefaultAzureCredential)."""
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, _TOKEN_SCOPE)

    return AzureOpenAI(
        azure_endpoint=cfg.endpoint,
        azure_ad_token_provider=token_provider,
        api_version=cfg.api_version,
    )


def generate_live_response(
    client: AzureOpenAI,
    deployment: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> str:
    """
    Send a system prompt + user prompt to the Foundry model and return the response.

    Low temperature (0.3) for eval consistency — we want the model's
    default behavior, not creative variation.
    """
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_completion_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


@dataclass
class ToolCallResponse:
    """Full response including tool calls for function-calling evals."""
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    raw_message: Optional[dict] = None


def generate_live_response_with_tools(
    client: AzureOpenAI,
    deployment: str,
    system_prompt: str,
    user_prompt: str,
    tools: list[dict],
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> ToolCallResponse:
    """
    Send a prompt with tool definitions so the model produces actual tool_calls.

    Returns a ToolCallResponse with both content and structured tool calls.
    This is the correct way to evaluate behavioral compliance — the model
    actually invokes tools (askQuestions, runSubagent, etc.) instead of
    narrating about them.
    """
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tools=tools,
        max_completion_tokens=max_tokens,
        temperature=temperature,
    )
    msg = response.choices[0].message
    content = msg.content or ""

    tool_calls = []
    if msg.tool_calls:
        for tc in msg.tool_calls:
            tool_calls.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            })

    # Build raw message dict for passing to Foundry evaluators
    raw = {"role": "assistant", "content": content}
    if tool_calls:
        raw["tool_calls"] = tool_calls

    return ToolCallResponse(content=content, tool_calls=tool_calls, raw_message=raw)


def load_tool_definitions(tools_path: Path) -> list[dict]:
    """Load tool definitions from a JSON file (OpenAI function-calling format)."""
    with open(tools_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_agent_system_prompt(agent_def_path: Path) -> str:
    """
    Extract the system prompt from an agent .md definition.

    Reads everything after the YAML frontmatter (after the second '---').
    """
    text = agent_def_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) >= 3:
        return parts[2].strip()
    # Fallback: return everything
    return text
