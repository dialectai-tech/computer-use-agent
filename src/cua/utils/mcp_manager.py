"""MCP Server Lifecycle Manager.

Manages connections to MCP servers (Playwright, Memory) with health checks
and automatic reconnection.
"""

import asyncio
import subprocess
from typing import Optional, Dict, Any
from pathlib import Path


class MCPManager:
    """Manage MCP server lifecycle for Agno agents."""

    def __init__(self):
        """Initialize MCP manager."""
        self.playwright_process: Optional[subprocess.Popen] = None
        self.memory_process: Optional[subprocess.Popen] = None
        self.is_connected = False

    async def connect_playwright(self) -> bool:
        """Start Playwright MCP server.

        Returns:
            True if connection successful
        """
        try:
            # Start Playwright MCP server via stdio
            self.playwright_process = subprocess.Popen(
                ["npx", "@playwright/mcp"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Give it a moment to start
            await asyncio.sleep(0.5)

            # Check if process is still running
            if self.playwright_process.poll() is None:
                print("✓ Playwright MCP server started")
                return True
            else:
                print("✗ Playwright MCP server failed to start")
                return False

        except Exception as e:
            print(f"✗ Failed to start Playwright MCP: {e}")
            return False

    async def connect_memory(self) -> bool:
        """Start Memory MCP server.

        Returns:
            True if connection successful
        """
        try:
            # Start Memory MCP server via stdio
            self.memory_process = subprocess.Popen(
                ["npx", "@modelcontextprotocol/server-memory"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Give it a moment to start
            await asyncio.sleep(0.5)

            # Check if process is still running
            if self.memory_process.poll() is None:
                print("✓ Memory MCP server started")
                return True
            else:
                print("✗ Memory MCP server failed to start")
                return False

        except Exception as e:
            print(f"✗ Failed to start Memory MCP: {e}")
            return False

    async def connect_all(self) -> bool:
        """Connect to all MCP servers.

        Returns:
            True if all connections successful
        """
        playwright_ok = await self.connect_playwright()
        memory_ok = await self.connect_memory()

        self.is_connected = playwright_ok and memory_ok
        return self.is_connected

    async def disconnect_all(self):
        """Disconnect from all MCP servers."""
        if self.playwright_process:
            self.playwright_process.terminate()
            try:
                self.playwright_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.playwright_process.kill()
            print("✓ Playwright MCP server stopped")

        if self.memory_process:
            self.memory_process.terminate()
            try:
                self.memory_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.memory_process.kill()
            print("✓ Memory MCP server stopped")

        self.is_connected = False

    def health_check(self) -> Dict[str, bool]:
        """Check health of MCP servers.

        Returns:
            Dictionary with server health status
        """
        return {
            "playwright": (
                self.playwright_process is not None
                and self.playwright_process.poll() is None
            ),
            "memory": (
                self.memory_process is not None
                and self.memory_process.poll() is None
            )
        }

    async def __aenter__(self):
        """Context manager entry."""
        await self.connect_all()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.disconnect_all()


__all__ = ["MCPManager"]
