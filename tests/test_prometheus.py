"""Tests for PrometheusSink."""

import pytest

from nfo.models import LogEntry

# Skip all tests if prometheus_client is not installed
prometheus_client = pytest.importorskip("prometheus_client")

from nfo.prometheus import PrometheusSink


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


class TestPrometheusSink:

    def test_increments_call_counter(self):
        sink = PrometheusSink()
        sink.write(_make_entry())
        sink.write(_make_entry())
        metrics = sink.get_metrics().decode()
        assert 'nfo_calls_total{function="test_func",level="DEBUG",module="test_module"}' in metrics

    def test_increments_error_counter(self):
        sink = PrometheusSink()
        sink.write(_make_entry(level="ERROR"))
        metrics = sink.get_metrics().decode()
        assert 'nfo_errors_total{function="test_func",module="test_module"}' in metrics

    def test_records_duration_histogram(self):
        sink = PrometheusSink()
        sink.write(_make_entry(duration_ms=500.0))
        metrics = sink.get_metrics().decode()
        assert "nfo_duration_seconds_bucket" in metrics

    def test_no_duration_when_none(self):
        sink = PrometheusSink()
        sink.write(_make_entry(duration_ms=None))
        metrics = sink.get_metrics().decode()
        # Metric should be registered (TYPE line) but no observations recorded
        assert "nfo_duration_seconds" in metrics
        assert "nfo_calls_total" in metrics

    def test_delegates_to_downstream(self):
        collected = []

        class FakeSink:
            def write(self, entry):
                collected.append(entry)
            def close(self):
                pass

        sink = PrometheusSink(delegate=FakeSink())
        entry = _make_entry()
        sink.write(entry)
        assert len(collected) == 1
        assert collected[0] is entry

    def test_close_delegates(self):
        closed = []

        class FakeSink:
            def write(self, entry):
                pass
            def close(self):
                closed.append(True)

        sink = PrometheusSink(delegate=FakeSink())
        sink.close()
        assert closed == [True]

    def test_custom_prefix(self):
        sink = PrometheusSink(prefix="myapp")
        sink.write(_make_entry())
        metrics = sink.get_metrics().decode()
        assert "myapp_calls_total" in metrics
        assert "nfo_calls_total" not in metrics

    def test_multiple_functions(self):
        sink = PrometheusSink()
        sink.write(_make_entry(function_name="func_a"))
        sink.write(_make_entry(function_name="func_b"))
        sink.write(_make_entry(function_name="func_a", level="ERROR"))
        metrics = sink.get_metrics().decode()
        assert 'function="func_a"' in metrics
        assert 'function="func_b"' in metrics

    def test_get_metrics_returns_bytes(self):
        sink = PrometheusSink()
        sink.write(_make_entry())
        result = sink.get_metrics()
        assert isinstance(result, bytes)
        assert b"nfo_calls_total" in result
