"""Main agent loop for computer use automation."""

import time
from dataclasses import dataclass
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from cua.providers.base import ComputerUseProvider, ActionType
from cua.browser.playwright_controller import PlaywrightController
from cua.tools.search_tool import SearchTool
from cua.utils.logger import AgentLogger


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
        two_phase_workflow: bool = False,
        max_message_turns: int = 10
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
            two_phase_workflow: Enable two-phase workflow (search first, then screenshot)
            max_message_turns: Maximum number of message turns to keep in history
        """
        self.provider = provider
        self.max_message_turns = max_message_turns

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
        self.two_phase_workflow = two_phase_workflow
        self.console = Console()
        self.browser: Optional[PlaywrightController] = None
        self.logger: Optional[AgentLogger] = None  # Will be initialized when task starts

        # Context management: track screenshots and actions for hybrid approach
        self.screenshot_history = []  # List of (screenshot, action_type, important_info)
        self.important_context = []  # List of important information to remember

        # Two-phase workflow state
        self.current_phase = 1 if two_phase_workflow else 0  # 0=normal, 1=search, 2=action
        self.phase_search_results = None  # Store search results from phase 1

        # Pass configuration to provider
        self.provider.enable_caching = enable_caching
        self.provider.extended_thinking = extended_thinking
        self.provider.thinking_budget = thinking_budget

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

            # Get page text for searching/analysis
            page_text = self.browser.get_page_text()

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
                    accessibility_tree=accessibility_tree,
                    page_text=page_text,
                    display_width=self.display_width,
                    display_height=self.display_height
                )
            else:
                # Normal workflow: send everything including screenshot
                response = self.provider.create_initial_request(
                    prompt=prompt,
                    screenshot=screenshot,
                    accessibility_tree=accessibility_tree,
                    page_text=page_text,
                    display_width=self.display_width,
                    display_height=self.display_height
                )

            # Main agent loop
            while iteration < max_iterations:
                iteration += 1

                self.console.print(f"[bold]Iteration {iteration}/{max_iterations}[/bold]")

                # Check if task is complete
                if self.provider.is_task_complete(response):
                    text = self.provider.get_response_text(response)
                    if text:
                        self.console.print(f"[green]✓ {text}[/green]")
                    self.console.print("\n[bold green]✓ Task completed successfully![/bold green]")

                    total_time = time.time() - start_time
                    page_info = self.browser.get_page_info()

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
                    page_text = self.browser.get_page_text()

                    # Continue with a prompt reminding AI to take action
                    response = self.provider.create_continuation_request(
                        screenshot=screenshot,
                        accessibility_tree=accessibility_tree,
                        page_text=page_text,
                        search_results=None,
                        display_width=self.display_width,
                        display_height=self.display_height
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

                has_computer_action = any(a.type not in [ActionType.SEARCH, ActionType.SCREENSHOT] for a in actions)
                has_search_action = any(a.type == ActionType.SEARCH for a in actions)

                if has_search_action and not has_computer_action:
                    self.search_only_count += 1
                elif has_computer_action:
                    self.search_only_count = 0

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
                    else:
                        # Execute browser action
                        result = self.browser.execute_action(action)

                    self.provider.stats.add_action()

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
                    page_text = self.browser.get_page_text()

                    # Build phase 2 prompt with search results
                    search_summary = "\n".join([f"- {r[1].get('summary', '')}" for r in search_results])
                    phase2_prompt = f"""📸 PHASE 2: NOW TAKE ACTION (REQUIRED)

Search results from Phase 1:
{search_summary}

**CRITICAL: You MUST now use the computer tool to take action. Do NOT just search again.**

Required workflow:
1. Look at the screenshot to find visual coordinates [x, y] of elements from search
2. Use browser_find(search_term) to navigate to specific elements (faster than scrolling)
3. Take a computer action: click, type, or keyboard shortcut
4. Take screenshot to see result

**DO NOT:**
- Search again without taking action
- Provide only text without tool calls
- Skip clicking/typing actions
- Declare task complete just because you FOUND elements - you must CLICK/TYPE/INTERACT first!
- Say "I need to do X" then stop - you must ACTUALLY DO X

**YOU MUST:** Use computer tool (click/type) or browser_find tool in this phase.
**REMEMBER:** Finding is NOT completing. You must PERFORM actions and VERIFY results before declaring completion."""

                    # Continue with phase 2 using search results
                    response = self.provider.create_continuation_request(
                        screenshot=screenshot,
                        accessibility_tree=accessibility_tree,
                        page_text=page_text,
                        search_results=search_results,
                        display_width=self.display_width,
                        display_height=self.display_height,
                        additional_instruction=phase2_prompt  # Send Phase 2 instructions to AI
                    )

                    # Show phase 2 prompt in console for user visibility
                    self.console.print(f"[dim]{phase2_prompt}[/dim]\n")

                    # Continue to next iteration with phase 2 response
                    continue

                # Take screenshot and accessibility tree after actions (normal flow)
                screenshot = self.browser.take_screenshot()
                self.provider.stats.add_screenshot()

                # Get accessibility tree if enabled
                accessibility_tree = None
                if self.use_accessibility_tree:
                    accessibility_tree = self.browser.get_accessibility_tree()

                # Get page text for searching/analysis
                page_text = self.browser.get_page_text()

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

                # Log context stats
                non_transient_count = sum(1 for item in self.screenshot_history if not item.get("transient", False))
                self.console.print(f"  [dim]Context: {len(self.screenshot_history)} screenshots ({non_transient_count} important)[/dim]")

                # Log this iteration
                if self.logger:
                    actions_taken = [self._format_action(action) for action in actions]
                    action_results_list = []
                    if search_results:
                        for _, sr in search_results:
                            action_results_list.append(sr.get('summary', 'Search completed'))

                    context_info = {
                        "phase": self.current_phase if self.two_phase_workflow else "normal",
                        "screenshots_in_context": len(self.screenshot_history),
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

                # Continue conversation (only with recent screenshots in context)
                # Pass search results if any
                response = self.provider.create_continuation_request(
                    screenshot=screenshot,
                    accessibility_tree=accessibility_tree,
                    page_text=page_text,
                    search_results=search_results if search_results else None,
                    display_width=self.display_width,
                    display_height=self.display_height
                )

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
        else:
            return f"{action_type.title()}"
