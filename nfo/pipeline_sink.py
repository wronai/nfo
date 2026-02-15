"""PipelineSink — groups LogEntry objects by pipeline_run_id and renders them as blocks.

Entries with ``extra["pipeline_run_id"]`` are buffered until a completion
marker (``extra["pipeline_complete"] == True``) arrives or a timeout expires.
Non-pipeline entries pass through to the delegate immediately.

The rendered output uses box-drawing characters for a compact, readable
terminal display of an entire pipeline tick.

Example output::

    ╔═══════════════════════════════════════════════════════════╗
    ║ TICK #42 │ a1b2c3 │ 14:23:01                             ║
    ╠═══════════════════════════════════════════════════════════╣
    ║ ✓ ScanWindows        12ms │ 8 win, active: VSCode        ║
    ║ ✓ CaptureScreen      45ms │ 64KB JPEG ██ CHANGE          ║
    ║ ✗ Analyze          3200ms │ ERROR: RateLimitError         ║
    ╠═══════════════════════════════════════════════════════════╣
    ║ 998ms │ $0.0023 │ next: ~1.0s                             ║
    ╚═══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import io
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, TextIO

from nfo.models import LogEntry
from nfo.sinks import Sink


# ANSI color codes
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_RESET = "\033[0m"

# Status symbols
_OK = f"{_GREEN}✓{_RESET}"
_FAIL = f"{_RED}✗{_RESET}"
_SKIP = f"{_DIM}⊘{_RESET}"
_DECISION = f"{_YELLOW}►{_RESET}"


class PipelineSink(Sink):
    """Sink that groups log entries by ``pipeline_run_id`` and renders pipeline ticks.

    Parameters:
        delegate: Optional downstream sink for non-pipeline entries.
        stream: Output stream for rendered blocks (default: ``sys.stderr``).
        width: Box width in characters.
        buffer_timeout: Seconds before an incomplete run is flushed.
        color: Enable ANSI colors (default: ``True``).
        tick_counter: Starting tick number.
    """

    def __init__(
        self,
        delegate: Optional[Sink] = None,
        stream: Optional[TextIO] = None,
        width: int = 72,
        buffer_timeout: float = 10.0,
        color: bool = True,
        tick_counter: int = 0,
    ):
        self._delegate = delegate
        self._stream = stream or sys.stderr
        self._width = max(40, width)
        self._timeout = buffer_timeout
        self._color = color
        self._tick = tick_counter
        self._lock = threading.Lock()
        # run_id -> (entries, first_seen_time)
        self._buffers: Dict[str, tuple] = {}
        # Session-level cost tracking
        self._session_cost: float = 0.0
        self._recent_costs: List[float] = []  # last N tick costs
        self._max_recent: int = 10

    # -- public properties ---------------------------------------------------

    @property
    def tick_count(self) -> int:
        """Number of completed ticks rendered so far."""
        return self._tick

    @property
    def pending_runs(self) -> int:
        """Number of pipeline runs currently buffered."""
        return len(self._buffers)

    @property
    def session_cost(self) -> float:
        """Total cost across all rendered ticks."""
        return self._session_cost

    # -- Sink interface ------------------------------------------------------

    def write(self, entry: LogEntry) -> None:
        run_id = entry.extra.get("pipeline_run_id")
        if not run_id:
            # Non-pipeline entry — pass through
            if self._delegate:
                self._delegate.write(entry)
            return

        with self._lock:
            if run_id not in self._buffers:
                self._buffers[run_id] = ([], time.monotonic())
            self._buffers[run_id][0].append(entry)

            if entry.extra.get("pipeline_complete"):
                self._flush_run(run_id)
            else:
                self._flush_stale()

    def close(self) -> None:
        with self._lock:
            # Flush all remaining buffers
            for run_id in list(self._buffers):
                self._flush_run(run_id)
        if self._delegate:
            self._delegate.close()

    # -- flushing ------------------------------------------------------------

    def _flush_stale(self) -> None:
        """Flush runs older than buffer_timeout (called under lock)."""
        now = time.monotonic()
        stale = [
            rid for rid, (_, t0) in self._buffers.items()
            if now - t0 > self._timeout
        ]
        for rid in stale:
            self._flush_run(rid)

    def _flush_run(self, run_id: str) -> None:
        """Render and output a completed pipeline run (called under lock)."""
        buf = self._buffers.pop(run_id, None)
        if not buf:
            return
        entries, _ = buf
        self._tick += 1

        # Track cost
        tick_cost = 0.0
        for e in entries:
            if e.extra.get("pipeline_complete"):
                tick_cost = e.extra.get("total_cost", 0)
                break
        if tick_cost == 0:
            tick_cost = sum(e.extra.get("cost_usd", 0) for e in entries)
        self._session_cost += tick_cost
        self._recent_costs.append(tick_cost)
        if len(self._recent_costs) > self._max_recent:
            self._recent_costs = self._recent_costs[-self._max_recent:]

        block = self._render_block(run_id, entries)
        self._stream.write(block)
        self._stream.flush()

    # -- rendering -----------------------------------------------------------

    def _c(self, code: str, text: str) -> str:
        """Apply ANSI color if enabled."""
        if not self._color:
            return text
        return f"{code}{text}{_RESET}"

    def _render_block(self, run_id: str, entries: List[LogEntry]) -> str:
        """Render a full pipeline tick block."""
        W = self._width
        inner = W - 4  # content width inside box (║ + space + content + space + ║)

        out = io.StringIO()

        # Separate step entries from completion entry
        steps: List[LogEntry] = []
        completion: Optional[LogEntry] = None
        for e in entries:
            if e.extra.get("pipeline_complete"):
                completion = e
            else:
                steps.append(e)

        # Header
        ts = ""
        if entries:
            ts = entries[0].timestamp.strftime("%H:%M:%S")
        header = f" TICK #{self._tick} │ {run_id} │ {ts} "
        out.write(f"╔{'═' * (W - 2)}╗\n")
        out.write(f"║{self._c(_BOLD, header):<{inner + self._ansi_pad(self._c(_BOLD, header))}}║\n")
        out.write(f"╠{'═' * (W - 2)}╣\n")

        # Step rows
        for entry in steps:
            line = self._render_step(entry, inner)
            out.write(f"║ {line} ║\n")

            # Sub-decisions / annotations
            for sub in self._render_sub_lines(entry, inner - 2):
                out.write(f"║   {sub} ║\n")

        # Data flow section (if any step has data_size_kb)
        flow_line = self._render_data_flow(steps, inner)
        if flow_line:
            out.write(f"║ {flow_line} ║\n")

        # Footer
        out.write(f"╠{'═' * (W - 2)}╣\n")
        footer = self._render_footer(completion, steps, inner)
        out.write(f"║ {footer} ║\n")

        # Rolling cost line (if any cost accumulated)
        cost_line = self._render_cost_line(inner)
        if cost_line:
            out.write(f"║ {cost_line} ║\n")

        out.write(f"╚{'═' * (W - 2)}╝\n")

        return out.getvalue()

    def _render_step(self, entry: LogEntry, width: int) -> str:
        """Render a single step line."""
        extra = entry.extra
        step_name = extra.get("step_name", entry.function_name or "?")
        decision = extra.get("decision", "")
        duration = entry.duration_ms

        # Status icon
        if entry.exception:
            icon = _FAIL if self._color else "✗"
        elif decision == "skipped":
            icon = _SKIP if self._color else "⊘"
        else:
            icon = _OK if self._color else "✓"

        # Duration string
        dur_str = ""
        if duration is not None:
            dur_str = f"{duration:>6.0f}ms"
        else:
            dur_str = "       "

        # Summary from extra fields
        summary = self._step_summary(entry)

        # Format: icon name duration │ summary
        name_part = f"{step_name:<20s}"
        if entry.exception:
            name_part = self._c(_RED, name_part) if self._color else name_part
        elif decision == "skipped":
            name_part = self._c(_DIM, name_part) if self._color else name_part

        left = f"{icon} {name_part} {dur_str}"
        if summary:
            left = f"{left} │ {summary}"

        # Pad to width
        visible_len = self._visible_len(left)
        pad = max(0, width - visible_len)
        return left + " " * pad

    def _step_summary(self, entry: LogEntry) -> str:
        """Extract a short summary string from entry extra fields."""
        extra = entry.extra
        parts = []

        if entry.exception:
            exc_type = entry.exception_type or "Error"
            parts.append(f"{exc_type}: {entry.exception[:40]}")
            return " ".join(parts)

        decision = extra.get("decision", "")
        if decision == "skipped":
            reason = extra.get("decision_reason", "")
            return f"skipped ({reason})" if reason else "skipped"

        # Generic metrics from extra
        for key in ("windows_total", "active_window", "data_size_kb",
                     "has_change", "context_length", "cost_usd",
                     "tokens_in", "tokens_out", "provider", "mode",
                     "actions_count", "events_count", "crops_total",
                     "ocr_chars", "memories_recalled"):
            val = extra.get(key)
            if val is not None:
                parts.append(self._format_metric(key, val))

        return ", ".join(parts[:4])  # limit to 4 metrics

    def _format_metric(self, key: str, val: Any) -> str:
        """Format a single metric for display."""
        labels = {
            "windows_total": lambda v: f"{v} win",
            "active_window": lambda v: str(v)[:25],
            "data_size_kb": lambda v: f"{v:.0f}KB",
            "has_change": lambda v: "CHANGE" if v else "no change",
            "context_length": lambda v: f"{v}ch ctx",
            "cost_usd": lambda v: f"${v:.4f}",
            "tokens_in": lambda v: f"{v}→",
            "tokens_out": lambda v: f"→{v}tok",
            "provider": lambda v: str(v),
            "mode": lambda v: str(v),
            "actions_count": lambda v: f"{v} actions",
            "events_count": lambda v: f"{v} events",
            "crops_total": lambda v: f"{v} crops",
            "ocr_chars": lambda v: f"{v}ch OCR",
            "memories_recalled": lambda v: f"{v} memories",
        }
        fmt = labels.get(key)
        if fmt:
            return fmt(val)
        return f"{key}={val}"

    def _render_sub_lines(self, entry: LogEntry, width: int) -> List[str]:
        """Render sub-lines for decisions and annotations."""
        lines = []
        extra = entry.extra

        # Decision annotation
        decision = extra.get("decision", "")
        reason = extra.get("decision_reason", "")
        if decision and decision not in ("executed", "skipped") and reason:
            icon = _DECISION if self._color else "►"
            text = f"{icon} DECISION: {decision} — {reason}"
            visible = self._visible_len(text)
            lines.append(text + " " * max(0, width - visible))

        # Cost detail
        cost = extra.get("cost_usd", 0)
        tokens_in = extra.get("tokens_in")
        tokens_out = extra.get("tokens_out")
        model = extra.get("model", "")
        if tokens_in and tokens_out:
            detail = f"  └─ {model} {tokens_in}→{tokens_out}tok"
            if cost:
                detail += f" ${cost:.4f}"
            visible = self._visible_len(detail)
            lines.append(detail + " " * max(0, width - visible))

        # OCR detail
        ocr_engine = extra.get("ocr_engine", "")
        ocr_ms = extra.get("ocr_ms")
        ocr_chars = extra.get("ocr_chars")
        if ocr_engine and ocr_ms is not None:
            detail = f"  └─ OCR: {ocr_engine} {ocr_ms:.0f}ms"
            if ocr_chars:
                detail += f", {ocr_chars}ch"
            visible = self._visible_len(detail)
            lines.append(detail + " " * max(0, width - visible))

        return lines

    def _render_footer(self, completion: Optional[LogEntry],
                       steps: List[LogEntry], width: int) -> str:
        """Render the summary footer line."""
        total_ms = 0.0
        total_cost = 0.0
        error_count = 0

        if completion:
            total_ms = completion.extra.get("total_ms", 0)
            total_cost = completion.extra.get("total_cost", 0)
            error_count = len([s for s in steps if s.exception])
        else:
            for s in steps:
                if s.duration_ms:
                    total_ms += s.duration_ms
                total_cost += s.extra.get("cost_usd", 0)
                if s.exception:
                    error_count += 1

        parts = [f"{total_ms:.0f}ms"]
        if total_cost > 0:
            parts.append(f"${total_cost:.4f}")
        if error_count:
            parts.append(self._c(_RED, f"{error_count} errors") if self._color else f"{error_count} errors")

        steps_total = len(steps)
        skipped = sum(1 for s in steps if s.extra.get("decision") == "skipped")
        executed = steps_total - skipped - error_count
        parts.append(f"{executed}/{steps_total} steps")

        footer = " │ ".join(parts)
        visible = self._visible_len(footer)
        pad = max(0, width - visible)
        return footer + " " * pad

    # -- ANSI helpers --------------------------------------------------------

    def _render_data_flow(self, steps: List[LogEntry], width: int) -> str:
        """Render a data flow summary showing sizes at key steps."""
        parts = []
        for e in steps:
            ex = e.extra
            name = ex.get("step_name", "")
            size_kb = ex.get("data_size_kb")
            if size_kb and size_kb > 0:
                parts.append(f"{name}:{size_kb:.0f}KB")
            ctx_len = ex.get("context_length")
            if ctx_len and ctx_len > 0:
                parts.append(f"ctx:{ctx_len}ch")
            tokens_in = ex.get("tokens_in")
            tokens_out = ex.get("tokens_out")
            if tokens_in and tokens_out:
                parts.append(f"llm:{tokens_in}→{tokens_out}tok")
        if not parts:
            return ""
        label = self._c(_DIM, "DATA") if self._color else "DATA"
        text = f"{label} {' → '.join(parts)}"
        visible = self._visible_len(text)
        return text + " " * max(0, width - visible)

    def _render_cost_line(self, width: int) -> str:
        """Render rolling cost summary if any cost was tracked."""
        if self._session_cost <= 0:
            return ""
        parts = [f"Session: ${self._session_cost:.4f}"]
        if self._recent_costs:
            avg = sum(self._recent_costs) / len(self._recent_costs)
            parts.append(f"avg/tick: ${avg:.4f}")
        label = self._c(_DIM, "COST") if self._color else "COST"
        text = f"{label} {' │ '.join(parts)}"
        visible = self._visible_len(text)
        return text + " " * max(0, width - visible)

    @staticmethod
    def _visible_len(text: str) -> int:
        """Length of text excluding ANSI escape sequences."""
        import re
        return len(re.sub(r'\033\[[0-9;]*m', '', text))

    def _ansi_pad(self, text: str) -> int:
        """Extra characters added by ANSI codes (for padding calculations)."""
        return len(text) - self._visible_len(text)
