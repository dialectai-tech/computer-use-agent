"""Analysis Agent for fact extraction and semantic diff computation.

This agent processes page content to extract facts, compute semantic diffs
between accessibility trees, and summarize state changes - achieving 90%+
token reduction through intelligent compression.

Phase 2: Real Python tools for processing (current)
"""

import re
from typing import Any, Dict, List
from agno.agent import Agent
from agno.models.aws import AwsBedrock
from agno.tools import Toolkit


ANALYSIS_AGENT_INSTRUCTIONS = """
You are the **Analysis Agent** for a browser automation system.

**Your Responsibilities:**
1. **Extract facts** from page content: codes, patterns, form structures
2. **Compute semantic diff** between accessibility trees (90% token reduction)
3. **Summarize page state changes** into compressed descriptions
4. **Detect completion signals**: success messages, redirects, form submissions

**Available Tools:**
- extract_facts(page_text): Extract codes, buttons, inputs from page text
- semantic_diff(old_tree, new_tree): Compute compressed diff between a11y trees
- detect_completion(page_state): Check if task is complete

**Token Efficiency Goals:**
- Semantic diff: 5000 tokens (2 trees) → 200 tokens (90% savings)
- Fact extraction: 2500 tokens (page text) → 50 tokens (98% savings)
- Compression: "3 new form fields appeared" vs. full a11y subtree

**Workflow:**
1. Orchestrator: "Analyze the page after Browser Agent clicked START"
   - Browser Agent provides: page_text, old_tree, new_tree
   - You use extract_facts(page_text) → Find codes, buttons
   - You use semantic_diff(old_tree, new_tree) → "Added: 1 modal, 3 inputs, 1 button"
   - You use detect_completion() → Check for success signals
   - Return compressed summary: "Found code ABC123 in modal. Submit button available. Task incomplete."

**Example Output:**
Input: 2500 token page text + 2500 token a11y tree
Output: "Extracted code ABC123. Page shows login form (3 inputs: username, password, code). Submit button present. No completion signal."
Compression: 5000 tokens → 50 tokens (99% reduction)

IMPORTANT: You are the compression layer. Process heavy data, return light summaries.
"""


# Analysis toolkit
class AnalysisToolkit(Toolkit):
    """Toolkit for fact extraction and semantic diff."""

    def extract_facts(self, page_text: str) -> Dict[str, Any]:
        """Extract facts from page text.

        Args:
            page_text: Full page text content

        Returns:
            Extracted facts (codes, buttons, inputs, links)
        """
        facts = {
            "codes": [],
            "buttons": [],
            "inputs": [],
            "links": [],
            "headings": []
        }

        # Extract codes (alphanumeric patterns like ABC123, XY789)
        code_pattern = r'\b[A-Z0-9]{4,10}\b'
        codes = re.findall(code_pattern, page_text)
        facts["codes"] = list(set(codes))[:10]  # Limit to 10 codes

        # Extract common button text patterns
        button_patterns = [
            r'(?:button|btn)[:\s]*([A-Za-z\s]+)',
            r'(?:click|press)[:\s]*([A-Za-z\s]+)',
            r'(submit|continue|next|start|finish|complete|done)',
        ]
        for pattern in button_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            facts["buttons"].extend(matches)

        # Extract common input field patterns
        input_patterns = [
            r'(?:input|enter|type)[:\s]*([A-Za-z\s]+)',
            r'(email|password|username|code|name|phone)',
        ]
        for pattern in input_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            facts["inputs"].extend(matches)

        # Deduplicate and clean
        facts["buttons"] = list(set([b.strip() for b in facts["buttons"] if b.strip()]))[:10]
        facts["inputs"] = list(set([i.strip() for i in facts["inputs"] if i.strip()]))[:10]

        return facts

    def semantic_diff(self, old_tree: str, new_tree: str) -> Dict[str, Any]:
        """Compute semantic diff between accessibility trees.

        Args:
            old_tree: Previous accessibility tree (as JSON string)
            new_tree: Current accessibility tree (as JSON string)

        Returns:
            Compressed diff summary
        """
        if not old_tree or not new_tree:
            return {
                "changes": "No trees provided for comparison",
                "added": [],
                "removed": []
            }

        # Simple text-based diff (counts occurrences of role keywords)
        roles = ["button", "textbox", "link", "heading", "dialog", "form", "input"]

        old_counts = {role: old_tree.lower().count(f'"{role}"') for role in roles}
        new_counts = {role: new_tree.lower().count(f'"{role}"') for role in roles}

        added = []
        removed = []

        for role in roles:
            diff = new_counts[role] - old_counts[role]
            if diff > 0:
                added.append(f"{diff} {role}(s)")
            elif diff < 0:
                removed.append(f"{abs(diff)} {role}(s)")

        changes_summary = []
        if added:
            changes_summary.append(f"Added: {', '.join(added)}")
        if removed:
            changes_summary.append(f"Removed: {', '.join(removed)}")

        return {
            "changes": "; ".join(changes_summary) if changes_summary else "No significant changes",
            "added": added,
            "removed": removed
        }

    def detect_completion(self, page_state: str) -> Dict[str, Any]:
        """Detect if task is complete based on page state.

        Args:
            page_state: Current page state description or text

        Returns:
            Completion status with reason
        """
        # Keywords indicating task completion
        completion_keywords = [
            "success", "complete", "congratulations", "done",
            "submitted", "thank you", "confirmed", "finished",
            "well done", "correct", "passed"
        ]

        page_lower = page_state.lower()
        completed = any(keyword in page_lower for keyword in completion_keywords)

        # Check for error keywords (indicates not complete)
        error_keywords = ["error", "failed", "incorrect", "wrong", "try again"]
        has_error = any(keyword in page_lower for keyword in error_keywords)

        if has_error:
            return {
                "completed": False,
                "reason": "Error detected - task not complete"
            }

        return {
            "completed": completed,
            "reason": "Completion signal detected" if completed else "No completion signal found"
        }


def create_analysis_agent(model: AwsBedrock) -> Agent:
    """Create Analysis Agent with real Python analysis tools.

    Phase 2: Full Python tools for fact extraction and semantic diff

    Args:
        model: Bedrock model instance (Haiku or Sonnet)

    Returns:
        Configured Analysis Agent with analysis tools
    """
    # Create analysis toolkit instance
    analysis_tools = AnalysisToolkit()

    return Agent(
        name="Analysis Agent",
        model=model,
        description="Extract facts and compute semantic diffs with 90%+ compression",
        instructions=ANALYSIS_AGENT_INSTRUCTIONS,
        tools=[analysis_tools],
        markdown=True
    )


__all__ = ["create_analysis_agent", "ANALYSIS_AGENT_INSTRUCTIONS", "AnalysisToolkit"]
