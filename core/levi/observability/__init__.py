"""LEVI observability — the decision-trace corpus.

Every bloodstream turn round-trips into an append-only JSONL corpus at
``~/.levi/observability/traces-YYYY-MM-DD.jsonl`` (owner-only). The
corpus is queryable via :class:`TraceStore` and the
``python -m levi.observability`` entrypoint.

Secret safety is structural: tool-call params are stored redacted with a
SHA-256 over the redacted form — raw secret values never reach the
corpus. See ``docs/OBSERVABILITY.md``.
"""

from levi.observability.hook import emit_turn_trace
from levi.observability.redact import REDACTED, canonical, params_hash, redact
from levi.observability.schema import (
    AWAITING_PERMISSION,
    DENIED,
    FAILED,
    OUTCOME_MAP,
    SCHEMA_VERSION,
    SUCCESS,
    StageTiming,
    ToolCallRecord,
    TurnTrace,
    from_bloodstream,
)
from levi.observability.store import TraceStore, default_store_dir

__all__ = [
    "AWAITING_PERMISSION",
    "DENIED",
    "FAILED",
    "OUTCOME_MAP",
    "REDACTED",
    "SCHEMA_VERSION",
    "SUCCESS",
    "StageTiming",
    "ToolCallRecord",
    "TraceStore",
    "TurnTrace",
    "canonical",
    "default_store_dir",
    "emit_turn_trace",
    "from_bloodstream",
    "params_hash",
    "redact",
]
