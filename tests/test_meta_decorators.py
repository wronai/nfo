"""Tests for nfo.meta_decorators — @meta_log decorator."""

import pytest

from nfo import Logger
from nfo.decorators import set_default_logger
from nfo.meta import ThresholdPolicy
from nfo.meta_decorators import meta_log
from nfo.models import LogEntry
from nfo.sinks import Sink


class MemorySink(Sink):
    def __init__(self):
        self.entries: list[LogEntry] = []

    def write(self, entry: LogEntry) -> None:
        self.entries.append(entry)

    def close(self) -> None:
        self.entries.clear()


@pytest.fixture()
def logger():
    sink = MemorySink()
    lgr = Logger(name="test_meta", propagate_stdlib=False, sinks=[sink])
    set_default_logger(lgr)
    yield lgr, sink
    lgr.close()


class TestMetaLogSync:

    def test_small_args_logged_as_repr(self, logger):
        lgr, sink = logger

        @meta_log
        def add(a, b):
            return a + b

        result = add(1, 2)
        assert result == 3
        assert len(sink.entries) == 1
        entry = sink.entries[0]
        assert entry.extra.get("meta_log") is True
        # Small args should appear as repr strings
        args_meta = entry.extra["args_meta"]
        assert len(args_meta) == 2
        assert args_meta[0]["a"] == "1"
        assert args_meta[1]["b"] == "2"

    def test_large_bytes_extracted_as_metadata(self, logger):
        lgr, sink = logger
        policy = ThresholdPolicy(max_arg_bytes=100)

        @meta_log(policy=policy)
        def process(data: bytes, quality: int) -> bytes:
            return data[:10]

        big_data = b"\x89PNG" + b"\x00" * 200
        result = process(big_data, 85)
        assert result == big_data[:10]

        entry = sink.entries[0]
        assert entry.extra["meta_log"] is True
        args_meta = entry.extra["args_meta"]
        # data (>100 bytes) should be metadata dict
        data_meta = args_meta[0]["data"]
        assert isinstance(data_meta, dict)
        assert "size_bytes" in data_meta
        # quality (small int) should be repr
        quality_meta = args_meta[1]["quality"]
        assert quality_meta == "85"

    def test_return_value_not_stored_raw(self, logger):
        lgr, sink = logger

        @meta_log
        def echo(x):
            return x

        echo(42)
        entry = sink.entries[0]
        # args and kwargs should be empty tuples/dicts (metadata in extra)
        assert entry.args == ()
        assert entry.kwargs == {}
        assert entry.return_value is None

    def test_exception_logged_with_meta(self, logger):
        lgr, sink = logger

        @meta_log
        def fail(data):
            raise ValueError("bad data")

        with pytest.raises(ValueError, match="bad data"):
            fail(b"x" * 100)

        entry = sink.entries[0]
        assert entry.level == "ERROR"
        assert entry.exception == "bad data"
        assert entry.exception_type == "ValueError"
        assert entry.extra["meta_log"] is True

    def test_custom_level(self, logger):
        lgr, sink = logger

        @meta_log(level="WARNING")
        def warn():
            return "warned"

        warn()
        assert sink.entries[0].level == "WARNING"

    def test_extract_fields_custom(self, logger):
        lgr, sink = logger

        class FakeImage:
            def __init__(self, w, h):
                self.width = w
                self.height = h

        @meta_log(extract_fields={"img": lambda i: {"w": i.width, "h": i.height}})
        def resize(img, scale):
            return "done"

        resize(FakeImage(1920, 1080), 0.5)
        entry = sink.entries[0]
        img_meta = entry.extra["args_meta"][0]["img"]
        assert img_meta == {"w": 1920, "h": 1080}

    def test_duration_recorded(self, logger):
        lgr, sink = logger

        @meta_log
        def noop():
            return None

        noop()
        assert sink.entries[0].duration_ms is not None
        assert sink.entries[0].duration_ms >= 0

    def test_function_name_captured(self, logger):
        lgr, sink = logger

        @meta_log
        def my_func():
            pass

        my_func()
        assert "my_func" in sink.entries[0].function_name


class TestMetaLogAsync:

    @pytest.mark.asyncio
    async def test_async_basic(self, logger):
        lgr, sink = logger

        @meta_log
        async def fetch(url):
            return f"data from {url}"

        result = await fetch("http://example.com")
        assert result == "data from http://example.com"
        assert len(sink.entries) == 1
        entry = sink.entries[0]
        assert entry.extra["meta_log"] is True

    @pytest.mark.asyncio
    async def test_async_exception(self, logger):
        lgr, sink = logger

        @meta_log
        async def fail():
            raise RuntimeError("async error")

        with pytest.raises(RuntimeError, match="async error"):
            await fail()

        assert sink.entries[0].level == "ERROR"
        assert sink.entries[0].extra["meta_log"] is True

    @pytest.mark.asyncio
    async def test_async_large_bytes(self, logger):
        lgr, sink = logger
        policy = ThresholdPolicy(max_arg_bytes=50)

        @meta_log(policy=policy)
        async def process(data: bytes) -> bytes:
            return data

        big = b"\xff" * 100
        result = await process(big)
        assert result == big

        entry = sink.entries[0]
        data_meta = entry.extra["args_meta"][0]["data"]
        assert isinstance(data_meta, dict)
        assert data_meta["size_bytes"] == 100

    @pytest.mark.asyncio
    async def test_async_preserves_coroutine(self, logger):
        import inspect as ins

        @meta_log
        async def coro():
            return 1

        assert ins.iscoroutinefunction(coro)


class TestMetaLogReturnMeta:

    def test_large_return_extracted(self, logger):
        lgr, sink = logger
        policy = ThresholdPolicy(max_arg_bytes=8192, max_return_bytes=50)

        @meta_log(policy=policy)
        def make_big() -> bytes:
            return b"\x89PNG" + b"\x00" * 100

        make_big()
        entry = sink.entries[0]
        return_meta = entry.extra["return_meta"]
        assert isinstance(return_meta, dict)
        assert return_meta.get("type") == "image"

    def test_small_return_as_repr(self, logger):
        lgr, sink = logger

        @meta_log
        def small():
            return 42

        small()
        entry = sink.entries[0]
        assert entry.extra["return_meta"] == "42"
