"""Timeline-based structured logging for browser automation sessions.

Provides correlated action timeline with timestamps, making it easy to:
- See exactly what happened in what order
- Correlate log entries with screenshots
- Measure time between steps
- Track token usage per action (when available)

Output: test_artifacts/{session_id}/logs/timeline.json
        test_artifacts/{session_id}/logs/session.log (human-readable)
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class TimelineLogger:
    """Structured timeline logger for browser automation sessions.

    Writes events to both a JSON timeline file (machine-readable)
    and a human-readable text log.
    """

    def __init__(self, session_id: str, logs_dir: Path) -> None:
        """Initialize timeline logger.

        Args:
            session_id: Unique session identifier (YYYYMMDD_HHMMSS format)
            logs_dir: Directory to write log files to
        """
        self.session_id = session_id
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.timeline_file = logs_dir / "timeline.json"
        self.text_log_file = logs_dir / "session.log"

        self.start_time = time.monotonic()
        self.start_wall = datetime.now(tz=timezone.utc)
        self.events: list[dict[str, Any]] = []

        # Write initial timeline entry
        self._append_event(
            "session_start",
            {
                "session_id": session_id,
                "start_time": self.start_wall.isoformat(),
            },
        )

    def log_event(
        self,
        event_type: str,
        data: Optional[dict[str, Any]] = None,
        screenshot: Optional[str] = None,
    ) -> None:
        """Log an event to the timeline.

        Args:
            event_type: Type of event (e.g. "navigate", "click", "task_start")
            data: Optional dictionary of event data
            screenshot: Optional path to associated screenshot file
        """
        self._append_event(event_type, data or {}, screenshot=screenshot)

    def log_action(
        self,
        action: str,
        details: str = "",
        screenshot: Optional[str] = None,
    ) -> None:
        """Log a browser action.

        Args:
            action: Action name (e.g. "click", "navigate", "type")
            details: Human-readable description of what happened
            screenshot: Optional path to screenshot taken after action
        """
        self._append_event(
            "browser_action",
            {"action": action, "details": details},
            screenshot=screenshot,
        )

    def log_step(self, step_num: int, description: str) -> None:
        """Log a task step starting.

        Args:
            step_num: Step number (1-based)
            description: What this step is doing
        """
        self._append_event("step_start", {"step": step_num, "description": description})

    def log_step_complete(self, step_num: int, description: str) -> None:
        """Log a task step completing.

        Args:
            step_num: Step number (1-based)
            description: What was accomplished
        """
        self._append_event("step_complete", {"step": step_num, "description": description})

    def log_fact(self, key: str, value: str) -> None:
        """Log discovery of an important fact (code, selector, etc).

        Args:
            key: Fact name
            value: Fact value
        """
        self._append_event("fact_discovered", {"key": key, "value": value})

    def log_token_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
    ) -> None:
        """Log token usage statistics.

        Args:
            input_tokens: Input token count
            output_tokens: Output token count
            total_tokens: Total token count
        """
        self._append_event(
            "token_usage",
            {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "estimated_cost_usd": self._estimate_cost(input_tokens, output_tokens),
            },
        )

    def log_info(self, message: str) -> None:
        """Log an informational message.

        Args:
            message: Info message
        """
        self._append_event("info", {"message": message})

    def log_error(self, message: str, error: Optional[Exception] = None) -> None:
        """Log an error.

        Args:
            message: Error description
            error: Optional exception object
        """
        data: dict[str, Any] = {"message": message}
        if error:
            data["error_type"] = type(error).__name__
            data["error_detail"] = str(error)
        self._append_event("error", data)

    def log_task_complete(
        self,
        success: bool,
        summary: str,
        completed_steps: list[str],
        facts: dict[str, str],
        total_tokens: int = 0,
    ) -> None:
        """Log task completion with full summary.

        Args:
            success: Whether task succeeded
            summary: Human-readable summary
            completed_steps: List of completed step descriptions
            facts: Key-value pairs of discovered facts
            total_tokens: Total tokens used (if available)
        """
        elapsed = time.monotonic() - self.start_time
        self._append_event(
            "task_complete",
            {
                "success": success,
                "summary": summary,
                "elapsed_seconds": round(elapsed, 1),
                "completed_steps": completed_steps,
                "facts_discovered": facts,
                "total_tokens": total_tokens,
            },
        )

    def write_report(self, report_path: Optional[Path] = None) -> Path:
        """Write a Markdown summary report.

        Args:
            report_path: Path to write report (defaults to logs_dir/report.md)

        Returns:
            Path where report was written
        """
        if report_path is None:
            report_path = self.logs_dir.parent / "REPORT.md"

        elapsed = time.monotonic() - self.start_time
        lines = [
            f"# Session Report: {self.session_id}",
            "",
            f"**Start**: {self.start_wall.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"**Duration**: {elapsed:.1f}s",
            "",
            "## Event Timeline",
            "",
        ]

        for evt in self.events:
            ts = evt.get("elapsed_s", 0)
            evt_type = evt.get("type", "?")
            data = evt.get("data", {})

            if evt_type == "browser_action":
                lines.append(f"- `+{ts:6.1f}s` **{data.get('action', '?')}**: {data.get('details', '')}")
            elif evt_type == "step_complete":
                lines.append(f"- `+{ts:6.1f}s` ✓ **Step {data.get('step')}**: {data.get('description', '')}")
            elif evt_type == "fact_discovered":
                lines.append(f"- `+{ts:6.1f}s` 📌 Fact: `{data.get('key')}` = `{data.get('value')}`")
            elif evt_type == "error":
                lines.append(f"- `+{ts:6.1f}s` ❌ Error: {data.get('message', '')}")
            elif evt_type in ("task_complete", "session_start"):
                pass  # Handled separately
            else:
                lines.append(f"- `+{ts:6.1f}s` {evt_type}: {json.dumps(data)}")

            if evt.get("screenshot"):
                lines.append(f"  - Screenshot: `{evt['screenshot']}`")

        # Add completion summary if present
        completion = next(
            (e for e in reversed(self.events) if e.get("type") == "task_complete"),
            None,
        )
        if completion:
            d = completion.get("data", {})
            lines += [
                "",
                "## Summary",
                "",
                f"**Status**: {'✅ SUCCESS' if d.get('success') else '❌ FAILED'}",
                f"**Summary**: {d.get('summary', 'N/A')}",
                f"**Total Tokens**: {d.get('total_tokens', 0):,}",
                "",
                "### Completed Steps",
            ]
            for s in d.get("completed_steps", []):
                lines.append(f"- {s}")
            lines += ["", "### Facts Discovered"]
            for k, v in d.get("facts_discovered", {}).items():
                lines.append(f"- **{k}**: {v}")

        report_path.write_text("\n".join(lines))
        return report_path

    def _append_event(
        self,
        event_type: str,
        data: dict[str, Any],
        screenshot: Optional[str] = None,
    ) -> None:
        """Append an event and write to files."""
        elapsed = time.monotonic() - self.start_time
        timestamp = datetime.now(tz=timezone.utc).isoformat()

        event: dict[str, Any] = {
            "time": timestamp,
            "elapsed_s": round(elapsed, 2),
            "type": event_type,
            "data": data,
        }
        if screenshot:
            event["screenshot"] = screenshot

        self.events.append(event)
        self._write_json_timeline()

        # Append to human-readable log
        with self.text_log_file.open("a") as f:
            details = json.dumps(data) if data else ""
            screenshot_note = f" [screenshot: {screenshot}]" if screenshot else ""
            f.write(f"[+{elapsed:7.2f}s] {event_type}: {details}{screenshot_note}\n")

    def _write_json_timeline(self) -> None:
        """Write full timeline to JSON file (overwrite)."""
        timeline = {
            "session_id": self.session_id,
            "start_time": self.start_wall.isoformat(),
            "events": self.events,
        }
        self.timeline_file.write_text(json.dumps(timeline, indent=2, default=str))

    @staticmethod
    def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD using Bedrock Haiku pricing.

        Haiku on Bedrock: ~$0.00025/1K input, ~$0.00125/1K output
        """
        input_cost = (input_tokens / 1000) * 0.00025
        output_cost = (output_tokens / 1000) * 0.00125
        return round(input_cost + output_cost, 6)
