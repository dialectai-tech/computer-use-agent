# Testing Guide - Search Tool Implementation

## Quick Start

You're now on branch: `feature/two-phase-workflow-and-search-tool`

This branch implements the **Custom Search Tool** from IDEAS.md.

---

## What Changed?

### New Feature: search_page_content Tool

The AI now has a dedicated tool to search ALL page content before taking actions:

```
search_page_content(query="[A-Z0-9]{6}", search_type="text")
→ Returns: "Found code AJAF5H at line 23"
```

### Key Changes:
1. ✅ Added `SearchTool` class (`src/cua/tools/search_tool.py`)
2. ✅ Added `search_page_content` tool to providers
3. ✅ Updated prompts to emphasize search tool usage
4. ✅ Agent loop handles SEARCH actions
5. ✅ Search results sent back to AI

---

## How to Test

### Test 1: Basic Search Functionality

```bash
cua --provider bedrock --model haiku \
  --url "serene-frangipane-7fd25b.netlify.app" \
  --max-iterations 20 \
  --use-accessibility-tree \
  --prompt "Use the search_page_content tool to find any 6-character codes on this page."
```

**What to Look For:**
- ✅ Agent uses `search_page_content` tool
- ✅ Search results appear in logs
- ✅ Code found in 1-2 iterations
- ❌ No excessive scrolling

**Expected Log Output:**
```
Iteration 2/100
  → Search: Query="[A-Z0-9]{6}", Type=text
  ✓ 🔍 Found 1 unique code(s): AJAF5H
     📄 Found 1 text match(es) at line(s): 23
```

---

### Test 2: Full Challenge (Same as Before)

```bash
cua --provider bedrock --model haiku \
  --url "serene-frangipane-7fd25b.netlify.app" \
  --max-iterations 100 \
  --zoom 85 \
  --context-window-size 5 \
  --enable-caching \
  --use-accessibility-tree \
  --record-video \
  --prompt "Complete the Browser Navigation Challenge efficiently. This is a 30-level challenge.

  OBJECTIVE: Progress through all 30 levels by finding codes, entering them, and submitting.

  ACTION CHAINING: Whenever possible, perform multiple related actions in a single turn.

  LEVEL WORKFLOW:
  1. Handle any popups (real close buttons, not fake ones)
  2. Use search_page_content tool to find the 6-character code
  3. Enter code into input field
  4. Submit to progress
  5. Repeat

  TIPS:
  - Use search_page_content tool BEFORE scrolling
  - Fake buttons exist - find real options
  - Chain actions when safe

  MEMORY MANAGEMENT:
  - After closing popup, note 'TRANSIENT'
  - When you find codes, note 'REMEMBER: [code]'
  - Focus on current level"
```

**What to Look For:**
- ✅ Agent uses search tool on each level
- ✅ Finds codes quickly (3-5 iterations per level vs 40+ before)
- ✅ No endless scrolling loops
- ✅ Much higher success rate

---

### Test 3: Try Sonnet (Better Instruction Following)

```bash
cua --provider bedrock --model sonnet \
  --url "serene-frangipane-7fd25b.netlify.app" \
  --max-iterations 100 \
  --use-accessibility-tree \
  --record-video \
  --prompt "Complete the challenge efficiently. ALWAYS use search_page_content tool to find codes BEFORE taking any other actions."
```

**Why Sonnet?**
- Better instruction following than Haiku
- More likely to consistently use search tool
- Worth the extra cost for better results

---

## Success Metrics

### ✅ Success Indicators:

| Metric | Before | Target | How to Check |
|--------|--------|--------|--------------|
| **Search tool usage** | 0% | >80% | Look for "→ Search:" in logs |
| **Iterations per level** | 40+ | 3-5 | Count iterations between levels |
| **Code finding time** | 20+ iters | 1-2 iters | See how quickly code is found |
| **Success rate** | ~20% | >80% | How many levels completed |
| **Scrolling actions** | Many | Minimal | Count "→ Scroll" in logs |

### ❌ Failure Indicators:
```
- Agent scrolls without searching first
- Agent never uses search_page_content tool
- Still takes 40+ iterations per level
- Gets stuck in scrolling loops
```

---

## Interpreting Results

### Scenario 1: Search Tool Works! 🎉
**Signs:**
- Agent uses search tool consistently
- Finds codes in 1-2 iterations
- Completes levels in 3-5 iterations
- High success rate (>80%)

**Action:** Success! Merge to main.

---

### Scenario 2: Search Tool Sometimes Works 🤔
**Signs:**
- Agent uses search tool 50% of the time
- Sometimes scrolls instead
- Better than before but not optimal

**Action:** Try Sonnet or add two-phase workflow (force search first).

---

### Scenario 3: Search Tool Rarely Works 😞
**Signs:**
- Agent ignores search tool
- Still scrolls excessively
- No improvement over baseline

**Action:**
1. First try Sonnet (better model)
2. If still fails → Implement two-phase workflow
3. If still fails → Try other solutions from IDEAS.md

---

## Debug Checklist

If search tool isn't being used, check:

### ✅ 1. Is the tool available?
Look for this in API request logs:
```python
"tools": [
    {"name": "search_page_content", ...},
    {"name": "computer", ...}
]
```

### ✅ 2. Is the prompt being sent?
Look for this in logs:
```
🚨 CRITICAL: YOU HAVE A SEARCH TOOL! 🚨
```

### ✅ 3. Is the AI seeing the tool?
Check the response - does AI mention:
- "search_page_content"
- "I'll search for..."
- "Let me use the search tool"

### ✅ 4. Are search results being returned?
Look for:
```
✓ 🔍 Found 1 unique code(s): AJAF5H
```

---

## Compare Before vs After

### BEFORE (main branch):
```
Iteration 1: Take screenshot
Iteration 2: Scroll page ("Let me scroll to find code")
Iteration 3: Scroll page
Iteration 4: Scroll page
...
Iteration 40: Still scrolling
Iteration 41: Give up or timeout
```

### AFTER (feature branch):
```
Iteration 1: Take screenshot
Iteration 2: Search for code
  → Search: Query="[A-Z0-9]{6}"
  ✓ Found: AJAF5H at line 23
Iteration 3: Click input field
Iteration 4: Type code
Iteration 5: Click submit
✅ Level complete!
```

---

## Next Steps After Testing

### If Successful:
1. Create PR to merge to main
2. Update README with search tool docs
3. Consider adding two-phase workflow as optional enhancement

### If Unsuccessful with Haiku:
1. Test with Sonnet
2. Test with Opus 4.5 (best model)
3. Review logs to understand why tool isn't used

### If Unsuccessful with All Models:
1. Implement two-phase workflow (withhold screenshot until after search)
2. Try screenshot degradation
3. Consider MCP server approach

---

## Files to Review

### Implementation Files:
- `src/cua/tools/search_tool.py` - Search logic
- `src/cua/agent/loop.py` - Search action handling
- `src/cua/providers/bedrock.py` - Tool config & prompts

### Documentation:
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- `IDEAS.md` - Original solutions document
- `CURRENT_SYSTEM_WALKTHROUGH.md` - System flow analysis

---

## Quick Commands

```bash
# Test basic search
cua --provider bedrock --model haiku --url "serene-frangipane-7fd25b.netlify.app" --max-iterations 20 --use-accessibility-tree --prompt "Use search_page_content to find codes"

# Test full challenge (Haiku)
cua --provider bedrock --model haiku --url "serene-frangipane-7fd25b.netlify.app" --max-iterations 100 --use-accessibility-tree --record-video --prompt "Complete challenge using search_page_content tool"

# Test with Sonnet (better model)
cua --provider bedrock --model sonnet --url "serene-frangipane-7fd25b.netlify.app" --max-iterations 100 --use-accessibility-tree --record-video --prompt "Use search_page_content ALWAYS"

# Switch back to main branch
git checkout main

# Switch to feature branch
git checkout feature/two-phase-workflow-and-search-tool
```

---

## Questions?

- **Q: Why not implement two-phase workflow yet?**
  A: Test search tool first. It's less invasive. Add two-phase if needed.

- **Q: Will this work with other providers (claude, openai)?**
  A: Yes! Tool is added to all providers. But test with bedrock first.

- **Q: What if AI still ignores the tool?**
  A: Try Sonnet (better), then two-phase workflow (force it), then other solutions.

- **Q: How do I know if it's working?**
  A: Look for "→ Search:" in logs and check iterations per level (should be 3-5).

---

## Ready to Test!

Run Test 2 (full challenge) and report back:
1. Did AI use search tool?
2. How many iterations per level?
3. Success rate?
4. Any issues?

Good luck! 🚀
