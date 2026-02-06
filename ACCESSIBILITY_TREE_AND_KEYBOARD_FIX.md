# Accessibility Tree Priority & Keyboard Shortcuts Fix

## Problems Identified

### 1. Agent Not Using Accessibility Tree
- Agent was scrolling aimlessly looking for codes/elements
- Only relying on screenshots for finding content
- Accessibility tree was being sent but ignored
- Result: Inefficient, many iterations wasted scrolling

### 2. Keyboard Shortcuts Not Working
- `Home` and `Ctrl+Home` not working
- `Space` bar not available for page scrolling
- Keyboard combinations not supported
- Result: Agent couldn't navigate efficiently

### 3. Agent Confusion
- Spending 40+ iterations looking for a code
- Scrolling up and down repeatedly
- Trying wrong buttons and getting confused
- No systematic search strategy

## Root Causes

### 1. Hybrid Guide Didn't Emphasize Tree Priority
The old hybrid guide said:
```
1. Use accessibility tree to IDENTIFY elements
2. Use screenshot to LOCATE and get coordinates
```

But agents interpreted this as: "Both are equal, I'll just use screenshots since they're easier to understand."

### 2. Keyboard Shortcuts Not Implemented
The `_map_key()` function didn't support:
- Keyboard combinations (Ctrl+Home, Shift+Space, etc.)
- Case-insensitive key matching
- Some special keys

### 3. Key Press Handler Didn't Parse Combinations
The key press action handler treated all keys as single keys, not combinations.

## Solutions Implemented

### 1. Emphasized Accessibility Tree Priority

**Updated all three providers** (bedrock.py, claude.py, openai.py) with new hybrid guide:

```
**CRITICAL: ALWAYS START WITH THE ACCESSIBILITY TREE!**

**MANDATORY WORKFLOW (DO THIS EVERY TIME):**
1. FIRST: Read the accessibility tree to understand what's on the page
   - Find all available elements by role (button, link, textbox, etc.)
   - Identify element names, text content, and states
   - See the complete page structure, including content scrolled out of view
   - Look for the information you need (codes, buttons, inputs, etc.)

2. SECOND: Use the screenshot to find visual coordinates
   - After identifying the target element in the tree, look at the screenshot
   - Find the element's visual position in the screenshot
   - Get the [x, y] pixel coordinates from the screenshot
```

**Why this matters:**
- The tree shows ALL page content, even if scrolled out of view
- Finding a code in the tree is instant vs scrolling for 40 iterations
- Much more efficient and systematic

**Example - Finding a code:**
```
Old way (screenshot-only):
- Scroll down, look for code
- Scroll more, still looking
- Scroll up, maybe missed it?
- Scroll down again
- Click random buttons hoping to reveal code
- 40 iterations, still confused

New way (tree-first):
- Read accessibility tree
- See: {"role": "text", "name": "Code: ABC123"}
- Done! Code found instantly
- 1 iteration
```

### 2. Implemented Keyboard Shortcuts

**Updated src/cua/browser/playwright_controller.py (lines 276-315):**

Added support for keyboard combinations:
```python
if "+" in key_text:
    # Parse key combination (e.g., "Control+Home", "ctrl+a")
    parts = [p.strip().lower() for p in key_text.split("+")]
    modifiers = []
    main_key = parts[-1]

    # Parse modifiers
    for part in parts[:-1]:
        if part in ["ctrl", "control"]:
            modifiers.append("Control")
        elif part in ["shift"]:
            modifiers.append("Shift")
        # ... etc

    # Press modifiers down
    for mod in modifiers:
        self.page.keyboard.down(mod)

    # Press main key
    self.page.keyboard.press(main_key)

    # Release modifiers
    for mod in reversed(modifiers):
        self.page.keyboard.up(mod)
```

**Updated key mapping** (lines 416-463):
- Made case-insensitive (home, Home, HOME all work)
- Added Space bar mapping
- Added F1-F12 keys
- Added Insert key

### 3. Added Keyboard Shortcuts Guide to Prompts

**Added to all three providers:**

```
**KEYBOARD SHORTCUTS AND NAVIGATION:**
You have access to powerful keyboard shortcuts for efficient navigation:
- Space - Scroll down one page viewport (fastest way to scan through content)
- Shift+Space - Scroll up one page viewport
- Home - Jump to top of page/element instantly
- End - Jump to bottom of page/element instantly
- Ctrl+Home - Jump to absolute beginning of page
- Ctrl+End - Jump to absolute end of page
- PageDown - Scroll down one page
- PageUp - Scroll up one page

**Use these shortcuts instead of multiple scroll actions!**
```

## What Changed

### Before:
```
Agent behavior:
1. Take screenshot
2. Look for code in screenshot
3. Don't see it, scroll down
4. Take screenshot
5. Look again
6. Scroll down
7-40. Repeat scrolling, still confused
```

### After:
```
Agent behavior:
1. Take screenshot
2. Read accessibility tree FIRST
3. Find code in tree: "Code: ABC123"
4. Done! (or if need to click, use screenshot for coordinates)
```

### Before (keyboard):
```
Agent: "Let me use Home to go to top"
Action: {"action": "key", "text": "Home"}
Result: Nothing happens

Agent: "Let me use Ctrl+Home"
Action: {"action": "key", "text": "Ctrl+Home"}
Result: Key "Ctrl+Home" not found, nothing happens
```

### After (keyboard):
```
Agent: "Let me use Home to go to top"
Action: {"action": "key", "text": "Home"}
Result: ✓ Jumps to top of page

Agent: "Let me use Ctrl+Home"
Action: {"action": "key", "text": "Ctrl+Home"}
Result: ✓ Parses as Control modifier + Home key, jumps to top

Agent: "Let me use Space to scroll down"
Action: {"action": "key", "text": "Space"}
Result: ✓ Scrolls down one page viewport
```

## Files Modified

### 1. src/cua/browser/playwright_controller.py
- Lines 276-315: Added keyboard combination parser
- Lines 416-463: Enhanced key mapping (case-insensitive, more keys)

### 2. src/cua/providers/bedrock.py
- Lines 181-229: Updated hybrid guide to emphasize tree priority
- Lines 232-248: Added keyboard shortcuts guide

### 3. src/cua/providers/claude.py
- Lines 59-100: Updated hybrid guide to emphasize tree priority
- Lines 103-118: Added keyboard shortcuts guide

### 4. src/cua/providers/openai.py
- Lines 55-72: Updated hybrid guide to emphasize tree priority
- Lines 75-84: Added keyboard shortcuts guide

## Expected Behavior After Fix

### Finding a Code (e.g., Level 1)

**Old behavior (40 iterations):**
1. Scroll down looking for code
2. Scroll more
3. Click random buttons
4. Scroll up
5. Scroll down again
6. Get confused
7-40. Keep scrolling

**New behavior (1-2 iterations):**
1. Take screenshot
2. Read accessibility tree
3. Find in tree: `{"role": "text", "name": "Your code is: AJAF5H"}`
4. Enter code "AJAF5H" in input field
5. Submit
6. Done!

### Navigating Long Pages

**Old behavior:**
1. Scroll down
2. Take screenshot
3. Scroll down
4. Take screenshot
5-20. Repeat many times

**New behavior:**
1. Take screenshot
2. Read tree to understand page structure
3. If need to scroll: Press Space to scroll one page at a time
4. Or use Home/End to jump to top/bottom
5. Much faster, fewer iterations

### Using Keyboard Shortcuts

**Now available:**
- `Space` - Fast page-down scrolling
- `Shift+Space` - Fast page-up scrolling
- `Home` - Jump to top
- `End` - Jump to bottom
- `Ctrl+Home` - Jump to absolute beginning
- `Ctrl+End` - Jump to absolute end
- `Ctrl+A` - Select all text
- `Ctrl+C` - Copy
- `Ctrl+V` - Paste
- And many more combinations

## Testing

The same test that took 41 iterations and failed should now:

1. **Start faster**: Agent reads tree immediately to understand page structure
2. **Find code faster**: Code is in the accessibility tree, no scrolling needed
3. **Navigate efficiently**: Uses keyboard shortcuts instead of multiple scrolls
4. **Complete successfully**: Should complete Level 1 in 5-10 iterations instead of 40+

## Benefits

### Efficiency
- **Before**: 40+ iterations to find a code
- **After**: 1-2 iterations to find a code

### Token Usage
- **Before**: Hundreds of thousands of tokens from repeated screenshots while scrolling
- **After**: Significantly fewer iterations = fewer tokens

### Success Rate
- **Before**: Agent getting confused, hitting max iterations, failing
- **After**: Agent finds content systematically, completes tasks successfully

### Speed
- **Before**: Multiple scroll actions, waiting for screenshots each time
- **After**: Keyboard shortcuts (Home/End/Space) for instant navigation

## Implementation Notes

### Accessibility Tree Structure

The tree contains everything the agent needs:
```json
{
  "role": "document",
  "children": [
    {
      "role": "text",
      "name": "Your code is: AJAF5H"  // <-- Code is here!
    },
    {
      "role": "textbox",
      "name": "Enter code here"
    },
    {
      "role": "button",
      "name": "Submit Code"
    }
  ]
}
```

Agent can find the code by searching for text nodes in the tree!

### Keyboard Combination Syntax

All these formats work:
- `"Control+Home"`
- `"ctrl+home"`
- `"Ctrl+Home"`
- `"CTRL+HOME"`

Modifiers supported:
- Control/Ctrl
- Shift
- Alt
- Meta/Cmd/Command

### Case-Insensitive Keys

All these work:
- `"Home"`, `"home"`, `"HOME"`
- `"Space"`, `"space"`, `"SPACE"`
- `"Enter"`, `"enter"`, `"ENTER"`

## Debug Output

If agent still has issues, check logs for:
```
"⚠️  WARNING: Coordinates are (0, 0)"  // Agent not using screenshot for coords
"⚠️  WARNING: No coordinates found"     // Agent not providing coordinates
```

Also check if agent's reasoning mentions:
- "Reading accessibility tree..." ✓ Good!
- "Looking at screenshot..." (without reading tree first) ✗ Bad!

## Summary

The agent now:
1. ✓ **Reads accessibility tree FIRST** to find content
2. ✓ **Uses screenshot SECOND** only for coordinates
3. ✓ **Has keyboard shortcuts** (Space, Home, End, Ctrl+combos)
4. ✓ **Navigates efficiently** instead of scrolling aimlessly
5. ✓ **Finds codes instantly** instead of scrolling for 40 iterations

This should dramatically improve success rate, reduce iterations, and lower token costs.
