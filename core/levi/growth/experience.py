"""Experience harvesting for LEVI's growth loop.

An *experience* is one unit of "something happened that Levi could learn
from": a user message, one of Levi's own turns, a session summary, or an
automation run record. Harvesting is read-only — it never modifies the
sources it reads.

Sources (all local-first):
  * agent chat sessions  — ``~/.levi/agent/sessions/*.jsonl``
  * daemon automations   — ``~/.levi/automations/automations.json``

A watermark per source (``~/.levi/growth/state.json``) keeps cycles
idempotent: re-running a cycle never re-harvests the same records.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass
class Experience:
    """One learnable unit of past activity."""

    id: str
    kind: str          # "user-said" | "levi-did" | "distilled" | "automation" | "note"
    source: str        # session name / automation id / "note"
    ts: str            # ISO timestamp ("" when unknown)
    content: str
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Session harvesting
# ---------------------------------------------------------------------------

_WS = re.compile(r"\s+")


def _clean(text: str, limit: int = 1200) -> str:
    text = _WS.sub(" ", (text or "").strip())
    return text[:limit]


def _session_records(path: Path) -> Iterator[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict) and rec.get("kind"):
                    yield rec
    except OSError:
        return


def harvest_sessions(
    sessions_dir: Path | None = None,
    since: dict[str, str] | None = None,
) -> tuple[list[Experience], dict[str, str]]:
    """Harvest new experiences from chat sessions.

    ``since`` maps session name -> ISO timestamp watermark; only records
    with ``ts`` strictly greater than the watermark are harvested.
    Returns ``(experiences, new_watermarks)``.
    """
    if sessions_dir is None:
        try:
            from levi.agent.chat import sessions_dir as _sd
            sessions_dir = _sd()
        except Exception:
            return [], {}
    since = since or {}
    experiences: list[Experience] = []
    watermarks: dict[str, str] = {}
    if not sessions_dir or not sessions_dir.is_dir():
        return [], {}

    for path in sorted(sessions_dir.glob("*.jsonl")):
        name = path.stem
        mark = since.get(name, "")
        latest = mark
        n = 0
        for rec in _session_records(path):
            ts = str(rec.get("ts", "") or "")
            if ts > latest:
                latest = ts
            if mark and ts <= mark:
                continue
            kind = rec.get("kind")
            if kind == "message":
                role = rec.get("role", "")
                content = _clean(str(rec.get("content", "") or ""))
                if not content or len(content) < 3:
                    continue
                if role == "user":
                    ekind = "user-said"
                elif role == "assistant":
                    ekind = "levi-did"
                elif role == "tool":
                    ekind = "levi-did"
                    content = f"[tool {rec.get('name', '?')}] {content}"
                else:
                    continue
                n += 1
                experiences.append(
                    Experience(
                        id=f"ses:{name}:{n}",
                        kind=ekind,
                        source=name,
                        ts=ts,
                        content=content,
                    )
                )
            elif kind == "summary":
                content = _clean(str(rec.get("content", "") or ""))
                if not content:
                    continue
                n += 1
                experiences.append(
                    Experience(
                        id=f"ses:{name}:{n}",
                        kind="distilled",
                        source=name,
                        ts=ts,
                        content=content,
                        meta={"covers_messages": rec.get("covers_messages", 0)},
                    )
                )
            elif kind == "note":
                content = _clean(str(rec.get("content", "") or ""))
                if not content:
                    continue
                n += 1
                experiences.append(
                    Experience(
                        id=f"ses:{name}:{n}",
                        kind="note",
                        source=name,
                        ts=ts,
                        content=content,
                    )
                )
        watermarks[name] = latest
    return experiences, watermarks


# ---------------------------------------------------------------------------
# Automation harvesting
# ---------------------------------------------------------------------------


def harvest_automations(auto_path: Path | None = None) -> list[Experience]:
    """One experience per automation that has run at least once."""
    if auto_path is None:
        auto_path = Path.home() / ".levi" / "automations" / "automations.json"
    try:
        raw = json.loads(auto_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out: list[Experience] = []
    for a in raw.get("automations", []):
        runs = int(a.get("run_count", 0) or 0)
        if runs <= 0:
            continue
        name = a.get("name", a.get("id", "?"))
        last = a.get("last_result", "") or ""
        out.append(
            Experience(
                id=f"auto:{a.get('id', '?')}",
                kind="automation",
                source=str(a.get("id", "?")),
                ts=str(a.get("last_run", "") or ""),
                content=(
                    f"Automation '{name}' has run {runs} time(s); "
                    f"status={a.get('status', '?')}; last result: {_clean(last, 400)}"
                ),
                meta={"run_count": runs, "status": a.get("status", "?")},
            )
        )
    return out


# ---------------------------------------------------------------------------
# Top-level harvest
# ---------------------------------------------------------------------------


def harvest_new(since: dict[str, str] | None = None) -> tuple[list[Experience], dict[str, str]]:
    """Harvest all new experiences across sources.

    Returns ``(experiences, watermarks)`` where watermarks should be
    persisted by the caller (see :mod:`levi.growth.cycle`).
    """
    experiences, watermarks = harvest_sessions(since=since)
    experiences.extend(harvest_automations())
    return experiences, watermarks
