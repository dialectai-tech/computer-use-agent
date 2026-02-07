"""OpenAI provider implementation."""

from typing import Any, Dict, List, Optional
from openai import OpenAI

from cua.providers.base import ComputerUseProvider, Action, ActionType


class OpenAIProvider(ComputerUseProvider):
    """OpenAI provider for computer use automation."""

    def __init__(self, api_key: str, model: str = "computer-use-preview"):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: OpenAI model to use (computer-use-preview)
        """
        super().__init__(api_key, model)
        self.client = OpenAI(api_key=api_key)
        self.last_response_id = None
        self.last_call_id = None

    def create_initial_request(
        self,
        prompt: str,
        screenshot: Optional[str] = None,
        accessibility_tree: Optional[dict] = None,
        page_text: Optional[str] = None,
        display_width: int = 1024,
        display_height: int = 768
    ) -> Any:
        """Create initial API request to OpenAI.

        Args:
            prompt: User's task description
            screenshot: Base64-encoded screenshot (optional)
            accessibility_tree: Accessibility tree from browser (optional)
            display_width: Display width in pixels
            display_height: Display height in pixels

        Returns:
            OpenAI API response
        """
        # Build autonomous agent instructions - START WITH ACCESSIBILITY TREE!
        autonomous_instructions = """

**AUTONOMOUS AGENT MODE:**
You are an AUTONOMOUS agent. Take actions, observe results via screenshots, and continue until complete. Do NOT ask the user for input. After each action, take a screenshot to see the result."""

        # CRITICAL: Put accessibility tree guide FIRST if available
        hybrid_guide = ""
        if accessibility_tree and not accessibility_tree.get("error"):
            hybrid_guide = """

═══════════════════════════════════════════════════════════════
🚨 CRITICAL: YOU HAVE AN ACCESSIBILITY TREE - USE IT FIRST! 🚨
═══════════════════════════════════════════════════════════════

**STEP 1: READ THE ACCESSIBILITY TREE BELOW**
The tree shows ALL page content instantly!

**EXAMPLE - Finding a 6-character code:**
❌ DON'T: Scroll 40 times looking for code
✅ DO: Check tree, find {"role": "text", "name": "Code: ABC123"}, done!

**MANDATORY WORKFLOW:**
1. FIRST: Search accessibility tree for what you need
2. SECOND: Use screenshot ONLY for coordinates

**NEVER:**
❌ Scroll aimlessly looking for content
❌ Ignore the tree and only use screenshots

**ALWAYS:**
✅ Read tree FIRST to find content
✅ Use screenshot for coordinates only
═══════════════════════════════════════════════════════════════
"""

        tool_usage_guide = """

**CRITICAL - Tool Usage:**
Click actions MUST include coordinates: {"action": "click", "x": 640, "y": 480}
Look at screenshot to find element position.

**SCROLLING IN MODALS/DIALOGS:**
To scroll within a modal or dialog: Position coordinates INSIDE the modal area, then use scroll action. The system will scroll the modal container at that position. Take a screenshot after to verify.

**KEYBOARD SHORTCUTS:**
Use keyboard shortcuts for efficient navigation:
- Space - Scroll down one page (fast scanning)
- Home/Ctrl+Home - Jump to top instantly
- End/Ctrl+End - Jump to bottom instantly
- PageDown/PageUp - Scroll by page

Use these instead of multiple scroll actions!"""

        # Build initial input content
        content = [{"type": "input_text", "text": prompt + autonomous_instructions + hybrid_guide + tool_usage_guide}]

        # Add accessibility tree if available
        if accessibility_tree and not accessibility_tree.get("error"):
            import json
            tree_text = f"\n\nAccessibility Tree:\n```json\n{json.dumps(accessibility_tree, indent=2)}\n```"
            content.append({"type": "input_text", "text": tree_text})

        if screenshot:
            content.append({
                "type": "input_image",
                "image_url": f"data:image/png;base64,{screenshot}"
            })

        # Create request with computer use tool
        response = self.client.responses.create(
            model=self.model,
            tools=[{
                "type": "computer_use_preview",
                "display_width": display_width,
                "display_height": display_height,
                "environment": "browser"
            }],
            input=[{
                "role": "user",
                "content": content
            }],
            reasoning={"summary": "concise"},
            truncation="auto"
        )

        self.last_response_id = response.id
        return response

    def create_continuation_request(
        self,
        screenshot: str,
        accessibility_tree: Optional[dict] = None,
        page_text: Optional[str] = None,
        search_results: Optional[List] = None,
        action_result: Optional[Dict[str, Any]] = None,
        display_width: int = 1024,
        display_height: int = 768
    ) -> Any:
        """Create continuation request with tool results.

        Args:
            screenshot: Base64-encoded screenshot
            accessibility_tree: Accessibility tree from browser (optional)
            action_result: Result from previous action execution
            display_width: Display width in pixels
            display_height: Display height in pixels

        Returns:
            OpenAI API response
        """
        if not self.last_call_id:
            raise ValueError("No previous call_id available")

        # Build output - include accessibility tree if available
        output_items = []

        if accessibility_tree and not accessibility_tree.get("error"):
            import json
            tree_text = f"Updated Accessibility Tree:\n```json\n{json.dumps(accessibility_tree, indent=2)}\n```"
            output_items.append({
                "type": "input_text",
                "text": tree_text
            })

        output_items.append({
            "type": "input_image",
            "image_url": f"data:image/png;base64,{screenshot}"
        })

        # Create continuation request using previous_response_id
        response = self.client.responses.create(
            model=self.model,
            previous_response_id=self.last_response_id,
            tools=[{
                "type": "computer_use_preview",
                "display_width": display_width,
                "display_height": display_height,
                "environment": "browser"
            }],
            input=[{
                "call_id": self.last_call_id,
                "type": "computer_call_output",
                "output": output_items
            }],
            reasoning={"summary": "concise"},
            truncation="auto"
        )

        self.last_response_id = response.id
        return response

    def extract_actions(self, response: Any) -> List[Action]:
        """Extract actions from OpenAI API response.

        Args:
            response: OpenAI API response

        Returns:
            List of actions to execute
        """
        actions = []

        for item in response.output:
            if item.type == "computer_call":
                # Store call_id for next request
                self.last_call_id = item.call_id

                action_type = self._map_action_type(item.action.type)
                if action_type:
                    # Convert OpenAI action format to our format
                    params = self._convert_action_params(item.action)
                    action = Action(
                        type=action_type,
                        params=params,
                        id=item.call_id
                    )
                    actions.append(action)

        return actions

    def is_task_complete(self, response: Any) -> bool:
        """Check if task is complete.

        Args:
            response: OpenAI API response

        Returns:
            True if task is complete (no computer_call)
        """
        for item in response.output:
            if item.type == "computer_call":
                return False
        return True

    def get_response_text(self, response: Any) -> str:
        """Extract text content from response.

        Args:
            response: OpenAI API response

        Returns:
            Text content from response
        """
        text_parts = []
        for item in response.output:
            if item.type == "reasoning":
                for summary_item in item.summary:
                    if hasattr(summary_item, "text"):
                        text_parts.append(summary_item.text)
        return " ".join(text_parts)

    def _map_action_type(self, action_type_str: str) -> Optional[ActionType]:
        """Map OpenAI action type to ActionType enum.

        Args:
            action_type_str: Action type string from OpenAI

        Returns:
            Corresponding ActionType or None
        """
        mapping = {
            "screenshot": ActionType.SCREENSHOT,
            "click": ActionType.CLICK,
            "double_click": ActionType.DOUBLE_CLICK,
            "type": ActionType.TYPE,
            "keypress": ActionType.KEYPRESS,
            "scroll": ActionType.SCROLL,
            "wait": ActionType.WAIT,
        }
        return mapping.get(action_type_str)

    def _convert_action_params(self, action) -> Dict[str, Any]:
        """Convert OpenAI action format to unified params format.

        Args:
            action: OpenAI action object

        Returns:
            Dictionary of action parameters
        """
        params = {"action": action.type}

        # Map common parameters
        if hasattr(action, "x") and hasattr(action, "y"):
            params["coordinate"] = [action.x, action.y]
            params["x"] = action.x
            params["y"] = action.y

        if hasattr(action, "button"):
            params["button"] = action.button

        if hasattr(action, "text"):
            params["text"] = action.text

        if hasattr(action, "keys"):
            params["keys"] = action.keys

        if hasattr(action, "scroll_x") and hasattr(action, "scroll_y"):
            params["scroll_x"] = action.scroll_x
            params["scroll_y"] = action.scroll_y

        return params
