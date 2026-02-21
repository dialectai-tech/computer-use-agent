"""Memory Agent for persistent knowledge storage and retrieval.

This agent manages a persistent knowledge graph of facts discovered during
browser automation tasks (codes, selectors, form data, successful sequences).

Phase 2: MCP Memory Server integration (current)
"""

from typing import Any
from agno.agent import Agent
from agno.models.aws import AwsBedrock

from cua.utils.bedrock_mcp_tools import create_bedrock_mcp_tools


MEMORY_AGENT_INSTRUCTIONS = """
You are the **Memory Agent** for a browser automation system.

**Your Responsibilities:**
1. **Store facts** discovered during automation: codes, selectors, form data
2. **Retrieve relevant memories** when Orchestrator requests context
3. **Maintain knowledge graph** across sessions
4. **Tag memories** appropriately for efficient retrieval

**Available Tools (via Memory MCP Server):**
- store_memory(key, value, metadata): Store a fact
- retrieve_memories(query, limit): Search memories by query
- list_memories(): List all stored memories
- delete_memory(key): Remove a memory

**Memory Types:**
1. **Codes**: Alphanumeric codes (e.g., "ABC123", "XY789")
2. **Selectors**: Element selectors that worked (e.g., "input#email", "button#submit")
3. **Form Data**: Form field mappings (e.g., {"email": "user@example.com"})
4. **Successful Sequences**: Action patterns that worked

**Workflow:**
1. Orchestrator: "Store the code ABC123 we just discovered"
   - You: Use store_memory(key="code_step3", value="ABC123", metadata={"type": "code", "step": 3})
   - Return: "Stored code ABC123 for step 3"

2. Orchestrator: "What codes have we discovered so far?"
   - You: Use retrieve_memories(query="type:code")
   - Return: "Found 2 codes: ABC123 (step 3), XY789 (step 7)"

**Token Efficiency:**
- Facts stored externally in MCP server (not in conversation)
- Retrieval on-demand (only fetch relevant context)
- Replaces re-extracting facts every iteration

**Tagging Strategy:**
- Always include "type" in metadata: "code", "selector", "form_data", "sequence"
- Include context: "step", "url", "iteration"
- Use descriptive keys: "code_step3", "selector_submit_button"

IMPORTANT: Store facts efficiently and retrieve only what's relevant.
"""


def create_memory_agent(model: AwsBedrock) -> Agent:
    """Create Memory Agent with Bedrock-compatible MCP Memory Server tools.

    Phase 2: Real MCP Memory Server integration with Bedrock translation layer

    Args:
        model: Bedrock model instance (Haiku or Sonnet)

    Returns:
        Configured Memory Agent with Bedrock-compatible MCP tools
    """
    # Create Bedrock-compatible MCP tools for Memory Server
    # This wrapper translates MCP responses to Bedrock format
    memory_mcp = create_bedrock_mcp_tools(
        command="npx @modelcontextprotocol/server-memory",
        refresh_connection=True
    )

    return Agent(
        name="Memory Agent",
        model=model,
        description="Manage persistent facts via MCP Memory Server",
        instructions=MEMORY_AGENT_INSTRUCTIONS,
        tools=[memory_mcp],
        markdown=True
    )


__all__ = ["create_memory_agent", "MEMORY_AGENT_INSTRUCTIONS"]
