"""Thin, non-invasive hook points: a decorator that wraps loop functions in
spans without touching their bodies.

Usage (one line + import at the call site)::

    from levi.telemetry import traced as _traced

    @_traced("growth.cycle")
    def run_cycle(...):
        ...

The decorator is total: if telemetry itself fails, the wrapped function
still runs exactly as before.
"""

from __future__ import annotations

import functools
from typing import Any, Callable

from .span import span as _span


def traced(name: str, attributes: dict | None = None) -> Callable:
    """Decorator: run the function inside a telemetry span named ``name``.

    The span records ``ok``/``error`` and finishes on every exit path,
    including exceptions (which still propagate to the caller).
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                with _span(name, attributes) as sp:
                    try:
                        result = fn(*args, **kwargs)
                    except Exception:
                        try:
                            sp.set_attribute("ok", False)
                        except Exception:
                            pass
                        raise
                    try:
                        sp.set_attribute("ok", True)
                    except Exception:
                        pass
                    return result
            except Exception:
                # If even the span machinery failed, run the function raw —
                # telemetry must never change loop behavior.
                return fn(*args, **kwargs)

        return wrapper

    return decorator
