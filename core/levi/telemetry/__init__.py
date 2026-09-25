"""LEVI telemetry: stdlib-only OTLP/HTTP span emission to self-hosted OpenObserve.

Provisional module name. This is the missing telemetry piece for the growth
loop's harvest/reflect stages: agent and daemon loops emit OpenTelemetry
spans, a self-hosted OpenObserve ingests them, and its MCP server can then
query that telemetry in natural language.

LAWS (invariants — declared up front, enforced by the guard tests):
  L1. Telemetry NEVER breaks the loop. Every public entry point is
      total: it cannot raise into the caller. When OpenObserve is down,
      spans degrade silently to drop-with-counter.
  L2. Spans are valid OTLP/HTTP JSON: resourceSpans/scopeSpans envelope,
      32-hex trace ids, 16-hex span ids, int64 nanosecond timestamps
      encoded as strings per the OTLP JSON mapping.
  L3. Zero third-party dependencies. The kernel stays stdlib-only:
      urllib + json + threading + queue + secrets + time + os.
  L4. The OpenObserve binary is used UNMODIFIED and self-hosted
      (AGPL-3.0: unmodified binary, no source distribution, no
      obligations triggered). The binary and its data dir live OUTSIDE
      the repo at ``~/workspace/services/openobserve/`` — never committed.

Public API:
  start_span(name, attributes=None) -> Span
  span(name, attributes=None)       -> context manager
  llm_span(model, ...)              -> context manager with token/cost attrs
  traced(name)                      -> decorator for thin loop hooks
  flush(timeout=5.0)                -> best-effort synchronous flush
  stats()                           -> {"emitted","dropped","failed"}
  reset()                           -> test seam: clear queue + counters
  configure(...)                    -> override endpoint/auth/service name
"""

from __future__ import annotations

from .emitter import configure, flush, reset, stats
from .hooks import traced
from .span import Span, llm_span, new_span_id, new_trace_id, span, start_span

__all__ = [
    "Span",
    "configure",
    "flush",
    "llm_span",
    "new_span_id",
    "new_trace_id",
    "reset",
    "span",
    "start_span",
    "stats",
    "traced",
]
