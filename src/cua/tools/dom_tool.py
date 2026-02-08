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
        jquery_patterns = [
            (":contains(", "Use text search or find_selectors instead. Example: find_selectors(search_text='START')"),
            (":has(", "Not valid CSS. Use descendant selectors like 'parent child' instead"),
            (":first", "Use :first-child or :first-of-type instead"),
            (":last", "Use :last-child or :last-of-type instead"),
            (":eq(", "Not valid CSS. Use :nth-child() or specific selectors instead"),
            (":gt(", "Not valid CSS. Use :nth-child() instead"),
            (":lt(", "Not valid CSS. Use :nth-child() instead"),
            (":even", "Not valid CSS. Use :nth-child(even) instead"),
            (":odd", "Not valid CSS. Use :nth-child(odd) instead"),
            (":visible", "Not valid CSS. Most elements are visible by default"),
            (":hidden", "Not valid CSS. Use [hidden] or check style directly"),
            (":checked", "Valid CSS! But use input:checked for checkboxes/radios"),
        ]

        for pattern, suggestion in jquery_patterns:
            if pattern in selector.lower():
                return {
                    "valid": False,
                    "error": f"Invalid jQuery selector '{pattern}' detected. {suggestion}"
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

                # Pick best selector (prefer ID, then class, then tag)
                best_selector = None
                for match in matches:
                    selector = match.get("selector", "")
                    if '#' in selector:
                        best_selector = selector
                        break
                    elif '.' in selector and not best_selector:
                        best_selector = selector
                    elif not best_selector:
                        best_selector = selector

                result["recommended_selector"] = best_selector
                result["message"] = f"Found {len(matches)} match(es). Use: {best_selector}"

                # Add helpful summary
                if len(matches) == 1:
                    result["summary"] = f"✓ Found 1 element. Next: click_selector(selector='{best_selector}')"
                else:
                    result["summary"] = f"✓ Found {len(matches)} elements. Use first: click_selector(selector='{best_selector}')"

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

**IMPORTANT**: action_type must be EXACTLY one of these 5 values:
1. "find_selectors" - Find CSS selectors by searching for text
2. "click_selector" - Click using CSS selector (NOT "click"!)
3. "fill_selector" - Fill input using CSS selector (NOT "fill"!)
4. "get_info" - Get element info (visible, text, value)
5. "evaluate_js" - Run JavaScript (advanced)

**Common workflow:**
1. find_selectors(search_text="START") → returns {"recommended_selector": "button#start"}
2. Use the recommended_selector: click_selector(selector="button#start")

**Important**: find_selectors returns a "recommended_selector" field - USE IT in the next action!

**Selector Requirements:**
- MUST be valid CSS selectors (NOT jQuery!)
- DON'T use: :contains(), :has(), :visible, :hidden, :eq(), :first, :last, :even, :odd
- DO use: #id, .class, [attribute], :first-child, :nth-child(), element.class
- AVOID generic tags alone (button, input, div) - use find_selectors to get specific selector
- GOOD: button#submit, .btn-primary, input[type="text"], div.container > p:first-child
- BAD: button:contains('text'), input, div:has(span), :visible

**Note**: Use "click_selector" not "click", and "fill_selector" not "fill"!""",
    "input_schema": {
        "type": "object",
        "properties": {
            "action_type": {
                "type": "string",
                "enum": ["find_selectors", "click_selector", "fill_selector", "get_info", "evaluate_js"],
                "description": "Type of DOM action to perform"
            },
            "selector": {
                "type": "string",
                "description": "CSS selector (required for click_selector, fill_selector, get_info)"
            },
            "text": {
                "type": "string",
                "description": "Text to fill (required for fill_selector)"
            },
            "search_text": {
                "type": "string",
                "description": "Text to search for (required for find_selectors)"
            },
            "script": {
                "type": "string",
                "description": "JavaScript to execute (required for evaluate_js)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results for find_selectors (default: 10)",
                "default": 10
            }
        },
        "required": ["action_type"]
    }
}
