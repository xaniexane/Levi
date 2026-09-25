"""Span model: real trace/span ids, attributes, events, LLM token/cost spans.

Every public entry point is total (cannot raise into the caller): if span
construction itself fails, a no-op span is returned instead.
"""

from __future__ import annotations

import secrets
import time
from contextlib import contextmanager
from typing import Any

from . import emitter


def new_trace_id() -> str:
    """128-bit trace id as 32 lowercase hex chars (W3C/OTLP format)."""
    return secrets.token_hex(16)


def new_span_id() -> str:
    """64-bit span id as 16 lowercase hex chars (W3C/OTLP format)."""
    return secrets.token_hex(8)


def _now_ns() -> int:
    return time.time_ns()


class Span:
    """One unit of timed work. Use as a context manager or call finish()."""

    __slots__ = (
        "name",
        "trace_id",
        "span_id",
        "parent_span_id",
        "attributes",
        "events",
        "start_ns",
        "end_ns",
        "error",
        "_finished",
    )

    def __init__(
        self,
        name: str,
        attributes: dict | None = None,
        parent: "Span | None" = None,
        trace_id: str | None = None,
    ) -> None:
        self.name = str(name)
        self.trace_id = (
            trace_id or (parent.trace_id if parent else None) or new_trace_id()
        )
        self.span_id = new_span_id()
        self.parent_span_id = parent.span_id if parent else None
        self.attributes: dict[str, Any] = dict(attributes or {})
        self.events: list[dict] = []
        self.start_ns = _now_ns()
        self.end_ns: int | None = None
        self.error = False
        self._finished = False

    # -- mutation (all total) -------------------------------------------
    def set_attribute(self, key: str, value: Any) -> "Span":
        try:
            self.attributes[str(key)] = value
        except Exception:
            pass
        return self

    def add_event(self, name: str, attributes: dict | None = None) -> "Span":
        try:
            self.events.append(
                {
                    "name": str(name),
                    "time_ns": _now_ns(),
                    "attributes": dict(attributes or {}),
                }
            )
        except Exception:
            pass
        return self

    def record_error(self) -> "Span":
        try:
            self.error = True
        except Exception:
            pass
        return self

    # -- lifecycle --------------------------------------------------------
    def finish(self) -> None:
        """Enqueue for background delivery. Never raises, never blocks."""
        try:
            if self._finished:
                return
            self._finished = True
            if self.end_ns is None:
                self.end_ns = _now_ns()
            emitter.enqueue(self)
        except Exception:
            pass

    def __enter__(self) -> "Span":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if exc_type is not None:
                self.record_error()
        except Exception:
            pass
        self.finish()
        return False  # never swallow the caller's exception


class _NoOpSpan:
    """Fallback when span construction fails: accepts every call, does nothing."""

    def __init__(self) -> None:
        self.name = "noop"
        self.trace_id = "0" * 32
        self.span_id = "0" * 16
        self.parent_span_id = None
        self.attributes: dict = {}
        self.events: list = []
        self.start_ns = 0
        self.end_ns = 0
        self.error = False

    def set_attribute(self, key, value):
        return self

    def add_event(self, name, attributes=None):
        return self

    def record_error(self):
        return self

    def finish(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def start_span(
    name: str, attributes: dict | None = None, parent: Span | None = None
) -> Span:
    """Create and start a span. Total: never raises; returns a no-op span
    on internal failure."""
    try:
        return Span(name, attributes=attributes, parent=parent)
    except Exception:
        return _NoOpSpan()  # type: ignore[return-value]


@contextmanager
def span(name: str, attributes: dict | None = None, parent: Span | None = None):
    """Context-manager form: ``with telemetry.span("growth.harvest"): ...``."""
    sp = start_span(name, attributes=attributes, parent=parent)
    try:
        yield sp
    except Exception:
        try:
            sp.record_error()
        except Exception:
            pass
        raise
    finally:
        try:
            sp.finish()
        except Exception:
            pass


@contextmanager
def llm_span(
    model: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
    input_cost_per_1k: float | None = None,
    output_cost_per_1k: float | None = None,
    **attributes: Any,
):
    """Span for one LLM call with token/cost attributes, so OpenObserve's
    token-cost tracking has real data to work with.

    Pass cost_usd directly, or pass per-1k rates and it is computed from
    the token counts. The cost attributes follow the OpenTelemetry
    semantic-convention style names (gen_ai.*) plus a plain
    ``llm.cost_usd`` for easy SQL.
    """
    attrs: dict[str, Any] = {"gen_ai.request.model": str(model)}
    if input_tokens is not None:
        attrs["gen_ai.usage.input_tokens"] = int(input_tokens)
    if output_tokens is not None:
        attrs["gen_ai.usage.output_tokens"] = int(output_tokens)
    computed = cost_usd
    if computed is None and (input_tokens or output_tokens):
        total = 0.0
        if input_cost_per_1k is not None and input_tokens:
            total += (input_tokens / 1000.0) * input_cost_per_1k
        if output_cost_per_1k is not None and output_tokens:
            total += (output_tokens / 1000.0) * output_cost_per_1k
        computed = total if total else None
    if computed is not None:
        attrs["llm.cost_usd"] = float(computed)
    attrs.update(attributes)
    with span("llm.call", attrs) as sp:
        yield sp
