# Multi-Action Support Design Document

## Overview

This document outlines the design and implementation for supporting multiple actions within a single AI response. This feature allows Claude to request multiple tool calls in parallel (e.g., search + browser_find + keyboard presses), and the system will execute all actions, capturing evidence for each, before sending a comprehensive continuation request back to the AI.

## Current State

### What Works
- ✅ **Action Extraction**: The system already extracts ALL tool uses from a single response
  ```python
  # bedrock.py line 1027-1094
  def extract_actions(self, response) -> List[Action]:
      for content_block in response['output']['message'].get('content', []):
          if 'toolUse' in content_block:
              # Extracts all tool uses into actions list
  ```

- ✅ **Action Execution Loop**: Actions are processed in a for loop
  ```python
  # loop.py line 666
  for action in actions:
      # Execute each action
  ```

- ✅ **AWS Bedrock Support**: According to AWS/Anthropic documentation, the Converse API supports multiple tool calls in a single response (parallel tool use)

### What's Missing

❌ **Multi-Action Evidence Collection**: Currently, only ONE screenshot is captured after ALL actions complete
   - Problem: If action 1 changes the page, then action 2 changes it again, we lose evidence of action 1's effect
   - Problem: The AI only sees the final state, not the intermediate states

❌ **Per-Action Tool Results**: The continuation request currently returns one tool result per tool use, but:
   - All tool results share the same screenshot (the final one)
   - No per-action page text capture
   - No intermediate screenshots for multi-step workflows

❌ **State Tracking Between Actions**: No tracking of:
   - URL changes between actions
   - Page text changes between actions
   - Visual changes between actions

## Architecture Overview

### Claude Tool Use Model (Parallel Tools)

From Anthropic documentation:

> "Claude can call multiple tools in parallel within a single response, which is useful for tasks that require multiple independent operations. When using parallel tools, all tool_use blocks are included in a single assistant message, and all corresponding tool_result blocks must be provided in the subsequent user message."

**Example Response Structure:**
```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "I'll search for the button and then navigate to it."
    },
    {
      "type": "tool_use",
      "id": "toolu_01A",
      "name": "search_page_content",
      "input": {"query": "START"}
    },
    {
      "type": "tool_use",
      "id": "toolu_01B",
      "name": "browser_find",
      "input": {"search_term": "START"}
    },
    {
      "type": "tool_use",
      "id": "toolu_01C",
      "name": "computer",
      "input": {"action": "left_click", "coordinate": [540, 400]}
    }
  ]
}
```

**Expected Continuation Request:**
```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_01A",
      "content": "📄 Found 1 match at line 10"
    },
    {
      "type": "tool_result",
      "tool_use_id": "toolu_01B",
      "content": "Browser find completed",
      "image": {"format": "png", "source": {"bytes": "<screenshot_after_browser_find>"}}
    },
    {
      "type": "tool_result",
      "tool_use_id": "toolu_01C",
      "content": "Action executed",
      "image": {"format": "png", "source": {"bytes": "<screenshot_after_click>"}}
    },
    {
      "type": "text",
      "text": "**Page Text (Current Page):**\n```\n<current_page_text>\n```"
    }
  ]
}
```

## Proposed Solution

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│ AI Response with Multiple Tool Uses                             │
│  - search_page_content(query="START")                           │
│  - browser_find(search_term="START")                            │
│  - computer(action="left_click", coordinate=[540, 400])         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Execute Actions Sequentially, Capture Evidence Per Action       │
│                                                                  │
│  Action 1: search_page_content                                  │
│    ├─ Execute search                                            │
│    ├─ Store result (text only, no screenshot needed)           │
│    └─ No page state change                                     │
│                                                                  │
│  Action 2: browser_find                                         │
│    ├─ Execute browser find (Ctrl+F)                            │
│    ├─ 📸 Capture screenshot (page scrolled to match)           │
│    ├─ 📄 Capture page text (if URL changed)                    │
│    └─ Store: screenshot_after_action_2                         │
│                                                                  │
│  Action 3: computer (click)                                     │
│    ├─ Execute click                                             │
│    ├─ 📸 Capture screenshot (after click)                       │
│    ├─ 📄 Capture page text (if URL changed)                    │
│    └─ Store: screenshot_after_action_3                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Build Continuation Request with ALL Evidence                    │
│                                                                  │
│  tool_result[0]: Search result text                             │
│  tool_result[1]: "Browser find completed" + screenshot_2        │
│  tool_result[2]: "Click completed" + screenshot_3               │
│  page_text: Final page text (global, after all actions)         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Send to AI - Claude sees ALL intermediate states                │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

#### 1. **Sequential Execution with Per-Action Evidence**

**Rationale**: While Claude makes "parallel" tool requests, we execute them **sequentially** because:
- Browser actions have dependencies (e.g., can't click until page loads)
- We need to capture state changes between actions
- The AI needs to see the effect of each action

**Implementation**:
```python
for action in actions:
    # Execute action
    result = execute_action(action)

    # Capture evidence IMMEDIATELY after this action
    if action_changes_page_state(action):
        screenshot = browser.screenshot()
        page_text = browser.get_page_text() if url_changed else None

        # Store per-action evidence
        action_evidence[action.id] = {
            "result": result,
            "screenshot": screenshot,
            "page_text": page_text,
            "url": current_url
        }
```

#### 2. **Evidence Collection Strategy**

Not all actions need screenshots. Here's the decision matrix:

| Action Type | Screenshot? | Page Text? | Rationale |
|-------------|-------------|------------|-----------|
| `search_page_content` | ❌ No | ❌ No | Text-only operation, no visual change |
| `browser_find` | ✅ Yes | ✅ If URL changed | Scrolls page, AI needs to see highlighted text |
| `computer` (click) | ✅ Yes | ✅ If URL changed | May change page, AI needs to see result |
| `computer` (type) | ✅ Yes | ❌ No | Visual change (text in field) |
| `computer` (key) | ⚠️ Conditional | ✅ If URL changed | Depends on key (Enter→Yes, Arrow→Maybe) |
| `dom_manipulation` | ✅ Yes | ✅ If URL changed | May change page state |
| `context_reset` | ❌ No | ❌ No | Meta operation |

**Optimization**: Track which actions are "visual" vs "non-visual":
```python
def requires_screenshot(action: Action) -> bool:
    """Determine if action needs screenshot evidence."""
    if action.type == ActionType.SEARCH:
        return False  # Text-only, no visual change
    elif action.type == ActionType.CONTEXT_RESET:
        return False  # Meta operation
    elif action.type == ActionType.BROWSER_FIND:
        return True  # Always need to see highlighted text
    elif action.type == ActionType.CLICK:
        return True  # May change page
    elif action.type == ActionType.TYPE:
        return True  # Visual change in input field
    elif action.type == ActionType.KEY:
        # Some keys don't change visuals (e.g., Control, Alt)
        # But most do (Enter, arrows, etc.)
        return True  # Conservative: assume visual change
    else:
        return True  # Default: capture screenshot
```

#### 3. **Continuation Request Format**

For each tool use, return a `tool_result` block in the SAME ORDER as tool uses:

```python
# bedrock.py - Revised create_continuation_request
def create_continuation_request(
    self,
    action_evidence: Dict[str, ActionEvidence],  # NEW: per-action evidence
    final_page_text: Optional[str] = None,
    ...
):
    tool_result_content = []

    # Process each tool use IN ORDER
    for tool_use in self.last_tool_uses:
        tool_id = tool_use.get('toolUseId')
        evidence = action_evidence.get(tool_id)

        if not evidence:
            # Fallback for missing evidence
            result_content = [{"text": "Action completed (no evidence captured)"}]
        else:
            result_content = build_tool_result(tool_use, evidence)

        tool_result_content.extend(result_content)

    # Add final page text ONCE at the end (not per-action)
    if final_page_text:
        tool_result_content.append({
            "text": f"\n\n**Page Text (Current Page):**\n```\n{final_page_text}\n```"
        })

    # Return as single user message
    self.messages.append({
        "role": "user",
        "content": tool_result_content
    })
```

#### 4. **Page Text Optimization**

**Problem**: Sending page text after EVERY action is wasteful (especially for non-navigation actions)

**Solution**:
- Track last URL
- Only capture page text when URL changes
- Send final page text ONCE globally (not per-action)

```python
last_url = current_url
for action in actions:
    result = execute_action(action)
    current_url = browser.current_url

    # Only capture page text on URL change
    if current_url != last_url:
        page_text = browser.get_page_text()
        action_evidence[action.id]["page_text"] = page_text
        last_url = current_url

# After all actions, get final page text
final_page_text = browser.get_page_text()
```

#### 5. **Screenshot Deduplication**

**Problem**: If 3 actions execute but page doesn't change visually, we send 3 identical screenshots

**Solution**: Hash-based deduplication (future optimization)
```python
import hashlib

def deduplicate_screenshots(action_evidence):
    """Replace duplicate screenshots with references."""
    screenshot_hashes = {}

    for action_id, evidence in action_evidence.items():
        if "screenshot" in evidence:
            screenshot = evidence["screenshot"]
            screenshot_hash = hashlib.sha256(screenshot).hexdigest()

            if screenshot_hash in screenshot_hashes:
                # Duplicate! Reference the original
                evidence["screenshot_ref"] = screenshot_hashes[screenshot_hash]
                del evidence["screenshot"]
            else:
                # First occurrence
                screenshot_hashes[screenshot_hash] = action_id
```

**Note**: This optimization can be implemented later if token costs become an issue.

## Implementation Plan

### Phase 1: Core Infrastructure (Essential)

1. **Define ActionEvidence Data Structure**
   ```python
   @dataclass
   class ActionEvidence:
       """Evidence captured after executing an action."""
       action_id: str
       action_type: ActionType
       result: Dict[str, Any]  # Action execution result
       screenshot: Optional[bytes] = None  # Screenshot after action
       page_text: Optional[str] = None  # Page text if URL changed
       url: Optional[str] = None  # URL after action
       timestamp: float = 0.0  # When action completed
   ```

2. **Modify Agent Loop to Collect Per-Action Evidence**
   - File: `src/cua/agent/loop.py`
   - Add: `action_evidence_map: Dict[str, ActionEvidence] = {}`
   - Modify: Execute action → Capture evidence → Store in map
   - After loop: Pass `action_evidence_map` to provider

3. **Modify Provider Continuation Request**
   - File: `src/cua/providers/bedrock.py`
   - Change signature: Add `action_evidence_map` parameter
   - Iterate through `last_tool_uses` in order
   - Build per-tool result blocks with corresponding evidence
   - Add final page text globally (once)

4. **Add Evidence Capture Logic**
   - Helper: `requires_screenshot(action: Action) -> bool`
   - Helper: `requires_page_text(old_url: str, new_url: str) -> bool`
   - Capture immediately after each action

### Phase 2: Optimizations (Nice-to-Have)

5. **Screenshot Deduplication**
   - Hash screenshots
   - Reference duplicates instead of sending multiple times

6. **Smart Page Text Capture**
   - Only on URL changes
   - Diff-based capture (send only changes, not full text)

7. **Evidence Pruning**
   - Drop old screenshots from history when message pruning occurs
   - Keep only last N action evidences per message turn

### Phase 3: Testing & Validation

8. **Test Scenarios**
   - Single action (verify no regression)
   - 2 actions: search + browser_find
   - 3 actions: search + browser_find + click
   - 5 actions: Complex workflow with keyboard + multiple clicks
   - Edge case: All actions are search-only (no screenshots needed)

9. **Token Impact Analysis**
   - Measure token increase for multi-action responses
   - Validate that pruning still works correctly
   - Ensure screenshot optimization doesn't break

## Data Flow Example

### Before (Current - Single Screenshot)

```
AI: [search, browser_find, click]
↓
Execute: search → browser_find → click
↓
Capture: ONE screenshot (final state only)
↓
Send: tool_result[search: text] + tool_result[browser_find: text] + tool_result[click: text] + screenshot
↓
Problem: AI can't see intermediate states!
```

### After (Proposed - Per-Action Evidence)

```
AI: [search, browser_find, click]
↓
Execute & Capture:
  - search → result_text (no screenshot)
  - browser_find → screenshot_1 (page scrolled)
  - click → screenshot_2 (after click)
↓
Send:
  - tool_result[search: text only]
  - tool_result[browser_find: text + screenshot_1]
  - tool_result[click: text + screenshot_2]
  - page_text (global, final state)
↓
Benefit: AI sees ALL intermediate states! 🎉
```

## API Compatibility

### AWS Bedrock Converse API

✅ **Confirmed Support** (from documentation):
- Multiple `tool_use` blocks in single assistant message
- Multiple `tool_result` blocks in single user message
- Each `tool_result` can contain:
  - Text content: `{"text": "..."}`
  - Image content: `{"image": {"format": "png", "source": {"bytes": b"..."}}}`
  - Multiple content blocks per result

**Example Response Structure**:
```python
{
    "role": "user",
    "content": [
        # Tool result 1: text only
        {
            "type": "tool_result",
            "tool_use_id": "toolu_01A",
            "content": [{"text": "Search result..."}]
        },
        # Tool result 2: text + image
        {
            "type": "tool_result",
            "tool_use_id": "toolu_01B",
            "content": [
                {"text": "Browser find completed"},
                {"image": {"format": "png", "source": {"bytes": b"..."}}}
            ]
        },
        # Tool result 3: text + image
        {
            "type": "tool_result",
            "tool_use_id": "toolu_01C",
            "content": [
                {"text": "Click completed"},
                {"image": {"format": "png", "source": {"bytes": b"..."}}}
            ]
        },
        # Global page text
        {"text": "**Page Text:**\n```\n...\n```"}
    ]
}
```

**Note**: AWS Bedrock API uses different field names than Anthropic API:
- Anthropic: `tool_result` with `tool_use_id`
- Bedrock: Uses `toolResult` with `toolUseId` (camelCase)

The code must use Bedrock's format since we're using the Converse API.

## Token Impact Analysis

### Current (Single Screenshot)

```
Example: 3 actions (search, browser_find, click)

Input Tokens:
- Tool definitions: ~2000 tokens
- System prompt: ~500 tokens
- Screenshot: ~1500 tokens (single screenshot after all actions)
- Page text: ~2000 tokens
- Message history: ~3000 tokens
Total: ~9000 tokens
```

### Proposed (Per-Action Screenshots)

```
Example: 3 actions (search, browser_find, click)

Input Tokens:
- Tool definitions: ~2000 tokens
- System prompt: ~500 tokens
- Screenshot 1 (browser_find): ~1500 tokens
- Screenshot 2 (click): ~1500 tokens
- Page text: ~2000 tokens (once, not per-action)
- Message history: ~3000 tokens
Total: ~11,000 tokens (+22% increase)
```

### Mitigation Strategies

1. **Screenshot Only When Needed**: Don't capture for non-visual actions (search)
2. **Deduplication**: Hash screenshots, reference duplicates
3. **Aggressive Pruning**: Drop old action evidence sooner
4. **Conditional Capture**: Flag to disable multi-action screenshots (fallback to current behavior)

### Expected Impact

- **Worst Case**: 3x actions → 3x screenshots → +200% tokens
- **Typical Case**: 3x actions → 2x visual actions → +50% tokens
- **Best Case**: 3x actions → 1x visual action → +10% tokens

**Recommendation**: Implement with CLI flag `--multi-action-evidence` (default: True)

## Configuration

Add new CLI flags to control behavior:

```python
@click.option(
    "--multi-action-evidence/--single-action-evidence",
    default=True,
    help="Capture per-action evidence (screenshots, page text) for multi-action responses (default: enabled)"
)
@click.option(
    "--max-actions-per-response",
    default=10,
    type=int,
    help="Maximum number of actions to execute in a single response (default: 10, 0 = unlimited)"
)
def cli(..., multi_action_evidence: bool, max_actions_per_response: int):
    pass
```

## Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Token explosion (3x actions → 3x screenshots) | High | Medium | Screenshot deduplication, smart capture |
| Message size exceeds API limits | High | Low | Max actions per response limit |
| Regression in single-action case | Medium | Medium | Extensive testing, feature flag |
| Increased latency (multiple screenshots) | Low | Medium | Parallel capture where possible |
| Pruning breaks with per-action evidence | High | Low | Update pruning logic to handle evidence map |

## Success Metrics

1. **Functional**:
   - ✅ AI receives screenshots for ALL visual actions
   - ✅ AI receives page text when URL changes
   - ✅ No regression in single-action responses

2. **Performance**:
   - ⬆️ Task completion rate increase (target: +10%)
   - ⬇️ Average iterations to completion (target: -20%)
   - ↔️ Token usage increase (target: <50% for typical 3-action case)

3. **Quality**:
   - ⬆️ AI makes better decisions with intermediate state visibility
   - ⬇️ Fewer "I don't see the result" messages from AI
   - ⬆️ Fewer stuck loops (AI can see progress)

## Future Enhancements

1. **Parallel Execution**: For truly independent actions (e.g., multiple searches), execute in parallel
2. **Video Evidence**: Instead of multiple screenshots, record video and send video file
3. **Diff Highlighting**: Visually highlight what changed between screenshots
4. **Smart Bundling**: Group actions that don't change state, capture once after group
5. **Streaming Evidence**: Stream screenshots to AI as actions complete (streaming API)

## References

- [AWS Bedrock Converse API - Tool Use](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use.html)
- [Anthropic Claude - Tool Use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [Anthropic Claude - Parallel Tool Use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use#parallel-tool-use)
- Current implementation: `src/cua/agent/loop.py` (line 666-730)
- Current provider: `src/cua/providers/bedrock.py` (line 710-850)

## Approval & Sign-off

- [ ] Design reviewed
- [ ] Implementation plan approved
- [ ] Test plan defined
- [ ] Token impact acceptable
- [ ] Ready to implement

---

**Document Version**: 1.0
**Created**: 2026-02-08
**Author**: Claude Sonnet 4.5
**Status**: Draft - Awaiting Review
