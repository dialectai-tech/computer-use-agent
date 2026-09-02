"""Persistent Playwright MCP session that outlives individual step conversations.

The browser session stays alive across all steps.
Only the LLM conversation context resets between steps.

Uses the mcp Python SDK (already installed as agno dependency):
- mcp.client.stdio.stdio_client: Start subprocess + connect via stdio
- mcp.ClientSession: Manage MCP protocol session
"""

from __future__ import annotations

import base64
import contextlib
from pathlib import Path
from typing import Optional

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cua.agno_agents.solo_agent import build_playwright_command


# Tools to expose to the model — filtered to the essential ~12
# Dropping: browser_run_code (wastes 36% of calls), install, resize, close,
# hover, drag, file_upload, navigate_back, reload, console/network/tabs, verify_*
ALLOWED_TOOLS: frozenset[str] = frozenset(
    {
        "browser_navigate",
        "browser_snapshot",
        "browser_click",
        "browser_type",
        "browser_press_key",
        "browser_evaluate",
        "browser_wait_for",
        "browser_select_option",
        "browser_mouse_wheel",
        "browser_handle_dialog",
        "browser_take_screenshot",
        "browser_fill_form",
    }
)

MAX_RESULT_CHARS = 1500  # Reduced from 2000 to cut within-step quadratic growth


class PlaywrightMCPSession:
    """Persistent Playwright MCP connection that outlives individual steps.

    The browser session is started once and reused for all steps.
    Only the LLM conversation context resets between steps.

    Usage:
        async with PlaywrightMCPSession(headless=True) as mcp:
            await mcp.call_tool("browser_navigate", {"url": "https://..."})
            result = await mcp.call_tool("browser_snapshot", {})
    """

    def __init__(
        self,
        recordings_dir: Optional[Path] = None,
        record_video: bool = False,
        viewport_size: str = "1280x720",
        headless: bool = True,
    ) -> None:
        self.recordings_dir = recordings_dir
        self.record_video = record_video
        self.viewport_size = viewport_size
        self.headless = headless

        self._session: Optional[ClientSession] = None
        self._tool_specs: list[dict] = []
        self._exit_stack = contextlib.AsyncExitStack()

    async def __aenter__(self) -> PlaywrightMCPSession:
        """Start Playwright MCP subprocess and initialize session."""
        cmd_str = build_playwright_command(
            recordings_dir=self.recordings_dir,
            record_video=self.record_video,
            viewport_size=self.viewport_size,
            headless=self.headless,
        )
        # --isolated keeps browser profile in memory, prevents SingletonLock
        # conflicts when multiple sessions start/stop (e.g. after crashes)
        cmd_str += " --isolated"

        # Parse command string into command + args for StdioServerParameters
        # e.g. "npx @playwright/mcp --headless --viewport-size=1280x720 --isolated"
        parts = cmd_str.split()
        command = parts[0]
        args = parts[1:]

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=None,
        )

        # Enter stdio_client context — starts the subprocess
        read, write = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )

        # Enter ClientSession context — manages MCP protocol
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )

        # Initialize MCP handshake
        await self._session.initialize()

        # Discover and cache tool schemas (filtered to allowed set)
        await self._load_tool_specs()

        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Gracefully shut down MCP subprocess."""
        await self._exit_stack.aclose()

    async def _load_tool_specs(self) -> None:
        """Load tool schemas from MCP, filter to allowed set, convert to Bedrock format."""
        assert self._session is not None
        response = await self._session.list_tools()

        self._tool_specs = []
        for tool in response.tools:
            if tool.name not in ALLOWED_TOOLS:
                continue

            # Get input schema (may be None for some tools)
            input_schema = tool.inputSchema if tool.inputSchema else {
                "type": "object",
                "properties": {},
            }

            spec = {
                "toolSpec": {
                    "name": tool.name,
                    "description": tool.description or f"Playwright browser tool: {tool.name}",
                    "inputSchema": {
                        "json": input_schema,
                    },
                }
            }
            self._tool_specs.append(spec)

    def get_tool_specs(self) -> list[dict]:
        """Return filtered Bedrock-formatted tool specifications."""
        return self._tool_specs

    def get_tool_config(self) -> dict:
        """Return Bedrock toolConfig object (passed to BedrockEngine.call)."""
        return {"tools": self._tool_specs}

    async def call_tool(self, name: str, args: dict) -> str:
        """Call an MCP tool and return result as a truncated string.

        Args:
            name: Tool name (e.g. "browser_navigate")
            args: Tool arguments dict

        Returns:
            Tool result as string, truncated to MAX_RESULT_CHARS
        """
        if self._session is None:
            raise RuntimeError("MCP session not initialized — use as async context manager")

        result = await self._session.call_tool(name, args)

        # Extract text from content blocks
        parts = []
        for item in result.content:
            if hasattr(item, "type"):
                if item.type == "text":
                    parts.append(item.text)
                elif item.type == "image":
                    # Include note about image but not the data itself
                    mime = getattr(item, "mimeType", "image/png")
                    data_len = len(getattr(item, "data", ""))
                    parts.append(f"[Image captured: {mime}, {data_len} chars base64]")
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))

        text = "\n".join(parts)

        # Truncate to prevent context bloat in tool result messages
        if len(text) > MAX_RESULT_CHARS:
            omitted = len(text) - MAX_RESULT_CHARS
            text = text[:MAX_RESULT_CHARS] + f"\n[...{omitted} chars omitted to limit context]"

        return text

    async def call_tool_with_images(self, name: str, args: dict) -> list[dict]:
        """Call an MCP tool and return Bedrock-formatted content blocks.

        Unlike call_tool(), this preserves image data for tools like
        browser_take_screenshot that return actual images.

        Args:
            name: Tool name
            args: Tool arguments dict

        Returns:
            List of Bedrock content blocks (text and/or image blocks)
        """
        if self._session is None:
            raise RuntimeError("MCP session not initialized")

        result = await self._session.call_tool(name, args)

        bedrock_blocks: list[dict] = []
        for item in result.content:
            if hasattr(item, "type"):
                if item.type == "text":
                    text = item.text
                    if len(text) > MAX_RESULT_CHARS:
                        omitted = len(text) - MAX_RESULT_CHARS
                        text = text[:MAX_RESULT_CHARS] + f"\n[...{omitted} chars omitted]"
                    bedrock_blocks.append({"text": text})
                elif item.type == "image":
                    try:
                        image_bytes = base64.b64decode(item.data)
                        mime = getattr(item, "mimeType", "image/png")
                        fmt = "png"
                        if "jpeg" in mime or "jpg" in mime:
                            fmt = "jpeg"
                        elif "webp" in mime:
                            fmt = "webp"
                        bedrock_blocks.append(
                            {
                                "image": {
                                    "format": fmt,
                                    "source": {"bytes": image_bytes},
                                }
                            }
                        )
                    except Exception as e:
                        bedrock_blocks.append({"text": f"[Image decode error: {e}]"})
                else:
                    bedrock_blocks.append({"text": str(item)})
            else:
                bedrock_blocks.append({"text": str(item)})

        return bedrock_blocks if bedrock_blocks else [{"text": "Tool returned no content"}]
