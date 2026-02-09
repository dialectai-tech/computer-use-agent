"""DOM Manipulation Tool - Direct selector-based actions."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class DOMAction:
    """DOM manipulation action."""
    action_type: str  # click_selector, fill_selector, get_info, find_selectors, evaluate_js
    selector: Optional[str] = None
    text: Optional[str] = None
    search_text: Optional[str] = None
    script: Optional[str] = None
    limit: int = 10


class DOMTool:
    """Tool for DOM manipulation via CSS selectors and JavaScript."""

    def __init__(self, browser):
        """Initialize DOM tool.

        Args:
            browser: PlaywrightController instance
        """
        self.browser = browser

    @staticmethod
    def validate_selector(selector: str) -> Dict[str, Any]:
        """Validate CSS selector and provide helpful errors.

        Args:
            selector: CSS selector string to validate

        Returns:
            Dictionary with 'valid' bool and 'error' string if invalid
        """
        if not selector or not selector.strip():
            return {"valid": False, "error": "Selector is empty"}

        selector = selector.strip()

        # Check for jQuery-style pseudo-selectors that aren't valid CSS
        # Use word boundaries to avoid false positives (e.g., :first-child is valid, :first is not)
        import re

        jquery_patterns = [
            (r":contains\(", "Use text search or find_selectors instead. Example: find_selectors(search_text='START')"),
            (r":has\(", "Not valid CSS. Use descendant selectors like 'parent child' instead"),
            (r":first(?!-)", "Use :first-child or :first-of-type instead"),  # :first but not :first-child
            (r":last(?!-)", "Use :last-child or :last-of-type instead"),  # :last but not :last-child
            (r":eq\(", "Not valid CSS. Use :nth-child() or specific selectors instead"),
            (r":gt\(", "Not valid CSS. Use :nth-child() instead"),
            (r":lt\(", "Not valid CSS. Use :nth-child() instead"),
            (r":even\b", "Not valid CSS. Use :nth-child(even) instead"),
            (r":odd\b", "Not valid CSS. Use :nth-child(odd) instead"),
            (r":visible\b", "Not valid CSS. Most elements are visible by default"),
            (r":hidden\b", "Not valid CSS. Use [hidden] or check style directly"),
        ]

        for pattern, suggestion in jquery_patterns:
            if re.search(pattern, selector, re.IGNORECASE):
                # Extract matched pattern for error message
                match = re.search(pattern, selector, re.IGNORECASE)
                matched_text = match.group(0) if match else pattern
                return {
                    "valid": False,
                    "error": f"Invalid jQuery selector '{matched_text}' detected. {suggestion}"
                }

        # Check for overly generic single-tag selectors
        single_tag_pattern = selector.lower().strip()
        generic_tags = ['input', 'button', 'div', 'span', 'a', 'select', 'textarea', 'form', 'img']

        if single_tag_pattern in generic_tags:
            return {
                "valid": False,
                "error": f"Selector '{selector}' is too generic (matches multiple elements). Use find_selectors to get specific selector with ID/class. Example: button#submit or button.primary"
            }

        # Selector looks valid
        return {"valid": True}

    def execute(self, action: DOMAction) -> Dict[str, Any]:
        """Execute a DOM manipulation action.

        Args:
            action: DOMAction to execute

        Returns:
            Dictionary with action result
        """
        # Normalize action type (accept common variations for better UX)
        action_type = action.action_type
        if action_type == "click":
            action_type = "click_selector"
        elif action_type == "fill":
            action_type = "fill_selector"

        if action_type == "click_selector":
            if not action.selector:
                return {"success": False, "error": "Missing selector parameter"}

            # Validate selector
            validation = self.validate_selector(action.selector)
            if not validation["valid"]:
                return {"success": False, "error": validation["error"]}

            return self.browser.click_selector(action.selector)

        elif action_type == "fill_selector":
            if not action.selector or not action.text:
                return {"success": False, "error": "Missing selector or text parameter"}

            # Validate selector
            validation = self.validate_selector(action.selector)
            if not validation["valid"]:
                return {"success": False, "error": validation["error"]}

            return self.browser.fill_selector(action.selector, action.text)

        elif action_type == "get_info":
            if not action.selector:
                return {"success": False, "error": "Missing selector parameter"}

            # Validate selector
            validation = self.validate_selector(action.selector)
            if not validation["valid"]:
                return {"success": False, "error": validation["error"]}

            return self.browser.get_element_info(action.selector)

        elif action_type == "find_selectors":
            if not action.search_text:
                return {"success": False, "error": "Missing search_text parameter"}

            result = self.browser.find_selectors_by_text(action.search_text, action.limit)

            # Enhance response with recommended selector
            if result.get("success") and result.get("matches"):
                matches = result["matches"]

                # Matches are already sorted by score (highest first)
                # Pick the best match (first in list = highest score)
                best_match = matches[0]
                best_selector = best_match.get("selector", "")
                matched_text = best_match.get("matchedText", best_match.get("text", ""))[:60]

                result["recommended_selector"] = best_selector
                result["message"] = f"Found {len(matches)} match(es). Best: {best_selector}"

                # Add helpful summary with matched text for verification
                if len(matches) == 1:
                    result["summary"] = f"✓ Found 1 element: \"{matched_text}\". Next: click_selector(selector='{best_selector}')"
                else:
                    # Show first 3 matches for context
                    match_list = []
                    for i, m in enumerate(matches[:3]):
                        text = m.get("matchedText", m.get("text", ""))[:40]
                        match_list.append(f"{i+1}. \"{text}\" → {m.get('selector', 'unknown')}")

                    matches_str = "\n".join(match_list)
                    if len(matches) > 3:
                        matches_str += f"\n... and {len(matches) - 3} more"

                    result["summary"] = f"✓ Found {len(matches)} elements. Using highest-scored match:\n{matches_str}\n\nRecommended: click_selector(selector='{best_selector}')"

            return result

        elif action_type == "evaluate_js":
            if not action.script:
                return {"success": False, "error": "Missing script parameter"}
            return self.browser.evaluate_js(action.script)

        else:
            return {
                "success": False,
                "error": f"Invalid action_type '{action.action_type}'. Must be one of: find_selectors, click_selector, fill_selector, get_info, evaluate_js"
            }


# Tool definition for AI providers
DOM_TOOL_DEFINITION = {
    "name": "dom_manipulation",
    "description": """Direct DOM manipulation using CSS selectors - 10-100x faster than coordinates!

**REQUIRED Parameters:**
- action_type: (string, REQUIRED) Must be EXACTLY one of these 5 values:
  1. "find_selectors" - Find CSS selectors by searching for text
  2. "click_selector" - Click element using CSS selector (NOT "click"!)
  3. "fill_selector" - Fill input field using CSS selector (NOT "fill"!)
  4. "get_info" - Get element info (visible, text, value)
  5. "evaluate_js" - Run JavaScript (advanced, rarely needed)

**Example Usage:**

1. Find selectors by text:
   dom_manipulation(action_type="find_selectors", search_text="START", limit=5)
   Returns: {"recommended_selector": "button#start", "matches": [...]}

2. Click using selector:
   dom_manipulation(action_type="click_selector", selector="button#start")
   Returns: ✓ Element clicked

3. Fill input field:
   dom_manipulation(action_type="fill_selector", selector="input#code", text="ABC123")
   Returns: ✓ Text entered

**Common Workflow:**
Step 1: find_selectors(search_text="START")
        → Get recommended_selector: "button#start"
Step 2: click_selector(selector="button#start")
        → Click the button

**IMPORTANT**: Always use the "recommended_selector" from find_selectors results!

**Selector Requirements:**
✓ MUST be valid CSS selectors (NOT jQuery pseudo-selectors!)
✓ DO use: #id, .class, [attribute="value"], :first-child, :nth-child(2), element.class
✗ DON'T use: :contains(), :has(), :visible, :hidden, :eq(), :first, :last, :even, :odd

**Good Selectors:**
✓ button#submit (ID selector)
✓ .btn-primary (class selector)
✓ input[type="text"] (attribute selector)
✓ div.container > p:first-child (child selector)
✓ button.start-btn (element + class)

**Bad Selectors (will FAIL):**
✗ button:contains('text') (jQuery, not CSS!)
✗ input (too generic, use find_selectors first)
✗ div:has(span) (jQuery, not CSS!)
✗ :visible (jQuery, not CSS!)
✗ button:eq(0) (jQuery, not CSS!)

**Common Mistakes:**
❌ action_type="click" (should be "click_selector")
❌ action_type="fill" (should be "fill_selector")
❌ Missing required parameters (selector for click/fill, search_text for find)
❌ Using generic selectors like "button" alone (use find_selectors first!)
✓ action_type="click_selector" with selector="button#start"
✓ Using recommended_selector from find_selectors results

**When to Use:**
✓ When you need to interact with elements by CSS selector (faster than coordinates)
✓ When find_selectors found a good selector for you
✗ Don't use if you don't have a valid CSS selector - use coordinates instead""",
    "input_schema": {
        "type": "object",
        "properties": {
            "action_type": {
                "type": "string",
                "enum": ["find_selectors", "click_selector", "fill_selector", "get_info", "evaluate_js"],
                "description": "REQUIRED: Type of DOM action. Must be EXACTLY: 'find_selectors', 'click_selector', 'fill_selector', 'get_info', or 'evaluate_js'"
            },
            "selector": {
                "type": "string",
                "description": "REQUIRED for click_selector, fill_selector, get_info: Valid CSS selector (e.g., 'button#start', '.btn-primary', 'input[type=\"text\"]'). Use recommended_selector from find_selectors results."
            },
            "text": {
                "type": "string",
                "description": "REQUIRED for fill_selector: Text to type into input field (e.g., 'ABC123', 'john@example.com')."
            },
            "search_text": {
                "type": "string",
                "description": "REQUIRED for find_selectors: Text to search for on page (e.g., 'START', 'Submit', 'Enter code'). Returns CSS selectors containing this text."
            },
            "script": {
                "type": "string",
                "description": "REQUIRED for evaluate_js: JavaScript code to execute. Use sparingly - prefer other action types."
            },
            "limit": {
                "type": "integer",
                "description": "OPTIONAL for find_selectors: Maximum number of results to return (default: 10, range: 1-50).",
                "default": 10
            }
        },
        "required": ["action_type"]
    }
}
