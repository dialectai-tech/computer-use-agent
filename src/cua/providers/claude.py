"""Claude (Anthropic) provider implementation."""

from typing import Any, Dict, List, Optional
import time
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
        accessibility_tree: Optional[dict] = None,
        display_width: int = 1024,
        display_height: int = 768
    ) -> Any:
        """Create initial API request to Claude.

        Args:
            prompt: User's task description
            screenshot: Base64-encoded screenshot (optional)
            accessibility_tree: Accessibility tree from browser (optional)
            display_width: Display width in pixels
            display_height: Display height in pixels

        Returns:
            Claude API response
        """
        # Build initial message content with autonomous agent instructions
        autonomous_instructions = """

**AUTONOMOUS AGENT MODE:**
You are an AUTONOMOUS agent. Do NOT ask the user for input or wait for them to "show you" anything. You can take screenshots yourself to see the current state. After EVERY action, take a screenshot to observe the result, then continue with your next action. Keep working until the task is FULLY complete.

**CRITICAL - Tool Usage:**
When using click actions, you MUST provide coordinates from the screenshot:
- ✅ CORRECT: {"action": "left_click", "coordinate": [640, 480]}
- ❌ WRONG: {"action": "left_click"} (missing coordinate!)

Look at the screenshot to find where the element is, then provide [x, y] pixel coordinates.

**SCROLLING IN MODALS/DIALOGS:**
When you need to scroll within a modal, dialog, or any scrollable container:
1. Position your mouse INSIDE the modal/container area (provide coordinates within the modal bounds)
2. Use the scroll action with those coordinates
3. The system will automatically find and scroll the scrollable container at that position
4. Take a screenshot after scrolling to verify the modal content scrolled

Example: If a modal is centered at x=500, y=300, use {"action": "scroll", "coordinate": [500, 300]}

**KEYBOARD SHORTCUTS AND NAVIGATION:**
You have access to powerful keyboard shortcuts for efficient navigation:
- **Space** - Scroll down one page viewport (fastest way to scan through content)
- **Shift+Space** - Scroll up one page viewport
- **Home** - Jump to top of page/element instantly
- **End** - Jump to bottom of page/element instantly
- **Ctrl+Home** - Jump to absolute beginning of page
- **Ctrl+End** - Jump to absolute end of page
- **PageDown** - Scroll down one page
- **PageUp** - Scroll up one page

**Use these shortcuts instead of multiple scroll actions!** For example:
- To scan a long page: Press Space repeatedly instead of scrolling
- To quickly return to top: Use Home or Ctrl+Home instead of scrolling up many times
- To jump to bottom: Use End or Ctrl+End instead of scrolling down many times"""

        # Build hybrid approach guide
        hybrid_guide = ""
        if accessibility_tree and not accessibility_tree.get("error"):
            hybrid_guide = """

HYBRID MODE: You have access to BOTH screenshot and accessibility tree.

**CRITICAL: ALWAYS START WITH THE ACCESSIBILITY TREE!**

**MANDATORY WORKFLOW (DO THIS EVERY TIME):**
1. **FIRST: Read the accessibility tree** to understand what's on the page
   - Find all available elements by role (button, link, textbox, etc.)
   - Identify element names, text content, and states
   - See the complete page structure, including content scrolled out of view
   - Look for the information you need (codes, buttons, inputs, etc.)

2. **SECOND: Use the screenshot** to find visual coordinates
   - After identifying the target element in the tree, look at the screenshot
   - Find the element's visual position in the screenshot
   - Get the [x, y] pixel coordinates from the screenshot

**Why this matters:**
- The accessibility tree shows ALL page content, even if scrolled out of view
- It reveals text content, element names, and semantic structure
- It's much more efficient than scrolling around blindly
- The screenshot is only needed for coordinates, not for finding content

**Example - Finding a code:**
1. Check accessibility tree for text nodes containing 6-character codes
2. Tree might show: `{"role": "text", "name": "Code: ABC123"}`
3. You now KNOW the code is ABC123 without needing to scroll around!
4. Use screenshot only if you need to click something

**Example - Finding a button:**
1. Tree shows: `{"role": "button", "name": "Submit & Continue"}`
2. Look at screenshot to find that button visually
3. Click at the coordinates where you see "Submit & Continue" button

**DON'T:**
- Don't scroll around aimlessly looking for content
- Don't rely only on screenshots
- Don't ignore the accessibility tree"""

        content = [{"type": "text", "text": prompt + autonomous_instructions + hybrid_guide}]

        # Add accessibility tree if available
        if accessibility_tree and not accessibility_tree.get("error"):
            import json
            tree_text = f"\n\n**Accessibility Tree:**\n```json\n{json.dumps(accessibility_tree, indent=2)}\n```"
            content.append({"type": "text", "text": tree_text})

        if screenshot:
            screenshot_block = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": screenshot
                }
            }

            # Add cache control to screenshot if caching is enabled
            if self.enable_caching:
                screenshot_block["cache_control"] = {"type": "ephemeral"}

            content.append(screenshot_block)

        self.messages = [{"role": "user", "content": content}]

        # Build request parameters
        request_params = {
            "model": self.model,
            "max_tokens": 4096 if self.extended_thinking else 2048,
            "tools": [
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
            "messages": self.messages,
            "betas": ["computer-use-2025-01-24"]
        }

        # Add extended thinking if enabled
        if self.extended_thinking:
            request_params["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget
            }

        # Create request with computer use tool
        start_time = time.time()
        response = self.client.beta.messages.create(**request_params)
        api_time = time.time() - start_time

        # Track stats
        self.stats.add_api_call(api_time)
        if hasattr(response, 'usage'):
            self.stats.add_tokens(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )

            # Track cache stats if available
            if hasattr(response.usage, 'cache_creation_input_tokens'):
                self.stats.cache_creation_tokens += response.usage.cache_creation_input_tokens
            if hasattr(response.usage, 'cache_read_input_tokens'):
                self.stats.cache_read_tokens += response.usage.cache_read_input_tokens

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

                    # For computer tool, return screenshot and optionally accessibility tree
                    if block.name == "computer":
                        content_blocks = []

                        # Add accessibility tree first (so it's read before image)
                        if accessibility_tree and not accessibility_tree.get("error"):
                            import json
                            tree_text = f"**Updated Accessibility Tree:**\n```json\n{json.dumps(accessibility_tree, indent=2)}\n```"
                            content_blocks.append({
                                "type": "text",
                                "text": tree_text
                            })

                        # Add screenshot
                        content_blocks.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot
                            }
                        })

                        tool_result["content"] = content_blocks
                    elif block.name == "bash":
                        # For bash tool, return command output
                        tool_result["content"] = action_result.get("output", "") if action_result else ""

                    tool_results.append(tool_result)

        # Add cache control to last tool result if caching is enabled
        if self.enable_caching and tool_results:
            # Add cache_control to the last tool result's content
            last_result = tool_results[-1]
            if isinstance(last_result.get("content"), list):
                # Image content
                last_result["content"][-1]["cache_control"] = {"type": "ephemeral"}
            elif isinstance(last_result.get("content"), str):
                # Text content - need to convert to list format
                last_result["content"] = [{
                    "type": "text",
                    "text": last_result["content"],
                    "cache_control": {"type": "ephemeral"}
                }]

        # Add tool results to conversation
        self.messages.append({
            "role": "user",
            "content": tool_results
        })

        # Build request parameters
        request_params = {
            "model": self.model,
            "max_tokens": 4096 if self.extended_thinking else 2048,
            "tools": [
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
            "messages": self.messages,
            "betas": ["computer-use-2025-01-24"]
        }

        # Add extended thinking if enabled
        if self.extended_thinking:
            request_params["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget
            }

        # Create continuation request
        start_time = time.time()
        response = self.client.beta.messages.create(**request_params)
        api_time = time.time() - start_time

        # Track stats
        self.stats.add_api_call(api_time)
        if hasattr(response, 'usage'):
            self.stats.add_tokens(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )

            # Track cache stats if available
            if hasattr(response.usage, 'cache_creation_input_tokens'):
                self.stats.cache_creation_tokens += response.usage.cache_creation_input_tokens
            if hasattr(response.usage, 'cache_read_input_tokens'):
                self.stats.cache_read_tokens += response.usage.cache_read_input_tokens

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
