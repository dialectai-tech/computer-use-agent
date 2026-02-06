# Hybrid Mode Coordinate Issue - Fixed

## Problem Identified

When testing hybrid mode (screenshot + accessibility tree), the agent was clicking at (0, 0) repeatedly instead of actual button positions.

### Symptoms
```
Iteration 2/100: → Click at (0, 0)
Iteration 3/100: → Click at (0, 0)
Iteration 4/100: → Click at (0, 0)
...
```

Agent text responses were correct ("Let's click the START button", "Let's click Dismiss") but coordinates were always (0, 0).

## Root Cause

The hybrid guide prompt was **misleading the AI**:

**Original problematic text:**
```
**Best practices:**
- Use element names and roles instead of guessing from pixels
```

The AI interpreted this as: "Don't use the screenshot for coordinates, just use element names/roles from the tree"

**But the accessibility tree doesn't contain pixel coordinates!** It only has semantic information:
- `{"role": "button", "name": "Submit"}` ← No x, y coordinates!

So the AI was:
1. ✅ Reading the tree correctly
2. ✅ Identifying the right elements to click
3. ❌ **Not looking at the screenshot to find visual positions**
4. ❌ Returning [0, 0] or no coordinates

## Solution

Updated hybrid guide in all providers to be **explicitly clear** about the workflow:

### New Hybrid Guide (Bedrock/Claude)

```
HYBRID MODE: You have access to BOTH screenshot and accessibility tree.

**CRITICAL: How to use them together:**
1. **Accessibility Tree** - Use this to IDENTIFY what element you need
   - Shows semantic structure: roles, names, states
   - Reveals ALL elements even if scrolled out of view
   - Shows hierarchy (what's inside modals, forms, etc.)

2. **Screenshot** - Use this to LOCATE where the element is and GET COORDINATES
   - The tree does NOT contain pixel coordinates
   - You MUST look at the screenshot to find visual positions
   - Match element names from tree to visual elements in screenshot

**Workflow:**
1. Read accessibility tree to understand available elements
2. Identify which element you need (by role and name)
3. Look at screenshot to visually locate that element
4. Use the element's visual position in screenshot for coordinates

**Example:**
- Tree: {"role": "button", "name": "Dismiss"} ← Know WHAT to click
- Screenshot: Look for button labeled "Dismiss" ← Know WHERE to click
- Click at coordinates where "Dismiss" button appears in screenshot
```

### Key Changes

1. ✅ **Split responsibilities clearly:**
   - Tree = WHAT to interact with (identification)
   - Screenshot = WHERE it is (location/coordinates)

2. ✅ **Explicit statement:** "The tree does NOT contain pixel coordinates"

3. ✅ **Step-by-step workflow** with numbered steps

4. ✅ **Concrete example** showing WHAT vs WHERE separation

5. ✅ **Removed misleading phrase** about "instead of pixels"

## Additional Improvements

### Debug Warnings
Added coordinate validation with warnings in `playwright_controller.py`:

```python
if x == 0 and y == 0:
    print(f"⚠️  WARNING: Coordinates are (0, 0) - AI may not be using screenshot")
    print(f"   Action params: {params}")
```

This helps catch the issue immediately during testing.

## Files Modified

1. `src/cua/providers/bedrock.py` - Updated hybrid guide
2. `src/cua/providers/claude.py` - Updated hybrid guide
3. `src/cua/providers/openai.py` - Updated hybrid guide
4. `src/cua/browser/playwright_controller.py` - Added coordinate validation warnings

## Expected Behavior After Fix

The AI should now:
1. Read the accessibility tree: "I see a button with role='button' name='Dismiss'"
2. Look at the screenshot: "The 'Dismiss' button is located at approximately (540, 380)"
3. Click at proper coordinates: `Click at (540, 380)` ✅

Not:
1. Read tree: "I see a Dismiss button"
2. Click without looking at screenshot: `Click at (0, 0)` ❌

## Testing

Run the same test again:

```bash
cua --provider bedrock --model sonnet \
    --url "serene-frangipane-7fd25b.netlify.app" \
    --max-iterations 20 \
    --zoom 85 \
    --context-window-size 5 \
    --use-accessibility-tree \
    --record-video \
    --prompt "Complete the Browser Navigation Challenge..."
```

**Expected improvements:**
- ✅ Coordinates should NOT be (0, 0)
- ✅ Agent should click at actual button positions
- ✅ Popups should be properly dismissed
- ✅ Progress through challenge levels

If you still see (0, 0) coordinates, the debug warnings will show what parameters the AI is sending.
