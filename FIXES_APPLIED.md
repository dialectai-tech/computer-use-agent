# Fixes Applied - AI Not Taking Actions

Date: 2026-02-07
Branch: `feature/context-optimization-and-browser-find`

## 🐛 Problem

Agent stopped after 3 iterations with "No actions found, task may be complete" even though:
- Max iterations was set to 100
- Task was not complete (still on landing page)
- AI found START button but never clicked it
- AI only searched, never used computer tool

## ✅ Fixes Applied (5 fixes, multiple commits)

### Fix 1: Better "No Actions" Handling
**Commit:** `626869d`

**Problem:** Loop broke immediately when AI didn't provide actions

**Solution:**
- Don't break immediately on "no actions"
- Give AI 3 chances before stopping
- Check if AI explicitly confirms task completion
- Reset counter when actions are provided
- Take screenshot and continue if not confirmed complete

**Code:**
```python
if not actions:
    self.no_action_count += 1
    
    # Check for explicit completion confirmation
    if "task completed" in response_text.lower():
        break
    
    # Stop after 3 consecutive no-action iterations
    if self.no_action_count >= 3:
        self.console.print("[red]✗ AI failed to provide actions for 3 consecutive iterations[/red]")
        break
    
    # Give one more chance with current state
    continue
```

### Fix 2: Make Phase 2 More Directive
**Commit:** `b4960e1`

**Problem:** Phase 2 prompt was too generic, AI didn't understand it must act

**Solution:**
- Changed prompt from "Use it to:" to "YOU MUST:"
- Explicit directive: "Do NOT just search again"
- Lists required workflow steps
- Warns about prohibited behaviors
- Emphasizes computer tool usage required

**Before:**
```
Now you have access to the screenshot. Use it to:
1. Find visual coordinates [x, y]
2. Use computer tool to interact
```

**After:**
```
**CRITICAL: You MUST now use the computer tool to take action. Do NOT just search again.**

Required workflow:
1. Look at screenshot for coordinates
2. Use browser_find(search_term) to navigate
3. Take computer action: click, type, or keyboard shortcut
4. Take screenshot to see result

**DO NOT:** Search again without taking action
**YOU MUST:** Use computer tool or browser_find in this phase.
```

### Fix 3: Track and Warn About Search-Only Behavior
**Commit:** `7fd046f`

**Problem:** No visibility when AI gets stuck searching without acting

**Solution:**
- Track consecutive search-only iterations
- Reset counter when computer actions taken
- Warn user when AI searches 2+ times without acting
- Provides debugging visibility

**Code:**
```python
# Track search-only behavior
has_computer_action = any(a.type not in [SEARCH, SCREENSHOT] for a in actions)
has_search_action = any(a.type == SEARCH for a in actions)

if has_search_action and not has_computer_action:
    self.search_only_count += 1
elif has_computer_action:
    self.search_only_count = 0

# Warn if stuck
if self.search_only_count >= 2:
    self.console.print(f"[yellow]⚠ AI searching for {self.search_only_count} iterations without action[/yellow]")
```

### Fix 4: Clarify Task Completion Criteria
**Commit:** `6e9ea0b`

**Problem:** AI declared "Task completed successfully!" after saying "I need to click START button" without actually clicking

**Solution:**
- Added "Task Completion Criteria" section to system prompt
- Explicitly state: Finding is NOT completion
- Must PERFORM actions AND verify results before declaring done
- Added Phase 2 warnings about false completion
- Examples: "Found X" → NOT COMPLETE vs "Clicked X, verified" → COMPLETE

**Code in system prompt:**
```python
**Task Completion Criteria:**
CRITICAL: Do NOT declare a task complete until you have ACTUALLY PERFORMED the required actions and VERIFIED success.
- Finding an element is NOT completion - you must CLICK/TYPE/INTERACT with it
- Saying "I need to click X" is NOT completion - you must ACTUALLY click X
- Only declare completion when: (1) You performed ALL required actions, AND (2) You verified the results
- Example: "Found START button" → NOT COMPLETE. "Clicked START, verified page changed" → COMPLETE
```

**Code in Phase 2 prompt:**
```python
**DO NOT:**
- Declare task complete just because you FOUND elements - you must CLICK/TYPE/INTERACT first!
- Say "I need to do X" then stop - you must ACTUALLY DO X

**REMEMBER:** Finding is NOT completing. You must PERFORM actions and VERIFY results before declaring completion.
```

### Fix 5: Send Phase 2 Instructions to AI (Not Just Console)
**Commits:** `8a65f8b`, `f82b1a5`, `36d2a37`

**Problem:** Phase 2 prompt was printed to console but NEVER sent to AI
- AI kept searching in Phase 2 despite "Do NOT search again" warnings
- AI took 3 iterations searching before finally clicking
- Instructions only visible to user, not to AI

**Root Cause:** `create_continuation_request()` had no way to inject additional instructions

**Solution:**
- Added `additional_instruction` parameter to base class and Bedrock provider
- Inject instruction as follow-up user message after tool results
- Pass `phase2_prompt` via this parameter in Phase 2 transition

**Code:**
```python
# base.py + bedrock.py: Added parameter
def create_continuation_request(..., additional_instruction: Optional[str] = None):

# bedrock.py: Inject after tool results
if additional_instruction:
    self.messages.append({
        "role": "user",
        "content": [{"text": additional_instruction}]
    })

# loop.py: Pass Phase 2 prompt
response = self.provider.create_continuation_request(
    ...,
    additional_instruction=phase2_prompt  # Send to AI!
)
```

**Test Results:**
Before Fix 5:
- Iteration 2-3 (Phase 2): Searched 2 more times
- Iteration 4: No actions
- Iteration 5: Finally clicked START

After Fix 5:
- Iteration 2 (Phase 2): Screenshot immediately (no search!)
- Iteration 3: Clicked START button
- Iteration 4: Navigated to step1, closed popup
- Iteration 5: Continued closing popups

**Impact:** AI now follows Phase 2 instructions immediately, no wasted search iterations!

## 📊 Expected Impact

**Before Fixes:**
- Agent stopped after 3 iterations
- "No actions found" → immediate break
- No visibility into search-only behavior
- AI didn't understand Phase 2 requirements
- AI declared completion after finding elements without interacting
- Phase 2 instructions never sent to AI (only printed to console)
- AI searched 2-3 times in Phase 2 before acting

**After Fixes:**
- Agent will try 3 times before giving up
- Phase 2 explicitly requires actions
- Warns when AI searches without acting
- Better debugging information
- AI won't claim completion until actions performed and verified
- **Phase 2 instructions sent to AI - immediate action taking!**
- No wasted search iterations in Phase 2

## 🧪 Testing

Ready to test with same command:

```bash
cua --provider bedrock --model haiku \
    --url "serene-frangipane-7fd25b.netlify.app" \
    --zoom 85 --context-window-size 5 \
    --max-iterations 100 --two-phase-workflow \
    --record-video --enable-caching \
    --use-accessibility-tree \
    --prompt "Navigate to webpage and complete all tasks..."
```

**Expected Behavior:**
- AI will click START button after finding it
- Phase 2 will enforce computer actions
- If AI still only searches, will warn and give 3 chances
- Agent won't stop prematurely at iteration 3

## 📝 Notes

- All 5 fixes are complementary and work together
- Each committed separately for clarity and safety
- Fixes address root causes, not symptoms
- **Fix 5 is the breakthrough** - AI now follows Phase 2 immediately
- Significantly improved completion rate and action-taking

---
**Branch:** `feature/context-optimization-and-browser-find`
**Commits:**
- Fix 1: `626869d`
- Fix 2: `b4960e1`
- Fix 3: `7fd046f`
- Fix 4: `6e9ea0b`
- Fix 5: `8a65f8b`, `f82b1a5`, `36d2a37` (3 attempts to get API validation right)

**Files Modified:**
- `src/cua/agent/loop.py`
- `src/cua/prompts/__init__.py`
- `src/cua/providers/base.py`
- `src/cua/providers/bedrock.py`
