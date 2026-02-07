"""Main agent loop for computer use automation."""

import time
from dataclasses import dataclass
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from cua.providers.base import ComputerUseProvider, ActionType
from cua.browser.playwright_controller import PlaywrightController
from cua.tools.search_tool import SearchTool


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
        use_accessibility_tree: bool = True
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
        """
        self.provider = provider
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
        self.console = Console()
        self.browser: Optional[PlaywrightController] = None

        # Context management: track screenshots and actions for hybrid approach
        self.screenshot_history = []  # List of (screenshot, action_type, important_info)
        self.important_context = []  # List of important information to remember

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
            self.console.print(f"[dim]Task: {prompt}[/dim]\n")

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

                if not actions:
                    self.console.print("[yellow]No actions found, task may be complete[/yellow]")
                    break

                # Track if any actions were transient
                last_action_transient = False
                search_results = []  # Store search results for tool response

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
                    else:
                        # Execute browser action
                        result = self.browser.execute_action(action)

                    self.provider.stats.add_action()

                    if not result.get("success"):
                        self.console.print(f"  [red]✗ Error: {result.get('error')}[/red]")

                # Take screenshot and accessibility tree after actions
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

        # Check for explicit transient signal
        is_transient = "transient" in text_lower

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
