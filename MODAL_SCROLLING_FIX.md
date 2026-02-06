# Modal Scrolling Fix

## Problem

Agent was unable to scroll within modal/dialog elements to reveal hidden content (like radio buttons). When trying to scroll a modal, the background page would scroll instead of the modal's internal content.

**Symptoms:**
- Agent executed scroll actions inside modals
- Background page scrolled successfully
- Modal internal content never scrolled
- Agent tried multiple approaches (scroll, PageDown, arrow keys) but none worked

**Root Cause:**
The scroll implementation in `playwright_controller.py` used `window.scrollBy()` which only scrolls the main page window, not individual scrollable elements like modals or dialogs.

```python
# Old implementation - WRONG
self.page.evaluate(f"window.scrollBy({scroll_x}, {scroll_y})")
```

## Solution

### 1. Enhanced Scroll Implementation

Updated `src/cua/browser/playwright_controller.py` (lines 289-347) to implement **element-specific scrolling**:

**How it works:**
1. Gets the element at the scroll coordinates
2. Walks up the DOM tree to find the nearest scrollable ancestor
3. Checks if element has `overflow: scroll/auto` and content that overflows
4. Scrolls that specific element instead of the window
5. Falls back to window scroll only if no scrollable container is found

**JavaScript logic:**
```javascript
// Get element at coordinates
const element = document.elementFromPoint(x, y);

// Find nearest scrollable ancestor
let scrollableElement = element;
while (scrollableElement && scrollableElement !== document.documentElement) {
    const style = window.getComputedStyle(scrollableElement);
    const overflowY = style.overflowY;

    // Check if scrollable
    const isScrollableY = (overflowY === 'scroll' || overflowY === 'auto') &&
                        scrollableElement.scrollHeight > scrollableElement.clientHeight;

    if (isScrollableY) {
        // Scroll this element, not the window
        scrollableElement.scrollBy(scroll_x, scroll_y);
        return;
    }

    scrollableElement = scrollableElement.parentElement;
}

// Fallback: scroll window if no scrollable ancestor found
window.scrollBy(scroll_x, scroll_y);
```

### 2. Updated Agent Prompts

Added explicit modal scrolling instructions to all three providers:

#### src/cua/providers/bedrock.py
#### src/cua/providers/claude.py
#### src/cua/providers/openai.py

**New instructions added:**
```
**SCROLLING IN MODALS/DIALOGS:**
When you need to scroll within a modal, dialog, or any scrollable container:
1. Position your mouse INSIDE the modal/container area (provide coordinates within the modal bounds)
2. Use the scroll action with those coordinates
3. The system will automatically find and scroll the scrollable container at that position
4. Take a screenshot after scrolling to verify the modal content scrolled

Example: If a modal is centered at x=500, y=300, use {"action": "scroll", "coordinate": [500, 300]}
```

## What Changed

### Before:
- `window.scrollBy()` always scrolled the main page
- Agent couldn't scroll modal internal content
- Background page scrolled when agent tried to scroll modals

### After:
- JavaScript finds scrollable element at coordinates
- Scrolls the specific container (modal, dialog, div, etc.)
- Falls back to window scroll only when appropriate

## Files Modified

1. **src/cua/browser/playwright_controller.py**
   - Line 289-347: Rewrote scroll action implementation
   - Added JavaScript to find and scroll scrollable elements
   - Returns debug info about what was scrolled

2. **src/cua/providers/bedrock.py**
   - Line 166-195: Added modal scrolling instructions

3. **src/cua/providers/claude.py**
   - Line 46-67: Added modal scrolling instructions

4. **src/cua/providers/openai.py**
   - Line 45-54: Added modal scrolling instructions

## Testing

The fix should resolve the Level 2 modal scrolling issue where:
- Modal displays text "Please select an option above"
- Radio buttons are scrolled out of view within the modal
- Agent needs to scroll the modal container to reveal the radio buttons

**Expected behavior after fix:**
1. Agent takes screenshot and sees modal with partial content
2. Agent uses accessibility tree to identify radio buttons exist but aren't visible
3. Agent positions scroll coordinates INSIDE the modal bounds (e.g., center of modal)
4. Agent executes scroll action
5. JavaScript finds the modal's scrollable container and scrolls IT specifically
6. Agent takes screenshot to verify modal content scrolled
7. Agent can now see and interact with previously hidden radio buttons

## Additional Benefits

This fix also improves scrolling for:
- Scrollable `<div>` containers
- Sidebar panels with overflow
- Nested scrollable regions
- Any element with `overflow: scroll` or `overflow: auto`

The implementation is smart enough to:
- Find the correct scrollable ancestor
- Avoid scrolling non-scrollable elements
- Fall back to window scroll when appropriate
- Work with all scroll directions and amounts

## Debugging

The scroll action now returns additional information:
```python
{
    "success": True,
    "action": "scroll",
    "x": 500,
    "y": 300,
    "scroll_result": {
        "scrolled": "element",  # or "window"
        "element": "DIV",       # HTML tag of scrolled element
        "class": "modal-body",  # CSS class
        "id": "content"         # Element ID
    }
}
```

This helps verify that the correct element was scrolled.
