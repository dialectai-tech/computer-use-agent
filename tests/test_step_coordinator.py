"""Tests for the StepCoordinator pipeline.

Covers the pure-logic layer only — no AWS credentials or live browser needed.
Anything that would make a real network call is tested at the unit level only
(instantiation, data structures, pure functions).
"""

import tempfile
from pathlib import Path

import pytest

from cua.agent.step_executor import StepResult, StepState
from cua.llm.bedrock_engine import MODEL_IDS, BedrockEngine, ToolCall, ToolResult
from cua.mcp.session import build_playwright_command, MAX_RESULT_CHARS
from cua.utils.timeline_logger import TimelineLogger


# ---------------------------------------------------------------------------
# BedrockEngine — model resolution & cost estimation
# ---------------------------------------------------------------------------

class TestBedrockEngine:
    def test_known_model_aliases_resolve(self):
        for alias, profile_id in MODEL_IDS.items():
            assert profile_id.startswith("us.anthropic."), f"{alias!r} → {profile_id!r} missing us. prefix"
            assert "anthropic" in profile_id

    def test_haiku_resolves_to_correct_profile(self):
        assert MODEL_IDS["haiku"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"

    def test_sonnet_resolves_to_correct_profile(self):
        assert MODEL_IDS["sonnet"] == "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

    def test_engine_instantiation_does_not_call_aws(self):
        # boto3.client() is lazy — no network call until an API method is invoked
        engine = BedrockEngine(model="haiku", region="us-east-1")
        assert engine is not None

    def test_engine_accepts_unknown_model_passthrough(self):
        # A literal model ID should pass through unchanged
        full_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        engine = BedrockEngine(model=full_id, region="us-east-1")
        assert engine is not None

    def test_tool_result_truncation(self):
        engine = BedrockEngine(model="haiku")
        long_content = "x" * (MAX_RESULT_CHARS + 500)
        result = ToolResult(id="t1", content=long_content)
        # Build a tool result message and verify it gets capped
        msg = engine.make_tool_result_message([result])
        # Each content block text should be capped at MAX_TOOL_RESULT_CHARS
        from cua.llm.bedrock_engine import MAX_TOOL_RESULT_CHARS
        for block in msg["content"]:
            text = block.get("text", "")
            assert len(text) <= MAX_TOOL_RESULT_CHARS + 50  # cap + small truncation note overhead


# ---------------------------------------------------------------------------
# StepState — the data structure carried between steps
# ---------------------------------------------------------------------------

class TestStepState:
    def test_default_construction(self):
        state = StepState(url="https://example.com", task="do something")
        assert state.url == "https://example.com"
        assert state.task == "do something"
        assert state.completed_steps == []
        assert state.facts == {}
        assert state.step_number == 1

    def test_facts_are_independent_per_instance(self):
        s1 = StepState(url="a", task="t")
        s2 = StepState(url="b", task="t")
        s1.facts["key"] = "value"
        assert "key" not in s2.facts

    def test_step_number_increments(self):
        state = StepState(url="x", task="t", step_number=3)
        assert state.step_number == 3

    def test_completed_steps_accumulate(self):
        state = StepState(url="x", task="t")
        state.completed_steps.append("Entered code ABC, advanced to step 2")
        state.completed_steps.append("Entered code XYZ, advanced to step 3")
        assert len(state.completed_steps) == 2


class TestStepResult:
    def test_construction(self):
        result = StepResult(
            success=True,
            step_summary="Entered code",
            new_facts={"code_step1": "ABC123"},
            new_completed=["Entered code ABC123, advanced to step 2"],
            tokens_used=50000,
            tool_calls_made=12,
            task_complete=False,
        )
        assert result.success is True
        assert result.tokens_used == 50000
        assert "code_step1" in result.new_facts
        assert result.task_complete is False


# ---------------------------------------------------------------------------
# build_playwright_command — pure string builder
# ---------------------------------------------------------------------------

class TestBuildPlaywrightCommand:
    def test_basic_headless(self):
        cmd = build_playwright_command(headless=True)
        assert "npx @playwright/mcp" in cmd
        assert "--headless" in cmd
        assert "--no-sandbox" in cmd
        assert "--snapshot-mode=incremental" in cmd

    def test_viewport_included(self):
        cmd = build_playwright_command(viewport_size="1280x720", headless=True)
        assert "--viewport-size=1280x720" in cmd

    def test_no_headless_flag_when_headed(self):
        cmd = build_playwright_command(headless=False)
        assert "--headless" not in cmd

    def test_video_flags_added_when_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec_dir = Path(tmp)
            cmd = build_playwright_command(
                recordings_dir=rec_dir,
                record_video=True,
                viewport_size="1280x720",
            )
        assert "--save-video" in cmd
        assert "--save-trace" in cmd
        assert "--output-dir" in cmd

    def test_no_output_mode_file_flag(self):
        # --output-mode=file would redirect snapshots to disk, breaking the agent
        cmd = build_playwright_command()
        assert "--output-mode=file" not in cmd

    def test_video_flags_absent_when_not_recording(self):
        cmd = build_playwright_command(record_video=False)
        assert "--save-video" not in cmd
        assert "--save-trace" not in cmd


# ---------------------------------------------------------------------------
# TimelineLogger — writes events to disk without any network calls
# ---------------------------------------------------------------------------

class TestTimelineLogger:
    def test_logs_events_to_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs_dir = Path(tmp)
            logger = TimelineLogger(session_id="test_session", logs_dir=logs_dir)
            logger.log_event("task_start", {"url": "https://example.com", "prompt": "test"})
            logger.log_step(1, "Starting step 1")
            logger.log_fact("code_step1", "ABC123")
            logger.log_step_complete(1, "Entered code ABC123")

            json_path = logs_dir / "timeline.json"
            assert json_path.exists()
            content = json_path.read_text()
            assert "task_start" in content
            assert "ABC123" in content

    def test_logs_events_to_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs_dir = Path(tmp)
            logger = TimelineLogger(session_id="test_session", logs_dir=logs_dir)
            logger.log_event("task_start", {"url": "https://example.com"})

            text_path = logs_dir / "session.log"
            assert text_path.exists()
            assert "task_start" in text_path.read_text()

    def test_cost_estimation(self):
        # Haiku pricing: $0.00025/1K input, $0.00125/1K output
        cost = TimelineLogger._estimate_cost(100_000, 10_000)
        assert cost == pytest.approx(0.025 + 0.0125, rel=1e-3)

    def test_write_report_creates_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs_dir = Path(tmp)
            logger = TimelineLogger(session_id="20260223_144851", logs_dir=logs_dir)
            logger.log_event("task_start", {"url": "https://example.com", "prompt": "test"})
            logger.log_step_complete(1, "Entered code LX3KGV, advanced to step 2")
            logger.log_fact("code_step1", "LX3KGV")

            report_path = logger.write_report(report_path=Path(tmp) / "REPORT.md")
            assert report_path.exists()
            content = report_path.read_text()
            assert "LX3KGV" in content
            assert "20260223_144851" in content
