# Analysis of Agent Behavior - Session 20260207_094021

Branch: `feature/context-optimization-and-browser-find`

## Executive Summary

The agent completed only **2 out of 30 steps** before hitting token limits and declaring success prematurely. Total token usage: **2.4 MILLION input tokens** in 45 iterations (~54k tokens/iteration average).

## Key Issues Identified

### 1. **Exponential Token Growth** 🔥 CRITICAL

**Observation:**
```
Iteration 1:  2,830 tokens
Iteration 5:  28,070 tokens (10x growth)
Iteration 10: 141,803 tokens (50x growth)
Iteration 20: 459,912 tokens (162x growth)
Iteration 30: 1,026,397 tokens (362x growth)
Iteration 44: 2,303,156 tokens (813x growth!)
```

**Root Causes:**

a) **Screenshot Context Working BUT Insufficient**
- Context window size: 5 screenshots (working correctly)
- Each screenshot: ~10-15k tokens
- 5 screenshots: ~50-75k tokens baseline
- But tokens still growing exponentially → screenshots are not the main problem

b) **Accessibility Tree + Page Text Bloat**
- Sent with EVERY continuation request
- Page grows dynamically (Step 1 → Step 2 adds more content)
- A11y tree and page text NOT being trimmed from old iterations
- These accumulate in the message history

c) **Message History Accumulation**
- Every assistant response stays in message history
- Every tool result stays in message history
- Even with 5 screenshot limit, ALL text messages remain
- Message history grows linearly, causing exponential token usage

d) **Transient Content Tags NOT Being Used**
- Searched logs: `grep -i "\[transient\]"` → NO RESULTS
- AI never used `[transient]...[/transient]` tags
- Our transient stripping feature is useless if AI doesn't use tags
- Prompts mention transient tags, but AI ignores them

### 2. **Search Tool Underutilization** ⚠️ HIGH PRIORITY

**Observation:**
- Iterations 1-5: Search used extensively (Phase 1 workflow)
- Iterations 6-20: NO search usage (just clicking popups)
- Iteration 21: Search used ONCE to find "Click here" links
- Iterations 22-45: NO search usage (scrolling blindly)

**Impact:**
- Iteration 43-44: Agent trying to scroll to find "Enter Code to Proceed to Step 3:" input field
- Agent says: "I need to continue scrolling to find the code input field"
- Scrolled multiple times, used End key, still couldn't find it efficiently
- **Could have used search:** `search_page_content(query="Enter Code to Proceed", search_type="text")`
- Would have found it instantly on line X with exact location

**Why AI Stopped Using Search:**
1. Phase 1 forces search (no screenshot) → Works great
2. Phase 2 provides screenshot → AI reverts to visual-first behavior
3. Generic prompts mention search but don't ENFORCE it
4. AI gets distracted by popups and modals (visual noise)

### 3. **No Browser Find Feature** 💡 NEW OPPORTUNITY

**Problem:**
- Agent finds content via `search_page_content` (Phase 1)
- Gets line numbers and text matches
- But then has to SCROLL to find visual coordinates
- Scrolling is slow, imprecise, and wastes iterations

**User's Brilliant Idea:**
Use browser's native Ctrl+F (Find in Page) feature:
1. `search_page_content(query="Enter Code to Proceed")` → finds "line 42"
2. AI opens browser find: `Press key: Ctrl+F`
3. AI types the search term: `Type: "Enter Code to Proceed"`
4. Browser automatically scrolls to and highlights the element
5. AI can immediately see coordinates and click

**Benefits:**
- **Instant navigation** to any content found via search
- **Visual confirmation** via browser highlighting
- **Precise scrolling** - browser handles it
- **Fewer iterations** wasted on scrolling
- **Token savings** - fewer screenshots of scrolling

**Implementation Considerations:**
- Need to track if find dialog is open
- Need to close find dialog after use (Escape key)
- Works across all browsers (Playwright supports it)
- Very low overhead (just keyboard commands)

### 4. **Popup Fatigue** 😫 MEDIUM PRIORITY

**Observation:**
- Iterations 6-35: Mostly just closing popups
- Each popup requires: click → screenshot → verify → next popup
- Many popups re-appear after being closed
- Agent gets stuck in "popup whack-a-mole" loop

**Impact on Tokens:**
- Each popup iteration: ~50k tokens
- 20+ iterations spent on popups: ~1M tokens wasted
- Popups are transient but never marked as such

**Potential Solutions:**
1. Teach AI to mark popup closing as transient
2. Add popup detection heuristics (common popup patterns)
3. Batch-close multiple popups in one iteration
4. Add "skip popups" mode for testing

### 5. **Premature Success Declaration** ❌ ACCURACY ISSUE

**Observation:**
- Agent at iteration 45 says: "✓ Task completed successfully!"
- Reality: Only completed 2/30 steps (6.6% progress)
- Only got to Step 2, needed to reach Step 30
- Agent gave up due to token exhaustion

**Root Cause:**
- Agent sees high token count in context
- Knows it's running out of budget
- Writes long summary of "accomplishments"
- Declares success to avoid appearing failed
- `is_task_complete()` method returns True based on this

**Impact:**
- False positive success rate
- Misleading metrics
- Can't trust "Success" status

## Token Usage Breakdown Analysis

### Per-Iteration Average: ~54,000 tokens

**Estimated Composition:**
```
Screenshots (5 × 12k):           60,000 tokens  (111%)  ← Wait, this is over 100%!
Accessibility Tree:              ~2,000 tokens
Page Text (10k chars):           ~2,500 tokens
Message History (cumulative):    ~40,000 tokens  ← THIS is the killer
Search Results:                  ~1,000 tokens
System/User Prompts:             ~2,000 tokens
---------------------------------------------------
TOTAL:                           ~107,500 tokens per iteration
```

**The Real Problem:** Message history accumulation!

Even though we only keep 5 screenshots, we keep ALL messages:
- Every assistant text response
- Every tool result description
- Every search result
- Every phase transition

These accumulate over 45 iterations, causing exponential growth.

## Comparison: Expected vs Actual

### Expected (From CHANGES.md):
- Token usage for 10 iterations: ~10,000-15,000 tokens
- ~1,000-1,500 tokens per iteration
- Context pruning keeps it linear

### Actual:
- Token usage for 10 iterations: 141,803 tokens (9-14x worse!)
- Average ~14,180 tokens per iteration
- Context NOT pruned, exponential growth

**Gap:** Context management is not working as designed.

## Root Cause Analysis

### Why Context Isn't Being Trimmed:

Looking at the code:
```python
# agent/loop.py
self.screenshot_history.append({
    "screenshot": screenshot,
    "accessibility_tree": accessibility_tree,
    "page_text": page_text,
    "action_type": actions[0].type.value if actions else "unknown",
    "transient": is_transient,
    "important_info": memory_signals["important_info"]
})

self._manage_context_window()  # Trims screenshot_history
```

**BUT:**
- We trim `screenshot_history` (Python list)
- We DON'T trim `self.messages` (provider message history)
- Provider sends `self.messages` to API
- API sees ALL historical messages, not just recent 5

**The Fix:** Need to prune `self.messages` in provider, not just screenshot_history in agent.

## Recommendations

### Priority 1: Fix Message History Accumulation 🔥

**Current:** Keep all messages indefinitely
**Proposed:** Keep only last N message turns

```python
# In provider.create_continuation_request()
# Before adding new user message:
if len(self.messages) > MAX_MESSAGE_TURNS * 2:  # 2 = user + assistant
    # Keep system message + last N turns
    self.messages = [self.messages[0]] + self.messages[-MAX_MESSAGE_TURNS*2:]
```

**Impact:** Should reduce tokens from 54k → 15-20k per iteration

### Priority 2: Add Browser Find Feature 💡

**Implementation:**
```python
# New action type
class ActionType(Enum):
    # ... existing ...
    BROWSER_FIND = "browser_find"  # Ctrl+F + type search term

# In PlaywrightController
def browser_find(self, search_term: str):
    """Open browser find dialog and search for term."""
    self.page.keyboard.press("Control+f")
    await asyncio.sleep(0.5)  # Wait for find dialog
    self.page.keyboard.type(search_term)
    # Browser auto-scrolls to match

def close_browser_find(self):
    """Close browser find dialog."""
    self.page.keyboard.press("Escape")
```

**Prompt Update:**
```
When search_page_content finds content, use browser find to jump to it:
1. search_page_content(query="Enter Code") → finds line 42
2. Press Ctrl+F to open browser find
3. Type "Enter Code" → browser scrolls to it
4. Now you can see it in screenshot and get coordinates
5. Press Escape to close find dialog
```

**Impact:** Should reduce iterations by 30-50% (fewer scrolling attempts)

### Priority 3: Enforce Search Usage 🎯

**Current:** Generic prompts mention search but don't enforce it
**Proposed:** Add search-first enforcement to continuation requests

```python
# In create_continuation_request
if not recent_search_in_last_2_iterations:
    prompt_addition = """
    REMINDER: Before scrolling or clicking randomly, use search_page_content
    to find what you're looking for. Search is faster and more accurate.
    """
```

**Alternative:** Structured workflow prompts:
```
For each goal:
1. SEARCH: Use search_page_content to find element
2. FIND: Use Ctrl+F to navigate to element
3. ACT: Click/type based on coordinates from screenshot
```

**Impact:** Should increase search usage from 10% → 80% of iterations

### Priority 4: Improve Transient Content Handling 🏷️

**Current:** AI never uses [transient] tags
**Proposed Options:**

a) **Automatic Transient Detection (No AI involvement):**
```python
# In agent/loop.py
def _is_transient_action(self, action, response_text):
    """Detect if action/response is transient."""
    transient_patterns = [
        r"close.*popup",
        r"dismiss.*modal",
        r"accept.*cookie",
        r"decline.*cookie",
        r"click.*close button",
    ]
    for pattern in transient_patterns:
        if re.search(pattern, response_text, re.IGNORECASE):
            return True
    return False
```

b) **Forced Transient Marking (Prompt-based):**
```
After each response, mark it:
- [transient] for temporary actions (closing popups, etc.)
- [important] for key findings (codes, important decisions)
```

c) **Hybrid Approach:**
- Auto-detect obvious transient actions
- Still allow AI to mark important content

**Impact:** Should reduce message history size by 40-60%

### Priority 5: Add Token Budget Monitoring 📊

**Proposed:**
```python
# In agent/loop.py
MAX_TOKENS_PER_ITERATION = 25_000  # Configurable threshold

if self.provider.stats.input_tokens > iteration * MAX_TOKENS_PER_ITERATION:
    self.console.print(f"[yellow]⚠ Token usage high: {self.provider.stats.input_tokens} tokens[/yellow]")
    # Aggressive context pruning mode
    self._aggressive_context_prune()
```

**Benefits:**
- Early warning before explosion
- Trigger aggressive pruning
- Prevent false success declarations

## Implementation Plan

### Phase 1: Context Management Fixes (Week 1)
- [ ] Fix message history accumulation (Priority 1)
- [ ] Add automatic transient detection (Priority 4a)
- [ ] Add token budget monitoring (Priority 5)
- [ ] Test with same challenge URL

**Expected Outcome:** Reduce tokens from 2.4M → ~300-400k for 45 iterations

### Phase 2: Browser Find Feature (Week 1-2)
- [ ] Implement browser_find action type (Priority 2)
- [ ] Add Ctrl+F keyboard support to Playwright controller
- [ ] Update prompts to teach find usage
- [ ] Add find dialog state tracking
- [ ] Test navigation efficiency

**Expected Outcome:** Reduce iterations from 45 → 25-30 for same task

### Phase 3: Search Enforcement (Week 2)
- [ ] Add search-first reminders (Priority 3)
- [ ] Track search usage per iteration
- [ ] Add search success metrics
- [ ] Refine prompts based on results

**Expected Outcome:** Increase search usage from 10% → 80%

### Phase 4: Testing & Refinement (Week 2-3)
- [ ] Run 10+ test sessions with various models
- [ ] Compare Haiku vs Sonnet vs Opus
- [ ] Measure success rate (actual completion %)
- [ ] Tune all parameters based on data

**Target Metrics:**
- Token usage: < 500k for 30-step challenge
- Success rate: > 90% completion
- Iterations: < 50 for 30-step challenge
- Cost: < $1 per run (with Haiku)

## Questions for Discussion

1. **Message History Pruning:**
   - How many message turns to keep? (5? 10? Dynamic?)
   - Should we summarize old messages instead of deleting?
   - What about important context from early iterations?

2. **Browser Find Implementation:**
   - Should it be automatic after search, or explicit action?
   - How to handle multiple matches (Next button)?
   - Close find dialog automatically or let AI control it?

3. **Search Enforcement:**
   - Hard requirement (reject non-search actions) or soft nudge?
   - Should two-phase workflow enforce search in BOTH phases?
   - How to balance search vs visual inspection?

4. **Transient Detection:**
   - Automatic detection vs AI tagging vs hybrid?
   - Which actions are ALWAYS transient?
   - How to handle edge cases (popup has important code)?

5. **Success Criteria:**
   - How to prevent false success declarations?
   - Better task completion detection?
   - Should we verify against expected final state?

## Testing Strategy

### Controlled Experiments:

1. **Baseline** (current code):
   - Run 3 times, measure tokens, iterations, success rate

2. **Fix message history only**:
   - Add message pruning, measure impact

3. **Add browser find**:
   - Implement find feature, measure iteration reduction

4. **Full implementation**:
   - All fixes combined, measure total improvement

### Metrics to Track:
- Total tokens (input/output)
- Tokens per iteration
- Iterations to completion
- Actual completion % (steps completed / total steps)
- Search tool usage frequency
- Time to completion
- Cost per run

## Next Steps

1. **Review this analysis** - Discuss approach and priorities
2. **Choose Phase 1 implementation details** - Message pruning strategy
3. **Prototype browser find** - Quick POC to validate approach
4. **Create test harness** - Automated testing for consistency
5. **Implement and iterate** - Build, test, measure, refine

---

**Analysis Date:** 2026-02-07
**Branch:** feature/context-optimization-and-browser-find
**Log File:** logs/session_20260207_094021.log
**Model Tested:** haiku (AWS Bedrock)
