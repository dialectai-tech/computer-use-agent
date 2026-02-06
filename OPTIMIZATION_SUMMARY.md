# CUA Optimization Implementation Summary

## Implemented Features

### 1. ✅ Viewport Optimization
- **Changed default resolution**: 1280×720 → **1024×768**
- **Token savings per screenshot**: ~15% (1,229 → 1,049 tokens)
- **Benefit**: More vertical space, better for scrollable modals

### 2. ✅ Browser Zoom Control
- **Default zoom**: **85%**
- **CLI flag**: `--zoom <percentage>`
- **Effect**: See ~18% more webpage content without token cost increase
- **Benefit**: Reduces scrolling needs, better overview of pages

### 3. ✅ Prompt Caching
- **Default**: Enabled (use `--disable-caching` to turn off)
- **Implementation**:
  - Claude (Anthropic API): Uses `cache_control: {"type": "ephemeral"}` on last content blocks
  - Bedrock: Automatic caching handled by AWS
- **Expected savings**: **70-90% on input tokens**
- **How it works**: Caches conversation history, tools, system prompt; pays 1.25x to write, 0.1x to read

### 4. ✅ Context Window Management (Hybrid Approach)
- **Default window size**: 10 screenshots
- **CLI flag**: `--context-window-size <N>`
- **Strategy**:
  1. **Screenshot window**: Keep only last N screenshots
  2. **Action-based pruning**: Auto-discard transient actions (close buttons, scrolls, mouse moves)
  3. **Memory signals**: Parse Claude responses for "REMEMBER:" and "TRANSIENT" markers
  4. **Heuristic detection**: Identifies close button clicks (top-right corner area)

### 5. ✅ Extended Thinking
- **Default**: Disabled
- **CLI flags**:
  - `--extended-thinking` to enable
  - `--thinking-budget <N>` (default: 10000 tokens)
- **When to use**: Complex multi-step reasoning, when model gets stuck
- **Trade-off**: Adds 2-4s latency but may reduce total iterations

## New CLI Flags

```bash
# Viewport & Zoom
--display-width 1024              # Default: 1024
--display-height 768              # Default: 768
--zoom 85                         # Default: 85 (%)

# Caching
--enable-caching / --disable-caching   # Default: enabled

# Context Management
--context-window-size 10          # Default: 10 screenshots

# Extended Thinking
--extended-thinking / --no-extended-thinking   # Default: disabled
--thinking-budget 10000           # Default: 10000 tokens
```

## Architecture Changes

### Browser Controller
- Added `zoom` parameter
- Applies CSS zoom after navigation: `document.body.style.zoom = 'zoom_factor'`

### Agent Loop
- Tracks screenshot history with metadata
- Implements `_is_transient_action()` for action classification
- Implements `_extract_memory_signals()` to parse AI responses
- Implements `_manage_context_window()` for pruning
- Displays context stats after each iteration

### Providers
- **Base Provider**: Added `enable_caching`, `extended_thinking`, `thinking_budget` properties
- **Claude Provider**:
  - Adds `cache_control` to image blocks when caching enabled
  - Adds `thinking` parameter when extended thinking enabled
  - Tracks cache creation/read tokens
- **Bedrock Provider**:
  - Adds `thinking` to `additionalModelRequestFields` when enabled
  - Bedrock's caching is automatic (no code changes needed)

### Statistics
- Added `cache_creation_tokens` and `cache_read_tokens` to `ProviderStats`
- Main CLI displays cache savings percentage

## Expected Performance Improvements

### Cost Reduction (100 iterations, Haiku)

**Before optimizations:**
- Screenshots: 100 × 1,229 = 122,900 tokens
- Total input: ~1.8M tokens
- **Cost: $1.80**

**After optimizations:**
- Screenshots: 10 × 1,049 = 10,490 tokens (in context)
- Prompt caching: 90% of tokens cached (0.1x cost)
- Cache creation: ~1,049 × 1.25 = $0.0013
- Cache reads: ~94K × 0.1 = $0.0094
- New content: ~2K × 100 = $0.20
- **Cost: ~$0.21 (88% savings!)**

### For Sonnet: $5.58 → $0.63 (89% savings)
### For Opus: $9.30 → $1.05 (89% savings)

## Improved Prompting

The system now supports action chaining and memory management signals:

### Memory Signals
- **"REMEMBER: [info]"**: Marks important information to keep in context
- **"TRANSIENT"**: Marks step as forgettable

### Action Chaining
- Models are encouraged to batch related actions in single response
- Example: "Click close button, then scroll to find code, then copy code"

## Testing

To test the optimizations:

```bash
# Test with Haiku (cheap, fast)
cua --provider bedrock --model haiku \
    --url "serene-frangipane-7fd25b.netlify.app" \
    --prompt "Complete the Browser Navigation Challenge..." \
    --max-iterations 25 \
    --record-video

# With extended thinking for complex tasks
cua --provider bedrock --model sonnet \
    --url "example.com" \
    --prompt "Complex task..." \
    --extended-thinking \
    --thinking-budget 16000 \
    --max-iterations 50

# Without caching (for comparison)
cua --provider claude --model claude-sonnet-4-5 \
    --url "example.com" \
    --disable-caching \
    --max-iterations 10
```

## Notes

1. **Caching TTL**: 5 minutes (auto-refreshes with each use)
2. **Context window**: Aggressively prunes transient screenshots
3. **Zoom compatibility**: Works with all browsers via CSS zoom
4. **Extended thinking**: Only use when needed (adds latency)
5. **Cache stats**: Displayed in results for Claude provider only

## Files Modified

1. `src/cua/main.py` - Added CLI flags, stats display
2. `src/cua/agent/loop.py` - Context management, agent configuration
3. `src/cua/browser/playwright_controller.py` - Zoom support
4. `src/cua/providers/base.py` - Base provider configuration
5. `src/cua/providers/claude.py` - Caching + thinking implementation
6. `src/cua/providers/bedrock.py` - Thinking implementation
