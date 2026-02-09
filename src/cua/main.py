"""CL I interface for Computer Use Automation."""

import os
import sys
import click
from dotenv import load_dotenv
from rich.console import Console

from cua.agent.loop import ComputerUseAgent
from cua.providers.claude import ClaudeProvider
from cua.providers.openai import OpenAIProvider
from cua.providers.bedrock import BedrockProvider

# Load environment variables
load_dotenv()

console = Console()


@click.command()
@click.option(
    "--url",
    required=True,
    help="URL to navigate to"
)
@click.option(
    "--prompt",
    required=True,
    help="Task description/prompt"
)
@click.option(
    "--provider",
    type=click.Choice(["claude", "openai", "bedrock"], case_sensitive=False),
    default=lambda: os.getenv("PROVIDER", "claude"),
    help="AI provider to use (default: from .env or claude)"
)
@click.option(
    "--model",
    default=None,
    help="Model to use (default: provider-specific default)"
)
@click.option(
    "--max-iterations",
    type=int,
    default=lambda: int(os.getenv("MAX_ITERATIONS", "30")),
    help="Maximum number of iterations (default: 30)"
)
@click.option(
    "--display-width",
    type=int,
    default=lambda: int(os.getenv("DISPLAY_WIDTH", "1024")),
    help="Display width in pixels (default: 1024)"
)
@click.option(
    "--display-height",
    type=int,
    default=lambda: int(os.getenv("DISPLAY_HEIGHT", "900")),
    help="Display height in pixels (default: 900)"
)
@click.option(
    "--zoom",
    type=int,
    default=lambda: int(os.getenv("BROWSER_ZOOM", "85")),
    help="Browser zoom level in percent (default: 85)"
)
@click.option(
    "--headless/--no-headless",
    default=True,
    help="Run browser in headless mode (default: True)"
)
@click.option(
    "--record-video/--no-record-video",
    default=False,
    help="Record video of the browser session (default: False)"
)
@click.option(
    "--video-dir",
    default="./recordings",
    help="Directory to save video recordings (default: ./recordings)"
)
@click.option(
    "--enable-caching/--disable-caching",
    default=True,
    help="Enable prompt caching for cost savings (default: enabled)"
)
@click.option(
    "--context-window-size",
    type=int,
    default=lambda: int(os.getenv("CONTEXT_WINDOW_SIZE", "3")),
    help="Number of recent screenshots to keep in context (default: 3)"
)
@click.option(
    "--extended-thinking/--no-extended-thinking",
    default=False,
    help="Enable extended thinking for complex reasoning (default: disabled)"
)
@click.option(
    "--thinking-budget",
    type=int,
    default=lambda: int(os.getenv("THINKING_BUDGET", "10000")),
    help="Token budget for extended thinking (default: 10000)"
)
@click.option(
    "--use-accessibility-tree/--no-accessibility-tree",
    default=False,
    help="Use accessibility tree alongside screenshots (default: disabled)"
)
@click.option(
    "--use-page-text/--no-page-text",
    default=True,
    help="Include extracted page text for search tool (default: enabled, needed for search_page_content)"
)
@click.option(
    "--use-dom-manipulation/--no-use-dom-manipulation",
    default=True,
    help="Enable DOM manipulation tool for CSS selector-based actions (default: enabled)"
)
@click.option(
    "--use-search-tool/--no-use-search-tool",
    default=True,
    help="Enable search_page_content tool for searching page text/tree (default: enabled)"
)
@click.option(
    "--use-find-tool/--no-use-find-tool",
    default=True,
    help="Enable browser_find tool for Ctrl+F navigation (default: enabled)"
)
@click.option(
    "--two-phase-workflow/--no-two-phase-workflow",
    default=False,
    help="Enable two-phase workflow: search first (no screenshot), then action with screenshot (default: disabled)"
)
@click.option(
    "--max-message-turns",
    type=int,
    default=lambda: int(os.getenv("MAX_MESSAGE_TURNS", "3")),
    help="Maximum number of message turns to keep in history (default: 3)"
)
@click.option(
    "--auto-context-reset/--no-auto-context-reset",
    default=True,
    help="Automatically reset context at milestones and token thresholds (default: enabled)"
)
@click.option(
    "--auto-reset-token-threshold",
    type=int,
    default=30000,
    help="Input token threshold for automatic context reset (default: 30000)"
)
@click.option(
    "--multi-action-evidence/--single-action-evidence",
    default=True,
    help="Capture per-action evidence (screenshots, page text) for multi-action responses (default: enabled)"
)
@click.option(
    "--max-actions-per-response",
    type=int,
    default=10,
    help="Maximum number of actions to execute in a single response (default: 10, 0 = unlimited)"
)
@click.option(
    "--use-semantic-diff/--no-use-semantic-diff",
    default=True,
    help="Use semantic diff for a11y tree instead of full tree after baseline (default: enabled, requires --use-accessibility-tree)"
)
def cli(
    url: str,
    prompt: str,
    provider: str,
    model: str,
    max_iterations: int,
    display_width: int,
    display_height: int,
    zoom: int,
    headless: bool,
    record_video: bool,
    video_dir: str,
    enable_caching: bool,
    context_window_size: int,
    extended_thinking: bool,
    thinking_budget: int,
    use_accessibility_tree: bool,
    use_page_text: bool,
    use_dom_manipulation: bool,
    use_search_tool: bool,
    use_find_tool: bool,
    two_phase_workflow: bool,
    max_message_turns: int,
    auto_context_reset: bool,
    auto_reset_token_threshold: int,
    multi_action_evidence: bool,
    max_actions_per_response: int,
    use_semantic_diff: bool
):
    """Computer Use Automation - Multi-provider AI agent for browser automation.

    This tool enables AI agents to autonomously complete web-based tasks through
    browser automation. It supports both Anthropic Claude and OpenAI models.

    Example usage:

        cua --url "https://example.com" --prompt "Fill out the contact form"

        cua --provider openai --url "https://forms.gle/xyz" --prompt "Complete survey"
    """
    # Display header
    console.print("\n[bold cyan]╔═══════════════════════════════════════╗[/bold cyan]")
    console.print("[bold cyan]║  Computer Use Automation (CUA)        ║[/bold cyan]")
    console.print("[bold cyan]╚═══════════════════════════════════════╝[/bold cyan]\n")

    # Validate flag combinations (atomic flag-to-feature relationships)
    if not use_page_text and not use_accessibility_tree:
        console.print("[yellow]⚠️  Warning: Both --no-page-text and --no-accessibility-tree are disabled.[/yellow]")
        console.print("[yellow]   The search_page_content tool will have no data to search.[/yellow]")
        console.print("[yellow]   Agent will rely on DOM manipulation and coordinate-based actions only.[/yellow]\n")

    if two_phase_workflow and not use_page_text and not use_accessibility_tree:
        console.print("[bold red]Error: --two-phase-workflow requires either --use-page-text or --use-accessibility-tree[/bold red]")
        console.print("Two-phase workflow's first phase is search-only, which needs data to search.")
        console.print("Enable at least one: --use-page-text (recommended) or --use-accessibility-tree")
        sys.exit(1)

    # Initialize provider
    try:
        if provider.lower() == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                console.print("[bold red]Error: ANTHROPIC_API_KEY not found in environment[/bold red]")
                console.print("Please set it in your .env file or environment variables")
                sys.exit(1)

            model = model or os.getenv("DEFAULT_MODEL", "claude-sonnet-4-5")
            ai_provider = ClaudeProvider(api_key=api_key, model=model)

        elif provider.lower() == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                console.print("[bold red]Error: OPENAI_API_KEY not found in environment[/bold red]")
                console.print("Please set it in your .env file or environment variables")
                sys.exit(1)

            model = model or "computer-use-preview"
            ai_provider = OpenAIProvider(api_key=api_key, model=model)

        elif provider.lower() == "bedrock":
            # Bedrock uses AWS credential chain
            # Priority: AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY > AWS_BEARER_TOKEN_BEDROCK > IAM Role
            model = model or os.getenv("BEDROCK_MODEL", "claude-sonnet-4-5")
            region = os.getenv("AWS_REGION", "us-east-1")

            # Check if any AWS credentials are configured
            has_credentials = (
                os.getenv("AWS_ACCESS_KEY_ID") or
                os.getenv("AWS_BEARER_TOKEN_BEDROCK") or
                os.getenv("AWS_SESSION_TOKEN")
            )

            if not has_credentials:
                console.print("[bold yellow]Warning: No AWS credentials found in environment[/bold yellow]")
                console.print("Bedrock will attempt to use IAM role or ~/.aws/credentials")
                console.print("\nTo authenticate, set one of:")
                console.print("  - AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY")
                console.print("  - AWS_BEARER_TOKEN_BEDROCK (mapped to AWS_SESSION_TOKEN)")
                console.print("  - Use IAM role (if running on AWS EC2/ECS)")
                console.print()

            try:
                ai_provider = BedrockProvider(model=model, region=region)
            except Exception as e:
                console.print(f"[bold red]Error initializing Bedrock provider: {str(e)}[/bold red]")
                console.print("\nPlease ensure you have valid AWS credentials configured.")
                sys.exit(1)

        else:
            console.print(f"[bold red]Error: Unknown provider '{provider}'[/bold red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]Error initializing provider: {str(e)}[/bold red]")
        sys.exit(1)

    # Ensure URL has protocol
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
        console.print(f"[dim]Adding https:// to URL: {url}[/dim]\n")

    # Initialize agent
    agent = ComputerUseAgent(
        provider=ai_provider,
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
        use_page_text=use_page_text,
        use_dom_manipulation=use_dom_manipulation,
        use_search_tool=use_search_tool,
        use_find_tool=use_find_tool,
        two_phase_workflow=two_phase_workflow,
        max_message_turns=max_message_turns,
        auto_context_reset=auto_context_reset,
        auto_reset_token_threshold=auto_reset_token_threshold,
        multi_action_evidence=multi_action_evidence,
        max_actions_per_response=max_actions_per_response,
        use_semantic_diff=use_semantic_diff
    )

    # Run task
    result = agent.run_task(
        url=url,
        prompt=prompt,
        max_iterations=max_iterations
    )

    # Display results
    console.print("\n[bold cyan]═══ Results ═══[/bold cyan]")
    console.print(f"Status: {'[green]✓ Success[/green]' if result.success else '[red]✗ Failed[/red]'}")
    console.print(f"Iterations: {result.iterations}")
    console.print(f"Total time: {result.total_time:.2f}s")

    if result.final_url:
        console.print(f"Final URL: {result.final_url}")

    if result.error:
        console.print(f"Error: [red]{result.error}[/red]")

    # Display stats if available
    if result.stats:
        console.print("\n[bold cyan]═══ Statistics ═══[/bold cyan]")
        console.print(f"API Calls: {result.stats['api_calls']}")
        console.print(f"Input Tokens: {result.stats['input_tokens']:,}")
        console.print(f"Output Tokens: {result.stats['output_tokens']:,}")
        console.print(f"Total Tokens: {result.stats['total_tokens']:,}")

        # Display cache stats if available
        if result.stats.get('cache_creation_tokens', 0) > 0 or result.stats.get('cache_read_tokens', 0) > 0:
            console.print(f"Cache Creation: {result.stats.get('cache_creation_tokens', 0):,} tokens")
            console.print(f"Cache Reads: {result.stats.get('cache_read_tokens', 0):,} tokens")

            # Calculate savings
            cache_read = result.stats.get('cache_read_tokens', 0)
            if cache_read > 0:
                # Cache reads are 90% cheaper (0.1x cost vs 1x)
                # So savings = cache_read * 0.9
                savings_pct = (cache_read / result.stats['input_tokens']) * 90 if result.stats['input_tokens'] > 0 else 0
                console.print(f"[green]Cache Savings: ~{savings_pct:.1f}% on input tokens[/green]")

        console.print(f"Screenshots: {result.stats['screenshots_taken']}")
        console.print(f"Actions: {result.stats['actions_executed']}")
        console.print(f"Avg API Time: {result.stats['avg_api_time']:.2f}s")

    # Display video path if recorded
    if result.video_path:
        console.print(f"\n[green]✓ Video saved: {result.video_path}[/green]")

    console.print()

    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    cli()
