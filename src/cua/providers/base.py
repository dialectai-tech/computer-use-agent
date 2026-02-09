"""Base provider interface for computer use automation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time
import difflib


class ActionType(Enum):
    """Types of actions that can be performed."""
    SCREENSHOT = "screenshot"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE = "type"
    KEY = "key"
    KEYPRESS = "keypress"
    SCROLL = "scroll"
    WAIT = "wait"
    MOUSE_MOVE = "mouse_move"
    SEARCH = "search"  # Search page content
    BROWSER_FIND = "browser_find"  # Browser find (Ctrl+F) to navigate to content
    DOM_MANIPULATION = "dom_manipulation"  # Direct DOM manipulation via CSS selectors
    CONTEXT_RESET = "context_reset"  # Reset conversation context at milestones


@dataclass
class Action:
    """Represents an action to be performed."""
    type: ActionType
    params: Dict[str, Any]
    id: str
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class AccessibilityTreeDiff:
    """Semantic diff of accessibility tree changes between actions.

    Captures what changed in the accessibility tree: elements added, removed,
    or modified. Much more compact than sending the full tree every time.
    """
    added_elements: List[Dict[str, Any]]  # Elements that appeared
    removed_elements: List[Dict[str, Any]]  # Elements that disappeared
    modified_elements: List[Dict[str, Any]]  # Elements with state/content changes
    summary: str  # Human-readable summary for LLM
    total_added: int = 0
    total_removed: int = 0
    total_modified: int = 0
    is_large_diff: bool = False  # If >60% changed, should send full tree instead


@dataclass
class ActionEvidence:
    """Evidence captured after executing an action.

    Used for multi-action support where each action in a response gets
    its own evidence (screenshot, page text, result) so the AI can see
    intermediate states, not just the final state.
    """
    action_id: str
    action_type: ActionType
    result: Dict[str, Any]  # Action execution result
    screenshot: Optional[bytes] = None  # Screenshot after action (if visual change)
    page_text: Optional[str] = None  # Page text if URL changed
    page_text_diff: Optional[str] = None  # Diff of page text changes (compact summary of what changed)
    accessibility_tree: Optional[dict] = None  # Full tree if baseline needed (page load, first action)
    accessibility_tree_diff: Optional[AccessibilityTreeDiff] = None  # Semantic diff if incremental update
    url: Optional[str] = None  # URL after action
    timestamp: float = None  # When action completed

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


def requires_screenshot(action: Action) -> bool:
    """Determine if an action requires screenshot evidence.

    Args:
        action: The action to check

    Returns:
        True if the action needs a screenshot, False otherwise
    """
    # Non-visual actions that don't need screenshots
    if action.type in (ActionType.SEARCH, ActionType.CONTEXT_RESET):
        return False

    # All other actions are visual or may change page state
    return True


def requires_page_text_capture(old_url: str, new_url: str) -> bool:
    """Determine if page text should be captured based on URL change.

    Args:
        old_url: URL before action
        new_url: URL after action

    Returns:
        True if page text should be captured, False otherwise
    """
    # Only capture page text when URL changes
    return old_url != new_url


def compute_page_text_diff(old_text: str, new_text: str, max_lines: int = 50) -> Optional[str]:
    """Compute a compact diff between two page texts.

    Creates a unified diff showing what changed, optimized for LLM consumption.
    Limits output to most significant changes to avoid token explosion.

    Args:
        old_text: Previous page text
        new_text: New page text
        max_lines: Maximum number of diff lines to return (default: 50)

    Returns:
        Compact diff string, or None if texts are identical or both empty
    """
    if not old_text and not new_text:
        return None

    if old_text == new_text:
        return None

    # Handle case where one is empty
    if not old_text:
        lines = new_text.split('\n')[:max_lines]
        return f"+ Added {len(new_text.split(chr(10)))} lines:\n" + '\n'.join(f"+ {line[:100]}" for line in lines[:10])

    if not new_text:
        lines = old_text.split('\n')[:max_lines]
        return f"- Removed {len(old_text.split(chr(10)))} lines:\n" + '\n'.join(f"- {line[:100]}" for line in lines[:10])

    # Compute unified diff
    old_lines = old_text.split('\n')
    new_lines = new_text.split('\n')

    # Use unified diff format (compact)
    diff_lines = list(difflib.unified_diff(
        old_lines,
        new_lines,
        lineterm='',
        n=1  # Context lines (minimal for compactness)
    ))

    if not diff_lines:
        return None

    # Filter out file headers and keep only actual changes
    significant_lines = []
    added_count = 0
    removed_count = 0

    for line in diff_lines:
        if line.startswith('+++') or line.startswith('---') or line.startswith('@@'):
            continue  # Skip headers

        if line.startswith('+'):
            added_count += 1
            if len(significant_lines) < max_lines:
                # Truncate long lines
                significant_lines.append(line[:150])
        elif line.startswith('-'):
            removed_count += 1
            if len(significant_lines) < max_lines:
                significant_lines.append(line[:150])

    if not significant_lines:
        return None

    # Create compact summary
    summary = f"📝 Page text changes (+{added_count} added, -{removed_count} removed):\n"
    summary += '\n'.join(significant_lines[:max_lines])

    if len(significant_lines) > max_lines:
        summary += f"\n... ({len(significant_lines) - max_lines} more changes not shown)"

    return summary


def truncate_a11y_tree_for_llm(tree: dict, max_depth: int = 8, max_children: int = 20, max_name_len: int = 100, max_value_len: int = 150) -> dict:
    """Truncate accessibility tree for LLM consumption while preserving structure.

    This creates a shallow copy of the tree with limits applied. The original tree
    is kept intact for accurate diff computation. This is purely for token efficiency
    when sending to the AI.

    Args:
        tree: Full accessibility tree (not modified)
        max_depth: Maximum depth to traverse (default: 8)
        max_children: Maximum children per node (default: 20)
        max_name_len: Maximum length for element names (default: 100)
        max_value_len: Maximum length for element values (default: 150)

    Returns:
        Truncated copy of tree suitable for LLM
    """
    # Thresholds for token efficiency
    # These are conservative to balance context vs completeness
    # - max_depth=8: Captures most UI structure without deep nesting
    # - max_children=20: Shows representative sample of repeating elements
    # - max_name_len=100: Enough for button labels, not entire paragraphs
    # - max_value_len=150: Enough for input values, not full form data

    def truncate_node(node: dict, depth: int) -> dict:
        """Recursively truncate a tree node."""
        if not node or isinstance(node, str):
            return node

        if depth > max_depth:
            # Depth limit reached - return placeholder
            return {"role": "...", "name": f"[Truncated at depth {max_depth}]"}

        # Copy node with truncated strings
        # Handle potential None values gracefully
        name = node.get("name", "")
        value = node.get("value", "")
        description = node.get("description", "")

        truncated = {
            "role": node.get("role", ""),
            "name": name[:max_name_len] if name else "",
            "value": value[:max_value_len] if value else None,
            "description": description[:max_name_len] if description else None,
            "checked": node.get("checked"),
            "disabled": node.get("disabled"),
            "expanded": node.get("expanded"),
        }

        # Remove None/empty values for compactness
        truncated = {k: v for k, v in truncated.items() if v not in (None, "")}

        # Truncate children
        if "children" in node and isinstance(node["children"], list):
            children = node["children"]
            if len(children) > max_children:
                # Take first N children + placeholder for remaining
                truncated["children"] = [truncate_node(child, depth + 1) for child in children[:max_children]]
                truncated["children"].append({
                    "role": "...",
                    "name": f"[{len(children) - max_children} more children not shown]"
                })
            else:
                truncated["children"] = [truncate_node(child, depth + 1) for child in children]

        return truncated

    if not tree:
        return {}

    return truncate_node(tree, 0)


def build_element_map(tree: dict, path: str = "") -> Dict[str, dict]:
    """Recursively build a flat map of elements with stable keys.

    Args:
        tree: Accessibility tree node
        path: Current path from root

    Returns:
        Dict mapping element_key → element_data
    """
    elements = {}

    if not tree or isinstance(tree, str):
        return elements

    # Generate stable key for this element
    role = tree.get("role", "unknown")
    name = tree.get("name", "")
    element_key = f"{role}:{name}:{path}"

    # Store element with key semantic attributes
    elements[element_key] = {
        "role": role,
        "name": name,
        "value": tree.get("value"),
        "description": tree.get("description"),
        "checked": tree.get("checked"),
        "disabled": tree.get("disabled"),
        "expanded": tree.get("expanded"),
        "path": path
    }

    # Recurse into children
    if "children" in tree and isinstance(tree["children"], list):
        for i, child in enumerate(tree["children"]):
            child_path = f"{path}/{role}[{i}]" if path else f"{role}[{i}]"
            child_elements = build_element_map(child, child_path)
            elements.update(child_elements)

    return elements


def compare_elements(old: dict, new: dict) -> Optional[Dict[str, tuple]]:
    """Compare two elements and return what changed.

    Args:
        old: Old element data
        new: New element data

    Returns:
        Dict of changed attributes with (old_value, new_value) tuples,
        or None if no meaningful changes
    """
    changes = {}

    # Compare meaningful attributes
    attributes_to_check = [
        "value", "checked", "disabled", "expanded",
        "name", "description"
    ]

    for attr in attributes_to_check:
        old_val = old.get(attr)
        new_val = new.get(attr)

        if old_val != new_val:
            changes[attr] = (old_val, new_val)

    return changes if changes else None


def generate_a11y_diff_summary(
    added: List[dict],
    removed: List[dict],
    modified: List[dict],
    max_items: int = 10
) -> str:
    """Generate human-readable summary of a11y changes for LLM consumption.

    Args:
        added: Added elements
        removed: Removed elements
        modified: Modified elements
        max_items: Max items to show per category

    Returns:
        Formatted summary string
    """
    lines = ["🌲 Accessibility Tree Changes:\n"]

    # Added elements
    if added:
        lines.append(f"Added ({len(added)}):")
        for elem in added[:max_items]:
            role = elem.get("role", "unknown")
            name = elem.get("name", "")
            disabled = " (disabled)" if elem.get("disabled") else ""
            lines.append(f"+ {role} \"{name}\"{disabled}")
        if len(added) > max_items:
            lines.append(f"  ... and {len(added) - max_items} more")
        lines.append("")

    # Removed elements
    if removed:
        lines.append(f"Removed ({len(removed)}):")
        for elem in removed[:max_items]:
            role = elem.get("role", "unknown")
            name = elem.get("name", "")
            lines.append(f"- {role} \"{name}\"")
        if len(removed) > max_items:
            lines.append(f"  ... and {len(removed) - max_items} more")
        lines.append("")

    # Modified elements
    if modified:
        lines.append(f"Modified ({len(modified)}):")
        for item in modified[:max_items]:
            key = item["key"]
            changes = item["changes"]

            # Parse key for display
            parts = key.split(":", 2)
            role = parts[0] if len(parts) > 0 else "unknown"
            name = parts[1] if len(parts) > 1 else ""

            # Format changes
            change_strs = []
            for attr, (old_val, new_val) in changes.items():
                # Format values nicely
                old_str = f"\"{old_val}\"" if old_val else "None"
                new_str = f"\"{new_val}\"" if new_val else "None"
                change_strs.append(f"{attr}: {old_str} → {new_str}")

            changes_text = ", ".join(change_strs)
            lines.append(f"~ {role} \"{name}\": {changes_text}")

        if len(modified) > max_items:
            lines.append(f"  ... and {len(modified) - max_items} more")

    # If no changes
    if not added and not removed and not modified:
        lines.append("(No semantic changes detected)")

    return "\n".join(lines)


def compute_a11y_tree_diff(old_tree: dict, new_tree: dict) -> Optional[AccessibilityTreeDiff]:
    """Compute semantic diff between two accessibility trees.

    Args:
        old_tree: Previous accessibility tree
        new_tree: Current accessibility tree

    Returns:
        AccessibilityTreeDiff with added/removed/modified elements,
        or None if trees are identical or both empty
    """
    if not old_tree and not new_tree:
        return None

    if old_tree == new_tree:
        return None

    # Handle case where one tree is empty
    if not old_tree:
        new_elements = build_element_map(new_tree)
        return AccessibilityTreeDiff(
            added_elements=list(new_elements.values()),
            removed_elements=[],
            modified_elements=[],
            summary=f"🌲 Accessibility Tree: Page loaded with {len(new_elements)} elements",
            total_added=len(new_elements),
            total_removed=0,
            total_modified=0,
            is_large_diff=False
        )

    if not new_tree:
        old_elements = build_element_map(old_tree)
        return AccessibilityTreeDiff(
            added_elements=[],
            removed_elements=list(old_elements.values()),
            modified_elements=[],
            summary=f"🌲 Accessibility Tree: {len(old_elements)} elements removed",
            total_added=0,
            total_removed=len(old_elements),
            total_modified=0,
            is_large_diff=True  # Everything removed = large change
        )

    # Step 1: Build element maps (key → element)
    old_elements = build_element_map(old_tree)
    new_elements = build_element_map(new_tree)

    # Step 2: Find added/removed elements
    old_keys = set(old_elements.keys())
    new_keys = set(new_elements.keys())

    added_keys = new_keys - old_keys
    removed_keys = old_keys - new_keys
    common_keys = old_keys & new_keys

    added_elements = [new_elements[k] for k in added_keys]
    removed_elements = [old_elements[k] for k in removed_keys]

    # Step 3: Find modified elements
    modified_elements = []
    for key in common_keys:
        old_elem = old_elements[key]
        new_elem = new_elements[key]

        changes = compare_elements(old_elem, new_elem)
        if changes:
            modified_elements.append({
                "key": key,
                "changes": changes,
                "old": old_elem,
                "new": new_elem
            })

    # Step 4: Check if diff is too large (>60% changed)
    total_elements = len(old_keys | new_keys)
    changed_elements = len(added_keys) + len(removed_keys) + len(modified_elements)
    is_large_diff = (changed_elements / total_elements) > 0.6 if total_elements > 0 else False

    # Step 5: Generate human-readable summary
    summary = generate_a11y_diff_summary(added_elements, removed_elements, modified_elements)

    return AccessibilityTreeDiff(
        added_elements=added_elements,
        removed_elements=removed_elements,
        modified_elements=modified_elements,
        summary=summary,
        total_added=len(added_elements),
        total_removed=len(removed_elements),
        total_modified=len(modified_elements),
        is_large_diff=is_large_diff
    )


@dataclass
class ProviderStats:
    """Statistics for provider API usage."""
    api_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    screenshots_taken: int = 0
    actions_executed: int = 0
    total_api_time: float = 0.0
    api_call_times: List[float] = field(default_factory=list)

    def add_tokens(self, input_tokens: int = 0, output_tokens: int = 0):
        """Add token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += input_tokens + output_tokens

    def add_api_call(self, duration: float):
        """Record an API call.

        Args:
            duration: Time taken for the API call in seconds
        """
        self.api_calls += 1
        self.total_api_time += duration
        self.api_call_times.append(duration)

    def add_screenshot(self):
        """Increment screenshot counter."""
        self.screenshots_taken += 1

    def add_action(self):
        """Increment action counter."""
        self.actions_executed += 1

    @property
    def avg_api_time(self) -> float:
        """Get average API call time."""
        if self.api_calls == 0:
            return 0.0
        return self.total_api_time / self.api_calls

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary.

        Returns:
            Dictionary representation of stats
        """
        result = {
            "api_calls": self.api_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "screenshots_taken": self.screenshots_taken,
            "actions_executed": self.actions_executed,
            "total_api_time": self.total_api_time,
            "avg_api_time": self.avg_api_time,
        }

        # Add cache stats if available
        if self.cache_creation_tokens > 0 or self.cache_read_tokens > 0:
            result["cache_creation_tokens"] = self.cache_creation_tokens
            result["cache_read_tokens"] = self.cache_read_tokens

        return result


class ComputerUseProvider(ABC):
    """Abstract base class for computer use providers."""

    def __init__(self, api_key: str, model: str = None):
        """Initialize provider.

        Args:
            api_key: API key for the provider
            model: Model name to use (provider-specific)
        """
        self.api_key = api_key
        self.model = model
        self.conversation_history = []
        self.stats = ProviderStats()

        # Configuration flags (set by agent)
        self.enable_caching = True
        self.extended_thinking = False
        self.thinking_budget = 10000

    @abstractmethod
    def create_initial_request(
        self,
        prompt: str,
        screenshot: Optional[str] = None,
        accessibility_tree: Optional[dict] = None,
        page_text: Optional[str] = None,
        display_width: int = 1024,
        display_height: int = 768
    ) -> Any:
        """Create initial API request.

        Args:
            prompt: User's task description
            screenshot: Base64-encoded screenshot (optional)
            accessibility_tree: Accessibility tree from browser (optional)
            page_text: Extracted text content from page (optional)
            display_width: Display width in pixels
            display_height: Display height in pixels

        Returns:
            API response object
        """
        pass

    @abstractmethod
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
            API response object
        """
        pass

    @abstractmethod
    def extract_actions(self, response: Any) -> List[Action]:
        """Extract actions from API response.

        Args:
            response: API response object

        Returns:
            List of actions to execute
        """
        pass

    @abstractmethod
    def is_task_complete(self, response: Any) -> bool:
        """Check if task is complete.

        Args:
            response: API response object

        Returns:
            True if task is complete, False otherwise
        """
        pass

    def reset_context(
        self,
        progress_summary: str,
        next_goal: str,
        current_screenshot: Optional[str] = None,
        current_page_info: Optional[Dict] = None
    ) -> bool:
        """Reset conversation context, keeping only essential information.

        Args:
            progress_summary: Summary of progress made so far
            next_goal: What needs to be done next
            current_screenshot: Current screenshot (optional)
            current_page_info: Current page information (optional)

        Returns:
            True if reset successful, False otherwise

        Note:
            Default implementation does nothing. Providers should override
            to implement context reset specific to their message format.
        """
        return False

    def get_response_text(self, response: Any) -> str:
        """Extract text content from response.

        Args:
            response: API response object

        Returns:
            Text content from response
        """
        return ""
