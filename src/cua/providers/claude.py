"""Claude (Anthropic) provider implementation."""

from typing import Any, Dict, List, Optional
import anthropic

from cua.providers.base import ComputerUseProvider, Action, ActionType


class ClaudeProvider(ComputerUseProvider):
    """Claude provider for computer use automation."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        """Initialize Claude provider.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
        """
        super().__init__(api_key, model)
        self.client = anthropic.Anthropic(api_key=api_key)
        self.messages = []
        self.last_response = None

    def create_initial_request(
        self,
        prompt: str,
        screenshot: Optional[str] = None,
        display_width: int = 1280,
        display_height: int = 720
    ) -> Any:
        """Create initial API request to Claude.

        Args:
            prompt: User's task description
            screenshot: Base64-encoded screenshot (optional)
            display_width: Display width in pixels
            display_height: Display height in pixels

        Returns:
            Claude API response
        """
        # Build initial message content
        content = [{"type": "text", "text": prompt}]

        if screenshot:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": screenshot
                }
            })

        self.messages = [{"role": "user", "content": content}]

        # Create request with computer use tool
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=2048,
            tools=[
                {
                    "type": "computer_20250124",
                    "name": "computer",
                    "display_width_px": display_width,
                    "display_height_px": display_height,
                    "display_number": 1,
                },
                {
                    "type": "bash_20250124",
                    "name": "bash"
                }
            ],
            messages=self.messages,
            betas=["computer-use-2025-01-24"]
        )

        self.last_response = response
        # Add assistant response to conversation
        self.messages.append({
            "role": "assistant",
            "content": response.content
        })

        return response

    def create_continuation_request(
        self,
        screenshot: str,
        action_result: Optional[Dict[str, Any]] = None,
        display_width: int = 1280,
        display_height: int = 720
    ) -> Any:
        """Create continuation request with tool results.

        Args:
            screenshot: Base64-encoded screenshot
            action_result: Result from previous action execution
            display_width: Display width in pixels
            display_height: Display height in pixels

        Returns:
            Claude API response
        """
        # Build tool results
        tool_results = []

        if self.last_response:
            for block in self.last_response.content:
                if block.type == "tool_use":
                    tool_result = {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                    }

                    # For computer tool, return screenshot
                    if block.name == "computer":
                        tool_result["content"] = [{
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot
                            }
                        }]
                    elif block.name == "bash":
                        # For bash tool, return command output
                        tool_result["content"] = action_result.get("output", "") if action_result else ""

                    tool_results.append(tool_result)

        # Add tool results to conversation
        self.messages.append({
            "role": "user",
            "content": tool_results
        })

        # Create continuation request
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=2048,
            tools=[
                {
                    "type": "computer_20250124",
                    "name": "computer",
                    "display_width_px": display_width,
                    "display_height_px": display_height,
                    "display_number": 1,
                },
                {
                    "type": "bash_20250124",
                    "name": "bash"
                }
            ],
            messages=self.messages,
            betas=["computer-use-2025-01-24"]
        )

        self.last_response = response
        # Add assistant response to conversation
        self.messages.append({
            "role": "assistant",
            "content": response.content
        })

        return response

    def extract_actions(self, response: Any) -> List[Action]:
        """Extract actions from Claude API response.

        Args:
            response: Claude API response

        Returns:
            List of actions to execute
        """
        actions = []

        for block in response.content:
            if block.type == "tool_use" and block.name == "computer":
                action_type = self._map_action_type(block.input.get("action"))
                if action_type:
                    action = Action(
                        type=action_type,
                        params=block.input,
                        id=block.id
                    )
                    actions.append(action)

        return actions

    def is_task_complete(self, response: Any) -> bool:
        """Check if task is complete.

        Args:
            response: Claude API response

        Returns:
            True if task is complete (no tool use)
        """
        for block in response.content:
            if block.type == "tool_use":
                return False
        return True

    def get_response_text(self, response: Any) -> str:
        """Extract text content from response.

        Args:
            response: Claude API response

        Returns:
            Text content from response
        """
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
        return " ".join(text_parts)

    def _map_action_type(self, action_str: str) -> Optional[ActionType]:
        """Map Claude action string to ActionType enum.

        Args:
            action_str: Action string from Claude

        Returns:
            Corresponding ActionType or None
        """
        mapping = {
            "screenshot": ActionType.SCREENSHOT,
            "left_click": ActionType.CLICK,
            "click": ActionType.CLICK,
            "double_click": ActionType.DOUBLE_CLICK,
            "right_click": ActionType.RIGHT_CLICK,
            "type": ActionType.TYPE,
            "key": ActionType.KEY,
            "scroll": ActionType.SCROLL,
            "wait": ActionType.WAIT,
            "mouse_move": ActionType.MOUSE_MOVE,
        }
        return mapping.get(action_str)
