"""Token usage statistics tracking."""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class TokenBreakdown:
    """Detailed breakdown of token usage per API call."""

    # Input token breakdown
    system_prompt_tokens: int = 0
    screenshots_tokens: int = 0
    page_text_tokens: int = 0
    accessibility_tree_tokens: int = 0
    ai_responses_tokens: int = 0  # Previous assistant responses in context

    # Total input/output
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens."""
        return self.total_input_tokens + self.total_output_tokens

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "input_breakdown": {
                "system_prompt": self.system_prompt_tokens,
                "screenshots": self.screenshots_tokens,
                "page_text": self.page_text_tokens,
                "accessibility_tree": self.accessibility_tree_tokens,
                "ai_responses": self.ai_responses_tokens,
            },
            "total_input": self.total_input_tokens,
            "total_output": self.total_output_tokens,
            "total": self.total_tokens
        }


@dataclass
class CumulativeTokenStats:
    """Cumulative token statistics across all iterations."""

    # Cumulative totals
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_api_calls: int = 0

    # Cumulative breakdown
    total_system_prompt_tokens: int = 0
    total_screenshots_tokens: int = 0
    total_page_text_tokens: int = 0
    total_accessibility_tree_tokens: int = 0
    total_ai_responses_tokens: int = 0

    # Per-iteration history
    iteration_breakdowns: list = field(default_factory=list)

    def add_iteration(self, breakdown: TokenBreakdown):
        """Add an iteration's token breakdown."""
        self.total_input_tokens += breakdown.total_input_tokens
        self.total_output_tokens += breakdown.total_output_tokens
        self.total_api_calls += 1

        self.total_system_prompt_tokens += breakdown.system_prompt_tokens
        self.total_screenshots_tokens += breakdown.screenshots_tokens
        self.total_page_text_tokens += breakdown.page_text_tokens
        self.total_accessibility_tree_tokens += breakdown.accessibility_tree_tokens
        self.total_ai_responses_tokens += breakdown.ai_responses_tokens

        self.iteration_breakdowns.append(breakdown.to_dict())

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens."""
        return self.total_input_tokens + self.total_output_tokens

    @property
    def avg_input_tokens_per_call(self) -> float:
        """Calculate average input tokens per API call."""
        return self.total_input_tokens / self.total_api_calls if self.total_api_calls > 0 else 0

    @property
    def avg_output_tokens_per_call(self) -> float:
        """Calculate average output tokens per API call."""
        return self.total_output_tokens / self.total_api_calls if self.total_api_calls > 0 else 0

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "cumulative": {
                "total_input": self.total_input_tokens,
                "total_output": self.total_output_tokens,
                "total": self.total_tokens,
                "api_calls": self.total_api_calls,
                "avg_input_per_call": round(self.avg_input_tokens_per_call, 2),
                "avg_output_per_call": round(self.avg_output_tokens_per_call, 2),
            },
            "breakdown": {
                "system_prompt": self.total_system_prompt_tokens,
                "screenshots": self.total_screenshots_tokens,
                "page_text": self.total_page_text_tokens,
                "accessibility_tree": self.total_accessibility_tree_tokens,
                "ai_responses": self.total_ai_responses_tokens,
            },
            "iterations": self.iteration_breakdowns
        }


def estimate_tokens(text: str) -> int:
    """Estimate tokens from text (rough approximation: 1 token ~ 4 chars)."""
    return len(text) // 4 if text else 0


def estimate_image_tokens(width: int, height: int) -> int:
    """Estimate tokens for an image based on dimensions.

    Claude's vision API uses approximately 1600 tokens per 1024x1024 image.
    For other sizes: tokens ≈ (width * height) / (1024 * 1024) * 1600
    """
    return int((width * height) / (1024 * 1024) * 1600)


def print_token_stats(iteration: int, breakdown: TokenBreakdown, cumulative: CumulativeTokenStats, console):
    """Print formatted token statistics to console.

    Args:
        iteration: Current iteration number
        breakdown: Token breakdown for this iteration
        cumulative: Cumulative stats across all iterations
        console: Rich console object for formatted output
    """
    # Print current iteration stats
    console.print(f"\n[bold cyan]╭─ Token Usage (Iteration {iteration}) ───────────────────────[/bold cyan]")
    console.print(f"[cyan]│[/cyan] [bold]Input Tokens:[/bold]      {breakdown.total_input_tokens:>10,}")
    console.print(f"[cyan]│[/cyan]   [dim]System Prompt:[/dim]   {breakdown.system_prompt_tokens:>10,}")
    console.print(f"[cyan]│[/cyan]   [dim]Screenshots:[/dim]     {breakdown.screenshots_tokens:>10,}")

    if breakdown.page_text_tokens > 0:
        console.print(f"[cyan]│[/cyan]   [dim]Page Text:[/dim]       {breakdown.page_text_tokens:>10,}")

    if breakdown.accessibility_tree_tokens > 0:
        console.print(f"[cyan]│[/cyan]   [dim]A11y Tree:[/dim]       {breakdown.accessibility_tree_tokens:>10,}")

    console.print(f"[cyan]│[/cyan]   [dim]AI Responses:[/dim]    {breakdown.ai_responses_tokens:>10,}")
    console.print(f"[cyan]│[/cyan] [bold]Output Tokens:[/bold]     {breakdown.total_output_tokens:>10,}")
    console.print(f"[cyan]│[/cyan] [bold yellow]Total This Call:[/bold yellow]   {breakdown.total_tokens:>10,}")
    console.print(f"[cyan]│[/cyan]")
    console.print(f"[cyan]│[/cyan] [bold green]Cumulative Total:[/bold green]  {cumulative.total_tokens:>10,} [dim]({cumulative.total_api_calls} calls)[/dim]")
    console.print(f"[cyan]╰────────────────────────────────────────────────────────[/cyan]\n")
