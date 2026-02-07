# Context Reset Feature - Implementation Status

## Branch: `feature/context-reset`

## Concept

Allow the AI agent to reset its own conversation context when it reaches milestones. This helps:
- **Save tokens**: Clear unnecessary history
- **Escape loops**: Fresh start when stuck
- **Focus attention**: Remove distracting old information
- **Speed up**: Less context to process

## Completed ✅

### 1. Context Reset Tool Definition ✅
**File**: `src/cua/tools/context_reset_tool.py`

Created comprehensive tool with:
- `ContextResetRequest` dataclass
- Request validation (prevents inappropriate resets)
- Message generation for post-reset checkpoint
- Clear documentation for AI on when/how to use

**Key features:**
- ✅ Validates reset timing (prevents mid-form resets)
- ✅ Requires meaningful progress summary
- ✅ Requires clear next goal
- ✅ Creates informative checkpoint message

### 2. Base Provider Method ✅
**File**: `src/cua/providers/base.py`

Added `reset_context()` method with signature:
```python
def reset_context(
    self,
    progress_summary: str,
    next_goal: str,
    current_screenshot: Optional[str] = None,
    current_page_info: Optional[Dict] = None
) -> bool
```

**Purpose**: Providers override this to implement context reset specific to their message format.

## Remaining Tasks 🚧

### 3. Implement Context Reset in BedrockProvider
**File**: `src/cua/providers/bedrock.py`

**What to do:**
```python
def reset_context(self, progress_summary: str, next_goal: str,
                  current_screenshot: Optional[str] = None,
                  current_page_info: Optional[Dict] = None) -> bool:
    """Reset conversation context for Bedrock Converse API."""

    if not self.messages or len(self.messages) == 0:
        return False

    # Keep ONLY the first user message (system + initial task)
    first_user_message = self.messages[0] if self.messages else None

    # Create checkpoint message
    from cua.tools.context_reset_tool import ContextResetTool
    checkpoint_msg = ContextResetTool.create_reset_message(
        ContextResetRequest(
            reason="Context reset requested",
            progress_summary=progress_summary,
            next_goal=next_goal
        ),
        current_page_info or {}
    )

    # Build new message list
    new_messages = []

    # 1. Keep first user message (system + task)
    if first_user_message:
        new_messages.append(first_user_message)

    # 2. Add checkpoint message with current state
    checkpoint_content = [{"text": checkpoint_msg}]
    if current_screenshot:
        checkpoint_content.append({
            "image": {
                "format": "png",
                "source": {"bytes": base64.b64decode(current_screenshot)}
            }
        })

    new_messages.append({
        "role": "user",
        "content": checkpoint_content
    })

    # Replace message history
    self.messages = new_messages
    self.first_user_message = first_user_message

    return True
```

### 4. Add Context Reset Tool to Provider Tool List
**File**: `src/cua/providers/bedrock.py`

In `_build_tool_config()`, add:
```python
from cua.tools.context_reset_tool import CONTEXT_RESET_TOOL_DEFINITION

tools.append(CONTEXT_RESET_TOOL_DEFINITION)
```

### 5. Handle Context Reset in Agent Loop
**File**: `src/cua/agent/loop.py`

**In action extraction:**
```python
# Check if AI requested context reset
reset_tool_uses = [
    tool for tool in tool_uses
    if tool.get('name') == 'reset_context'
]

if reset_tool_uses:
    reset_request = reset_tool_uses[0].get('input', {})

    # Validate request
    from cua.tools.context_reset_tool import ContextResetRequest, ContextResetTool
    request = ContextResetRequest(
        reason=reset_request.get('reason', ''),
        progress_summary=reset_request.get('progress_summary', ''),
        next_goal=reset_request.get('next_goal', '')
    )

    validation = ContextResetTool.validate_request(request)

    if validation['success']:
        # Get current state
        page_info = self.browser.get_page_info()
        screenshot = self.browser.take_screenshot()

        # Perform reset
        success = self.provider.reset_context(
            progress_summary=request.progress_summary,
            next_goal=request.next_goal,
            current_screenshot=screenshot,
            current_page_info=page_info
        )

        if success:
            self.console.print("[bold green]✓ Context reset successful![/bold green]")
            self.console.print(f"[dim]{request.progress_summary}[/dim]")

            # Log the reset
            self.logger.log_context_reset(iteration, request)

            # Return tool result
            return {
                "success": True,
                "message": "Context has been reset. Continue with your next goal."
            }
```

### 6. Update System Prompt
**File**: `src/cua/prompts/__init__.py`

Add section:
```
**CONTEXT RESET (Save Tokens & Escape Loops):**
When you reach a milestone or get stuck, you can reset conversation context.

**When to use:**
- ✅ Just completed a major step (e.g., submitted Step 5, now on Step 6)
- ✅ Conversation history is very long (20+ turns)
- ✅ You're stuck in a repetitive loop
- ✅ You've successfully saved data and no longer need that context

**When NOT to use:**
- ❌ In the middle of a multi-part task
- ❌ While troubleshooting an error
- ❌ Less than 10 iterations into the task

**How to use:**
Call reset_context with:
- progress_summary: "Completed steps 1-5. On Step 6 of 30."
- next_goal: "Find code for Step 6, enter it, proceed to Step 7."
- reason: "Completed Step 5 milestone, fresh start for Step 6"

**What happens:**
- All intermediate conversation history is cleared
- You get a fresh start with only: task + progress + current state
- Saves tokens, speeds up processing, escapes stuck patterns
```

## Example Usage

### Scenario: Multi-Step Challenge

**After completing Step 5:**
```python
# AI calls:
reset_context(
    reason="Successfully completed Step 5, transitioning to Step 6",
    progress_summary="Completed steps 1-5 of the browser navigation challenge. Found and entered codes for each step. Currently on Step 6 of 30.",
    next_goal="Analyze Step 6 requirements, find the required code, enter it in the input field, and proceed to Step 7."
)
```

**Result:**
- Context cleared (steps 1-5 history removed)
- Fresh start with checkpoint: "On Step 6 of 30"
- Current screenshot and page state preserved
- Ready to tackle Step 6 with clean context

## Testing Plan

### Test 1: Manual Reset After Milestone
1. Run challenge until Step 5 complete
2. AI calls reset_context with proper summary
3. Verify: message history cleared, checkpoint created
4. Continue to Step 6 with fresh context
5. Measure: token reduction, performance

### Test 2: Auto-Reset on Stuck Detection
1. Agent detects stuck pattern (3+ same actions)
2. Agent calls reset_context to escape loop
3. Verify: fresh start, different approach
4. Measure: success rate improvement

### Test 3: Token Savings
**Before reset** (at iteration 50):
- Messages: 100 items (50 turns)
- Tokens: ~500k cumulative
- Context per call: ~50k tokens

**After reset** (at iteration 51):
- Messages: 2 items (first + checkpoint)
- Tokens: ~510k cumulative (+10k only!)
- Context per call: ~15k tokens

**Savings**: 70% reduction in context size!

## Expected Impact

### Token Savings
| Scenario | Without Reset | With Reset | Savings |
|----------|---------------|------------|---------|
| 10 steps | 1M tokens | 400k tokens | 60% |
| 30 steps | 10M tokens | 2M tokens | 80% |

**Why**: Context doesn't accumulate linearly, resets every 5-10 steps

### Performance
- **Faster API calls**: Less context to process
- **Better focus**: No distraction from old steps
- **Escape loops**: Fresh perspective when stuck

### Success Rate
- **More steps completed**: Less token exhaustion
- **Better decisions**: Clear context, focused attention
- **Cost efficiency**: Same budget, more progress

## Integration Steps

1. ✅ Create tool definition and validation
2. ✅ Add base provider method
3. 🚧 Implement in BedrockProvider
4. 🚧 Add to provider tool list
5. 🚧 Handle in agent loop
6. 🚧 Update system prompts
7. 🚧 Test with challenge
8. 🚧 Measure impact

## Code Status

```bash
git log --oneline -1
f0fb255 feat: Add context reset tool and base provider method
```

**Next**: Implement in Bedrock provider and integrate into agent loop (estimated 2 hours)

---

**Note**: This feature is 30% complete. Foundation is solid, integration is straightforward.
