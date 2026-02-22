"""Structured logging for Agno multi-agent system.

Provides JSON-structured logging for background execution (nohup support)
with comprehensive tracking of screenshots, recordings, and agent actions.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from cua.utils.session_paths import get_logs_dir, get_session_dir


class StructuredLogger:
    """JSON-structured logging for background execution."""

    def __init__(self, session_id: str, log_level: str = "INFO"):
        """Initialize structured logger.

        Args:
            session_id: Unique session ID
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.session_id = session_id
        self.log_level = log_level

        # Create session directory under test_artifacts
        self.session_dir = get_session_dir(session_id)
        self.logs_dir = get_logs_dir(session_id)

        # Setup log file
        self.log_file = self.logs_dir / "session.log"
        self.setup_logger()

    def setup_logger(self):
        """Setup Python logging with JSON format."""
        # Create logger
        self.logger = logging.getLogger(f"cua.{self.session_id}")
        self.logger.setLevel(getattr(logging, self.log_level))

        # Remove existing handlers
        self.logger.handlers = []

        # File handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(getattr(logging, self.log_level))

        # Console handler (for real-time monitoring)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, self.log_level))

        # Simple formatter (we'll add JSON structure in log methods)
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log_agent_action(
        self,
        agent_name: str,
        action: str,
        details: Dict[str, Any]
    ):
        """Log agent delegation and results.

        Args:
            agent_name: Name of the agent
            action: Action performed
            details: Action details
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "agent": agent_name,
            "action": action,
            "details": details
        }
        self.logger.info(json.dumps(log_entry))

    def log_screenshot(self, iteration: int, file_path: str, action: str):
        """Log screenshot capture with clear path.

        Args:
            iteration: Iteration number
            file_path: Path to screenshot file
            action: Action that triggered screenshot
        """
        self.logger.info(
            f"[SCREENSHOT] Iteration {iteration} | Action: {action} | Path: {file_path}"
        )

    def log_recording(self, session_id: str, file_path: str, duration: float):
        """Log video recording with path.

        Args:
            session_id: Session ID
            file_path: Path to video file
            duration: Duration in seconds
        """
        self.logger.info(
            f"[RECORDING] Session: {session_id} | Duration: {duration:.1f}s | Path: {file_path}"
        )

    def log_token_usage(
        self,
        agent: str,
        input_tokens: int,
        output_tokens: int
    ):
        """Log token consumption per agent.

        Args:
            agent: Agent name
            input_tokens: Input tokens consumed
            output_tokens: Output tokens generated
        """
        self.logger.info(
            f"[TOKENS] Agent: {agent} | Input: {input_tokens} | Output: {output_tokens}"
        )

    def log_info(self, message: str):
        """Log info message.

        Args:
            message: Message to log
        """
        self.logger.info(message)

    def log_warning(self, message: str):
        """Log warning message.

        Args:
            message: Message to log
        """
        self.logger.warning(f"[WARNING] {message}")

    def log_error(self, message: str, error: Optional[Exception] = None):
        """Log error message.

        Args:
            message: Error message
            error: Exception object (optional)
        """
        error_msg = f"[ERROR] {message}"
        if error:
            error_msg += f" - {str(error)}"
        self.logger.error(error_msg)


__all__ = ["StructuredLogger"]
