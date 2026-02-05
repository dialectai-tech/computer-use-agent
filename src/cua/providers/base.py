"""Base provider interface for computer use automation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
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

    @abstractmethod
    def create_initial_request(
        self,
        prompt: str,
        screenshot: Optional[str] = None,
        display_width: int = 1280,
        display_height: int = 720
    ) -> Any:
        """Create initial API request.

        Args:
            prompt: User's task description
            screenshot: Base64-encoded screenshot (optional)
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

    def get_response_text(self, response: Any) -> str:
        """Extract text content from response.

        Args:
            response: API response object

        Returns:
            Text content from response
        """
        return ""
