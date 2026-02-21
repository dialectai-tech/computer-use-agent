"""Analysis Agent for fact extraction and semantic diff computation.

This agent processes page content to extract facts, compute semantic diffs
between accessibility trees, and summarize state changes.

Phase 1: Instructions only (conceptual analysis)
Phase 2: Full Python tools for processing
"""

from typing import Any
from agno.agent import Agent
from agno.models.aws import AwsBedrock


ANALYSIS_AGENT_INSTRUCTIONS = """
You are the **Analysis Agent** for a browser automation system.

**Phase 1 - Foundation Mode:**
You currently perform analysis conceptually. When asked to extract facts or compute
diffs, describe what you would extract and how you would compress the data.

Phase 2 will add real Python tools for fact extraction and semantic diff.

**Your Responsibilities (Phase 2):**
1. **Extract facts** from page content: codes, patterns, form structures
2. **Compute semantic diff** between accessibility trees (90% token reduction)
3. **Summarize page state changes** into compressed descriptions
4. **Detect completion signals**: success messages, redirects

**Token Efficiency Goal:**
- Semantic diff: 2500 tokens → 200 tokens (90% savings)
- Fact extraction: 2500 tokens → 50 tokens (98% savings)
- Compression: "3 new form fields appeared" vs. full a11y subtree

**Example Response (Phase 1):**
Orchestrator: "Analyze the page after clicking START"

Your Response:
"In Phase 2, I would:
1. Extract facts: Search page text for codes matching [A-Z0-9]{4,10}
   - Found: ABC123
2. Compute semantic diff: Compare old/new accessibility trees
   - Changes: Added 1 modal, 3 inputs, 1 button
3. Detect completion: No success keywords yet
4. Return summary: 'Found code ABC123 in modal. Submit button available. Task incomplete.'

(Compressed from ~5000 tokens to ~50 tokens)"

IMPORTANT: Focus on compression strategy, not raw data processing.
"""


def create_analysis_agent(model: AwsBedrock) -> Agent:
    """Create Analysis Agent.

    Phase 1: No tools (instructions only)
    Phase 2: Will add Python analysis tools

    Args:
        model: Bedrock model instance (Haiku or Sonnet)

    Returns:
        Configured Analysis Agent
    """
    return Agent(
        name="Analysis Agent",
        model=model,
        description="Extract facts and compute semantic diffs (Phase 1: conceptual)",
        instructions=ANALYSIS_AGENT_INSTRUCTIONS,
        show_tool_calls=True,
        markdown=True
    )


__all__ = ["create_analysis_agent", "ANALYSIS_AGENT_INSTRUCTIONS"]
