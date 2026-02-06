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
        # Build hybrid guide if accessibility tree is available
        hybrid_guide = ""
        if accessibility_tree and not accessibility_tree.get("error"):
            hybrid_guide = """

HYBRID MODE: You have BOTH screenshot and accessibility tree.

**How to use them:**
1. **Accessibility Tree** - IDENTIFY what element you need (role, name, state)
2. **Screenshot** - LOCATE where it is visually and GET COORDINATES

**CRITICAL:** Tree does NOT have coordinates. You MUST use screenshot for click positions.

**Workflow:**
1. Read tree to identify element (e.g., role="button" name="Submit")
2. Look at screenshot to find that button visually
3. Click at coordinates where you see it in the screenshot
"""

        # Build initial input content
        content = [{"type": "input_text", "text": prompt + hybrid_guide}]

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
