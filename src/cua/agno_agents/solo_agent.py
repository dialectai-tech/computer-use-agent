"""Single-agent browser automation - efficient replacement for multi-agent team.

Replaces the 4-agent Team (Orchestrator + Browser + Memory + Analysis) with
a single Agent that has direct access to Playwright MCP and Python progress
tracking tools. Reduces API calls from ~395 to ~30 for the same task.

Key improvements:
- No delegation overhead (was 7 API calls per browser action, now 1)
- No context copying between agents
- Direct tool access with no wrapper layers
- Built-in progress tracking
- Video recording via Playwright MCP --save-video flag
"""

from pathlib import Path
from typing import Optional

from agno.agent import Agent
from agno.tools import Toolkit
from agno.tools.mcp import MCPTools

from cua.agno_config.bedrock_mcp_model import BedrockMCPModel


SOLO_AGENT_INSTRUCTIONS = """You are an expert browser automation agent. Complete browser tasks efficiently.

## TOOLS
You have direct Playwright browser tools:

Navigation & Page:
- browser_navigate(url): Navigate to URL
- browser_navigate_back(): Go back in history
- browser_wait_for(text, time): Wait for text to appear or N seconds to pass
- browser_snapshot(): Get page accessibility tree — PREFERRED for decision-making
- browser_take_screenshot(): Take screenshot — observation only, NOT for actions

Interaction:
- browser_click(element, ref): Click an element (use ref from snapshot)
- browser_type(ref, text): Type into a field (use ref from snapshot)
- browser_fill_form(fields): Fill multiple fields at once — efficient!
- browser_select_option(ref, values): Select dropdown option
- browser_press_key(key): Press a keyboard key (e.g. "Enter", "Tab", "Escape")
- browser_mouse_wheel(deltaX, deltaY): Scroll the page (positive deltaY = scroll down)
- browser_handle_dialog(accept, promptText): Accept or dismiss dialogs/alerts

Advanced:
- browser_evaluate(function): Execute JavaScript — for complex interactions
- browser_hover(ref): Hover over element
- browser_drag(startRef, endRef): Drag and drop

Verification:
- browser_verify_text_visible(text): Verify text is on page
- browser_verify_element_visible(ref): Verify element exists

Progress tracking (Python tools, no browser needed):
- store_fact(key, value): Store a code, URL, or important value for later
- mark_complete(step): Record that a step is done
- get_facts(): Retrieve all stored facts
- get_progress(): Review completed steps

## CRITICAL RULES
1. ALWAYS use browser_snapshot() to understand page structure — it includes element refs (e.g. ref="e123")
2. Use element refs from snapshots for clicking/typing — they are more reliable than selectors
3. browser_take_screenshot() is for observation only — you CANNOT act based on it
4. After clicking/typing, proceed with the next action IMMEDIATELY if you know what to do
5. Only re-snapshot when you need to find new element refs
6. Use browser_fill_form() to fill multiple fields at once — more efficient than filling one by one

## EXECUTION PATTERN
1. browser_navigate(url) to go to the page
2. browser_snapshot() to see page structure and get element refs
3. Execute actions using refs from the snapshot (click, type, fill_form, etc.)
4. Only re-snapshot when page changes and you need new refs
5. store_fact() for any codes, tokens, or important values discovered
6. mark_complete() when a significant milestone is reached

## HANDLING COMMON SCENARIOS
- **Popups/dialogs/overlays**: Close them first using browser_handle_dialog() or click the X/close button
- **Codes revealed by clicking**: Click the reveal button → store_fact() → then enter the code
- **Multi-step forms**: Fill all visible fields, then submit
- **Element not found**: Scroll down with browser_mouse_wheel(0, 500), then re-snapshot
- **Click not working**: Try browser_evaluate() with document.querySelector(...).click()
- **Page not loaded**: browser_wait_for(time=3) then try again
- **Confused about progress**: Use get_progress() + get_facts() then re-snapshot

## PROGRESS TRACKING
- State your current step: "Step N: [what I am doing]"
- After finding important info: "Found [VALUE] — storing with store_fact()"
- After milestone: "✓ Completed: [what was done]"
- NEVER repeat a completed step — check get_progress() if uncertain
- If stuck (same action attempted 3 times), try completely different approach

## COMPLETION
When the task is fully done, output exactly:
TASK COMPLETE: [brief description of what was accomplished]

IMPORTANT: Do not give up early. Try alternative approaches if direct ones fail.
"""


class BrowserStateTracker(Toolkit):
    """Python toolkit for tracking browser automation progress.

    Provides in-process state management with no external dependencies.
    Replaces the separate Memory Agent with much lower overhead.
    """

    def __init__(self) -> None:
        super().__init__(name="browser_state")
        self.completed_steps: list[str] = []
        self.facts: dict[str, str] = {}
        self.register(self.mark_complete)
        self.register(self.store_fact)
        self.register(self.get_facts)
        self.register(self.get_progress)

    def mark_complete(self, step: str) -> str:
        """Mark a task step as completed.

        Args:
            step: Description of the completed step (e.g. "Clicked START button")
        """
        self.completed_steps.append(step)
        return f"Step completed: {step} (total completed: {len(self.completed_steps)})"

    def store_fact(self, key: str, value: str) -> str:
        """Store an important fact for later use.

        Args:
            key: Name for this fact (e.g. "challenge_code", "submit_selector")
            value: The value to store (e.g. "ABC123", "button#submit")
        """
        self.facts[key] = value
        return f"Stored: {key} = {value}"

    def get_facts(self) -> str:
        """Retrieve all stored facts.

        Returns:
            All stored key-value pairs, or a message if nothing stored
        """
        if not self.facts:
            return "No facts stored yet."
        lines = ["Stored facts:"]
        lines.extend(f"  {k}: {v}" for k, v in self.facts.items())
        return "\n".join(lines)

    def get_progress(self) -> str:
        """Get current task progress summary.

        Returns:
            List of completed steps, or message if nothing done
        """
        if not self.completed_steps:
            return "No steps completed yet."
        lines = ["Completed steps:"]
        lines.extend(f"  {i + 1}. {s}" for i, s in enumerate(self.completed_steps))
        return "\n".join(lines)


def build_playwright_command(
    recordings_dir: Optional[Path] = None,
    record_video: bool = False,
    viewport_size: str = "1280x720",
    headless: bool = True,
) -> str:
    """Build Playwright MCP command with options.

    Args:
        recordings_dir: Directory for saving video recordings
        record_video: Whether to record browser video
        viewport_size: Browser viewport (e.g. "1280x720")
        headless: Whether to run headless

    Returns:
        Full command string for MCPTools

    Note:
        Do NOT use --output-mode=file — it redirects snapshot responses
        to disk, breaking the agent's ability to see page content.
        --output-dir is only used for --save-video output.
    """
    parts = ["npx @playwright/mcp"]
    parts.append(f"--viewport-size={viewport_size}")
    parts.append("--no-sandbox")  # Required in many Linux/Docker environments

    if headless:
        parts.append("--headless")

    if record_video and recordings_dir:
        # Ensure directory exists before telling MCP to write there
        recordings_dir.mkdir(parents=True, exist_ok=True)
        parts.append(f"--output-dir={recordings_dir}")
        parts.append(f"--save-video={viewport_size}")

    return " ".join(parts)


def create_solo_agent(
    model: BedrockMCPModel,
    session_dir: Optional[Path] = None,
    record_video: bool = False,
    viewport_size: str = "1280x720",
    headless: bool = True,
    max_tool_calls: int = 150,
) -> tuple[Agent, BrowserStateTracker]:
    """Create a single-agent browser automation agent.

    Replaces the 4-agent Agno Team with one agent that has all tools
    directly attached. Eliminates delegation overhead.

    Args:
        model: Bedrock model instance (Haiku or Sonnet)
        session_dir: Session root directory (test_artifacts/{session_id}/)
        record_video: Whether to record browser session video
        viewport_size: Browser viewport size (e.g. "1280x720")
        headless: Whether to run headless
        max_tool_calls: Maximum tool calls per run (safety limit)

    Returns:
        Tuple of (configured Agent, BrowserStateTracker for post-run inspection)
    """
    # Determine recordings dir if video is requested
    recordings_dir = None
    if record_video and session_dir is not None:
        recordings_dir = session_dir / "recordings"

    # Screenshots dir hint for agent instructions
    screenshots_dir = None
    if session_dir is not None:
        screenshots_dir = session_dir / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

    # Build playwright command with options
    playwright_cmd = build_playwright_command(
        recordings_dir=recordings_dir,
        record_video=record_video,
        viewport_size=viewport_size,
        headless=headless,
    )

    # Direct Playwright MCP - no wrappers, no delegation
    playwright_mcp = MCPTools(
        command=playwright_cmd,
        refresh_connection=False,  # Keep same browser session throughout task
        timeout_seconds=30,  # Reasonable timeout for page loads
    )

    # Python-based state tracker (no MCP overhead for memory)
    state_tracker = BrowserStateTracker()

    # Build instructions, optionally including screenshot path hint
    instructions = SOLO_AGENT_INSTRUCTIONS
    if screenshots_dir:
        instructions += (
            f"\n\n## SCREENSHOT PATHS\n"
            f"When saving screenshots, use this absolute path prefix: {screenshots_dir}/\n"
            f"Example: browser_take_screenshot(filename=\"{screenshots_dir}/step-01.png\")\n"
        )

    agent = Agent(
        name="Browser Automation Agent",
        model=model,
        description="Autonomous browser automation agent with direct tool access",
        instructions=instructions,
        tools=[playwright_mcp, state_tracker],
        tool_call_limit=max_tool_calls,
        markdown=False,
        add_datetime_to_context=False,  # Don't add noise to context
        show_tool_calls=False,  # Handled by our logger
    )

    return agent, state_tracker


__all__ = ["create_solo_agent", "BrowserStateTracker", "SOLO_AGENT_INSTRUCTIONS"]
