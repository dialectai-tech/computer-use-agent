"""OpenAI provider implementation."""

from typing import Any, Dict, List, Optional
import re
from openai import OpenAI

from cua.providers.base import ComputerUseProvider, Action, ActionType
from cua.prompts import build_initial_prompt, get_system_prompt, TWO_PHASE_PROMPT_P2


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
        self.system_prompt = get_system_prompt()  # Generic system prompt

    def _strip_transient_content(self, text: str) -> str:
        """Remove transient content marked with [transient]...[/transient] tags.

        Args:
            text: Text potentially containing transient tags

        Returns:
            Text with transient sections removed
        """
        # Remove transient sections
        text = re.sub(r'\[transient\].*?\[/transient\]', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Clean up extra whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        return text.strip()

    def create_initial_request(
        self,
        prompt: str,
        screenshot: Optional[str] = None,
        accessibility_tree: Optional[dict] = None,
        page_text: Optional[str] = None,
        display_width: int = 1024,
        display_height: int = 768,
        use_dom_manipulation: bool = True,
        use_search_tool: bool = True,
        use_find_tool: bool = True
    ) -> Any:
        """Create initial API request to OpenAI.

        Args:
            prompt: User's task description
            screenshot: Base64-encoded screenshot (optional)
            accessibility_tree: Accessibility tree from browser (optional)
            page_text: Extracted page text (optional)
            display_width: Display width in pixels
            display_height: Display height in pixels

        Returns:
            OpenAI API response
        """
        # Build concise, generic prompt
        has_search_tool = page_text is not None or (accessibility_tree and not accessibility_tree.get("error"))
        full_prompt = build_initial_prompt(
            user_prompt=prompt,
            has_search_tool=use_search_tool,
            has_page_text=bool(page_text),
            two_phase=False,
            use_dom_manipulation=use_dom_manipulation,
            use_find_tool=use_find_tool
        )

        # Build initial input content with system prompt + user prompt
        content = [{"type": "input_text", "text": self.system_prompt + "\n\n" + full_prompt}]

        # Add accessibility tree if available (FIRST - so AI reads it before image)
        if accessibility_tree and not accessibility_tree.get("error"):
            import json
            tree_text = f"\n\n**Accessibility Tree (Page Structure):**\n```json\n{json.dumps(accessibility_tree, indent=2)}\n```\n"
            content.append({"type": "input_text", "text": tree_text})

        # Add page text if available (SECOND - full text content)
        if page_text:
            # Truncate if too long to avoid token explosion
            max_text_length = 10000  # ~2500 tokens
            truncated_text = page_text[:max_text_length]
            if len(page_text) > max_text_length:
                truncated_text += f"\n\n[... text truncated, {len(page_text) - max_text_length} more characters ...]"

            text_section = f"\n\n**Page Text (All Visible Text):**\n```\n{truncated_text}\n```\n"
            content.append({"type": "input_text", "text": text_section})

        # Add screenshot last (THIRD - visual reference)
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
            Text content from response (with transient content stripped)
        """
        text_parts = []
        for item in response.output:
            if item.type == "reasoning":
                for summary_item in item.summary:
                    if hasattr(summary_item, "text"):
                        text_parts.append(summary_item.text)
        full_text = " ".join(text_parts)

        # Strip transient content before returning
        return self._strip_transient_content(full_text)

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
