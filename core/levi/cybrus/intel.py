"""Cybrus threat-intel ingestion — the Cybrus side of the DemandPulse feed.

DemandPulse's scans surface threat/scam signals (see the 🔗 pairing
alliance, ``levi.demand.cybrus_alliance`` — owned by a teammate; this
module never edits it). The publisher side lives in
``levi.demandpulse.threat_feed``. THIS module is the ingestion interface
that FRONT-GUARD's screening layer consumes.

LAWS (binding — declared first, enforced below, machine-checked by
tests/test_front_feed.py — honestly named invariant checks; nothing
here is formally proven):
  I1  Provenance or refusal. Every indicator must carry source,
      published_ts, and confidence. An envelope missing any of the
      three is REFUSED, not consumed. No silent acceptance. One
      self-asserted source name may occupy at most
      ``_INTEL_SOURCE_QUOTA`` records (FF5): the quota cannot stop a
      determined attacker from minting fresh names (sources are
      unauthenticated), but it bounds one name's blast radius and
      forces name-rotation, which is itself a detectable signal.
  I2  Stale intel is refused. published_ts older than
      ``STALE_AFTER_S`` (72h) never enters the store. Future
      timestamps beyond ``CLOCK_SKEW_S`` are refused as forgery.
  I3  Append-only. Accepted indicators land in the hash-chained
      ``intel.jsonl`` store. Nothing is deleted, nothing is
      overwritten; duplicates are refused — including near-duplicates
      (FF2: a cosmetic text mutation with overlapping markers is the
      same intel, not new intel). Consumption (``get_indicators``)
      never mutates the store. Every append anchors ``{count,
      tip_hash}`` in ``intel.state.json`` (FF3/FF4): verify_chain()
      fails closed on a rewritten chain or a truncated tail. A writer
      who can rewrite BOTH files can re-anchor — full protection needs
      an external anchor (same residual as the audit trail).
  I4  Intel is input, never decision. This module makes NO verdicts:
      no screening, no quarantine, no release, no blocking. It never
      calls front, enforce, gateway, broker, money, or vault. It only
      stores indicators and hands them to the screening layer.
  I5  No new egress. Zero network. Stdlib only. It never fetches,
      verifies, or reports anything upstream.
  I6  Fail closed on intake. A malformed envelope yields a refused
      receipt, never an exception to the caller, never silent
      acceptance.
  I7  Every intake — accepted or refused — is audit-logged through the
      tamper-evident AuditEngine (metadata only: indicator_id, source,
      decision, reason — never full intel text).
  I8  Coverage, not bypass. Enforced through the existing 12 Cybrus
      laws; no exceptions, no new allow paths.

Seam for FRONT-GUARD (🏰 owns ``front.py``; this file never edits it):
  ``get_indicators(min_confidence=..., fresh_within_s=...)`` returns the
  active indicator set for the screening layer to consult. FRONT
  decides what to do with them — ingestion holds no opinion.

State: ``~/.levi/cybrus/intel.jsonl`` (LEVI_HOME override honored).
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- provenance / freshness policy --------------------------------------
STALE_AFTER_S = 72 * 3600        #: intel older than 72h is refused
CLOCK_SKEW_S = 5 * 60           #: future timestamps beyond 5m are refused
INTEL_TEXT_MAX = 280            #: one sentence, same discipline as the feed
CONFIDENCE_FLOOR = 0.0
CONFIDENCE_CEIL = 1.0

#: FF5 — per-source intake quota. Source names are self-asserted
#: (no intake authentication), so a quota cannot stop a determined
#: attacker from minting fresh names — but it bounds how much of the
#: store ONE name can occupy, and forces name-rotation, which is
#: itself a detectable signal. Legitimate publishers emit a handful of
#: indicators per scan; 100 is generous.
_INTEL_SOURCE_QUOTA = 100

#: FF2 — near-duplicate similarity floor. A new indicator whose
#: normalized text scores at or above this against a stored indicator
#: (with overlapping markers) is a cosmetic mutation of the same intel
#: ("...credentials." vs "...credentials!"), not new intel.
_DEDUPE_SIMILARITY = 0.92

_INTEL_NAME = "intel.jsonl"

#: Store name (→ ``intel.state.json``) for the truncation anchor (FF4).
_INTEL_STATE_NAME = "intel.state.json"

_REQUIRED_PROVENANCE = ("source", "published_ts", "confidence")


# --- standalone-safe sibling imports (same pattern as front.py) ---------
def _cybrus_module(name: str):
    try:
        from levi.cybrus import _paths as _p  # noqa: F401

        import importlib

        return importlib.import_module(f"levi.cybrus.{name}")
    except ImportError:
        import importlib.util

        here = Path(__file__).resolve().parent
        spec = importlib.util.spec_from_file_location(
            f"levi.cybrus.{name}.standalone", here / f"{name}.py"
        )
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError(f"cybrus module {name!r} unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def _paths():
    return _cybrus_module("_paths")


def _AuditEngine():
    """An AuditEngine instance (tamper-evident audit log)."""
    return _cybrus_module("audit").AuditEngine()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


def _parse_ts(raw: Any) -> Optional[datetime]:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _content_hash(text: str, markers: List[str]) -> str:
    body = "\x00".join([text, ",".join(sorted(markers))])
    return hashlib.sha256(body.encode("utf-8", "replace")).hexdigest()


# --- append-only, hash-chained intel store -------------------------------
GENESIS_PREV = "0" * 64


def _store_path() -> Path:
    return Path(_paths().cybrus_dir()) / _INTEL_NAME


def _chain_hash(prev: str, record: Dict[str, Any]) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev + canonical).encode("utf-8")).hexdigest()


def _tail_hash(path: Path) -> Optional[str]:
    """Hash of the last stored record (None when the store is empty).

    Reads from the tail; the store is append-only so the last non-empty
    line is the chain head.
    """
    if not path.exists():
        return None
    head = None
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            head = rec.get("hash")
    return head


def _store_records() -> List[Dict[str, Any]]:
    path = _store_path()
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
    return records


def _append_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Atomic append (O_APPEND + fsync); the directory and file are
    owner-only. There is no delete or rewrite path — append-only by
    construction (I3)."""
    path = _store_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.exists():
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    prev = _tail_hash(path) or GENESIS_PREV
    body = dict(record)
    stored = {**body, "prev": prev, "hash": _chain_hash(prev, body)}
    blob = (
        json.dumps(stored, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND)
    try:
        os.write(fd, blob)
        os.fsync(fd)
    finally:
        os.close(fd)
    return stored


def verify_chain() -> Dict[str, Any]:
    """Walk the hash chain, then check the truncation anchor.

    Any flipped byte fails at its exact index (``broken_at``). A fully
    rewritten chain (FF3) or a truncated tail (FF4) fails on the anchor:
    ``{"count", "tip_hash"}`` in ``intel.state.json`` — written
    atomically beside every append — records the true record count and
    chain tip, so a recomputed chain over forged text, or a store with
    its tail deleted, cannot verify. A non-empty store with no anchor
    fails closed (legacy predating anchors; use :func:`reanchor`
    explicitly after review).

    Honest limit (same residual as the audit trail, RED-1 L10): the
    anchor stops an attacker who can rewrite the LOG but not the anchor
    file. A writer who can rewrite BOTH files can re-anchor a forged
    chain — full protection needs an external anchor.
    """
    records = _store_records()
    prev = GENESIS_PREV
    for i, rec in enumerate(records):
        body = {k: v for k, v in rec.items() if k not in ("prev", "hash")}
        if rec.get("prev") != prev or rec.get("hash") != _chain_hash(prev, body):
            return {"ok": False, "broken_at": i, "records": len(records)}
        prev = rec["hash"]
    count, tip = len(records), prev
    anchor = _load_state()
    if anchor is None:
        if count == 0:
            return {"ok": True, "records": 0}
        return {"ok": False, "broken_at": None, "records": count,
                "anchor": "missing"}
    if anchor.get("count") != count or anchor.get("tip_hash") != tip:
        return {"ok": False, "broken_at": None, "records": count,
                "anchor": "mismatch"}
    return {"ok": True, "records": count}


def _state_path() -> Path:
    return Path(_paths().cybrus_dir()) / _INTEL_STATE_NAME


def _load_state() -> Optional[Dict[str, Any]]:
    """The ``{"count", "tip_hash"}`` anchor, or ``None`` when no anchor
    exists yet (fresh store, or legacy store predating anchors)."""
    try:
        data = _paths().load_json_store(_state_path())
    except Exception:
        # Corrupt anchor: quarantined by _paths; treat as missing —
        # verify_chain() fails closed on a non-empty store.
        return None
    if isinstance(data, dict) and isinstance(data.get("count"), int):
        return data
    return None


def _save_state(count: int, tip_hash: str) -> None:
    _paths().save_json_store(_state_path(), {"count": count, "tip_hash": tip_hash})


def reanchor() -> Dict[str, Any]:
    """Explicit operator escape hatch for legacy stores predating
    anchors (mirrors the audit-trail reanchor, RED-1 L10). Recomputes
    the truncation anchor from the current chain after verifying
    internal links; audit-logs its own use. Never raises."""
    try:
        records = _store_records()
        prev = GENESIS_PREV
        for rec in records:
            body = {k: v for k, v in rec.items() if k not in ("prev", "hash")}
            if rec.get("prev") != prev or rec.get("hash") != _chain_hash(prev, body):
                return {"reanchored": False,
                        "reason": "chain link broken; not re-anchored"}
            prev = rec["hash"]
        tip = records[-1]["hash"] if records else GENESIS_PREV
        _save_state(len(records), tip)
    except Exception:
        return {"reanchored": False, "reason": "internal error"}
    try:
        _AuditEngine().append(
            "cybrus.intel.reanchored", "cybrus-intel", {"count": len(records)}
        )
    except Exception:
        pass
    return {"reanchored": True, "count": len(records)}


def _near_duplicate(text: str, markers: List[str], rec: Dict[str, Any]) -> bool:
    """FF2: True when (text, markers) is a cosmetic mutation of a stored
    indicator. Normalized texts are compared with a similarity floor;
    the marker sets must overlap (disjoint markers mean distinct
    indicators, even when the texts read alike)."""
    old_markers = {
        str(m).strip().lower() for m in (rec.get("markers") or []) if str(m).strip()
    }
    new_markers = {str(m).strip().lower() for m in markers if str(m).strip()}
    if old_markers and new_markers and not (old_markers & new_markers):
        return False
    old_text = str(rec.get("text") or "").strip().lower()
    new_text = text.strip().lower()
    if not old_text or not new_text:
        return old_text == new_text
    return (
        difflib.SequenceMatcher(None, old_text, new_text).ratio() >= _DEDUPE_SIMILARITY
    )


# --- ingestion -----------------------------------------------------------
def _refuse(indicator_id: str, reason: str, envelope: Any) -> Dict[str, Any]:
    receipt = {
        "accepted": False,
        "reason": reason,
        "indicator_id": indicator_id,
        "ts": _utcnow_iso(),
    }
    _audit(receipt, envelope)
    return receipt


def _audit(receipt: Dict[str, Any], envelope: Any) -> None:
    try:
        env = envelope if isinstance(envelope, dict) else {}
        _AuditEngine().append(
            "cybrus.intel.ingest",
            "cybrus-intel",
            {
                "indicator_id": receipt.get("indicator_id"),
                "accepted": receipt.get("accepted"),
                "reason": receipt.get("reason"),
                "source": str(env.get("source") or ""),
                "confidence": env.get("confidence"),
            },
        )
    except Exception:
        # I6: audit failure must not break intake's fail-closed posture.
        pass


def ingest(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Ingest one threat-intel envelope. NEVER raises (I6).

    Accepts a dict with provenance fields ``source``, ``published_ts``
    (ISO-8601), ``confidence`` (0..1), plus ``text`` and ``markers``.
    Returns a receipt ``{accepted, reason, indicator_id, ts}``.

    Refusal reasons: ``unprovenanced`` (I1), ``stale`` (I2),
    ``future_timestamp`` (I2), ``invalid_confidence`` (I1),
    ``malformed`` (I6), ``duplicate`` (I3 — exact or near-duplicate,
    FF2), ``quota`` (FF5 — per-source intake quota).
    """
    try:
        return _ingest_inner(dict(envelope or {}))
    except Exception as exc:  # I6: intake failure is a refusal, never a crash
        return _refuse("", f"malformed:{type(exc).__name__}", envelope)


def _ingest_inner(env: Dict[str, Any]) -> Dict[str, Any]:
    indicator_id = str(env.get("indicator_id") or uuid.uuid4().hex)

    # I1 — provenance or refusal
    missing = [
        f for f in _REQUIRED_PROVENANCE if f in (None, "") or env.get(f) in (None, "")
    ]
    if missing:
        return _refuse(indicator_id, f"unprovenanced:missing {','.join(missing)}", env)

    source = str(env["source"]).strip()
    if not source:
        return _refuse(indicator_id, "unprovenanced:missing source", env)

    ts = _parse_ts(env["published_ts"])
    if ts is None:
        return _refuse(indicator_id, "unprovenanced:bad published_ts", env)

    conf = env["confidence"]
    if isinstance(conf, bool) or not isinstance(conf, (int, float)):
        return _refuse(indicator_id, "invalid_confidence:not-a-number", env)
    conf = float(conf)
    if not (CONFIDENCE_FLOOR <= conf <= CONFIDENCE_CEIL):
        return _refuse(indicator_id, "invalid_confidence:out-of-range", env)

    # I2 — freshness: stale refused, future-skewed refused (forgery guard)
    now = _utcnow()
    age = (now - ts).total_seconds()
    if age > STALE_AFTER_S:
        return _refuse(indicator_id, "stale:intel older than 72h", env)
    if age < -CLOCK_SKEW_S:
        return _refuse(indicator_id, "future_timestamp:skew beyond 5m", env)

    text = str(env.get("text") or "")[:INTEL_TEXT_MAX]
    markers = [str(m) for m in (env.get("markers") or []) if str(m).strip()]
    if not text and not markers:
        return _refuse(indicator_id, "malformed:empty indicator", env)

    # I3 — dedupe by content; duplicates are refused, never re-appended.
    # The check → append → anchor sequence holds the store lock so two
    # concurrent intakes cannot interleave (dedupe TOCTOU).
    chash = _content_hash(text, markers)
    with _paths().store_lock(_store_path()):
        records = _store_records()
        for rec in records:
            if rec.get("content_hash") == chash:
                dup = _refuse(indicator_id, "duplicate:already ingested", env)
                dup["existing_id"] = rec.get("indicator_id")
                return dup
            # FF2 — near-duplicate: a cosmetic text mutation with
            # overlapping markers is the same intel, not new intel.
            if _near_duplicate(text, markers, rec):
                dup = _refuse(
                    indicator_id, "duplicate:near-duplicate of stored intel", env
                )
                dup["existing_id"] = rec.get("indicator_id")
                return dup
        # FF5 — per-source quota: one self-asserted source name can
        # occupy at most _INTEL_SOURCE_QUOTA records.
        if sum(1 for rec in records if rec.get("source") == source) >= _INTEL_SOURCE_QUOTA:
            return _refuse(
                indicator_id,
                f"quota:source exceeded {_INTEL_SOURCE_QUOTA} records",
                env,
            )
        stored = _append_record(
            {
                "indicator_id": indicator_id,
                "kind": str(env.get("kind") or "threat_indicator"),
                "text": text,
                "markers": markers,
                "source": source,
                "scan_ref": str(env.get("scan_ref") or ""),
                "published_ts": env["published_ts"],
                "confidence": conf,
                "content_hash": chash,
                "ingested_ts": _utcnow_iso(),
            }
        )
        # FF3/FF4 — anchor the new head beside the append, atomically.
        _save_state(len(records) + 1, stored["hash"])
    receipt = {
        "accepted": True,
        "reason": "ingested",
        "indicator_id": indicator_id,
        "ts": stored["ingested_ts"],
    }
    _audit(receipt, env)
    return receipt


# --- consumption seam for FRONT-GUARD ------------------------------------
def get_indicators(
    min_confidence: float = CONFIDENCE_FLOOR,
    fresh_within_s: float = STALE_AFTER_S,
) -> List[Dict[str, Any]]:
    """Active indicators for the screening layer. Read-only (I3/I4):
    the store is never mutated here and no verdict is made.

    An indicator is active when its confidence >= min_confidence and it
    was published within fresh_within_s. Results carry the indicator's
    provenance so FRONT can weigh it honestly.
    """
    now = _utcnow()
    active: List[Dict[str, Any]] = []
    for rec in _store_records():
        ts = _parse_ts(rec.get("published_ts"))
        if ts is None:
            continue
        age = (now - ts).total_seconds()
        if age < -CLOCK_SKEW_S or age > fresh_within_s:
            continue
        conf = rec.get("confidence", 0.0)
        if not isinstance(conf, (int, float)) or conf < min_confidence:
            continue
        active.append(
            {
                "indicator_id": rec.get("indicator_id"),
                "kind": rec.get("kind"),
                "text": rec.get("text"),
                "markers": list(rec.get("markers") or []),
                "source": rec.get("source"),
                "published_ts": rec.get("published_ts"),
                "confidence": float(conf),
            }
        )
    return active


def stats() -> Dict[str, Any]:
    """Honest posture of the intel store."""
    return {
        "records": len(_store_records()),
        "chain": verify_chain(),
        "active": len(get_indicators()),
        "stale_after_s": STALE_AFTER_S,
    }


def describe_posture() -> Dict[str, Any]:
    """Backend posture, honestly reported (12-law L12)."""
    s = stats()
    return {
        "module": "levi.cybrus.intel",
        "laws": ["I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8"],
        "store": str(_store_path()),
        "records": s["records"],
        "active_indicators": s["active"],
        "chain_ok": s["chain"]["ok"],
        "proof": "tests/test_front_feed.py (invariant checks, not formal proof)",
    }
