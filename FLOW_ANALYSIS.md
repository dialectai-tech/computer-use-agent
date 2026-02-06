# Flow Analysis - Why Agent Ignores Text/Tree

## Current Flow (What Actually Happens)

### Initial Request Structure:
```
Message to Bedrock API:
├─ Content Block 1 (text):
│  ├─ User prompt ("Complete the Browser Navigation Challenge...")
│  ├─ Autonomous instructions ("You are an AUTONOMOUS agent...")
│  ├─ Hybrid guide ("🚨 CRITICAL: YOU HAVE PAGE TEXT & TREE! 🚨...")
│  └─ Tool usage guide ("When using computer tool...")
│
├─ Content Block 2 (text):
│  └─ Accessibility Tree (JSON)
│
├─ Content Block 3 (text):
│  └─ Page Text (all visible text)
│
└─ Content Block 4 (image):
   └─ Screenshot (PNG)
```

### The Problem:

**Order of Processing:**
1. Agent reads Block 1: "Complete this challenge... READ TEXT FIRST!"
2. Agent reads Block 2: Accessibility tree (glances at it)
3. Agent reads Block 3: Page text (glances at it)
4. Agent sees Block 4: Screenshot (FOCUSES ON THIS)
5. Agent responds based on screenshot

**Why it fails:**
- By the time the agent reads "READ TEXT FIRST", it hasn't seen the text yet
- When the text/tree appear later, the agent has already read all instructions
- The screenshot appears last, which is what the agent focuses on
- Models are trained to prefer visual information (screenshot) over text dumps

## Evidence from Logs

### Token Usage:
- Input: 260,923 tokens over 15 iterations = ~17,395 tokens/iteration
- This confirms text/tree IS being sent (otherwise would be ~5k tokens)

### Agent Responses:
```
❌ "Good! I can see the start page..." - describing screenshot
❌ "I can see:" - listing what's visible
❌ "Now I can see the options clearly" - visual description

✅ NEVER MENTIONS: "page text", "found in text", "searched text"
```

## Root Causes

### 1. Instruction-Data Ordering Problem
```
INSTRUCTION: "Read the page text first!"
   ↓ (agent continues reading...)
DATA: [page text appears here]
   ↓ (agent has already processed the instruction)
ACTION: Agent looks at screenshot instead
```

**Fix**: Put the actual text/tree BEFORE the instruction to read it.

### 2. Visual Bias
- Models are trained to describe images
- When both text and image are available, models default to image
- Need STRONGER forcing to use text first

### 3. Weak Enforcement
Current: "You should read the page text first"
Needed: "You MUST print what you found in page text BEFORE taking action"

### 4. Haiku Optimization
- Haiku is optimized for speed/cost
- May be "skimming" text blocks and focusing on image
- Sonnet might follow instructions better

### 5. No Verification Mechanism
- No way to FORCE the agent to prove it read the text
- Need a "thinking step" that requires text acknowledgment

## Proposed Solutions

### Solution 1: Reorder Content Blocks ⭐ BEST
```python
# NEW ORDER:
content = []

# 1. STOP instruction
content.append({"text": "🛑 STOP! READ BELOW FIRST:\n\n"})

# 2. Page text (what agent needs to read)
if page_text:
    content.append({"text": f"**PAGE TEXT:**\n{page_text}\n\n"})

# 3. Accessibility tree
if accessibility_tree:
    content.append({"text": f"**PAGE STRUCTURE:**\n{json.dumps(tree)}\n\n"})

# 4. Now the instructions
content.append({"text": "NOW read your task:\n" + prompt + instructions})

# 5. Screenshot LAST (de-emphasize it)
if screenshot:
    content.append({"image": ...})
```

**Benefits:**
- Agent sees text BEFORE instructions
- Screenshot appears last (less emphasis)
- Natural reading order

**Risks:**
- Might break existing prompt flow
- Need to test carefully

---

### Solution 2: Force Acknowledgment ⭐ GOOD
```python
# Add to instructions:
"""
🚨 MANDATORY FIRST STEP:
Before taking ANY action, you MUST respond with:
"I searched the page text and found: [what you found]"

If you don't do this, the task will FAIL.

Example:
✅ CORRECT: "I searched the page text and found code: AJAF5H. Now I'll enter it."
❌ WRONG: "I can see the page with a form." (didn't search text!)
"""
```

**Benefits:**
- Forces agent to acknowledge reading text
- Easy to implement
- No structural changes needed

**Risks:**
- Agent might fake it
- Adds extra output

---

### Solution 3: Highlight Important Info 🔍
```python
# Pre-process page text to highlight codes:
import re

def highlight_codes(text):
    # Find 6-character codes
    codes = re.findall(r'\b[A-Z0-9]{6}\b', text)

    if codes:
        return f"""
🔍 CODES FOUND IN PAGE TEXT:
{codes}

Full page text:
{text}
"""
    return text
```

**Benefits:**
- Makes codes impossible to miss
- No prompt changes needed
- Works with current flow

**Risks:**
- Might miss codes in different formats
- Adds processing overhead

---

### Solution 4: Use Sonnet Instead of Haiku 🚀
```bash
# Change from:
--model haiku

# To:
--model sonnet
```

**Benefits:**
- Sonnet is more capable
- Better at following complex instructions
- Might actually read text/tree

**Risks:**
- More expensive (~10x)
- Slower (~2x)

---

### Solution 5: Add "Search" Tool 🔧
```python
# Add a new tool:
{
    "type": "search_20250124",
    "name": "search_page",
    "description": "Search page text for patterns"
}

# Agent must use: search_page(pattern="[A-Z0-9]{6}")
```

**Benefits:**
- Forces agent to actively search
- More structured approach
- Clear when search is used

**Risks:**
- Requires new tool implementation
- More complex
- May not be worth the effort

---

### Solution 6: Extended Thinking 🧠
```bash
# Add flag:
--extended-thinking --thinking-budget 20000
```

**Benefits:**
- Agent reasons more carefully
- May notice and use text/tree
- Better instruction following

**Risks:**
- Slower
- More tokens
- May not help if visual bias is strong

## Recommended Approach

### Phase 1: Quick Wins (Try First)
1. ✅ **Add forced acknowledgment** (Solution 2)
2. ✅ **Highlight codes in text** (Solution 3)
3. ✅ **Test with Sonnet** (Solution 4)

### Phase 2: If Quick Wins Don't Work
4. ✅ **Reorder content blocks** (Solution 1)

### Phase 3: Nuclear Option
5. ✅ **Add search tool** (Solution 5)

## Testing Protocol

### For Each Solution:
1. Run agent with same test
2. Check logs for:
   - "searched page text"
   - "found in text"
   - Mentions of specific codes from text
3. Count iterations to complete level 1
4. Measure success rate

### Success Criteria:
- Agent explicitly mentions searching text ✅
- Finds code in 1-2 iterations ✅
- No excessive scrolling ✅
- High success rate (>80%) ✅

## Immediate Next Steps

1. **Implement Solution 2** (force acknowledgment) - 5 minutes
2. **Implement Solution 3** (highlight codes) - 10 minutes
3. **Test with Sonnet** - 2 minutes
4. **Run test and compare** - 5 minutes

If all three fail → implement Solution 1 (reorder blocks)

---

## Code Locations to Modify

### For Solution 2 (Force Acknowledgment):
- File: `src/cua/providers/bedrock.py`
- Line: ~230 (add to hybrid_guide)

### For Solution 3 (Highlight Codes):
- File: `src/cua/browser/playwright_controller.py`
- Method: `get_page_text()`
- Add regex highlighting

### For Solution 1 (Reorder):
- File: `src/cua/providers/bedrock.py`
- Method: `create_initial_request()` - lines 278-296
- Method: `create_continuation_request()` - lines 388-404

