"""Bedrock-Compatible MCP Tools Wrapper

Wraps Agno's MCPTools to translate responses into Bedrock Converse API format.
"""

from typing import Any, Dict, List, Optional
from agno.tools.mcp import MCPTools
from agno.tools.toolkit import Toolkit
from agno.tools.function import Function
import logging

from cua.utils.mcp_bedrock_adapter import get_adapter

logger = logging.getLogger(__name__)


class BedrockMCPTools(Toolkit):
    """MCP Tools wrapper with Bedrock translation layer.

    This wrapper:
    1. Delegates to native MCPTools for MCP protocol communication
    2. Translates MCP responses to Bedrock-compatible format
    3. Handles image format specification
    4. Wraps responses in toolResult blocks
    """

    def __init__(
        self,
        command: str,
        env: Optional[Dict[str, str]] = None,
        refresh_connection: bool = False,
        **kwargs
    ):
        """Initialize Bedrock-compatible MCP tools.

        Args:
            command: Command to start MCP server (e.g., "npx @playwright/mcp")
            env: Environment variables for MCP server
            refresh_connection: Whether to auto-reconnect on failures
            **kwargs: Additional arguments passed to Toolkit
        """
        super().__init__(**kwargs)

        # Create underlying MCPTools instance
        self.mcp_tools = MCPTools(
            command=command,
            env=env,
            refresh_connection=refresh_connection
        )

        # Get adapter instance
        self.adapter = get_adapter()

        self.logger = logger
        self.logger.info(f"Initialized BedrockMCPTools for command: {command}")

    def connect(self):
        """Connect to MCP server."""
        return self.mcp_tools.connect()

    async def aconnect(self):
        """Async connect to MCP server."""
        return await self.mcp_tools.aconnect()

    def disconnect(self):
        """Disconnect from MCP server."""
        return self.mcp_tools.disconnect()

    async def adisconnect(self):
        """Async disconnect from MCP server."""
        return await self.mcp_tools.adisconnect()

    def get_tools(self) -> List[Function]:
        """Get available MCP tools.

        Returns:
            List of Function objects representing MCP tools
        """
        # Get tools from underlying MCPTools
        mcp_tool_functions = self.mcp_tools.get_tools()

        # Wrap each tool function to apply translation
        wrapped_functions = []
        for tool_func in mcp_tool_functions:
            wrapped_func = self._wrap_tool_function(tool_func)
            wrapped_functions.append(wrapped_func)

        return wrapped_functions

    def _wrap_tool_function(self, original_func: Function) -> Function:
        """Wrap an MCP tool function to translate responses.

        Args:
            original_func: Original MCP tool function

        Returns:
            Wrapped function that translates responses
        """
        # Create a new Function with the same metadata but wrapped entrypoint
        original_entrypoint = original_func.entrypoint

        def translated_entrypoint(*args, **kwargs):
            """Wrapper that translates MCP response to Bedrock format."""
            try:
                # Call original MCP tool
                mcp_response = original_entrypoint(*args, **kwargs)

                # Log raw response for debugging
                self.logger.debug(f"Raw MCP response from {original_func.name}: {type(mcp_response)}")

                # For Bedrock compatibility, we need to return the raw response
                # and let Agno's framework handle the toolResult wrapping
                # The adapter will be used at a different layer

                # Actually, we need to ensure the response is in a format
                # that Agno can serialize properly for Bedrock
                return self._ensure_bedrock_compatible(mcp_response)

            except Exception as e:
                self.logger.error(f"Error in MCP tool {original_func.name}: {e}")
                # Return error message as text
                return f"Error executing {original_func.name}: {str(e)}"

        # Create new Function with same metadata
        wrapped_func = Function(
            name=original_func.name,
            entrypoint=translated_entrypoint,
            description=original_func.description,
            parameters=original_func.parameters,
            sanitize_arguments=original_func.sanitize_arguments
        )

        return wrapped_func

    def _ensure_bedrock_compatible(self, mcp_response: Any) -> Any:
        """Ensure MCP response is Bedrock-compatible.

        This handles:
        1. Image responses - ensure they have format specification
        2. Complex objects - convert to simple types
        3. Lists/dicts - ensure they're JSON-serializable

        Args:
            mcp_response: Raw MCP response

        Returns:
            Bedrock-compatible response
        """
        if isinstance(mcp_response, str):
            # Simple text response - already compatible
            return mcp_response

        elif isinstance(mcp_response, dict):
            # Check if it's an image response
            if "type" in mcp_response and mcp_response["type"] == "image":
                # Ensure image has format
                if "format" not in mcp_response.get("image", {}):
                    # Add format specification
                    return self._fix_image_format(mcp_response)
                return mcp_response

            # Check for MCP content structure
            if "content" in mcp_response:
                # Process each content item
                fixed_content = []
                for item in mcp_response["content"]:
                    fixed_item = self._ensure_bedrock_compatible(item)
                    fixed_content.append(fixed_item)
                return {"content": fixed_content}

            # Regular dict - ensure JSON-serializable
            return mcp_response

        elif isinstance(mcp_response, list):
            # Process each item
            return [self._ensure_bedrock_compatible(item) for item in mcp_response]

        else:
            # Convert other types to string
            return str(mcp_response)

    def _fix_image_format(self, image_response: Dict[str, Any]) -> Dict[str, Any]:
        """Fix image response to include format specification.

        Args:
            image_response: MCP image response

        Returns:
            Fixed image response with format
        """
        # Extract MIME type or default to PNG
        mime_type = image_response.get("mimeType", "image/png")

        # Determine format
        if "png" in mime_type.lower():
            format_type = "png"
        elif "jpeg" in mime_type.lower() or "jpg" in mime_type.lower():
            format_type = "jpeg"
        elif "gif" in mime_type.lower():
            format_type = "gif"
        elif "webp" in mime_type.lower():
            format_type = "webp"
        else:
            format_type = "png"  # Default

        # Add format to response
        if "image" in image_response:
            image_response["image"]["format"] = format_type
        else:
            # Restructure to proper format
            image_response = {
                "type": "image",
                "image": {
                    "format": format_type,
                    "source": image_response.get("source", image_response.get("data", {}))
                }
            }

        return image_response


def create_bedrock_mcp_tools(
    command: str,
    env: Optional[Dict[str, str]] = None,
    refresh_connection: bool = True
) -> BedrockMCPTools:
    """Factory function to create Bedrock-compatible MCP tools.

    Args:
        command: Command to start MCP server
        env: Environment variables
        refresh_connection: Auto-reconnect on failures

    Returns:
        BedrockMCPTools instance
    """
    return BedrockMCPTools(
        command=command,
        env=env,
        refresh_connection=refresh_connection
    )
