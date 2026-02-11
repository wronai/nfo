"""
Multi-environment log correlation and dynamic sink routing.

Provides:
- EnvTagger: auto-tags log entries with environment, trace_id, version
- DynamicRouter: routes entries to different sinks based on environment
- DiffTracker: tracks input/output changes between function versions
"""

from __future__ import annotations

import hashlib
import os
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence

from nfo.models import LogEntry
from nfo.sinks import Sink


# ---------------------------------------------------------------------------
# Multi-env log correlation
# ---------------------------------------------------------------------------

def _detect_environment() -> str:
    """Auto-detect environment from common env vars."""
    for var in ("NFO_ENV", "APP_ENV", "ENVIRONMENT", "ENV", "NODE_ENV", "FLASK_ENV", "DJANGO_ENV"):
        val = os.environ.get(var)
        if val:
            return val.strip().lower()

    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return "k8s"
    if os.environ.get("DOCKER_CONTAINER") or os.path.exists("/.dockerenv"):
        return "docker"
    if os.environ.get("CI"):
        return "ci"
    if os.environ.get("GITHUB_ACTIONS"):
        return "github-actions"
    if os.environ.get("GITLAB_CI"):
        return "gitlab-ci"

    return "local"


def _detect_trace_id() -> Optional[str]:
    """Extract trace ID from common tracing env vars."""
    for var in ("TRACE_ID", "X_TRACE_ID", "OTEL_TRACE_ID", "DD_TRACE_ID",
                "PACTOWN_TRACE_ID", "REQUEST_ID"):
        val = os.environ.get(var)
        if val:
            return val.strip()
    return None


def _detect_version() -> Optional[str]:
    """Extract app version from common env vars or git."""
    for var in ("APP_VERSION", "VERSION", "GIT_SHA", "GIT_COMMIT",
                "GITHUB_SHA", "CI_COMMIT_SHA"):
        val = os.environ.get(var)
        if val:
            return val.strip()[:12]
    return None


def generate_trace_id() -> str:
    """Generate a new trace ID."""
    return uuid.uuid4().hex[:16]


class EnvTagger(Sink):
    """
    Sink wrapper that auto-tags every log entry with:
    - environment (dev/staging/prod/k8s/docker/ci)
    - trace_id (from env or auto-generated per session)
    - version (from env or git)

    Then forwards to a delegate sink.

    This solves the "Multi-env log correlation" gap:
    every log entry is tagged so you can correlate
    "error in pod-3 → Git commit abc123".
    """

    def __init__(
        self,
        delegate: Sink,
        *,
        environment: Optional[str] = None,
        trace_id: Optional[str] = None,
        version: Optional[str] = None,
        auto_detect: bool = True,
    ) -> None:
        self.delegate = delegate
        self.environment = environment
        self.trace_id = trace_id
        self.version = version

        if auto_detect:
            self.environment = self.environment or _detect_environment()
            self.trace_id = self.trace_id or _detect_trace_id() or generate_trace_id()
            self.version = self.version or _detect_version()

    def write(self, entry: LogEntry) -> None:
        if self.environment and not entry.environment:
            entry.environment = self.environment
        if self.trace_id and not entry.trace_id:
            entry.trace_id = self.trace_id
        if self.version and not entry.version:
            entry.version = self.version
        self.delegate.write(entry)

    def close(self) -> None:
        self.delegate.close()


# ---------------------------------------------------------------------------
# Dynamic sink routing
# ---------------------------------------------------------------------------

class DynamicRouter(Sink):
    """
    Routes log entries to different sinks based on rules.

    Solves the "Dynamic sink routing" gap:
    Prod → SQLite/Elasticsearch, dev → Markdown, CI → CSV.

    Rules are evaluated in order; first match wins.
    If no rule matches, entry goes to the default sink.

    Example:
        router = DynamicRouter(
            rules=[
                (lambda e: e.environment == "prod", sqlite_sink),
                (lambda e: e.environment == "ci", csv_sink),
                (lambda e: e.level == "ERROR", error_sqlite_sink),
            ],
            default=markdown_sink,
        )
    """

    def __init__(
        self,
        rules: Sequence[tuple[Callable[[LogEntry], bool], Sink]],
        default: Optional[Sink] = None,
    ) -> None:
        self.rules = list(rules)
        self.default = default

    def write(self, entry: LogEntry) -> None:
        for predicate, sink in self.rules:
            try:
                if predicate(entry):
                    sink.write(entry)
                    return
            except Exception:
                continue
        if self.default:
            self.default.write(entry)

    def close(self) -> None:
        closed = set()
        for _, sink in self.rules:
            if id(sink) not in closed:
                sink.close()
                closed.add(id(sink))
        if self.default and id(self.default) not in closed:
            self.default.close()


# ---------------------------------------------------------------------------
# Structured diff logs (version tracking)
# ---------------------------------------------------------------------------

class DiffTracker(Sink):
    """
    Tracks input/output changes between function calls across versions.

    Solves the "Structured diff logs" gap:
    logs when a function's output changes for the same input between versions.

    Example log: "v1.2.1 add(1,2) → 3 | v1.2.2 add(1,2) → 4 [DIFF DETECTED]"

    Stores a fingerprint of (function_name, args_hash) → (version, return_value).
    When the same function is called with the same args but a different version
    produces a different return value, it flags the diff.
    """

    def __init__(self, delegate: Sink) -> None:
        self.delegate = delegate
        self._history: Dict[str, tuple[str, str]] = {}  # key → (version, return_repr)
        self._lock = threading.Lock()

    @staticmethod
    def _make_key(entry: LogEntry) -> str:
        args_str = repr(entry.args) + repr(entry.kwargs)
        args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
        return f"{entry.function_name}:{args_hash}"

    def write(self, entry: LogEntry) -> None:
        version = entry.version
        if version and entry.return_value is not None:
            key = self._make_key(entry)
            current_return = repr(entry.return_value)

            with self._lock:
                prev = self._history.get(key)
                if prev is not None:
                    prev_version, prev_return = prev
                    if prev_version != version and prev_return != current_return:
                        diff_msg = (
                            f"DIFF: {entry.function_name}({repr(entry.args)}) "
                            f"v{prev_version}→{current_return!r} vs "
                            f"v{version}→{current_return!r}"
                        )
                        entry.extra["version_diff"] = diff_msg
                        entry.extra["prev_version"] = prev_version
                        entry.extra["prev_return"] = prev_return
                self._history[key] = (version, current_return)

        self.delegate.write(entry)

    def close(self) -> None:
        self.delegate.close()
