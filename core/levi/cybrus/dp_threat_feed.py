"""Cybrus DP-THREAT-FEED — DemandPulse threat/scam signals become FRONT intel.

Direction: DemandPulse -> Cybrus (the reverse of demand_guard.py, which is
Cybrus guarding DemandPulse). When DemandPulse surfaces threat/scam
signals — "I got a phishing text pretending to be my bank", "fake invoice
email from ..." — this feed extracts screening intel from them (domain
roots, threat keywords, signal refs) and writes it to the FRONT intel
file. FRONT's rule R11 then scores future inbound messages against that
intel. Nothing here directs DemandPulse; nothing here screens messages.
Screening stays in front.py.

LAWS (binding — declared first, enforced below, machine-checked by
tests/test_cybrus_dp_threat_feed.py — honestly named invariant checks;
nothing here is formally proven):
  T1 Guard-crossed reads. The DemandPulse store is read ONLY through
     ``demand_guard.GuardedDemandStore`` with a validated
     ``demandpulse.read`` receipt (DG1). No raw file reads of the store,
     no bypass, no cached permission trusted twice.
  T2 Metadata-only intel. The intel file carries signal ids, kinds,
     matched keywords, and domain roots — never signal text, needs, or
     notes. Audit records carry digests and counts, never content.
  T3 Deterministic. The same store document yields a byte-identical
     intel file (sorted lists, canonical JSON). Refresh is idempotent.
  T4 Advisory only. Intel can only ADD to a FRONT score (rule R11);
     it can never subtract, never force CLEAN, never release quarantine.
  T5 Versioned + audited. Every refresh stamps round/ts/source digest;
     every refresh is audit-logged with metadata only.
  T6 No new egress. Stdlib-only, zero network. The feed never fetches,
     never sends, never reports upstream.

Stdlib-only, no network. Intel state under ``~/.levi/cybrus/``
(``LEVI_HOME`` override honored). Proof: tests/test_cybrus_dp_threat_feed.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Standalone-safe imports (same pattern as front.py / demand_guard.py)


def _cybrus_module(name: str):
    """Import a sibling cybrus module, with a standalone file fallback."""
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


def _demand_guard():
    return _cybrus_module("demand_guard")


def _audit_engine():
    return _cybrus_module("audit").AuditEngine()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Declared laws (machine-readable so tests pin every id)

LAWS = (
    ("T1", "DemandPulse store reads go through demand_guard with a validated demandpulse.read receipt; no bypass."),
    ("T2", "Intel file carries ids, kinds, matched keywords, domain roots — never signal text or notes."),
    ("T3", "Deterministic: same store document yields a byte-identical intel file; refresh is idempotent."),
    ("T4", "Advisory only: intel can only add to a FRONT score (R11), never subtract, never force CLEAN."),
    ("T5", "Every refresh stamps round/ts/source digest and is audit-logged with metadata only."),
    ("T6", "No new egress: stdlib-only, zero network."),
)

_INTEL_NAME = "front_intel.json"
_INTEL_FORMAT = "cybrus.front_intel/1"

# Threat phrasing that marks a demand signal as a threat/scam signal.
# Matched as case-insensitive substrings on normalized text. Deliberately
# narrow: these are words people use when REPORTING an attack, not words
# attackers use. Deterministic, stdlib-only.
THREAT_KEYWORDS = (
    "phishing",
    "phish",
    "smishing",
    "vishing",
    "scam",
    "scammer",
    "fraud",
    "fraudulent",
    "spoof",
    "spoofed",
    "impostor",
    "social engineering",
    "identity theft",
    "fake invoice",
    "fake text",
    "fake email",
    "malware",
    "ransomware",
    "hacked",
    "data breach",
    "don't click",
    "do not click",
    "suspicious text",
    "suspicious email",
    "suspicious link",
)

_DOMAIN_RE = re.compile(
    r"(?<![\w@-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}",
    re.IGNORECASE,
)


def _registrable(domain: str) -> str:
    labels = [t for t in (domain or "").lower().strip(".").split(".") if t]
    if len(labels) >= 2:
        return ".".join(labels[-2:])
    return ".".join(labels)


def _canonical(doc: Any) -> str:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _doc_digest(doc: Any) -> str:
    return hashlib.sha256(_canonical(doc).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Extraction (pure: store doc -> threat intel, no IO)


def extract_threat_signals(store_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract threat/scam signals from a DemandPulse store document.

    Pure function (T3): no IO, no guard, deterministic. Returns one entry
    per signal whose ``need`` text matches THREAT_KEYWORDS, carrying only
    metadata (T2): id, kind, matched keywords, domain roots mentioned in
    the text. Signal text itself is never copied out.
    """
    out: List[Dict[str, Any]] = []
    signals = store_doc.get("signals") or []
    if not isinstance(signals, list):
        return out
    for sig in signals:
        if not isinstance(sig, dict):
            continue
        need = str(sig.get("need") or "")
        norm = need.lower()
        matched = sorted({kw for kw in THREAT_KEYWORDS if kw in norm})
        if not matched:
            continue
        domains = sorted(
            {_registrable(m.group(0)) for m in _DOMAIN_RE.finditer(need)}
        )
        out.append(
            {
                "id": str(sig.get("id") or ""),
                "kind": str(sig.get("kind") or ""),
                "matched": matched,
                "domains": domains,
            }
        )
    out.sort(key=lambda e: e["id"])
    return out


def build_intel(store_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Build the deterministic intel document for a store snapshot (T3).

    Byte-identical for the same store document: no wall-clock fields in
    the file. ``round`` comes from the store's own ``updated_at`` stamp
    (falling back to the source digest), so re-running a refresh without
    store changes is a byte-identical no-op.
    """
    threats = extract_threat_signals(store_doc)
    domains = sorted({d for t in threats for d in t["domains"] if d})
    keywords = sorted({k for t in threats for k in t["matched"] if k})
    return {
        "format": _INTEL_FORMAT,
        "round": str(store_doc.get("updated_at") or _doc_digest(store_doc)[:16]),
        "source_digest": _doc_digest(store_doc),
        "signal_count": len(store_doc.get("signals") or []),
        "threat_signal_count": len(threats),
        "threat_signals": threats,
        "domains": domains,
        "keywords": keywords,
    }


# ---------------------------------------------------------------------------
# Intel store


def _intel_path(explicit: Optional[Path] = None) -> Path:
    if explicit is not None:
        return Path(explicit)
    return _paths().cybrus_dir() / _INTEL_NAME


def load_intel(intel_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the FRONT intel file. NEVER raises: missing/corrupt -> {}.

    FRONT calls this on every screened message; a broken intel file must
    degrade to "no intel" rather than break screening (fail-open on the
    ADVISORY input only — the screen itself still fails closed per F5).
    """
    try:
        p = _intel_path(intel_path)
        raw = p.read_text(encoding="utf-8")
        doc = json.loads(raw)
        if not isinstance(doc, dict) or doc.get("format") != _INTEL_FORMAT:
            return {}
        return doc
    except Exception:
        return {}


def _write_intel(doc: Dict[str, Any], intel_path: Optional[Path] = None) -> Path:
    """Write the intel file atomically-ish: 0600, fsync, metadata only."""
    p = _intel_path(intel_path)
    blob = (_canonical(doc) + "\n").encode("utf-8")
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, blob)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(p, 0o600)
    return p


# ---------------------------------------------------------------------------
# Refresh — the guarded pipeline (T1/T5)


def refresh_intel(
    credential: Optional[str],
    *,
    store_path: Optional[Path] = None,
    intel_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Refresh FRONT threat intel from the DemandPulse store.

    ``credential`` is a Cybrus grant receipt (api token) carrying
    ``demandpulse.read``. Without a valid receipt the guard refuses and
    this raises ``demand_guard.DemandGuardError`` — fail closed (T1).
    Returns a metadata-only summary (T2).
    """
    dg = _demand_guard()
    store = dg.GuardedDemandStore(path=store_path) if store_path else dg.GuardedDemandStore()
    handle = store.authorize(credential, dg.SCOPE_READ)  # T1: guard-crossed read
    doc = handle.read()
    intel = build_intel(doc)
    p = _write_intel(intel, intel_path)
    summary = {
        "ts": _utcnow_iso(),
        "round": intel["round"],
        "source_digest": intel["source_digest"][:16],
        "signals_scanned": intel["signal_count"],
        "threat_signals": intel["threat_signal_count"],
        "domains": list(intel["domains"]),
        "keywords": list(intel["keywords"]),
        "intel_path": str(p),
    }
    try:
        _audit_engine().append(
            "cybrus.dp_threat_feed.refresh",
            "cybrus-dp-threat-feed",
            {
                "source_digest": summary["source_digest"],
                "signals_scanned": summary["signals_scanned"],
                "threat_signals": summary["threat_signals"],
                "domains": summary["domains"],
                "keywords": summary["keywords"],
            },
        )
    except Exception:
        pass  # T5: audit is best-effort; the intel file is already written
    return summary


def describe_posture() -> Dict[str, Any]:
    """Honest backend posture (cf. front.describe_posture, L12-style)."""
    intel = load_intel()
    return {
        "module": "levi.cybrus.dp_threat_feed",
        "direction": "DemandPulse -> Cybrus (intel feed)",
        "laws": [lid for lid, _ in LAWS],
        "egress": "none — stdlib-only, zero network",
        "reads": "through demand_guard.GuardedDemandStore with a demandpulse.read grant receipt (T1)",
        "intel": {
            "path": str(_intel_path()),
            "present": bool(intel),
            "round": intel.get("round") if intel else None,
            "source_digest": (intel.get("source_digest") or "")[:16] if intel else None,
            "threat_signals": intel.get("threat_signal_count", 0) if intel else 0,
            "domains": len(intel.get("domains", [])) if intel else 0,
            "keywords": len(intel.get("keywords", [])) if intel else 0,
        },
        "consumer": "front.py rule R11 (advisory: adds score only, T4)",
    }
