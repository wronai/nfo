"""Secret redaction for nfo log entries — prevents password/key leaks in logs."""

from __future__ import annotations

import re
from typing import Any, Dict, FrozenSet, Optional, Set, Tuple

# Key name patterns that indicate sensitive values
_SENSITIVE_PATTERNS: FrozenSet[str] = frozenset({
    "PASSWORD", "PASSWD", "PASS",
    "SECRET", "TOKEN",
    "API_KEY", "APIKEY",
    "PRIVATE_KEY", "PRIVATE",
    "ACCESS_KEY", "ACCESS_TOKEN",
    "AUTH", "AUTHORIZATION",
    "CREDENTIAL", "CREDENTIALS",
    "SESSION_ID", "SESSION",
    "COOKIE",
})

_SENSITIVE_RE = re.compile(
    r"(" + "|".join(re.escape(p) for p in sorted(_SENSITIVE_PATTERNS, key=len, reverse=True)) + r")",
    re.IGNORECASE,
)

# Default placeholder
REDACTED = "***REDACTED***"


def is_sensitive_key(key: str) -> bool:
    """Check if a key/parameter name likely holds a secret value."""
    return bool(_SENSITIVE_RE.search(key.upper()))


def redact_value(value: str, visible_chars: int = 0) -> str:
    """Replace a sensitive value with a redacted placeholder.

    Args:
        value: The secret value to redact.
        visible_chars: Number of leading characters to keep visible (0 = full redaction).
    """
    if not value:
        return REDACTED
    if visible_chars <= 0:
        return REDACTED
    if len(value) <= visible_chars:
        return REDACTED
    return value[:visible_chars] + REDACTED


def redact_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of kwargs with sensitive values redacted."""
    result = {}
    for key, value in kwargs.items():
        if is_sensitive_key(key):
            result[key] = REDACTED if not isinstance(value, str) else redact_value(value)
        else:
            result[key] = value
    return result


def redact_args(args: Tuple[Any, ...], param_names: Optional[Tuple[str, ...]] = None) -> Tuple[Any, ...]:
    """Redact positional args if their parameter names are sensitive.

    Args:
        args: Positional arguments to check.
        param_names: Corresponding parameter names (from inspect.signature).
    """
    if not param_names:
        return args
    result = list(args)
    for i, (arg, name) in enumerate(zip(args, param_names)):
        if is_sensitive_key(name) and isinstance(arg, str):
            result[i] = redact_value(arg)
    return tuple(result)


def redact_string(text: str) -> str:
    """Scan a string for common secret patterns and redact inline values.

    Catches patterns like:
      password=secret123
      "api_key": "sk-1234..."
      PASSWORD: mypass
      --token abc123
    """
    # KEY=VALUE patterns (env-style, JSON-style, YAML-style)
    def _mask_match(m: re.Match) -> str:
        prefix = m.group(1)  # key + separator
        return prefix + REDACTED

    # Match: KEY_PATTERN followed by =, :, or " then value
    text = re.sub(
        r'((?:password|passwd|pass|secret|token|api_key|apikey|private_key|access_key|'
        r'access_token|auth|authorization|credential|session_id|cookie)'
        r'\s*[:=]\s*)["\']?([^"\'\s,}\]]+)',
        _mask_match,
        text,
        flags=re.IGNORECASE,
    )
    return text
