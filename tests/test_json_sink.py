"""Tests for JSONSink."""

import json
import os
import tempfile

import pytest

from nfo.json_sink import JSONSink
from nfo.models import LogEntry


@pytest.fixture
def tmp_jsonl(tmp_path):
    return str(tmp_path / "test.jsonl")


def _make_entry(**overrides):
    defaults = dict(
        timestamp=LogEntry.now(),
        level="DEBUG",
        function_name="test_func",
        module="test_module",
        args=(1, 2),
        kwargs={"key": "val"},
        arg_types=["int", "int"],
        kwarg_types={"key": "str"},
        return_value=42,
        return_type="int",
        duration_ms=1.23,
    )
    defaults.update(overrides)
    return LogEntry(**defaults)


class TestJSONSink:

    def test_write_creates_file(self, tmp_jsonl):
        sink = JSONSink(tmp_jsonl)
        sink.write(_make_entry())
        assert os.path.exists(tmp_jsonl)

    def test_write_valid_json_lines(self, tmp_jsonl):
        sink = JSONSink(tmp_jsonl)
        sink.write(_make_entry(function_name="func_a"))
        sink.write(_make_entry(function_name="func_b"))

        with open(tmp_jsonl) as f:
            lines = f.readlines()
        assert len(lines) == 2

        obj1 = json.loads(lines[0])
        obj2 = json.loads(lines[1])
        assert obj1["function_name"] == "func_a"
        assert obj2["function_name"] == "func_b"

    def test_includes_all_fields(self, tmp_jsonl):
        sink = JSONSink(tmp_jsonl)
        entry = _make_entry(
            environment="prod",
            trace_id="abc123",
            version="1.0.0",
        )
        sink.write(entry)

        with open(tmp_jsonl) as f:
            obj = json.loads(f.readline())
        assert obj["environment"] == "prod"
        assert obj["trace_id"] == "abc123"
        assert obj["version"] == "1.0.0"
        assert obj["duration_ms"] == 1.23

    def test_includes_extra_fields(self, tmp_jsonl):
        sink = JSONSink(tmp_jsonl)
        entry = _make_entry(extra={"custom_key": "custom_val"})
        sink.write(entry)

        with open(tmp_jsonl) as f:
            obj = json.loads(f.readline())
        assert obj["extra"]["custom_key"] == "custom_val"

    def test_pretty_mode(self, tmp_jsonl):
        sink = JSONSink(tmp_jsonl, pretty=True)
        sink.write(_make_entry())

        with open(tmp_jsonl) as f:
            content = f.read()
        # Pretty mode should have newlines within the JSON object
        assert content.count("\n") > 2

    def test_delegates_to_downstream(self, tmp_jsonl):
        collected = []

        class FakeSink:
            def write(self, entry):
                collected.append(entry)
            def close(self):
                pass

        sink = JSONSink(tmp_jsonl, delegate=FakeSink())
        entry = _make_entry()
        sink.write(entry)

        assert len(collected) == 1
        assert collected[0] is entry

    def test_close_delegates(self, tmp_jsonl):
        closed = []

        class FakeSink:
            def write(self, entry):
                pass
            def close(self):
                closed.append(True)

        sink = JSONSink(tmp_jsonl, delegate=FakeSink())
        sink.close()
        assert closed == [True]

    def test_error_entry(self, tmp_jsonl):
        sink = JSONSink(tmp_jsonl)
        entry = _make_entry(
            level="ERROR",
            exception="division by zero",
            exception_type="ZeroDivisionError",
            traceback="Traceback...",
        )
        sink.write(entry)

        with open(tmp_jsonl) as f:
            obj = json.loads(f.readline())
        assert obj["level"] == "ERROR"
        assert obj["exception"] == "division by zero"
        assert obj["exception_type"] == "ZeroDivisionError"
