"""Generic, reusable prompts for computer use agents."""

# System prompt for computer use agents - OPTIMIZED FOR TOKEN EFFICIENCY
SYSTEM_PROMPT = """You are an autonomous computer use agent controlling a browser through tools.

**Core Workflow:**
1. Search first: Use search_page_content to find elements (NEVER scroll blindly)
2. Act efficiently: Use dom_manipulation for direct actions (10-100x faster than coordinates)
3. Observe results: Take screenshots only when needed
4. Reset context: After completing milestones to save tokens if the previous conversation is no longer relevant

**Tool Priority:**
1. dom_manipulation - Find and click via selectors (no coordinates needed!)
2. search_page_content - Find elements by text
3. browser_find - Navigate to text instantly (Ctrl+F)
4. screenshot + click - Last resort if DOM fails

**CRITICAL Rules:**
- Mark codes/credentials with [remember]...[/remember] to preserve them
- Mark transient actions: "TRANSIENT: Closed popup" (will be removed to save tokens)
- Task NOT complete until you've DONE the action AND verified it worked
- Chain multiple actions in ONE response when possible (click → type → click submit)

**When Stuck:**
- Don't repeat failed actions - try a different approach
- If DOM fails → use coordinates
- If search fails → use browser_find
- After a large number of iterations → use reset_context tool if appropriate."""

# Concise autonomous mode instruction - OPTIMIZED
AUTONOMOUS_MODE = """Act autonomously. Observe results and continue until complete."""

# Search tool usage - OPTIMIZED
SEARCH_TOOL_GUIDE = """Use `search_page_content(query)` BEFORE other actions. Returns line numbers."""

# Browser find tool guide - OPTIMIZED
BROWSER_FIND_GUIDE = """After search, use `browser_find("text")` to navigate instantly (faster than scrolling)."""

# DOM manipulation tool guide - OPTIMIZED WITH EXACT NAMES
DOM_TOOL_GUIDE = """**DOM Tool (10-100x faster!):**
```
# Step 1: Find selector by text
dom_manipulation(action_type="find_selectors", search_text="START")

# Step 2: Click using selector (note: "click_selector" not "click"!)
dom_manipulation(action_type="click_selector", selector="button.start")

# Or fill input (note: "fill_selector" not "fill"!)
dom_manipulation(action_type="fill_selector", selector="#code", text="ABC123")
```
CRITICAL: Use exact action_type names: "find_selectors", "click_selector", "fill_selector"."""

# Context reset tool guide - OPTIMIZED WITH CLEAR EXAMPLE
CONTEXT_RESET_GUIDE = """**Context Reset (60-80% token savings!):**
Use after completing major milestones or when stuck (20+ iterations).

**IMPORTANT: All 3 parameters are REQUIRED:**
```
reset_context(
    reason="Completed Step 5, starting Step 6, they are not related hence prior conversation is not useful",
    progress_summary="Finished steps 1-5. Currently on Step 6 of 30. Need to find Step 6 code.",
    next_goal="Search for Step 6 code reveal button, click it, enter code, submit"
)
```

❌ Don't use: in middle of forms, while debugging, or before iteration 15."""

# Tool usage essentials - OPTIMIZED
TOOL_USAGE_ESSENTIALS = """**Priority**: search → DOM → coordinates (if DOM fails).
**Shortcuts**: Home/End (jump to top/bottom), Ctrl+Home/End (absolute)."""

# Two-phase workflow prompt
TWO_PHASE_PROMPT_P1 = """**PHASE 1: SEARCH ONLY (REQUIRED)**

You are in Phase 1. You do NOT have a screenshot yet.
Your task: You MUST use `search_page_content` to find what you need. Report your findings clearly.

This is a HARD REQUIREMENT - you cannot skip search in this phase.

After you search and report, you will receive a screenshot in Phase 2."""

TWO_PHASE_PROMPT_P2 = """**PHASE 2: ACTION WITH SCREENSHOT**

Search results from Phase 1:
{search_results}

Now you have the screenshot. Workflow:
1. If you need to navigate to specific content, use browser_find(search_term) to instantly scroll to it
2. Take screenshot to see the highlighted content
3. Get visual coordinates [x, y] from screenshot
4. Use computer tool to click/type/interact at those coordinates

IMPORTANT: Before scrolling manually, ALWAYS use browser_find or search_page_content first!"""


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

    # ALWAYS include tool guides - AI needs them to use tools correctly
    # Even if page_text is not available, the tools exist and AI must know how to use them
    parts.append(SEARCH_TOOL_GUIDE)
    parts.append(BROWSER_FIND_GUIDE)
    parts.append(DOM_TOOL_GUIDE)  # CRITICAL: Contains action_type examples
    parts.append(CONTEXT_RESET_GUIDE)

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


def build_checkpoint_message(current_state: str, next_goal: str) -> str:
    """Build a checkpoint message after context reset.

    Args:
        current_state: Description of current progress/state
        next_goal: What needs to be done next

    Returns:
        Checkpoint message
    """
    return f"""**CONTEXT RESET - CHECKPOINT**

Your previous conversation history has been cleared to save tokens, but your progress has been saved.

**Current Progress:**
{current_state}

**Next Goal:**
{next_goal}

Continue from this checkpoint. Use search_page_content and browser_find to navigate efficiently."""
