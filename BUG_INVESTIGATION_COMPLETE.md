# Complete Bug Investigation - Token Growth Issues

Date: 2026-02-07
Status: Investigation Complete - Ready for Fixes

---

## Executive Summary

Found TWO critical bugs causing exponential token growth:

1. **Page text sent every iteration** (should only send once)
2. **Message history pruning LIKELY not working** (AI responses accumulating)

---

## Bug #1: Page Text Sent Every Iteration ✅ CONFIRMED

### Evidence from Test Output
```
Iteration 1: 19 tokens (landing page)
Iteration 2: 38 tokens (+19)
Iteration 7: 1,278 tokens (+1,164) ← Agent navigated to Step 1
Iteration 8: 4,716 tokens (+3,438) ← More popups/content appeared
```

### Root Cause

**File:** `src/cua/agent/loop.py`

**Line 764:** Page text fetched EVERY iteration
```python
page_text = self.browser.get_page_text()  # ← Fetched every time!
```

**Line 892:** Page text sent EVERY iteration
```python
response = self.provider.create_continuation_request(
    screenshot=screenshot,
    page_text=page_text if self.use_page_text else None,  # ← Sent every time!
    ...
)
```

### The Optimization That Never Happened

**File:** `src/cua/providers/bedrock.py` (lines 564-567)

```python
# OPTIMIZATION: Do NOT send page text with every action
# Page text is already available to AI via search_page_content
# Only send it with initial request or after page loads
# This saves ~2,500 tokens per action!
```

**Comment exists, but optimization NOT IMPLEMENTED!**

### Impact

- Iteration 1-6: Wastes 19-114 tokens per iteration (~500 tokens total)
- Iteration 7+: Wastes 1,278-4,716 tokens per iteration (HUGE!)
- By iteration 30: Wastes ~4,000 tokens/iteration = 120,000 tokens cumulative
- **Cost:** ~$3-30 per test run depending on model

### Fix Required

Only send page_text on iteration 1:

```python
# In loop.py
if iteration == 0:  # First iteration only
    page_text = self.browser.get_page_text()
else:
    page_text = None

response = self.provider.create_continuation_request(
    page_text=page_text,
    ...
)
```

---

## Bug #2: Message History Pruning Not Working ⚠️ LIKELY ISSUE

### Evidence from Test Output
```
Iteration 1: AI Responses: 3,504 tokens
Iteration 10: AI Responses: 40,745 tokens (expected: ~9,000)
Iteration 20: AI Responses: 94,655 tokens (expected: ~9,000)
Iteration 27: AI Responses: 132,914 tokens (expected: ~9,000)
```

With `max_message_turns=3`, AI response history should be capped at ~9,000 tokens.
**Actual: Growing linearly without bound!**

### The Pruning Logic

**File:** `src/cua/providers/bedrock.py` (line 181-244)

The `_prune_message_history()` method exists and is called (line 527), but it's not working.

**Logic:**
1. Keep first_user_message (iteration 1: prompt + screenshot + page text)
2. Keep last N complete cycles (N = max_message_turns = 3)
3. Keep pending assistant message (waiting for tool results)

**Expected after iteration 10:**
- 1 first message (~1,500 tokens)
- 6 messages for 3 cycles (~6,000 tokens)
- 1 pending assistant (~2,000 tokens)
- **Total: ~9,500 tokens**

**Actual after iteration 10:**
- **40,745 tokens** (4x expected!)

### Possible Root Causes

**Hypothesis A: first_user_message is a reference, not a copy**
```python
# Line 382
self.first_user_message = self.messages[0]  # ← Reference or copy?
```

If it's a reference, modifications to messages[0] would affect first_user_message.

**Hypothesis B: Message structure doesn't alternate as expected**
The pruning logic expects: user → assistant → user → assistant → ...

Maybe there are extra messages being inserted that break this pattern.

**Hypothesis C: Pruning is called but messages are re-added**
Order of operations in `create_continuation_request`:
1. Line 527: Prune messages
2. Line 631: Append new user message (tool results)
3. Line 767: Append assistant response

If pruning happens before the new messages are added, it might not be effective.

**Hypothesis D: Cycle detection is broken**
The backward traversal logic might not be correctly identifying cycles.

### Investigation Needed

Add debug logging to understand what's happening:

```python
def _prune_message_history(self):
    print(f"[DEBUG] Before pruning: {len(self.messages)} messages")
    print(f"[DEBUG] min_messages threshold: {1 + (self.max_message_turns * 2)}")

    # ... existing logic ...

    print(f"[DEBUG] After pruning: {len(self.messages)} messages")
    print(f"[DEBUG] Cycles found: {cycles_found}")
```

---

## Bug #3: Two-Phase Workflow (UNCLEAR)

### Evidence
First test output showed "Phase 2 transition", but it's unclear if user requested it.

### Status
Need clarification from user:
- Was `--two-phase-workflow` flag used in first test?
- Or is it being activated incorrectly?

### Default Value
```python
# src/cua/main.py line 115
"--two-phase-workflow/--no-two-phase-workflow",
default=False,  # ← Correct default
```

### Activation Logic
```python
# src/cua/agent/loop.py line 688
if self.two_phase_workflow and self.current_phase == 1 and search_results:
    # Transition to Phase 2
```

This should only trigger if `two_phase_workflow=True`, which requires explicit flag.

**Conclusion:** Likely not a bug, user may have used flag in first test.

---

## Other Observations

### Screenshot Context Window (Minor Issue)
- User set `--context-window-size 5`
- Expected: Keep 5 screenshots (~7,030 tokens)
- Actual: Keeping 6 screenshots (~8,436 tokens)
- Off by 1? Not critical but should fix.

### DOM Tool Selector Errors (Not a Bug)
```
→ DOM Click: button:contains("START")
✗ Error: 'button:contains("START")' is not a valid selector
```

This is AI using wrong selectors. The tool is working correctly by rejecting invalid selectors.
AI should use the two-step workflow:
1. `find_selectors` to get valid selector
2. `click_selector` with that selector

This is a prompt/guidance issue, not a code bug.

---

## Token Growth Analysis

### Current State (Iteration 27)
- Input tokens per call: 145,478
- AI responses: 132,914 tokens (should be ~9,000)
- Page text: 4,128 tokens (should be 0)
- Screenshots: 8,436 tokens (acceptable)

### After Fixes
**Fix page_text bug:**
- Save 4,128 tokens per iteration after iteration 1
- Cumulative savings at iteration 27: ~110,000 tokens

**Fix message pruning:**
- Reduce AI responses from 132,914 to ~9,000
- Save ~123,914 tokens

**Total savings: ~234,000 tokens at iteration 27**

### Projected Performance
After fixes, iteration 27 should use:
- Input: ~11,564 tokens (vs 145,478 current)
- **92% reduction!**

For 100 iterations:
- Current trajectory: ~8M tokens total
- After fixes: ~1.2M tokens total
- **85% cost reduction!**

---

## Files Affected

### Primary Issues
1. `src/cua/agent/loop.py` - Page text fetched/sent every iteration
2. `src/cua/providers/bedrock.py` - Message pruning not working

### Related Files
- `src/cua/providers/openai.py` - Same page_text issue
- `src/cua/providers/claude.py` - Same page_text issue

---

## Recommended Fix Order

### Priority 1: Page Text (Easy Fix)
**Effort:** Low (5-10 lines of code)
**Impact:** High (saves ~4,000 tokens/iteration)
**Risk:** Low (straightforward logic change)

### Priority 2: Message Pruning (Needs Investigation)
**Effort:** Medium (debug first, then fix)
**Impact:** Critical (saves ~120,000 tokens/iteration)
**Risk:** Medium (need to understand why it's not working)

### Priority 3: Screenshot Off-by-One (Minor)
**Effort:** Low (check array indexing)
**Impact:** Low (saves ~1,400 tokens)
**Risk:** Low (simple fix)

---

## Next Steps

1. **Make safety commit** (current state before changes)
2. **Fix page_text bug** (easy win)
3. **Add debug logging to pruning** (understand the issue)
4. **Run test with debug logging** (see what's happening)
5. **Fix pruning bug** (based on findings)
6. **Test with 30+ iterations** (verify fixes work)

---

## Test Plan

After implementing fixes:

```bash
cua \
  --provider bedrock \
  --model haiku \
  --url "serene-frangipane-7fd25b.netlify.app" \
  --zoom 50 \
  --context-window-size 5 \
  --enable-caching \
  --max-iterations 30 \
  --record-video \
  --prompt "Click START and complete Step 1"
```

**Expected results:**
- Iteration 1: ~5,500 tokens (no change)
- Iteration 10: ~10,000 tokens (vs 54,653 current)
- Iteration 20: ~11,000 tokens (vs 109,178 current)
- Iteration 30: ~12,000 tokens (vs ~160,000 projected current)

**Success criteria:**
- Page text tokens = 0 after iteration 1
- AI response tokens stable at ~9,000
- Total input tokens < 15,000 per iteration

---

## Summary

### Bugs Found
1. ✅ **Page text sent every iteration** - CONFIRMED
2. ⚠️ **Message pruning not working** - LIKELY (needs debug)
3. ❓ **Two-phase activated incorrectly** - UNCLEAR (need clarification)

### Root Causes
1. Optimization comment exists but NOT implemented
2. Pruning logic exists but not effective (unknown why)

### Impact
- Current: ~80,000 tokens/iteration by iteration 27
- After fixes: ~12,000 tokens/iteration
- **85% cost reduction**

### Confidence Level
- Page text bug: 100% confident
- Pruning bug: 90% confident (need to see debug output)
- Two-phase bug: 20% confident (likely not a bug)
