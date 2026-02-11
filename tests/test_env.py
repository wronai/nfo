"""Tests for nfo.env (EnvTagger, DynamicRouter, DiffTracker)."""

import pytest

from nfo.env import (
    EnvTagger,
    DynamicRouter,
    DiffTracker,
    _detect_environment,
    generate_trace_id,
)
from nfo.models import LogEntry
from nfo.sinks import Sink


class MemorySink(Sink):
    def __init__(self):
        self.entries: list[LogEntry] = []

    def write(self, entry: LogEntry) -> None:
        self.entries.append(entry)

    def close(self) -> None:
        self.entries.clear()


def _make_entry(**overrides) -> LogEntry:
    defaults = dict(
        timestamp=LogEntry.now(),
        level="DEBUG",
        function_name="my_func",
        module="test",
        args=(1, 2),
        kwargs={},
        arg_types=["int", "int"],
        kwarg_types={},
        return_value=3,
        return_type="int",
        duration_ms=1.0,
    )
    defaults.update(overrides)
    return LogEntry(**defaults)


# -- EnvTagger ---------------------------------------------------------------

class TestEnvTagger:

    def test_tags_environment(self):
        mem = MemorySink()
        tagger = EnvTagger(mem, environment="prod", auto_detect=False)
        entry = _make_entry()
        tagger.write(entry)
        assert mem.entries[0].environment == "prod"

    def test_tags_trace_id(self):
        mem = MemorySink()
        tagger = EnvTagger(mem, trace_id="abc123", auto_detect=False)
        entry = _make_entry()
        tagger.write(entry)
        assert mem.entries[0].trace_id == "abc123"

    def test_tags_version(self):
        mem = MemorySink()
        tagger = EnvTagger(mem, version="1.2.3", auto_detect=False)
        entry = _make_entry()
        tagger.write(entry)
        assert mem.entries[0].version == "1.2.3"

    def test_auto_detect_env(self, monkeypatch):
        monkeypatch.setenv("NFO_ENV", "staging")
        mem = MemorySink()
        tagger = EnvTagger(mem, auto_detect=True)
        assert tagger.environment == "staging"

    def test_auto_detect_ci(self, monkeypatch):
        monkeypatch.setenv("CI", "true")
        monkeypatch.delenv("NFO_ENV", raising=False)
        monkeypatch.delenv("APP_ENV", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("ENV", raising=False)
        monkeypatch.delenv("NODE_ENV", raising=False)
        monkeypatch.delenv("FLASK_ENV", raising=False)
        monkeypatch.delenv("DJANGO_ENV", raising=False)
        monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
        monkeypatch.delenv("DOCKER_CONTAINER", raising=False)
        mem = MemorySink()
        tagger = EnvTagger(mem, auto_detect=True)
        assert tagger.environment == "ci"

    def test_does_not_overwrite_existing(self):
        mem = MemorySink()
        tagger = EnvTagger(mem, environment="prod", auto_detect=False)
        entry = _make_entry(environment="staging")
        tagger.write(entry)
        assert mem.entries[0].environment == "staging"

    def test_close_delegates(self):
        mem = MemorySink()
        tagger = EnvTagger(mem, auto_detect=False)
        tagger.close()

    def test_generate_trace_id(self):
        tid = generate_trace_id()
        assert len(tid) == 16
        assert tid != generate_trace_id()


# -- DynamicRouter ------------------------------------------------------------

class TestDynamicRouter:

    def test_routes_by_env(self):
        prod_sink = MemorySink()
        dev_sink = MemorySink()
        router = DynamicRouter(
            rules=[
                (lambda e: e.environment == "prod", prod_sink),
                (lambda e: e.environment == "dev", dev_sink),
            ],
        )
        entry_prod = _make_entry(environment="prod")
        entry_dev = _make_entry(environment="dev")
        router.write(entry_prod)
        router.write(entry_dev)
        assert len(prod_sink.entries) == 1
        assert len(dev_sink.entries) == 1

    def test_routes_by_level(self):
        error_sink = MemorySink()
        default_sink = MemorySink()
        router = DynamicRouter(
            rules=[
                (lambda e: e.level == "ERROR", error_sink),
            ],
            default=default_sink,
        )
        router.write(_make_entry(level="ERROR"))
        router.write(_make_entry(level="DEBUG"))
        assert len(error_sink.entries) == 1
        assert len(default_sink.entries) == 1

    def test_default_fallback(self):
        default_sink = MemorySink()
        router = DynamicRouter(rules=[], default=default_sink)
        router.write(_make_entry())
        assert len(default_sink.entries) == 1

    def test_no_default_no_match(self):
        router = DynamicRouter(rules=[], default=None)
        router.write(_make_entry())  # should not crash

    def test_first_match_wins(self):
        sink1 = MemorySink()
        sink2 = MemorySink()
        router = DynamicRouter(
            rules=[
                (lambda e: True, sink1),
                (lambda e: True, sink2),
            ],
        )
        router.write(_make_entry())
        assert len(sink1.entries) == 1
        assert len(sink2.entries) == 0

    def test_close_all_sinks(self):
        s1 = MemorySink()
        s2 = MemorySink()
        default = MemorySink()
        router = DynamicRouter(
            rules=[(lambda e: True, s1), (lambda e: False, s2)],
            default=default,
        )
        router.close()


# -- DiffTracker --------------------------------------------------------------

class TestDiffTracker:

    def test_no_diff_same_version(self):
        mem = MemorySink()
        tracker = DiffTracker(mem)
        e1 = _make_entry(version="1.0", return_value=3)
        e2 = _make_entry(version="1.0", return_value=3)
        tracker.write(e1)
        tracker.write(e2)
        assert "version_diff" not in mem.entries[1].extra

    def test_detects_diff_across_versions(self):
        mem = MemorySink()
        tracker = DiffTracker(mem)
        e1 = _make_entry(version="1.0", return_value=3)
        e2 = _make_entry(version="2.0", return_value=99)
        tracker.write(e1)
        tracker.write(e2)
        assert "version_diff" in mem.entries[1].extra
        assert "prev_version" in mem.entries[1].extra
        assert mem.entries[1].extra["prev_version"] == "1.0"

    def test_no_diff_without_version(self):
        mem = MemorySink()
        tracker = DiffTracker(mem)
        e1 = _make_entry(version=None, return_value=3)
        e2 = _make_entry(version=None, return_value=99)
        tracker.write(e1)
        tracker.write(e2)
        assert "version_diff" not in mem.entries[1].extra

    def test_different_functions_no_diff(self):
        mem = MemorySink()
        tracker = DiffTracker(mem)
        e1 = _make_entry(function_name="add", version="1.0", return_value=3)
        e2 = _make_entry(function_name="mul", version="2.0", return_value=99)
        tracker.write(e1)
        tracker.write(e2)
        assert "version_diff" not in mem.entries[1].extra

    def test_close_delegates(self):
        mem = MemorySink()
        tracker = DiffTracker(mem)
        tracker.close()
