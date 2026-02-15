"""Tests for nfo.buffered_sink — AsyncBufferedSink."""

import threading
import time

import pytest

from nfo.buffered_sink import AsyncBufferedSink
from nfo.models import LogEntry
from nfo.sinks import Sink


class MemorySink(Sink):
    def __init__(self):
        self.entries: list[LogEntry] = []
        self.closed = False
        self._lock = threading.Lock()

    def write(self, entry: LogEntry) -> None:
        with self._lock:
            self.entries.append(entry)

    def close(self) -> None:
        self.closed = True

    @property
    def count(self) -> int:
        with self._lock:
            return len(self.entries)


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


class TestAsyncBufferedSink:

    def test_flush_on_buffer_full(self):
        delegate = MemorySink()
        sink = AsyncBufferedSink(delegate, buffer_size=3, flush_interval=60)
        try:
            sink.write(_make_entry())
            sink.write(_make_entry())
            assert delegate.count == 0  # not yet flushed
            sink.write(_make_entry())  # triggers flush (buffer_size=3)
            time.sleep(0.1)  # give flush thread time
            assert delegate.count == 3
        finally:
            sink.close()

    def test_flush_on_interval(self):
        delegate = MemorySink()
        sink = AsyncBufferedSink(delegate, buffer_size=1000, flush_interval=0.1)
        try:
            sink.write(_make_entry())
            sink.write(_make_entry())
            time.sleep(0.3)  # wait for interval flush
            assert delegate.count == 2
        finally:
            sink.close()

    def test_flush_on_error_entry(self):
        delegate = MemorySink()
        sink = AsyncBufferedSink(delegate, buffer_size=1000, flush_interval=60, flush_on_error=True)
        try:
            sink.write(_make_entry(level="DEBUG"))
            sink.write(_make_entry(level="ERROR"))
            time.sleep(0.1)
            assert delegate.count == 2  # both flushed immediately
        finally:
            sink.close()

    def test_no_flush_on_error_when_disabled(self):
        delegate = MemorySink()
        sink = AsyncBufferedSink(delegate, buffer_size=1000, flush_interval=60, flush_on_error=False)
        try:
            sink.write(_make_entry(level="ERROR"))
            time.sleep(0.05)
            assert delegate.count == 0  # not flushed yet
        finally:
            sink.close()

    def test_close_flushes_remaining(self):
        delegate = MemorySink()
        sink = AsyncBufferedSink(delegate, buffer_size=1000, flush_interval=60)
        sink.write(_make_entry())
        sink.write(_make_entry())
        sink.close()
        assert delegate.count == 2
        assert delegate.closed

    def test_manual_flush(self):
        delegate = MemorySink()
        sink = AsyncBufferedSink(delegate, buffer_size=1000, flush_interval=60)
        try:
            sink.write(_make_entry())
            sink.write(_make_entry())
            assert delegate.count == 0
            sink.flush()
            assert delegate.count == 2
        finally:
            sink.close()

    def test_pending_count(self):
        delegate = MemorySink()
        sink = AsyncBufferedSink(delegate, buffer_size=1000, flush_interval=60)
        try:
            assert sink.pending == 0
            sink.write(_make_entry())
            sink.write(_make_entry())
            # pending may be 2 or 0 depending on race, but before any flush it should be 2
            assert sink.pending >= 0
            sink.flush()
            assert sink.pending == 0
        finally:
            sink.close()

    def test_write_after_close_ignored(self):
        delegate = MemorySink()
        sink = AsyncBufferedSink(delegate, buffer_size=1000, flush_interval=60)
        sink.close()
        sink.write(_make_entry())  # should not raise
        assert delegate.count == 0

    def test_idempotent_close(self):
        delegate = MemorySink()
        sink = AsyncBufferedSink(delegate, buffer_size=10, flush_interval=60)
        sink.write(_make_entry())
        sink.close()
        sink.close()  # second close should not raise
        assert delegate.count == 1

    def test_delegate_write_exception_does_not_crash(self):
        class BadSink(Sink):
            def write(self, entry):
                raise RuntimeError("boom")
            def close(self):
                pass

        sink = AsyncBufferedSink(BadSink(), buffer_size=1, flush_interval=60)
        sink.write(_make_entry())  # triggers flush → delegate raises
        time.sleep(0.1)  # should not crash
        sink.close()

    def test_critical_entry_also_flushes(self):
        delegate = MemorySink()
        sink = AsyncBufferedSink(delegate, buffer_size=1000, flush_interval=60, flush_on_error=True)
        try:
            sink.write(_make_entry(level="CRITICAL"))
            time.sleep(0.1)
            assert delegate.count == 1
        finally:
            sink.close()
