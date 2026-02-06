# Issues Found & Proposed Solutions

## 🔴 CRITICAL ISSUES IDENTIFIED

### Issue #1: Instruction-Data Ordering Problem
**Problem**: The prompt says "READ TEXT FIRST" but the text appears in a LATER content block.

```
Current Flow:
Block 1: "Read the page text first!" ← instruction
Block 2: [accessibility tree]         ← agent glances
Block 3: [page text]                  ← agent glances
Block 4: [screenshot]                 ← agent FOCUSES HERE ❌
```

**Result**: Agent reads instruction, then by the time it sees text, it's ready to act and just looks at screenshot.

---

### Issue #2: Visual Bias
**Problem**: Models are trained to describe images. When text + image are both available, model defaults to image.

**Evidence**: Agent always says "I can see..." (screenshot-based) instead of "I found in text..." (text-based)

---

### Issue #3: No Enforcement
**Problem**: Instructions say "should use text" but nothing FORCES the agent to prove it read the text.

**Result**: Agent ignores the suggestion and does what's easier (look at screenshot).

---

### Issue #4: Haiku May Be Too Fast
**Problem**: Haiku is optimized for speed/cost. May be "skimming" text and focusing on image.

**Evidence**: 17k tokens/iteration (text IS being sent) but agent doesn't use it.

---

## 🎯 PROPOSED SOLUTIONS (Pick Your Path)

### ⭐ QUICK WINS (Try These First)

#### Solution A: Force Acknowledgment
**Effort**: 5 minutes | **Risk**: Low | **Effectiveness**: Medium-High

Add this to the prompt:
```python
"""
🚨 MANDATORY PROTOCOL:
Before taking ANY action, you MUST state:
'SEARCH RESULT: I found [X] in the page text.'

Example:
✅ "SEARCH RESULT: I found code AJAF5H in page text at line 23. Now entering it."
❌ "I can see a form on the page." ← FAILS! Didn't search text!

If you don't search the text first, you will fail the task.
"""
```

**Pros**: Easy, forces acknowledgment, no structural changes
**Cons**: Agent might fake it (say it searched without actually searching)

---

#### Solution B: Highlight Codes Automatically
**Effort**: 10 minutes | **Risk**: Low | **Effectiveness**: High

Pre-process page text to make codes unmissable:

```python
def highlight_codes(text):
    import re
    codes = re.findall(r'\b[A-Z0-9]{6}\b', text)

    if codes:
        return f"""
🔍🔍🔍 CODES DETECTED IN PAGE TEXT 🔍🔍🔍
Codes found: {', '.join(codes)}

⚠️ USE THESE CODES! Don't scroll looking for them!

Full page text below:
{text}
"""
    return text
```

**Pros**: Impossible to miss, no prompt changes, works with current flow
**Cons**: Might miss non-standard code formats

---

#### Solution C: Test with Sonnet
**Effort**: 30 seconds | **Risk**: None | **Effectiveness**: ?

```bash
# Just change the model:
--model sonnet    # instead of haiku
```

**Pros**: Sonnet is more capable, better instruction-following, easy to test
**Cons**: 10x more expensive, 2x slower

---

### 🔧 STRUCTURAL FIX (If Quick Wins Fail)

#### Solution D: Reorder Content Blocks
**Effort**: 20 minutes | **Risk**: Medium | **Effectiveness**: Very High

Change the order so text appears BEFORE instructions:

```python
content = []

# 1. Stop instruction
content.append({"text": "🛑 STOP! READ THESE SECTIONS FIRST:\n\n"})

# 2. Page text (agent reads this first)
content.append({"text": f"📄 PAGE TEXT:\n{page_text}\n\n"})

# 3. Accessibility tree
content.append({"text": f"🌲 PAGE STRUCTURE:\n{tree}\n\n"})

# 4. Now the task
content.append({"text": f"📋 YOUR TASK:\n{prompt}\n\n{instructions}"})

# 5. Screenshot last (de-emphasized)
content.append({"image": screenshot})
```

**Pros**: Natural reading order, text appears before instructions, screenshot de-emphasized
**Cons**: Requires testing, might break existing flow, more complex changes

---

### 🚀 ADVANCED OPTIONS

#### Solution E: Add Extended Thinking
**Effort**: 0 minutes (flag exists) | **Risk**: Low | **Effectiveness**: Medium

```bash
--extended-thinking --thinking-budget 20000
```

**Pros**: More careful reasoning, better instruction following
**Cons**: Slower, more tokens, may not overcome visual bias

---

#### Solution F: Add Search Tool
**Effort**: 2 hours | **Risk**: High | **Effectiveness**: Very High

Implement a dedicated `search_page` tool that the agent must use.

**Pros**: Forces active searching, very structured
**Cons**: Complex, time-consuming, overkill for this problem

---

## 📊 RECOMMENDATION

### Try in This Order:

1. **Solution B** (Highlight Codes) - 10 min
   - Easy, high effectiveness
   - Makes codes unmissable
   - Works with existing flow

2. **Solution A** (Force Acknowledgment) - 5 min
   - Quick to implement
   - Adds verification
   - Low risk

3. **Solution C** (Test Sonnet) - 30 sec
   - No code changes
   - Sonnet might just work better
   - Worth testing

4. **If 1-3 fail → Solution D** (Reorder) - 20 min
   - More invasive but likely to work
   - Fixes root cause

5. **If all fail → Solution E + D** - 30 min
   - Extended thinking + reordering
   - Nuclear option

---

## 🧪 IMPLEMENTATION PLAN

### Step 1: Implement B + A (15 minutes)
```python
# In playwright_controller.py:
def get_page_text(self):
    text = self.page.evaluate(...)  # existing code
    return self._highlight_codes(text)

def _highlight_codes(self, text):
    import re
    codes = re.findall(r'\b[A-Z0-9]{6}\b', text)
    if codes:
        return f"🔍 CODES FOUND: {', '.join(codes)}\n\n{text}"
    return text

# In bedrock.py:
hybrid_guide += """
🚨 MANDATORY: Before any action, respond with:
'SEARCH: Found [X] in page text'
"""
```

### Step 2: Test (5 minutes)
```bash
# Run same test
cua --provider bedrock --model haiku ...
```

### Step 3: Check Logs
Look for:
- ✅ "SEARCH: Found AJAF5H"
- ✅ Mentions of "page text"
- ✅ Quick code finding (1-2 iterations)

### Step 4: If Still Fails → Try Sonnet
```bash
cua --provider bedrock --model sonnet ...
```

### Step 5: If Still Fails → Implement Solution D
- Reorder content blocks
- Test again

---

## 🎯 EXPECTED OUTCOMES

### After Fix:
```
Iteration 1/100
  → Take screenshot
  SEARCH: Found code AJAF5H in page text. Located at "Your code is: AJAF5H"

Iteration 2/100
  → Click at (640, 300)
  Clicking on the input field to enter the code

Iteration 3/100
  → Type: "AJAF5H"
  Entering the code I found in the page text

Iteration 4/100
  → Click at (700, 350)
  Clicking Submit button

Iteration 5/100
  ✓ Level 1 complete!
```

---

## 💡 WHY THIS WILL WORK

### Solution B (Highlight):
- Codes are impossible to miss
- Appears at top of text section
- Agent HAS to see it

### Solution A (Force Acknowledgment):
- Agent must explicitly state what it found
- Creates verification step
- Harder to ignore

### Together:
- Code highlighted → Agent sees it
- Forced acknowledgment → Agent must mention it
- Both reinforce each other

---

## ⚠️ POTENTIAL GOTCHAS

1. **Agent might still ignore it**
   - If so → Solution D (reorder)

2. **Code format might vary**
   - Regex might miss some formats
   - Can add more patterns

3. **Haiku might be too simple**
   - Try Sonnet if Haiku fails

4. **Prompt might be too long**
   - Already at 17k tokens
   - Watch for truncation

---

## 📝 WANT ME TO IMPLEMENT?

I can implement any combination of these solutions. My recommendation:

**Option 1 (Quick)**: Implement B + A (15 min)
**Option 2 (Thorough)**: Implement B + A + D (35 min)
**Option 3 (Test First)**: Just try Sonnet (30 sec)

Which would you like to try?
