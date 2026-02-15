"""Tests for @decision_log decorator and _build_decision_extra helper."""

import asyncio
from dataclasses import dataclass

import pytest

from nfo.decorators import decision_log, _build_decision_extra
from nfo.models import LogEntry
from nfo.logger import Logger
from nfo.sinks import Sink


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MemorySink(Sink):
    def __init__(self):
        self.entries: list[LogEntry] = []

    def write(self, entry: LogEntry):
        self.entries.append(entry)

    def close(self):
        pass


def _make_logger():
    sink = MemorySink()
    lg = Logger(name="test", sinks=[sink], level="DEBUG")
    return lg, sink


# ---------------------------------------------------------------------------
# _build_decision_extra
# ---------------------------------------------------------------------------

class TestBuildDecisionExtra:

    def test_dict_result_extracts_decision_and_reason(self):
        extra = _build_decision_extra("my_decision", {"decision": "ok", "reason": "within_limits"})
        assert extra["decision_name"] == "my_decision"
        assert extra["decision"] == "ok"
        assert extra["decision_reason"] == "within_limits"

    def test_dict_result_includes_extra_keys(self):
        extra = _build_decision_extra("d", {
            "decision": "downgraded",
            "reason": "budget_80%",
            "from_mode": "full",
            "to_mode": "hybrid",
        })
        assert extra["from_mode"] == "full"
        assert extra["to_mode"] == "hybrid"

    def test_dict_without_decision_key_uses_str(self):
        extra = _build_decision_extra("d", {"foo": "bar"})
        assert "decision" in extra
        # Should be str representation since no "decision" key
        assert "foo" in str(extra["decision"])

    def test_object_with_decision_and_reason_attrs(self):
        @dataclass
        class DecisionResult:
            decision: str
            reason: str

        obj = DecisionResult(decision="approved", reason="quota_ok")
        extra = _build_decision_extra("d", obj)
        assert extra["decision"] == "approved"
        assert extra["decision_reason"] == "quota_ok"

    def test_plain_string_result(self):
        extra = _build_decision_extra("d", "just_a_string")
        assert extra["decision"] == "just_a_string"

    def test_int_result(self):
        extra = _build_decision_extra("d", 42)
        assert extra["decision"] == "42"

    def test_none_result(self):
        extra = _build_decision_extra("d", None)
        assert extra["decision"] == "None"


# ---------------------------------------------------------------------------
# @decision_log — sync
# ---------------------------------------------------------------------------

class TestDecisionLogSync:

    def test_basic_dict_return(self):
        lg, sink = _make_logger()

        @decision_log(logger=lg)
        def check_budget():
            return {"decision": "ok", "reason": "within_limits"}

        result = check_budget()
        assert result == {"decision": "ok", "reason": "within_limits"}
        assert len(sink.entries) == 1

        entry = sink.entries[0]
        assert entry.level == "INFO"
        assert entry.extra["decision"] == "ok"
        assert entry.extra["decision_reason"] == "within_limits"
        assert entry.return_type == "decision"

    def test_custom_name(self):
        lg, sink = _make_logger()

        @decision_log(name="my_check", logger=lg)
        def some_func():
            return {"decision": "skip", "reason": "not_needed"}

        some_func()
        assert sink.entries[0].function_name == "my_check"
        assert sink.entries[0].extra["decision_name"] == "my_check"

    def test_default_name_is_qualname(self):
        lg, sink = _make_logger()

        @decision_log(logger=lg)
        def another_func():
            return {"decision": "x", "reason": "y"}

        another_func()
        assert "another_func" in sink.entries[0].function_name

    def test_custom_level(self):
        lg, sink = _make_logger()

        @decision_log(level="WARNING", logger=lg)
        def warn_func():
            return {"decision": "degraded", "reason": "load_high"}

        warn_func()
        assert sink.entries[0].level == "WARNING"

    def test_extra_dict_keys_propagated(self):
        lg, sink = _make_logger()

        @decision_log(logger=lg)
        def mode_check():
            return {
                "decision": "downgraded",
                "reason": "budget_exceeded",
                "from_mode": "full",
                "to_mode": "hybrid",
                "budget_pct": 87.5,
            }

        mode_check()
        extra = sink.entries[0].extra
        assert extra["from_mode"] == "full"
        assert extra["to_mode"] == "hybrid"
        assert extra["budget_pct"] == 87.5

    def test_non_dict_return(self):
        lg, sink = _make_logger()

        @decision_log(logger=lg)
        def simple():
            return "approved"

        result = simple()
        assert result == "approved"
        assert sink.entries[0].extra["decision"] == "approved"

    def test_exception_logged_and_reraised(self):
        lg, sink = _make_logger()

        @decision_log(logger=lg)
        def failing():
            raise ValueError("bad input")

        with pytest.raises(ValueError, match="bad input"):
            failing()

        assert len(sink.entries) == 1
        entry = sink.entries[0]
        assert entry.level == "ERROR"
        assert entry.exception == "bad input"
        assert entry.exception_type == "ValueError"

    def test_duration_recorded(self):
        lg, sink = _make_logger()

        @decision_log(logger=lg)
        def slow():
            import time
            time.sleep(0.01)
            return {"decision": "ok", "reason": "done"}

        slow()
        assert sink.entries[0].duration_ms is not None
        assert sink.entries[0].duration_ms >= 5  # at least ~10ms

    def test_bare_decorator_no_parens(self):
        lg, sink = _make_logger()

        @decision_log
        def bare():
            return {"decision": "bare", "reason": "test"}

        # bare decorator uses the global logger, not our test logger
        # Just verify it doesn't crash and returns correctly
        result = bare()
        assert result == {"decision": "bare", "reason": "test"}


# ---------------------------------------------------------------------------
# @decision_log — async
# ---------------------------------------------------------------------------

class TestDecisionLogAsync:

    def test_async_basic(self):
        lg, sink = _make_logger()

        @decision_log(logger=lg)
        async def async_check():
            return {"decision": "ok", "reason": "async_done"}

        result = asyncio.get_event_loop().run_until_complete(async_check())
        assert result == {"decision": "ok", "reason": "async_done"}
        assert len(sink.entries) == 1
        assert sink.entries[0].extra["decision"] == "ok"

    def test_async_exception(self):
        lg, sink = _make_logger()

        @decision_log(logger=lg)
        async def async_fail():
            raise RuntimeError("async boom")

        with pytest.raises(RuntimeError, match="async boom"):
            asyncio.get_event_loop().run_until_complete(async_fail())

        assert len(sink.entries) == 1
        assert sink.entries[0].level == "ERROR"
        assert sink.entries[0].exception == "async boom"

    def test_async_custom_name(self):
        lg, sink = _make_logger()

        @decision_log(name="async_budget", logger=lg)
        async def check():
            return {"decision": "downgraded", "reason": "hourly_limit"}

        asyncio.get_event_loop().run_until_complete(check())
        assert sink.entries[0].function_name == "async_budget"
        assert sink.entries[0].extra["decision_name"] == "async_budget"
