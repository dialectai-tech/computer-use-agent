"""Main agent loop for computer use automation."""

import time
from dataclasses import dataclass
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from cua.providers.base import ComputerUseProvider
from cua.browser.playwright_controller import PlaywrightController


@dataclass
class TaskResult:
    """Result from running a task."""
    success: bool
    iterations: int
    total_time: float
    error: Optional[str] = None
    final_url: Optional[str] = None


class ComputerUseAgent:
    """Main agent for computer use automation."""

    def __init__(
        self,
        provider: ComputerUseProvider,
        display_width: int = 1280,
        display_height: int = 720,
        headless: bool = True
    ):
        """Initialize agent.

        Args:
            provider: AI provider to use
            display_width: Browser viewport width
            display_height: Browser viewport height
            headless: Whether to run browser in headless mode
        """
        self.provider = provider
        self.display_width = display_width
        self.display_height = display_height
        self.headless = headless
        self.console = Console()
        self.browser: Optional[PlaywrightController] = None

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
            self.browser = PlaywrightController(
                display_width=self.display_width,
                display_height=self.display_height,
                headless=self.headless
            )
            self.browser.start()

            # Navigate to URL
            self.console.print(f"[yellow]Navigating to {url}...[/yellow]")
            self.browser.navigate(url)

            # Take initial screenshot
            screenshot = self.browser.take_screenshot()

            # Create initial request
            self.console.print(f"[yellow]Sending task to AI...[/yellow]")
            self.console.print(f"[dim]Task: {prompt}[/dim]\n")

            response = self.provider.create_initial_request(
                prompt=prompt,
                screenshot=screenshot,
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
                        final_url=page_info.get("url")
                    )

                # Extract and execute actions
                actions = self.provider.extract_actions(response)

                if not actions:
                    self.console.print("[yellow]No actions found, task may be complete[/yellow]")
                    break

                for action in actions:
                    action_desc = self._format_action(action)
                    self.console.print(f"  → {action_desc}")

                    # Execute action
                    result = self.browser.execute_action(action)

                    if not result.get("success"):
                        self.console.print(f"  [red]✗ Error: {result.get('error')}[/red]")

                # Take screenshot after actions
                screenshot = self.browser.take_screenshot()

                # Get response text
                response_text = self.provider.get_response_text(response)
                if response_text:
                    self.console.print(f"  [dim]{response_text}[/dim]")

                # Continue conversation
                response = self.provider.create_continuation_request(
                    screenshot=screenshot,
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
                final_url=page_info.get("url")
            )

        except Exception as e:
            self.console.print(f"\n[bold red]✗ Error: {str(e)}[/bold red]")

            total_time = time.time() - start_time
            return TaskResult(
                success=False,
                iterations=iteration,
                total_time=total_time,
                error=str(e)
            )

        finally:
            # Clean up
            if self.browser:
                self.console.print("\n[yellow]Stopping browser...[/yellow]")
                self.browser.stop()

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
