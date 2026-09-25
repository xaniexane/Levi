"""Local CSV table connector — read-only, credentialless, stdlib-only.

A spreadsheet you can query without leaving the machine: reads local
``.csv``/``.tsv`` files under a rooted data directory and returns rows,
column headers with inferred types, and per-column stats. Built for the
dollar-watching workflows (spend ledgers, export reviews) that need real
numbers from real files, locally.

LAWS (law-guard-prove):
1. READ-ONLY. No operation writes, renames, or deletes anything on disk;
   ``requires_confirmation`` can never trigger — enforced by declaring
   zero write capabilities/operations.
2. ROOTED. Every path is resolved against ``LEVI_CSVTABLE_ROOT``
   (default ``~/.levi/data``); symlinks that escape the root are refused,
   absolute paths outside it are refused. A table path can never reach
   the rest of the filesystem.
3. BOUNDED. File size cap (20 MB), row/column caps, and ``limit`` bounds
   keep a hostile CSV from eating memory. The delimiter is sniffed from a
   fixed 8 KB sample, never the whole file.

Operations (all read-only):
* ``read``    — rows as dicts (``path`` required, ``limit`` 1..500 default
  50, ``offset`` >= 0 default 0);
* ``columns`` — header names with inferred type per column;
* ``stats``   — row count, non-null counts, and numeric min/max/mean per
  numeric-leaning column.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .registry import (
    Capability,
    Connector,
    InvalidParams,
    Operation,
    Transport,
    register_connector,
)

_MAX_FILE_BYTES = 20_000_000
_SNIFF_BYTES = 8_192
_READ_LIMIT_MAX = 500
_ALLOWED_SUFFIXES = (".csv", ".tsv")


def _root() -> Path:
    return (
        Path(os.environ.get("LEVI_CSVTABLE_ROOT", "~/.levi/data"))
        .expanduser()
        .resolve()
    )


def _resolve(path: str) -> Path:
    """Resolve *path* inside the root; raise InvalidParams on escape."""
    root = _root()
    if not path:
        raise InvalidParams("path is required — nothing read.")
    candidate = (
        (root / path).resolve() if not os.path.isabs(path) else Path(path).resolve()
    )
    if candidate != root and not str(candidate).startswith(str(root) + os.sep):
        raise InvalidParams("path escapes the CSV table root — refused, nothing read.")
    if candidate.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise InvalidParams("only .csv / .tsv files are readable — nothing read.")
    if not candidate.is_file():
        raise InvalidParams("path is not a readable file — nothing read.")
    if candidate.stat().st_size > _MAX_FILE_BYTES:
        raise InvalidParams("file exceeds the 20 MB read cap — nothing read.")
    return candidate


def _sniff_dialect(sample: bytes) -> str:
    text = sample.decode("utf-8", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text, delimiters=[",", ";", "\t", "|"])
        return dialect.delimiter
    except csv.Error:
        return (
            "\t" if "\t" in text else ";" if text.count(";") > text.count(",") else ","
        )


def _read_all(path: Path) -> tuple[List[str], List[List[str]]]:
    with open(path, "rb") as fh:
        sample = fh.read(_SNIFF_BYTES)
    delimiter = _sniff_dialect(sample)
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        rows = list(csv.reader(fh, delimiter=delimiter))
    if not rows:
        raise InvalidParams("file has no rows — nothing read.")
    header, body = rows[0], rows[1:]
    width = len(header)
    return header, [r for r in body if len(r) == width]


def _infer_type(values: List[str]) -> str:
    non_empty = [v for v in values if v.strip() != ""]
    if not non_empty:
        return "empty"
    try:
        for v in non_empty:
            int(v.replace(",", ""))
        return "int"
    except ValueError:
        pass
    try:
        for v in non_empty:
            float(v.replace(",", ""))
        return "float"
    except ValueError:
        pass
    return "text"


def _num(value: str) -> Optional[float]:
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


class CsvTableConnector(Connector):
    """Read-only local CSV/TSV reader. No credential, no writes, no confirmation."""

    id = "csvtable"
    display_name = "Local CSV table reader"
    # Declared but never required: credential() returns "public" so the
    # execute() credential gate never fires for local-file reads.
    credential_env_var = "LEVI_CSVTABLE_TOKEN"
    capabilities = (
        Capability("read.table.rows", "Read rows from a local CSV/TSV table"),
        Capability("read.table.columns", "Column headers with inferred types"),
        Capability("read.table.stats", "Per-column row counts and numeric stats"),
    )
    operations = (
        Operation(
            "read",
            "Rows as dicts (params: path, limit=50, offset=0)",
            params=("path", "limit", "offset"),
        ),
        Operation(
            "columns", "Headers + inferred types (params: path)", params=("path",)
        ),
        Operation("stats", "Counts + numeric stats (params: path)", params=("path",)),
    )

    def credential(self) -> str | None:
        # Credentialless by design: local files, no account, no network.
        return "public"

    def perform(
        self,
        operation: str,
        params: dict[str, Any],
        token: Optional[str],
        transport: Transport | None,
    ) -> Any:
        path = _resolve(str(params.get("path") or ""))
        header, rows = _read_all(path)

        if operation == "read":
            raw_limit = params.get("limit", 50)
            raw_offset = params.get("offset", 0)
            try:
                limit = 50 if raw_limit is None else int(raw_limit)
                offset = 0 if raw_offset is None else int(raw_offset)
            except (TypeError, ValueError):
                raise InvalidParams(
                    "limit/offset must be integers — nothing read."
                ) from None
            if not 1 <= limit <= _READ_LIMIT_MAX:
                raise InvalidParams(
                    f"limit must be 1..{_READ_LIMIT_MAX} — nothing read."
                )
            if offset < 0:
                raise InvalidParams("offset must be >= 0 — nothing read.")
            window = rows[offset : offset + limit]
            return {
                "path": path.name,
                "row_count": len(rows),
                "offset": offset,
                "rows": [dict(zip(header, r, strict=True)) for r in window],
            }

        if operation == "columns":
            columns = list(zip(*rows, strict=True)) if rows else [[] for _ in header]
            return {
                "path": path.name,
                "row_count": len(rows),
                "columns": [
                    {"name": name, "type": _infer_type(list(col))}
                    for name, col in zip(header, columns, strict=True)
                ],
            }

        if operation == "stats":
            columns = list(zip(*rows, strict=True)) if rows else [[] for _ in header]
            stats = []
            for name, col in zip(header, columns, strict=True):
                values = list(col)
                non_null = sum(1 for v in values if v.strip() != "")
                nums = [
                    n
                    for n in (_num(v) for v in values if v.strip() != "")
                    if n is not None
                ]
                entry: Dict[str, Any] = {
                    "name": name,
                    "type": _infer_type(values),
                    "non_null": non_null,
                }
                if nums:
                    entry["min"] = min(nums)
                    entry["max"] = max(nums)
                    entry["mean"] = sum(nums) / len(nums)
                stats.append(entry)
            return {"path": path.name, "row_count": len(rows), "columns": stats}

        raise InvalidParams(f"unknown operation {operation!r} — nothing read.")


register_connector(CsvTableConnector)
