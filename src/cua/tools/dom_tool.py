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

    def execute(self, action: DOMAction) -> Dict[str, Any]:
        """Execute a DOM manipulation action.

        Args:
            action: DOMAction to execute

        Returns:
            Dictionary with action result
        """
        if action.action_type == "click_selector":
            if not action.selector:
                return {"success": False, "error": "Missing selector parameter"}
            return self.browser.click_selector(action.selector)

        elif action.action_type == "fill_selector":
            if not action.selector or not action.text:
                return {"success": False, "error": "Missing selector or text parameter"}
            return self.browser.fill_selector(action.selector, action.text)

        elif action.action_type == "get_info":
            if not action.selector:
                return {"success": False, "error": "Missing selector parameter"}
            return self.browser.get_element_info(action.selector)

        elif action.action_type == "find_selectors":
            if not action.search_text:
                return {"success": False, "error": "Missing search_text parameter"}
            return self.browser.find_selectors_by_text(action.search_text, action.limit)

        elif action.action_type == "evaluate_js":
            if not action.script:
                return {"success": False, "error": "Missing script parameter"}
            return self.browser.evaluate_js(action.script)

        else:
            return {"success": False, "error": f"Unknown action type: {action.action_type}"}


# Tool definition for AI providers
DOM_TOOL_DEFINITION = {
    "name": "dom_manipulation",
    "description": """Direct DOM manipulation tool using CSS selectors. MUCH faster and more reliable than coordinate-based clicking.

**When to use:**
- When you know the element's text content (find selectors by text)
- When you have a CSS selector (click or fill directly)
- For any form filling (much more reliable than coordinates)
- To check if elements exist before acting

**Actions:**
1. find_selectors: Find CSS selectors for elements containing specific text
2. click_selector: Click element by CSS selector (no coordinates needed!)
3. fill_selector: Fill input by CSS selector (no coordinates needed!)
4. get_info: Get element information (check if exists, visible, get text/value)
5. evaluate_js: Execute JavaScript (advanced use)

**Example workflow:**
1. Use find_selectors with text="Submit" to find submit button selector
2. Use click_selector with the selector found in step 1
3. Much faster than: screenshot → find coordinates → click coordinates""",
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
