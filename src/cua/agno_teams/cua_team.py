"""CUA Team - Agno multi-agent team for browser automation.

This module creates a coordinated team of specialized agents that work together
to solve browser automation tasks with minimal token overhead.
"""

from agno.team import Team
from agno.models.aws import AwsBedrock

from cua.agno_agents.orchestrator import create_orchestrator_agent
from cua.agno_agents.browser_agent import create_browser_agent
from cua.agno_agents.memory_agent import create_memory_agent
from cua.agno_agents.analysis_agent import create_analysis_agent


def create_cua_team(
    orchestrator_model: AwsBedrock,
    agent_model: AwsBedrock = None,
    playwright_controller: any = None
) -> Team:
    """Create CUA Team with all specialized agents.

    The team uses "coordinate" mode where the Orchestrator agent decomposes
    tasks and delegates to specialized sub-agents, then synthesizes results.

    Args:
        orchestrator_model: Model for Orchestrator agent (typically Haiku)
        agent_model: Model for sub-agents (defaults to orchestrator_model)
        playwright_controller: PlaywrightController instance (optional, for Phase 1)

    Returns:
        Configured Agno Team with all agents

    Example:
        from cua.agno_config.models import HAIKU_MODEL
        from cua.agno_teams import create_cua_team

        team = create_cua_team(orchestrator_model=HAIKU_MODEL)
        result = await team.arun("Navigate to example.com and click START button")
    """
    if agent_model is None:
        agent_model = orchestrator_model

    # Create all agents
    orchestrator = create_orchestrator_agent(orchestrator_model)
    browser_agent = create_browser_agent(agent_model, playwright_controller)
    memory_agent = create_memory_agent(agent_model)
    analysis_agent = create_analysis_agent(agent_model)

    # Create team in coordinate mode
    # Orchestrator will decompose tasks and delegate to specialists
    team = Team(
        name="CUA Team",
        agents=[orchestrator, browser_agent, memory_agent, analysis_agent],
        mode="coordinate",  # Orchestrator coordinates, delegates, and synthesizes
        show_progress=True,
        markdown=True
    )

    return team


__all__ = ["create_cua_team"]
