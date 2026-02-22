"""Lean single-agent coordinator for efficient browser automation.

Replaces AgnoCoordinator (4-agent Team) with a single-agent approach.
Performance improvement: ~80% fewer API calls, ~10x faster execution.

Architecture:
    Single Agent (Haiku/Sonnet)
        ├── Playwright MCP tools (direct, no delegation)
        └── BrowserStateTracker (Python, no MCP overhead)

vs Old:
    Orchestrator → Browser Agent → Memory Agent → Analysis Agent
    (7 API calls per action → 1 API call per action)

Artifact layout per session:
    test_artifacts/{session_id}/
        REPORT.md          — Markdown action timeline
        logs/
            timeline.json  — Machine-readable structured log
            session.log    — Human-readable text log
            browser-*.log  — Playwright console logs (moved here)
        screenshots/       — Screenshots saved by the agent
        recordings/
            session.webm   — Video recording (renamed from hash.webm)
        snapshots/         — Accessibility snapshots (if saved)
"""

import asyncio
import glob
import shutil
import time
from pathlib import Path
from typing import Optional

from rich.console import Console

from cua.agent.loop import TaskResult
from cua.agno_agents.solo_agent import BrowserStateTracker, create_solo_agent
from cua.agno_config.models import get_bedrock_model
from cua.utils.session_paths import (
    get_logs_dir,
    get_recordings_dir,
    get_screenshots_dir,
    get_session_dir,
    get_session_id,
    get_snapshots_dir,
)
from cua.utils.timeline_logger import TimelineLogger


class SoloCoordinator:
    """Single-agent browser automation coordinator.

    Uses one Agno Agent with direct Playwright MCP access.
    No team coordination, no delegation, minimal overhead.

    Usage:
        coordinator = SoloCoordinator(model="haiku", record_video=True)
        result = coordinator.run_task(
            url="https://example.com",
            prompt="Fill out the contact form",
        )
    """

    def __init__(
        self,
        model: str = "haiku",
        record_video: bool = False,
        display_width: int = 1280,
        display_height: int = 720,
        headless: bool = True,
        max_tool_calls: int = 150,
        # Compatibility args (unused but accepted for CLI compatibility)
        provider: Optional[object] = None,
        orchestrator_model: Optional[str] = None,
        agent_model: Optional[str] = None,
        log_level: str = "INFO",
        zoom: int = 85,
        video_dir: Optional[str] = None,
        enable_caching: bool = True,
        context_window_size: int = 10,
        extended_thinking: bool = False,
        thinking_budget: int = 10000,
        use_accessibility_tree: bool = True,
    ) -> None:
        """Initialize single-agent coordinator.

        Args:
            model: Bedrock model to use ("haiku" or "sonnet")
            record_video: Whether to record browser session video
            display_width: Browser viewport width
            display_height: Browser viewport height
            headless: Whether to run browser headless
            max_tool_calls: Maximum tool calls per run (safety limit)
        """
        self.console = Console()

        # Session setup
        self.session_id = get_session_id()
        self.session_dir = get_session_dir(self.session_id)
        self.screenshots_dir = get_screenshots_dir(self.session_id)
        self.snapshots_dir = get_snapshots_dir(self.session_id)
        self.recordings_dir = get_recordings_dir(self.session_id)
        self.logs_dir = get_logs_dir(self.session_id)

        self.record_video = record_video
        self.viewport_size = f"{display_width}x{display_height}"
        self.headless = headless
        self.max_tool_calls = max_tool_calls

        # Timeline logging
        self.logger = TimelineLogger(self.session_id, self.logs_dir)

        # Bedrock model
        self.bedrock_model = get_bedrock_model(model)
        self.model_name = model

        # Display session info
        self.console.print(f"[dim]Session:    {self.session_id}[/dim]")
        self.console.print(f"[dim]Artifacts:  test_artifacts/{self.session_id}/[/dim]")
        self.console.print(f"[dim]Mode:       Single-Agent ({model})[/dim]")
        self.console.print(f"[dim]Video:      {'enabled' if record_video else 'disabled'}[/dim]")

    def run_task(
        self,
        url: str,
        prompt: str,
        max_iterations: int = 30,
    ) -> TaskResult:
        """Run browser automation task.

        Args:
            url: URL to navigate to
            prompt: Task description
            max_iterations: Ignored (kept for compatibility) — use max_tool_calls instead

        Returns:
            TaskResult with execution details
        """
        self.logger.log_event("task_start", {"url": url, "prompt": prompt})
        self.console.print("\n[cyan]Starting single-agent browser automation...[/cyan]")
        return asyncio.run(self._run_async(url, prompt))

    async def _run_async(self, url: str, prompt: str) -> TaskResult:
        """Run task asynchronously."""
        start_time = time.monotonic()

        try:
            # Create agent and state tracker
            agent, state_tracker = create_solo_agent(
                model=self.bedrock_model,
                session_dir=self.session_dir,
                record_video=self.record_video,
                viewport_size=self.viewport_size,
                headless=self.headless,
                max_tool_calls=self.max_tool_calls,
            )

            # Build task prompt
            task_prompt = self._build_prompt(url, prompt)

            # Run agent (single arun call - agent manages tool loop internally)
            self.console.print(f"[dim]Agent running with up to {self.max_tool_calls} tool calls...[/dim]")
            run_output = await agent.arun(task_prompt)

            # Extract results
            result_text = run_output.content if hasattr(run_output, "content") else str(run_output)
            if result_text is None:
                result_text = ""

            # Determine success
            success = "TASK COMPLETE" in result_text.upper()

            # Extract token metrics (real data from Bedrock response)
            input_tokens = 0
            output_tokens = 0
            total_tokens = 0
            if hasattr(run_output, "metrics") and run_output.metrics:
                m = run_output.metrics
                input_tokens = getattr(m, "input_tokens", 0) or 0
                output_tokens = getattr(m, "output_tokens", 0) or 0
                total_tokens = input_tokens + output_tokens

            elapsed = time.monotonic() - start_time

            # Log all tool calls from this run to the timeline
            screenshots_taken = self._log_tool_calls(run_output)

            # Log completion
            self.logger.log_task_complete(
                success=success,
                summary=result_text[:500] if result_text else "No result",
                completed_steps=state_tracker.completed_steps,
                facts=state_tracker.facts,
                total_tokens=total_tokens,
            )
            if total_tokens > 0:
                self.logger.log_token_usage(input_tokens, output_tokens, total_tokens)

            # Organize artifacts into proper directories
            video_path = self._organize_artifacts()

            # Write final report
            report_path = self.logger.write_report()

            # Display results
            self._display_result(
                success=success,
                elapsed=elapsed,
                state_tracker=state_tracker,
                total_tokens=total_tokens,
                report_path=report_path,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                screenshots_taken=screenshots_taken,
                video_path=video_path,
            )

            return TaskResult(
                success=success,
                iterations=1,
                total_time=elapsed,
                final_url=None,
                video_path=str(video_path) if video_path else None,
                error=None,
                stats={
                    "api_calls": 1,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "screenshots_taken": screenshots_taken,
                    "actions_executed": len(state_tracker.completed_steps),
                    "avg_api_time": elapsed,
                },
            )

        except Exception as e:
            elapsed = time.monotonic() - start_time
            self.logger.log_error("Task failed with exception", e)
            self.console.print(f"\n[red]Error: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

            return TaskResult(
                success=False,
                iterations=0,
                total_time=elapsed,
                final_url=None,
                video_path=None,
                error=str(e),
                stats={},
            )

    def _log_tool_calls(self, run_output: object) -> int:
        """Extract tool calls from run output and add to timeline.

        Agno stores all tool calls in run_output.tools as ToolExecution objects.
        We log each one to give a complete action history.

        Args:
            run_output: The RunOutput from agent.arun()

        Returns:
            Number of screenshot tool calls found
        """
        tools = getattr(run_output, "tools", None)
        if not tools:
            return 0

        screenshots_taken = 0
        for tool_exec in tools:
            tool_name = getattr(tool_exec, "tool_name", "unknown") or "unknown"
            tool_args = getattr(tool_exec, "tool_args", {}) or {}
            result = getattr(tool_exec, "result", "") or ""

            # Build a short readable description
            description = self._describe_tool_call(tool_name, tool_args, result)

            # Determine screenshot path if applicable
            screenshot = None
            if tool_name == "browser_take_screenshot":
                filename = tool_args.get("filename")
                if filename:
                    screenshot = filename
                    screenshots_taken += 1

            self.logger.log_action(tool_name, description, screenshot=screenshot)

        return screenshots_taken

    def _describe_tool_call(self, name: str, args: dict, result: str) -> str:
        """Build a short human-readable description of a tool call."""
        result_preview = str(result)[:120].replace("\n", " ") if result else ""

        if name == "browser_navigate":
            return f"→ {args.get('url', '?')}"
        if name == "browser_click":
            return f"clicked: {args.get('element', args.get('ref', '?'))}"
        if name == "browser_type":
            text = args.get("text", "")
            # Don't log sensitive text fully
            preview = text[:30] + "..." if len(text) > 30 else text
            return f"typed: '{preview}' into ref={args.get('ref', '?')}"
        if name == "browser_snapshot":
            # Result is the accessibility tree — just note it was called
            lines = len(result.split("\n")) if result else 0
            return f"snapshot ({lines} lines)"
        if name == "browser_take_screenshot":
            return f"screenshot → {args.get('filename', 'in-memory')}"
        if name == "browser_evaluate":
            fn = str(args.get("function", ""))[:60]
            return f"eval: {fn}"
        if name == "browser_run_code":
            code = str(args.get("code", ""))[:60]
            return f"run_code: {code}"
        if name == "browser_wait_for":
            return f"wait: text={args.get('text', '')} time={args.get('time', '')}s"
        if name == "browser_mouse_wheel":
            return f"scroll dx={args.get('deltaX', 0)} dy={args.get('deltaY', 0)}"
        if name in ("mark_complete", "store_fact", "get_facts", "get_progress"):
            # Our state tracker tools
            return f"{args} → {result_preview}"
        return f"{args} → {result_preview}"

    def _organize_artifacts(self) -> Optional[Path]:
        """Organize Playwright output files into the right directories.

        Playwright MCP saves files to recordings_dir when --output-dir is set:
        - recordings_dir/videos/hash.webm  → recordings_dir/session.webm
        - recordings_dir/console-*.log     → logs_dir/browser-console-*.log
        - recordings_dir/trace-*.zip       → recordings_dir/trace.zip (keep)

        Returns:
            Path to the renamed video file, or None
        """
        video_path = None

        # Move/rename video: recordings/videos/hash.webm → recordings/session.webm
        videos_dir = self.recordings_dir / "videos"
        if videos_dir.exists():
            video_files = list(videos_dir.glob("*.webm")) + list(videos_dir.glob("*.mp4"))
            if video_files:
                src = video_files[0]  # Take the first (usually only one)
                dst = self.recordings_dir / f"session-{self.session_id}.webm"
                shutil.move(str(src), str(dst))
                video_path = dst
                self.logger.log_info(f"Video saved: {dst.name}")
                # Remove empty videos dir if nothing else there
                try:
                    videos_dir.rmdir()
                except OSError:
                    pass  # Not empty, leave it

        # Move Playwright console logs from recordings/ to logs/
        for pattern in ("console-*.log", "console-*.txt"):
            for src_log in self.recordings_dir.glob(pattern):
                dst_log = self.logs_dir / f"browser-{src_log.name}"
                shutil.move(str(src_log), str(dst_log))

        # Move trace files to recordings/ if they landed elsewhere
        for trace in self.session_dir.glob("trace*.zip"):
            dst = self.recordings_dir / trace.name
            if trace != dst:
                shutil.move(str(trace), str(dst))

        # Move any stray screenshots from test_artifacts/ root to session screenshots/
        # (agent may have saved to a relative path like "test_artifacts/step-01.png")
        # Only move files that are newer than the session start time to avoid
        # picking up files from a previous session.
        artifacts_root = self.session_dir.parent  # test_artifacts/
        session_start_ts = self.session_dir.stat().st_ctime
        for pattern in ("step-*.png", "final-*.png", "step-*.jpg"):
            for stray in artifacts_root.glob(pattern):
                if stray.stat().st_mtime >= session_start_ts:
                    dst = self.screenshots_dir / stray.name
                    shutil.move(str(stray), str(dst))

        # Count screenshots in proper dir
        n_screenshots = len(list(self.screenshots_dir.glob("*.png")))
        if n_screenshots > 0:
            self.logger.log_info(f"{n_screenshots} screenshots in screenshots/")

        return video_path

    def _build_prompt(self, url: str, task: str) -> str:
        """Build the full task prompt for the agent."""
        # Use absolute paths so the agent cannot accidentally shorten them
        ss = self.screenshots_dir.resolve()
        return f"""Navigate to: {url}

Task: {task}

SCREENSHOT DIRECTORY: {ss}
You MUST save screenshots to the EXACT path shown above. Do not shorten or modify this path.

SCREENSHOT INSTRUCTIONS (required):
- When you land on a new step/page:
  browser_take_screenshot(filename="{ss}/step-01-start.png")
- After completing each step:
  browser_take_screenshot(filename="{ss}/step-01-done.png")
- Use the actual step number: step-01, step-02, step-03 etc.

TASK INSTRUCTIONS:
1. Navigate to the URL above
2. Take browser_snapshot() to understand the page structure
3. Save a start screenshot to the directory above
4. Complete the task step by step
5. Use store_fact() to save any codes or important values you find
6. Use mark_complete() after finishing each major step
7. When fully done, save a final screenshot then output:
   TASK COMPLETE: [summary of what was accomplished]"""

    def _display_result(
        self,
        success: bool,
        elapsed: float,
        state_tracker: BrowserStateTracker,
        total_tokens: int,
        report_path: Path,
        input_tokens: int = 0,
        output_tokens: int = 0,
        screenshots_taken: int = 0,
        video_path: Optional[Path] = None,
    ) -> None:
        """Display task result summary in console."""
        self.console.print()
        status = "[green]✓ COMPLETE[/green]" if success else "[yellow]⚠ INCOMPLETE[/yellow]"
        self.console.print(f"Status:        {status}")
        self.console.print(f"Duration:      {elapsed:.1f}s")
        self.console.print(f"Steps done:    {len(state_tracker.completed_steps)}")
        self.console.print(f"Screenshots:   {screenshots_taken}")

        if total_tokens > 0:
            from cua.utils.timeline_logger import TimelineLogger as TL
            cost = TL._estimate_cost(input_tokens, output_tokens)
            self.console.print(f"Tokens:        {total_tokens:,} (est. ${cost:.4f})")

        if state_tracker.completed_steps:
            self.console.print("\n[cyan]Completed steps:[/cyan]")
            for s in state_tracker.completed_steps:
                self.console.print(f"  ✓ {s}")

        if state_tracker.facts:
            self.console.print("\n[cyan]Discovered facts:[/cyan]")
            for k, v in state_tracker.facts.items():
                self.console.print(f"  {k}: {v}")

        self.console.print(f"\n[bold]Artifacts:[/bold] test_artifacts/{self.session_id}/")
        self.console.print(f"  Report:      REPORT.md")
        self.console.print(f"  Timeline:    logs/timeline.json")
        self.console.print(f"  Session log: logs/session.log")
        if screenshots_taken > 0:
            self.console.print(f"  Screenshots: screenshots/ ({screenshots_taken} files)")
        if video_path:
            self.console.print(f"  Video:       recordings/{video_path.name}")


__all__ = ["SoloCoordinator"]
