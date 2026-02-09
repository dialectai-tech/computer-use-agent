"""Main agent loop for computer use automation."""

import time
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from cua.providers.base import (
    ComputerUseProvider,
    ActionType,
    ActionEvidence,
    AccessibilityTreeDiff,
    requires_screenshot,
    requires_page_text_capture,
    compute_page_text_diff,
    compute_a11y_tree_diff
)
from cua.browser.playwright_controller import PlaywrightController
from cua.tools.search_tool import SearchTool
from cua.utils.logger import AgentLogger
from cua.utils.token_stats import (
    TokenBreakdown,
    CumulativeTokenStats,
    print_token_stats,
    estimate_tokens,
    estimate_image_tokens
)


@dataclass
class TaskResult:
    """Result from running a task."""
    success: bool
    iterations: int
    total_time: float
    error: Optional[str] = None
    final_url: Optional[str] = None
    stats: Optional[dict] = None
    video_path: Optional[str] = None


class ComputerUseAgent:
    """Main agent for computer use automation."""

    def __init__(
        self,
        provider: ComputerUseProvider,
        display_width: int = 1024,
        display_height: int = 768,
        zoom: int = 85,
        headless: bool = True,
        record_video: bool = False,
        video_dir: Optional[str] = None,
        enable_caching: bool = True,
        context_window_size: int = 10,
        extended_thinking: bool = False,
        thinking_budget: int = 10000,
        use_accessibility_tree: bool = True,
        use_page_text: bool = True,
        use_dom_manipulation: bool = True,
        use_search_tool: bool = True,
        use_find_tool: bool = True,
        two_phase_workflow: bool = False,
        max_message_turns: int = 10,
        auto_context_reset: bool = True,
        auto_reset_token_threshold: int = 30000,
        multi_action_evidence: bool = True,
        max_actions_per_response: int = 10,
        use_semantic_diff: bool = True
    ):
        """Initialize agent.

        Args:
            provider: AI provider to use
            display_width: Browser viewport width
            display_height: Browser viewport height
            zoom: Browser zoom level as percentage
            headless: Whether to run browser in headless mode
            record_video: Whether to record video of the session
            video_dir: Directory to save videos
            enable_caching: Enable prompt caching for cost savings
            context_window_size: Number of recent screenshots to keep
            extended_thinking: Enable extended thinking for complex reasoning
            thinking_budget: Token budget for extended thinking
            use_accessibility_tree: Use accessibility tree alongside screenshots
            use_page_text: Include extracted page text alongside screenshots
            use_dom_manipulation: Enable DOM manipulation tool for CSS selector-based actions
            two_phase_workflow: Enable two-phase workflow (search first, then screenshot)
            max_message_turns: Maximum number of message turns to keep in history
            auto_context_reset: Enable automatic context reset at milestones
            auto_reset_token_threshold: Input token threshold for automatic reset
            multi_action_evidence: Capture per-action evidence (screenshots, page text) for multi-action responses
            max_actions_per_response: Maximum number of actions to execute in a single response (0 = unlimited)
            use_semantic_diff: Use semantic diff for a11y tree instead of full tree after baseline (default: True)
        """
        self.provider = provider
        self.max_message_turns = max_message_turns
        self.auto_context_reset = auto_context_reset
        self.auto_reset_token_threshold = auto_reset_token_threshold
        self.multi_action_evidence = multi_action_evidence
        self.max_actions_per_response = max_actions_per_response
        self.use_semantic_diff = use_semantic_diff

        # Pass max_message_turns to provider if it supports it
        if hasattr(self.provider, 'max_message_turns'):
            self.provider.max_message_turns = max_message_turns
        self.display_width = display_width
        self.display_height = display_height
        self.zoom = zoom
        self.headless = headless
        self.record_video = record_video
        self.video_dir = video_dir
        self.enable_caching = enable_caching
        self.context_window_size = context_window_size
        self.extended_thinking = extended_thinking
        self.thinking_budget = thinking_budget
        self.use_accessibility_tree = use_accessibility_tree
        self.use_page_text = use_page_text
        self.use_dom_manipulation = use_dom_manipulation
        self.use_search_tool = use_search_tool
        self.use_find_tool = use_find_tool
        self.two_phase_workflow = two_phase_workflow
        self.console = Console()
        self.browser: Optional[PlaywrightController] = None
        self.logger: Optional[AgentLogger] = None  # Will be initialized when task starts
        self.last_page_url: Optional[str] = None  # Track URL to detect page navigation

        # Token statistics tracking
        self.cumulative_token_stats = CumulativeTokenStats()
        self.conversation_dump_dir: Optional[Path] = None  # Will be set when task starts

        # Context management: track screenshots and actions for hybrid approach
        self.screenshot_history = []  # List of (screenshot, action_type, important_info)
        self.important_context = []  # List of important information to remember

        # Two-phase workflow state
        self.current_phase = 1 if two_phase_workflow else 0  # 0=normal, 1=search, 2=action
        self.phase_search_results = None  # Store search results from phase 1

        # Automatic context reset tracking
        self.last_reset_iteration = 0  # Track when we last reset context
        self.last_milestone_step = 0  # Track last completed step number
        self.current_page_section = None  # Track current page section for navigation detection
        self.just_reset = False  # Flag to indicate reset just happened, skip continuation

        # Pass configuration to provider
        self.provider.enable_caching = enable_caching
        self.provider.extended_thinking = extended_thinking
        self.provider.thinking_budget = thinking_budget

    def _calculate_token_breakdown(
        self,
        response,
        screenshot: Optional[str],
        accessibility_tree: Optional[dict],
        page_text: Optional[str],
        context_size: int,
        iteration: int = 1
    ) -> TokenBreakdown:
        """Calculate detailed token breakdown for an API call.

        Args:
            response: Provider response object with usage stats
            screenshot: Base64 screenshot (if sent)
            accessibility_tree: Accessibility tree (if sent)
            page_text: Page text (if sent)
            context_size: Number of previous responses in context
            iteration: Current iteration number (for system prompt counting)

        Returns:
            TokenBreakdown with estimated breakdown
        """
        breakdown = TokenBreakdown()

        # Get total tokens from response
        if hasattr(response, 'input_tokens'):
            # Response object with attributes
            breakdown.total_input_tokens = response.input_tokens
            breakdown.total_output_tokens = response.output_tokens
        elif isinstance(response, dict) and 'usage' in response:
            # Bedrock Converse API response dict format
            breakdown.total_input_tokens = response['usage'].get('inputTokens', 0)
            breakdown.total_output_tokens = response['usage'].get('outputTokens', 0)
        elif hasattr(self.provider, 'stats') and self.provider.stats:
            # Fallback: get from provider stats (LAST RESORT - this is cumulative!)
            # This should rarely be reached now that we check dict responses
            breakdown.total_input_tokens = self.provider.stats.input_tokens
            breakdown.total_output_tokens = self.provider.stats.output_tokens
        else:
            # Last resort: estimate based on content
            breakdown.total_input_tokens = 0
            breakdown.total_output_tokens = 0

        # Estimate breakdown (rough approximations)
        # System prompt is sent via 'system' parameter and cached by Bedrock
        # Only count it on the first iteration
        if iteration == 1:
            breakdown.system_prompt_tokens = 500  # Actual optimized prompt is ~500 tokens (was 5000)
        else:
            breakdown.system_prompt_tokens = 0  # Cached by API, not re-sent

        # Screenshot tokens
        # NOTE: With screenshot stripping optimization, only the most recent screenshot
        # is sent to the API (old screenshots are stripped during message pruning).
        # So we only count 1 screenshot, not (context_size + 1).
        if screenshot:
            breakdown.screenshots_tokens = estimate_image_tokens(
                self.display_width,
                self.display_height
            )  # Only current screenshot (old ones stripped)

        # Page text tokens
        if page_text:
            breakdown.page_text_tokens = estimate_tokens(page_text) * (context_size + 1)

        # Accessibility tree tokens
        if accessibility_tree:
            import json
            tree_str = json.dumps(accessibility_tree)
            breakdown.accessibility_tree_tokens = estimate_tokens(tree_str) * (context_size + 1)

        # AI responses (remaining tokens)
        estimated_content = (
            breakdown.system_prompt_tokens +
            breakdown.screenshots_tokens +
            breakdown.page_text_tokens +
            breakdown.accessibility_tree_tokens
        )
        breakdown.ai_responses_tokens = max(0, breakdown.total_input_tokens - estimated_content)

        return breakdown

    def _dump_conversation(self, iteration: int):
        """Dump current conversation state to JSON file.

        Args:
            iteration: Current iteration number
        """
        if not self.conversation_dump_dir:
            return

        # Extract session_id from directory name
        session_id = self.conversation_dump_dir.name.replace("conversations_", "")

        # Get messages from provider
        messages = []
        if hasattr(self.provider, 'messages'):
            messages = self.provider.messages

        # Create dump data
        dump_data = {
            "session_id": session_id,
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "message_count": len(messages),
            "messages": messages,
            "token_stats": self.cumulative_token_stats.to_dict(),
            "configuration": {
                "display_width": self.display_width,
                "display_height": self.display_height,
                "zoom": self.zoom,
                "use_accessibility_tree": self.use_accessibility_tree,
                "use_page_text": self.use_page_text,
                "use_dom_manipulation": self.use_dom_manipulation,
                "use_search_tool": self.use_search_tool,
                "use_find_tool": self.use_find_tool,
                "context_window_size": self.context_window_size,
                "two_phase_workflow": self.two_phase_workflow,
                "max_message_turns": self.max_message_turns,
            }
        }

        # Save to file
        filename = f"conversation_{session_id}_iter{iteration:03d}.json"
        filepath = self.conversation_dump_dir / filename

        try:
            with open(filepath, 'w') as f:
                json.dump(dump_data, f, indent=2, default=str)
        except Exception as e:
            self.console.print(f"[yellow]Warning: Failed to dump conversation: {e}[/yellow]")

    def run_task(
        self,
        url: str,
        prompt: str,
        max_iterations: int = 30
    ) -> TaskResult:
        """Run a computer use automation task.

        Args:
            url: URL to navigate to
            prompt: Task description
            max_iterations: Maximum number of iterations

        Returns:
            TaskResult with execution details
        """
        start_time = time.time()
        iteration = 0

        self.console.print(f"\n[bold cyan]🤖 Computer Use Agent[/bold cyan]")
        self.console.print(f"[dim]Provider: {self.provider.__class__.__name__}[/dim]")
        self.console.print(f"[dim]Model: {self.provider.model}[/dim]")
        self.console.print(f"[dim]URL: {url}[/dim]\n")

        try:
            # Initialize browser
            self.console.print("[yellow]Starting browser...[/yellow]")
            if self.record_video:
                self.console.print("[yellow]Video recording enabled[/yellow]")
            if self.zoom != 100:
                self.console.print(f"[yellow]Zoom level: {self.zoom}%[/yellow]")
            if self.enable_caching:
                self.console.print("[yellow]Prompt caching: enabled[/yellow]")
            if self.use_accessibility_tree:
                self.console.print("[yellow]Accessibility tree: enabled (hybrid mode)[/yellow]")
            if self.two_phase_workflow:
                self.console.print("[yellow]Two-phase workflow: enabled (search first, then screenshot)[/yellow]")
            if self.extended_thinking:
                self.console.print(f"[yellow]Extended thinking: enabled (budget: {self.thinking_budget})[/yellow]")

            self.browser = PlaywrightController(
                display_width=self.display_width,
                display_height=self.display_height,
                zoom=self.zoom,
                headless=self.headless,
                record_video=self.record_video,
                video_dir=self.video_dir
            )
            self.browser.start()

            # Initialize logger
            from datetime import datetime
            session_name = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.logger = AgentLogger(session_name=session_name)
            self.console.print(f"[dim]Logging to: {self.logger.get_log_path()}[/dim]")

            # Initialize conversation dump directory
            session_id = session_name
            self.conversation_dump_dir = Path("logs") / f"conversations_{session_id}"
            self.conversation_dump_dir.mkdir(parents=True, exist_ok=True)
            self.console.print(f"[dim]Conversation dumps: {self.conversation_dump_dir}[/dim]")

            # Navigate to URL
            self.console.print(f"[yellow]Navigating to {url}...[/yellow]")
            self.browser.navigate(url)

            # Take initial screenshot and accessibility tree
            screenshot = self.browser.take_screenshot()
            self.provider.stats.add_screenshot()

            # Get accessibility tree if enabled
            accessibility_tree = None
            if self.use_accessibility_tree:
                accessibility_tree = self.browser.get_accessibility_tree()

            # Get page text for initial page load
            page_text = self.browser.get_page_text() if self.use_page_text else None
            # Initialize last_page_url tracker
            if self.use_page_text:
                self.last_page_url = self.browser.get_page_info().get('url', '')

            # Track initial screenshot
            self.screenshot_history.append({
                "screenshot": screenshot,
                "accessibility_tree": accessibility_tree,
                "page_text": page_text,
                "action_type": "initial",
                "transient": False,
                "important_info": None
            })

            # Create initial request
            self.console.print(f"[yellow]Sending task to AI...[/yellow]")
            if self.two_phase_workflow:
                self.console.print(f"[cyan]Two-phase workflow: Phase 1 (Search Only)[/cyan]")
            self.console.print(f"[dim]Task: {prompt}[/dim]\n")

            # Two-phase workflow: Phase 1 sends text+tree only (NO screenshot)
            if self.two_phase_workflow:
                phase1_prompt = f"""{prompt}

🔍 PHASE 1: SEARCH ONLY (No Screenshot Yet)

You are in Phase 1 of a two-phase workflow. In this phase:
- You do NOT have access to a screenshot
- You MUST use the search_page_content tool to find what you need
- Report your findings clearly

After you search and report findings, you will receive a screenshot in Phase 2.

Your task: Use search_page_content to find all relevant content needed to complete the task.
Report what you found (codes, buttons, inputs, etc.) with line numbers and locations."""

                response = self.provider.create_initial_request(
                    prompt=phase1_prompt,
                    screenshot=None,  # NO screenshot in phase 1
                    accessibility_tree=accessibility_tree if self.use_accessibility_tree else None,
                    page_text=page_text if self.use_page_text else None,
                    display_width=self.display_width,
                    display_height=self.display_height,
                    use_dom_manipulation=self.use_dom_manipulation,
                    use_search_tool=self.use_search_tool,
                    use_find_tool=self.use_find_tool
                )
            else:
                # Normal workflow: send everything including screenshot
                response = self.provider.create_initial_request(
                    prompt=prompt,
                    screenshot=screenshot,
                    accessibility_tree=accessibility_tree if self.use_accessibility_tree else None,
                    page_text=page_text if self.use_page_text else None,
                    display_width=self.display_width,
                    display_height=self.display_height,
                    use_dom_manipulation=self.use_dom_manipulation,
                    use_search_tool=self.use_search_tool,
                    use_find_tool=self.use_find_tool
                )

            # Track initial request tokens
            initial_breakdown = self._calculate_token_breakdown(
                response,
                screenshot if not self.two_phase_workflow else None,
                accessibility_tree if self.use_accessibility_tree else None,
                page_text if self.use_page_text else None,
                context_size=0,
                iteration=1  # First iteration
            )
            self.cumulative_token_stats.add_iteration(initial_breakdown)
            print_token_stats(1, initial_breakdown, self.cumulative_token_stats, self.console)
            self._dump_conversation(1)

            # Main agent loop
            while iteration < max_iterations:
                iteration += 1

                self.console.print(f"[bold]Iteration {iteration}/{max_iterations}[/bold]")

                # If we just reset context, start fresh instead of continuing from previous state
                if self.just_reset:
                    self.just_reset = False  # Clear the flag
                    self.console.print(f"[dim]Starting fresh iteration after context reset...[/dim]")

                    # Take fresh screenshot and get new response
                    screenshot = self.browser.take_screenshot()
                    self.provider.stats.add_screenshot()
                    accessibility_tree = self.browser.get_accessibility_tree() if self.use_accessibility_tree else None

                    # Get page text only if URL changed
                    page_text = None
                    if self.use_page_text:
                        current_url = self.browser.get_page_info().get('url', '')
                        page_text = self.browser.get_page_text()
                        # Track URL changes for logging
                        if current_url != self.last_page_url:
                            self.last_page_url = current_url

                    # Get fresh response (continuation will properly handle the reset state)
                    response = self.provider.create_continuation_request(
                        screenshot=screenshot,
                        accessibility_tree=accessibility_tree if self.use_accessibility_tree else None,
                        page_text=page_text if self.use_page_text else None,
                        search_results=None,
                        display_width=self.display_width,
                        display_height=self.display_height,
                        additional_instruction=None,
                        use_dom_manipulation=self.use_dom_manipulation,
                        use_search_tool=self.use_search_tool,
                        use_find_tool=self.use_find_tool
                    )
                    # Continue to next iteration to process this response normally
                    continue

                # Check if task is complete
                if self.provider.is_task_complete(response):
                    text = self.provider.get_response_text(response)

                    # Verify if truly complete by checking page content for progress indicators
                    page_text = self.browser.get_page_text() if hasattr(self.browser, 'get_page_text') else ""
                    page_info = self.browser.get_page_info()

                    # Check for multi-step progress indicators (Step X of Y, Task X/Y, etc.)
                    import re
                    # Use empty string if page_text is None (no navigation occurred)
                    page_text_str = page_text or ""
                    step_match = re.search(r'Step\s+(\d+)\s+of\s+(\d+)', page_text_str, re.IGNORECASE)
                    task_match = re.search(r'Task\s+(\d+)\s*/\s*(\d+)', page_text_str, re.IGNORECASE)

                    is_truly_complete = True
                    completion_message = text

                    if step_match:
                        current_step = int(step_match.group(1))
                        total_steps = int(step_match.group(2))
                        if current_step < total_steps:
                            is_truly_complete = False
                            completion_message = f"Step {current_step} of {total_steps} completed, but {total_steps - current_step} more steps remain!"
                    elif task_match:
                        current_task = int(task_match.group(1))
                        total_tasks = int(task_match.group(2))
                        if current_task < total_tasks:
                            is_truly_complete = False
                            completion_message = f"Task {current_task} of {total_tasks} completed, but {total_tasks - current_task} more tasks remain!"

                    if is_truly_complete:
                        # Actually complete - celebrate and exit!
                        if text:
                            self.console.print(f"[green]✓ {text}[/green]")
                        self.console.print("\n[bold green]✓ Task completed successfully![/bold green]")

                        total_time = time.time() - start_time

                        # Log final success
                        if self.logger:
                            summary = {
                                "success": True,
                                "iterations": iteration,
                                "total_time": total_time,
                                "final_url": page_info.get("url"),
                                "stats": self.provider.stats.to_dict(),
                                "two_phase_workflow": self.two_phase_workflow,
                                "extended_thinking": self.extended_thinking,
                                "accessibility_tree_enabled": self.use_accessibility_tree,
                            }
                            self.logger.log_summary(summary)

                        return TaskResult(
                            success=True,
                            iterations=iteration,
                            total_time=total_time,
                            final_url=page_info.get("url"),
                            stats=self.provider.stats.to_dict(),
                            video_path=self.browser.get_video_path() if self.browser else None
                        )
                    else:
                        # False completion - continue with reminder
                        self.console.print(f"[yellow]⚠️ {completion_message}[/yellow]")
                        self.console.print(f"[yellow]Continuing to next step...[/yellow]")

                        # Take screenshot to see current state
                        screenshot = self.browser.take_screenshot()
                        self.provider.stats.add_screenshot()
                        accessibility_tree = self.browser.get_accessibility_tree() if self.use_accessibility_tree else None

                        # Get page text only if URL changed (page navigation)
                        page_text = None
                        if self.use_page_text:
                            current_url = self.browser.get_page_info().get('url', '')
                            if current_url != self.last_page_url:
                                page_text = self.browser.get_page_text()
                                self.last_page_url = current_url

                        # Build reminder message
                        progress_reminder = f"""⚠️ IMPORTANT: Task is NOT complete yet!

{completion_message}

You MUST continue to the next step. Do NOT stop here.

Take a screenshot, analyze the current state, and proceed with the next step of the challenge."""

                        # Continue with reminder
                        response = self.provider.create_continuation_request(
                            screenshot=screenshot,
                            accessibility_tree=accessibility_tree if self.use_accessibility_tree else None,
                            page_text=page_text if self.use_page_text else None,
                            search_results=None,
                            display_width=self.display_width,
                            display_height=self.display_height,
                            additional_instruction=progress_reminder,
                            use_dom_manipulation=self.use_dom_manipulation,
                            use_search_tool=self.use_search_tool,
                            use_find_tool=self.use_find_tool
                        )
                        continue

                # Extract and execute actions
                actions = self.provider.extract_actions(response)

                # Track consecutive no-action iterations
                if not hasattr(self, 'no_action_count'):
                    self.no_action_count = 0

                if not actions:
                    self.no_action_count += 1

                    # Check if AI explicitly said task is complete
                    response_text = self.provider.get_response_text(response)
                    if "task completed" in response_text.lower() or "task is complete" in response_text.lower():
                        self.console.print("[green]✓ AI confirmed task completion[/green]")
                        break

                    # If AI keeps not providing actions (3 times in a row), stop
                    if self.no_action_count >= 3:
                        self.console.print("[red]✗ AI failed to provide actions for 3 consecutive iterations[/red]")
                        break

                    # Give AI one more chance with a reminder
                    self.console.print(f"[yellow]⚠ No actions provided (attempt {self.no_action_count}/3). Continuing...[/yellow]")

                    # Take screenshot to give AI current state
                    screenshot = self.browser.take_screenshot()
                    self.provider.stats.add_screenshot()

                    # Get current page state
                    accessibility_tree = self.browser.get_accessibility_tree() if self.use_accessibility_tree else None

                    # Get page text only if URL changed (page navigation)
                    page_text = None
                    if self.use_page_text:
                        current_url = self.browser.get_page_info().get('url', '')
                        page_text = self.browser.get_page_text()
                        # Track URL changes for logging
                        if current_url != self.last_page_url:
                            self.last_page_url = current_url

                    # Build explicit instruction for retry
                    retry_instruction = f"""⚠️ NO TOOL CALLS DETECTED - You provided only text, no actions!

You MUST call tools to make progress. Here's what to do RIGHT NOW:

1. Look at the screenshot below
2. Find an element to interact with (button, link, input field)
3. Call the computer tool with proper parameters:
   - For clicking: {{"action": "left_click", "coordinate": [x, y]}}
   - For typing: {{"action": "type", "text": "your text here"}}
   - For keys: {{"action": "key", "text": "Return"}}

EXAMPLE: If you see a START button at position [640, 400]:
Call: {{"action": "left_click", "coordinate": [640, 400]}}

This is attempt {self.no_action_count}/3. If you don't provide actions now, the task will fail."""

                    # Continue with a prompt reminding AI to take action
                    response = self.provider.create_continuation_request(
                        screenshot=screenshot,
                        accessibility_tree=accessibility_tree if self.use_accessibility_tree else None,
                        page_text=page_text if self.use_page_text else None,
                        search_results=None,
                        display_width=self.display_width,
                        display_height=self.display_height,
                        additional_instruction=retry_instruction,
                        use_dom_manipulation=self.use_dom_manipulation,
                        use_search_tool=self.use_search_tool,
                        use_find_tool=self.use_find_tool
                    )
                    continue
                else:
                    # Reset counter when actions are provided
                    self.no_action_count = 0

                # Track if any actions were transient
                last_action_transient = False
                search_results = []  # Store search results for tool response

                # Track if AI is only searching without taking computer actions
                if not hasattr(self, 'search_only_count'):
                    self.search_only_count = 0

                # Track action history for stuck detection
                if not hasattr(self, 'action_history'):
                    self.action_history = []

                has_computer_action = any(a.type not in [ActionType.SEARCH, ActionType.SCREENSHOT, ActionType.DOM_MANIPULATION] for a in actions)
                has_search_action = any(a.type == ActionType.SEARCH for a in actions)
                has_dom_action = any(a.type == ActionType.DOM_MANIPULATION for a in actions)

                if has_search_action and not has_computer_action and not has_dom_action:
                    self.search_only_count += 1
                elif has_computer_action or has_dom_action:
                    self.search_only_count = 0

                # Add current actions to history (keep last 5)
                action_types = [a.type.value for a in actions]
                self.action_history.append(action_types)
                if len(self.action_history) > 5:
                    self.action_history.pop(0)

                # Multi-action evidence collection: Store evidence per action
                action_evidence_map = {}
                last_url = self.browser.get_page_info().get('url', '') if hasattr(self.browser, 'get_page_info') else ''
                last_page_text = self.browser.get_page_text() if hasattr(self.browser, 'get_page_text') else ''

                # Track a11y tree for semantic diff (across entire session)
                if not hasattr(self, 'last_a11y_tree'):
                    self.last_a11y_tree = None
                if not hasattr(self, 'last_a11y_url'):
                    self.last_a11y_url = None

                for action in actions:
                    action_desc = self._format_action(action)
                    self.console.print(f"  → {action_desc}")

                    # Check if action is transient
                    is_transient = self._is_transient_action(action)
                    if is_transient:
                        last_action_transient = True

                    # Execute action
                    if action.type == ActionType.SEARCH:
                        # Handle search action with SearchTool (not through browser)
                        page_text = self.browser.get_page_text() if hasattr(self.browser, 'get_page_text') else ""
                        accessibility_tree = self.browser.get_accessibility_tree() if self.use_accessibility_tree else None

                        search_tool = SearchTool(page_text, accessibility_tree)
                        query = action.params.get("query", "")
                        search_type = action.params.get("search_type", "both")

                        search_result = search_tool.search(query, search_type)
                        search_results.append((action.id, search_result))

                        # Display search results
                        if search_result["found"]:
                            self.console.print(f"  [green]✓ {search_result['summary']}[/green]")
                        else:
                            self.console.print(f"  [yellow]✗ {search_result['summary']}[/yellow]")

                        result = {"success": True, "search_result": search_result}

                        # Two-phase workflow: Store search results for phase transition
                        if self.two_phase_workflow and self.current_phase == 1:
                            self.phase_search_results = search_results
                    elif action.type == ActionType.DOM_MANIPULATION:
                        # Handle DOM manipulation action with DOMTool
                        from cua.tools.dom_tool import DOMTool, DOMAction

                        dom_tool = DOMTool(self.browser)
                        dom_action = DOMAction(
                            action_type=action.params.get("action_type"),
                            selector=action.params.get("selector"),
                            text=action.params.get("text"),
                            search_text=action.params.get("search_text"),
                            script=action.params.get("script"),
                            limit=action.params.get("limit", 10)
                        )

                        result = dom_tool.execute(dom_action)

                        # Display result
                        if result.get("success"):
                            self.console.print(f"  [green]✓ DOM action successful[/green]")
                        else:
                            self.console.print(f"  [red]✗ Error: {result.get('error')}[/red]")
                    elif action.type == ActionType.CONTEXT_RESET:
                        # Handle context reset action
                        from cua.tools.context_reset_tool import ContextResetRequest, ContextResetTool

                        # Create reset request from params
                        request = ContextResetRequest(
                            reason=action.params.get("reason", ""),
                            progress_summary=action.params.get("progress_summary", ""),
                            next_goal=action.params.get("next_goal", "")
                        )

                        # Validate request
                        validation = ContextResetTool.validate_request(request)

                        if validation["success"]:
                            # Get current state
                            page_info = self.browser.get_page_info() if hasattr(self.browser, 'get_page_info') else {}
                            screenshot = self.browser.take_screenshot()

                            # Perform reset
                            success = self.provider.reset_context(
                                progress_summary=request.progress_summary,
                                next_goal=request.next_goal,
                                current_screenshot=screenshot,
                                current_page_info=page_info
                            )

                            if success:
                                self.console.print(f"  [bold green]✓ Context reset successful![/bold green]")
                                self.console.print(f"  [dim]Progress: {request.progress_summary}[/dim]")
                                self.console.print(f"  [dim]Next: {request.next_goal}[/dim]")

                                # Log the reset
                                if self.logger:
                                    self.logger.log_event("context_reset", {
                                        "iteration": iteration,
                                        "reason": request.reason,
                                        "progress_summary": request.progress_summary,
                                        "next_goal": request.next_goal
                                    })

                                result = {
                                    "success": True,
                                    "message": "Context has been reset. Continue with your next goal."
                                }
                            else:
                                self.console.print(f"  [red]✗ Context reset failed[/red]")
                                result = {
                                    "success": False,
                                    "error": "Failed to reset context"
                                }
                        else:
                            self.console.print(f"  [red]✗ Invalid reset request: {validation['error']}[/red]")
                            result = {
                                "success": False,
                                "error": validation["error"]
                            }
                    else:
                        # Execute browser action
                        result = self.browser.execute_action(action)

                    self.provider.stats.add_action()

                    # Multi-action evidence: Collect evidence immediately after action
                    if self.multi_action_evidence:
                        # Get current URL after action
                        current_url = self.browser.get_page_info().get('url', '') if hasattr(self.browser, 'get_page_info') else ''

                        # Capture screenshot if action requires it
                        action_screenshot = None
                        if requires_screenshot(action):
                            action_screenshot = self.browser.take_screenshot()
                            self.provider.stats.add_screenshot()

                        # Capture page text and compute diff if URL changed
                        action_page_text = None
                        action_page_text_diff = None
                        if self.use_page_text and requires_page_text_capture(last_url, current_url):
                            action_page_text = self.browser.get_page_text()

                            # Compute diff to show what changed
                            if last_page_text and action_page_text:
                                action_page_text_diff = compute_page_text_diff(last_page_text, action_page_text)
                                if action_page_text_diff:
                                    self.console.print(f"  [dim]📝 Page text changed ({len(action_page_text_diff)} chars diff)[/dim]")

                            # Update last page text for next action
                            last_page_text = action_page_text

                        # Capture a11y tree or compute semantic diff
                        action_a11y_tree = None
                        action_a11y_diff = None

                        if self.use_accessibility_tree:
                            current_a11y_tree = self.browser.get_accessibility_tree() if hasattr(self.browser, 'get_accessibility_tree') else None

                            if current_a11y_tree:
                                # Determine if we should send full tree or diff
                                should_send_full_tree = (
                                    self.last_a11y_tree is None or  # First action (no baseline)
                                    current_url != self.last_a11y_url or  # Page navigation
                                    action.type == ActionType.CONTEXT_RESET  # After context reset
                                )

                                if should_send_full_tree:
                                    # Send full tree (establish baseline)
                                    action_a11y_tree = current_a11y_tree
                                    self.console.print(f"  [dim]📊 A11y: Full tree (baseline)[/dim]")
                                elif self.use_semantic_diff:
                                    # Compute semantic diff
                                    action_a11y_diff = compute_a11y_tree_diff(self.last_a11y_tree, current_a11y_tree)

                                    if action_a11y_diff:
                                        # Check if diff is too large (>60% changed)
                                        if action_a11y_diff.is_large_diff:
                                            # Send full tree instead
                                            action_a11y_tree = current_a11y_tree
                                            self.console.print(f"  [dim]📊 A11y: Large diff (>60%), sending full tree[/dim]")
                                        else:
                                            # Send diff only
                                            self.console.print(f"  [dim]🔄 A11y changes: +{action_a11y_diff.total_added} -{action_a11y_diff.total_removed} ~{action_a11y_diff.total_modified}[/dim]")
                                    else:
                                        # No changes detected
                                        self.console.print(f"  [dim]✓ A11y: No changes[/dim]")
                                else:
                                    # Semantic diff disabled, always send full tree
                                    action_a11y_tree = current_a11y_tree

                                # Update tracking for next action
                                self.last_a11y_tree = current_a11y_tree
                                self.last_a11y_url = current_url

                        # Store evidence for this action
                        evidence = ActionEvidence(
                            action_id=action.id,
                            action_type=action.type,
                            result=result,
                            screenshot=action_screenshot,
                            page_text=action_page_text,
                            page_text_diff=action_page_text_diff,
                            accessibility_tree=action_a11y_tree,
                            accessibility_tree_diff=action_a11y_diff,
                            url=current_url
                        )
                        action_evidence_map[action.id] = evidence

                        # Update last URL for next iteration
                        last_url = current_url

                    if not result.get("success"):
                        self.console.print(f"  [red]✗ Error: {result.get('error')}[/red]")

                # Two-phase workflow: Check if we need to transition from phase 1 to phase 2
                if self.two_phase_workflow and self.current_phase == 1 and search_results:
                    self.console.print(f"\n[cyan]→ Transitioning to Phase 2 (Action with Screenshot)[/cyan]")
                    if self.logger:
                        self.logger.log_phase_transition(
                            from_phase=1,
                            to_phase=2,
                            reason="Search completed, transitioning to action phase with screenshot"
                        )
                    self.current_phase = 2

                    # Now send screenshot with phase 2 prompt
                    screenshot = self.browser.take_screenshot()
                    self.provider.stats.add_screenshot()

                    # Get fresh accessibility tree and page text
                    accessibility_tree = None
                    if self.use_accessibility_tree:
                        accessibility_tree = self.browser.get_accessibility_tree()

                    # Get page text only if URL changed (page navigation)
                    page_text = None
                    if self.use_page_text:
                        current_url = self.browser.get_page_info().get('url', '')
                        page_text = self.browser.get_page_text()
                        # Track URL changes for logging
                        if current_url != self.last_page_url:
                            self.last_page_url = current_url

                    # Build phase 2 prompt with search results
                    search_summary = "\n".join([f"- {r[1].get('summary', '')}" for r in search_results])
                    phase2_prompt = f"""📸 PHASE 2: NOW TAKE ACTION (REQUIRED)

Search results from Phase 1:
{search_summary}

**CRITICAL: You MUST now use the computer tool to take action. Do NOT just search again.**

**EXAMPLE - If you found "START" button in search:**
CORRECT: Use computer tool to click at its coordinates from the screenshot:
- Look at screenshot, see START button at position [640, 400]
- Call: {{"action": "left_click", "coordinate": [640, 400]}}

WRONG: Saying "I will click START" without actually calling the computer tool
WRONG: Calling browser_find without search_term parameter

**Required workflow for THIS iteration:**
1. Look at screenshot for visual coordinates [x, y] of elements you found
2. Call computer tool with action and coordinate
3. OR use browser_find with search_term parameter: {{"search_term": "START", "close_after": true}}

**DO NOT:**
- Provide only text without tool calls
- Call tools with missing required parameters
- Say "I need to do X" then stop - you must ACTUALLY DO X with a tool call

**YOU MUST make at least ONE tool call in this response (computer or browser_find).**"""

                    # Continue with phase 2 using search results
                    response = self.provider.create_continuation_request(
                        screenshot=screenshot,
                        accessibility_tree=accessibility_tree if self.use_accessibility_tree else None,
                        page_text=page_text if self.use_page_text else None,
                        search_results=search_results,
                        display_width=self.display_width,
                        display_height=self.display_height,
                        additional_instruction=phase2_prompt,  # Send Phase 2 instructions to AI
                        use_dom_manipulation=self.use_dom_manipulation,
                        use_search_tool=self.use_search_tool,
                        use_find_tool=self.use_find_tool
                    )

                    # Show phase 2 prompt in console for user visibility
                    self.console.print(f"[dim]{phase2_prompt}[/dim]\n")

                    # Continue to next iteration with phase 2 response
                    continue

                # Multi-action mode: Use per-action evidence (already collected)
                # Single-action mode: Take one screenshot after all actions
                screenshot = None
                accessibility_tree = None
                page_text = None

                if not self.multi_action_evidence or not action_evidence_map:
                    # Legacy mode: Single screenshot after all actions
                    screenshot = self.browser.take_screenshot()
                    self.provider.stats.add_screenshot()

                    # Get accessibility tree if enabled
                    if self.use_accessibility_tree:
                        accessibility_tree = self.browser.get_accessibility_tree()

                    # Get page text if enabled (needed after message pruning to restore context)
                    if self.use_page_text:
                        current_url = self.browser.get_page_info().get('url', '')
                        page_text = self.browser.get_page_text()

                        # Track URL changes for logging
                        if current_url != self.last_page_url:
                            self.last_page_url = current_url
                            self.console.print(f"  [dim]📄 Page navigated to: {current_url[:60]}... (fetching page text)[/dim]")
                else:
                    # Multi-action mode: Get final page text and accessibility tree
                    if self.use_accessibility_tree:
                        accessibility_tree = self.browser.get_accessibility_tree()

                    if self.use_page_text:
                        current_url = self.browser.get_page_info().get('url', '')
                        page_text = self.browser.get_page_text()

                        if current_url != self.last_page_url:
                            self.last_page_url = current_url
                            self.console.print(f"  [dim]📄 Page navigated to: {current_url[:60]}... (fetching page text)[/dim]")

                    # Use last action's screenshot for history (backward compat)
                    # Find the last visual action's screenshot
                    for action_id in reversed(list(action_evidence_map.keys())):
                        evidence = action_evidence_map[action_id]
                        if evidence.screenshot:
                            screenshot = evidence.screenshot
                            break

                    # If no screenshots in evidence (all non-visual actions), take one now
                    if screenshot is None:
                        screenshot = self.browser.take_screenshot()
                        self.provider.stats.add_screenshot()

                # Get response text and extract memory signals
                response_text = self.provider.get_response_text(response)
                memory_signals = self._extract_memory_signals(response_text)

                if response_text:
                    self.console.print(f"  [dim]{response_text}[/dim]")

                # Track important information
                if memory_signals["important_info"]:
                    self.important_context.append(memory_signals["important_info"])
                    self.console.print(f"  [cyan]📝 Remembered: {memory_signals['important_info'][:50]}...[/cyan]")

                # Add screenshot to history with metadata
                is_transient = memory_signals["transient"] or last_action_transient
                self.screenshot_history.append({
                    "screenshot": screenshot,
                    "accessibility_tree": accessibility_tree,
                    "page_text": page_text,
                    "action_type": actions[0].type.value if actions else "unknown",
                    "transient": is_transient,
                    "important_info": memory_signals["important_info"]
                })

                # Manage context window (prune old screenshots)
                self._manage_context_window()

                # Log context stats (note: screenshot_history is for internal tracking, only latest sent to API)
                non_transient_count = sum(1 for item in self.screenshot_history if not item.get("transient", False))
                # self.console.print(f"  [dim]Screenshot history: {len(self.screenshot_history)} tracked ({non_transient_count} important) | API sends: 1 latest[/dim]")
                # Note: Removed confusing display - screenshot optimization sends only latest to API

                # Log this iteration
                if self.logger:
                    actions_taken = [self._format_action(action) for action in actions]
                    action_results_list = []
                    if search_results:
                        for _, sr in search_results:
                            action_results_list.append(sr.get('summary', 'Search completed'))

                    context_info = {
                        "phase": self.current_phase if self.two_phase_workflow else "normal",
                        "screenshots_tracked": len(self.screenshot_history),
                        "non_transient_screenshots": non_transient_count,
                        "input_tokens": self.provider.stats.input_tokens,
                        "output_tokens": self.provider.stats.output_tokens,
                        "api_calls": self.provider.stats.api_calls,
                    }

                    self.logger.log_iteration(
                        iteration=iteration,
                        prompt_sent=prompt if iteration == 1 else "(continuation with screenshot + a11y tree + page text)",
                        response_received=response_text,
                        actions_taken=actions_taken,
                        action_results=action_results_list,
                        context_info=context_info
                    )

                # Check if AI has been searching without acting for too long
                if hasattr(self, 'search_only_count') and self.search_only_count >= 2:
                    self.console.print(f"[yellow]⚠ AI has been searching for {self.search_only_count} iterations without taking action[/yellow]")
                    # Note: The provider will add this reminder to the context automatically
                    # via the enhanced Phase 2 prompts and system prompts

                # Detect if stuck (repeating same actions)
                stuck_message = None
                if len(self.action_history) >= 3:
                    # Check if last 3 iterations have similar action patterns
                    recent = self.action_history[-3:]
                    # Flatten the lists
                    all_actions = [item for sublist in recent for item in sublist]
                    # Count occurrences
                    if len(all_actions) > 0:
                        from collections import Counter
                        action_counts = Counter(all_actions)
                        most_common = action_counts.most_common(1)[0]
                        # If one action type appears 3+ times in last 3 iterations
                        if most_common[1] >= 3:
                            stuck_action = most_common[0]

                            # Build suggestions based on enabled tools and stuck action
                            suggestions = []

                            if stuck_action == 'search' and self.use_find_tool:
                                suggestions.append("If searching fails → Use browser_find to navigate instantly")

                            if stuck_action == 'find' and self.use_search_tool:
                                suggestions.append("If browser_find fails → Use search_page_content for detailed results")

                            if stuck_action == 'click':
                                suggestions.append("If clicking fails → Verify element is visible in screenshot first")
                                if self.use_dom_manipulation:
                                    suggestions.append("If coordinates fail → Try DOM manipulation with CSS selectors")

                            if stuck_action in ['search', 'find', 'scroll']:
                                suggestions.append("Try using keyboard shortcuts: Home/End (jump to top/bottom)")

                            # Always suggest multi-action responses
                            suggestions.append("Consider calling MULTIPLE actions in one response (click → type → submit)")

                            # Build the message
                            stuck_message = f"⚠️ STUCK DETECTED: You've used '{stuck_action}' {most_common[1]} times recently without making progress.\n\nTry a DIFFERENT approach:"
                            if suggestions:
                                stuck_message += "\n" + "\n".join(f"- {s}" for s in suggestions)

                            self.console.print(f"[yellow]{stuck_message}[/yellow]")

                # Add progress reminder every 5 iterations
                progress_reminder = None
                if iteration % 5 == 0:
                    # Check for progress indicators in current page
                    import re
                    # Use empty string if page_text is None (no navigation occurred)
                    page_text_str = page_text or ""
                    step_match = re.search(r'Step\s+(\d+)\s+of\s+(\d+)', page_text_str, re.IGNORECASE)
                    task_match = re.search(r'Task\s+(\d+)\s*/\s*(\d+)', page_text_str, re.IGNORECASE)

                    if step_match:
                        current_step = int(step_match.group(1))
                        total_steps = int(step_match.group(2))
                        progress_reminder = f"""📊 PROGRESS CHECK (Iteration {iteration}):
Currently on Step {current_step} of {total_steps}.
{total_steps - current_step} more steps to complete.

Remember: Keep working through ALL steps until you reach Step {total_steps}."""
                    elif task_match:
                        current_task = int(task_match.group(1))
                        total_tasks = int(task_match.group(2))
                        progress_reminder = f"""📊 PROGRESS CHECK (Iteration {iteration}):
Currently on Task {current_task} of {total_tasks}.
{total_tasks - current_task} more tasks to complete.

Remember: Keep working through ALL tasks until you reach Task {total_tasks}."""

                # Combine stuck message and progress reminder if both exist
                combined_message = None
                if stuck_message and progress_reminder:
                    combined_message = f"{stuck_message}\n\n{progress_reminder}"
                elif stuck_message:
                    combined_message = stuck_message
                elif progress_reminder:
                    combined_message = progress_reminder
                    self.console.print(f"[cyan]{progress_reminder}[/cyan]")

                # Continue conversation (only with recent screenshots in context)
                # Pass search results if any, and combined messages if detected
                response = self.provider.create_continuation_request(
                    screenshot=screenshot,
                    accessibility_tree=accessibility_tree if self.use_accessibility_tree else None,
                    page_text=page_text if self.use_page_text else None,
                    search_results=search_results if search_results else None,
                    action_evidence_map=action_evidence_map if self.multi_action_evidence else None,
                    display_width=self.display_width,
                    display_height=self.display_height,
                    additional_instruction=combined_message,  # Inject stuck/progress messages
                    use_dom_manipulation=self.use_dom_manipulation,
                    use_search_tool=self.use_search_tool,
                    use_find_tool=self.use_find_tool
                )

                # Calculate and display token stats
                breakdown = self._calculate_token_breakdown(
                    response,
                    screenshot,
                    accessibility_tree if self.use_accessibility_tree else None,
                    page_text if self.use_page_text else None,
                    context_size=min(iteration, self.context_window_size),
                    iteration=iteration + 1  # Pass 1-indexed iteration for display
                )
                self.cumulative_token_stats.add_iteration(breakdown)
                print_token_stats(iteration + 1, breakdown, self.cumulative_token_stats, self.console)

                # Check if automatic context reset should be triggered
                # (Must be after breakdown calculation to use current iteration's token count)
                current_url = self.browser.get_page_info().get('url', '') if self.browser else ''
                self._auto_reset_context_if_needed(
                    iteration=iteration + 1,
                    page_text=page_text if self.use_page_text else None,
                    current_url=current_url,
                    current_input_tokens=breakdown.total_input_tokens
                )

                # Dump conversation to JSON
                self._dump_conversation(iteration + 1)

                # Small delay between iterations
                time.sleep(0.5)

            # Max iterations reached
            total_time = time.time() - start_time
            page_info = self.browser.get_page_info()

            self.console.print(f"\n[yellow]⚠ Max iterations ({max_iterations}) reached[/yellow]")

            return TaskResult(
                success=False,
                iterations=iteration,
                total_time=total_time,
                error="Max iterations reached",
                final_url=page_info.get("url"),
                stats=self.provider.stats.to_dict(),
                video_path=self.browser.get_video_path() if self.browser else None
            )

        except KeyboardInterrupt:
            self.console.print(f"\n[bold yellow]⚠ Interrupted by user (Ctrl+C)[/bold yellow]")

            total_time = time.time() - start_time
            return TaskResult(
                success=False,
                iterations=iteration,
                total_time=total_time,
                error="Interrupted by user",
                stats=self.provider.stats.to_dict() if hasattr(self.provider, 'stats') else None,
                video_path=self.browser.get_video_path() if self.browser else None
            )

        except Exception as e:
            self.console.print(f"\n[bold red]✗ Error: {str(e)}[/bold red]")

            total_time = time.time() - start_time
            return TaskResult(
                success=False,
                iterations=iteration,
                total_time=total_time,
                error=str(e),
                stats=self.provider.stats.to_dict() if hasattr(self.provider, 'stats') else None,
                video_path=self.browser.get_video_path() if self.browser else None
            )

        finally:
            # Log session summary
            if self.logger:
                summary = {
                    "success": False,  # Will be overridden if success
                    "iterations": iteration,
                    "total_time": time.time() - start_time,
                    "stats": self.provider.stats.to_dict() if hasattr(self.provider, 'stats') else None,
                    "two_phase_workflow": self.two_phase_workflow,
                    "extended_thinking": self.extended_thinking,
                    "accessibility_tree_enabled": self.use_accessibility_tree,
                }
                self.logger.log_summary(summary)
                self.console.print(f"[dim]Full logs saved to: {self.logger.get_log_path()}[/dim]")

            # Clean up and save video
            if self.browser:
                self.console.print("\n[yellow]Stopping browser...[/yellow]")

                # Get video path before stopping (if recording)
                video_path = None
                if self.record_video:
                    video_path = self.browser.get_video_path()
                    if video_path:
                        self.console.print(f"[yellow]Saving video recording...[/yellow]")

                self.browser.stop()

                # Print video path after stopping (video is finalized on stop)
                if video_path:
                    self.console.print(f"[green]✓ Video saved: {video_path}[/green]")

    def _is_transient_action(self, action) -> bool:
        """Determine if an action is transient (can be forgotten).

        Args:
            action: Action to check

        Returns:
            True if action is transient
        """
        # Actions that don't produce important info
        transient_actions = {
            "mouse_move",
            "scroll",
            "wait"
        }

        action_type = action.type.value

        # Check if it's a popup/modal close action (heuristic)
        if action_type == "click":
            # If clicking on common close button locations (top-right corner area)
            x = action.params.get("x", action.params.get("coordinate", [0, 0])[0])
            y = action.params.get("y", action.params.get("coordinate", [0, 0])[1])

            # Heuristic: top-right 20% of screen is often close buttons
            if x > self.display_width * 0.8 and y < self.display_height * 0.2:
                return True

        return action_type in transient_actions

    def _extract_memory_signals(self, text: str) -> dict:
        """Extract memory management signals from response text.

        Args:
            text: Response text from AI

        Returns:
            Dict with 'transient' (bool) and 'important_info' (str or None)
        """
        if not text:
            return {"transient": False, "important_info": None}

        text_lower = text.lower()

        # Check for explicit transient signal (TRANSIENT: marker)
        is_transient = "transient:" in text_lower

        # Check for remember signal
        important_info = None
        if "remember:" in text_lower:
            # Extract text after "REMEMBER:"
            parts = text.split("REMEMBER:", 1)
            if len(parts) > 1:
                # Get the important info (up to next sentence or 200 chars)
                info = parts[1].strip()
                important_info = info[:200].split("\n")[0]

        return {
            "transient": is_transient,
            "important_info": important_info
        }

    def _manage_context_window(self):
        """Manage the context window by pruning old screenshots.

        This implements the hybrid approach:
        1. Keep only last N screenshots (context_window_size)
        2. Prioritize keeping screenshots with important info
        3. Always discard transient action screenshots
        """
        if len(self.screenshot_history) <= self.context_window_size:
            return

        # Separate into transient and non-transient
        non_transient = []
        transient = []

        for item in self.screenshot_history:
            if item.get("transient", False):
                transient.append(item)
            else:
                non_transient.append(item)

        # Keep the most recent non-transient items up to window size
        # Always discard transient items beyond the window
        if len(non_transient) > self.context_window_size:
            # Keep most recent N non-transient items
            self.screenshot_history = non_transient[-self.context_window_size:]
        else:
            # Keep all non-transient + fill with recent transient if needed
            remaining = self.context_window_size - len(non_transient)
            self.screenshot_history = non_transient + transient[-remaining:] if remaining > 0 else non_transient

    def _should_auto_reset_context(
        self,
        iteration: int,
        page_text: Optional[str],
        current_url: str,
        input_tokens: int
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Detect if context should be automatically reset.

        Args:
            iteration: Current iteration number
            page_text: Current page text (for milestone detection)
            current_url: Current URL (for navigation detection)
            input_tokens: Current input token count

        Returns:
            Tuple of (should_reset, progress_summary, next_goal)
        """
        import re

        # Don't reset too frequently (minimum 5 iterations between resets)
        if iteration - self.last_reset_iteration < 5:
            return (False, None, None)

        # Condition 1: Milestone detection (Step X completed, now on Step X+1)
        if page_text:
            # Look for step indicators like "Step 5 of 30"
            step_match = re.search(r'Step\s+(\d+)\s+of\s+(\d+)', page_text, re.IGNORECASE)
            if step_match:
                current_step = int(step_match.group(1))
                total_steps = int(step_match.group(2))

                # Trigger reset every 5 steps or on major milestones
                if current_step > self.last_milestone_step and current_step % 5 == 0:
                    progress_summary = f"Completed steps {self.last_milestone_step + 1} through {current_step - 1}. Currently on Step {current_step} of {total_steps}."
                    next_goal = f"Complete Step {current_step} and continue progressing through remaining steps to reach Step {total_steps}."
                    self.last_milestone_step = current_step
                    self.last_reset_iteration = iteration
                    return (True, progress_summary, next_goal)

        # Condition 2: Token threshold (conversation getting too long)
        # Reset if input tokens exceed configured threshold
        if input_tokens > self.auto_reset_token_threshold:
            page_info = self.browser.get_page_info() if self.browser else {}
            page_title = page_info.get('title', 'Unknown page')
            progress_summary = f"Conversation context has grown large ({input_tokens:,} input tokens). Currently on: {page_title}"
            next_goal = "Continue with the current task from this checkpoint with a fresh context."
            self.last_reset_iteration = iteration
            return (True, progress_summary, next_goal)

        # Condition 3: Major navigation (URL path changed significantly)
        # Detect transitions like /step1 -> /step2, or main page -> different section
        if self.current_page_section and current_url:
            # Extract meaningful path segment
            current_section = re.search(r'/([^/?]+)', current_url)
            if current_section:
                current_section = current_section.group(1)
                if current_section != self.current_page_section:
                    # Section changed, consider reset after multiple iterations in new section
                    # (Don't reset immediately on navigation, give AI time to work)
                    if iteration - self.last_reset_iteration > 10:
                        page_info = self.browser.get_page_info() if self.browser else {}
                        page_title = page_info.get('title', 'New section')
                        progress_summary = f"Navigated from {self.current_page_section} to {current_section}. Now on: {page_title}"
                        next_goal = "Continue working on the current task in this new section."
                        self.current_page_section = current_section
                        self.last_reset_iteration = iteration
                        return (True, progress_summary, next_goal)
                    else:
                        # Update tracking but don't reset yet
                        self.current_page_section = current_section
            else:
                # Initialize current section if not set
                if current_url and not self.current_page_section:
                    section = re.search(r'/([^/?]+)', current_url)
                    if section:
                        self.current_page_section = section.group(1)

        return (False, None, None)

    def _auto_reset_context_if_needed(
        self,
        iteration: int,
        page_text: Optional[str],
        current_url: str,
        current_input_tokens: int
    ):
        """Automatically reset context if conditions are met.

        Args:
            iteration: Current iteration number
            page_text: Current page text
            current_url: Current URL
            current_input_tokens: Input token count for current iteration
        """
        # Check if auto reset is enabled
        if not self.auto_context_reset:
            return

        # Debug logging for auto-reset detection
        print(f"[DEBUG AUTO-RESET] Iteration {iteration}: Checking with {current_input_tokens:,} tokens (threshold: {self.auto_reset_token_threshold:,})")

        should_reset, progress_summary, next_goal = self._should_auto_reset_context(
            iteration=iteration,
            page_text=page_text,
            current_url=current_url,
            input_tokens=current_input_tokens
        )

        if should_reset and progress_summary and next_goal:
            self.console.print(f"\n[bold cyan]🔄 Automatic Context Reset Triggered[/bold cyan]")
            self.console.print(f"[dim]Reason: Token optimization and milestone checkpoint[/dim]")

            # Get current state
            page_info = self.browser.get_page_info() if self.browser else {}
            screenshot = self.browser.take_screenshot() if self.browser else None

            # Perform reset
            success = self.provider.reset_context(
                progress_summary=progress_summary,
                next_goal=next_goal,
                current_screenshot=screenshot,
                current_page_info=page_info
            )

            if success:
                self.console.print(f"  [bold green]✓ Context reset successful![/bold green]")
                self.console.print(f"  [dim]Progress: {progress_summary}[/dim]")
                self.console.print(f"  [dim]Next: {next_goal}[/dim]\n")

                # Set flag to indicate we just reset, so loop should start fresh
                self.just_reset = True

                # Log the reset
                if self.logger:
                    self.logger.log_event("auto_context_reset", {
                        "iteration": iteration,
                        "trigger": "automatic",
                        "progress_summary": progress_summary,
                        "next_goal": next_goal,
                        "input_tokens_before": current_input_tokens
                    })
            else:
                self.console.print(f"  [red]✗ Automatic context reset failed[/red]\n")

    def _format_action(self, action) -> str:
        """Format action for display.

        Args:
            action: Action to format

        Returns:
            Formatted action string
        """
        action_type = action.type.value

        if action.type.value == "click":
            x = action.params.get("x", action.params.get("coordinate", [0, 0])[0])
            y = action.params.get("y", action.params.get("coordinate", [0, 0])[1])
            return f"Click at ({x}, {y})"
        elif action.type.value == "type":
            text = action.params.get("text", "")
            truncated = text[:50] + "..." if len(text) > 50 else text
            return f"Type: '{truncated}'"
        elif action.type.value == "key" or action.type.value == "keypress":
            key = action.params.get("text", action.params.get("keys", [""])[0])
            return f"Press key: {key}"
        elif action.type.value == "scroll":
            return "Scroll page"
        elif action.type.value == "screenshot":
            return "Take screenshot"
        elif action.type.value == "wait":
            return "Wait"
        elif action.type.value == "dom_manipulation":
            dom_action_type = action.params.get("action_type", "unknown")
            if dom_action_type == "click_selector":
                selector = action.params.get("selector", "")
                return f"DOM Click: {selector}"
            elif dom_action_type == "fill_selector":
                selector = action.params.get("selector", "")
                text = action.params.get("text", "")
                truncated = text[:30] + "..." if len(text) > 30 else text
                return f"DOM Fill: {selector} = '{truncated}'"
            elif dom_action_type == "find_selectors":
                search_text = action.params.get("search_text", "")
                return f"DOM Find: '{search_text}'"
            elif dom_action_type == "get_info":
                selector = action.params.get("selector", "")
                return f"DOM Info: {selector}"
            elif dom_action_type == "evaluate_js":
                return "DOM Evaluate JS"
            else:
                return f"DOM: {dom_action_type}"
        elif action.type.value == "context_reset":
            reason = action.params.get("reason", "")
            truncated_reason = reason[:40] + "..." if len(reason) > 40 else reason
            return f"Context Reset: {truncated_reason}"
        else:
            return f"{action_type.title()}"
