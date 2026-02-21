"""MCP → Bedrock Translation Adapter

Translates MCP tool responses into AWS Bedrock Converse API compatible format.

This adapter solves two critical compatibility issues:
1. Image Format: MCP returns images without format specification,
   Bedrock requires {"format": "png", "source": {"bytes": b"..."}}
2. Tool Results: MCP returns native format, Bedrock expects
   {"toolResult": {"toolUseId": "...", "content": [...]}}
"""

import base64
import json
from typing import Any, Dict, List, Union
import logging

logger = logging.getLogger(__name__)


class MCPBedrockAdapter:
    """Adapt MCP tool responses for Bedrock Converse API compatibility."""

    def __init__(self):
        """Initialize the adapter."""
        self.logger = logger

    def translate_tool_result(
        self, mcp_response: Any, tool_use_id: str
    ) -> Dict[str, Any]:
        """Convert MCP response to Bedrock toolResult format.

        Args:
            mcp_response: Raw response from MCP tool (can be dict, str, list, etc.)
            tool_use_id: The tool use ID from Bedrock request

        Returns:
            Bedrock-compatible toolResult block:
            {
                "toolResult": {
                    "toolUseId": "tooluse_xxx",
                    "content": [
                        {"text": "..."},
                        {"image": {"format": "png", "source": {"bytes": b"..."}}}
                    ]
                }
            }
        """
        content = self._convert_to_content_blocks(mcp_response)

        return {
            "toolResult": {
                "toolUseId": tool_use_id,
                "content": content,
                "status": "success"
            }
        }

    def _convert_to_content_blocks(self, mcp_response: Any) -> List[Dict[str, Any]]:
        """Convert MCP response to Bedrock content blocks.

        Args:
            mcp_response: Raw MCP response

        Returns:
            List of Bedrock content blocks
        """
        content_blocks = []

        # Handle different MCP response types
        if isinstance(mcp_response, str):
            # Simple string response
            content_blocks.append({"text": mcp_response})

        elif isinstance(mcp_response, dict):
            # Check for MCP content structure
            if "content" in mcp_response:
                # MCP standard format: {"content": [...]}
                for item in mcp_response["content"]:
                    block = self._convert_content_item(item)
                    if block:
                        content_blocks.append(block)
            elif "type" in mcp_response:
                # Single content item: {"type": "text", "text": "..."}
                block = self._convert_content_item(mcp_response)
                if block:
                    content_blocks.append(block)
            else:
                # Generic dict - convert to JSON text
                content_blocks.append({"text": json.dumps(mcp_response)})

        elif isinstance(mcp_response, list):
            # List of content items
            for item in mcp_response:
                block = self._convert_content_item(item)
                if block:
                    content_blocks.append(block)

        else:
            # Fallback: convert to string
            content_blocks.append({"text": str(mcp_response)})

        return content_blocks

    def _convert_content_item(self, item: Dict[str, Any]) -> Dict[str, Any] | None:
        """Convert a single MCP content item to Bedrock format.

        Args:
            item: MCP content item (e.g., {"type": "text", "text": "..."})

        Returns:
            Bedrock content block or None if unsupported
        """
        if not isinstance(item, dict):
            return {"text": str(item)}

        content_type = item.get("type", "text")

        if content_type == "text":
            return {"text": item.get("text", "")}

        elif content_type == "image":
            return self._handle_image_content(item)

        elif content_type == "resource":
            # MCP resource reference - convert to text
            return {"text": f"Resource: {item.get('resource', {}).get('uri', 'unknown')}"}

        else:
            # Unknown type - convert to JSON text
            return {"text": json.dumps(item)}

    def _handle_image_content(self, mcp_image: Dict[str, Any]) -> Dict[str, Any]:
        """Convert MCP image to Bedrock image format.

        MCP format:
            {"type": "image", "data": "base64...", "mimeType": "image/png"}
            or
            {"type": "image", "source": {"bytes": b"..."}}

        Bedrock format:
            {"image": {"format": "png", "source": {"bytes": b"..."}}}

        Args:
            mcp_image: MCP image content

        Returns:
            Bedrock image block
        """
        # Determine image format
        mime_type = mcp_image.get("mimeType", "image/png")
        image_format = self._extract_image_format(mime_type)

        # Get image data
        image_bytes = None

        if "data" in mcp_image:
            # Base64 encoded data
            base64_data = mcp_image["data"]
            try:
                image_bytes = base64.b64decode(base64_data)
            except Exception as e:
                self.logger.error(f"Failed to decode base64 image: {e}")
                return {"text": f"[Image decode error: {e}]"}

        elif "source" in mcp_image and "bytes" in mcp_image["source"]:
            # Already in bytes format
            image_bytes = mcp_image["source"]["bytes"]

        else:
            self.logger.warning(f"Unknown image format in MCP response: {mcp_image}")
            return {"text": "[Image data not found]"}

        return {
            "image": {
                "format": image_format,
                "source": {"bytes": image_bytes}
            }
        }

    def _extract_image_format(self, mime_type: str) -> str:
        """Extract Bedrock-compatible format from MIME type.

        Args:
            mime_type: MIME type (e.g., "image/png", "image/jpeg")

        Returns:
            Bedrock format string ("png", "jpeg", "gif", "webp")
        """
        mime_lower = mime_type.lower()

        if "png" in mime_lower:
            return "png"
        elif "jpeg" in mime_lower or "jpg" in mime_lower:
            return "jpeg"
        elif "gif" in mime_lower:
            return "gif"
        elif "webp" in mime_lower:
            return "webp"
        else:
            # Default to png if unknown
            self.logger.warning(f"Unknown MIME type {mime_type}, defaulting to png")
            return "png"

    def translate_error_result(
        self, error: Exception, tool_use_id: str
    ) -> Dict[str, Any]:
        """Convert an error to Bedrock toolResult format.

        Args:
            error: The exception that occurred
            tool_use_id: The tool use ID from Bedrock request

        Returns:
            Bedrock-compatible error toolResult
        """
        return {
            "toolResult": {
                "toolUseId": tool_use_id,
                "content": [
                    {
                        "text": f"Error executing tool: {str(error)}"
                    }
                ],
                "status": "error"
            }
        }


# Singleton instance for convenience
_adapter_instance = None


def get_adapter() -> MCPBedrockAdapter:
    """Get singleton adapter instance.

    Returns:
        Shared MCPBedrockAdapter instance
    """
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = MCPBedrockAdapter()
    return _adapter_instance
