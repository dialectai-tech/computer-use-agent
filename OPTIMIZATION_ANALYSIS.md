# CUA Token Optimization & Performance Analysis

## Test Results Summary
- **Model**: Haiku (cheap)
- **Iterations**: 100 (max reached)
- **Progress**: Step 3 of 30 completed
- **Total Time**: 651 seconds (~11 minutes)
- **Total Tokens**: 4,032,706 tokens
  - Input: 4,017,114 tokens
  - Output: 15,592 tokens
- **Avg API Time**: 5.29s per call
- **Context Window**: 5 screenshots

## Token Growth Analysis

| Iteration Range | Token Growth | Per Iteration |
|----------------|--------------|---------------|
| 1 → 10 | 154,764 | 17,196/iter |
| 10 → 50 | 1,628,598 | 40,715/iter |
| 50 → 90 | 1,976,081 | 49,402/iter |
| 90 → 100 | 251,450 | 25,145/iter |

**Average**: ~40-50k tokens added per iteration despite keeping only 5 screenshots.

## Root Causes

### 1. Context Accumulation
Each message cycle contains:
- Screenshot (~8k tokens)
- Accessibility tree (~10-20k tokens, grows with page complexity)
- Page text (~2.5k tokens, truncated at 10k chars)

With 5 cycles in context:
- 5 screenshots × 8k = 40k tokens
- 5 accessibility trees × 15k = 75k tokens (average)
- 5 page texts × 2.5k = 12.5k tokens
- **Total per cycle**: ~127.5k tokens baseline
- **Plus AI responses**: ~1-2k tokens each

As pages get more complex (Step 3 has more modals, content), the tree and text grow larger.

### 2. Accessibility Tree Not Optimized Enough
Current simplification:
- Max depth: limited
- Children: limited to 50 per node
- Names: truncated to 100 chars

**Problem**: Complex pages (with modals, nested content) still generate huge trees.

### 3. Page Text Duplication
Page text includes all visible content, which duplicates information already in the accessibility tree.

### 4. No Differential Updates
Every tool result sends the FULL page state (screenshot + tree + text), even if only small parts changed.

## Performance Issues

### 1. API Call Time
- **Average**: 5.29s per API call
- **100 iterations**: 529s total API time (88% of total time)
- **Breakdown**:
  - Network latency: ~500ms
  - Model processing: ~4-5s per call
  - Token processing: Higher with more tokens

### 2. Browser Actions
- **Total actions**: 115 (more than iterations due to multi-action support)
- **Action time**: ~0.5-1s per action
- **Total**: ~60-120s for actions

### 3. Screenshot/Data Collection
- **Per iteration**: ~1-2s for screenshot + tree + text extraction
- **Total**: ~100-200s for data collection

## Browser Dimension Issue

**User's Observation**:
- Video recording: 1280x720
- User's laptop: 1920x950
- No scrollbar visible in recording

**Analysis**:
- Default viewport: 1024×768
- User used: `--zoom 50`
- Effective viewport at 50% zoom: 2048×1536 equivalent
- Video should be recorded at viewport size (1024×768), not 1280×720

**Possible causes**:
1. Video file metadata showing different dimensions than actual recording
2. Playwright automatically upscaling/downscaling
3. Different display dimensions were used than logged

## Optimization Recommendations

### Priority 1: Reduce Token Consumption (Critical)

#### A. Aggressive Accessibility Tree Pruning
**Current**: Simplified tree with truncation
**Proposed**: Extract only interactive elements and structure

```python
def get_minimal_accessibility_tree(self, tree: dict) -> dict:
    """Extract minimal interactive elements only."""
    def extract_interactive(node, path=""):
        # Only keep: buttons, inputs, links, headings, modals
        interactive_roles = {
            'button', 'link', 'textbox', 'checkbox', 'radio',
            'combobox', 'listbox', 'menuitem', 'heading', 'dialog', 'alertdialog'
        }

        if node.get('role') in interactive_roles:
            return {
                'role': node['role'],
                'name': node.get('name', '')[:50],  # Shorter truncation
                'path': path  # Keep path for reference
            }

        # Recursively process children
        results = []
        for i, child in enumerate(node.get('children', [])[:20]):  # Fewer children
            result = extract_interactive(child, f"{path}/{i}")
            if result:
                if isinstance(result, list):
                    results.extend(result)
                else:
                    results.append(result)

        return results if results else None

    return extract_interactive(tree)
```

**Savings**: 10-20k tokens → 2-5k tokens per tree (60-75% reduction)

#### B. Remove Page Text from Tool Results
**Current**: Send full page text in every tool result
**Proposed**: Only send page text in initial request and Phase 1 of two-phase workflow

```python
def create_continuation_request(
    self,
    screenshot: str,
    accessibility_tree: dict = None,
    page_text: str = None,  # Make optional
    search_results: list = None,
    additional_instruction: str = None
) -> Any:
    # Only include page_text if explicitly needed (e.g., Phase 1)
    # For Phase 2 (action), skip page_text entirely
    if self.two_phase_mode and self.phase == 2:
        page_text = None  # Don't send in action phase
```

**Savings**: 2.5k tokens × 5 cycles = 12.5k tokens (removed entirely from tool results)

#### C. Truncate Page Text More Aggressively
**Current**: 10k chars (~2.5k tokens)
**Proposed**: 4k chars (~1k tokens)

**Savings**: 1.5k tokens per cycle × 5 = 7.5k tokens

#### D. Reduce Context Window
**Current**: User used 5 cycles
**Proposed**: Test with 3 cycles (only recent history matters)

**Savings**: 40-50k tokens per cycle × 2 = 80-100k tokens removed

### Priority 2: Speed Optimization

#### A. Enable Prompt Caching (Already Enabled)
**Status**: `--enable-caching` is used
**Effect**: System prompt and first message cached
**Savings**: Reduced latency on subsequent calls

#### B. Parallel Tool Execution (Already Implemented)
**Status**: Multi-action support in Fix 10
**Effect**: Multiple actions in one API call
**Current**: 115 actions in 100 iterations (1.15 actions/iter)
**Potential**: Could be 2-3 actions/iter with better prompting

#### C. Reduce Screenshot Size
**Current**: Full viewport at 1024×768
**Proposed**: Reduce resolution or compress more

```python
# In take_screenshot()
screenshot = self.page.screenshot()
# Compress more aggressively
img = Image.open(io.BytesIO(screenshot))
img = img.resize((800, 600), Image.LANCZOS)  # Smaller
```

**Savings**: ~2-3k tokens per screenshot × 5 = 10-15k tokens

#### D. Use Haiku More Efficiently
**Current**: 5.29s avg API time
**Analysis**: Haiku should be faster (~1-2s typical)
**Cause**: Large token count slows processing

With token optimizations, API time should drop to 2-3s average.

### Priority 3: Browser Configuration

#### A. Fix Viewport for Better Scrollbar Visibility
```python
# Use larger viewport that matches modern screens
--display-width 1280 --display-height 800
```

#### B. Optimize Zoom Level
**Current**: User used 50%
**Recommendation**: Try 70-85% for balance between:
- Seeing more content (lower zoom)
- Better element visibility (higher zoom)

#### C. Ensure Video Matches Viewport
Verify video recording size matches viewport:
```python
context_options["record_video_size"] = {
    "width": self.display_width,
    "height": self.display_height
}
```

### Priority 4: Agent Behavior

#### A. Better Modal Handling
**Observation**: Agent spent many iterations on modal selections
**Improvement**: Add modal-specific guidance to prompts

#### B. Stronger Search-First Enforcement
**Current**: Two-phase workflow helps
**Enhancement**: Validate AI used search before allowing actions

## Implementation Priority

### Phase 1: Critical Token Optimizations (Implement First)
1. Remove page text from tool results (except initial/Phase 1)
2. Implement minimal accessibility tree extraction
3. Reduce context window to 3 cycles
4. Truncate page text to 4k chars

**Expected Impact**:
- Token reduction: 50-60%
- Cost reduction: 50-60%
- Speed improvement: 30-40% (less processing)

### Phase 2: Speed Enhancements
1. Optimize screenshot compression
2. Verify prompt caching is working
3. Encourage more multi-action usage

**Expected Impact**:
- Speed improvement: 20-30%
- API time: 5.29s → 3-4s average

### Phase 3: Browser & UX Improvements
1. Fix viewport dimensions
2. Verify video recording
3. Add scrollbar visibility checks

**Expected Impact**:
- Better user experience
- Easier debugging via video

## Target Metrics

### After Optimizations
- **Token usage**: 4M → 1.5-2M tokens (50-60% reduction)
- **Time per iteration**: 6.5s → 4-5s (25-35% reduction)
- **Total time**: 11 minutes → 7-8 minutes for 100 iterations
- **Cost**: ~50-60% reduction

### For 30-Step Completion
If current rate = 3 steps in 100 iterations:
- Estimated total: ~1000 iterations needed
- With optimizations:
  - Time: ~65-80 minutes (vs 110 minutes now)
  - Tokens: ~15-20M tokens (vs 40M now)
  - Cost: ~$5-10 for full completion (Haiku)

## Next Steps

1. **Implement Phase 1 optimizations** (critical for cost/speed)
2. **Test with same challenge** to verify improvements
3. **Measure token reduction** and speed gains
4. **Iterate** on Phase 2 and 3 if needed

## Questions for User

1. Should we proceed with Phase 1 optimizations immediately?
2. Do you want to test with a different challenge/page first?
3. What's the acceptable time/cost for completing all 30 steps?
4. Should we focus on speed or accuracy first?
