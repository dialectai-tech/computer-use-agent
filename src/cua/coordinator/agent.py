"""Simplified coordinator agent for MCP multi-agent architecture.

This coordinator wraps the existing ComputerUseAgent logic while adding:
- Critical facts tracking for better context management
- Foundation for MCP server integration (future)
- Simplified delegation pattern (no workers upfront)
"""

from typing import Optional
from rich.console import Console

from cua.providers.base import ComputerUseProvider
from cua.agent.loop import ComputerUseAgent, TaskResult
from cua.coordinator.facts_tracker import CriticalFactsTracker


class CoordinatorAgent:
    """Coordinator agent that orchestrates task execution.

    This is a simplified coordinator that:
    1. Wraps existing ComputerUseAgent for browser automation
    2. Tracks critical facts (codes, selectors, completed steps)
    3. Prepares foundation for MCP integration

    Philosophy: Start minimal, expand when needed (YAGNI)
    """

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
        track_facts: bool = True,
    ):
        """Initialize coordinator agent.

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
            track_facts: Enable critical facts tracking
        """
        self.console = Console()
        self.track_facts = track_facts

        # Initialize facts tracker
        self.facts_tracker = CriticalFactsTracker() if track_facts else None

        # Initialize the existing agent (wrapping pattern)
        # This preserves all working functionality while we add new features
        self.agent = ComputerUseAgent(
            provider=provider,
            display_width=display_width,
            display_height=display_height,
            zoom=zoom,
            headless=headless,
            record_video=record_video,
            video_dir=video_dir,
            enable_caching=enable_caching,
            context_window_size=context_window_size,
            extended_thinking=extended_thinking,
            thinking_budget=thinking_budget,
            use_accessibility_tree=use_accessibility_tree,
        )

    def run_task(
        self,
        url: str,
        prompt: str,
        max_iterations: int = 30
    ) -> TaskResult:
        """Run a computer use automation task with facts tracking.

        This is the main entry point for task execution. Currently delegates
        to the existing ComputerUseAgent while tracking critical facts.

        Args:
            url: URL to navigate to
            prompt: Task description
            max_iterations: Maximum number of iterations

        Returns:
            TaskResult with execution details
        """
        # Show coordinator mode
        if self.track_facts:
            self.console.print("[dim]Using CoordinatorAgent with facts tracking[/dim]")

        # Enhance prompt with facts context if available
        enhanced_prompt = self._enhance_prompt_with_facts(prompt)

        # Delegate to existing agent
        # TODO: Add MCP integration here in future
        result = self.agent.run_task(
            url=url,
            prompt=enhanced_prompt,
            max_iterations=max_iterations
        )

        # Extract facts from result (if tracking enabled)
        if self.track_facts and self.facts_tracker:
            self._extract_facts_from_result(result)
            facts_summary = self.facts_tracker.get_summary()
            if any(facts_summary.values()):
                self.console.print("\n[bold cyan]═══ Tracked Facts ═══[/bold cyan]")
                self.console.print(self.facts_tracker.to_context_string())

        return result

    def _enhance_prompt_with_facts(self, prompt: str) -> str:
        """Enhance prompt with tracked critical facts.

        Args:
            prompt: Original prompt

        Returns:
            Enhanced prompt with facts context
        """
        if not self.track_facts or not self.facts_tracker:
            return prompt

        facts_context = self.facts_tracker.to_context_string()
        if facts_context == "No critical facts tracked yet.":
            return prompt

        # Add facts context to prompt
        return f"""{prompt}

CRITICAL FACTS FROM PREVIOUS ACTIONS:
{facts_context}

Use this information to avoid repeating work or losing important data."""

    def _extract_facts_from_result(self, result: TaskResult) -> None:
        """Extract critical facts from task result.

        Args:
            result: Task execution result
        """
        if not self.facts_tracker:
            return

        # Extract from final URL if available
        if result.final_url:
            self.facts_tracker.extract_from_text(result.final_url)

        # Extract from error message if available
        if result.error:
            self.facts_tracker.extract_from_text(result.error)

        # TODO: Add more sophisticated extraction
        # - Extract from action results
        # - Extract from page content
        # - Track successful sequences
        # This will be enhanced as we add MCP integration
