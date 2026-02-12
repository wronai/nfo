"""Tests for nfo.configure and nfo.logged."""

import os
import logging
import pytest

from nfo import configure, log_call, logged, skip, Logger
from nfo.configure import _parse_sink_spec, _StdlibBridge
from nfo.decorators import set_default_logger
from nfo.models import LogEntry
from nfo.sinks import Sink, SQLiteSink, CSVSink, MarkdownSink


class MemorySink(Sink):
    def __init__(self):
        self.entries: list[LogEntry] = []

    def write(self, entry: LogEntry) -> None:
        self.entries.append(entry)

    def close(self) -> None:
        self.entries.clear()


# -- _parse_sink_spec --------------------------------------------------------

class TestParseSinkSpec:

    def test_sqlite(self, tmp_path):
        sink = _parse_sink_spec(f"sqlite:{tmp_path / 'test.db'}")
        assert isinstance(sink, SQLiteSink)
        sink.close()

    def test_csv(self, tmp_path):
        sink = _parse_sink_spec(f"csv:{tmp_path / 'test.csv'}")
        assert isinstance(sink, CSVSink)

    def test_md(self, tmp_path):
        sink = _parse_sink_spec(f"md:{tmp_path / 'test.md'}")
        assert isinstance(sink, MarkdownSink)

    def test_invalid_no_colon(self):
        with pytest.raises(ValueError, match="Invalid sink spec"):
            _parse_sink_spec("sqlite")

    def test_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown sink type"):
            _parse_sink_spec("redis:localhost")


# -- configure() -------------------------------------------------------------

class TestConfigure:

    def test_returns_logger(self):
        lgr = configure(name="test-cfg", propagate_stdlib=False)
        assert isinstance(lgr, Logger)
        lgr.close()

    def test_with_sink_specs(self, tmp_path):
        db = tmp_path / "cfg.db"
        lgr = configure(
            name="test-cfg2",
            sinks=[f"sqlite:{db}"],
            propagate_stdlib=False,
        )
        assert len(lgr._sinks) == 1
        assert isinstance(lgr._sinks[0], SQLiteSink)
        lgr.close()

    def test_with_sink_instances(self):
        sink = MemorySink()
        lgr = configure(
            name="test-cfg3",
            sinks=[sink],
            propagate_stdlib=False,
        )
        assert lgr._sinks[0] is sink
        lgr.close()

    def test_env_override_level(self, monkeypatch):
        monkeypatch.setenv("NFO_LEVEL", "WARNING")
        lgr = configure(name="test-cfg4", propagate_stdlib=False)
        assert lgr.level == "WARNING"
        lgr.close()

    def test_env_override_sinks(self, tmp_path, monkeypatch):
        csv_path = tmp_path / "env.csv"
        monkeypatch.setenv("NFO_SINKS", f"csv:{csv_path}")
        lgr = configure(name="test-cfg5", propagate_stdlib=False)
        assert len(lgr._sinks) == 1
        assert isinstance(lgr._sinks[0], CSVSink)
        lgr.close()

    def test_decorators_use_configured_logger(self):
        sink = MemorySink()
        configure(name="test-cfg6", sinks=[sink], propagate_stdlib=False)

        @log_call
        def add(a, b):
            return a + b

        add(1, 2)
        assert len(sink.entries) == 1
        assert sink.entries[0].return_value == 3


# -- @logged class decorator -------------------------------------------------

class TestLogged:

    def test_wraps_public_methods(self):
        sink = MemorySink()
        lgr = Logger(name="test-logged", sinks=[sink], propagate_stdlib=False)
        set_default_logger(lgr)

        @logged
        class Calc:
            def add(self, a, b):
                return a + b

            def mul(self, a, b):
                return a * b

            def _private(self):
                return "secret"

        c = Calc()
        assert c.add(1, 2) == 3
        assert c.mul(3, 4) == 12
        assert c._private() == "secret"

        assert len(sink.entries) == 2  # add + mul, not _private
        lgr.close()

    def test_skip_decorator(self):
        sink = MemorySink()
        lgr = Logger(name="test-skip", sinks=[sink], propagate_stdlib=False)
        set_default_logger(lgr)

        @logged
        class Svc:
            def tracked(self):
                return 1

            @skip
            def untracked(self):
                return 2

        s = Svc()
        s.tracked()
        s.untracked()

        assert len(sink.entries) == 1  # only tracked
        lgr.close()

    def test_logged_with_level(self):
        sink = MemorySink()
        lgr = Logger(name="test-lvl", sinks=[sink], propagate_stdlib=False)
        set_default_logger(lgr)

        @logged(level="INFO")
        class Svc:
            def do(self):
                return "ok"

        Svc().do()
        assert sink.entries[0].level == "INFO"
        lgr.close()

    def test_logged_preserves_exceptions(self):
        sink = MemorySink()
        lgr = Logger(name="test-exc", sinks=[sink], propagate_stdlib=False)
        set_default_logger(lgr)

        @logged
        class Svc:
            def fail(self):
                raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            Svc().fail()

        assert len(sink.entries) == 1
        assert sink.entries[0].level == "ERROR"
        lgr.close()


# -- StdlibBridge ------------------------------------------------------------

class TestStdlibBridge:

    def test_bridge_captures_stdlib_logs(self):
        sink = MemorySink()
        lgr = Logger(name="test-bridge", sinks=[sink], propagate_stdlib=False)

        bridge = _StdlibBridge(lgr)
        bridge.setLevel(logging.DEBUG)

        stdlib_logger = logging.getLogger("test.bridge.module")
        stdlib_logger.addHandler(bridge)
        stdlib_logger.setLevel(logging.DEBUG)

        stdlib_logger.info("hello from stdlib")

        assert len(sink.entries) == 1
        assert sink.entries[0].level == "INFO"
        assert sink.entries[0].module == "test.bridge.module"
        assert sink.entries[0].return_value == "hello from stdlib"
        assert sink.entries[0].return_type == "str"
        assert sink.entries[0].extra["message"] == "hello from stdlib"
        assert sink.entries[0].extra["source"] == "stdlib_bridge"

        stdlib_logger.removeHandler(bridge)
        lgr.close()

    def test_bridge_qualified_function_name(self):
        sink = MemorySink()
        lgr = Logger(name="test-bridge-qual", sinks=[sink], propagate_stdlib=False)

        bridge = _StdlibBridge(lgr)
        bridge.setLevel(logging.DEBUG)

        stdlib_logger = logging.getLogger("pactown.sandbox")
        stdlib_logger.addHandler(bridge)
        stdlib_logger.setLevel(logging.DEBUG)

        stdlib_logger.info("[my-service] Starting build")

        entry = sink.entries[0]
        assert entry.module == "pactown.sandbox"
        # function_name should include the module prefix
        assert "pactown.sandbox" in entry.function_name
        assert entry.return_value == "[my-service] Starting build"

        stdlib_logger.removeHandler(bridge)
        lgr.close()

    def test_bridge_multiple_loggers(self):
        sink = MemorySink()
        lgr = Logger(name="test-bridge-multi", sinks=[sink], propagate_stdlib=False)

        bridge = _StdlibBridge(lgr)
        bridge.setLevel(logging.DEBUG)

        loggers = []
        for name in ["pactown.sandbox", "pactown.builders", "pactown.builders.mobile"]:
            sl = logging.getLogger(name)
            sl.addHandler(bridge)
            sl.setLevel(logging.DEBUG)
            sl.propagate = False  # prevent child→parent duplication
            loggers.append((sl, name))

        loggers[0][0].info("sandbox msg")
        loggers[1][0].warning("builder msg")
        loggers[2][0].error("mobile msg")

        assert len(sink.entries) == 3
        assert sink.entries[0].module == "pactown.sandbox"
        assert sink.entries[0].level == "INFO"
        assert sink.entries[1].module == "pactown.builders"
        assert sink.entries[1].level == "WARNING"
        assert sink.entries[2].module == "pactown.builders.mobile"
        assert sink.entries[2].level == "ERROR"

        for sl, _ in loggers:
            sl.removeHandler(bridge)
        lgr.close()

    def test_bridge_no_duplicate_from_child_propagation(self):
        """When both parent and child loggers are in the bridge list,
        only the parent gets the handler — child propagates automatically.
        This mirrors configure()'s dedup logic."""
        sink = MemorySink()
        lgr = Logger(name="test-dedup", sinks=[sink], propagate_stdlib=False)

        bridge = _StdlibBridge(lgr)
        bridge.setLevel(logging.DEBUG)

        # Only attach to parent (as configure() would do)
        parent = logging.getLogger("test.dedup.builders")
        parent.addHandler(bridge)
        parent.setLevel(logging.DEBUG)

        child = logging.getLogger("test.dedup.builders.mobile")
        child.setLevel(logging.DEBUG)
        # child.propagate=True by default → propagates to parent

        child.error("mobile build failed")

        # Should appear exactly once via propagation to parent
        mobile_entries = [
            e for e in sink.entries if e.return_value == "mobile build failed"
        ]
        assert len(mobile_entries) == 1
        assert mobile_entries[0].module == "test.dedup.builders.mobile"

        parent.removeHandler(bridge)
        lgr.close()

    def test_bridge_exception_info(self):
        sink = MemorySink()
        lgr = Logger(name="test-bridge-exc", sinks=[sink], propagate_stdlib=False)

        bridge = _StdlibBridge(lgr)
        bridge.setLevel(logging.DEBUG)

        stdlib_logger = logging.getLogger("test.bridge.exc")
        stdlib_logger.addHandler(bridge)
        stdlib_logger.setLevel(logging.DEBUG)

        try:
            raise ValueError("test error")
        except ValueError:
            stdlib_logger.exception("caught error")

        assert len(sink.entries) == 1
        assert sink.entries[0].exception == "test error"
        assert sink.entries[0].exception_type == "ValueError"

        stdlib_logger.removeHandler(bridge)
        lgr.close()
