"""Context Reset Tool - Allow AI to reset conversation context at milestones."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ContextResetRequest:
    """Request to reset conversation context."""
    reason: str  # Why the reset is being requested
    progress_summary: str  # Summary of progress made so far
    next_goal: str  # What needs to be done next


# Tool definition for AI providers
CONTEXT_RESET_TOOL_DEFINITION = {
    "name": "reset_context",
    "description": """Reset conversation context to save tokens and get out of stuck situations.

**When to use:**
- ✅ After completing a major milestone (e.g., completed Step 5, now on Step 6)
- ✅ When conversation history is very long and slowing you down
- ✅ When you're stuck in a loop and need a fresh start
- ✅ After successfully saving/submitting data (context no longer needed)
- ✅ When transitioning between different parts of a multi-step task

**When NOT to use:**
- ❌ In the middle of filling out a form (you'll lose context!)
- ❌ While troubleshooting an error (you need the history)
- ❌ Early in the task (context is still useful)

**What gets kept:**
- System prompt and instructions
- Original user task
- Your progress summary (what you provide)
- Current screenshot and page state

**What gets cleared:**
- All previous conversation turns
- Old screenshots
- Intermediate steps that are no longer relevant

**Example workflow:**
1. Complete Step 5 successfully (code entered, submitted, moved to Step 6)
2. Call reset_context with:
   - progress_summary: "Completed steps 1-5 successfully. Now on Step 6 of 30."
   - next_goal: "Find the code for Step 6, enter it, and proceed to Step 7."
3. Context is reset, fresh start with only essential info
4. Continue with Step 6 with much cleaner context

**Benefits:**
- Saves tokens (faster, cheaper)
- Escapes stuck loops
- Focuses AI on current task
- Removes distracting old information""",
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Why you're resetting context (e.g., 'Completed Step 5, starting Step 6')"
            },
            "progress_summary": {
                "type": "string",
                "description": "Summary of what has been accomplished so far"
            },
            "next_goal": {
                "type": "string",
                "description": "What needs to be done next after the reset"
            }
        },
        "required": ["reason", "progress_summary", "next_goal"]
    }
}


class ContextResetTool:
    """Tool for resetting conversation context at milestones."""

    @staticmethod
    def validate_request(request: ContextResetRequest) -> dict:
        """Validate a context reset request.

        Args:
            request: Context reset request

        Returns:
            Dictionary with validation result
        """
        # Basic validation
        if not request.reason or len(request.reason) < 10:
            return {
                "success": False,
                "error": "Reason must be at least 10 characters"
            }

        if not request.progress_summary or len(request.progress_summary) < 20:
            return {
                "success": False,
                "error": "Progress summary must be at least 20 characters"
            }

        if not request.next_goal or len(request.next_goal) < 10:
            return {
                "success": False,
                "error": "Next goal must be at least 10 characters"
            }

        # Check for keywords that suggest bad timing
        bad_keywords = ["in the middle", "half way", "not finished", "incomplete"]
        reason_lower = request.reason.lower()

        for keyword in bad_keywords:
            if keyword in reason_lower:
                return {
                    "success": False,
                    "error": f"Context reset may not be appropriate: reason contains '{keyword}'"
                }

        return {
            "success": True,
            "request": request
        }

    @staticmethod
    def create_reset_message(request: ContextResetRequest, current_state: dict) -> str:
        """Create a message for the user after context reset.

        Args:
            request: Context reset request
            current_state: Current page state (URL, screenshot description, etc.)

        Returns:
            Message string to inject after reset
        """
        message = f"""
╔══════════════════════════════════════════════════════════════╗
║  CONTEXT RESET - FRESH START                                ║
╚══════════════════════════════════════════════════════════════╝

**Reason for Reset:**
{request.reason}

**Progress Made So Far:**
{request.progress_summary}

**Current State:**
- URL: {current_state.get('url', 'Unknown')}
- Page: {current_state.get('title', 'Unknown')}

**Next Goal:**
{request.next_goal}

**Instructions:**
Continue from this checkpoint with a fresh perspective. All previous conversation
history has been cleared to save tokens and focus your attention.

Use your tools to observe the current state and proceed with the next goal.
"""
        return message
