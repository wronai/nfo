"""Tests for WebhookSink."""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from unittest.mock import patch, MagicMock

import pytest

from nfo.webhook import WebhookSink
from nfo.models import LogEntry


def _make_entry(**overrides):
    defaults = dict(
        timestamp=LogEntry.now(),
        level="ERROR",
        function_name="test_func",
        module="test_module",
        args=(1, 2),
        kwargs={"key": "val"},
        arg_types=["int", "int"],
        kwarg_types={"key": "str"},
        return_value=None,
        return_type=None,
        exception="division by zero",
        exception_type="ZeroDivisionError",
        traceback="Traceback...",
        duration_ms=1.23,
    )
    defaults.update(overrides)
    return LogEntry(**defaults)


class TestWebhookSink:

    def test_only_sends_configured_levels(self):
        """Should not send for DEBUG when levels=["ERROR"]."""
        sink = WebhookSink(url="http://localhost:9999", levels=["ERROR"])
        with patch("nfo.webhook.urllib.request.urlopen") as mock_open:
            sink.write(_make_entry(level="DEBUG"))
            # Give thread time to run (if it was started)
            import time; time.sleep(0.1)
            mock_open.assert_not_called()

    def test_sends_for_error_level(self):
        """Should send for ERROR level."""
        sink = WebhookSink(url="http://localhost:9999")
        with patch("nfo.webhook.urllib.request.urlopen") as mock_open:
            sink.write(_make_entry(level="ERROR"))
            import time; time.sleep(0.2)
            mock_open.assert_called_once()

    def test_slack_payload_format(self):
        sink = WebhookSink(url="http://localhost:9999", format="slack")
        entry = _make_entry()
        payload = sink._build_payload(entry)
        assert "text" in payload
        assert "blocks" in payload
        assert payload["blocks"][0]["type"] == "header"

    def test_discord_payload_format(self):
        sink = WebhookSink(url="http://localhost:9999", format="discord")
        entry = _make_entry()
        payload = sink._build_payload(entry)
        assert "embeds" in payload
        assert payload["embeds"][0]["color"] == 0xFF0000

    def test_teams_payload_format(self):
        sink = WebhookSink(url="http://localhost:9999", format="teams")
        entry = _make_entry()
        payload = sink._build_payload(entry)
        assert payload["@type"] == "MessageCard"
        assert payload["themeColor"] == "FF0000"

    def test_raw_payload_format(self):
        sink = WebhookSink(url="http://localhost:9999", format="raw")
        entry = _make_entry()
        payload = sink._build_payload(entry)
        assert payload["function_name"] == "test_func"
        assert payload["level"] == "ERROR"

    def test_delegates_to_downstream(self):
        collected = []

        class FakeSink:
            def write(self, entry):
                collected.append(entry)
            def close(self):
                pass

        sink = WebhookSink(url="http://localhost:9999", delegate=FakeSink())
        entry = _make_entry(level="DEBUG")  # not ERROR, so no webhook send
        sink.write(entry)
        assert len(collected) == 1

    def test_close_delegates(self):
        closed = []

        class FakeSink:
            def write(self, entry):
                pass
            def close(self):
                closed.append(True)

        sink = WebhookSink(url="http://localhost:9999", delegate=FakeSink())
        sink.close()
        assert closed == [True]

    def test_custom_levels(self):
        sink = WebhookSink(url="http://localhost:9999", levels=["WARNING", "ERROR"])
        with patch("nfo.webhook.urllib.request.urlopen") as mock_open:
            sink.write(_make_entry(level="WARNING"))
            import time; time.sleep(0.2)
            mock_open.assert_called_once()

    def test_fire_and_forget_no_crash(self):
        """Should not crash even if URL is unreachable."""
        sink = WebhookSink(url="http://192.0.2.1:1", timeout=0.1)
        sink.write(_make_entry(level="ERROR"))
        import time; time.sleep(0.3)
        # No exception raised — fire-and-forget worked
