"""Data models for log entries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_MAX_REPR_LENGTH = 2048


def _truncate_text(text: str, max_length: Optional[int]) -> str:
    """Truncate text representation to a bounded length (if configured)."""
    if max_length is None or max_length <= 0:
        return text
    if len(text) <= max_length:
        return text
    omitted = len(text) - max_length
    return f"{text[:max_length]}... [truncated {omitted} chars]"


def safe_repr(value: Any, max_length: Optional[int] = DEFAULT_MAX_REPR_LENGTH) -> str:
    """Best-effort repr with defensive truncation."""
    try:
        rendered = repr(value)
    except Exception as exc:  # pragma: no cover - very rare edge-case
        rendered = f"<repr failed: {type(exc).__name__}: {exc}>"
    return _truncate_text(rendered, max_length)


@dataclass
class LogEntry:
    """A single log entry produced by a decorated function call."""

    timestamp: datetime
    level: str
    function_name: str
    module: str
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]
    arg_types: List[str]
    kwarg_types: Dict[str, str]
    return_value: Any = None
    return_type: Optional[str] = None
    exception: Optional[str] = None
    exception_type: Optional[str] = None
    traceback: Optional[str] = None
    duration_ms: Optional[float] = None
    environment: Optional[str] = None
    trace_id: Optional[str] = None
    version: Optional[str] = None
    llm_analysis: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    max_repr_length: Optional[int] = DEFAULT_MAX_REPR_LENGTH

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

    def args_repr(self) -> str:
        return safe_repr(self.args, self.max_repr_length)

    def kwargs_repr(self) -> str:
        return safe_repr(self.kwargs, self.max_repr_length)

    def return_value_repr(self) -> str:
        return safe_repr(self.return_value, self.max_repr_length)

    def as_dict(self) -> Dict[str, Any]:
        """Convert to a flat dictionary suitable for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "function_name": self.function_name,
            "module": self.module,
            "args": self.args_repr(),
            "kwargs": self.kwargs_repr(),
            "arg_types": ", ".join(self.arg_types),
            "kwarg_types": safe_repr(self.kwarg_types, self.max_repr_length),
            "return_value": self.return_value_repr(),
            "return_type": self.return_type or "",
            "exception": self.exception or "",
            "exception_type": self.exception_type or "",
            "traceback": self.traceback or "",
            "duration_ms": self.duration_ms,
            "environment": self.environment or "",
            "trace_id": self.trace_id or "",
            "version": self.version or "",
            "llm_analysis": self.llm_analysis or "",
        }

    def as_compact(self) -> Dict[str, Any]:
        """Convert to a minimal dictionary optimised for LLM token budgets.

        Omits empty/None fields and uses short keys to reduce token count
        by ~40-60% compared to :meth:`as_dict`.
        """
        d: Dict[str, Any] = {
            "fn": self.function_name,
            "lvl": self.level,
        }
        if self.module:
            d["mod"] = self.module
        if self.args:
            d["a"] = self.args_repr()
        if self.kwargs:
            d["kw"] = self.kwargs_repr()
        if self.return_value is not None:
            d["ret"] = self.return_value_repr()
        if self.return_type:
            d["rt"] = self.return_type
        if self.exception:
            d["err"] = self.exception
            if self.exception_type:
                d["et"] = self.exception_type
        if self.duration_ms is not None:
            d["ms"] = round(self.duration_ms, 2)
        if self.environment:
            d["env"] = self.environment
        if self.trace_id:
            d["tid"] = self.trace_id
        return d
