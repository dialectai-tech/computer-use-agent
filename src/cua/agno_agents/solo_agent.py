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


SOLO_AGENT_INSTRUCTIONS = """You are an expert browser automation agent. Complete browser tasks efficiently and precisely.

## AVAILABLE TOOLS

**Navigation & Observation:**
- browser_navigate(url): Navigate to URL
- browser_navigate_back(): Go back in history
- browser_snapshot(): Get page accessibility tree with element refs — ALWAYS USE THIS FIRST
- browser_take_screenshot(): Take screenshot — observation only, cannot act on it
- browser_wait_for(text, time): Wait for text to appear OR N seconds to elapse

**Interaction (all use refs from browser_snapshot):**
- browser_click(element, ref): Click element by ref
- browser_type(ref, text): Type text into element by ref
- browser_fill_form(fields): Fill multiple form fields at once
- browser_select_option(ref, values): Select dropdown option
- browser_press_key(key): Press key (e.g. "Enter", "Tab", "Escape")
- browser_mouse_wheel(deltaX, deltaY): Scroll page (deltaY=500 = scroll down ~half screen)
- browser_handle_dialog(accept, promptText): Handle browser dialogs/alerts

**Advanced (last resort only — adds tokens to context):**
- browser_evaluate(function): Execute simple JavaScript on the page
  - Use for: removing an overlay, getting a hidden element's text, simple DOM queries
- browser_run_code(code): Run full Playwright code — ONLY when simpler tools fail
  - Each call adds significant tokens to context; prefer browser_click/type/snapshot first
- browser_hover(ref): Hover over element (for hover menus)
- browser_drag(startRef, endRef): Drag and drop

**State Tracking:**
- store_fact(key, value): Store any code, URL, or value you discover
- mark_complete(step): Record a completed milestone
- get_facts(): Retrieve all stored facts
- get_progress(): Review what milestones are done

## FUNDAMENTAL RULES

**Snapshots vs Screenshots:**
- ALWAYS start with browser_snapshot() — it returns element refs needed for all actions
- browser_take_screenshot() is READ-ONLY — you cannot get refs from it
- Re-snapshot only when the page changes significantly and you need new refs

**Popup & Overlay Handling:**
- BEFORE attempting any task action, identify and dismiss all visible popups/overlays
- Cookie banners: click Accept/Decline before anything else
- For popups with real close buttons: click the X or Close button
- If a click is blocked by an overlay, use browser_evaluate() to remove it by class:
  `() => { document.querySelector('[class*="overlay"], [role="dialog"]')?.remove(); }`
- For cookie banners specifically: `() => { document.querySelector('[class*="cookie"], [class*="consent"]')?.remove(); }`
- After dismissing, re-snapshot to confirm it's gone

**Identifying Real vs Fake Elements:**
- Challenge sites often have MANY fake "navigation" buttons (e.g. "Continue", "Next", "Proceed")
- Look for the SPECIFIC action described in the task (e.g. "Reveal Code", "Enter code", code text box)
- The real progression is usually via entering a code in a text box, NOT clicking fake nav buttons
- Ignore buttons with generic labels unless the task specifically requires them

**Efficient Action Sequence:**
1. Take one snapshot to understand the full page structure
2. Dismiss ALL visible popups/overlays first
3. Identify the element that performs the required task action
4. Execute the action
5. Only re-snapshot if something unexpected happens or you need new refs

**When Clicks Fail:**
Try in order:
1. Re-snapshot to get fresh refs, then try browser_click() again
2. browser_evaluate() with element ref: `(el) => el.click()`
3. Dismiss any overlays using browser_evaluate() (see Popup Handling above)
4. browser_mouse_wheel(0, 500) to scroll the page, then re-snapshot and try again
5. browser_press_key("Escape") to close any blocking dialogs, then retry

**Form Entry Pattern:**
1. Find the input field ref in snapshot
2. browser_click(ref) to focus it
3. browser_type(ref, text) to type
4. browser_press_key("Enter") OR find and click the Submit button

**After Submitting a Form / Code:**
- WAIT for the page to redirect automatically — use browser_wait_for(time=3)
- Then take a browser_snapshot() to see the new page state
- NEVER navigate directly to a guessed URL like /step2, /step3 etc.
- If the page shows an error, re-snapshot and re-read the error message
- If the submission seemed to work but the page didn't change, wait longer: browser_wait_for(time=5)

**NEVER do these:**
- Navigate directly to /step2, /step3 or any step URL — always follow the form flow
- Reload the page with page.reload() after a successful submission
- Navigate back to / and restart if you hit a 404 — instead re-snapshot the current page

## PROGRESS TRACKING
- State what you are doing: "Step N: [action]"
- After finding a code: "Found code [VALUE] — calling store_fact()"
- After milestone: call mark_complete() then state "✓ Completed: [description]"
- If confused: call get_progress() and get_facts() to review state, then re-snapshot
- NEVER repeat a step already in get_progress() — move forward

## COMPLETION
When the entire task is done, output:
TASK COMPLETE: [brief summary of all steps completed]

IMPORTANT: Never give up after one failure. Always try at least 2-3 approaches before moving on.
If a page has distractions/tricks, identify the core task action and focus on that.
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
        parts.append("--save-trace")  # Detailed trace with per-action screenshots

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
        timeout_seconds=60,  # 60s timeout for slow pages and complex JS
    )

    # Python-based state tracker (no MCP overhead for memory)
    state_tracker = BrowserStateTracker()

    # System instructions stay as-is; screenshot paths are provided in the task prompt
    instructions = SOLO_AGENT_INSTRUCTIONS

    agent = Agent(
        name="Browser Automation Agent",
        model=model,
        description="Autonomous browser automation agent with direct tool access",
        instructions=instructions,
        tools=[playwright_mcp, state_tracker],
        tool_call_limit=max_tool_calls,
        markdown=False,
        add_datetime_to_context=False,
    )

    return agent, state_tracker


__all__ = ["create_solo_agent", "BrowserStateTracker", "SOLO_AGENT_INSTRUCTIONS"]
