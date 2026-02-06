"""AWS Bedrock (Anthropic Claude) provider implementation using Converse API."""

from typing import Any, Dict, List, Optional
import time
import base64
import os
import boto3

from cua.providers.base import ComputerUseProvider, Action, ActionType


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

    def create_initial_request(
        self,
        prompt: str,
        screenshot: Optional[str] = None,
        accessibility_tree: Optional[dict] = None,
        display_width: int = 1024,
        display_height: int = 768
    ) -> Any:
        """Create initial API request using Bedrock Converse API.

        Args:
            prompt: User's task description
            screenshot: Base64-encoded screenshot (optional)
            accessibility_tree: Accessibility tree from browser (optional)
            display_width: Display width in pixels
            display_height: Display height in pixels

        Returns:
            Bedrock Converse API response
        """
        # Build message content with hybrid guide
        hybrid_guide = ""
        if accessibility_tree and not accessibility_tree.get("error"):
            hybrid_guide = """

HYBRID MODE: You have access to BOTH screenshot and accessibility tree.

**CRITICAL: How to use them together:**
1. **Accessibility Tree** - Use this to IDENTIFY what element you need (e.g., role="button" name="Submit")
   - Shows semantic structure, element names, roles, states
   - Reveals elements even if not visible in screenshot (scrolled content, collapsed sections)
   - Shows hierarchy (what's inside modals, forms, etc.)

2. **Screenshot** - Use this to LOCATE where the element is visually and GET COORDINATES
   - The tree does NOT contain pixel coordinates
   - You MUST look at the screenshot to find the visual position of elements
   - Match element names from tree to visual elements in screenshot

**Workflow:**
1. Read the accessibility tree to understand available elements and page structure
2. Identify which element you need to interact with (by role and name)
3. Look at the screenshot to visually locate that element
4. Use the element's position in the screenshot to determine click coordinates

**Example:**
- Tree shows: `{"role": "button", "name": "Submit & Continue"}`
- Look at screenshot to find button labeled "Submit & Continue"
- Click at the coordinates where you see that button in the screenshot
"""

        # Build message content for Converse API format
        content = [{"text": prompt + hybrid_guide}]

        # Add accessibility tree if available
        if accessibility_tree and not accessibility_tree.get("error"):
            import json
            tree_text = f"\n\n**Accessibility Tree:**\n```json\n{json.dumps(accessibility_tree, indent=2)}\n```"
            content.append({"text": tree_text})

        if screenshot:
            # Decode base64 screenshot to bytes for Converse API
            screenshot_bytes = base64.b64decode(screenshot)
            content.append({
                "image": {
                    "format": "png",
                    "source": {"bytes": screenshot_bytes}
                }
            })

        self.messages = [{"role": "user", "content": content}]

        # Tools configuration - use model-specific tool version
        tools_config = [
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
            Bedrock Converse API response
        """
        # Build tool result content for each tool use
        tool_result_content = []

        for tool_use in self.last_tool_uses:
            tool_id = tool_use.get('toolUseId')
            tool_name = tool_use.get('name')

            # Format tool result based on tool type
            if tool_name == "computer":
                # Return accessibility tree and screenshot
                result_content = []

                # Add accessibility tree first (so it's read before image)
                if accessibility_tree and not accessibility_tree.get("error"):
                    import json
                    tree_text = f"**Updated Accessibility Tree:**\n```json\n{json.dumps(accessibility_tree, indent=2)}\n```"
                    result_content.append({"text": tree_text})

                # Return screenshot as image
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

        # Add tool results as user message
        self.messages.append({
            "role": "user",
            "content": tool_result_content
        })

        # Tools configuration - use model-specific tool version
        tools_config = [
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
            Text content from response
        """
        text_parts = []

        if 'output' not in response or 'message' not in response['output']:
            return ""

        for content_block in response['output']['message'].get('content', []):
            if 'text' in content_block:
                text_parts.append(content_block['text'])

        return " ".join(text_parts)

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
