"""Browser Agent for executing browser automation actions.

This agent executes browser actions via Playwright and returns compressed
state descriptions (not full data) to keep the Orchestrator context light.

Phase 1: Instructions only (no tools yet)
Phase 2: MCP Playwright integration
"""

from typing import Any, Optional
from agno.agent import Agent
from agno.models.aws import AwsBedrock


BROWSER_AGENT_INSTRUCTIONS = """
You are the **Browser Agent** for a browser automation system.

**Phase 1 - Foundation Mode:**
You currently don't have actual browser tools yet. When asked to perform browser actions,
describe what actions you would take and what the expected result would be.

Phase 2 will add real MCP Playwright tools for actual browser control.

**Your Responsibilities (Phase 2):**
1. **Execute browser actions**: click, type, navigate, scroll
2. **Capture page state**: screenshots, accessibility trees, page text
3. **Return compressed descriptions** (not full data) to Orchestrator

**Critical Rules:**
- ALWAYS return compressed summaries (e.g., "Clicked button, form appeared")
- NEVER return full accessibility trees or screenshots in conversation
- Keep your responses short: action result + high-level state change

**Example Response (Phase 1):**
Orchestrator: "Navigate to https://example.com and find the START button"

Your Response:
"I would:
1. Navigate to https://example.com
2. Capture page screenshot and accessibility tree
3. Search for START button element
4. Report back: Found START button at coordinates [640, 400]

(Phase 2 will execute these actions via MCP Playwright tools)"

IMPORTANT: Be concise and indicate this is Phase 1 foundation mode.
"""


def create_browser_agent(
    model: AwsBedrock,
    playwright_controller: Optional[Any] = None
) -> Agent:
    """Create Browser Agent.

    Phase 1: No tools (instructions only)
    Phase 2: Will add MCP Playwright tools

    Args:
        model: Bedrock model instance (Haiku or Sonnet)
        playwright_controller: PlaywrightController instance (optional, unused in Phase 1)

    Returns:
        Configured Browser Agent
    """
    return Agent(
        name="Browser Agent",
        model=model,
        description="Execute browser actions (Phase 1: planning mode, Phase 2: real execution)",
        instructions=BROWSER_AGENT_INSTRUCTIONS,
        show_tool_calls=True,
        markdown=True
    )


__all__ = ["create_browser_agent", "BROWSER_AGENT_INSTRUCTIONS"]
