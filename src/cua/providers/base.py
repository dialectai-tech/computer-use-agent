"""Base provider interface for computer use automation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time


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
