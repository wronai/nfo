"""Tests for nfo.binary_router — BinaryAwareRouter sink."""

import pytest

from nfo.binary_router import BinaryAwareRouter
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


class TestBinaryAwareRouter:

    def test_meta_log_routes_to_lightweight(self):
        light = MemorySink()
        full = MemorySink()
        router = BinaryAwareRouter(lightweight_sink=light, full_sink=full)

        entry = _make_entry(extra={"meta_log": True, "args_meta": []})
        router.write(entry)

        assert len(light.entries) == 1
        assert len(full.entries) == 0

    def test_normal_entry_routes_to_full(self):
        light = MemorySink()
        full = MemorySink()
        router = BinaryAwareRouter(lightweight_sink=light, full_sink=full)

        entry = _make_entry()
        router.write(entry)

        assert len(light.entries) == 0
        assert len(full.entries) == 1

    def test_large_data_routes_to_heavy(self):
        light = MemorySink()
        full = MemorySink()
        heavy = MemorySink()
        router = BinaryAwareRouter(
            lightweight_sink=light,
            full_sink=full,
            heavy_sink=heavy,
            size_threshold=100,
        )

        entry = _make_entry(args=(b"x" * 200,))
        router.write(entry)

        assert len(light.entries) == 0
        assert len(full.entries) == 0
        assert len(heavy.entries) == 1

    def test_large_data_no_heavy_sink_falls_to_full(self):
        light = MemorySink()
        full = MemorySink()
        router = BinaryAwareRouter(
            lightweight_sink=light,
            full_sink=full,
            size_threshold=100,
        )

        entry = _make_entry(args=(b"x" * 200,))
        router.write(entry)

        assert len(full.entries) == 1
        assert len(light.entries) == 0

    def test_large_return_value_routes_to_heavy(self):
        light = MemorySink()
        full = MemorySink()
        heavy = MemorySink()
        router = BinaryAwareRouter(
            lightweight_sink=light,
            full_sink=full,
            heavy_sink=heavy,
            size_threshold=50,
        )

        entry = _make_entry(return_value=b"x" * 100)
        router.write(entry)

        assert len(heavy.entries) == 1

    def test_close_closes_all_sinks(self):
        light = MemorySink()
        full = MemorySink()
        heavy = MemorySink()
        router = BinaryAwareRouter(
            lightweight_sink=light,
            full_sink=full,
            heavy_sink=heavy,
        )

        router.close()
        assert light.closed
        assert full.closed
        assert heavy.closed

    def test_close_without_heavy(self):
        light = MemorySink()
        full = MemorySink()
        router = BinaryAwareRouter(lightweight_sink=light, full_sink=full)

        router.close()
        assert light.closed
        assert full.closed

    def test_mixed_entries_routed_correctly(self):
        light = MemorySink()
        full = MemorySink()
        heavy = MemorySink()
        router = BinaryAwareRouter(
            lightweight_sink=light,
            full_sink=full,
            heavy_sink=heavy,
            size_threshold=100,
        )

        # meta_log entry → light
        router.write(_make_entry(extra={"meta_log": True}))
        # normal entry → full
        router.write(_make_entry())
        # large binary → heavy
        router.write(_make_entry(args=(b"x" * 200,)))
        # another meta → light
        router.write(_make_entry(extra={"meta_log": True, "args_meta": []}))

        assert len(light.entries) == 2
        assert len(full.entries) == 1
        assert len(heavy.entries) == 1

    def test_small_binary_not_routed_to_heavy(self):
        light = MemorySink()
        full = MemorySink()
        heavy = MemorySink()
        router = BinaryAwareRouter(
            lightweight_sink=light,
            full_sink=full,
            heavy_sink=heavy,
            size_threshold=1000,
        )

        entry = _make_entry(args=(b"small",))
        router.write(entry)

        assert len(full.entries) == 1
        assert len(heavy.entries) == 0
