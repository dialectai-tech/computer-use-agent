"""Direct AWS Bedrock Converse API wrapper with tool call support.

Thin wrapper around boto3 converse() with:
- Token tracking across all calls
- Tool call parsing
- Tool result message building
- Result truncation to prevent context bloat
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import boto3


# Model ID mappings (inference profile IDs with us. prefix for cross-region)
MODEL_IDS: dict[str, str] = {
    "haiku": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "haiku-3.5": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    "sonnet": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "sonnet-4.5": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "opus": "us.anthropic.claude-opus-4-5-20251101-v1:0",
}

# Maximum characters per tool result — caps quadratic context growth
MAX_TOOL_RESULT_CHARS = 2000


@dataclass
class ToolCall:
    """A tool call extracted from a Bedrock response."""

    id: str
    name: str
    args: dict


@dataclass
class BedrockTurn:
    """Result of a single Bedrock Converse API call."""

    assistant_message: dict  # Ready to append to messages list
    tool_calls: list[ToolCall]
    text: str
    input_tokens: int
    output_tokens: int


@dataclass
class ToolResult:
    """Result to return for a tool call."""

    id: str
    content: str  # Text content (will be truncated if needed)


class BedrockEngine:
    """Direct boto3 Bedrock Converse API wrapper.

    Handles authentication, tool call parsing, and token tracking.
    Maintains cumulative token counts across all calls (used for reporting).

    Authentication order:
    1. AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY env vars
    2. AWS_BEARER_TOKEN_BEDROCK → mapped to AWS_SESSION_TOKEN
    3. IAM role (EC2/ECS)
    4. ~/.aws/credentials fallback
    """

    def __init__(self, model: str = "haiku", region: str = "us-east-1") -> None:
        self.model_id = MODEL_IDS.get(model.lower(), model)
        self.region = region

        # Map AWS_BEARER_TOKEN_BEDROCK to AWS_SESSION_TOKEN if needed
        if "AWS_BEARER_TOKEN_BEDROCK" in os.environ and "AWS_SESSION_TOKEN" not in os.environ:
            os.environ["AWS_SESSION_TOKEN"] = os.environ["AWS_BEARER_TOKEN_BEDROCK"]

        self.client = boto3.client("bedrock-runtime", region_name=region)

        self.total_input_tokens = 0
        self.total_output_tokens = 0

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def call(
        self,
        system: str,
        messages: list[dict],
        tool_config: dict,
    ) -> BedrockTurn:
        """Make a single Bedrock Converse API call.

        Args:
            system: System prompt string
            messages: Conversation messages list (user/assistant alternating)
            tool_config: Bedrock toolConfig dict with tool specs

        Returns:
            BedrockTurn with assistant message, tool calls, text, token counts
        """
        kwargs: dict[str, Any] = {
            "modelId": self.model_id,
            "system": [{"text": system}],
            "messages": messages,
            "inferenceConfig": {"maxTokens": 4096},
        }

        if tool_config and tool_config.get("tools"):
            kwargs["toolConfig"] = tool_config

        response = self.client.converse(**kwargs)

        # Track cumulative tokens
        usage = response.get("usage", {})
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        # Extract content blocks from response
        assistant_msg = response.get("output", {}).get("message", {})
        content_blocks = assistant_msg.get("content", [])

        # Parse text and tool calls from content blocks
        text_parts = []
        tool_calls = []

        for block in content_blocks:
            if "text" in block:
                text_parts.append(block["text"])
            elif "toolUse" in block:
                tc = block["toolUse"]
                tool_calls.append(
                    ToolCall(
                        id=tc.get("toolUseId", ""),
                        name=tc.get("name", ""),
                        args=tc.get("input", {}),
                    )
                )

        text = " ".join(text_parts)

        # Build assistant message ready for messages list
        assistant_message = {"role": "assistant", "content": content_blocks}

        return BedrockTurn(
            assistant_message=assistant_message,
            tool_calls=tool_calls,
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def make_tool_result_message(self, results: list[ToolResult]) -> dict:
        """Build a single user message containing all tool results.

        Bedrock Converse API requires consecutive tool results to be grouped
        into a single message with role="user", not sent as separate messages.

        Each result is truncated to MAX_TOOL_RESULT_CHARS to prevent context bloat.

        Args:
            results: List of ToolResult objects

        Returns:
            Bedrock message dict: {"role": "user", "content": [{toolResult: ...}, ...]}
        """
        content = []
        for result in results:
            text = result.content
            if len(text) > MAX_TOOL_RESULT_CHARS:
                omitted = len(text) - MAX_TOOL_RESULT_CHARS
                text = text[:MAX_TOOL_RESULT_CHARS] + f"\n[...{omitted} chars omitted]"

            content.append(
                {
                    "toolResult": {
                        "toolUseId": result.id,
                        "content": [{"text": text}],
                    }
                }
            )

        return {"role": "user", "content": content}
