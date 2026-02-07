# Current System - Complete Walkthrough

## Overview: What Actually Happens

The system sends the AI **three types of data** on every iteration:
1. **Accessibility Tree** (JSON structure)
2. **Page Text** (extracted visible text)
3. **Screenshot** (PNG image)

The AI responds with **tool use actions** (click, type, scroll, etc.)

---

## The Flow: Start to Finish

### Step 1: User Runs Command
```bash
cua --provider bedrock --model haiku \
  --url "serene-frangipane-7fd25b.netlify.app" \
  --use-accessibility-tree \
  --prompt "Complete the challenge..."
```

### Step 2: Browser Launches
- Playwright starts Chromium
- Navigates to URL
- Sets zoom to 85%
- Waits for page load

### Step 3: Initial Data Collection
Three things happen simultaneously:

#### A. Take Screenshot
```python
screenshot = self.browser.take_screenshot()
# Returns: base64-encoded PNG of viewport
```

#### B. Extract Page Text
```python
page_text = self.browser.get_page_text()
# Returns: String of all visible text
```

**Example output:**
```
Browser Navigation Challenge
Step 1 of 30
Enter Code to Proceed to Step 2:
[input field]
Move On
Advance
Click Here
Section 1
This is filler content
Section 2
More filler content
...
```

#### C. Get Accessibility Tree
```python
accessibility_tree = self.browser.get_accessibility_tree()
# Returns: JSON structure of page elements
```

**Example output:**
```json
{
  "role": "WebArea",
  "name": "Browser Navigation Challenge",
  "children": [
    {
      "role": "heading",
      "name": "Browser Navigation Challenge",
      "level": 1
    },
    {
      "role": "heading",
      "name": "Step 1 of 30",
      "level": 2
    },
    {
      "role": "textbox",
      "name": "Enter Code to Proceed to Step 2:"
    },
    {
      "role": "button",
      "name": "Move On"
    },
    {
      "role": "button",
      "name": "Advance"
    },
    {
      "role": "text",
      "name": "Section 1"
    }
  ]
}
```

### Step 4: Message Construction

The system builds a message with **4 content blocks** sent to Bedrock:

#### Block 1: Instructions (Text)
```python
content = [{
    "text": """
    [USER'S PROMPT]
    Complete the Browser Navigation Challenge...

    [AUTONOMOUS INSTRUCTIONS]
    You are an AUTONOMOUS agent. Take actions, observe results...

    [HYBRID GUIDE]
    🚨 CRITICAL: YOU HAVE PAGE TEXT & ACCESSIBILITY TREE! 🚨
    ⚠️ STOP! Before you scroll even ONCE, you MUST:
    **STEP 1: READ THE PAGE TEXT BELOW**
    **STEP 2: READ THE ACCESSIBILITY TREE BELOW**
    These show EVERYTHING on the page - you do NOT need to scroll!
    [detailed examples and instructions...]

    [TOOL USAGE GUIDE]
    When using the computer tool with click actions, you MUST provide coordinates...
    [keyboard shortcuts info...]
    """
}]
```

**Size**: ~5,000 tokens

#### Block 2: Accessibility Tree (Text)
```python
content.append({
    "text": """
    **Accessibility Tree (Page Structure):**
    ```json
    {
      "role": "WebArea",
      "name": "Browser Navigation Challenge",
      "children": [...]
    }
    ```
    """
})
```

**Size**: ~2,000-5,000 tokens (depends on page complexity)

#### Block 3: Page Text (Text)
```python
content.append({
    "text": """
    **Page Text (All Visible Text):**
    ```
    Browser Navigation Challenge
    Step 1 of 30
    Enter Code to Proceed to Step 2:
    [all the text content...]
    ```
    """
})
```

**Size**: ~2,000-10,000 tokens (truncated at 10k chars)

#### Block 4: Screenshot (Image)
```python
content.append({
    "image": {
        "format": "png",
        "source": {"bytes": screenshot_bytes}
    }
})
```

**Size**: ~5,000-8,000 tokens (depending on image complexity)

### Step 5: API Call to Bedrock

```python
response = client.converse(
    modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    messages=[
        {
            "role": "user",
            "content": [block1, block2, block3, block4]
        }
    ],
    toolConfig={...},
    additionalModelRequestFields={
        "anthropic_beta": ["computer-use-2025-01-24"],
        "tools": [
            {
                "type": "computer_20250124",
                "name": "computer",
                "display_width_px": 1024,
                "display_height_px": 768
            }
        ]
    }
)
```

**Total input**: ~17,000-20,000 tokens per request

### Step 6: AI Processing

The AI (Haiku) processes the message:

**What it sees:**
1. Long instructions block ("Read text first! Use tree!")
2. JSON structure (accessibility tree)
3. Text dump (page text)
4. Image (screenshot)

**What it typically does:**
- Reads instructions (gets the idea)
- Glances at JSON (too much structure)
- Glances at text (wall of text)
- **Focuses on image** (visual, easy to understand)
- Generates response based primarily on screenshot

**Example AI reasoning:**
```
Internal thought process:
"Okay, I need to complete a challenge. I should use page text first.
Let me see... [sees JSON]... that's complex...
[sees text dump]... lots of text...
[sees screenshot]... AH! I can SEE the page clearly!
The screenshot shows buttons, a form, popups...
Let me describe what I see and take action."
```

### Step 7: AI Response

The AI returns **tool use** actions:

```json
{
  "output": {
    "message": {
      "content": [
        {
          "text": "Good! I can see the start page with a START button. Let me click it to begin."
        },
        {
          "toolUse": {
            "toolUseId": "abc123",
            "name": "computer",
            "input": {
              "action": "left_click",
              "coordinate": [640, 385]
            }
          }
        }
      ]
    }
  }
}
```

**Note**: The text response describes what it sees in the **screenshot**, not what it found in the **page text**.

### Step 8: Action Execution

```python
# Extract action from response
action = Action(
    type=ActionType.CLICK,
    params={"coordinate": [640, 385]}
)

# Execute in browser
self.browser.execute_action(action)
# → Clicks at (640, 385)
```

### Step 9: Loop Back to Step 3

After action execution:
- Take new screenshot
- Extract new page text
- Get new accessibility tree
- Send as tool result to continue conversation

```python
response = client.converse(
    modelId="...",
    messages=[
        # Previous user message
        {"role": "user", "content": [...]},
        # Previous assistant response
        {"role": "assistant", "content": [...]},
        # New tool result
        {
            "role": "user",
            "content": [{
                "toolResult": {
                    "toolUseId": "abc123",
                    "content": [
                        {"text": "[Updated Accessibility Tree]"},
                        {"text": "[Updated Page Text]"},
                        {"image": {"bytes": new_screenshot}}
                    ]
                }
            }]
        }
    ]
)
```

---

## What the AI Can Do: Available Actions

The AI has access to the `computer` tool with these actions:

### 1. Screenshot
```json
{"action": "screenshot"}
```
Returns current viewport image.

### 2. Click
```json
{"action": "left_click", "coordinate": [x, y]}
```
Clicks at pixel coordinates.

### 3. Double Click
```json
{"action": "double_click", "coordinate": [x, y]}
```

### 4. Right Click
```json
{"action": "right_click", "coordinate": [x, y]}
```

### 5. Type
```json
{"action": "type", "text": "Hello"}
```
Types text at current focus.

### 6. Key Press
```json
{"action": "key", "text": "Return"}
{"action": "key", "text": "Space"}
{"action": "key", "text": "Ctrl+Home"}
```

**Available keys:**
- Return/Enter
- Space
- Tab
- Backspace
- Delete
- Escape
- Arrow keys (ArrowUp, ArrowDown, ArrowLeft, ArrowRight)
- Page keys (PageDown, PageUp, Home, End)
- Modifiers (Ctrl+X, Shift+X, Alt+X)

### 7. Scroll
```json
{"action": "scroll", "coordinate": [x, y], "scroll_direction": "down", "scroll_amount": 3}
```

The system finds the scrollable element at [x, y] and scrolls it.

### 8. Wait
```json
{"action": "wait"}
```
Pauses for 2 seconds.

### 9. Mouse Move
```json
{"action": "mouse_move", "coordinate": [x, y]}
```

---

## The Prompts: What Instructions the AI Gets

### 1. User's Task Prompt
Whatever you provide via `--prompt` flag.

### 2. Autonomous Instructions
```
You are an AUTONOMOUS agent. Do NOT ask the user questions or wait for input.
Take actions, observe results via screenshots, and continue until complete.
After EVERY action, take a screenshot to see the result, then decide your next action.
```

**Purpose**: Prevents AI from asking questions or waiting.

### 3. Hybrid Guide (The Big One)
```
═══════════════════════════════════════════════════════════════
🚨 CRITICAL: YOU HAVE PAGE TEXT & ACCESSIBILITY TREE! 🚨
═══════════════════════════════════════════════════════════════

⚠️ STOP! Before you scroll even ONCE, you MUST:

**STEP 1: READ THE PAGE TEXT BELOW (ALL visible text on the page)**
**STEP 2: READ THE ACCESSIBILITY TREE BELOW (ALL page structure)**

These show EVERYTHING on the page - you do NOT need to scroll!

**EXAMPLE - Finding a 6-character code (THE WRONG WAY):**
  ❌ "Let me scroll down to find the code"
  ❌ "Let me scroll more to look for the code"
  ...

**EXAMPLE - Finding a 6-character code (THE RIGHT WAY):**
  ✅ STEP 1: Search PAGE TEXT for any 6-character codes
  ✅ STEP 2: If found in text → locate in screenshot → get coordinates
  ...

**MANDATORY WORKFLOW FOR ANY TASK:**
1. FIRST: Search PAGE TEXT
2. SECOND: Search ACCESSIBILITY TREE
3. THIRD: Use SCREENSHOT for coordinates ONLY

**NEVER DO THIS:**
❌ Scroll up and down looking for content
❌ Press Ctrl+F to search (you already have the text!)
❌ Click random buttons hoping something appears
❌ Ignore the page text and accessibility tree

**ALWAYS DO THIS:**
✅ Search PAGE TEXT first for any text content
✅ Search ACCESSIBILITY TREE second for structure/elements
✅ Use SCREENSHOT third for coordinates
✅ Be efficient - everything is already provided!
```

**Size**: ~2,000 tokens
**Purpose**: Tell AI to use text/tree before screenshot

### 4. Tool Usage Guide
```
**CRITICAL - Tool Usage:**
When using the computer tool with click actions, you MUST provide coordinates:
- ✅ CORRECT: {"action": "left_click", "coordinate": [640, 480]}
- ❌ WRONG: {"action": "click"} (missing coordinate!)

**SCROLLING IN MODALS:**
Position your mouse INSIDE the modal/container area, then scroll at those coordinates.

**KEYBOARD SHORTCUTS:**
- Space - Scroll down one page
- Home/End - Jump to top/bottom
- Ctrl+Home/End - Jump to absolute top/bottom
- PageDown/PageUp - Page navigation
```

**Purpose**: Technical guidance on using tools correctly.

---

## What the AI Actually Sees: Example

### Iteration 1: Initial Request

**Content Block 1 (Text - Instructions):**
```
Complete the Browser Navigation Challenge efficiently. [your full prompt]

You are an AUTONOMOUS agent...

🚨 CRITICAL: YOU HAVE PAGE TEXT & TREE! 🚨
[full hybrid guide]

[tool usage guide]
```

**Content Block 2 (Text - Accessibility Tree):**
```
**Accessibility Tree (Page Structure):**
```json
{
  "role": "WebArea",
  "name": "Browser Navigation Challenge",
  "children": [
    {"role": "heading", "name": "Browser Navigation Challenge", "level": 1},
    {"role": "heading", "name": "A 30-level interactive challenge...", "level": 2},
    {"role": "button", "name": "START"}
  ]
}
```
```

**Content Block 3 (Text - Page Text):**
```
**Page Text (All Visible Text):**
```
Browser Navigation Challenge
A 30-level interactive challenge to test AI agent navigation skills
START
```
```

**Content Block 4 (Image - Screenshot):**
[PNG image showing the start page with START button]

### AI's Response:
```
"Good! I can see the start page with a START button. Let me click it to begin."

Tool use: left_click at [640, 385]
```

**Observation**: AI described the screenshot ("I can see"), not the text ("I found in text").

---

## Why It's Not Working as Intended

### The Design:
1. Send text/tree (data)
2. Tell AI to use text/tree first (instruction)
3. Send screenshot (reference)
4. AI uses text/tree for searching, screenshot for coordinates

### The Reality:
1. ✅ Text/tree are sent (17k tokens proves it)
2. ✅ Instructions are sent (prompts are clear)
3. ✅ Screenshot is sent
4. ❌ AI ignores text/tree and just uses screenshot

### Why AI Ignores Text/Tree:

**Theory 1: Order Matters**
- Instructions come first
- Text/tree come second
- By the time AI sees text/tree, it's already read instructions
- Screenshot appears last, becomes the "freshest" information

**Theory 2: Visual Bias**
- Models are trained on image description tasks
- When both text and image available, models prefer image
- Image is more "natural" to process than JSON + text dump

**Theory 3: Haiku Optimization**
- Haiku is optimized for speed/cost
- May be "skimming" text blocks to save processing time
- Focuses on image as the primary data source

**Theory 4: Prompt Fatigue**
- Too many instructions (~7k tokens of instructions)
- AI gets tired of reading and just looks at image
- "Instruction following" competes with "task completion"

---

## The Current State: Summary

### ✅ What's Working:
- Data collection (text, tree, screenshot) ✅
- Browser automation ✅
- Action execution ✅
- Loop mechanism ✅
- Prompt delivery ✅

### ❌ What's Not Working:
- AI attention/focus ❌
- AI ignores text/tree ❌
- AI defaults to screenshot ❌
- No verification that AI used text ❌

### 🤔 The Core Issue:
**The system PROVIDES the right data, but the AI CHOOSES not to use it.**

This is a **behavioral problem**, not a technical problem.

---

## Possible Reasons (Ranked by Likelihood)

1. **Visual Bias** (90% likely)
   - Models prefer images over text dumps
   - Screenshot is easier to understand than JSON + text
   - This is how models are trained

2. **Order Effects** (70% likely)
   - Instructions → Text → Tree → Image
   - Image is "last" so it's most salient
   - AI processes sequentially, image is freshest

3. **Prompt Overload** (50% likely)
   - Too many instructions (7k tokens)
   - AI skims and focuses on image
   - "Just tell me what to do" vs "read all this"

4. **Haiku Limitations** (40% likely)
   - Haiku is fast/cheap, not deep
   - May not follow complex instructions well
   - Sonnet might work better

5. **No Enforcement** (30% likely)
   - Nothing forces AI to prove it read text
   - AI can "get away with" ignoring instructions
   - No penalty for not using text

---

## What We Know For Sure

1. ✅ Text extraction works (we see it in token counts)
2. ✅ Tree extraction works (we see it in token counts)
3. ✅ Prompts are being sent (full instructions delivered)
4. ✅ AI receives all data (17k tokens/iteration)
5. ❌ AI responds based on screenshot only ("I can see...")
6. ❌ AI never mentions "page text" or "found in text"
7. ❌ AI behavior matches "screenshot-only" approach

---

## The Question

Given all this, what's the best fix?

**Option A**: Force AI to acknowledge text (behavioral nudge)
**Option B**: Highlight important info (make it unmissable)
**Option C**: Reorder blocks (fix the flow)
**Option D**: Try better model (Sonnet vs Haiku)
**Option E**: Combination of above

What's your intuition?
