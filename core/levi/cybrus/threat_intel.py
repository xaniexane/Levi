"""Cybrus threat-intel feed — the DemandPulse → Cybrus one-way intel lane.

DemandPulse scans the wild (demand scans, watcher channels) and surfaces
threat patterns — scam lures, fraud signals, phishing, social-engineering
pressure, prompt-injection payloads. Those sightings become screening intel
for Cybrus's FRONT guard (``levi.cybrus.front`` — sibling 🏰 owns the
inbound screening layer; this module is the intel interface beside it).

LAWS (binding — declared first, enforced below, machine-checked by
tests/test_cybrus_demand_pairing.py; honestly named invariant checks,
nothing formally proven):
  I1 (provenance) No threat intel is published or consumed without
      provenance. Every indicator carries publisher identity, detector
      name@version, and a timestamp. Anonymous, incomplete, or
      impersonating indicators are refused at publish and skipped (with
      an audit receipt) at consume.
  I2 (one-way) The feed never commands. Publishing intel grants no
      authority over Cybrus; consuming intel grants no authority over
      DemandPulse. Neither organ gates, approves, or vetoes the other.
      The publisher identity is bound to the presenting credential's
      label — a publisher cannot publish as anyone else.
  I3 (append-only) The intel store only appends. Records are never
      edited or deleted; tampering is detected by the hash chain
      (``verify``) and tampered records are skipped at consume time.
  I4 (metadata-only audit) Audit records carry indicator ids, kinds,
      publisher, and decisions — never raw scanned text bodies.

Relationship to FRONT (``levi.cybrus.front``):
  FRONT screens inbound messages with its own deterministic rule
  catalog. This feed does NOT inject rules into FRONT — that is the
  FRONT sibling's call. The consumer seam is :func:`consume` /
  :func:`screening_snapshot` / :func:`match_hints`: vetted indicators
  with provenance, ready for a screening layer to consult. FRONT
  decides; the feed only informs.

Stdlib-only, no network. State under ``~/.levi/cybrus/``
(``LEVI_HOME`` override honored). The publisher authenticates with a
Cybrus bearer token carrying the ``threat.intel.publish`` scope.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# --- standalone-safe import of the sibling _paths helper -------------------
def _paths():  # noqa: D103 - private helper
    try:
        from levi.cybrus import _paths as _p

        return _p
    except ImportError:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "levi.cybrus._paths.standalone",
            Path(__file__).resolve().parent / "_paths.py",
        )
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError("cybrus _paths helper unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


#: The declared intel laws, machine-readable (tests pin every id).
INTEL_LAWS = (
    ("I1", "No threat intel without provenance: publisher, detector name@version, and timestamp on every indicator."),
    ("I2", "The feed is one-way: publishing grants no authority over Cybrus; consuming grants no authority over DemandPulse."),
    ("I3", "The intel store is append-only; tampering is detected by the hash chain and skipped at consume time."),
    ("I4", "Audit records carry metadata only — never raw scanned text bodies."),
)

#: Threat classes the feed carries. Aligned with the FRONT guard's rule
#: catalog (R03/R07/R08/R09) plus prompt-injection (twins' hostile-marker
#: discipline).
INTEL_KINDS = (
    "scam",
    "fraud",
    "phishing",
    "social_engineering",
    "prompt_injection",
)

#: Scope a publisher token must carry.
PUBLISH_SCOPE = "threat.intel.publish"

#: Snippet bound — matches the watcher discipline (NEED_TEXT_MAX): enough
#: to screen on, never a full body.
SNIPPET_MAX = 280

_INTEL_NAME = "threat_intel.jsonl"

_DETECTOR_RE = re.compile(r"^[\w.\-]+@\d+\.\d+\.\d+$")


class IntelError(Exception):
    """Base class for threat-intel feed failures."""


class IntelRefused(IntelError):
    """Publish refused: bad credential, missing scope, or bad provenance."""


# ---------------------------------------------------------------------------
# Indicator


@dataclass
class ThreatIndicator:
    """One vetted threat sighting. ``publisher`` is filled by
    :func:`publish` from the presenting credential's label (I2: the
    publisher cannot claim to be anyone else)."""

    id: str
    kind: str
    confidence: float
    snippet: str
    detector: str
    ts: str
    publisher: Optional[str] = None
    signal_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if self.kind not in INTEL_KINDS:
            raise ValueError(f"kind must be one of {INTEL_KINDS}, got {self.kind!r}")
        c = self.confidence
        if isinstance(c, bool) or not isinstance(c, (int, float)) or not 0.0 <= c <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {c!r}")
        if not isinstance(self.snippet, str) or not self.snippet.strip():
            raise ValueError("snippet must be a non-empty string")
        if len(self.snippet) > SNIPPET_MAX:
            raise ValueError(f"snippet must be at most {SNIPPET_MAX} chars")
        if not isinstance(self.detector, str) or not _DETECTOR_RE.match(self.detector):
            raise ValueError(
                f"detector must be name@x.y.z, got {self.detector!r}"
            )
        try:
            datetime.fromisoformat(self.ts)
        except (ValueError, TypeError):
            raise ValueError(f"ts must be an ISO timestamp, got {self.ts!r}")
        if self.publisher is not None and (
            not isinstance(self.publisher, str) or not self.publisher.strip()
        ):
            raise ValueError("publisher must be a non-empty string when given")
        if self.signal_ref is not None and (
            not isinstance(self.signal_ref, str) or not self.signal_ref.strip()
        ):
            raise ValueError("signal_ref must be a non-empty string when given")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "confidence": self.confidence,
            "snippet": self.snippet,
            "detector": self.detector,
            "ts": self.ts,
            "publisher": self.publisher,
            "signal_ref": self.signal_ref,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ThreatIndicator":
        return cls(
            id=str(raw.get("id") or ""),
            kind=str(raw.get("kind") or ""),
            confidence=raw.get("confidence"),
            snippet=str(raw.get("snippet") or ""),
            detector=str(raw.get("detector") or ""),
            ts=str(raw.get("ts") or ""),
            publisher=raw.get("publisher"),
            signal_ref=raw.get("signal_ref"),
        )


def _indicator_id(publisher: str, detector: str, ts: str, kind: str, snippet: str) -> str:
    """Server-side id: recomputed at publish, never trusted from the
    client (I1 — the publisher does not assign identities)."""
    body = "\x00".join((publisher, detector, ts, kind, snippet))
    return "ti-" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Store — append-only, hash-chained, owner-only (I3)


def _store_path() -> Path:
    p = _paths().cybrus_dir() / _INTEL_NAME
    if not p.exists():
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    else:
        os.chmod(p, 0o600)
    return p


def _canonical(record: Dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"))


def _hash_record(prev_hash: str, record: Dict[str, Any]) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    return hashlib.sha256((prev_hash + _canonical(body)).encode("utf-8")).hexdigest()


_GENESIS_PREV = "0" * 64


def _read_records() -> List[Tuple[int, Optional[Dict[str, Any]]]]:
    out: List[Tuple[int, Optional[Dict[str, Any]]]] = []
    try:
        with _store_path().open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                idx = len(out)
                try:
                    out.append((idx, json.loads(line)))
                except json.JSONDecodeError:
                    out.append((idx, None))
    except OSError:
        pass
    return out


def _last_hash() -> Tuple[str, int]:
    prev, seq = _GENESIS_PREV, -1
    for _, rec in _read_records():
        if isinstance(rec, dict):
            prev = rec.get("hash", prev)
            seq = rec.get("seq", seq)
    return prev, seq


def _append_record(indicator: ThreatIndicator) -> Dict[str, Any]:
    prev_hash, last_seq = _last_hash()
    record = {
        "seq": last_seq + 1,
        "ts": _utcnow_iso(),
        "indicator": indicator.to_dict(),
        "prev": prev_hash,
    }
    record["hash"] = _hash_record(prev_hash, record)
    blob = (_canonical(record) + "\n").encode("utf-8")
    fd = os.open(_store_path(), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, blob)
        os.fsync(fd)
    finally:
        os.close(fd)
    return record


def verify() -> Tuple[bool, Optional[int]]:
    """Walk the intel store's hash chain. Returns ``(True, None)`` when
    intact, else ``(False, first_bad_index)``."""
    expected_prev = _GENESIS_PREV
    expected_seq = 0
    for idx, rec in _read_records():
        if not isinstance(rec, dict):
            return False, idx
        if rec.get("seq") != expected_seq:
            return False, idx
        if rec.get("prev") != expected_prev:
            return False, idx
        if rec.get("hash") != _hash_record(rec.get("prev", ""), rec):
            return False, idx
        expected_prev = rec["hash"]
        expected_seq += 1
    return True, None


# ---------------------------------------------------------------------------
# Audit (I4: metadata only)


def _audit(event: str, actor: str, details: Dict[str, Any]) -> None:
    try:
        from levi.cybrus.audit import AuditEngine

        AuditEngine().append(event, str(actor), dict(details))
    except Exception:
        pass  # audit failure never breaks the feed's fail-closed path


# ---------------------------------------------------------------------------
# Publish — DemandPulse -> feed (I1/I2)


def _authenticate_publisher(credential: str) -> Dict[str, Any]:
    from levi.cybrus.tokens import TokenEngine

    payload = TokenEngine().validate(credential)
    if payload is None:
        raise IntelRefused(
            "credential did not validate (unknown / revoked / expired); "
            "present a live Cybrus bearer token"
        )
    if PUBLISH_SCOPE not in (payload.get("scopes") or []):
        raise IntelRefused(
            f"credential lacks the {PUBLISH_SCOPE!r} scope — "
            "publish is closed to this identity"
        )
    label = payload.get("label")
    if not label:
        raise IntelRefused(
            "publishing requires a labeled (named) credential — "
            "anonymous publishers are refused (I1)"
        )
    return payload


def publish(
    indicators: List[Dict[str, Any]],
    *,
    credential: Optional[str] = None,
) -> Dict[str, Any]:
    """Publish threat indicators into the feed. One-way intel (I2).

    ``indicators``: dicts with kind, confidence, snippet, detector, ts,
    and optional signal_ref. ``publisher`` is NOT accepted from the
    caller — it is bound from the credential's label, so a publisher
    cannot publish as anyone else.

    Every indicator is provenance-checked (I1); any failure refuses the
    WHOLE batch — a poisoned batch never partially lands. Returns the
    publish receipt. Raises :class:`IntelRefused` on any refusal, naming
    the remedy (L6).
    """
    if credential is None:
        raise IntelRefused(
            "no credential: present a Cybrus bearer token with the "
            f"{PUBLISH_SCOPE!r} scope"
        )
    payload = _authenticate_publisher(credential)
    publisher = payload["label"]

    if not isinstance(indicators, list) or not indicators:
        raise IntelRefused("indicators must be a non-empty list")

    vetted: List[ThreatIndicator] = []
    for raw in indicators:
        if not isinstance(raw, dict):
            _audit("intel.rejected", publisher, {"reason": "indicator_not_a_dict"})
            raise IntelRefused("every indicator must be a dict with provenance")
        if raw.get("publisher") not in (None, publisher):
            # A caller-supplied publisher that is not the credential's
            # own label is impersonation — refuse the batch (I1/I2).
            _audit(
                "intel.rejected",
                publisher,
                {"reason": "publisher_mismatch", "claimed": str(raw.get("publisher"))[:64]},
            )
            raise IntelRefused(
                "indicator publisher does not match the credential's label — "
                "publish as yourself or not at all"
            )
        try:
            ind = ThreatIndicator.from_dict(raw)
        except (ValueError, TypeError) as exc:
            _audit(
                "intel.rejected",
                publisher,
                {"reason": "bad_provenance", "detail": str(exc)[:160]},
            )
            raise IntelRefused(f"indicator failed provenance checks: {exc}")
        ind.publisher = publisher
        ind.id = _indicator_id(publisher, ind.detector, ind.ts, ind.kind, ind.snippet)
        vetted.append(ind)

    stored_ids: List[str] = []
    for ind in vetted:
        rec = _append_record(ind)
        stored_ids.append(rec["indicator"]["id"])

    kinds = sorted({i.kind for i in vetted})
    receipt = {
        "receipt_id": "ir-" + hashlib.sha256(
            (publisher + _utcnow_iso() + "".join(stored_ids)).encode("utf-8")
        ).hexdigest()[:12],
        "publisher": publisher,
        "count": len(vetted),
        "kinds": kinds,
        "indicator_ids": stored_ids,
        "ts": _utcnow_iso(),
    }
    _audit(
        "intel.published",
        publisher,
        {
            "receipt_id": receipt["receipt_id"],
            "count": receipt["count"],
            "kinds": kinds,
        },
    )
    return receipt


# ---------------------------------------------------------------------------
# Consume — feed -> FRONT guard (I1/I3)


def _record_ok(rec: Dict[str, Any], expected_prev: str, expected_seq: int) -> bool:
    """One record passes iff its chain link holds AND its indicator
    carries complete provenance (I1/I3)."""
    if rec.get("seq") != expected_seq:
        return False
    if rec.get("prev") != expected_prev:
        return False
    if rec.get("hash") != _hash_record(rec.get("prev", ""), rec):
        return False
    raw = rec.get("indicator")
    if not isinstance(raw, dict):
        return False
    try:
        ind = ThreatIndicator.from_dict(raw)
    except (ValueError, TypeError):
        return False
    return bool(ind.publisher)


def consume(
    *,
    since: Optional[str] = None,
    kinds: Optional[List[str]] = None,
    limit: int = 500,
) -> List[ThreatIndicator]:
    """Read vetted indicators for the screening layer. Every record is
    re-checked: broken chain links and incomplete provenance are
    skipped and audit-logged (I1/I3) — poisoned or tampered records
    never reach a consumer. Oldest first."""
    if kinds is not None:
        unknown = [k for k in kinds if k not in INTEL_KINDS]
        if unknown:
            raise IntelError(f"unknown kinds: {unknown}")
    if not isinstance(limit, int) or limit < 1:
        raise IntelError("limit must be a positive integer")

    since_dt = datetime.fromisoformat(since) if since else None

    out: List[ThreatIndicator] = []
    skipped: List[str] = []
    expected_prev = _GENESIS_PREV
    expected_seq = 0
    for idx, rec in _read_records():
        if not isinstance(rec, dict) or not _record_ok(rec, expected_prev, expected_seq):
            skipped.append(f"idx-{idx}")
            # A broken link breaks every link after it: the chain cannot
            # be trusted past the break, so stop (I3).
            if isinstance(rec, dict):
                break
            continue
        expected_prev = rec["hash"]
        expected_seq += 1
        ind = ThreatIndicator.from_dict(rec["indicator"])
        if kinds is not None and ind.kind not in kinds:
            continue
        if since_dt is not None:
            try:
                if datetime.fromisoformat(ind.ts) < since_dt:
                    continue
            except ValueError:
                skipped.append(ind.id)
                continue
        out.append(ind)
        if len(out) >= limit:
            break

    if skipped:
        _audit(
            "intel.skipped_unprovenanced",
            "cybrus-threat-intel",
            {"skipped": skipped[:50], "count": len(skipped)},
        )
    _audit(
        "intel.consumed",
        "cybrus-threat-intel",
        {"returned": len(out), "skipped": len(skipped)},
    )
    return out


def screening_snapshot(*, kinds: Optional[List[str]] = None, limit: int = 200) -> Dict[str, Any]:
    """Consumer-shaped view for the FRONT guard: newest-first vetted
    indicators as plain dicts, with per-kind counts. FRONT decides what
    to do with them — the feed only informs (I2)."""
    vetted = consume(kinds=kinds, limit=limit)
    counts: Dict[str, int] = {}
    for ind in vetted:
        counts[ind.kind] = counts.get(ind.kind, 0) + 1
    return {
        "ts": _utcnow_iso(),
        "count": len(vetted),
        "kinds": counts,
        # newest first for a screening layer that wants recent intel first
        "indicators": [i.to_dict() for i in reversed(vetted)],
    }


def match_hints(*, kinds: Optional[List[str]] = None, limit: int = 200) -> Dict[str, Any]:
    """Compile consumed intel into screening match hints: per-kind
    snippet phrases a screening layer can substring-match, plus counts.

    Recipe for the FRONT sibling: consult ``match_hints()["phrases"]``
    as an additional low-weight signal alongside the deterministic rule
    catalog — never as a verdict by itself (the feed is intel, not
    adjudication; I2)."""
    snap = screening_snapshot(kinds=kinds, limit=limit)
    phrases: List[str] = []
    seen = set()
    for ind in snap["indicators"]:
        s = ind["snippet"].strip().lower()
        if s and s not in seen:
            seen.add(s)
            phrases.append(ind["snippet"])
    return {
        "ts": snap["ts"],
        "count": snap["count"],
        "kinds": snap["kinds"],
        "phrases": phrases,
    }


def describe_posture() -> Dict[str, Any]:
    """Honest backend posture (cf. enforce.py L12)."""
    ok, bad = verify()
    return {
        "module": "levi.cybrus.threat_intel",
        "direction": "DemandPulse -> Cybrus (one-way intel, I2)",
        "laws": [lid for lid, _ in INTEL_LAWS],
        "kinds": list(INTEL_KINDS),
        "publish_scope": PUBLISH_SCOPE,
        "store": str(_store_path()),
        "chain_ok": ok,
        "first_bad_index": bad,
        "egress": "none — stdlib-only, zero network",
        "not": [
            "not a command channel: publishing grants no authority over Cybrus",
            "not adjudication: consumers decide; the feed only informs",
            "not tamper-proof: tamper-EVIDENT (hash chain); OS-level writes are outside the boundary",
        ],
    }
