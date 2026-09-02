"""CLI interface for Computer Use Automation."""

import os
import sys
import click
from dotenv import load_dotenv
from rich.console import Console

from cua.coordinator.step_coordinator import StepCoordinator  # default mode — always imported

# Legacy modes use agno which has a version conflict with newer mcp SDK.
# Import lazily inside the mode branch so the CLI still starts for --mode step.
def _get_legacy_coordinators():
    from cua.coordinator.agent import CoordinatorAgent
    from cua.coordinator.agno_coordinator import AgnoCoordinator
    from cua.coordinator.solo_coordinator import SoloCoordinator
    from cua.providers.bedrock import BedrockProvider
    return CoordinatorAgent, AgnoCoordinator, SoloCoordinator, BedrockProvider

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
    "--model",
    type=click.Choice(["haiku", "sonnet"], case_sensitive=False),
    default=lambda: os.getenv("BEDROCK_MODEL", "haiku"),
    help="Claude model via Bedrock: haiku (faster/cheaper) or sonnet (smarter) [default: haiku]"
)
@click.option(
    "--max-iterations",
    type=int,
    default=lambda: int(os.getenv("MAX_ITERATIONS", "30")),
    help="Maximum iterations (default: 30)"
)
@click.option(
    "--max-tool-calls",
    type=int,
    default=lambda: int(os.getenv("MAX_TOOL_CALLS", "150")),
    help="Maximum tool calls per run in efficient mode (default: 150)"
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
    default=None,
    help="Directory to save video recordings (default: test_artifacts/{session_id}/recordings)"
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
    help="Enable extended thinking (default: disabled)"
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
    help="Use accessibility tree for web automation (default: enabled)"
)
@click.option(
    "--mode",
    type=click.Choice(["step", "efficient", "agno", "classic"], case_sensitive=False),
    default="step",
    help=(
        "Agent mode: 'step' (per-step context reset, default), "
        "'efficient' (single-agent legacy), "
        "'agno' (multi-agent team), 'classic' (legacy coordinator)"
    )
)
@click.option(
    "--max-steps",
    type=int,
    default=lambda: int(os.getenv("MAX_STEPS", "40")),
    help="Maximum steps in step mode (default: 40)"
)
@click.option(
    "--use-agno/--no-agno",
    default=False,
    hidden=True,  # Legacy flag, use --mode agno instead
    help="[Legacy] Use Agno multi-agent architecture"
)
@click.option(
    "--orchestrator-model",
    type=click.Choice(["haiku", "sonnet"], case_sensitive=False),
    default=None,
    help="Model for orchestrator agent in multi-agent mode (optional, defaults to --model)"
)
@click.option(
    "--agent-model",
    type=click.Choice(["haiku", "sonnet"], case_sensitive=False),
    default=None,
    help="Model for sub-agents in multi-agent mode (optional, defaults to --model)"
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Logging level (default: INFO)"
)
def cli(
    url: str,
    prompt: str,
    model: str,
    max_iterations: int,
    max_tool_calls: int,
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
    mode: str,
    max_steps: int,
    use_agno: bool,
    orchestrator_model: str,
    agent_model: str,
    log_level: str
) -> None:
    """Computer Use Automation — AI-powered browser task automation.

    Four modes available:

    \b
    STEP (default): Per-step context reset — prevents quadratic token growth.
      - Each logical step runs in an isolated mini-conversation
      - Browser session persists; only LLM context resets
      - ~17x fewer tokens than single-agent for long tasks
      - Target: complete 30-step challenges for ~$0.50-$0.65

    \b
    EFFICIENT: Single-agent with direct Playwright MCP access (legacy).
      - All tool calls accumulate in one conversation
      - Works well for short tasks (<20 tool calls)

    \b
    AGNO: Multi-agent Agno Team (Orchestrator + Browser + Memory + Analysis).
      - More structured delegation
      - Higher API call overhead

    \b
    CLASSIC: Original CoordinatorAgent with facts tracking.
      - Legacy mode, direct Bedrock + Playwright loop

    \b
    Examples:
        # Step mode (default) — best for long tasks
        cua --url "https://example.com" --prompt "Complete all 30 steps"

        # With video recording
        cua --url "https://example.com" --prompt "Complete challenge" --record-video

        # Limit steps
        cua --url "https://example.com" --prompt "Complete task" --max-steps 10

        # Legacy efficient mode
        cua --mode efficient --url "https://example.com" --prompt "Short task"
    """
    # Display header
    console.print("\n[bold cyan]╔═══════════════════════════════════════╗[/bold cyan]")
    console.print("[bold cyan]║  Computer Use Automation (CUA)        ║[/bold cyan]")
    console.print("[bold cyan]╚═══════════════════════════════════════╝[/bold cyan]\n")

    # Handle legacy --use-agno flag
    if use_agno:
        mode = "agno"

    # Ensure URL has protocol
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
        console.print(f"[dim]Adding https:// to URL: {url}[/dim]\n")

    region = os.getenv("AWS_REGION", "us-east-1")

    # Check for AWS credentials
    has_credentials = (
        os.getenv("AWS_ACCESS_KEY_ID") or
        os.getenv("AWS_BEARER_TOKEN_BEDROCK") or
        os.getenv("AWS_SESSION_TOKEN")
    )
    if not has_credentials:
        console.print("[bold yellow]Warning: No AWS credentials found in environment[/bold yellow]")
        console.print("Bedrock will attempt to use IAM role or ~/.aws/credentials\n")

    # Choose agent mode
    if mode == "step":
        console.print(f"[dim]Mode: Step-Reset ({model}) — per-step context isolation[/dim]")
        agent = StepCoordinator(
            model=model,
            record_video=record_video,
            display_width=display_width,
            display_height=display_height,
            headless=headless,
            max_tool_calls_per_step=15,
        )

    elif mode == "efficient":
        console.print(f"[dim]Mode: Efficient Single-Agent ({model})[/dim]")
        CoordinatorAgent, AgnoCoordinator, SoloCoordinator, BedrockProvider = _get_legacy_coordinators()
        agent = SoloCoordinator(
            model=model,
            record_video=record_video,
            display_width=display_width,
            display_height=display_height,
            headless=headless,
            max_tool_calls=max_tool_calls,
        )

    elif mode == "agno":
        console.print("[dim]Mode: Agno Multi-Agent Team[/dim]")
        CoordinatorAgent, AgnoCoordinator, SoloCoordinator, BedrockProvider = _get_legacy_coordinators()

        # Map model shorthand to Bedrock model ID for BedrockProvider
        model_map = {
            "haiku": "claude-3-5-haiku-20241022-v1:0",
            "sonnet": "claude-sonnet-4-5"
        }
        bedrock_model = model_map.get(model.lower(), model)

        try:
            ai_provider = BedrockProvider(model=bedrock_model, region=region)
        except Exception as e:
            console.print(f"[bold red]Error initializing Bedrock provider: {e}[/bold red]")
            sys.exit(1)

        agent = AgnoCoordinator(
            provider=ai_provider,
            model=model,
            orchestrator_model=orchestrator_model,
            agent_model=agent_model,
            log_level=log_level.upper(),
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

    else:  # classic
        console.print("[dim]Mode: Classic Coordinator[/dim]")
        CoordinatorAgent, AgnoCoordinator, SoloCoordinator, BedrockProvider = _get_legacy_coordinators()

        model_map = {
            "haiku": "claude-3-5-haiku-20241022-v1:0",
            "sonnet": "claude-sonnet-4-5"
        }
        bedrock_model = model_map.get(model.lower(), model)

        try:
            ai_provider = BedrockProvider(model=bedrock_model, region=region)
            console.print(f"[dim]Using AWS Bedrock: {model} ({bedrock_model})[/dim]")
        except Exception as e:
            console.print(f"[bold red]Error initializing Bedrock provider: {e}[/bold red]")
            console.print("\nPlease ensure you have valid AWS credentials configured.")
            sys.exit(1)

        agent = CoordinatorAgent(
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
            track_facts=True,
        )

    # Run task
    result = agent.run_task(
        url=url,
        prompt=prompt,
        max_iterations=max_steps if mode == "step" else max_iterations,
    )

    # Display results (for modes that don't display internally)
    if mode in ("agno", "classic"):
        console.print("\n[bold cyan]═══ Results ═══[/bold cyan]")
        console.print(f"Status: {'[green]✓ Success[/green]' if result.success else '[red]✗ Failed[/red]'}")
        console.print(f"Iterations: {result.iterations}")
        console.print(f"Total time: {result.total_time:.2f}s")

        if result.final_url:
            console.print(f"Final URL: {result.final_url}")
        if result.error:
            console.print(f"Error: [red]{result.error}[/red]")

        if result.stats:
            console.print("\n[bold cyan]═══ Statistics ═══[/bold cyan]")
            console.print(f"API Calls: {result.stats.get('api_calls', 0)}")
            console.print(f"Input Tokens: {result.stats.get('input_tokens', 0):,}")
            console.print(f"Output Tokens: {result.stats.get('output_tokens', 0):,}")
            console.print(f"Total Tokens: {result.stats.get('total_tokens', 0):,}")
            console.print(f"Screenshots: {result.stats.get('screenshots_taken', 0)}")
            console.print(f"Actions: {result.stats.get('actions_executed', 0)}")

        if result.video_path:
            console.print(f"\n[green]✓ Video saved: {result.video_path}[/green]")

    console.print()
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    cli()
