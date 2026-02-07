# Context Optimization Analysis - 2026-02-07

## Problem Summary
Token usage explodes from 5k → 82k in just 8 iterations (~10k per iteration), and 15k → 1.2M in 100 iterations. This is unsustainable for long tasks.

## Root Causes Identified

### 1. **Search Results Explosion** (CRITICAL)
- **Issue**: Search returns ALL matches with no limit
- **Example**: Query "" returns 436 line matches = 49,499 chars in one tool result
- **Impact**: Massive, grows with page complexity
- **Fix**: Limit to first 10 matches, add pagination if needed

### 2. **System Prompt Repetition**
- **Issue**: 4,510 char system prompt in every initial message
- **Impact**: Moderate but unnecessary
- **Fix**: System prompt should be in system parameter, not user message

### 3. **Page Text Duplication**
- **Issue**: Up to 10,000 chars of page text sent with EVERY computer action
- **Impact**: High for action-heavy workflows
- **Fix**: Only send page text when actually needed (search, initial)

### 4. **Accessibility Tree Overhead**
- **Issue**: Full tree sent with every computer action
- **Impact**: Medium-high depending on page complexity
- **Fix**: Only send tree on explicit request or with search

### 5. **Verbose Tool Result Formatting**
- **Issue**: JSON formatting with markdown code blocks adds ~15% overhead
- **Impact**: Cumulative across all results
- **Fix**: Use more compact formatting

### 6. **Context Reset Not Working**
- **Issue**: AI provides empty parameters, validation fails silently
- **Impact**: CRITICAL - prevents token savings on long tasks
- **Fix**: Better prompts with examples, error feedback to AI

### 7. **Message History Pruning Ineffective**
- **Issue**: max_message_turns=10 but all assistant responses accumulate
- **Impact**: High - the 98.9% of tokens from AI responses in original run
- **Fix**: Already implemented but screenshots/results still accumulate

## Token Breakdown (Iteration 8)

| Component | Tokens | % | Chars | Fix Priority |
|-----------|--------|---|-------|--------------|
| System prompt (first msg) | ~1,100 | 13% | 4,510 | HIGH |
| Search results (1 query) | ~12,000 | 45% | 49,499 | CRITICAL |
| Page text (per action) | ~2,500 | 10% | 10,000 | HIGH |
| Accessibility tree | ~1,000 | 4% | ~4,000 | MEDIUM |
| Screenshots (3 images) | ~4,200 | 16% | N/A | MEDIUM |
| Assistant responses | ~3,000 | 12% | varies | INFO ONLY |

## Optimization Plan

### Phase 1: Critical Fixes (Immediate)
1. ✅ **Limit search results to 10-20 matches**
2. ✅ **Stop sending page text with every action** (only on search/initial)
3. ✅ **Fix context reset parameter validation** with clear error messages
4. ✅ **Improve prompts** with clear tool usage examples

### Phase 2: Medium Priority
5. ✅ **Reduce system prompt verbosity** (target: 2,500 chars, save ~1k tokens)
6. ✅ **Optimize tool result formatting** (remove markdown, compact JSON)
7. ✅ **Smarter accessibility tree usage** (only when needed)

### Phase 3: Advanced (Future)
8. ⏳ Implement token budget tracking
9. ⏳ Auto-reset at token thresholds
10. ⏳ Summarization of old context

## Expected Impact

### Current (8 iterations):
- Start: 5,769 tokens
- End: 82,138 tokens
- Growth: ~10k per iteration

### After Critical Fixes:
- Start: 4,000 tokens (save 1.7k from prompt optimization)
- Per iteration: ~3-4k tokens (save 6-7k per iteration!)
- End (8 iter): ~28,000 tokens (65% reduction!)

### After All Fixes:
- Per iteration: ~2-3k tokens
- End (8 iter): ~20,000 tokens (75% reduction!)
- 100 iterations: ~250k tokens (vs 1.2M = 80% savings!)

## Implementation Priority

1. **Search result limiting** - 10 min implementation, massive impact
2. **Page text optimization** - 20 min, high impact
3. **Context reset fixes** - 30 min, critical for long tasks
4. **Prompt optimization** - 40 min, cumulative benefit
5. **Tool result formatting** - 20 min, moderate impact

Total implementation: ~2 hours for 75% token savings!
