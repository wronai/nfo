"""
Class-level decorator for automatic method logging.

Follows SOLID principles:
- Single Responsibility: each method's logging is isolated
- Open/Closed: extend via custom sinks, not code changes
- Liskov Substitution: decorated class behaves identically
- Interface Segregation: only public methods are logged
- Dependency Inversion: depends on Sink abstraction, not concrete sinks

Usage:
    from nfo import logged

    @logged
    class UserService:
        def create(self, name: str) -> dict:
            return {"name": name}

        def _internal(self):
            pass  # not logged (private)
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Optional, TypeVar, overload

from nfo.decorators import log_call

C = TypeVar("C", bound=type)


def _should_wrap(name: str, attr: Any) -> bool:
    """Determine if a class attribute should be auto-logged."""
    if name.startswith("_"):
        return False
    if not callable(attr):
        return False
    if isinstance(attr, (staticmethod, classmethod)):
        return False
    if getattr(attr, "_nfo_skip", False):
        return False
    return True


def skip(func: Callable) -> Callable:
    """Mark a public method to be excluded from @logged auto-wrapping."""
    func._nfo_skip = True  # type: ignore[attr-defined]
    return func


@overload
def logged(cls: C) -> C: ...

@overload
def logged(*, level: str = "DEBUG", logger: Any = None) -> Callable[[C], C]: ...

def logged(cls: Optional[C] = None, *, level: str = "DEBUG", logger: Any = None) -> Any:
    """
    Class decorator that auto-wraps all public methods with @log_call.

    Can be used bare (``@logged``) or with parameters
    (``@logged(level="INFO")``).

    Private methods (starting with ``_``) and methods marked with
    ``@nfo.skip`` are excluded.
    """

    def decorator(klass: C) -> C:
        for name in list(vars(klass)):
            attr = getattr(klass, name, None)
            if _should_wrap(name, attr):
                wrapped = log_call(attr, level=level, logger=logger)
                setattr(klass, name, wrapped)
        return klass

    if cls is not None:
        return decorator(cls)
    return decorator
