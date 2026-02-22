"""Custom Bedrock model with MCP compatibility.

Extends Agno's AwsBedrock to properly format MCP tool responses for Bedrock API.

Key fix: Bedrock Converse API requires consecutive tool results to be grouped
into a single message, not sent as separate messages.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from agno.models.aws import AwsBedrock
from agno.models.message import Message
from agno.utils.log import log_debug, log_warning


class BedrockMCPModel(AwsBedrock):
    """AWS Bedrock model with MCP tool result translation.

    Extends AwsBedrock to properly handle MCP tool results that may
    contain text-only responses (not wrapped in json/text blocks).

    Critical fix: Groups consecutive tool results into a single message
    with role="user" to satisfy Bedrock Converse API requirements.
    """

    def _format_messages(
        self, messages: List[Message], compress_tool_results: bool = False
    ) -> Tuple[List[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
        """Override to handle MCP tool results properly.

        MCP tools may return simple strings instead of structured content.
        We need to ensure they're properly wrapped for Bedrock.

        CRITICAL: Multiple consecutive tool results must be grouped into a
        single message with role="user", not separate messages.

        Args:
            messages: List of messages to format
            compress_tool_results: Whether to compress tool results

        Returns:
            Tuple of (formatted_messages, system_message)
        """
        formatted_messages: List[Dict[str, Any]] = []
        system_message = None

        # Collect consecutive tool results to group them
        pending_tool_results: List[Dict[str, Any]] = []

        for message in messages:
            if message.role == "system":
                # Flush any pending tool results before system message
                if pending_tool_results:
                    formatted_messages.append({
                        "role": "user",
                        "content": pending_tool_results
                    })
                    pending_tool_results = []
                system_message = [{"text": message.content}]

            elif message.role == "tool":
                # Collect tool result - will be grouped with consecutive tool results
                content = message.get_content(use_compressed_content=compress_tool_results)
                tool_result_content = self._format_tool_result_content(content)

                tool_result = {
                    "toolUseId": message.tool_call_id,
                    "content": tool_result_content,
                }
                pending_tool_results.append({"toolResult": tool_result})

            else:
                # Flush any pending tool results before this non-tool message
                if pending_tool_results:
                    formatted_messages.append({
                        "role": "user",
                        "content": pending_tool_results
                    })
                    pending_tool_results = []

                formatted_message: Dict[str, Any] = {"role": message.role, "content": []}

                if isinstance(message.content, list):
                    formatted_message["content"].extend(message.content)
                elif message.tool_calls:
                    tool_use_content = []
                    for tool_call in message.tool_calls:
                        try:
                            arguments = tool_call["function"]["arguments"]
                            if not arguments or arguments.strip() == "":
                                tool_input = {}
                            else:
                                tool_input = json.loads(arguments)
                        except (json.JSONDecodeError, KeyError) as e:
                            log_warning(f"Failed to parse tool call arguments: {e}")
                            tool_input = {}

                        tool_use_content.append(
                            {
                                "toolUse": {
                                    "toolUseId": tool_call["id"],
                                    "name": tool_call["function"]["name"],
                                    "input": tool_input,
                                }
                            }
                        )
                    formatted_message["content"].extend(tool_use_content)
                else:
                    formatted_message["content"].append({"text": message.content})

                # Handle images
                if message.images:
                    for image in message.images:
                        if not image.content:
                            log_warning("Image has no content, skipping")
                            raise ValueError("Image content is required for AWS Bedrock.")
                        if not image.format:
                            image.format = "png"

                        formatted_message["content"].append(
                            {
                                "image": {
                                    "format": image.format,
                                    "source": {
                                        "bytes": image.content,
                                    },
                                }
                            }
                        )

                formatted_messages.append(formatted_message)

        # Flush any remaining pending tool results
        if pending_tool_results:
            formatted_messages.append({
                "role": "user",
                "content": pending_tool_results
            })

        log_debug(f"Formatted {len(messages)} messages → {len(formatted_messages)} Bedrock messages")
        return formatted_messages, system_message

    def _format_tool_result_content(self, content: Any) -> List[Dict[str, Any]]:
        """Format tool result content for Bedrock API.

        MCP tools may return:
        - Plain strings → wrap in {"text": ...}
        - Structured objects → wrap in {"json": ...}
        - Already-formatted Bedrock content → use as-is

        Args:
            content: Raw tool result content

        Returns:
            List of content blocks for Bedrock API
        """
        if isinstance(content, list):
            # Check if already Bedrock-formatted
            if all(isinstance(item, dict) and any(k in item for k in ["text", "json", "image"]) for item in content):
                return content
            return [{"json": {"result": content}}]

        if isinstance(content, str):
            return [{"text": content}]

        return [{"json": {"result": content}}]


def get_bedrock_mcp_model(
    model_type: str = "haiku",
    region: Optional[str] = None
) -> BedrockMCPModel:
    """Create Bedrock MCP model instance.

    Args:
        model_type: "haiku" or "sonnet"
        region: AWS region (default: us-east-1)

    Returns:
        BedrockMCPModel configured for the specified model type
    """
    import os

    HAIKU_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    SONNET_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250514-v1:0"

    model_id = HAIKU_MODEL_ID if model_type == "haiku" else SONNET_MODEL_ID

    if region is None:
        region = os.getenv("AWS_REGION", "us-east-1")

    if "AWS_BEARER_TOKEN_BEDROCK" in os.environ and "AWS_SESSION_TOKEN" not in os.environ:
        os.environ["AWS_SESSION_TOKEN"] = os.environ["AWS_BEARER_TOKEN_BEDROCK"]

    return BedrockMCPModel(
        id=model_id,
        aws_region=region
    )
