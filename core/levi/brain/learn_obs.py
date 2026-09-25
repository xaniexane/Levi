"""Learning-loop observation reader — the CONSUMER side of the observation store.

The writer lives in ``levi.brain.runtime`` (the torch-free model runner):
every run through the runner appends one JSONL record with schema
``levi-observation/1`` to ``~/.levi/model-observations.jsonl`` (owner-only,
local only, never networked). This module reads that log defensively for
the learning loop:

- missing store -> clean empty result (the writer may not have landed yet;
  a scheduled loop must never crash on that),
- corrupt lines (not JSON, wrong schema version, missing required fields)
  are SKIPPED and counted honestly,
- unknown/extra fields are tolerated and ignored.

The schema contract is duplicated here on purpose: the schema version IS
the decoupling mechanism between the writer (runtime worker's file) and
this consumer. If the writer ever bumps the schema, this reader keeps
accepting v1 and reports the version skew in the skipped count.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

OBS_SCHEMA = "levi-observation/1"
"""Observation record schema version this reader accepts."""

# Required fields per the v1 writer contract (see runtime._OBS_REQUIRED).
_OBS_REQUIRED = (
    "schema",
    "ts",
    "model_id",
    "arch",
    "prompt_sha256",
    "sampling",
    "timing",
    "receipt",
)


def observations_file() -> Path:
    """Path of the local observation log.

    Tests (and hermetic environments) point elsewhere with the
    ``LEVI_OBSERVATIONS_FILE`` environment variable — the same override
    the writer honors.
    """
    override = os.environ.get("LEVI_OBSERVATIONS_FILE")
    if override:
        return Path(override)
    return Path.home() / ".levi" / "model-observations.jsonl"


def _valid_record(rec: Any) -> bool:
    if not isinstance(rec, dict):
        return False
    if rec.get("schema") != OBS_SCHEMA:
        return False
    return all(key in rec for key in _OBS_REQUIRED)


def read_observations(
    path: Optional[Path] = None,
    *,
    model_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Read the observation log defensively.

    Returns ``{"records": [...], "skipped": N, "path": str}``. A missing
    file yields zero records and zero skipped — never an exception. One
    bad line never poisons the whole log.
    """
    store = Path(path) if path is not None else observations_file()
    records: List[Dict[str, Any]] = []
    skipped = 0
    if store.is_file():
        try:
            fh = store.open("r", encoding="utf-8")
        except OSError:
            return {"records": records, "skipped": skipped, "path": str(store)}
        with fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    skipped += 1
                    continue
                if not _valid_record(rec):
                    skipped += 1
                    continue
                if model_id is not None and rec.get("model_id") != model_id:
                    continue
                records.append(rec)
    if limit is not None:
        records = records[-max(0, int(limit)) :]
    return {"records": records, "skipped": skipped, "path": str(store)}


def extract_text(rec: Dict[str, Any]) -> str:
    """Distillation text for one observation: prompt + model output.

    The v1 writer stores ``prompt`` (plaintext, possibly truncated and
    flagged) and ``output`` (the sampled continuation / actions /
    decisions). Missing pieces degrade gracefully to whatever is present;
    a record with neither yields an empty string (and scores zero
    downstream).
    """
    parts: List[str] = []
    prompt = rec.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        parts.append(prompt.strip())
    output = rec.get("output")
    if isinstance(output, str) and output.strip():
        parts.append(output.strip())
    else:
        # Future writers may record structured actions/decisions instead
        # of flat text; accept those too, deterministically ordered.
        for key in ("actions", "decisions"):
            val = rec.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val.strip())
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and item.strip():
                        parts.append(item.strip())
                    elif isinstance(item, dict):
                        blob = json.dumps(item, sort_keys=True, ensure_ascii=False)
                        if blob.strip():
                            parts.append(blob)
    return "\n".join(parts)
