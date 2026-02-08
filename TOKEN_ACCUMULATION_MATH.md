# Token Accumulation Math

## Message Structure

Each API call sends:
- **System prompt** (separate parameter, cached after first call)
- **Messages array** containing:
  - User messages: screenshots + page text + tool results
  - Assistant messages: text responses + tool use blocks

Messages accumulate over time until pruning occurs.

## Recurrence Equations

### Iteration 1 (Initial)
```
Input_1 = SystemPrompt_0 + Screenshot_1 + PageText_1 + AccessibilityTree_1 + UserPrompt_0
Output_1 = AssistantResponse_1
Cumulative_1 = Input_1 + Output_1
```

### Iteration t (t ≥ 2, No Pruning)
```
Input_t = SystemPrompt_0 * δ(t=1)                    // Only counted at t=1, cached after
        + Σ(i=1 to t) Screenshot_i                   // All screenshots accumulate
        + Σ(i=1 to t) PageText_i * δ(navigation_i)   // Only when URL changes
        + Σ(i=1 to t-1) AssistantResponse_i          // All past AI responses
        + Σ(i=1 to t) UserToolResults_i              // All tool results

Output_t = AssistantResponse_t

TotalThisCall_t = Input_t + Output_t
Cumulative_t = Cumulative_{t-1} + TotalThisCall_t
```

**Growth pattern**: Each component accumulates linearly, leading to O(t²) growth without pruning.

### With Pruning (t > threshold)

Pruning keeps:
- First user message (task context)
- Last N complete cycles (N = max_message_turns)

```
Input_t = SystemPrompt_0 * 0                                    // Cached (free)
        + Screenshot_1 (in FirstUserMessage)                    // Always kept
        + Σ(i in last N cycles) Screenshot_i                    // Recent screenshots only
        + PageText_1 (in FirstUserMessage, if present)          // Initial page text
        + Σ(i in last N cycles) PageText_i * δ(navigation_i)   // Recent navigations only
        + Σ(i in last N cycles) AssistantResponse_i            // Recent responses only
        + Σ(i in last N cycles) UserToolResults_i              // Recent results only
```

**Growth pattern**: Bounded by N cycles, but screenshots still accumulate linearly O(t).

## Test Data (Session 20260208_101904)

| Iteration | System | Screenshots | Page Text | AI Responses | Input | Output | Cumulative |
|-----------|--------|-------------|-----------|--------------|-------|--------|------------|
| 1 | 500 | 1,406 | 19 | 3,447 | 5,372 | 78 | 5,450 |
| 2 | 0 | 2,812 | 0 | 5,299 | 8,111 | 176 | 13,737 |
| 3 | 0 | 4,218 | 0 | 6,748 | 10,966 | 262 | 24,965 |
| 4 | 0 | 5,624 | 8,784 | 0 | 13,925 | 314 | 39,204 |
| 6 | 0 | 8,436 | 0 | 14,485 | 22,921 | 548 | 62,673 |

**Pruning triggered at iteration 6**: Messages reduced from 10 → 8 (keeping first + last 3 cycles).

## Key Observations

1. **System Prompt Caching**: 500 tokens at t=1, then 0 (effectively free)

2. **Screenshot Accumulation**: ~1,406 tokens/screenshot, linear growth
   - t=1: 1,406 (1 screenshot)
   - t=2: 2,812 (2 screenshots)
   - t=3: 4,218 (3 screenshots)
   - t=4: 5,624 (4 screenshots)
   - t=6: 8,436 (6 screenshots)

3. **Page Text Optimization**: Only sent on navigation
   - t=1: 19 tokens (initial load)
   - t=2-3: 0 tokens (no navigation)
   - t=4: 8,784 tokens (navigated to step1 page)
   - t=6: 0 tokens (no navigation)
   - **Savings**: ~17,568 tokens avoided over 2 non-navigation iterations

4. **AI Response Accumulation**: Grows with message history
   - Before pruning (t=1-4): Cumulative (3,447 → 5,299 → 6,748 → 0)
   - After pruning (t=6): 14,485 (only last 3 cycles worth)

5. **Pruning Effect**:
   - Prevents O(t²) explosion by capping message history
   - Keeps growth closer to O(t) from screenshots
   - AI responses stay bounded by N * avg_response_size

## Growth Rates

- **Without optimizations**: O(t²) - everything accumulates
- **With page text optimization**: Saves 2,500-10,000 tokens per non-navigation iteration
- **With message pruning**: Bounded by O(N) for messages, but O(t) for screenshots
- **With both**: Linear growth O(t) dominated by screenshot accumulation
