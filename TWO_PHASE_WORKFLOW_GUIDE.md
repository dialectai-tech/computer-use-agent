# Two-Phase Workflow Guide

## Overview

The **Two-Phase Workflow** is an advanced feature that forces the AI to search for content BEFORE seeing screenshots. This removes visual bias and ensures the AI uses the search tool.

## How It Works

### Traditional Workflow (Without Two-Phase):
```
1. AI receives: Text + Tree + Screenshot (all at once)
2. AI tends to focus on screenshot (visual bias)
3. AI may ignore text/tree and scroll randomly
4. Result: Inefficient, many iterations
```

### Two-Phase Workflow:
```
Phase 1: SEARCH ONLY
├─ AI receives: Text + Tree ONLY (NO screenshot)
├─ AI MUST use search_page_content tool
├─ AI reports findings
└─ Screenshot is withheld (forces search)

Phase 2: ACTION WITH SCREENSHOT
├─ AI receives: Screenshot + Search results
├─ AI uses search results to know WHAT to interact with
├─ AI uses screenshot to find WHERE (coordinates)
└─ AI takes actions using coordinates
```

## Benefits

### 1. Forces Search Tool Usage
- AI cannot see screenshot in phase 1
- MUST use search tool to find content
- Eliminates visual bias completely

### 2. Sequential Processing
- Search happens FIRST (always)
- Actions happen SECOND (with context)
- Natural workflow: find → see → act

### 3. Better Efficiency
- No random scrolling
- No "looking around" behavior
- Direct path: search → locate → act

## When to Use

### ✅ Use Two-Phase Workflow When:
- AI ignores search tool despite instructions
- AI scrolls excessively looking for content
- Search tool alone doesn't improve results
- You need guaranteed search-first behavior

### ❌ Don't Use Two-Phase Workflow When:
- Search tool already works well
- AI consistently uses search tool
- Task doesn't involve searching (e.g., just clicking visible buttons)
- You want AI to have more flexibility

## How to Enable

### CLI Flag:
```bash
cua --provider bedrock --model haiku \
  --url "https://example.com" \
  --two-phase-workflow \
  --use-accessibility-tree \
  --prompt "Your task here"
```

### In Code:
```python
agent = ComputerUseAgent(
    provider=provider,
    two_phase_workflow=True,
    use_accessibility_tree=True,
    # ... other options
)
```

## Example Usage

### Test 1: Basic Two-Phase Test
```bash
cua --provider bedrock --model haiku \
  --url "serene-frangipane-7fd25b.netlify.app" \
  --max-iterations 50 \
  --use-accessibility-tree \
  --two-phase-workflow \
  --prompt "Complete the Browser Navigation Challenge using two-phase workflow."
```

**Expected Output:**
```
Iteration 1/50
  Two-phase workflow: Phase 1 (Search Only)
  → Search: Query="[A-Z0-9]{6}", Type=text
  ✓ Found code AJAF5H at line 23

  → Transitioning to Phase 2 (Action with Screenshot)

Iteration 2/50
  → Click at (640, 300)
  → Type: "AJAF5H"
  → Click at (700, 350)

✓ Level complete!
```

### Test 2: Compare With and Without
```bash
# WITHOUT two-phase (baseline)
cua --url "..." --prompt "..." --max-iterations 100

# WITH two-phase (enhanced)
cua --url "..." --prompt "..." --max-iterations 100 --two-phase-workflow
```

**Metrics to Compare:**
- Iterations per level
- Search tool usage rate
- Success rate
- Time per level

## What Happens in Each Phase

### Phase 1: Search Only

**AI Receives:**
```
Prompt: "Your task + PHASE 1: SEARCH ONLY (No Screenshot Yet)"
Text: [All page text]
Tree: [Accessibility tree]
Tools: search_page_content, computer (but no screenshot to use)
```

**AI Must:**
- Use search_page_content tool
- Find codes, buttons, inputs, etc.
- Report findings with line numbers/locations

**AI Cannot:**
- See the screenshot (it's not sent yet)
- Use computer tool effectively (no coordinates)
- Take actions (must search first)

**Example Phase 1 Response:**
```
"I'll search for the 6-character code using the search tool."

Tool use: search_page_content(query="[A-Z0-9]{6}", search_type="text")
Result: "Found code AJAF5H at line 23 in page text"

"Phase 1 complete. I found the code AJAF5H. Ready for Phase 2."
```

### Phase 2: Action with Screenshot

**AI Receives:**
```
Prompt: "PHASE 2: ACTION WITH SCREENSHOT"
Search Results: "Found code AJAF5H at line 23"
Screenshot: [PNG image of page]
Text: [Updated page text]
Tree: [Updated accessibility tree]
Tools: computer (now with screenshot for coordinates)
```

**AI Must:**
- Use search results to know WHAT to interact with
- Use screenshot to find WHERE (coordinates)
- Take actions using computer tool

**AI Can:**
- Click at specific coordinates
- Type text into inputs
- Verify actions visually

**Example Phase 2 Response:**
```
"Based on Phase 1 search results, I found code AJAF5H.
Now looking at the screenshot to find coordinates."

Tool use: left_click at [640, 300] (input field)
Tool use: type "AJAF5H"
Tool use: left_click at [700, 350] (Submit button)

"Actions complete!"
```

## Phase Transition

**Automatic Transition:**
The agent automatically detects when Phase 1 is complete:

1. Phase 1 iteration completes
2. Search tool was used → search results collected
3. Agent detects search results exist
4. Console shows: "→ Transitioning to Phase 2"
5. Screenshot is loaded and sent
6. Phase 2 begins automatically

**No Manual Intervention:**
- Transition is automatic
- AI doesn't need to request Phase 2
- System handles the flow

## Comparison: Traditional vs Two-Phase

### Traditional Workflow (Search Tool Only):

**Iteration 1:**
```
AI receives: Text + Tree + Screenshot
AI sees screenshot first (visual bias)
AI: "Let me scroll to find the code"
→ Scroll action (ignores search tool!)
```

**Iteration 2-40:**
```
More scrolling...
Eventually may use search tool
Or may give up
```

### Two-Phase Workflow:

**Iteration 1 (Phase 1):**
```
AI receives: Text + Tree (NO screenshot)
AI has no choice but to search
AI: "I'll use search_page_content"
→ Search action (forced!)
Result: "Found code AJAF5H"
```

**Iteration 2 (Phase 2):**
```
AI receives: Screenshot + Search results
AI: "I found AJAF5H in Phase 1"
AI: "Now clicking at coordinates"
→ Click, type, submit
Success!
```

## Troubleshooting

### Issue 1: Phase 1 Never Completes
**Symptom:** Agent gets stuck in Phase 1, never transitions

**Causes:**
- AI didn't use search tool
- Search tool returned no results
- Search results not properly stored

**Fix:**
- Check if search tool is being used (look for "→ Search:" in logs)
- Ensure page has searchable content
- Try with better model (Sonnet instead of Haiku)

### Issue 2: Phase 2 Has Wrong Coordinates
**Symptom:** Phase 2 actions click wrong locations

**Causes:**
- AI misinterpreted search results
- Screenshot doesn't match expected content
- Coordinates not aligned with search findings

**Fix:**
- Make search results more specific
- Ensure screenshot is taken after page loads
- Use better model with better visual understanding

### Issue 3: Still Ignores Search in Phase 1
**Symptom:** AI tries to use computer tool in Phase 1

**Causes:**
- Model not following instructions
- Prompt not clear enough

**Fix:**
- Try Sonnet or Opus (better instruction following)
- Enhance Phase 1 prompt to be more explicit
- Add examples in prompt

## Performance Comparison

### Expected Metrics:

| Metric | No Search Tool | Search Tool Only | Two-Phase Workflow |
|--------|----------------|------------------|--------------------|
| **Search tool usage** | 0% | 50-80% | 100% ✅ |
| **Iterations/level** | 40+ | 10-20 | 3-5 ✅ |
| **Success rate** | ~20% | ~60% | ~90%+ ✅ |
| **Visual bias** | High | Medium | None ✅ |

## Code Changes

### Files Modified:
1. `src/cua/agent/loop.py`
   - Added `two_phase_workflow` parameter
   - Added phase tracking (current_phase, phase_search_results)
   - Modified initial request to send text+tree only in Phase 1
   - Added phase transition logic
   - Added Phase 2 prompt with search results

2. `src/cua/main.py`
   - Added `--two-phase-workflow` CLI flag
   - Added parameter to agent initialization

### New Logic:
- Phase 1: Text + Tree only → Search required
- Transition: Detect search completion → Load screenshot
- Phase 2: Screenshot + Results → Actions with coordinates

## Best Practices

### 1. Use with Search Tool
Two-phase workflow is designed to work WITH the search tool, not replace it.

### 2. Test Both Modes
Compare results with and without two-phase to see improvement.

### 3. Start with Sonnet
Haiku may struggle with complex phase instructions. Start with Sonnet.

### 4. Monitor Phase Transitions
Watch logs for "→ Transitioning to Phase 2" message.

### 5. Combine with Other Features
- ✅ Use with `--use-accessibility-tree`
- ✅ Use with `--enable-caching`
- ✅ Use with `--extended-thinking` for complex tasks
- ✅ Use with `--record-video` to review behavior

## Example Command (Full)

```bash
cua --provider bedrock --model sonnet \
  --url "serene-frangipane-7fd25b.netlify.app" \
  --max-iterations 100 \
  --zoom 85 \
  --use-accessibility-tree \
  --two-phase-workflow \
  --enable-caching \
  --record-video \
  --context-window-size 5 \
  --prompt "Complete the Browser Navigation Challenge efficiently.

Use two-phase workflow:
- Phase 1: Search for codes using search_page_content tool
- Phase 2: Use screenshot to click/type at correct coordinates

Work through all 30 levels systematically."
```

## When to Choose Each Approach

### Use Search Tool Only (No Two-Phase):
- AI consistently uses search tool
- Tasks are straightforward
- Want simpler workflow

### Use Two-Phase Workflow:
- AI ignores search tool
- Need guaranteed search-first behavior
- Want maximum efficiency
- Complex multi-step tasks

### Use Traditional (No Search, No Two-Phase):
- Task doesn't involve searching
- Content is always visible
- Simple click-only tasks

## Summary

**Two-Phase Workflow** = **Forced efficiency**

- Phase 1 forces search (no screenshot = must search)
- Phase 2 enables actions (screenshot + results = precise actions)
- Result: Maximum efficiency, no visual bias, guaranteed search usage

**Perfect for:** Challenges where AI needs to find specific content (codes, text, data) before taking actions.

**Not needed for:** Simple tasks where content is already visible and obvious.

## Questions?

- **Q: Can I disable it mid-run?**
  A: No, it's set at startup. Restart with flag removed.

- **Q: Does it work with all providers?**
  A: Yes! Works with bedrock, claude, and openai providers.

- **Q: How much slower is it?**
  A: Actually FASTER! Reduces wasted iterations.

- **Q: What if Phase 1 finds nothing?**
  A: Phase 2 still happens. AI can try other approaches with screenshot.

---

Ready to test? Start with the basic test command and compare results!
