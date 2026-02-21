"""Memory Agent for persistent knowledge storage and retrieval.

This agent manages a persistent knowledge graph of facts discovered during
browser automation tasks (codes, selectors, form data, successful sequences).

Phase 1: Instructions only (in-memory dict for demo)
Phase 2: MCP Memory Server integration
"""

from typing import Any
from agno.agent import Agent
from agno.models.aws import AwsBedrock


MEMORY_AGENT_INSTRUCTIONS = """
You are the **Memory Agent** for a browser automation system.

**Phase 1 - Foundation Mode:**
You currently track facts conceptually. When asked to store or retrieve information,
acknowledge what you would store and how you would retrieve it.

Phase 2 will add real MCP Memory Server for persistent storage.

**Your Responsibilities (Phase 2):**
1. **Store facts**: codes, selectors, form data
2. **Retrieve relevant memories** when requested
3. **Maintain knowledge graph** across sessions
4. **Prune stale memories** for efficiency

**Memory Types:**
1. **Codes**: Alphanumeric codes (e.g., "ABC123")
2. **Selectors**: Element selectors (e.g., "input#email")
3. **Form Data**: Field mappings (e.g., {"email": "user@example.com"})
4. **Successful Sequences**: Action patterns that worked

**Example Response (Phase 1):**
Orchestrator: "Store the code ABC123"

Your Response:
"I would store:
- Key: code_1
- Value: ABC123
- Tags: [code, discovered_at_step_3]

(Phase 2 will persist this to MCP Memory Server)"

Orchestrator: "What codes did we discover?"

Your Response:
"In Phase 2, I would query the Memory Server with tags=['code'].
For now, tracking conceptually: [ABC123] from previous request."

IMPORTANT: Be concise and acknowledge Phase 1 limitations.
"""


def create_memory_agent(model: AwsBedrock) -> Agent:
    """Create Memory Agent.

    Phase 1: No tools (instructions only)
    Phase 2: Will add MCP Memory Server tools

    Args:
        model: Bedrock model instance (Haiku or Sonnet)

    Returns:
        Configured Memory Agent
    """
    return Agent(
        name="Memory Agent",
        model=model,
        description="Manage persistent facts (Phase 1: conceptual, Phase 2: MCP Server)",
        instructions=MEMORY_AGENT_INSTRUCTIONS,
        show_tool_calls=True,
        markdown=True
    )


__all__ = ["create_memory_agent", "MEMORY_AGENT_INSTRUCTIONS"]
