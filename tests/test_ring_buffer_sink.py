"""Tests for nfo.ring_buffer_sink — RingBufferSink."""

import pytest

from nfo.ring_buffer_sink import RingBufferSink
from nfo.models import LogEntry
from nfo.sinks import Sink


class MemorySink(Sink):
    def __init__(self):
        self.entries: list[LogEntry] = []
        self.closed = False

    def write(self, entry: LogEntry) -> None:
        self.entries.append(entry)

    def close(self) -> None:
        self.closed = True


def _make_entry(**overrides) -> LogEntry:
    defaults = dict(
        timestamp=LogEntry.now(),
        level="DEBUG",
        function_name="test_func",
        module="test",
        args=(),
        kwargs={},
        arg_types=[],
        kwarg_types={},
        return_value=None,
        return_type="NoneType",
        duration_ms=1.0,
    )
    defaults.update(overrides)
    return LogEntry(**defaults)


class TestRingBufferSink:

    def test_normal_entries_buffered_not_written(self):
        delegate = MemorySink()
        sink = RingBufferSink(delegate, capacity=100)
        sink.write(_make_entry(level="DEBUG"))
        sink.write(_make_entry(level="INFO"))
        sink.write(_make_entry(level="WARNING"))
        assert len(delegate.entries) == 0
        assert sink.buffered == 3

    def test_error_flushes_context_plus_error(self):
        delegate = MemorySink()
        sink = RingBufferSink(delegate, capacity=100)
        sink.write(_make_entry(level="DEBUG", function_name="step_1"))
        sink.write(_make_entry(level="INFO", function_name="step_2"))
        sink.write(_make_entry(level="ERROR", function_name="boom"))
        # 2 buffered context + 1 error = 3 written
        assert len(delegate.entries) == 3
        assert delegate.entries[0].function_name == "step_1"
        assert delegate.entries[1].function_name == "step_2"
        assert delegate.entries[2].function_name == "boom"
        assert sink.buffered == 0
        assert sink.flush_count == 1

    def test_critical_also_flushes(self):
        delegate = MemorySink()
        sink = RingBufferSink(delegate, capacity=100)
        sink.write(_make_entry(level="INFO"))
        sink.write(_make_entry(level="CRITICAL"))
        assert len(delegate.entries) == 2
        assert sink.flush_count == 1

    def test_custom_trigger_levels(self):
        delegate = MemorySink()
        sink = RingBufferSink(delegate, capacity=100, trigger_levels=["WARNING"])
        sink.write(_make_entry(level="DEBUG"))
        sink.write(_make_entry(level="WARNING"))
        # WARNING should trigger flush
        assert len(delegate.entries) == 2
        assert sink.flush_count == 1

    def test_error_does_not_trigger_with_custom_levels(self):
        delegate = MemorySink()
        sink = RingBufferSink(delegate, capacity=100, trigger_levels=["CRITICAL"])
        sink.write(_make_entry(level="ERROR"))
        # ERROR is NOT in trigger_levels
        assert len(delegate.entries) == 0
        assert sink.buffered == 1

    def test_capacity_evicts_oldest(self):
        delegate = MemorySink()
        sink = RingBufferSink(delegate, capacity=3)
        sink.write(_make_entry(level="DEBUG", function_name="a"))
        sink.write(_make_entry(level="DEBUG", function_name="b"))
        sink.write(_make_entry(level="DEBUG", function_name="c"))
        sink.write(_make_entry(level="DEBUG", function_name="d"))
        # "a" evicted, buffer has b, c, d
        assert sink.buffered == 3
        sink.write(_make_entry(level="ERROR", function_name="err"))
        # Should flush b, c, d + err = 4
        assert len(delegate.entries) == 4
        assert delegate.entries[0].function_name == "b"

    def test_include_trigger_false(self):
        delegate = MemorySink()
        sink = RingBufferSink(delegate, capacity=100, include_trigger=False)
        sink.write(_make_entry(level="DEBUG", function_name="ctx"))
        sink.write(_make_entry(level="ERROR", function_name="err"))
        # Only context written, not the error entry
        assert len(delegate.entries) == 1
        assert delegate.entries[0].function_name == "ctx"

    def test_buffer_cleared_after_flush(self):
        delegate = MemorySink()
        sink = RingBufferSink(delegate, capacity=100)
        sink.write(_make_entry(level="DEBUG"))
        sink.write(_make_entry(level="ERROR"))
        assert sink.buffered == 0
        # New entries after flush should buffer again
        sink.write(_make_entry(level="INFO"))
        assert sink.buffered == 1
        assert len(delegate.entries) == 2  # from previous flush

    def test_multiple_errors(self):
        delegate = MemorySink()
        sink = RingBufferSink(delegate, capacity=100)
        sink.write(_make_entry(level="DEBUG"))
        sink.write(_make_entry(level="ERROR"))  # flush 1
        sink.write(_make_entry(level="INFO"))
        sink.write(_make_entry(level="ERROR"))  # flush 2
        assert sink.flush_count == 2
        assert len(delegate.entries) == 4  # 1+1 from flush 1, 1+1 from flush 2

    def test_close_clears_buffer_and_closes_delegate(self):
        delegate = MemorySink()
        sink = RingBufferSink(delegate, capacity=100)
        sink.write(_make_entry(level="DEBUG"))
        sink.close()
        assert sink.buffered == 0
        assert delegate.closed

    def test_capacity_property(self):
        delegate = MemorySink()
        sink = RingBufferSink(delegate, capacity=500)
        assert sink.capacity == 500

    def test_empty_buffer_error_only_writes_error(self):
        delegate = MemorySink()
        sink = RingBufferSink(delegate, capacity=100)
        sink.write(_make_entry(level="ERROR", function_name="lonely_err"))
        assert len(delegate.entries) == 1
        assert delegate.entries[0].function_name == "lonely_err"

    def test_case_insensitive_trigger(self):
        delegate = MemorySink()
        sink = RingBufferSink(delegate, capacity=100, trigger_levels=["error"])
        sink.write(_make_entry(level="DEBUG"))
        sink.write(_make_entry(level="ERROR"))  # "ERROR".upper() in {"ERROR"}
        assert len(delegate.entries) == 2
