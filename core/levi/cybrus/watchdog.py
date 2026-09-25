"""Cybrus QUETTA-PAN WATCHDOG — Chauncey's four-direction monitor, inside Cybrus.

A watchdog is a monitor that barks on anomaly and holds receipts. This one
watches Cybrus's four directions on a poll (never a persistent daemon —
``sweep()`` is one pass; the host schedules it):

  FRONT inbound   phishing/scam screening stream anomalies (flag spikes,
                  screening-error storms, quarantine bypass/release velocity)
  BACK  archives  backup-integrity anomalies (manifest failures, missing
                  expected archives, unrecorded archives on disk)
  LEFT  devices   device-trust anomalies (untrusted/unknown devices present,
                  revoked devices reappearing)
  RIGHT money     silent-movement detection + approval-pattern anomalies
                  (refused grants, movement without receipt, approval velocity)

QUETTA-PAN MEANING (A): this watchdog borrows the Quetta-Pan meaning (A)
framing only — the quetta-scale all-form matrix as *eyes over every
direction*, because total visibility is the job. It invents NO new
Quetta-Pan mechanics (no qid machinery, no matrix machinery) and does not
touch meaning (B), the Quetta-Pan Studio prototype. Which meaning governs
the name is Chauncey's ruling to make; until then the watchdog answers
entirely to Cybrus law.

WATCHDOG LAWS (binding — declared first, enforced below, machine-checked
by tests/test_cybrus_watchdog.py; honestly named invariant checks):
  W1 (L1/L4)  Every bark lands in the hash-chained AuditEngine as
              ``cybrus.watchdog.bark``: metadata only — direction, signal,
              severity, evidence hash, timestamp — never payloads.
  W2 (L1/L3)  FAIL CLOSED: a check that cannot read its source barks
              ``blind`` (loss of visibility is itself an anomaly). A check
              never goes silent.
  W3 (L9)     Read-only toward sibling state: the watchdog appends only
              to the audit trail. It never writes another organ's stores,
              releases nothing, enrolls nothing, moves nothing.
  W4 (L10)    No new state channels: dedup runs by reading prior
              ``cybrus.watchdog.bark`` records from the audit log itself.
              The watchdog keeps no side-channel stores.
  W5 (L6)     Every bark names its remedy (keeper's law / anticipation).
  W6 (L12)    Honest posture: :func:`describe_posture` reports what the
              watchdog sees and, explicitly, what it does not.

Stdlib-only, no network. State is the audit trail itself
(``~/.levi/cybrus/audit.jsonl``; ``LEVI_HOME`` override honored).

Proof: tests/test_cybrus_watchdog.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Standalone-safe imports (same pattern as enforce.py / front.py)


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


def _audit_engine():
    return _cybrus_module("audit").AuditEngine()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


def _parse_ts(ts: Any) -> Optional[datetime]:
    if not ts or not isinstance(ts, str):
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _evidence_hash(evidence: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(evidence).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Declared laws (W6: machine-readable so tests pin every id)


LAWS = (
    ("W1", "Every bark lands in the hash-chained AuditEngine as cybrus.watchdog.bark (metadata only)."),
    ("W2", "Fail closed: an unreadable check source barks 'blind' — never silence."),
    ("W3", "Read-only toward sibling state: only the audit trail is appended."),
    ("W4", "No new state channels: dedup reads prior watchdog barks from the audit log."),
    ("W5", "Every bark names its remedy."),
    ("W6", "Honest posture: describe_posture reports what is seen and what is not."),
)

#: The four directions of Chauncey's mandate.
DIRECTIONS = ("front", "back", "left", "right")

WATCHDOG_ACTOR = "cybrus-watchdog"
BARK_EVENT = "cybrus.watchdog.bark"

# --- poll windows -----------------------------------------------------------
#: Recent window every check scans for fresh anomalies.
WINDOW_HOURS = 1
#: Baseline window for spike detection (prior hours before the recent window).
BASELINE_HOURS = 23

# --- thresholds (module constants, pinned so tests can reference them) ------
FRONT_SPIKE_ABSOLUTE_MIN = 5   #: min quarantines/hour to bark even at zero baseline
FRONT_SPIKE_MULTIPLIER = 5.0   #: recent must be >= this x the median hourly baseline
FRONT_ERROR_STORM = 3          #: R99 screening errors/hour before "screening outage"
FRONT_RELEASE_VELOCITY = 4     #: quarantine releases/hour before "release velocity"
LEFT_UNTRUSTED_GRACE_MIN = 0   #: untrusted devices bark immediately (fail closed)
RIGHT_REFUSAL_WINDOW = 1       #: money grant refusals barked per event in window (h)
RIGHT_APPROVAL_VELOCITY = 10   #: decided approvals/hour before "approval velocity"
RIGHT_DENIAL_SPIKE = 3         #: denied approvals/hour before "denial spike"

#: Audit records scanned per sweep (tail window for event history).
AUDIT_TAIL = 5000
#: Audit records scanned for bark dedup.
DEDUP_TAIL = 1000


class BlindCheck(Exception):
    """A check could not read its source. Raised inside a check; the
    sweep converts it into a ``blind`` bark (W2) — never into silence."""


# ---------------------------------------------------------------------------
# Barking (W1: through the audit trail; W5: every bark names its remedy)


def _already_barked(direction: str, signal: str, evidence_hash: str) -> bool:
    """Dedup against the audit log itself (W4): has this exact
    direction+signal+evidence_hash already been barked?"""
    try:
        records = _audit_engine().tail(DEDUP_TAIL)
    except Exception:
        return False  # fail closed: bark again rather than assume it was logged
    for rec in records:
        if rec.get("event") != BARK_EVENT:
            continue
        details = rec.get("details") or {}
        if (
            details.get("direction") == direction
            and details.get("signal") == signal
            and details.get("evidence_hash") == evidence_hash
        ):
            return True
    return False


def bark(direction: str, signal: str, evidence: Dict[str, Any],
         severity: str, remedy: str) -> Dict[str, Any]:
    """Bark one anomaly through the hash-chained audit trail (W1).

    Returns the receipt (direction, signal, severity, evidence hash,
    timestamp, audit seq/hash). ``deduped=True`` when the identical bark
    is already on the trail (W4) — no double entry.
    """
    if direction not in DIRECTIONS:
        raise ValueError(f"unknown direction {direction!r}")
    eh = _evidence_hash(evidence)
    details = {
        "direction": direction,
        "signal": signal,
        "severity": severity,
        "evidence_hash": eh,
        "remedy": remedy,
    }
    if _already_barked(direction, signal, eh):
        return {
            "direction": direction,
            "signal": signal,
            "severity": severity,
            "evidence_hash": eh,
            "ts": _utcnow_iso(),
            "deduped": True,
            "audit_seq": None,
            "audit_hash": None,
        }
    record = _audit_engine().append(BARK_EVENT, WATCHDOG_ACTOR, details)
    return {
        "direction": direction,
        "signal": signal,
        "severity": severity,
        "evidence_hash": eh,
        "ts": record["ts"],
        "deduped": False,
        "audit_seq": record["seq"],
        "audit_hash": record["hash"],
    }


def bark_blind(direction: str, source: str, error: str) -> Dict[str, Any]:
    """The W2 bark: loss of visibility is itself an anomaly."""
    return bark(
        direction,
        "blind",
        {"source": source, "error": error},
        "high",
        f"restore visibility on {source}: fix the unreadable source, then re-run "
        "the watchdog sweep ('levi cybrus watchdog sweep') and confirm the bark "
        "trail resumes",
    )


def recent_barks(n: int = 20) -> List[Dict[str, Any]]:
    """The last *n* watchdog bark records, oldest first."""
    try:
        records = _audit_engine().tail(AUDIT_TAIL)
    except Exception:
        return []
    barks = [r for r in records if r.get("event") == BARK_EVENT]
    return barks[-n:]


# ---------------------------------------------------------------------------
# Source readers (each check's only inputs — W3 read-only)


def _screen_events(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in records if r.get("event") == "cybrus.front.screen"]


def _events_since(records: List[Dict[str, Any]], event: str,
                  hours: float) -> List[Dict[str, Any]]:
    cutoff = _utcnow() - timedelta(hours=hours)
    out = []
    for r in records:
        if r.get("event") != event:
            continue
        ts = _parse_ts(r.get("ts"))
        if ts is not None and ts >= cutoff:
            out.append(r)
    return out


def _hourly_buckets(events: List[Dict[str, Any]],
                     since: datetime) -> List[int]:
    """Count of events per hour from *since* to now (whole hours)."""
    hours = max(1, int((_utcnow() - since).total_seconds() // 3600))
    buckets = [0] * hours
    for e in events:
        ts = _parse_ts(e.get("ts"))
        if ts is None:
            continue
        idx = int((ts - since).total_seconds() // 3600)
        if 0 <= idx < hours:
            buckets[idx] += 1
    return buckets


def _median(values: List[int]) -> float:
    vals = sorted(values)
    n = len(vals)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2:
        return float(vals[mid])
    return (vals[mid - 1] + vals[mid]) / 2.0


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read a JSONL store. Raises OSError when unreadable (blind, W2)."""
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


# ---------------------------------------------------------------------------
# FRONT: inbound screening stream


def _check_front(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    front_mod = _cybrus_module("front")
    screens = _screen_events(records)
    quarantines = [
        e for e in screens
        if (e.get("details") or {}).get("verdict") == "QUARANTINE"
    ]

    # 1) flag spike: recent quarantines vs median hourly baseline
    baseline_start = _utcnow() - timedelta(hours=WINDOW_HOURS + BASELINE_HOURS)
    base_quar = [
        e for e in quarantines
        if (_parse_ts(e.get("ts")) or _utcnow()) < _utcnow() - timedelta(hours=WINDOW_HOURS)
    ]
    recent = _events_since(quarantines, "cybrus.front.screen", WINDOW_HOURS)
    buckets = _hourly_buckets(base_quar, baseline_start)
    baseline = _median(buckets)
    if len(recent) >= max(FRONT_SPIKE_ABSOLUTE_MIN, baseline * FRONT_SPIKE_MULTIPLIER):
        out.append(bark(
            "front", "flag_spike",
            {"quarantines_last_hour": len(recent),
             "baseline_median_per_hour": baseline},
            "high",
            "inspect the quarantine ('levi cybrus front quarantine' path "
            "via the front module): a flag spike means the stream changed or "
            "the screeners misfire — clear quarantines only via Chauncey's "
            "F6 release",
        ))

    # 2) screening-error storm: R99 receipts mean the screener itself is sick
    errors = [
        e for e in recent
        if "R99" in ((e.get("details") or {}).get("rules") or [])
    ]
    if len(errors) >= FRONT_ERROR_STORM:
        out.append(bark(
            "front", "screening_errors",
            {"r99_last_hour": len(errors)},
            "high",
            "screening is failing closed (R99): check front.py parser inputs "
            "and the quarantine store health; unscreened traffic must not be "
            "assumed clean",
        ))

    # 3) quarantine bypass: a release for an item never quarantined
    try:
        releases_path = _paths().cybrus_dir() / "front_releases.jsonl"
        release_records = _read_jsonl(releases_path) if releases_path.exists() else []
        quarantined_refs = {r.get("msg_ref") for r in front_mod.quarantine_list()}
        for rec in release_records:
            ref = rec.get("msg_ref")
            if ref and ref not in quarantined_refs:
                out.append(bark(
                    "front", "quarantine_bypass",
                    {"msg_ref": ref[:16] + "…" if len(str(ref)) > 16 else ref,
                     "released_by": rec.get("released_by")},
                    "high",
                    "treat the released item as hostile: it left quarantine "
                    "without a quarantine record — only Chauncey's F6 release "
                    "moves items out; investigate and re-quarantine",
                ))
        # 4) release velocity
        recent_releases = [
            r for r in release_records
            if (_parse_ts(r.get("ts")) or _utcnow()) >= _utcnow() - timedelta(hours=WINDOW_HOURS)
        ]
        if len(recent_releases) >= FRONT_RELEASE_VELOCITY:
            out.append(bark(
                "front", "release_velocity",
                {"releases_last_hour": len(recent_releases)},
                "medium",
                "confirm with Chauncey that each release was his deliberate "
                "F6 action; bulk releases outside his hand are the anomaly",
            ))
    except OSError as exc:
        raise BlindCheck(f"front release/quarantine stores unreadable: {exc}") from exc

    return out


# ---------------------------------------------------------------------------
# BACK: backup integrity


def _check_back(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    del records  # BACK reads the manifest, not the audit trail
    manifest_mod = _cybrus_module("backup_manifest")
    try:
        manifest = manifest_mod.ManifestEngine()
    except Exception as exc:
        raise BlindCheck(f"backup manifest unavailable: {exc}") from exc
    try:
        report = manifest.verify(rehash_archives=True)
    except Exception as exc:
        raise BlindCheck(f"backup manifest verify failed to run: {exc}") from exc
    if not report.get("ok"):
        failures = report.get("failures") or []
        by_reason: Dict[str, List[int]] = {}
        for f in failures:
            by_reason.setdefault(str(f.get("reason", "unknown")), []).append(f.get("seq"))
        out.append(bark(
            "back", "backup_manifest_failure",
            {"failures": len(failures), "by_reason": {k: len(v) for k, v in by_reason.items()},
             "tip": report.get("tip")},
            "high",
            "archives or the manifest changed under us: treat the tip as "
            "suspect, re-run 'backup-manifest verify', restore from a known-"
            "good archive, and never delete the failing entries — L10, the "
            "chain only ever grows",
        ))
    try:
        unrecorded = manifest.status().get("unrecorded_archives") or []
    except Exception as exc:
        raise BlindCheck(f"backup manifest status unreadable: {exc}") from exc
    if unrecorded:
        out.append(bark(
            "back", "unrecorded_archives",
            {"count": len(unrecorded), "names": unrecorded[:10]},
            "medium",
            "archives exist on disk that the manifest never recorded: record "
            "them with the manifest or remove them — unrecorded archives are "
            "untracked state, the thing the manifest exists to prevent",
        ))
    return out


# ---------------------------------------------------------------------------
# LEFT: device trust


def _check_left(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    devices_mod = _cybrus_module("devices")
    try:
        registry = devices_mod.DeviceTrust()
        devices = registry.list_public()
    except Exception as exc:
        raise BlindCheck(f"device trust registry unreadable: {exc}") from exc

    # 1) unknown/untrusted devices present — every one is an alert candidate
    for dev in devices:
        if dev.get("trust") == "untrusted":
            out.append(bark(
                "left", "unknown_device",
                {"device_id": dev.get("id"), "name": dev.get("name"),
                 "first_seen": dev.get("first_seen"),
                 "fingerprint_bound": dev.get("fingerprint_bound")},
                "high",
                "identify the device: if it is not one of Chauncey's, keep it "
                "untrusted (it cannot execute privileged calls) and revoke it "
                "'levi cybrus device revoke'; if it is his, raise a trust "
                "grant ('levi cybrus device request')",
            ))

    # 2) revoked device reappearing: revoked, then sighted again later
    revoked_ts: Dict[str, datetime] = {}
    for r in records:
        if r.get("event") != "device.revoked":
            continue
        ts = _parse_ts(r.get("ts"))
        did = (r.get("details") or {}).get("device_id")
        if ts and did:
            revoked_ts[did] = ts
    if revoked_ts:
        for r in records:
            if r.get("event") not in ("device.sighted",):
                continue
            ts = _parse_ts(r.get("ts"))
            did = (r.get("details") or {}).get("device_id")
            if ts and did and did in revoked_ts and ts > revoked_ts[did]:
                out.append(bark(
                    "left", "revoked_device_reappeared",
                    {"device_id": did},
                    "high",
                    "a revoked device presented itself again: do NOT re-trust "
                    "it on sight — challenge it ('levi cybrus device challenge') "
                    "and find out how it came back",
                ))
    return out


# ---------------------------------------------------------------------------
# RIGHT: money + approvals


def _read_money_audit() -> List[Dict[str, Any]]:
    """Read the money-gateway audit log. Raises BlindCheck when the file
    exists but is unreadable; returns [] when it never existed (no
    movements yet — not blindness)."""
    base = os.environ.get("LEVI_CYBRUS_DIR", "").strip()
    data_dir = Path(base) / "money" if base else Path.home() / ".levi" / "cybrus" / "money"
    path = data_dir / "money_audit.jsonl"
    if not path.exists():
        return []
    try:
        return _read_jsonl(path)
    except OSError as exc:
        raise BlindCheck(f"money audit log unreadable: {exc}") from exc


def _check_right(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    # 1) silent-movement violations: attempts outside the gateway
    for r in _events_since(records, "right.violation", WINDOW_HOURS):
        details = r.get("details") or {}
        out.append(bark(
            "right", "silent_movement",
            {"actor": details.get("actor"), "action": details.get("action"),
             "audit_ref": r.get("seq")},
            "high",
            "silent movement was DENIED and logged — confirm the actor did "
            "not find another path, and route the action through the gateway "
            "with a proper approval if it was legitimate",
        ))

    # 2) money-grant anomalies from the money audit log
    money_records = _read_money_audit()
    cutoff = _utcnow() - timedelta(hours=RIGHT_REFUSAL_WINDOW)
    for rec in money_records:
        ts = _parse_ts(rec.get("ts"))
        if ts is None or ts < cutoff:
            continue
        event = rec.get("event")
        if event in ("authorize_refused", "execute_refused"):
            out.append(bark(
                "right", "money_grant_refusal",
                {"event": event, "plan_id": rec.get("plan_id"),
                 "reason": rec.get("reason")},
                "high",
                "a money grant was refused — inspect the reason (replay, "
                "double spend, no receipt); if the refusal was wrong, issue a "
                "fresh approval rather than forcing the old one through",
            ))
        elif event == "rail_suspended":
            out.append(bark(
                "right", "rail_suspended",
                {"name": rec.get("name"), "by": rec.get("by")},
                "medium",
                "a money rail was suspended: confirm the suspension was "
                "deliberate and that no movements are queued against it",
            ))

    # 3) movements without receipts: executed with no approval receipt on the
    #    Cybrus audit trail — exactly what the sentry exists to catch
    executed = [r for r in money_records if r.get("event") == "executed"]
    if executed:
        receipted_plans = {
            (r.get("details") or {}).get("plan_id")
            for r in records
            if r.get("event") == "money.approval_receipt"
        }
        for rec in executed:
            pid = rec.get("plan_id")
            if pid and pid not in receipted_plans:
                out.append(bark(
                    "right", "movement_without_receipt",
                    {"plan_id": pid},
                    "high",
                    "a money movement executed with no approval receipt on "
                    "the Cybrus trail: treat it as silent movement until "
                    "proven otherwise — do not re-execute, investigate",
                ))

    # 4) approval-pattern anomalies from the approval ledger
    try:
        approval_mod = _cybrus_module("approval")
        entries = approval_mod.ApprovalEngine().list_all()
    except Exception as exc:
        raise BlindCheck(f"approval ledger unreadable: {exc}") from exc
    cutoff = _utcnow() - timedelta(hours=WINDOW_HOURS)
    decided = [
        e for e in entries
        if (_parse_ts(e.get("decided_at")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
        and e.get("status") in ("approved", "denied")
    ]
    denied = [e for e in decided if e.get("status") == "denied"]
    if len(decided) >= RIGHT_APPROVAL_VELOCITY:
        out.append(bark(
            "right", "approval_velocity",
            {"decided_last_hour": len(decided),
             "actions": sorted({str(e.get("action")) for e in decided})},
            "medium",
            "approval decisions are arriving far faster than Chauncey's human "
            "pace: verify each was his hand, and look for automation pressing "
            "the gate",
        ))
    if len(denied) >= RIGHT_DENIAL_SPIKE:
        out.append(bark(
            "right", "approval_denial_spike",
            {"denied_last_hour": len(denied)},
            "medium",
            "a burst of denials is itself a signal — either pressure on the "
            "gate or a broken requester; read the denial reasons before "
            "re-requesting",
        ))
    return out


# ---------------------------------------------------------------------------
# The sweep


_CHECKS = (
    ("front", _check_front),
    ("back", _check_back),
    ("left", _check_left),
    ("right", _check_right),
)


class Watchdog:
    """One watchdog: poll pass over the four directions, barking through
    the audit trail. Stateless (W4) — history lives in the audit log."""

    def __init__(self, audit_tail: int = AUDIT_TAIL) -> None:
        self._audit_tail = audit_tail

    def _records(self) -> List[Dict[str, Any]]:
        try:
            return _audit_engine().tail(self._audit_tail)
        except Exception as exc:
            raise BlindCheck(f"audit trail unreadable: {exc}") from exc

    def sweep(self) -> Dict[str, Any]:
        """Run every direction's checks once. Returns a receipt:

        {ts, directions: {front/back/left/right: {status, signals}},
         barks: [bark receipts], bark_count, blind_count}
        """
        receipts: List[Dict[str, Any]] = []
        directions: Dict[str, Dict[str, Any]] = {}
        try:
            records = self._records()
        except BlindCheck as exc:
            # The trail itself is gone: bark blind for every direction, loudly.
            for direction, _ in _CHECKS:
                receipts.append(bark_blind(direction, "audit.jsonl", str(exc)))
                directions[direction] = {"status": "blind", "signals": ["blind"]}
            return self._receipt(directions, receipts)
        for direction, check in _CHECKS:
            try:
                barks = check(records)
            except BlindCheck as exc:
                barks = [bark_blind(direction, str(exc), "unreadable source")]
            directions[direction] = {
                "status": "blind" if any(b["signal"] == "blind" for b in barks)
                else ("anomaly" if barks else "ok"),
                "signals": [b["signal"] for b in barks],
            }
            receipts.extend(barks)
        return self._receipt(directions, receipts)

    def _receipt(self, directions: Dict[str, Dict[str, Any]],
                 barks: List[Dict[str, Any]]) -> Dict[str, Any]:
        blind = sum(1 for b in barks if b.get("signal") == "blind")
        return {
            "ts": _utcnow_iso(),
            "watchdog": "cybrus.quettapan-watchdog",
            "directions": directions,
            "barks": barks,
            "bark_count": len(barks),
            "blind_count": blind,
            "laws": [lid for lid, _ in LAWS],
        }

    def watch(self, interval_seconds: float = 300.0,
              stop_after: Optional[int] = None) -> None:
        """Foreground poll loop: sweep every *interval_seconds*.

        No daemon persistence — this loop dies with the process. Long-term
        scheduling belongs to the host (cron/systemd/LEVI daemon).
        ``stop_after`` bounds the run for tests.
        """
        if interval_seconds <= 0:
            raise ValueError("interval must be positive")
        sweeps = 0
        while True:
            self.sweep()
            sweeps += 1
            if stop_after is not None and sweeps >= stop_after:
                return
            time.sleep(interval_seconds)


def sweep() -> Dict[str, Any]:
    """One watchdog pass. Entry point for schedulers and the CLI."""
    return Watchdog().sweep()


def describe_posture() -> Dict[str, Any]:
    """Honest backend posture (W6 / L12)."""
    return {
        "organism": "levi",
        "organ": "levi.cybrus.watchdog",
        "role": "Quetta-Pan watchdog, inside Cybrus: poll monitor barking "
                "anomalies on the four directions through the audit trail",
        "directions": list(DIRECTIONS),
        "writes": ["audit.jsonl (barks only)"],
        "reads": [
            "audit.jsonl (screen/release/violation/grant events)",
            "front_quarantine.jsonl + front_releases.jsonl",
            "backup-manifest.jsonl + backup archives (verify only)",
            "device trust registry (read-only list)",
            "money/money_audit.jsonl + approval ledger (read-only)",
        ],
        "does_not": [
            "invent Quetta-Pan mechanics (meaning A framing only: total visibility)",
            "release quarantines, enroll devices, move money, or write sibling stores",
            "daemonize or persist its own state (history lives in the audit log)",
            "watch backguard.py's per-directory egress manifests "
            "(sibling-owned, out of this watchdog's scope until Chauncey says otherwise)",
        ],
        "network": "none — stdlib only; no egress, no sockets",
        "laws": [lid for lid, _ in LAWS],
        "cybrus_laws_binding": [f"L{i}" for i in range(1, 13)],
    }
