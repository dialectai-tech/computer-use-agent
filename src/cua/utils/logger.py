"""Detailed logging system for agent iterations."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict


class AgentLogger:
    """Logger for detailed agent behavior tracking."""

    def __init__(self, log_dir: str = "./logs", session_name: Optional[str] = None):
        """Initialize logger.

        Args:
            log_dir: Directory for log files (will be gitignored)
            session_name: Optional session name (default: timestamp)
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create session-specific log file
        if session_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_name = f"session_{timestamp}"

        self.log_file = self.log_dir / f"{session_name}.log"
        self.iteration_count = 0

        # Write header
        self._write_header()

    def _write_header(self):
        """Write log file header."""
        with open(self.log_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write(f"AGENT SESSION LOG\n")
            f.write(f"Started: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")

    def log_iteration(
        self,
        iteration: int,
        prompt_sent: Optional[str] = None,
        response_received: Optional[str] = None,
        actions_taken: Optional[list] = None,
        action_results: Optional[list] = None,
        context_info: Optional[Dict[str, Any]] = None
    ):
        """Log a complete iteration.

        Args:
            iteration: Iteration number
            prompt_sent: The prompt sent to AI (text only, no images)
            response_received: The response from AI
            actions_taken: List of actions executed
            action_results: Results of each action
            context_info: Additional context (tokens, timing, etc.)
        """
        self.iteration_count = iteration

        with open(self.log_file, "a") as f:
            # Iteration header
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"ITERATION {iteration}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")

            # Context info
            if context_info:
                f.write("--- CONTEXT INFO ---\n")
                for key, value in context_info.items():
                    f.write(f"{key}: {value}\n")
                f.write("\n")

            # Prompt sent
            if prompt_sent:
                f.write("--- PROMPT SENT (Text Only) ---\n")
                f.write(prompt_sent)
                f.write("\n\n")

            # Response received
            if response_received:
                f.write("--- RESPONSE RECEIVED ---\n")
                f.write(response_received)
                f.write("\n\n")

            # Actions taken
            if actions_taken:
                f.write("--- ACTIONS TAKEN ---\n")
                for i, action in enumerate(actions_taken, 1):
                    f.write(f"{i}. {action}\n")
                f.write("\n")

            # Action results
            if action_results:
                f.write("--- ACTION RESULTS ---\n")
                for i, result in enumerate(action_results, 1):
                    f.write(f"{i}. {result}\n")
                f.write("\n")

            f.write("-" * 80 + "\n")

    def log_event(self, event_type: str, message: str, data: Optional[Dict] = None):
        """Log a specific event.

        Args:
            event_type: Type of event (ERROR, WARNING, INFO, etc.)
            message: Event message
            data: Optional event data
        """
        with open(self.log_file, "a") as f:
            f.write(f"\n[{event_type}] {datetime.now().isoformat()}\n")
            f.write(f"{message}\n")
            if data:
                f.write(f"Data: {json.dumps(data, indent=2)}\n")
            f.write("\n")

    def log_phase_transition(self, from_phase: int, to_phase: int, reason: str):
        """Log two-phase workflow transitions.

        Args:
            from_phase: Current phase
            to_phase: Next phase
            reason: Reason for transition
        """
        with open(self.log_file, "a") as f:
            f.write(f"\n{'*' * 80}\n")
            f.write(f"PHASE TRANSITION: Phase {from_phase} → Phase {to_phase}\n")
            f.write(f"Reason: {reason}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"{'*' * 80}\n\n")

    def log_summary(self, summary: Dict[str, Any]):
        """Log session summary at the end.

        Args:
            summary: Summary data (success, iterations, stats, etc.)
        """
        with open(self.log_file, "a") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write("SESSION SUMMARY\n")
            f.write("=" * 80 + "\n")
            f.write(json.dumps(summary, indent=2))
            f.write("\n\n")
            f.write(f"Ended: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n")

    def get_log_path(self) -> str:
        """Get the path to the log file.

        Returns:
            Path to log file
        """
        return str(self.log_file)
