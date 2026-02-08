"""AWS Bedrock (Anthropic Claude) provider implementation using Converse API."""

from typing import Any, Dict, List, Optional
import time
import base64
import os
import boto3
import re

from cua.providers.base import ComputerUseProvider, Action, ActionType
from cua.prompts import build_initial_prompt, get_system_prompt, TWO_PHASE_PROMPT_P2
from cua.tools.dom_tool import DOM_TOOL_DEFINITION
from cua.tools.context_reset_tool import CONTEXT_RESET_TOOL_DEFINITION


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
        - Last N complete conversation cycles (N = max_message_turns)

        NOTE: This is called BEFORE adding the new user message with tool results,
        so the conversation ends with an assistant message (with toolUse blocks).
        We need to keep this final assistant message along with the previous cycles.
        """
        # DEBUG: Log before pruning
        print(f"[DEBUG PRUNING] Before: {len(self.messages)} messages")
        print(f"[DEBUG PRUNING] max_message_turns: {self.max_message_turns}")

        # Calculate threshold for pruning
        # Need at least first message + (max_message_turns * 2) messages
        min_messages = 1 + (self.max_message_turns * 2)
        print(f"[DEBUG PRUNING] min_messages threshold: {min_messages}")

        if len(self.messages) <= min_messages:
            print(f"[DEBUG PRUNING] Skipping pruning (not enough messages)")
            return  # No pruning needed

        # Work backwards to find N complete cycles
        # Each cycle = user message (with toolResult) + assistant message (with toolUse)
        # The current last message is an assistant message (we haven't added the new user message yet)
        cycles_to_keep = self.max_message_turns
        messages_to_keep = []

        # Start from the end (most recent)
        i = len(self.messages) - 1
        cycles_found = 0

        # The last message should be assistant (with toolUse) - keep it unconditionally
        if i >= 0 and self.messages[i]["role"] == "assistant":
            messages_to_keep.insert(0, self.messages[i])
            i -= 1
            # This assistant message is waiting for tool results, not counted as complete cycle yet

        # Now work backwards finding complete cycles (user + assistant pairs)
        while i >= 0 and cycles_found < cycles_to_keep:
            msg = self.messages[i]

            # A complete cycle ends with a user message
            if msg["role"] == "user":
                messages_to_keep.insert(0, msg)
                i -= 1

                # The preceding message should be assistant
                if i >= 0 and self.messages[i]["role"] == "assistant":
                    messages_to_keep.insert(0, self.messages[i])
                    i -= 1
                    cycles_found += 1
                else:
                    # Incomplete cycle, stop here
                    break
            else:
                # Unexpected assistant message, skip it
                i -= 1

        # DEBUG: Log pruning results
        print(f"[DEBUG PRUNING] Cycles found: {cycles_found}")
        print(f"[DEBUG PRUNING] messages_to_keep: {len(messages_to_keep)}")

        # Prepend first user message if it exists and isn't already included
        if self.first_user_message:
            # Check if first message is already in messages_to_keep
            if not messages_to_keep or messages_to_keep[0] != self.first_user_message:
                self.messages = [self.first_user_message] + messages_to_keep
                print(f"[DEBUG PRUNING] Added first_user_message (not in kept messages)")
            else:
                self.messages = messages_to_keep
                print(f"[DEBUG PRUNING] First message already in kept messages")
        else:
            self.messages = messages_to_keep
            print(f"[DEBUG PRUNING] No first_user_message stored")

        # Strip screenshots from all messages except the most recent 2
        # (Keep recent assistant response + current user message intact)
        # This keeps AI responses (text) but discards old screenshots to save tokens
        if len(self.messages) > 2:
            screenshot_count_before = 0
            screenshot_count_after = 0

            # Count screenshots before stripping
            for msg in self.messages[:-2]:  # All except last 2
                if "content" in msg and isinstance(msg["content"], list):
                    for block in msg["content"]:
                        if isinstance(block, dict) and "image" in block:
                            screenshot_count_before += 1

            # Strip screenshots from old messages (keep text, tool results, etc.)
            for msg in self.messages[:-2]:  # All except last 2
                if "content" in msg and isinstance(msg["content"], list):
                    # Check if message has non-image content
                    non_image_blocks = [
                        block for block in msg["content"]
                        if not (isinstance(block, dict) and "image" in block)
                    ]

                    # Only strip screenshots if there's other content to preserve
                    # (AWS Bedrock rejects empty content arrays)
                    if len(non_image_blocks) > 0:
                        msg["content"] = non_image_blocks
                    # else: Keep the screenshot to avoid empty content

            # Count screenshots after stripping
            for msg in self.messages[:-2]:  # All except last 2
                if "content" in msg and isinstance(msg["content"], list):
                    for block in msg["content"]:
                        if isinstance(block, dict) and "image" in block:
                            screenshot_count_after += 1

            # Count screenshots in most recent messages
            recent_screenshots = 0
            for msg in self.messages[-2:]:  # Last 2 messages
                if "content" in msg and isinstance(msg["content"], list):
                    for block in msg["content"]:
                        if isinstance(block, dict) and "image" in block:
                            recent_screenshots += 1

            print(f"[DEBUG PRUNING] Screenshots stripped: {screenshot_count_before} → {screenshot_count_after} (kept {recent_screenshots} in last 2 messages)")

        print(f"[DEBUG PRUNING] After: {len(self.messages)} messages")
        print(f"[DEBUG PRUNING] ---")

    def reset_context(
        self,
        progress_summary: str,
        next_goal: str,
        current_screenshot: Optional[str] = None,
        current_page_info: Optional[Dict] = None
    ) -> bool:
        """Reset conversation context for Bedrock Converse API.

        Args:
            progress_summary: Summary of progress made so far
            next_goal: What needs to be done next
            current_screenshot: Current screenshot (optional)
            current_page_info: Current page information (optional)

        Returns:
            True if reset successful, False otherwise
        """
        if not self.messages or len(self.messages) == 0:
            return False

        # Keep ONLY the first user message (system + initial task)
        first_user_message = self.first_user_message or (self.messages[0] if self.messages else None)

        if not first_user_message:
            return False

        # Create checkpoint message
        from cua.tools.context_reset_tool import ContextResetRequest, ContextResetTool
        checkpoint_msg = ContextResetTool.create_reset_message(
            ContextResetRequest(
                reason="Context reset requested",
                progress_summary=progress_summary,
                next_goal=next_goal
            ),
            current_page_info or {}
        )

        # Build checkpoint content
        checkpoint_content = [{"text": checkpoint_msg}]

        # Add current screenshot if available
        if current_screenshot:
            screenshot_bytes = base64.b64decode(current_screenshot)
            checkpoint_content.append({
                "image": {
                    "format": "png",
                    "source": {"bytes": screenshot_bytes}
                }
            })

        # Build new message list: first message + checkpoint
        # Use a copy of first_user_message so subsequent stripping doesn't affect the stored version
        import copy
        new_messages = [
            copy.deepcopy(first_user_message),
            {
                "role": "user",
                "content": checkpoint_content
            }
        ]

        # Replace message history
        self.messages = new_messages
        # Ensure first_user_message stays as the deep copy (don't overwrite with reference)
        if not self.first_user_message:
            import copy
            self.first_user_message = copy.deepcopy(first_user_message)

        # Clear last tool uses since we're starting fresh
        self.last_tool_uses = []

        return True

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
        """Create initial API request using Bedrock Converse API.

        Args:
            prompt: User's task description
            screenshot: Base64-encoded screenshot (optional)
            accessibility_tree: Accessibility tree from browser (optional)
            page_text: Extracted page text (optional)
            display_width: Display width in pixels
            display_height: Display height in pixels
            use_dom_manipulation: Enable DOM manipulation tool (default: True)

        Returns:
            Bedrock Converse API response
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

        # Build message content for Converse API format
        # IMPORTANT: Do NOT embed system prompt in user message!
        # It will be sent via the 'system' parameter to avoid re-sending it every time
        content = [{"text": full_prompt}]

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

        # Store first user message for context reset (deep copy to avoid mutations)
        if not self.first_user_message:
            import copy
            self.first_user_message = copy.deepcopy(self.messages[0])

        # Tools configuration - use model-specific tool version
        tools_config = []

        # Add search tool if enabled
        if use_search_tool:
            tools_config.append({
                "name": "search_page_content",
                "description": """Search page text and accessibility tree to FIND what exists on the page. Use this to DISCOVER content BEFORE interacting!

**KEY DISTINCTION:**
- search_page_content = FIND what text/elements exist on page (returns line numbers and content)
- browser_find = NAVIGATE to text you already know exists (scrolls and highlights)
- computer = INTERACT with coordinates after finding location

**What this tool does:**
- Searches ALL page content including text not visible in screenshots
- Returns line numbers and exact text matches
- Searches both visible text and accessibility tree structure
- Helps you DISCOVER what buttons, links, inputs, codes exist on the page

**REQUIRED Parameters:**
- query: (string, REQUIRED) What to search for - can be text, button name, code, etc.
- search_type: (string, optional) Where to search - "text", "tree", or "both" (default: "both")

**Example Usage:**

1. Find a button by text:
   {"query": "START", "search_type": "both"}
   Returns: "📄 Found 3 text match(es) at line(s): 10, 25, 37"

2. Find code or specific text:
   {"query": "CODE123", "search_type": "text"}
   Returns: "📄 Found 1 text match(es) at line(s): 42"

3. Search for element that might not exist:
   {"query": "correct option select"}
   Returns: "❌ No matches found for 'correct option select'"

**Returns:**
✓ Found matches: "📄 Found 3 text match(es) at line(s): 10, 25, 37" + first match content
✗ No matches: "❌ No matches found for 'your query'"

**What to do when NO MATCHES found:**
1. Try different variations (e.g., "Submit" vs "submit" vs "SUBMIT")
2. Try shorter/simpler queries (e.g., "START" instead of "START button")
3. Try searching just part of the text (e.g., "option" instead of "correct option")
4. Look at the screenshot - the element might be visible with different text
5. Try searching in tree only: search_type="tree"
6. If multiple searches fail, the element may not exist - try a different approach

**Best Practices:**
- Use SHORT, SPECIFIC queries (avoid long phrases like "correct option select")
- Search for UNIQUE words (e.g., "Reveal" not "the")
- Try multiple variations if first search returns zero results
- This tool tells you IF something exists - use browser_find or coordinates to interact after

**Common Mistakes:**
❌ Don't search for long phrases: query="the correct option to select" (too specific!)
❌ Don't give up after one failed search - try variations!
❌ Don't pass empty query: query=""
✓ Do use SHORT specific text: query="Reveal"
✓ Do try multiple variations: "Submit", then "submit", then "button"
✓ Do check if zero results means element doesn't exist or you need different query,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "REQUIRED: Text to search for (e.g., 'START', 'Submit', 'Enter code'). Be specific and concise."
                        },
                        "search_type": {
                            "type": "string",
                            "enum": ["text", "tree", "both"],
                            "description": "OPTIONAL: Where to search. Options: 'text' (page text only), 'tree' (accessibility tree only), 'both' (searches everywhere, DEFAULT)"
                        }
                    },
                    "required": ["query"]
                }
            })

        # Add browser find tool if enabled
        if use_find_tool:
            tools_config.append({
                "name": "browser_find",
                "description": """Use browser's native find (Ctrl+F) to NAVIGATE to text you already know exists. Use AFTER search_page_content!

**KEY DISTINCTION:**
- search_page_content = FIND/DISCOVER what text exists (returns "found" or "not found")
- browser_find = NAVIGATE to text you ALREADY KNOW exists (scrolls to it and highlights)
- Don't use browser_find for text that might not exist - use search_page_content first!

**What this tool does:**
- Opens browser's native find dialog (Ctrl+F)
- Automatically scrolls to first match
- Highlights all matching text on the page
- Brings the text into view so you can click near it

**REQUIRED Parameters:**
- search_term: (string, REQUIRED) Exact text to find on the page

**OPTIONAL Parameters:**
- close_after: (boolean, optional) Close find dialog after finding (default: true)

**CRITICAL: Parameter name is "search_term" NOT "text"!**

**Example Usage (with exact JSON format):**

1. Navigate to button text (after confirming it exists via search_page_content):
   {"search_term": "START"}
   → Scrolls to "START" button and highlights it

2. Navigate to specific code (that you found via search_page_content):
   {"search_term": "CODE123"}
   → Scrolls to "CODE123" text and highlights it

3. Navigate and keep dialog open:
   {"search_term": "Enter code", "close_after": false}
   → Scrolls to text but leaves find dialog open

**Parameter Name Warning:**
✗ WRONG: {"text": "START"} ← This will fail!
✓ CORRECT: {"search_term": "START"} ← Use this!

**Recommended Workflow:**
1. search_page_content FIRST to DISCOVER what text exists
   Example: search_page_content(query="START") → Returns "📄 Found at line 10"
2. browser_find SECOND to NAVIGATE to that text
   Example: browser_find(search_term="START") → Scrolls to and highlights "START"
3. computer tool THIRD to INTERACT with coordinates
   Example: computer(action="left_click", coordinate=[540, 400])

**Returns:**
- Message: "Browser find completed"
- Screenshot showing the page scrolled to the matched text (highlighted)

**Best Practices:**
- ALWAYS use search_page_content FIRST to verify text exists
- Use EXACT text from search_page_content results
- Use unique text that appears only once (e.g., "Reveal Code" not just "Code")
- Short text is better (3-10 words max)
- Case-sensitive: "START" ≠ "start"

**Common Mistakes:**
❌ Don't use browser_find without search_page_content first
❌ Don't pass empty string: search_term=""
❌ Don't use for text that might not exist (browser find will fail silently)
❌ Don't search for text you haven't confirmed exists via search_page_content
✓ Do use search_page_content first, then browser_find
✓ Do use exact text: search_term="Click here to reveal"
✓ Do use unique text: search_term="Step 2 of 30"

**When to Use:**
✓ After search_page_content confirms text exists
✓ When you need to scroll to specific content
✓ When content is below the fold (not visible in current screenshot)
✗ Don't use if text might not exist - check with search_page_content first!
✗ Don't use if you already see the element in screenshot - just click it!""",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "search_term": {
                            "type": "string",
                            "description": "REQUIRED: Exact text to find (e.g., 'START', 'Reveal Code', 'Step 2 of 30'). Must be exact match, case-sensitive."
                        },
                        "close_after": {
                            "type": "boolean",
                            "description": "OPTIONAL: Close find dialog after finding. Default: true. Set to false to keep dialog open."
                        }
                    },
                    "required": ["search_term"]
                }
            })

        # Add DOM manipulation tool if enabled
        if use_dom_manipulation:
            tools_config.append(DOM_TOOL_DEFINITION)

        # Add context reset and computer tools
        tools_config.extend([
            # Context reset tool - AI can reset its own context at milestones
            CONTEXT_RESET_TOOL_DEFINITION,
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
        ])

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
        # Send system prompt via 'system' parameter (sent once, cached by API)
        start_time = time.time()
        response = self.client.converse(
            modelId=self.model_id,
            messages=self.messages,
            system=[{"text": self.system_prompt}],  # System prompt sent separately, not in messages
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
        additional_instruction: Optional[str] = None,
        use_dom_manipulation: bool = True,
        use_search_tool: bool = True,
        use_find_tool: bool = True
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
            use_dom_manipulation: Enable DOM manipulation tool (default: True)

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
                # Return search results - compact format without full JSON dump
                if tool_id in search_results_dict:
                    search_result = search_results_dict[tool_id]
                    # Just return the summary - AI doesn't need the full JSON structure
                    result_text = search_result.get('summary', 'Search completed')
                    result_content = [{"text": result_text}]
                else:
                    result_content = [{"text": "Search completed but no results available"}]
            elif tool_name == "computer":
                # Return screenshot (page text is added globally after all tool results)
                screenshot_bytes = base64.b64decode(screenshot)
                result_content = [{
                    "image": {
                        "format": "png",
                        "source": {"bytes": screenshot_bytes}
                    }
                }]
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
            elif tool_name == "dom_manipulation":
                # Return DOM manipulation result - compact format
                if action_result:
                    success = action_result.get("success", False)
                    if success:
                        # For find_selectors, return compact list
                        if "matches" in action_result:
                            matches = action_result["matches"][:3]  # Show first 3
                            selectors = [m.get("selector", "") for m in matches]
                            result_text = f"✓ Found: {', '.join(selectors)}"
                        else:
                            result_text = "✓ DOM action successful"
                    else:
                        error = action_result.get("error", "Unknown error")
                        result_text = f"✗ DOM action failed: {error}"
                    result_content = [{"text": result_text}]
                else:
                    result_content = [{"text": "✓ DOM action completed"}]
            elif tool_name == "reset_context":
                # Return context reset confirmation
                message = action_result.get("message", "Context has been reset") if action_result else "Context has been reset"
                result_content = [{"text": message}]
            else:
                result_content = [{"text": "success"}]

            tool_result_content.append({
                "toolResult": {
                    "toolUseId": tool_id,
                    "content": result_content
                }
            })

        # Add page text AFTER all tool results to maintain context (especially after pruning)
        if page_text:
            # Truncate if too long to avoid token explosion
            max_text_length = 10000  # ~2500 tokens
            truncated_text = page_text[:max_text_length]
            if len(page_text) > max_text_length:
                truncated_text += f"\n\n[... text truncated, {len(page_text) - max_text_length} more characters ...]"

            text_section = f"\n\n**Page Text (Current Page):**\n```\n{truncated_text}\n```\n"
            tool_result_content.append({"text": text_section})

        # Inject additional instruction as text AFTER all tool results if provided
        if additional_instruction:
            tool_result_content.append({"text": additional_instruction})

        # AWS Bedrock rejects empty content arrays
        # If there are no tool results (e.g., after context reset), add current state as text
        if len(tool_result_content) == 0:
            tool_result_content.append({
                "text": "Continuing from current state. Please analyze the screenshot and proceed."
            })

        # Add tool results as user message (with optional instruction appended)
        self.messages.append({
            "role": "user",
            "content": tool_result_content
        })

        # Tools configuration - use model-specific tool version
        tools_config = []

        # Add search tool if enabled
        if use_search_tool:
            tools_config.append({
                "name": "search_page_content",
                "description": """Search page text and tree to DISCOVER what exists. Use FIRST to find content before interacting!

**KEY: search_page_content=FIND what exists, browser_find=NAVIGATE to it, computer=INTERACT with it**

**REQUIRED Parameters:**
- query: (string, REQUIRED) Text to search for (e.g., "START", "Submit")
- search_type: (string, optional) "text", "tree", or "both" (default: "both")

**Example:** {"query": "START", "search_type": "both"}

**Returns:**
✓ Found: "📄 Found 3 text match(es) at line(s): 10, 25, 37"
✗ Not found: "❌ No matches found for 'START'"

**Zero Results?** Try variations: shorter text, different case, or just part of the word.

**Best Practices:** Use SHORT queries. If no results, try variations before giving up.""",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "REQUIRED: Text to search for (e.g., 'START', 'Submit'). Be specific."
                        },
                        "search_type": {
                            "type": "string",
                            "enum": ["text", "tree", "both"],
                            "description": "OPTIONAL: Where to search. 'both' is default."
                        }
                    },
                    "required": ["query"]
                }
            })

        # Add browser find tool if enabled
        if use_find_tool:
            tools_config.append({
                "name": "browser_find",
                "description": """Use browser find (Ctrl+F) to NAVIGATE to text you know exists. Use AFTER search_page_content!

**KEY: search_page_content=FIND what exists, browser_find=NAVIGATE to it, computer=INTERACT**

**CRITICAL: Parameter name is "search_term" NOT "text"!**

**REQUIRED Parameters:**
- search_term: (string, REQUIRED) Exact text to find on the page

**Example:** {"search_term": "Reveal Code"}

**Returns:** Screenshot with page scrolled to matched text (highlighted)

**Workflow:** 1) search_page_content to confirm text exists, 2) browser_find to navigate to it, 3) computer to click

**Best Practices:** Use EXACT text from search_page_content results. Case-sensitive. Don't use for text that might not exist.,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "search_term": {
                            "type": "string",
                            "description": "REQUIRED: Exact text to find (case-sensitive). Use unique text."
                        },
                        "close_after": {
                            "type": "boolean",
                            "description": "OPTIONAL: Close dialog after finding. Default: true."
                        }
                    },
                    "required": ["search_term"]
                }
            })

        # Add DOM manipulation tool if enabled
        if use_dom_manipulation:
            tools_config.append(DOM_TOOL_DEFINITION)

        # Add context reset and computer tools
        tools_config.extend([
            # Context reset tool - AI can reset its own context at milestones
            CONTEXT_RESET_TOOL_DEFINITION,
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
        ])

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
        # Send system prompt via 'system' parameter (cached by API, not re-sent each time)
        start_time = time.time()
        response = self.client.converse(
            modelId=self.model_id,
            messages=self.messages,
            system=[{"text": self.system_prompt}],  # System prompt sent separately
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
                elif tool_name == "dom_manipulation":
                    # Handle DOM manipulation tool
                    tool_input = tool_use.get('input', {})
                    action = Action(
                        type=ActionType.DOM_MANIPULATION,
                        params=tool_input,
                        id=tool_use.get('toolUseId', '')
                    )
                    actions.append(action)
                elif tool_name == "reset_context":
                    # Handle context reset tool
                    tool_input = tool_use.get('input', {})
                    action = Action(
                        type=ActionType.CONTEXT_RESET,
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
