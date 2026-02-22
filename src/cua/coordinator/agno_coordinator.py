"""Agno-based coordinator with Phase 2 MCP integration.

This coordinator wraps the Agno team with real MCP server integration,
enabling actual browser automation via Playwright MCP and persistent
memory via Memory MCP Server.
"""

import asyncio
from typing import Optional
from datetime import datetime
from rich.console import Console

from cua.providers.base import ComputerUseProvider
from cua.agent.loop import TaskResult
from cua.agno_config.models import get_bedrock_model
from cua.agno_teams.cua_team import create_cua_team
from cua.utils.token_tracker import TokenTracker
from cua.utils.structured_logger import StructuredLogger
from cua.utils.session_paths import (
    get_session_id, get_recordings_dir, get_screenshots_dir, get_snapshots_dir
)


class AgnoCoordinator:
    """Agno multi-agent coordinator with Phase 2 MCP integration.

    This coordinator:
    1. Manages MCP server lifecycle (Playwright, Memory)
    2. Creates Agno team with MCP-enabled agents
    3. Delegates tasks to the team
    4. Tracks token usage across agents
    5. Provides structured logging for background execution
    """

    def __init__(
        self,
        provider: ComputerUseProvider = None,
        model: str = "haiku",
        orchestrator_model: str = None,
        agent_model: str = None,
        log_level: str = "INFO",
        # Preserved options for compatibility
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
    ):
        """Initialize Agno coordinator with Phase 2 MCP integration.

        Args:
            provider: AI provider (preserved for compatibility, not used by Agno)
            model: Default model for all agents
            orchestrator_model: Override model for orchestrator (optional)
            agent_model: Override model for sub-agents (optional)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            (other args preserved for compatibility with existing CLI)
        """
        self.console = Console()

        # Create session ID for logging
        self.session_id = get_session_id()

        # Setup session directories
        self.recordings_dir = get_recordings_dir(self.session_id)
        self.screenshots_dir = get_screenshots_dir(self.session_id)
        self.snapshots_dir = get_snapshots_dir(self.session_id)

        # Override video_dir if not provided or if using default
        if video_dir is None or video_dir == "./recordings":
            video_dir = str(self.recordings_dir)

        self.video_dir = video_dir
        self.record_video = record_video

        # Setup structured logging
        self.logger = StructuredLogger(self.session_id, log_level)

        # Token tracking
        self.token_tracker = TokenTracker()

        # Get Bedrock models
        orchestrator_model_name = orchestrator_model or model
        agent_model_name = agent_model or model

        self.orchestrator_model = get_bedrock_model(orchestrator_model_name)
        self.agent_model = get_bedrock_model(agent_model_name)

        # Store config for team creation
        self.config = {
            "orchestrator_model": self.orchestrator_model,
            "agent_model": self.agent_model,
        }

        self.logger.log_info(
            f"Initialized Agno Coordinator (Phase 2: MCP Integration) with "
            f"orchestrator={orchestrator_model_name}, agents={agent_model_name}"
        )

        # Log session paths
        self.console.print(f"[dim]Session ID: {self.session_id}[/dim]")
        self.console.print(f"[dim]Outputs: test_artifacts/{self.session_id}/[/dim]")
        if self.record_video:
            self.console.print(f"[dim]Recording: enabled → {self.recordings_dir}[/dim]")
        else:
            self.console.print(f"[dim]Recording: disabled[/dim]")

    def run_task(
        self,
        url: str,
        prompt: str,
        max_iterations: int = 30
    ) -> TaskResult:
        """Run browser automation task using Agno team with MCP servers.

        Args:
            url: URL to navigate to
            prompt: Task description
            max_iterations: Maximum iterations (preserved for compatibility)

        Returns:
            TaskResult with execution details
        """
        self.console.print(
            "[dim]Using Agno Multi-Agent Architecture (Phase 2: MCP Integration)[/dim]"
        )

        # Build enhanced prompt with URL
        full_prompt = f"""
Navigate to: {url}

Task: {prompt}

Use the browser automation tools to complete this task.
You have access to:
- Browser Agent: Navigate, click, type, take screenshots
- Memory Agent: Store and retrieve facts (codes, selectors, form data)
- Analysis Agent: Extract facts, compute diffs, detect completion

Work step-by-step to complete the task.
"""

        # Run async task with MCP servers
        result = asyncio.run(self._run_async(full_prompt, max_iterations))

        return result

    async def _run_async(self, prompt: str, max_iterations: int) -> TaskResult:
        """Run task asynchronously using Agno team with MCP servers.

        Args:
            prompt: Full task prompt
            max_iterations: Maximum iterations

        Returns:
            TaskResult
        """
        import time
        start_time = time.time()

        try:
            # Create Agno team with MCP-enabled agents
            # Note: MCPTools in agents will handle MCP server lifecycle automatically
            self.console.print("\n[cyan]Creating Agno Team...[/cyan]")
            team = create_cua_team(
                orchestrator_model=self.config["orchestrator_model"],
                agent_model=self.config["agent_model"],
                playwright_controller=None  # Phase 2: MCP handles browser
            )

            # Log task start
            self.logger.log_agent_action(
                agent_name="AgnoCoordinator",
                action="task_start",
                details={
                    "prompt": prompt,
                    "max_iterations": max_iterations
                }
            )

            # Run Agno team
            # MCPTools will start MCP servers on first use
            self.console.print("\n[cyan]Running Agno Team...[/cyan]")
            team_result = await team.arun(prompt)

            # Extract result
            result_text = team_result if isinstance(team_result, str) else str(team_result)

            # Calculate stats
            total_time = time.time() - start_time
            total_tokens = self.token_tracker.get_total_tokens()

            # Log completion
            self.logger.log_agent_action(
                agent_name="AgnoCoordinator",
                action="task_complete",
                details={
                    "total_time": total_time,
                    "total_tokens": total_tokens,
                    "result_length": len(result_text)
                }
            )

            # Build TaskResult
            result = TaskResult(
                success=True,
                iterations=1,  # Phase 2: Single team execution
                total_time=total_time,
                final_url=None,  # TODO: Extract from browser agent
                video_path=None,  # TODO: Phase 3 will support video
                error=None,
                stats={
                    "api_calls": sum(
                        agent.api_calls
                        for agent in self.token_tracker.agent_tokens.values()
                    ),
                    "input_tokens": sum(
                        agent.input_tokens
                        for agent in self.token_tracker.agent_tokens.values()
                    ),
                    "output_tokens": sum(
                        agent.output_tokens
                        for agent in self.token_tracker.agent_tokens.values()
                    ),
                    "total_tokens": total_tokens,
                    "screenshots_taken": 0,  # TODO: Track from browser agent
                    "actions_executed": 0,  # TODO: Track from browser agent
                    "avg_api_time": total_time,
                }
            )

            return result

        except Exception as e:
            self.logger.log_error(f"Task failed", e)

            return TaskResult(
                success=False,
                iterations=0,
                total_time=time.time() - start_time,
                final_url=None,
                video_path=None,
                error=str(e),
                stats={}
            )


__all__ = ["AgnoCoordinator"]
