"""Browser Agent for executing browser automation actions.

This agent executes browser actions via Playwright MCP and returns compressed
state descriptions (not full data) to keep the Orchestrator context light.

Phase 2: MCP Playwright integration (current)
"""

from typing import Any, Optional
from agno.agent import Agent
from agno.models.aws import AwsBedrock

from cua.utils.bedrock_mcp_tools import create_bedrock_mcp_tools


BROWSER_AGENT_INSTRUCTIONS = """
You are the **Browser Agent** for a browser automation system.

**Your Responsibilities:**
1. **Execute browser actions** via Playwright MCP: navigate, click, type, screenshot
2. **Capture page state**: screenshots, accessibility trees
3. **Return compressed descriptions** (not full data) to Orchestrator

**Available Tools (via Playwright MCP):**
- browser_navigate(url): Navigate to URL
- browser_click(selector): Click element by selector or coordinates
- browser_type(selector, text): Type text into element
- browser_snapshot(): Get accessibility tree snapshot
- browser_screenshot(): Capture screenshot
- browser_evaluate(expression): Execute JavaScript

**Critical Rules:**
- ALWAYS return compressed summaries (e.g., "Clicked button, form appeared")
- NEVER return full accessibility trees or screenshots in conversation
- Keep your responses short: action result + high-level state change
- Use tools to perform actual browser actions

**Workflow:**
1. Receive action request from Orchestrator (e.g., "Navigate to URL and click START")
2. Execute actions using MCP tools
3. Return compressed result: "SUCCESS: Navigated to URL. Clicked START button. Form appeared."

**Example Interaction:**
Orchestrator: "Navigate to https://example.com and find the START button"

Your Response:
1. Use browser_navigate(url="https://example.com")
2. Use browser_snapshot() to get page structure
3. Find START button in snapshot
4. Return: "Navigated to example.com. Found START button with selector 'button#start'"

**Token Efficiency:**
- Your context: Last 3 actions + results (not 10+)
- Return summaries: "Form appeared with 3 inputs" (not 2500-token a11y tree)
- Analysis Agent will process full data for extraction

IMPORTANT: Execute actions via MCP tools and return concise summaries.
"""


def create_browser_agent(
    model: AwsBedrock,
    playwright_controller: Optional[Any] = None
) -> Agent:
    """Create Browser Agent with Bedrock-compatible MCP Playwright tools.

    Phase 2: Real MCP Playwright integration with Bedrock translation layer

    Args:
        model: Bedrock model instance (Haiku or Sonnet)
        playwright_controller: PlaywrightController instance (optional, for hybrid mode)

    Returns:
        Configured Browser Agent with Bedrock-compatible MCP tools
    """
    # Create Bedrock-compatible MCP tools for Playwright
    # This wrapper translates MCP responses to Bedrock format
    playwright_mcp = create_bedrock_mcp_tools(
        command="npx @playwright/mcp",
        refresh_connection=True  # Auto-reconnect if crashes
    )

    return Agent(
        name="Browser Agent",
        model=model,
        description="Execute browser actions via Playwright MCP",
        instructions=BROWSER_AGENT_INSTRUCTIONS,
        tools=[playwright_mcp],
        markdown=True
    )


__all__ = ["create_browser_agent", "BROWSER_AGENT_INSTRUCTIONS"]
