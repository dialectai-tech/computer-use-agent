"""Step-based browser automation coordinator with per-step context reset.

Architecture:
- Single Playwright MCP session: browser stays alive for the entire task
- Per-step isolated LLM conversation: context resets after each step
- Structured state carried forward: URL, facts, completed_steps only

This eliminates the quadratic token growth that occurs when accumulating
the full conversation history across hundreds of tool calls.

Token economics:
- Old approach (efficient-single-agent): 3.33M tokens for ~2 steps
- New approach: ~50-80K tokens per step × 30 steps = ~2M tokens total
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from rich.console import Console

from cua.agent.loop import TaskResult
from cua.agent.step_executor import StepResult, StepState, execute_step
from cua.llm.bedrock_engine import BedrockEngine
from cua.mcp.session import PlaywrightMCPSession
from cua.prompts.step_prompt import SYSTEM_PROMPT
from cua.utils.session_paths import (
    get_logs_dir,
    get_recordings_dir,
    get_screenshots_dir,
    get_session_dir,
    get_session_id,
    get_snapshots_dir,
)
from cua.utils.timeline_logger import TimelineLogger


# JavaScript to dismiss common overlays without burning LLM tokens
# Run before each step so the model starts with a clean page
_OVERLAY_DISMISS_JS = """() => {
    const selectors = [
        '[role="dialog"]',
        '[class*="overlay"]', '[class*="modal"]', '[class*="popup"]',
        '[class*="cookie"]', '[class*="consent"]', '[class*="banner"]',
        '[class*="backdrop"]', '[class*="Dialog"]', '[class*="Modal"]',
        '[aria-modal="true"]', '[data-overlay]'
    ];
    let removed = 0;
    selectors.forEach(sel => {
        document.querySelectorAll(sel).forEach(el => {
            el.remove();
            removed++;
        });
    });
    // Also remove body overflow:hidden that modals set (restores scrolling)
    document.body.style.overflow = '';
    document.documentElement.style.overflow = '';
    return 'cleared ' + removed + ' elements';
}"""


class StepCoordinator:
    """Browser automation coordinator with per-step LLM context reset.

    Each logical step runs in its own isolated mini-conversation (5-20 tool calls).
    The Playwright browser session persists throughout the entire task.
    Only structured state (URL, facts, completed_steps) carries forward.

    Usage:
        coordinator = StepCoordinator(model="haiku", record_video=True)
        result = coordinator.run_task(
            url="https://example.com",
            prompt="Complete the challenge",
            max_iterations=40,
        )
    """

    def __init__(
        self,
        model: str = "haiku",
        record_video: bool = False,
        display_width: int = 1280,
        display_height: int = 720,
        headless: bool = True,
        max_tool_calls_per_step: int = 20,
        # Compatibility args — accepted but unused (for CLI compatibility with other modes)
        provider: Optional[object] = None,
        max_tool_calls: int = 150,
        zoom: int = 85,
        video_dir: Optional[str] = None,
        enable_caching: bool = True,
        context_window_size: int = 10,
        extended_thinking: bool = False,
        thinking_budget: int = 10000,
        use_accessibility_tree: bool = True,
        orchestrator_model: Optional[str] = None,
        agent_model: Optional[str] = None,
        log_level: str = "INFO",
    ) -> None:
        self.console = Console()
        self.model = model
        self.record_video = record_video
        self.viewport_size = f"{display_width}x{display_height}"
        self.headless = headless
        self.max_tool_calls_per_step = max_tool_calls_per_step

        region = os.getenv("AWS_REGION", "us-east-1")
        self.engine = BedrockEngine(model=model, region=region)

        # Session setup (same pattern as SoloCoordinator)
        self.session_id = get_session_id()
        self.session_dir = get_session_dir(self.session_id)
        self.screenshots_dir = get_screenshots_dir(self.session_id)
        self.snapshots_dir = get_snapshots_dir(self.session_id)
        self.recordings_dir = get_recordings_dir(self.session_id)
        self.logs_dir = get_logs_dir(self.session_id)

        # Timeline logging
        self.logger = TimelineLogger(self.session_id, self.logs_dir)

        # Display session info
        self.console.print(f"[dim]Session:    {self.session_id}[/dim]")
        self.console.print(f"[dim]Artifacts:  test_artifacts/{self.session_id}/[/dim]")
        self.console.print(f"[dim]Mode:       Step-Reset ({model})[/dim]")
        self.console.print(f"[dim]Video:      {'enabled' if record_video else 'disabled'}[/dim]")

    def run_task(
        self,
        url: str,
        prompt: str,
        max_iterations: int = 40,
    ) -> TaskResult:
        """Run browser automation task with per-step context reset.

        Args:
            url: URL to navigate to
            prompt: Task description
            max_iterations: Maximum number of steps (each = one mini-conversation)

        Returns:
            TaskResult with execution details
        """
        self.logger.log_event("task_start", {"url": url, "prompt": prompt})
        self.console.print("\n[cyan]Starting step-reset browser automation...[/cyan]")
        return asyncio.run(self._run_async(url, prompt, max_iterations))

    async def _run_async(self, url: str, prompt: str, max_steps: int) -> TaskResult:
        """Run task asynchronously with per-step isolated conversations."""
        start_time = time.monotonic()

        # Create MCP session (browser stays alive for all steps)
        mcp_session = PlaywrightMCPSession(
            recordings_dir=self.recordings_dir if self.record_video else None,
            record_video=self.record_video,
            viewport_size=self.viewport_size,
            headless=self.headless,
        )

        last_result: Optional[StepResult] = None

        try:
            async with mcp_session as mcp:
                self.console.print("[dim]Playwright MCP session started[/dim]")

                # Navigate to starting URL before first step
                await mcp.call_tool("browser_navigate", {"url": url})
                self.console.print(f"[dim]Navigated to: {url}[/dim]")

                # Initialize step state (carries forward between steps)
                state = StepState(
                    url=url,
                    task=prompt,
                    completed_steps=[],
                    facts={},
                    step_number=1,
                )

                consecutive_stalls = 0

                for step_num in range(1, max_steps + 1):
                    state.step_number = step_num

                    self.console.print(
                        f"\n[bold cyan]━━━ Step {step_num}/{max_steps} ━━━[/bold cyan]"
                    )
                    self.logger.log_step(step_num, f"Starting step {step_num}")

                    # Pre-step: dismiss overlays twice (some appear after first removal)
                    await self._dismiss_overlays(mcp)
                    await self._dismiss_overlays(mcp)

                    # Sync current URL into state before the step
                    current_url = await self._get_current_url(mcp)
                    if current_url and current_url != state.url:
                        state.url = current_url

                    # Execute step in an isolated mini-conversation
                    # After this returns, the messages list is garbage collected
                    result = await execute_step(
                        engine=self.engine,
                        mcp=mcp,
                        state=state,
                        system_prompt=SYSTEM_PROMPT,
                        max_calls=self.max_tool_calls_per_step,
                    )
                    last_result = result

                    # Display step summary
                    self.console.print(
                        f"  [dim]Tool calls: {result.tool_calls_made} | "
                        f"Tokens: {result.tokens_used:,} | "
                        f"Total: {self.engine.total_tokens:,}[/dim]"
                    )
                    for s in result.new_completed:
                        self.console.print(f"  [green]✓[/green] {s}")
                    for k, v in result.new_facts.items():
                        self.console.print(f"  [cyan]📌[/cyan] {k}: {v}")

                    # Log to timeline
                    self.logger.log_event(
                        "step_result",
                        {
                            "step": step_num,
                            "tool_calls": result.tool_calls_made,
                            "tokens_this_step": result.tokens_used,
                            "total_tokens": self.engine.total_tokens,
                            "new_completed": result.new_completed,
                            "new_facts": result.new_facts,
                            "success": result.success,
                            "task_complete": result.task_complete,
                        },
                    )
                    for s in result.new_completed:
                        self.logger.log_step_complete(step_num, s)
                    for k, v in result.new_facts.items():
                        self.logger.log_fact(k, v)

                    # Detect URL change after the step
                    new_url = await self._get_current_url(mcp)
                    if new_url and new_url != state.url:
                        self.console.print(f"  [dim]URL → {new_url}[/dim]")
                        state.url = new_url

                    # Check if the full task is complete
                    if result.task_complete:
                        self.console.print("\n[bold green]✓ Task complete![/bold green]")
                        break

                    # Stall detection: if step made no progress, count it
                    if not result.success:
                        consecutive_stalls += 1
                        self.console.print(
                            f"  [yellow]⚠ No progress detected "
                            f"(stall {consecutive_stalls}/3)[/yellow]"
                        )
                        if consecutive_stalls >= 3:
                            self.console.print(
                                "[yellow]3 consecutive stalls — stopping task[/yellow]"
                            )
                            break
                    else:
                        consecutive_stalls = 0

            elapsed = time.monotonic() - start_time

            # Determine overall success
            task_complete = last_result.task_complete if last_result else False
            success = task_complete or bool(state.completed_steps)

            # Log completion and token usage
            self.logger.log_task_complete(
                success=success,
                summary=(
                    last_result.step_summary
                    if last_result
                    else "No steps executed"
                ),
                completed_steps=state.completed_steps,
                facts=state.facts,
                total_tokens=self.engine.total_tokens,
            )
            self.logger.log_token_usage(
                self.engine.total_input_tokens,
                self.engine.total_output_tokens,
                self.engine.total_tokens,
            )

            # Organize artifacts and write report
            video_path = self._organize_artifacts()
            report_path = self.logger.write_report()

            # Display final summary
            self._display_result(
                success=success,
                elapsed=elapsed,
                completed_steps=state.completed_steps,
                facts=state.facts,
                report_path=report_path,
                video_path=video_path,
            )

            return TaskResult(
                success=success,
                iterations=state.step_number,
                total_time=elapsed,
                final_url=state.url,
                video_path=str(video_path) if video_path else None,
                error=None,
                stats={
                    "api_calls": state.step_number,
                    "input_tokens": self.engine.total_input_tokens,
                    "output_tokens": self.engine.total_output_tokens,
                    "total_tokens": self.engine.total_tokens,
                    "screenshots_taken": 0,
                    "actions_executed": len(state.completed_steps),
                },
            )

        except Exception as exc:
            elapsed = time.monotonic() - start_time
            self.logger.log_error("Task failed with exception", exc)
            self.console.print(f"\n[red]Error: {exc}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

            return TaskResult(
                success=False,
                iterations=0,
                total_time=elapsed,
                final_url=None,
                video_path=None,
                error=str(exc),
                stats={},
            )

    async def _dismiss_overlays(self, mcp: PlaywrightMCPSession) -> None:
        """Remove common overlays before a step — zero LLM token cost."""
        try:
            await mcp.call_tool("browser_evaluate", {"function": _OVERLAY_DISMISS_JS})
        except Exception:
            pass  # Ignore errors — page might not be ready or have no overlays

    async def _get_current_url(self, mcp: PlaywrightMCPSession) -> Optional[str]:
        """Get the current browser URL via JavaScript."""
        try:
            result = await mcp.call_tool(
                "browser_evaluate",
                {"function": "() => window.location.href"},
            )
            url = result.strip()
            if url and url.startswith("http"):
                return url
        except Exception:
            pass
        return None

    def _organize_artifacts(self) -> Optional[Path]:
        """Organize Playwright output files into the session directories.

        Playwright MCP saves files to recordings_dir when --output-dir is set.
        """
        video_path = None

        # Move/rename video: recordings/videos/hash.webm → recordings/session-{id}.webm
        videos_dir = self.recordings_dir / "videos"
        if videos_dir.exists():
            video_files = list(videos_dir.glob("*.webm")) + list(videos_dir.glob("*.mp4"))
            if video_files:
                src = video_files[0]
                dst = self.recordings_dir / f"session-{self.session_id}.webm"
                shutil.move(str(src), str(dst))
                video_path = dst
                self.logger.log_info(f"Video saved: {dst.name}")
                try:
                    videos_dir.rmdir()
                except OSError:
                    pass

        # Move Playwright console logs from recordings/ to logs/
        for pattern in ("console-*.log", "console-*.txt"):
            for src_log in self.recordings_dir.glob(pattern):
                dst_log = self.logs_dir / f"browser-{src_log.name}"
                shutil.move(str(src_log), str(dst_log))

        # Move trace files to recordings/
        for trace in self.session_dir.glob("trace*.zip"):
            dst = self.recordings_dir / trace.name
            if trace != dst:
                shutil.move(str(trace), str(dst))

        return video_path

    def _display_result(
        self,
        success: bool,
        elapsed: float,
        completed_steps: list[str],
        facts: dict[str, str],
        report_path: Path,
        video_path: Optional[Path] = None,
    ) -> None:
        """Display task result summary in the console."""
        self.console.print()
        status = "[green]✓ COMPLETE[/green]" if success else "[yellow]⚠ INCOMPLETE[/yellow]"
        self.console.print(f"Status:        {status}")
        self.console.print(f"Duration:      {elapsed:.1f}s")
        self.console.print(f"Steps done:    {len(completed_steps)}")

        total_tokens = self.engine.total_tokens
        if total_tokens > 0:
            cost = TimelineLogger._estimate_cost(
                self.engine.total_input_tokens, self.engine.total_output_tokens
            )
            self.console.print(f"Tokens:        {total_tokens:,} (est. ${cost:.4f})")

        if completed_steps:
            self.console.print("\n[cyan]Completed steps:[/cyan]")
            for s in completed_steps:
                self.console.print(f"  ✓ {s}")

        if facts:
            self.console.print("\n[cyan]Discovered facts:[/cyan]")
            for k, v in facts.items():
                self.console.print(f"  {k}: {v}")

        self.console.print(f"\n[bold]Artifacts:[/bold] test_artifacts/{self.session_id}/")
        self.console.print("  Report:      REPORT.md")
        self.console.print("  Timeline:    logs/timeline.json")
        self.console.print("  Session log: logs/session.log")
        if video_path:
            self.console.print(f"  Video:       recordings/{video_path.name}")


__all__ = ["StepCoordinator"]
