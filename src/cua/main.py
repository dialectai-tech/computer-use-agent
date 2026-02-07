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
    default=lambda: int(os.getenv("DISPLAY_HEIGHT", "768")),
    help="Display height in pixels (default: 768)"
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
    default=lambda: int(os.getenv("CONTEXT_WINDOW_SIZE", "10")),
    help="Number of recent screenshots to keep in context (default: 10)"
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
    default=True,
    help="Use accessibility tree alongside screenshots for better web automation (default: enabled)"
)
@click.option(
    "--two-phase-workflow/--no-two-phase-workflow",
    default=False,
    help="Enable two-phase workflow: search first (no screenshot), then action with screenshot (default: disabled)"
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
    two_phase_workflow: bool
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
        two_phase_workflow=two_phase_workflow
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
