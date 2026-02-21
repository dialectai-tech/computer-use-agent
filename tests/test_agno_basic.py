"""Basic tests for Agno multi-agent setup.

Phase 1: Foundation tests - verify agents can be created and basic coordination works.
"""

import pytest
from cua.agno_config.models import get_bedrock_model, HAIKU_MODEL
from cua.agno_agents.orchestrator import create_orchestrator_agent
from cua.agno_agents.browser_agent import create_browser_agent
from cua.agno_agents.memory_agent import create_memory_agent
from cua.agno_agents.analysis_agent import create_analysis_agent
from cua.agno_teams.cua_team import create_cua_team
from cua.utils.token_tracker import TokenTracker


def test_get_bedrock_model():
    """Test Bedrock model creation."""
    model = get_bedrock_model("haiku")
    assert model is not None
    assert hasattr(model, "id")


def test_create_orchestrator_agent():
    """Test Orchestrator agent creation."""
    model = HAIKU_MODEL
    agent = create_orchestrator_agent(model)
    assert agent is not None
    assert agent.name == "Orchestrator"


def test_create_browser_agent():
    """Test Browser agent creation."""
    model = HAIKU_MODEL
    agent = create_browser_agent(model)
    assert agent is not None
    assert agent.name == "Browser Agent"


def test_create_memory_agent():
    """Test Memory agent creation."""
    model = HAIKU_MODEL
    agent = create_memory_agent(model)
    assert agent is not None
    assert agent.name == "Memory Agent"


def test_create_analysis_agent():
    """Test Analysis agent creation."""
    model = HAIKU_MODEL
    agent = create_analysis_agent(model)
    assert agent is not None
    assert agent.name == "Analysis Agent"


def test_create_cua_team():
    """Test CUA team creation."""
    team = create_cua_team(orchestrator_model=HAIKU_MODEL)
    assert team is not None
    assert team.name == "CUA Team"
    assert len(team.agents) == 4  # Orchestrator + 3 sub-agents


def test_token_tracker():
    """Test token tracker functionality."""
    tracker = TokenTracker()

    # Log some token usage
    tracker.log_agent_call("orchestrator", 100, 50)
    tracker.log_agent_call("browser_agent", 200, 100)

    # Check totals
    assert tracker.get_total_tokens() == 450  # 100+50+200+100

    # Check per-agent
    orchestrator_tokens = tracker.get_agent_tokens("orchestrator")
    assert orchestrator_tokens.input_tokens == 100
    assert orchestrator_tokens.output_tokens == 50

    # Test baseline comparison
    tracker.set_baseline(1000)
    comparison = tracker.compare_to_baseline()
    assert comparison["baseline"] == 1000
    assert comparison["total"] == 450
    assert comparison["savings"] == 550
    assert comparison["savings_pct"] == 55.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
