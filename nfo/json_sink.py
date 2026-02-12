"""
JSON sink for nfo — structured JSON log output for ELK/Grafana Loki.

Writes one JSON object per line (JSON Lines format), suitable for
ingestion by Elasticsearch, Grafana Loki, Fluentd, etc.

Zero external dependencies — uses only stdlib ``json``.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional, TextIO

from nfo.models import LogEntry
from nfo.sinks import Sink


class JSONSink(Sink):
    """
    Append log entries as JSON Lines (one JSON object per line).

    Compatible with:
    - Elasticsearch / ELK stack (Filebeat → Logstash → ES)
    - Grafana Loki (Promtail)
    - Fluentd / Fluent Bit
    - Any JSON Lines consumer

    Args:
        file_path: Path to the JSON Lines file (default: ``logs.jsonl``).
        pretty: If True, indent JSON for readability (not recommended for production).
        delegate: Optional downstream sink to forward entries to.
    """

    def __init__(
        self,
        file_path: str | Path = "logs.jsonl",
        *,
        pretty: bool = False,
        delegate: Optional[Sink] = None,
    ) -> None:
        self.file_path = str(file_path)
        self.pretty = pretty
        self.delegate = delegate
        self._lock = threading.Lock()

    def write(self, entry: LogEntry) -> None:
        d = entry.as_dict()
        # Add extra fields if present
        if entry.extra:
            d["extra"] = {k: repr(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
                          for k, v in entry.extra.items()}

        indent = 2 if self.pretty else None
        line = json.dumps(d, ensure_ascii=False, default=str, indent=indent)

        with self._lock:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

        if self.delegate:
            self.delegate.write(entry)

    def close(self) -> None:
        if self.delegate:
            self.delegate.close()
