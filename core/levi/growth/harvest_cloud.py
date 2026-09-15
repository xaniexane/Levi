"""Cloud-session harvesting for the growth loop.

Cloud API chat sessions live in the same sessions directory as local
ones (see :mod:`levi.agent.chat`), but namespaced per API key by
:mod:`levi.agent.server`: ``cloud_<tail>_<session_id>.jsonl`` where
``<tail>`` is the last 8 alnum characters of the key's public prefix.

Consent model (enforced here, before any file is opened):

* global kill switch: ``LEVI_GROWTH_CLOUD_LEARN=0`` disables cloud
  harvest entirely;
* per-key opt-out: the key record's ``learn`` flag (``levi cloud keys
  create --no-learn``, ``levi cloud keys learn <name> off``). Keys
  whose flag is false are skipped *entirely* — their session files
  are never opened, not even for redacted ingestion;
* unknown tails (no matching key record) are skipped: without a key
  record there is no verifiable consent.

Each harvested experience is tagged ``meta["origin"] = "cloud"``,
``meta["key_name"]`` (the key *name*, never the raw key), and
``meta["provider"]`` from the turn-meta records written by
:class:`levi.agent.chat.ConversationManager` (``"?"`` when absent).

Only persistent ``/v1/agent/chat`` sessions are harvestable. One-shot
``/v1/agent/run`` calls leave no session record (only metering), so
there is nothing to learn from — an honest, documented limit.
"""

from __future__ import annotations

import os
from pathlib import Path

from levi.growth.experience import Experience, _clean, _session_records


def cloud_learn_enabled() -> bool:
    """Global kill switch. ``LEVI_GROWTH_CLOUD_LEARN=0`` disables."""
    return os.environ.get("LEVI_GROWTH_CLOUD_LEARN", "1").strip() not in (
        "0",
        "false",
        "no",
    )


def _sessions_dir() -> Path | None:
    try:
        from levi.agent.chat import sessions_dir as _sd

        return _sd()
    except Exception:
        return None


def _key_tails() -> dict[str, dict]:
    """Map session-file tail -> key record for keys that consent.

    Consent default: a missing ``learn`` field means opt-out-able but
    currently opted IN (disclosed in docs/CLOUD_API.md). Revoked keys
    are never included.
    """
    try:
        from levi.cloud import apikeys
    except Exception:
        return {}
    out: dict[str, dict] = {}
    try:
        records = apikeys.list_keys(include_revoked=False)
    except Exception:
        return {}
    for rec in records:
        if not rec.get("learn", True):
            continue
        prefix = str(rec.get("prefix", "") or "")
        tail = "".join(c for c in prefix if c.isalnum())[-8:]
        if tail:
            out[tail] = rec
    return out


def harvest_cloud_sessions(
    since: dict[str, str] | None = None,
) -> tuple[list[Experience], dict[str, str]]:
    """Harvest new experiences from consenting cloud API sessions.

    Returns ``(experiences, watermarks)``; watermark keys are
    ``"cloud:<stem>"`` so they never collide with local session marks.
    """
    if not cloud_learn_enabled():
        return [], {}
    sessions_dir = _sessions_dir()
    if not sessions_dir or not sessions_dir.is_dir():
        return [], {}
    tails = _key_tails()
    if not tails:
        return [], {}

    since = since or {}
    experiences: list[Experience] = []
    watermarks: dict[str, str] = {}

    for path in sorted(sessions_dir.glob("cloud_*.jsonl")):
        stem = path.stem  # cloud_<tail>_<session_id>
        key_rec = None
        for tail, rec in tails.items():
            if stem.startswith("cloud_" + tail + "_"):
                key_rec = rec
                break
        if key_rec is None:
            continue  # no verifiable consent — skip entirely
        key_name = str(key_rec.get("name", "?"))

        mark_key = "cloud:" + stem
        mark = since.get(mark_key, "")
        latest = mark
        n = 0
        provider = "?"  # from the most recent turn-meta record
        for rec in _session_records(path):
            ts = str(rec.get("ts", "") or "")
            if ts > latest:
                latest = ts
            if mark and ts <= mark:
                continue
            kind = rec.get("kind")
            if kind == "turn-meta":
                provider = str(rec.get("provider", "") or "?")
                continue
            if kind == "message":
                role = rec.get("role", "")
                content = _clean(str(rec.get("content", "") or ""))
                if not content or len(content) < 3:
                    continue
                if role == "user":
                    ekind = "user-said"
                elif role in ("assistant", "tool"):
                    ekind = "levi-did"
                    if role == "tool":
                        content = f"[tool {rec.get('name', '?')}] {content}"
                else:
                    continue
                n += 1
                experiences.append(
                    Experience(
                        id=f"cloud:{stem}:{n}",
                        kind=ekind,
                        source="cloud:" + key_name,
                        ts=ts,
                        content=content,
                        meta={
                            "origin": "cloud",
                            "key_name": key_name,
                            "provider": provider,
                            "session": stem,
                        },
                    )
                )
        watermarks[mark_key] = latest
    return experiences, watermarks
