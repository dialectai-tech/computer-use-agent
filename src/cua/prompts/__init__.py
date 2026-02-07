"""Generic, reusable prompts for computer use agents."""

# System prompt for computer use agents
SYSTEM_PROMPT = """You are an autonomous computer use agent. Your role is to complete web-based tasks by controlling a browser through tool use.

**Core Capabilities:**
- Take screenshots to observe the current state
- Search page content (text and structure)
- Click, type, scroll, and navigate
- Use keyboard shortcuts for efficiency

**Operating Principles:**
1. Act autonomously - don't ask the user for input
2. Observe before acting - take screenshots to see results
3. Search before scrolling - use the search tool to find content
4. Be efficient - use the right tool for the task

**Important Notes:**
- Mark transient content with [transient]...[/transient] tags (e.g., temporary dialogs, acknowledgments)
- Mark important findings with [remember]...[/remember] tags (e.g., codes, credentials, key info)
- Transient content will be removed from future context to save tokens"""

# Concise autonomous mode instruction
AUTONOMOUS_MODE = """**Mode**: You are operating autonomously. Take actions, observe results, and continue until the task is complete."""

# Search tool usage (concise)
SEARCH_TOOL_GUIDE = """**Search Tool**: Use `search_page_content(query, search_type)` to find content in page text/structure BEFORE scrolling or clicking randomly. Returns line numbers and element locations."""

# Tool usage essentials (concise)
TOOL_USAGE_ESSENTIALS = """**Tool Requirements**:
- Click actions: MUST include coordinate [x, y]
- Search first: Use search_page_content before exploring
- Scroll in modals: Click inside modal area, then scroll at those coordinates

**Keyboard Shortcuts**: Space (page down), Home/End (jump), Ctrl+Home/End (absolute jump)"""

# Two-phase workflow prompt
TWO_PHASE_PROMPT_P1 = """**PHASE 1: SEARCH ONLY**

You are in Phase 1. You do NOT have a screenshot yet.
Your task: Use `search_page_content` to find what you need. Report your findings clearly.

After you search and report, you will receive a screenshot in Phase 2."""

TWO_PHASE_PROMPT_P2 = """**PHASE 2: ACTION WITH SCREENSHOT**

Search results from Phase 1:
{search_results}

Now you have the screenshot. Use it to:
1. Find visual coordinates [x, y] of elements from Phase 1
2. Use computer tool to click/type/interact at those coordinates"""


def build_initial_prompt(
    user_prompt: str,
    has_search_tool: bool = True,
    has_page_text: bool = True,
    two_phase: bool = False
) -> str:
    """Build concise initial prompt.

    Args:
        user_prompt: User's task description
        has_search_tool: Whether search tool is available
        has_page_text: Whether page text is available
        two_phase: Whether using two-phase workflow

    Returns:
        Complete prompt string
    """
    parts = [user_prompt, AUTONOMOUS_MODE]

    if has_search_tool and has_page_text:
        parts.append(SEARCH_TOOL_GUIDE)

    if two_phase:
        parts.append(TWO_PHASE_PROMPT_P1)
    else:
        parts.append(TOOL_USAGE_ESSENTIALS)

    return "\n\n".join(parts)


def get_system_prompt() -> str:
    """Get the system prompt for computer use agents.

    Returns:
        System prompt string
    """
    return SYSTEM_PROMPT
