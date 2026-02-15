"""Tests for nfo.pipeline_sink — PipelineSink."""

import io
import time
from datetime import datetime, timezone

import pytest

from nfo.models import LogEntry
from nfo.pipeline_sink import PipelineSink
from nfo.sinks import Sink


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MemorySink(Sink):
    def __init__(self):
        self.entries = []

    def write(self, entry: LogEntry):
        self.entries.append(entry)

    def close(self):
        pass


def _make_entry(
    function_name="test_fn",
    level="INFO",
    duration_ms=None,
    exception=None,
    exception_type=None,
    extra=None,
):
    return LogEntry(
        timestamp=datetime.now(timezone.utc),
        level=level,
        function_name=function_name,
        module="test",
        args=(),
        kwargs={},
        arg_types=[],
        kwarg_types={},
        duration_ms=duration_ms,
        exception=exception,
        exception_type=exception_type,
        extra=extra or {},
    )


def _step_entry(run_id, step_name, duration_ms=10.0, **extra_kwargs):
    """Create a pipeline step entry."""
    extra = {
        "pipeline_run_id": run_id,
        "step_name": step_name,
        "decision": "executed",
        **extra_kwargs,
    }
    return _make_entry(
        function_name=f"pipeline.{step_name}",
        duration_ms=duration_ms,
        extra=extra,
    )


def _completion_entry(run_id, total_ms=100.0, total_cost=0.0, total_steps=3):
    """Create a pipeline completion marker entry."""
    return _make_entry(
        function_name="pipeline.complete",
        extra={
            "pipeline_run_id": run_id,
            "pipeline_complete": True,
            "total_ms": total_ms,
            "total_cost": total_cost,
            "total_steps": total_steps,
        },
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPipelineSinkBasic:

    def test_non_pipeline_entry_passes_through(self):
        mem = MemorySink()
        sink = PipelineSink(delegate=mem)
        entry = _make_entry(extra={})
        sink.write(entry)
        assert len(mem.entries) == 1
        assert mem.entries[0] is entry

    def test_non_pipeline_entry_no_delegate(self):
        sink = PipelineSink(delegate=None)
        entry = _make_entry(extra={})
        # Should not raise
        sink.write(entry)

    def test_pipeline_entry_buffered_until_complete(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False)
        sink.write(_step_entry("run1", "StepA", duration_ms=12.0))
        assert buf.getvalue() == ""  # still buffered
        assert sink.pending_runs == 1

    def test_complete_marker_flushes_run(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry("run1", "StepA", duration_ms=12.0))
        sink.write(_step_entry("run1", "StepB", duration_ms=45.0))
        sink.write(_completion_entry("run1", total_ms=57.0))

        output = buf.getvalue()
        assert "TICK #1" in output
        assert "run1" in output
        assert "StepA" in output
        assert "StepB" in output
        assert sink.pending_runs == 0
        assert sink.tick_count == 1

    def test_tick_counter_increments(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, tick_counter=5)

        sink.write(_step_entry("r1", "A"))
        sink.write(_completion_entry("r1"))
        assert sink.tick_count == 6

        sink.write(_step_entry("r2", "B"))
        sink.write(_completion_entry("r2"))
        assert sink.tick_count == 7


class TestPipelineSinkRendering:

    def test_box_drawing_chars_present(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry("run1", "StepA", duration_ms=12.0))
        sink.write(_completion_entry("run1"))
        output = buf.getvalue()
        assert "╔" in output
        assert "╗" in output
        assert "╠" in output
        assert "╣" in output
        assert "╚" in output
        assert "╝" in output
        assert "║" in output

    def test_step_with_error_shows_fail_icon(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        entry = _make_entry(
            function_name="pipeline.Analyze",
            duration_ms=3200.0,
            exception="RateLimitError",
            exception_type="RateLimitError",
            extra={
                "pipeline_run_id": "run1",
                "step_name": "Analyze",
            },
        )
        sink.write(entry)
        sink.write(_completion_entry("run1"))
        output = buf.getvalue()
        assert "✗" in output
        assert "RateLimitError" in output

    def test_skipped_step_shows_skip_icon(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        entry = _step_entry(
            "run1", "CropWindows", duration_ms=None,
            decision="skipped", decision_reason="can_run=False",
        )
        sink.write(entry)
        sink.write(_completion_entry("run1"))
        output = buf.getvalue()
        assert "⊘" in output or "skipped" in output

    def test_step_metrics_displayed(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry(
            "run1", "ScanWindows", duration_ms=12.0,
            windows_total=8, active_window="VSCode",
        ))
        sink.write(_completion_entry("run1"))
        output = buf.getvalue()
        assert "8 win" in output
        assert "VSCode" in output

    def test_cost_in_footer(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry("run1", "Analyze", duration_ms=890.0, cost_usd=0.0023))
        sink.write(_completion_entry("run1", total_ms=900.0, total_cost=0.0023))
        output = buf.getvalue()
        assert "$0.0023" in output

    def test_duration_in_footer(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry("run1", "A", duration_ms=500.0))
        sink.write(_completion_entry("run1", total_ms=500.0))
        output = buf.getvalue()
        assert "500ms" in output

    def test_decision_sub_line(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry(
            "run1", "Analyze", duration_ms=890.0,
            decision="budget_downgrade",
            decision_reason="hourly_limit_80%",
        ))
        sink.write(_completion_entry("run1"))
        output = buf.getvalue()
        assert "DECISION" in output
        assert "budget_downgrade" in output
        assert "hourly_limit_80%" in output

    def test_tokens_sub_line(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry(
            "run1", "Analyze", duration_ms=890.0,
            tokens_in=1200, tokens_out=350, model="gemini-2.0-flash",
        ))
        sink.write(_completion_entry("run1"))
        output = buf.getvalue()
        assert "1200→350tok" in output
        assert "gemini-2.0-flash" in output

    def test_ocr_sub_line(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry(
            "run1", "Analyze", duration_ms=890.0,
            ocr_engine="paddleocr", ocr_ms=23.0, ocr_chars=847,
        ))
        sink.write(_completion_entry("run1"))
        output = buf.getvalue()
        assert "OCR: paddleocr" in output
        assert "23ms" in output
        assert "847ch" in output


class TestPipelineSinkColor:

    def test_color_enabled_has_ansi(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=True, width=72)
        sink.write(_step_entry("run1", "StepA", duration_ms=12.0))
        sink.write(_completion_entry("run1"))
        output = buf.getvalue()
        assert "\033[" in output

    def test_color_disabled_no_ansi(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry("run1", "StepA", duration_ms=12.0))
        sink.write(_completion_entry("run1"))
        output = buf.getvalue()
        assert "\033[" not in output


class TestPipelineSinkTimeout:

    def test_stale_buffer_flushed(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, buffer_timeout=0.0)
        sink.write(_step_entry("run1", "StepA"))
        # Buffer timeout is 0 so next write should flush stale
        sink.write(_step_entry("run2", "StepB"))
        # run1 should have been flushed
        output = buf.getvalue()
        assert "TICK #1" in output
        assert "StepA" in output

    def test_close_flushes_all(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False)
        sink.write(_step_entry("run1", "StepA"))
        sink.write(_step_entry("run2", "StepB"))
        assert buf.getvalue() == ""  # still buffered
        sink.close()
        output = buf.getvalue()
        assert "TICK #1" in output
        assert "TICK #2" in output


class TestPipelineSinkMultipleRuns:

    def test_independent_runs(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False)

        # Interleave two runs
        sink.write(_step_entry("r1", "Step1"))
        sink.write(_step_entry("r2", "Step1"))
        sink.write(_step_entry("r1", "Step2"))
        sink.write(_completion_entry("r1"))

        output = buf.getvalue()
        assert "TICK #1" in output
        assert sink.pending_runs == 1  # r2 still buffered

        sink.write(_completion_entry("r2"))
        output = buf.getvalue()
        assert "TICK #2" in output
        assert sink.pending_runs == 0


class TestPipelineSinkFooter:

    def test_error_count_in_footer(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry("run1", "StepOK", duration_ms=10.0))
        sink.write(_make_entry(
            function_name="pipeline.StepFail",
            duration_ms=100.0,
            exception="Boom",
            exception_type="RuntimeError",
            extra={"pipeline_run_id": "run1", "step_name": "StepFail"},
        ))
        sink.write(_completion_entry("run1"))
        output = buf.getvalue()
        assert "1 errors" in output
        assert "1/2 steps" in output

    def test_steps_count_in_footer(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry("run1", "A", duration_ms=10.0))
        sink.write(_step_entry("run1", "B", duration_ms=20.0))
        sink.write(_step_entry("run1", "C", duration_ms=30.0))
        sink.write(_completion_entry("run1", total_ms=60.0))
        output = buf.getvalue()
        assert "3/3 steps" in output


class TestPipelineSinkDataFlow:

    def test_data_flow_shown_when_size_present(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry("run1", "capture_screen", duration_ms=45.0, data_size_kb=64))
        sink.write(_step_entry("run1", "build_context", duration_ms=5.0, context_length=1200))
        sink.write(_step_entry(
            "run1", "analyze", duration_ms=890.0,
            tokens_in=1200, tokens_out=350,
        ))
        sink.write(_completion_entry("run1"))
        output = buf.getvalue()
        assert "DATA" in output
        assert "capture_screen:64KB" in output
        assert "ctx:1200ch" in output
        assert "llm:1200→350tok" in output

    def test_data_flow_hidden_when_no_sizes(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry("run1", "StepA", duration_ms=10.0))
        sink.write(_completion_entry("run1"))
        output = buf.getvalue()
        assert "DATA" not in output

    def test_data_flow_arrows_separate_parts(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry("run1", "capture_screen", duration_ms=45.0, data_size_kb=64))
        sink.write(_step_entry("run1", "build_context", duration_ms=5.0, context_length=800))
        sink.write(_completion_entry("run1"))
        output = buf.getvalue()
        assert "→" in output  # arrow between flow parts


class TestPipelineSinkRollingCost:

    def test_session_cost_tracks_across_ticks(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry("r1", "Analyze", duration_ms=890.0, cost_usd=0.0023))
        sink.write(_completion_entry("r1", total_ms=900.0, total_cost=0.0023))
        assert sink.session_cost == pytest.approx(0.0023)

        sink.write(_step_entry("r2", "Analyze", duration_ms=700.0, cost_usd=0.0015))
        sink.write(_completion_entry("r2", total_ms=710.0, total_cost=0.0015))
        assert sink.session_cost == pytest.approx(0.0038)

    def test_cost_line_shown_when_cost_exists(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry("r1", "Analyze", cost_usd=0.005))
        sink.write(_completion_entry("r1", total_cost=0.005))
        output = buf.getvalue()
        assert "COST" in output
        assert "Session:" in output
        assert "$0.005" in output

    def test_cost_line_hidden_when_zero(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry("r1", "StepA", duration_ms=10.0))
        sink.write(_completion_entry("r1", total_cost=0.0))
        output = buf.getvalue()
        assert "COST" not in output

    def test_avg_per_tick_shown(self):
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        for i, cost in enumerate([0.002, 0.004, 0.006]):
            rid = f"r{i}"
            sink.write(_step_entry(rid, "Analyze", cost_usd=cost))
            sink.write(_completion_entry(rid, total_cost=cost))
        output = buf.getvalue()
        assert "avg/tick:" in output

    def test_session_cost_zero_initially(self):
        sink = PipelineSink(color=False)
        assert sink.session_cost == 0.0

    def test_cost_from_step_extra_when_completion_has_zero(self):
        """If completion total_cost is 0, fall back to summing step cost_usd."""
        buf = io.StringIO()
        sink = PipelineSink(stream=buf, color=False, width=72)
        sink.write(_step_entry("r1", "Analyze", cost_usd=0.003))
        sink.write(_completion_entry("r1", total_cost=0.0))
        # cost_usd from step should be summed
        assert sink.session_cost == pytest.approx(0.003)


class TestPipelineSinkDelegate:

    def test_close_calls_delegate_close(self):
        mem = MemorySink()
        sink = PipelineSink(delegate=mem)
        sink.close()
        # MemorySink.close() is a no-op but should not raise

    def test_delegate_receives_non_pipeline_entries(self):
        mem = MemorySink()
        sink = PipelineSink(delegate=mem)
        entry1 = _make_entry(extra={})
        entry2 = _make_entry(extra={"pipeline_run_id": "run1", "step_name": "A"})
        entry3 = _make_entry(extra={"some_other_key": True})
        sink.write(entry1)
        sink.write(entry2)
        sink.write(entry3)
        # Only entry1 and entry3 should pass through (no pipeline_run_id)
        assert len(mem.entries) == 2
        assert mem.entries[0] is entry1
        assert mem.entries[1] is entry3
