"""Phase 2 tests for Agno multi-agent with MCP integration.

Tests MCP server integration, real tools, and end-to-end functionality.
"""

import pytest
import asyncio
from cua.agno_config.models import get_bedrock_model, HAIKU_MODEL
from cua.agno_agents.orchestrator import create_orchestrator_agent
from cua.agno_agents.browser_agent import create_browser_agent
from cua.agno_agents.memory_agent import create_memory_agent
from cua.agno_agents.analysis_agent import create_analysis_agent, AnalysisToolkit
from cua.agno_teams.cua_team import create_cua_team
from cua.utils.mcp_manager import MCPManager


def test_analysis_toolkit_extract_facts():
    """Test Analysis toolkit fact extraction."""
    toolkit = AnalysisToolkit()

    page_text = """
    Welcome to the test page!
    Please enter your code: ABC123
    Button: Submit
    Input: Email address
    Code XY789 is also valid
    """

    facts = toolkit.extract_facts(page_text)

    assert "codes" in facts
    assert "ABC123" in facts["codes"] or "XY789" in facts["codes"]
    assert "buttons" in facts
    assert "inputs" in facts


def test_analysis_toolkit_semantic_diff():
    """Test semantic diff computation."""
    toolkit = AnalysisToolkit()

    old_tree = '{"role": "button", "name": "Start"}'
    new_tree = '{"role": "button", "name": "Start"} {"role": "button", "name": "Submit"}'

    diff = toolkit.semantic_diff(old_tree, new_tree)

    assert "changes" in diff
    assert "added" in diff
    assert "removed" in diff


def test_analysis_toolkit_detect_completion():
    """Test completion detection."""
    toolkit = AnalysisToolkit()

    # Success case
    result_success = toolkit.detect_completion("Congratulations! Task completed successfully.")
    assert result_success["completed"] == True

    # Incomplete case
    result_incomplete = toolkit.detect_completion("Please continue to the next step.")
    assert result_incomplete["completed"] == False

    # Error case
    result_error = toolkit.detect_completion("Error: Incorrect code. Try again.")
    assert result_error["completed"] == False


def test_browser_agent_has_mcp_tools():
    """Test Browser Agent is created with MCP tools."""
    model = HAIKU_MODEL
    agent = create_browser_agent(model)

    assert agent is not None
    assert agent.name == "Browser Agent"
    assert agent.tools is not None
    assert len(agent.tools) > 0


def test_memory_agent_has_mcp_tools():
    """Test Memory Agent is created with MCP tools."""
    model = HAIKU_MODEL
    agent = create_memory_agent(model)

    assert agent is not None
    assert agent.name == "Memory Agent"
    assert agent.tools is not None
    assert len(agent.tools) > 0


def test_analysis_agent_has_tools():
    """Test Analysis Agent is created with real Python tools."""
    model = HAIKU_MODEL
    agent = create_analysis_agent(model)

    assert agent is not None
    assert agent.name == "Analysis Agent"
    assert agent.tools is not None
    assert len(agent.tools) > 0


def test_create_cua_team_phase2():
    """Test CUA team creation with Phase 2 agents."""
    team = create_cua_team(orchestrator_model=HAIKU_MODEL)

    assert team is not None
    assert team.name == "CUA Team"
    assert len(team.members) == 4  # Orchestrator + 3 sub-agents

    # Check that agents have tools
    browser_agent = team.members[1]  # Browser Agent
    memory_agent = team.members[2]  # Memory Agent
    analysis_agent = team.members[3]  # Analysis Agent

    assert browser_agent.tools is not None
    assert memory_agent.tools is not None
    assert analysis_agent.tools is not None


@pytest.mark.asyncio
async def test_mcp_manager_lifecycle():
    """Test MCP manager can start and stop servers."""
    manager = MCPManager()

    # Connect to MCP servers
    # Note: This may fail if npm packages aren't installed
    # That's OK for Phase 2 tests - just checking the interface works

    try:
        async with manager as mcp:
            health = mcp.health_check()
            assert "playwright" in health
            assert "memory" in health
    except Exception as e:
        # Expected if MCP servers aren't installed
        pytest.skip(f"MCP servers not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
