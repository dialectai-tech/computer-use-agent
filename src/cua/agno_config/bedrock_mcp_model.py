"""Custom Bedrock model with MCP compatibility.

Extends Agno's AwsBedrock to properly format MCP tool responses for Bedrock API.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from agno.models.aws import AwsBedrock
from agno.models.message import Message
from agno.utils.log import log_debug, log_warning


class BedrockMCPModel(AwsBedrock):
    """AWS Bedrock model with MCP tool result translation.

    This model extends AwsBedrock to properly handle MCP tool results
    that may contain text-only responses (not wrapped in json/text blocks).
    """

    def _format_messages(
        self, messages: List[Message], compress_tool_results: bool = False
    ) -> Tuple[List[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
        """Override to handle MCP tool results properly.

        MCP tools may return simple strings instead of structured content.
        We need to ensure they're properly wrapped for Bedrock.

        Args:
            messages: List of messages to format
            compress_tool_results: Whether to compress tool results

        Returns:
            Tuple of (formatted_messages, system_message)
        """
        log_debug(f"BedrockMCPModel._format_messages called with {len(messages)} messages")

        formatted_messages: List[Dict[str, Any]] = []
        system_message = None

        for idx, message in enumerate(messages):
            log_debug(f"Processing message {idx}: role={message.role}, "
                     f"has_content={bool(message.content)}, "
                     f"has_tool_calls={bool(message.tool_calls)}, "
                     f"has_images={bool(message.images)}, "
                     f"tool_call_id={message.tool_call_id}")
            if message.role == "system":
                system_message = [{"text": message.content}]
            elif message.role == "tool":
                # Get tool result content
                content = message.get_content(use_compressed_content=compress_tool_results)

                log_debug(f"Tool result - tool_call_id={message.tool_call_id}, "
                         f"content_type={type(content)}, "
                         f"content_preview={str(content)[:200] if content else 'None'}")

                # Check if message has images
                if message.images:
                    log_debug(f"Tool result has {len(message.images)} images")
                    for img_idx, img in enumerate(message.images):
                        log_debug(f"  Image {img_idx}: format={img.format}, "
                                 f"has_content={bool(img.content)}, "
                                 f"content_size={len(img.content) if img.content else 0}")

                # Handle MCP tool results which might be plain strings
                tool_result_content = self._format_tool_result_content(content)

                tool_result = {
                    "toolUseId": message.tool_call_id,
                    "content": tool_result_content,
                }

                formatted_message: Dict[str, Any] = {
                    "role": "user",
                    "content": [{"toolResult": tool_result}]
                }

                log_debug(f"Formatted tool result: {formatted_message}")
                formatted_messages.append(formatted_message)
            else:
                # Handle other messages normally (use parent implementation logic)
                formatted_message = {"role": message.role, "content": []}

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
                    log_debug(f"Message has {len(message.images)} images")
                    for img_idx, image in enumerate(message.images):
                        log_debug(f"Processing image {img_idx}: format={image.format}, "
                                 f"has_content={bool(image.content)}, "
                                 f"content_size={len(image.content) if image.content else 0}")

                        if not image.content:
                            log_warning(f"Image {img_idx} has no content!")
                            raise ValueError("Image content is required for AWS Bedrock.")
                        if not image.format:
                            log_warning(f"Image {img_idx} has no format! Attempting to infer...")
                            # Try to infer format from content or default to png
                            image.format = "png"
                            log_debug(f"Set image format to: {image.format}")

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

        return formatted_messages, system_message

    def _format_tool_result_content(self, content: Any) -> List[Dict[str, Any]]:
        """Format tool result content for Bedrock API.

        MCP tools may return:
        - Plain strings → wrap in {"text": ...}
        - Structured objects → wrap in {"json": ...}
        - Already formatted content → use as-is

        Args:
            content: Raw tool result content

        Returns:
            List of content blocks for Bedrock API
        """
        log_debug(f"_format_tool_result_content called with type={type(content)}")

        # If content is already a list, check if it's properly formatted
        if isinstance(content, list):
            log_debug(f"Content is list with {len(content)} items")
            if content:
                log_debug(f"First item type: {type(content[0])}, value preview: {str(content[0])[:100]}")

            # Check if list items are already Bedrock-formatted
            if all(isinstance(item, dict) and any(k in item for k in ["text", "json", "image"]) for item in content):
                log_debug("Content is already Bedrock-formatted, returning as-is")
                return content
            # Otherwise wrap list as JSON
            log_debug("Content is list but not Bedrock-formatted, wrapping in json block")
            return [{"json": {"result": content}}]

        # If content is a plain string, wrap in text block
        if isinstance(content, str):
            log_debug(f"Wrapping string tool result in text block: {content[:100]}...")
            return [{"text": content}]

        # If content is dict/list/other, wrap in json block
        log_debug(f"Wrapping structured tool result in json block: {type(content)}, preview: {str(content)[:200]}")
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

    # Model IDs
    HAIKU_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    SONNET_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250514-v1:0"

    # Select model
    model_id = HAIKU_MODEL_ID if model_type == "haiku" else SONNET_MODEL_ID

    # Get region
    if region is None:
        region = os.getenv("AWS_REGION", "us-east-1")

    # Handle AWS_BEARER_TOKEN_BEDROCK → AWS_SESSION_TOKEN mapping
    if "AWS_BEARER_TOKEN_BEDROCK" in os.environ and "AWS_SESSION_TOKEN" not in os.environ:
        os.environ["AWS_SESSION_TOKEN"] = os.environ["AWS_BEARER_TOKEN_BEDROCK"]

    return BedrockMCPModel(
        id=model_id,
        aws_region=region
    )
