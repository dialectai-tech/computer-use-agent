"""AWS Bedrock (Anthropic Claude) provider implementation using Converse API."""

from typing import Any, Dict, List, Optional
import time
import base64
import os
import boto3
import re

from cua.providers.base import ComputerUseProvider, Action, ActionType
from cua.prompts import build_initial_prompt, get_system_prompt, TOOL_USAGE_ESSENTIALS, TWO_PHASE_PROMPT_P2


class BedrockProvider(ComputerUseProvider):
    """AWS Bedrock provider for computer use automation using Claude models via Converse API."""

    # Tool version mappings - different models support different tool versions
    TOOL_VERSIONS = {
        # Claude 3.5 models use older tool version
        "us.anthropic.claude-3-5-sonnet-20241022-v2:0": "computer_20241022",
        "us.anthropic.claude-3-5-haiku-20241022-v1:0": "computer_20241022",

        # All other models (3.7+, 4+) use newer tool version
        # This includes Sonnet 3.7, 4, 4.5 and Haiku 4.5, Opus 4+
    }
    DEFAULT_TOOL_VERSION = "computer_20250124"  # Default for newer models

    # Model ID mappings for Bedrock
    # Must use inference profile IDs (with us./global. prefix), not direct model ARNs
    MODEL_IDS = {
        # ===== SONNET MODELS =====
        # Claude 3.5 Sonnet v2 (original computer use model - proven)
        "claude-3-5-sonnet": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        "sonnet-3.5": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",

        # Claude 3.7 Sonnet (latest 3.x)
        "claude-3-7-sonnet": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        "sonnet-3.7": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",

        # Claude Sonnet 4
        "claude-sonnet-4": "us.anthropic.claude-sonnet-4-20250514-v1:0",
        "sonnet-4": "us.anthropic.claude-sonnet-4-20250514-v1:0",

        # Claude Sonnet 4.5 (latest)
        "claude-sonnet-4-5": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "sonnet-4.5": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",

        # ===== HAIKU MODELS (fast, cheap) =====
        # Claude 3 Haiku (oldest)
        "claude-3-haiku": "us.anthropic.claude-3-haiku-20240307-v1:0",
        "haiku-3": "us.anthropic.claude-3-haiku-20240307-v1:0",

        # Claude 3.5 Haiku
        "claude-3-5-haiku": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        "haiku-3.5": "us.anthropic.claude-3-5-haiku-20241022-v1:0",

        # Claude Haiku 4.5 (latest)
        "claude-haiku-4-5": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "haiku-4.5": "us.anthropic.claude-haiku-4-5-20251001-v1:0",

        # ===== OPUS MODELS (highest quality, slowest) =====
        # Claude 3 Opus (oldest)
        "claude-3-opus": "us.anthropic.claude-3-opus-20240229-v1:0",
        "opus-3": "us.anthropic.claude-3-opus-20240229-v1:0",

        # Claude Opus 4
        "claude-opus-4": "us.anthropic.claude-opus-4-20250514-v1:0",
        "opus-4": "us.anthropic.claude-opus-4-20250514-v1:0",

        # Claude Opus 4.1
        "claude-opus-4-1": "us.anthropic.claude-opus-4-1-20250805-v1:0",
        "opus-4.1": "us.anthropic.claude-opus-4-1-20250805-v1:0",

        # Claude Opus 4.5
        "claude-opus-4-5": "us.anthropic.claude-opus-4-5-20251101-v1:0",
        "opus-4.5": "us.anthropic.claude-opus-4-5-20251101-v1:0",

        # Claude Opus 4.6 (latest)
        "claude-opus-4-6": "us.anthropic.claude-opus-4-6-v1",
        "opus-4.6": "us.anthropic.claude-opus-4-6-v1",

        # ===== SHORT ALIASES =====
        "sonnet": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",  # Default to proven 3.5 v2
        "haiku": "us.anthropic.claude-haiku-4-5-20251001-v1:0",  # Latest Haiku
        "opus": "us.anthropic.claude-opus-4-5-20251101-v1:0",  # Latest stable Opus

        # Latest versions
        "sonnet-latest": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "haiku-latest": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "opus-latest": "us.anthropic.claude-opus-4-6-v1",
    }

    def __init__(
        self,
        api_key: str = None,
        model: str = "sonnet",
        region: str = "us-east-1",
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        aws_session_token: str = None
    ):
        """Initialize Bedrock provider using Converse API.

        Args:
            api_key: Legacy parameter (kept for compatibility, not used)
            model: Claude model name (sonnet/sonnet-3.5/sonnet-3.7)
            region: AWS region
            aws_access_key_id: AWS Access Key ID (optional)
            aws_secret_access_key: AWS Secret Access Key (optional)
            aws_session_token: AWS Session Token (optional)
        """
        super().__init__(api_key or "bedrock", model)

        # Map short names to full model IDs
        self.model_id = self.MODEL_IDS.get(model, model)

        # Determine which tool version this model supports
        self.tool_version = self.TOOL_VERSIONS.get(
            self.model_id,
            self.DEFAULT_TOOL_VERSION
        )
        self.bash_version = self.tool_version.replace("computer", "bash")

        # Handle AWS_BEARER_TOKEN_BEDROCK environment variable
        if not aws_session_token and 'AWS_BEARER_TOKEN_BEDROCK' in os.environ:
            aws_session_token = os.environ['AWS_BEARER_TOKEN_BEDROCK']

        # Build client kwargs
        client_kwargs = {'service_name': 'bedrock-runtime', 'region_name': region}

        # Add explicit credentials if provided
        if aws_access_key_id and aws_secret_access_key:
            client_kwargs['aws_access_key_id'] = aws_access_key_id
            client_kwargs['aws_secret_access_key'] = aws_secret_access_key
            if aws_session_token:
                client_kwargs['aws_session_token'] = aws_session_token
        elif aws_session_token:
            client_kwargs['aws_session_token'] = aws_session_token

        # Initialize Bedrock client for Converse API
        self.client = boto3.client(**client_kwargs)

        self.messages = []
        self.last_response = None
        self.last_tool_uses = []
        self.system_prompt = get_system_prompt()  # Generic system prompt
        self.first_user_message = None  # Store first user message for context reset
        self.max_message_turns = 10  # Keep last N message turns (configurable)

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

    def _is_transient_response(self, text: str) -> bool:
        """Check if AI explicitly marked this response as transient.

        Args:
            text: Response text from AI

        Returns:
            True if response contains TRANSIENT marker
        """
        # Check for explicit TRANSIENT: marker at end of response
        if re.search(r'TRANSIENT:', text, re.IGNORECASE):
            return True
        return False

    def _prune_message_history(self):
        """Prune message history to keep only recent turns + first user message.

        Keeps:
        - First user message (task description)
        - Last N message turns (N = max_message_turns)
        """
        if len(self.messages) <= self.max_message_turns * 2:
            return  # No pruning needed

        # Keep first user message + last N turns
        # Each turn = user message + assistant message (2 messages)
        keep_count = self.max_message_turns * 2

        if self.first_user_message:
            # Keep first message + last N turns
            self.messages = [self.first_user_message] + self.messages[-keep_count:]
        else:
            # Just keep last N turns
            self.messages = self.messages[-keep_count:]

    def create_initial_request(
        self,
        prompt: str,
        screenshot: Optional[str] = None,
        accessibility_tree: Optional[dict] = None,
        page_text: Optional[str] = None,
        display_width: int = 1024,
        display_height: int = 768
    ) -> Any:
        """Create initial API request using Bedrock Converse API.

        Args:
            prompt: User's task description
            screenshot: Base64-encoded screenshot (optional)
            accessibility_tree: Accessibility tree from browser (optional)
            page_text: Extracted page text (optional)
            display_width: Display width in pixels
            display_height: Display height in pixels

        Returns:
            Bedrock Converse API response
        """
        # Build concise, generic prompt
        has_search_tool = page_text is not None or (accessibility_tree and not accessibility_tree.get("error"))
        full_prompt = build_initial_prompt(
            user_prompt=prompt,
            has_search_tool=has_search_tool,
            has_page_text=bool(page_text),
            two_phase=False
        )

        # Build message content for Converse API format
        # Add system prompt as first message (only text, not in content blocks)
        content = [{"text": self.system_prompt + "\n\n" + full_prompt}]

        # Add accessibility tree if available (FIRST - so AI reads it before image)
        if accessibility_tree and not accessibility_tree.get("error"):
            import json
            tree_text = f"\n\n**Accessibility Tree (Page Structure):**\n```json\n{json.dumps(accessibility_tree, indent=2)}\n```\n"
            content.append({"text": tree_text})

        # Add page text if available (SECOND - full text content)
        if page_text:
            # Truncate if too long to avoid token explosion
            max_text_length = 10000  # ~2500 tokens
            truncated_text = page_text[:max_text_length]
            if len(page_text) > max_text_length:
                truncated_text += f"\n\n[... text truncated, {len(page_text) - max_text_length} more characters ...]"

            text_section = f"\n\n**Page Text (All Visible Text):**\n```\n{truncated_text}\n```\n"
            content.append({"text": text_section})

        if screenshot:
            # Decode base64 screenshot to bytes for Converse API (LAST - visual reference)
            screenshot_bytes = base64.b64decode(screenshot)
            content.append({
                "image": {
                    "format": "png",
                    "source": {"bytes": screenshot_bytes}
                }
            })

        self.messages = [{"role": "user", "content": content}]

        # Store first user message for context reset
        if not self.first_user_message:
            self.first_user_message = self.messages[0]

        # Tools configuration - use model-specific tool version
        tools_config = [
            # Custom search tool - MUST be used before computer tool
            {
                "name": "search_page_content",
                "description": "Search page text and accessibility tree for content. ALWAYS use this BEFORE taking any computer actions. This tool has access to ALL page content including text that may not be visible in screenshots.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What to search for (text, code, button name, etc.). Supports regex patterns."
                        },
                        "search_type": {
                            "type": "string",
                            "enum": ["text", "tree", "both"],
                            "description": "Where to search: 'text' (page text), 'tree' (accessibility tree), or 'both'. Default: 'both'"
                        }
                    },
                    "required": ["query"]
                }
            },
            # Browser find tool - use after search to navigate instantly
            {
                "name": "browser_find",
                "description": "Use browser's native find (Ctrl+F) to instantly navigate to and highlight content. MUCH faster than scrolling! Use after search_page_content finds content. Browser will auto-scroll to first match and highlight all matches.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "search_term": {
                            "type": "string",
                            "description": "Exact text to find on page. Use unique text from search_page_content results to avoid ambiguity."
                        },
                        "close_after": {
                            "type": "boolean",
                            "description": "Whether to close find dialog after finding (default: true)"
                        }
                    },
                    "required": ["search_term"]
                }
            },
            {
                "type": self.tool_version,
                "name": "computer",
                "display_width_px": display_width,
                "display_height_px": display_height,
                "display_number": 0,  # Bedrock uses 0, not 1
            },
            {
                "type": self.bash_version,
                "name": "bash"
            }
        ]

        # Determine beta version based on tool version
        # computer_20241022 -> computer-use-2024-10-22
        # computer_20250124 -> computer-use-2025-01-24
        beta_version = "computer-use-2025-01-24" if "20250124" in self.tool_version else "computer-use-2024-10-22"

        # Tools go in additionalModelRequestFields for Converse API
        additional_fields = {
            "anthropic_beta": [beta_version],
            "tools": tools_config
        }

        # Build inference config with extended thinking if enabled
        inference_config = {"maxTokens": 4096}

        # Add extended thinking configuration if enabled
        if self.extended_thinking:
            additional_fields["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget
            }

        # Call Bedrock Converse API
        # For initial request, tools are ONLY in additionalModelRequestFields
        # toolConfig is not needed for initial request
        start_time = time.time()
        response = self.client.converse(
            modelId=self.model_id,
            messages=self.messages,
            inferenceConfig=inference_config,
            additionalModelRequestFields=additional_fields
        )
        api_time = time.time() - start_time

        # Track stats
        self.stats.add_api_call(api_time)
        if 'usage' in response:
            self.stats.add_tokens(
                input_tokens=response['usage'].get('inputTokens', 0),
                output_tokens=response['usage'].get('outputTokens', 0)
            )

        self.last_response = response

        # Extract tool uses for continuation
        self.last_tool_uses = []
        if 'output' in response and 'message' in response['output']:
            for content_block in response['output']['message'].get('content', []):
                if 'toolUse' in content_block:
                    self.last_tool_uses.append(content_block['toolUse'])

        # Add assistant message to conversation
        if 'output' in response and 'message' in response['output']:
            self.messages.append(response['output']['message'])

        return response

    def create_continuation_request(
        self,
        screenshot: str,
        accessibility_tree: Optional[dict] = None,
        page_text: Optional[str] = None,
        search_results: Optional[List] = None,
        action_result: Optional[Dict[str, Any]] = None,
        display_width: int = 1024,
        display_height: int = 768,
        additional_instruction: Optional[str] = None
    ) -> Any:
        """Create continuation request with tool results.

        Args:
            screenshot: Base64-encoded screenshot
            accessibility_tree: Accessibility tree from browser (optional)
            page_text: Extracted text content from page (optional)
            search_results: Results from search_page_content tool (optional)
            action_result: Result from previous action execution
            display_width: Display width in pixels
            display_height: Display height in pixels
            additional_instruction: Additional instruction/prompt to inject (optional)

        Returns:
            Bedrock Converse API response
        """
        # Prune message history to keep only recent turns
        self._prune_message_history()

        # Build tool result content for each tool use
        tool_result_content = []

        # Create a dict of search results by tool ID for quick lookup
        search_results_dict = {}
        if search_results:
            for tool_id, result in search_results:
                search_results_dict[tool_id] = result

        for tool_use in self.last_tool_uses:
            tool_id = tool_use.get('toolUseId')
            tool_name = tool_use.get('name')

            # Format tool result based on tool type
            if tool_name == "search_page_content":
                # Return search results
                if tool_id in search_results_dict:
                    import json
                    search_result = search_results_dict[tool_id]
                    result_text = f"**Search Results:**\n```json\n{json.dumps(search_result, indent=2)}\n```\n\n{search_result.get('summary', '')}"
                    result_content = [{"text": result_text}]
                else:
                    result_content = [{"text": "Search completed but no results available"}]
            elif tool_name == "computer":
                # Return accessibility tree, page text, and screenshot
                result_content = []

                # Add accessibility tree first (so it's read before image)
                if accessibility_tree and not accessibility_tree.get("error"):
                    import json
                    tree_text = f"**Updated Accessibility Tree:**\n```json\n{json.dumps(accessibility_tree, indent=2)}\n```\n"
                    result_content.append({"text": tree_text})

                # Add page text second (full text content)
                if page_text:
                    # Truncate if too long
                    max_text_length = 10000  # ~2500 tokens
                    truncated_text = page_text[:max_text_length]
                    if len(page_text) > max_text_length:
                        truncated_text += f"\n\n[... text truncated, {len(page_text) - max_text_length} more characters ...]"

                    text_section = f"**Updated Page Text:**\n```\n{truncated_text}\n```\n"
                    result_content.append({"text": text_section})

                # Return screenshot as image (last - for visual reference)
                screenshot_bytes = base64.b64decode(screenshot)
                result_content.append({
                    "image": {
                        "format": "png",
                        "source": {"bytes": screenshot_bytes}
                    }
                })
            elif tool_name == "browser_find":
                # Return browser find result with updated screenshot
                message = action_result.get("message", "") if action_result else "Browser find completed"
                result_content = [{"text": message}]

                # Add screenshot to show highlighted content
                screenshot_bytes = base64.b64decode(screenshot)
                result_content.append({
                    "image": {
                        "format": "png",
                        "source": {"bytes": screenshot_bytes}
                    }
                })
            elif tool_name == "bash":
                # Return command output as text
                output = action_result.get("output", "") if action_result else ""
                result_content = [{"text": output}]
            else:
                result_content = [{"text": "success"}]

            tool_result_content.append({
                "toolResult": {
                    "toolUseId": tool_id,
                    "content": result_content
                }
            })

        # Inject additional instruction as first content block if provided
        if additional_instruction:
            tool_result_content.insert(0, {"text": additional_instruction})

        # Add tool results as user message
        self.messages.append({
            "role": "user",
            "content": tool_result_content
        })

        # Tools configuration - use model-specific tool version
        tools_config = [
            # Custom search tool - MUST be used before computer tool
            {
                "name": "search_page_content",
                "description": "Search page text and accessibility tree for content. ALWAYS use this BEFORE taking any computer actions.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What to search for"
                        },
                        "search_type": {
                            "type": "string",
                            "enum": ["text", "tree", "both"],
                            "description": "Where to search"
                        }
                    },
                    "required": ["query"]
                }
            },
            # Browser find tool - use after search to navigate instantly
            {
                "name": "browser_find",
                "description": "Use browser find (Ctrl+F) to instantly navigate to content. Use after search_page_content.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "search_term": {
                            "type": "string",
                            "description": "Exact text to find"
                        },
                        "close_after": {
                            "type": "boolean",
                            "description": "Whether to close find dialog after finding"
                        }
                    },
                    "required": ["search_term"]
                }
            },
            {
                "type": self.tool_version,
                "name": "computer",
                "display_width_px": display_width,
                "display_height_px": display_height,
                "display_number": 0,
            },
            {
                "type": self.bash_version,
                "name": "bash"
            }
        ]

        # Determine beta version based on tool version
        beta_version = "computer-use-2025-01-24" if "20250124" in self.tool_version else "computer-use-2024-10-22"

        # For continuation: tools go in toolConfig wrapped as toolSpec
        # additionalModelRequestFields only contains beta header (no tools to avoid duplication)
        additional_fields_continuation = {
            "anthropic_beta": [beta_version]
        }

        # Add extended thinking configuration if enabled
        if self.extended_thinking:
            additional_fields_continuation["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget
            }

        # Build toolConfig for continuation (required when using tool results)
        # Wrap each tool as a toolSpec with minimal valid input schema
        bedrock_tool_config = {
            "tools": [
                {
                    "toolSpec": {
                        "name": tool["name"],
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {}
                            }
                        }
                    }
                }
                for tool in tools_config
            ]
        }

        # Build inference config
        inference_config = {"maxTokens": 4096}

        # Call Converse API with continuation
        # NOTE: Tools are defined in BOTH places but this appears to be required:
        # - toolConfig: References tools by name (Bedrock requirement for tool results)
        # - additionalModelRequestFields: Full Anthropic tool config with dimensions
        start_time = time.time()
        response = self.client.converse(
            modelId=self.model_id,
            messages=self.messages,
            inferenceConfig=inference_config,
            toolConfig=bedrock_tool_config,
            additionalModelRequestFields=additional_fields_continuation
        )
        api_time = time.time() - start_time

        # Track stats
        self.stats.add_api_call(api_time)
        if 'usage' in response:
            self.stats.add_tokens(
                input_tokens=response['usage'].get('inputTokens', 0),
                output_tokens=response['usage'].get('outputTokens', 0)
            )

        self.last_response = response

        # Extract tool uses for next continuation
        self.last_tool_uses = []
        if 'output' in response and 'message' in response['output']:
            for content_block in response['output']['message'].get('content', []):
                if 'toolUse' in content_block:
                    self.last_tool_uses.append(content_block['toolUse'])

        # Add assistant message to conversation
        if 'output' in response and 'message' in response['output']:
            self.messages.append(response['output']['message'])

        return response

    def extract_actions(self, response: Any) -> List[Action]:
        """Extract actions from Bedrock Converse API response.

        Args:
            response: Bedrock Converse API response

        Returns:
            List of actions to execute
        """
        actions = []

        # Extract tool uses from response
        if 'output' not in response or 'message' not in response['output']:
            return actions

        for content_block in response['output']['message'].get('content', []):
            if 'toolUse' in content_block:
                tool_use = content_block['toolUse']
                tool_name = tool_use.get('name')

                if tool_name == "computer":
                    tool_input = tool_use.get('input', {})
                    action_type = self._map_action_type(tool_input.get('action'))
                    if action_type:
                        action = Action(
                            type=action_type,
                            params=tool_input,
                            id=tool_use.get('toolUseId', '')
                        )
                        actions.append(action)
                elif tool_name == "search_page_content":
                    # Handle search tool
                    tool_input = tool_use.get('input', {})
                    action = Action(
                        type=ActionType.SEARCH,
                        params=tool_input,
                        id=tool_use.get('toolUseId', '')
                    )
                    actions.append(action)
                elif tool_name == "browser_find":
                    # Handle browser find tool
                    tool_input = tool_use.get('input', {})
                    action = Action(
                        type=ActionType.BROWSER_FIND,
                        params=tool_input,
                        id=tool_use.get('toolUseId', '')
                    )
                    actions.append(action)

        return actions

    def is_task_complete(self, response: Any) -> bool:
        """Check if task is complete.

        Args:
            response: Bedrock Converse API response

        Returns:
            True if task is complete (no tool use)
        """
        if 'output' not in response or 'message' not in response['output']:
            return True

        for content_block in response['output']['message'].get('content', []):
            if 'toolUse' in content_block:
                return False

        return True

    def get_response_text(self, response: Any) -> str:
        """Extract text content from response.

        Args:
            response: Bedrock Converse API response

        Returns:
            Text content from response (with transient content stripped)
        """
        text_parts = []

        if 'output' not in response or 'message' not in response['output']:
            return ""

        for content_block in response['output']['message'].get('content', []):
            if 'text' in content_block:
                text_parts.append(content_block['text'])

        full_text = " ".join(text_parts)

        # Strip transient content before returning
        return self._strip_transient_content(full_text)

    def _map_action_type(self, action_str: str) -> Optional[ActionType]:
        """Map action string to ActionType enum.

        Args:
            action_str: Action string from Bedrock

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
