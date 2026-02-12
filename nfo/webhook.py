"""
Webhook sink for nfo — HTTP POST alerts to Slack, Discord, Teams, etc.

Sends log entries (typically ERROR-level) as JSON payloads to a webhook URL.
Zero external dependencies — uses only ``urllib`` from stdlib.
"""

from __future__ import annotations

import json
import threading
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Sequence

from nfo.models import LogEntry
from nfo.sinks import Sink


class WebhookSink(Sink):
    """
    Sink that POSTs log entries to an HTTP webhook endpoint.

    Designed for Slack, Discord, Microsoft Teams, or any service
    accepting JSON POST requests.

    Args:
        url: Webhook URL to POST to.
        delegate: Optional downstream sink to forward entries to.
        levels: Only send entries with these levels (default: ["ERROR"]).
        headers: Extra HTTP headers (e.g. Authorization).
        timeout: HTTP request timeout in seconds.
        format: Payload format — "slack", "discord", "teams", or "raw".
    """

    def __init__(
        self,
        url: str,
        delegate: Optional[Sink] = None,
        *,
        levels: Optional[Sequence[str]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 5.0,
        format: str = "slack",
    ) -> None:
        self.url = url
        self.delegate = delegate
        self.levels = set(l.upper() for l in (levels or ["ERROR"]))
        self.headers = headers or {}
        self.timeout = timeout
        self.format = format.lower()
        self._lock = threading.Lock()

    def _build_payload(self, entry: LogEntry) -> Dict[str, Any]:
        """Build webhook payload based on format."""
        d = entry.as_dict()
        func = d["function_name"]
        level = d["level"]
        duration = d["duration_ms"]
        exc = d["exception"]
        exc_type = d["exception_type"]
        env = d.get("environment", "")
        trace = d.get("trace_id", "")

        title = f"🚨 {level}: `{func}()`"
        body_parts = [f"**Function:** `{func}`"]
        if d["args"] and d["args"] != "()":
            body_parts.append(f"**Args:** `{d['args']}`")
        if exc:
            body_parts.append(f"**Exception:** `{exc_type}: {exc}`")
        if duration is not None:
            body_parts.append(f"**Duration:** {duration}ms")
        if env:
            body_parts.append(f"**Env:** {env}")
        if trace:
            body_parts.append(f"**Trace:** `{trace}`")
        body = "\n".join(body_parts)

        if self.format == "slack":
            return {
                "text": title,
                "blocks": [
                    {"type": "header", "text": {"type": "plain_text", "text": f"{level}: {func}()"}},
                    {"type": "section", "text": {"type": "mrkdwn", "text": body}},
                ],
            }
        elif self.format == "discord":
            return {
                "content": title,
                "embeds": [
                    {
                        "title": f"{level}: {func}()",
                        "description": body,
                        "color": 0xFF0000 if level == "ERROR" else 0xFFAA00,
                    }
                ],
            }
        elif self.format == "teams":
            return {
                "@type": "MessageCard",
                "summary": title,
                "themeColor": "FF0000" if level == "ERROR" else "FFAA00",
                "title": f"{level}: {func}()",
                "text": body,
            }
        else:  # raw
            return d

    def _send(self, payload: Dict[str, Any]) -> None:
        """Send payload via HTTP POST (fire-and-forget, no crash on failure)."""
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.url,
                data=data,
                headers={"Content-Type": "application/json", **self.headers},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=self.timeout)
        except Exception:
            pass  # fire-and-forget: don't crash on webhook failure

    def write(self, entry: LogEntry) -> None:
        if entry.level.upper() in self.levels:
            payload = self._build_payload(entry)
            # Send in a background thread to avoid blocking
            t = threading.Thread(target=self._send, args=(payload,), daemon=True)
            t.start()

        if self.delegate:
            self.delegate.write(entry)

    def close(self) -> None:
        if self.delegate:
            self.delegate.close()
