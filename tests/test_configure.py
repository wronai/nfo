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
        assert "hello from stdlib" in sink.entries[0].extra.get("message", "")

        stdlib_logger.removeHandler(bridge)
        lgr.close()
