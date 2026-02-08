# Context Optimization Features Summary

## Overview

This document summarizes the token optimization features implemented to manage conversation context growth and reduce token costs.

## Features Implemented

### 1. Page Text Optimization (Already Existed)
- **What**: Only send page text when URL changes (navigation occurs)
- **Savings**: ~2,500-10,000 tokens per non-navigation iteration
- **Implementation**: Tracks last URL, compares before sending page text

### 2. Message History Pruning (Already Existed)
- **What**: Keep only first message + last N conversation cycles
- **Control**: `--max-message-turns N` (default: 3)
- **Effect**: Prevents unlimited message history growth

### 3. Screenshot Stripping (New - Branch: `feature/latest-screenshot-only`)
- **What**: Strip old screenshots from messages, keep only most recent
- **Why**: Screenshots (~1,406 tokens each) served their purpose, AI responses provide context
- **Savings**:
  - Iteration 10: ~12,654 tokens saved (9 old screenshots removed)
  - Linear savings grow with iterations
- **Result**: Screenshots now O(1) instead of O(t)

### 4. Automatic Context Reset (New - Branch: `feature/automatic-context-reset`)
- **What**: Automatically reset conversation context at optimal points
- **When**:
  1. Every 5 steps in multi-step tasks (e.g., Step 5, 10, 15...)
  2. Input tokens exceed threshold (configurable)
  3. Major navigation after 10+ iterations in new section
- **Controls**:
  - `--auto-context-reset` / `--no-auto-context-reset` (default: enabled)
  - `--auto-reset-token-threshold N` (default: 30000)
- **Effect**: Reduces messages to 2 (first + checkpoint), massive token savings
- **Preserves**: Progress summary, current goal, current screenshot

## Test Results

### Baseline (No Optimizations)
| Iteration | Screenshots | AI Responses | Input Tokens |
|-----------|-------------|--------------|--------------|
| 6 | 8,436 (6×) | 14,485 | 62,673 |
| 10 | 14,060 (10×) | ~40,000 | ~150,000+ |

### With All Optimizations
| Iteration | Screenshots | AI Responses | Input Tokens | Notes |
|-----------|-------------|--------------|--------------|-------|
| 6 | 1,406 (1×) | 14,485 | ~17,000 | Screenshot stripping active |
| 9 | 1,406 (1×) | 30,053 | 31,459 | Auto reset triggered |
| 10 | 1,406 (1×) | ~3,000 | ~6,000 | After reset (fresh start) |

### Token Savings Breakdown

**Per Iteration (with screenshot stripping):**
- Iteration 10: Saved 12,654 tokens from screenshots
- Iteration 20: Would save 26,714 tokens from screenshots
- Iteration 30: Would save 40,774 tokens from screenshots

**With Automatic Reset (at 30K tokens):**
- Resets every ~7-10 iterations
- Each reset: 25,000-40,000 tokens → ~5,000 tokens
- Savings: 20,000-35,000 tokens per reset

## Usage Examples

### Default (All Optimizations Enabled)
```bash
cua --provider bedrock --model haiku \
    --url "example.com" \
    --prompt "Complete all steps"
```

### Custom Token Threshold
```bash
cua --provider bedrock --model haiku \
    --url "example.com" \
    --auto-reset-token-threshold 20000 \
    --prompt "Complete all steps"
```

### Disable Automatic Reset (Manual Control Only)
```bash
cua --provider bedrock --model haiku \
    --url "example.com" \
    --no-auto-context-reset \
    --prompt "Complete all steps"
```

### Conservative Message Pruning + Auto Reset
```bash
cua --provider bedrock --model haiku \
    --url "example.com" \
    --max-message-turns 5 \
    --auto-reset-token-threshold 40000 \
    --prompt "Complete all steps"
```

## Growth Rate Analysis

### Before All Optimizations
- **Screenshots**: O(t) - linear growth
- **AI Responses**: O(t) - linear growth with pruning
- **Total**: O(t²) without pruning, O(t) with pruning

### After All Optimizations
- **Screenshots**: O(1) - constant (only latest)
- **AI Responses**: O(1) with auto reset - bounded by threshold
- **Total**: O(1) - bounded growth, resets periodically

### Practical Impact
For a 30-iteration task:
- **Without optimizations**: ~300,000+ input tokens
- **With screenshot stripping**: ~150,000 input tokens
- **With auto reset (every 10 iter)**: ~60,000 input tokens
- **Savings**: 80% reduction in token costs

## Manual Context Reset Tool

The AI can still manually call `reset_context` tool when appropriate:
- Mid-task milestones
- Getting stuck in loops
- After major task completions

The automatic reset complements (doesn't replace) this capability.

## Branch Structure

```
main
 ├─ feature/context-reset-from-dom (page_text fixes)
 │   └─ d775792: fix: Resolve NoneType errors in page_text regex operations
 │
 ├─ feature/latest-screenshot-only
 │   └─ 36b1865: feat: Strip old screenshots from message history
 │       │
 │       └─ feature/automatic-context-reset
 │           └─ e5bbc32: feat: Add automatic context reset at milestones
```

## Recommendations

1. **For cost optimization**: Use all defaults (enabled by default)
2. **For long tasks (30+ steps)**: Lower threshold to 20,000-25,000
3. **For debugging**: Disable auto-reset to see full conversation history
4. **For token-heavy tasks**: Combine with `--max-message-turns 2` for aggressive pruning

## Future Enhancements

Potential additional optimizations:
1. Smart screenshot compression (reduce image quality for old screenshots)
2. Semantic deduplication (detect repeated AI reasoning patterns)
3. Tool result summarization (compress verbose tool outputs)
4. Adaptive thresholds (learn optimal reset points per task type)
