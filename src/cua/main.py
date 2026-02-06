"""CL I interface for Computer Use Automation."""

import os
import sys
import click
from dotenv import load_dotenv
from rich.console import Console

from cua.agent.loop import ComputerUseAgent
from cua.providers.claude import ClaudeProvider
from cua.providers.openai import OpenAIProvider

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
    type=click.Choice(["claude", "openai"], case_sensitive=False),
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
    default=lambda: int(os.getenv("DISPLAY_WIDTH", "1280")),
    help="Display width in pixels (default: 1280)"
)
@click.option(
    "--display-height",
    type=int,
    default=lambda: int(os.getenv("DISPLAY_HEIGHT", "720")),
    help="Display height in pixels (default: 720)"
)
@click.option(
    "--headless/--no-headless",
    default=True,
    help="Run browser in headless mode (default: True)"
)
def cli(
    url: str,
    prompt: str,
    provider: str,
    model: str,
    max_iterations: int,
    display_width: int,
    display_height: int,
    headless: bool
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
        headless=headless
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

    console.print()

    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    cli()
