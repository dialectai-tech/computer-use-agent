# Bug Fixes Summary - Session 2026-02-08

## Critical Bugs Fixed

### ✅ BUG-001: Automatic context reset not triggering
**Commits**: ac64c77, 273ff29

**Problem**:
Auto-reset threshold set to 200,000 but never triggered even at 210,390 tokens.

**Root Cause**:
- Check used `provider.stats.input_tokens` (cumulative total: 1.8M)
- Should have used current iteration's input tokens (210K)
- Check happened BEFORE breakdown calculation, so wrong data was available

**Fix**:
- Moved auto-reset check to AFTER breakdown calculation
- Pass `breakdown.total_input_tokens` (current iteration)
- Added debug logging: `[DEBUG AUTO-RESET] Iteration X: Checking with N tokens`

**Verification**: Reset now triggers correctly when threshold exceeded

---

### ✅ BUG-007: Empty messages after context reset
**Commits**: 31115d8, fd50030, 5bc50d7, 11ba1e3

**Problem**:
AWS Bedrock error: "messages.2 is empty" after context reset

**Root Cause** (Multiple issues):
1. Screenshot stripping created empty content arrays (Bedrock rejects these)
2. `first_user_message` stored as reference, got mutated during stripping
3. Reset reused the mutated reference, creating empty messages

**Fix**:
1. Only strip screenshots if message has OTHER content
   - If message contains only screenshots, keep them (avoid empty arrays)
2. Deep copy `first_user_message` when initially storing
3. Deep copy again when using in reset
4. Keep last 2 messages intact during stripping (more conservative)

**Verification**: Context reset no longer creates empty messages

---

## Outstanding Issues

### 🔴 BUG-002: Invalid CSS selectors from AI (Critical)
**Example**: `button:contains('START')` - jQuery syntax, not valid CSS

**Impact**: Wasted iterations, confusing error messages

**Recommended Fix**:
- Add selector validation before execution
- Update system prompt to explicitly forbid jQuery selectors
- Provide better examples in tool descriptions

---

### 🟡 BUG-003: Generic selectors cause timeouts (Medium)
**Example**: `input` - matches multiple/hidden elements

**Recommended Fix**:
- DOM Find should return specific selector to use
- Validate selector specificity (reject single-tag selectors)
- Return top 3 matching elements with their selectors

---

### 🟢 BUG-004: Misleading screenshot count display (Low)
**Issue**: Shows "Context: 5 screenshots" but only 1 sent to API

**Recommended Fix**:
- Rename to "Screenshot History: 5 (API sends: 1)"
- Or remove this display entirely

---

## Test Command

Use this to verify all fixes:

```bash
cua --provider bedrock --model haiku \
    --url "serene-frangipane-7fd25b.netlify.app" \
    --no-accessibility-tree \
    --max-iterations 15 \
    --max-message-turns 3 \
    --auto-reset-token-threshold 20000 \
    --prompt "Click START and complete as many steps as possible"
```

**Expected behavior:**
- ✅ Auto-reset triggers around iteration 5-7 (when tokens > 20K)
- ✅ Debug log shows: `🔄 Automatic Context Reset Triggered`
- ✅ No empty message errors after reset
- ✅ Screenshots constant at ~1,406 tokens (not growing)
- ✅ Messages reduced to 2 after reset (first + checkpoint)

**What to watch for:**
- Invalid selectors (BUG-002) - AI may still generate these
- Generic selector timeouts (BUG-003) - AI may use `button`, `input`, etc.
- Task completion - may not finish due to AI behavior issues, not code bugs

---

## Commits in This Session

1. `186c9c3` - docs: Add bug tracking document
2. `ac64c77` - fix: BUG-001 - Auto-reset now uses current iteration tokens
3. `273ff29` - fix: Correct variable name in auto-reset logger
4. `31115d8` - fix: BUG-007 - Add placeholder text to empty messages
5. `fd50030` - fix: Improve screenshot stripping logic
6. `5bc50d7` - fix: BUG-007 - Deep copy first_user_message (initial storage)
7. `11ba1e3` - fix: BUG-007 - Deep copy first_user_message (reset usage)
8. `3a518a7` - docs: Update BUGS.md status

---

## Token Optimization Status

### Working Correctly ✅
- Page text optimization: Only sent on navigation
- Screenshot stripping: Constant 1,406 tokens per iteration
- Message pruning: Keeps last N turns
- System prompt caching: 0 tokens after first call
- Auto-reset: Triggers at threshold, reduces to 2 messages

### Needs Improvement 🟡
- Token growth still high due to verbose AI responses (see BUG-005)
- Consider reducing `max_message_turns` to 2-3 for more aggressive pruning

### Recommendations
- Default threshold (30K) is good for normal use
- For testing/debugging: Use 15K-20K threshold to see reset sooner
- For production: Consider 25K-35K based on model context limits
