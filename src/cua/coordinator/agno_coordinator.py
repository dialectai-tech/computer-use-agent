"""Agno-based coordinator that integrates multi-agent team with existing CLI.

This coordinator wraps the Agno team and provides compatibility with the
existing main.py CLI interface while enabling token-efficient multi-agent
architecture.
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


class AgnoCoordinator:
    """Agno multi-agent coordinator for browser automation.

    This coordinator:
    1. Creates Agno team with specialized agents
    2. Delegates tasks to the team
    3. Tracks token usage across agents
    4. Provides structured logging for background execution
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
        """Initialize Agno coordinator.

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
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Setup structured logging
        self.logger = StructuredLogger(self.session_id, log_level)

        # Token tracking
        self.token_tracker = TokenTracker()

        # Get Bedrock models
        orchestrator_model_name = orchestrator_model or model
        agent_model_name = agent_model or model

        self.orchestrator_model = get_bedrock_model(orchestrator_model_name)
        self.agent_model = get_bedrock_model(agent_model_name)

        # Create Agno team
        self.team = create_cua_team(
            orchestrator_model=self.orchestrator_model,
            agent_model=self.agent_model,
            playwright_controller=None  # Phase 1: Will integrate in Phase 2
        )

        self.logger.log_info(
            f"Initialized Agno Coordinator with orchestrator={orchestrator_model_name}, "
            f"agents={agent_model_name}"
        )

    def run_task(
        self,
        url: str,
        prompt: str,
        max_iterations: int = 30
    ) -> TaskResult:
        """Run browser automation task using Agno team.

        Args:
            url: URL to navigate to
            prompt: Task description
            max_iterations: Maximum iterations (preserved for compatibility)

        Returns:
            TaskResult with execution details
        """
        self.console.print(
            "[dim]Using Agno Multi-Agent Architecture (Phase 1: Foundation)[/dim]"
        )

        # Build enhanced prompt with URL
        full_prompt = f"""
Navigate to: {url}

Task: {prompt}

Execute this task using the browser automation system.
"""

        # Run async task
        result = asyncio.run(self._run_async(full_prompt, max_iterations))

        return result

    async def _run_async(self, prompt: str, max_iterations: int) -> TaskResult:
        """Run task asynchronously using Agno team.

        Args:
            prompt: Full task prompt
            max_iterations: Maximum iterations

        Returns:
            TaskResult
        """
        import time
        start_time = time.time()

        try:
            # Log task start
            self.logger.log_agent_action(
                agent_name="AgnoCoordinator",
                action="task_start",
                details={"prompt": prompt, "max_iterations": max_iterations}
            )

            # Run Agno team (Phase 1: Basic implementation)
            # Note: In Phase 1, tools are placeholders. Phase 2 will add real browser control.
            team_result = await self.team.arun(prompt)

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
                iterations=1,  # Phase 1: Single team execution
                total_time=total_time,
                final_url=None,  # Phase 2: Will extract from browser agent
                video_path=None,  # Phase 2: Will support video
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
                    "screenshots_taken": 0,  # Phase 2
                    "actions_executed": 0,  # Phase 2
                    "avg_api_time": total_time,  # Simplified for Phase 1
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
