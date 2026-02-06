# Agent Not Using Accessibility Tree - CRITICAL FIX

## Problem

The agent was **completely ignoring the accessibility tree** despite it being sent with every request. Looking at the logs:

```
Iteration 3: "I need to scroll in this modal to find the actual 6-character code"
Iteration 31-56: Scrolling through sections 36-100, then back up, looking for code
NO MENTION of the accessibility tree at all in agent's reasoning
```

**The agent:**
- Scrolled aimlessly for 56 iterations
- Never mentioned or read the accessibility tree
- Only used screenshots
- Got stuck in endless scroll loops
- Failed to complete even Level 1

**The root cause:** The hybrid guide instructions were buried in the middle of a long prompt and weren't strong enough. The agent was trained to rely on screenshots and simply ignored the tree.

## Solution Implemented

### 1. Made Instructions IMPOSSIBLE to Ignore

**New instruction format** (all three providers):

```
═══════════════════════════════════════════════════════════════
🚨 CRITICAL: YOU HAVE AN ACCESSIBILITY TREE - USE IT FIRST! 🚨
═══════════════════════════════════════════════════════════════

Before you do ANYTHING else (especially scrolling), you MUST:

**STEP 1: READ THE ACCESSIBILITY TREE BELOW**
The tree shows ALL page content instantly - codes, buttons, text, everything!
You do NOT need to scroll to find content - it's already in the tree!

**EXAMPLE - Finding a 6-character code:**
Instead of scrolling for 40 iterations like this:
  ❌ "Let me scroll down to find the code"
  ❌ "Let me scroll more to look for the code"
  ❌ "Still scrolling to find the code..."
  ❌ [wastes 40 iterations and fails]

Do this in 1 iteration:
  ✅ "I'll check the accessibility tree for text containing a 6-character code"
  ✅ Found in tree: {"role": "text", "name": "Your code: AJAF5H"}
  ✅ "The code is AJAF5H, now I'll enter it"
  ✅ [Success in 3 iterations!]
```

### 2. Visual Emphasis

Used visual elements to grab attention:
- **Banner with emojis** (🚨)
- **Separators** (═══════════)
- **Clear examples** showing wrong vs right approach
- **Explicit comparison** of 40 failed iterations vs 3 successful ones

### 3. Positioned Instructions FIRST

The accessibility tree instructions now appear **before** everything else in the prompt, so the agent sees them immediately.

### 4. Added Negative Examples

Explicitly showed what **NOT** to do:
```
**NEVER DO THIS:**
❌ Scroll up and down looking for content
❌ Click random buttons hoping to reveal content
❌ Ignore the accessibility tree and only use screenshots
❌ Scroll through 100 sections of filler content
```

### 5. Added Positive Examples

Showed exactly what to do:
```
**ALWAYS DO THIS:**
✅ Read accessibility tree FIRST to find what you need
✅ Use screenshot for coordinates only
✅ Be efficient - find content in tree instantly
```

## Ctrl+C Video Recording Fix

### Problem
When user pressed Ctrl+C to abort, the video recording was lost because the browser was terminated immediately.

### Solution
Added `KeyboardInterrupt` exception handling:

```python
except KeyboardInterrupt:
    self.console.print(f"\n[bold yellow]⚠ Interrupted by user (Ctrl+C)[/bold yellow]")
    # ... return TaskResult with video_path ...

finally:
    if self.browser:
        # Get video path before stopping
        video_path = None
        if self.record_video:
            video_path = self.browser.get_video_path()
            if video_path:
                self.console.print(f"[yellow]Saving video recording...[/yellow]")

        self.browser.stop()  # This finalizes the video

        if video_path:
            self.console.print(f"[green]✓ Video saved: {video_path}[/green]")
```

**Now when you press Ctrl+C:**
1. Agent catches KeyboardInterrupt
2. Prints "Interrupted by user (Ctrl+C)"
3. Gets video path before stopping browser
4. Stops browser (this finalizes the video file)
5. Prints video path so you know where it was saved
6. Returns TaskResult with the video path

## Files Modified

### 1. src/cua/providers/bedrock.py
- Lines 166-265: Completely rewrote hybrid guide with massive visual emphasis
- Added banner, examples, negative/positive lists
- Positioned tree instructions FIRST in the prompt

### 2. src/cua/providers/claude.py
- Lines 46-142: Same strong tree-first instructions
- Visual emphasis and examples

### 3. src/cua/providers/openai.py
- Lines 45-96: Condensed but equally strong tree-first instructions
- Visual emphasis and examples

### 4. src/cua/agent/loop.py
- Lines 280-310: Added KeyboardInterrupt handling
- Enhanced finally block to save video before exit
- Prints video path after successful save

## Expected Behavior After Fix

### Before (what you saw in logs):

```
Iteration 1: Click START
Iteration 2: Close popup
Iteration 3: "I need to scroll to find the code"
Iteration 4-30: Scrolling, scrolling, scrolling...
Iteration 31-56: Still scrolling, scrolling, scrolling...
Result: Aborted, no code found, 56 iterations wasted
```

### After (expected):

```
Iteration 1: Click START
Iteration 2: Close popup
Iteration 3: "I'll read the accessibility tree to find the code"
            "Tree shows: {'role': 'text', 'name': 'Code: AJAF5H'}"
            "The code is AJAF5H"
Iteration 4: Enter AJAF5H in input field
Iteration 5: Click Submit
Iteration 6: Level 1 complete, moving to Level 2
Result: ✓ Success in 6 iterations
```

## Why This Should Work

### 1. Visual Impact
The banner format (🚨 + separators) is **visually striking** and hard to ignore.

### 2. Explicit Comparison
Showing "40 failed iterations vs 3 successful iterations" gives the agent a concrete reason to use the tree.

### 3. Positioned First
Tree instructions appear **before** other instructions, so agent reads them first.

### 4. Negative Examples
Explicitly listing behaviors to avoid (scrolling 100 sections, clicking random buttons) matches exactly what the agent was doing wrong.

### 5. Repetition
The message is repeated multiple times in different ways:
- In the banner
- In the example
- In the NEVER/ALWAYS lists
- In the mandatory workflow

## Testing

Run the same test again:

```bash
cua --provider bedrock --model haiku \
    --url "serene-frangipane-7fd25b.netlify.app" \
    --max-iterations 100 \
    --zoom 85 \
    --context-window-size 5 \
    --enable-caching \
    --use-accessibility-tree \
    --record-video \
    --prompt "Complete the Browser Navigation Challenge..."
```

**What to look for in logs:**
1. ✅ Agent mentions "reading accessibility tree" or "checking tree"
2. ✅ Agent finds code in tree: "Tree shows: Code: ABC123"
3. ✅ Agent enters code without scrolling
4. ✅ Completes levels in 5-10 iterations instead of 40+
5. ✅ If you press Ctrl+C, video is saved and path is printed

**If agent STILL ignores tree:**
Check logs for any mention of "accessibility tree" in reasoning. If not mentioned at all, the model may need even stronger prompting or a different approach (like putting the tree in a separate message).

## Ctrl+C Testing

1. Start a task with `--record-video`
2. Let it run for a few iterations
3. Press Ctrl+C
4. You should see:
   ```
   ⚠ Interrupted by user (Ctrl+C)
   Stopping browser...
   Saving video recording...
   ✓ Video saved: /path/to/video.webm
   ```
5. Video file should exist and be playable

## Summary

**Accessibility Tree Fix:**
- Added massive visual emphasis (🚨 banners, separators)
- Positioned tree instructions FIRST
- Showed explicit examples of 40 failed iterations vs 3 successful
- Added NEVER/ALWAYS lists
- Made instructions impossible to ignore

**Ctrl+C Video Fix:**
- Added KeyboardInterrupt exception handling
- Video path is retrieved before stopping browser
- Browser.stop() finalizes the video
- Video path is printed after save
- Video is preserved even when user aborts

The agent should now use the tree automatically and complete tasks in 5-10 iterations instead of 40+. Videos will be saved even if you press Ctrl+C.
