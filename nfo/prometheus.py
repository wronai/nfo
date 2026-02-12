"""
Prometheus metrics sink for nfo.

Exports function call metrics (duration, error rate, call count) as
Prometheus metrics. Optionally starts an HTTP server on a configurable port
so Prometheus can scrape ``/metrics``.

Requires: ``pip install nfo[prometheus]``  (prometheus_client)
"""

from __future__ import annotations

import threading
from typing import Optional

from nfo.models import LogEntry
from nfo.sinks import Sink

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Histogram,
        Gauge,
        start_http_server,
        generate_latest,
    )

    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False


class PrometheusSink(Sink):
    """
    Sink that exports nfo log entries as Prometheus metrics.

    Metrics exposed:
    - ``nfo_calls_total`` — counter of function calls (labels: function, module, level)
    - ``nfo_errors_total`` — counter of ERROR-level calls (labels: function, module)
    - ``nfo_duration_seconds`` — histogram of call durations (labels: function, module)
    - ``nfo_last_call_timestamp`` — gauge of last call unix timestamp (labels: function)

    Args:
        delegate: Optional downstream sink to forward entries to.
        port: If set, starts an HTTP server on this port exposing ``/metrics``.
        registry: Custom Prometheus CollectorRegistry (default: new registry).
        prefix: Metric name prefix (default: ``nfo``).
    """

    def __init__(
        self,
        delegate: Optional[Sink] = None,
        *,
        port: Optional[int] = None,
        registry: Optional["CollectorRegistry"] = None,
        prefix: str = "nfo",
    ) -> None:
        if not _HAS_PROMETHEUS:
            raise ImportError(
                "prometheus_client is required for PrometheusSink. "
                "Install with: pip install nfo[prometheus]"
            )

        self.delegate = delegate
        self._port = port
        self._prefix = prefix
        self._registry = registry or CollectorRegistry()
        self._server_started = False
        self._lock = threading.Lock()

        # -- metrics ---------------------------------------------------------
        self._calls_total = Counter(
            f"{prefix}_calls_total",
            "Total number of function calls logged by nfo",
            ["function", "module", "level"],
            registry=self._registry,
        )
        self._errors_total = Counter(
            f"{prefix}_errors_total",
            "Total number of ERROR-level function calls",
            ["function", "module"],
            registry=self._registry,
        )
        self._duration_seconds = Histogram(
            f"{prefix}_duration_seconds",
            "Function call duration in seconds",
            ["function", "module"],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self._registry,
        )
        self._last_call_ts = Gauge(
            f"{prefix}_last_call_timestamp",
            "Unix timestamp of the last call to this function",
            ["function"],
            registry=self._registry,
        )

        # Auto-start /metrics server if port specified
        if port is not None:
            self._start_server(port)

    def _start_server(self, port: int) -> None:
        with self._lock:
            if not self._server_started:
                start_http_server(port, registry=self._registry)
                self._server_started = True

    def write(self, entry: LogEntry) -> None:
        func = entry.function_name or "unknown"
        module = entry.module or "unknown"
        level = entry.level or "DEBUG"

        self._calls_total.labels(function=func, module=module, level=level).inc()

        if level == "ERROR":
            self._errors_total.labels(function=func, module=module).inc()

        if entry.duration_ms is not None:
            self._duration_seconds.labels(
                function=func, module=module
            ).observe(entry.duration_ms / 1000.0)

        self._last_call_ts.labels(function=func).set_to_current_time()

        if self.delegate:
            self.delegate.write(entry)

    def close(self) -> None:
        if self.delegate:
            self.delegate.close()

    def get_metrics(self) -> bytes:
        """Return current metrics in Prometheus text format."""
        return generate_latest(self._registry)
