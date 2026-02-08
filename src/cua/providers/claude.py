"""Claude (Anthropic) provider implementation."""

from typing import Any, Dict, List, Optional
import time
import re
import anthropic

from cua.providers.base import ComputerUseProvider, Action, ActionType
from cua.prompts import build_initial_prompt, get_system_prompt, TWO_PHASE_PROMPT_P2


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
        """Create initial API request to Claude.

        Args:
            prompt: User's task description
            screenshot: Base64-encoded screenshot (optional)
            accessibility_tree: Accessibility tree from browser (optional)
            page_text: Extracted page text (optional)
            display_width: Display width in pixels
            display_height: Display height in pixels

        Returns:
            Claude API response
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

        # Build message content with system prompt + user prompt
        content = [{"type": "text", "text": self.system_prompt + "\n\n" + full_prompt}]

        # Add accessibility tree if available (FIRST - so AI reads it before image)
        if accessibility_tree and not accessibility_tree.get("error"):
            import json
            tree_text = f"\n\n**Accessibility Tree (Page Structure):**\n```json\n{json.dumps(accessibility_tree, indent=2)}\n```\n"
            content.append({"type": "text", "text": tree_text})

        # Add page text if available (SECOND - full text content)
        if page_text:
            # Truncate if too long to avoid token explosion
            max_text_length = 10000  # ~2500 tokens
            truncated_text = page_text[:max_text_length]
            if len(page_text) > max_text_length:
                truncated_text += f"\n\n[... text truncated, {len(page_text) - max_text_length} more characters ...]"

            text_section = f"\n\n**Page Text (All Visible Text):**\n```\n{truncated_text}\n```\n"
            content.append({"type": "text", "text": text_section})

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
            Text content from response (with transient content stripped)
        """
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
        full_text = " ".join(text_parts)

        # Strip transient content before returning
        return self._strip_transient_content(full_text)

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
