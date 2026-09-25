"""DemandPulse autonomous upgrade authority.

Canon (Chauncey, 2026-09-17): DemandPulse may AUTOMATICALLY execute
upgrades/changes when it senses time-sensitivity.

  MINOR     — reversible, low-risk (config tweaks, small patches): full auto.
  MID       — bounded (dependency upgrades, module improvements): auto, but
              every action carries a full audit trail + receipt.
  MAJOR     — architecture changes, irreversible acts, security, founder-level:
              NEVER auto. Escalates to Chauncey; the framework executes nothing.

Time-sensitivity is the trigger: without a live sensed signal, no autonomous
action runs at all. The six-gate chain (Plan -> Preview -> Permission -> Execute
-> Verify -> Receipt) governs consequential acts — recorded per action. Global
posture: high deterministic ambition (aggressive, ambitious methods; never
violent, never manipulative) — recorded on every receipt.

Safety by construction:
  - Major-tier actions are structurally unexecutable: the framework has NO code
    path that invokes an executor for a major action (even if one is passed).
  - Ambiguous classification fails closed: unknown kinds classify as MAJOR.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


HOME = Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
AUDIT_PATH = HOME / "demand" / "authority-audit.jsonl"
ESCALATION_PATH = HOME / "demand" / "escalations.jsonl"
APPLIED_CONFIG = HOME / "demand" / "applied-config.json"

TIER_MINOR = "minor"
TIER_MID = "mid"
TIER_MAJOR = "major"
TIERS = (TIER_MINOR, TIER_MID, TIER_MAJOR)

POSTURE = "high-deterministic-ambition"
AUTHORITY_GRANT = "standing grant — Chauncey, 2026-09-17"

# Kinds with known classification. Anything not listed here classifies MAJOR.
MINOR_KINDS = frozenset(
    {
        "config-tweak",
        "small-patch",
        "text-update",
        "cache-clear",
        "log-rotate",
    }
)
MID_KINDS = frozenset(
    {
        "dependency-upgrade",
        "module-improvement",
        "config-schema",
        "index-rebuild",
    }
)
MAJOR_KINDS = frozenset(
    {
        "architecture",
        "irreversible",
        "security",
        "founder",
        "data-destruction",
        "credential",
        "network-egress",
        "identity",
        "policy",
    }
)

MIN_CONFIDENCE = 0.5  # signal must clear this to count as a trigger


class AuthorityRefused(Exception):
    """Raised when the framework refuses an autonomous action."""


def classify_action(
    kind: str,
    *,
    irreversible: bool = False,
    security_sensitive: bool = False,
    founder_level: bool = False,
    scope: str = "local",
) -> str:
    """Classify an action into minor / mid / major. Fails closed.

    Any uncertainty — unknown kind, irreversible, security-sensitive,
    founder-level, non-local scope — lands at MAJOR (escalate, never auto).
    """
    if not isinstance(kind, str) or not kind.strip():
        return TIER_MAJOR
    kind = kind.strip().lower()
    if founder_level or security_sensitive or irreversible:
        return TIER_MAJOR
    if scope not in ("local",):
        return TIER_MAJOR
    if kind in MAJOR_KINDS:
        return TIER_MAJOR
    if kind in MID_KINDS:
        return TIER_MID
    if kind in MINOR_KINDS:
        return TIER_MINOR
    # Unknown kind: fail closed.
    return TIER_MAJOR


@dataclass
class SensedSignal:
    """A time-sensitivity signal DemandPulse sensed. The trigger condition."""

    id: str
    source: str
    evidence: str
    confidence: float = 0.5
    sensed_at: str = field(default_factory=lambda: _utcnow())
    ttl_seconds: int = 3600

    def __post_init__(self) -> None:
        if not self.id or not self.source:
            raise ValueError("signal id and source are required")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not math.isfinite(self.confidence)
            or not 0.0 <= self.confidence <= 1.0
        ):
            raise ValueError(f"confidence must be in [0,1], got {self.confidence!r}")

    def is_live(self, now: Optional[datetime] = None) -> bool:
        if self.confidence < MIN_CONFIDENCE:
            return False
        now = now or datetime.now(timezone.utc)
        try:
            sensed = datetime.fromisoformat(self.sensed_at)
        except ValueError:
            return False
        return now <= sensed + timedelta(seconds=self.ttl_seconds)


@dataclass
class Action:
    id: str
    kind: str
    target: str
    description: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    proposed_at: str = field(default_factory=lambda: _utcnow())


@dataclass
class Receipt:
    id: str
    action_id: str
    tier: str
    signal_id: str
    outcome: str  # executed | escalated | refused
    gates: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    posture: str = POSTURE
    finished_at: str = field(default_factory=lambda: _utcnow())


@dataclass
class Escalation:
    id: str
    action_id: str
    kind: str
    target: str
    tier: str
    signal_id: str
    reason: str
    status: str = "open"  # open | resolved
    created_at: str = field(default_factory=lambda: _utcnow())
    resolved_at: Optional[str] = None
    resolution: str = ""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


# --- Executor registry -------------------------------------------------------
# Executors run ONLY for minor and mid tiers. There is deliberately no way to
# register (or invoke) an executor for a major action.

_Executors: Dict[str, Callable[[Action], Dict[str, Any]]] = {}


def register_executor(kind: str, fn: Callable[[Action], Dict[str, Any]]) -> None:
    """Register an executor for a minor or mid kind. Majors are refused."""
    if classify_action(kind) == TIER_MAJOR:
        raise AuthorityRefused(
            f"cannot register an executor for major-tier kind {kind!r}: "
            "major actions are structurally unexecutable"
        )
    _Executors[kind.strip().lower()] = fn


def _builtin_config_tweak(action: Action) -> Dict[str, Any]:
    """Demo executor: applies a config key=value under the authority sandbox."""
    key = action.params.get("key")
    if not key:
        return {"ok": False, "error": "config-tweak requires params.key"}
    APPLIED_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    store: Dict[str, Any] = {}
    if APPLIED_CONFIG.exists():
        try:
            store = json.loads(APPLIED_CONFIG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            store = {}
    store[str(key)] = action.params.get("value")
    APPLIED_CONFIG.write_text(json.dumps(store, indent=2), encoding="utf-8")
    return {"ok": True, "applied": {str(key): action.params.get("value")}}


def _builtin_dry_note(action: Action) -> Dict[str, Any]:
    """Demo executor for patch-like kinds: records intent, changes nothing real."""
    return {
        "ok": True,
        "note": "recorded as advisory; no real change applied by the demo executor",
        "kind": action.kind,
        "target": action.target,
    }


for _kind in MINOR_KINDS:
    _Executors[_kind] = _builtin_config_tweak if _kind == "config-tweak" else _builtin_dry_note
for _kind in MID_KINDS:
    _Executors[_kind] = _builtin_dry_note


# --- Engine ------------------------------------------------------------------


class AuthorityEngine:
    """DemandPulse's autonomous authority: sense, classify, act or escalate."""

    def __init__(
        self,
        audit_path: Path = AUDIT_PATH,
        escalation_path: Path = ESCALATION_PATH,
        signal_path: Optional[Path] = None,
    ) -> None:
        self.audit_path = audit_path
        self.escalation_path = escalation_path
        self.signal_path = signal_path or (audit_path.parent / "signals.jsonl")
        self._signals: Dict[str, SensedSignal] = {}
        self._load_signals()

    def _load_signals(self) -> None:
        for rec in _read_jsonl(self.signal_path):
            try:
                sig = SensedSignal(**{k: rec[k] for k in (
                    "id", "source", "evidence", "confidence", "sensed_at", "ttl_seconds"
                ) if k in rec})
            except (TypeError, ValueError):
                continue
            if sig.is_live():
                self._signals[sig.id] = sig

    # -- sensing -----------------------------------------------------------
    def sense(
        self,
        source: str,
        evidence: str,
        confidence: float = 0.6,
        ttl_seconds: int = 3600,
    ) -> SensedSignal:
        signal = SensedSignal(
            id=f"sig-{uuid.uuid4().hex[:12]}",
            source=source,
            evidence=evidence,
            confidence=confidence,
            ttl_seconds=ttl_seconds,
        )
        self._signals[signal.id] = signal
        _append_jsonl(self.signal_path, asdict(signal))
        return signal

    def live_signal(self, signal_id: str) -> Optional[SensedSignal]:
        sig = self._signals.get(signal_id)
        return sig if sig and sig.is_live() else None

    # -- classification ----------------------------------------------------
    def classify(self, action: Action) -> str:
        return classify_action(
            action.kind,
            irreversible=bool(action.params.get("irreversible", False)),
            security_sensitive=bool(action.params.get("security_sensitive", False)),
            founder_level=bool(action.params.get("founder_level", False)),
            scope=str(action.params.get("scope", "local")),
        )

    # -- audit -------------------------------------------------------------
    def _audit(self, entry: Dict[str, Any]) -> None:
        entry = dict(entry)
        entry.setdefault("at", _utcnow())
        entry.setdefault("posture", POSTURE)
        _append_jsonl(self.audit_path, entry)

    # -- execution ---------------------------------------------------------
    def run(self, action: Action, signal_id: Optional[str] = None) -> Receipt:
        """Run an action under the authority framework.

        Returns a Receipt in all cases. Raises nothing on the happy path;
        refusals and escalations are receipts, not exceptions.
        """
        signal = self.live_signal(signal_id) if signal_id else None
        if signal is None:
            self._audit(
                {
                    "event": "refused",
                    "action_id": action.id,
                    "kind": action.kind,
                    "target": action.target,
                    "reason": "no live time-sensitive signal: authority requires a trigger",
                }
            )
            return Receipt(
                id=f"rcpt-{uuid.uuid4().hex[:12]}",
                action_id=action.id,
                tier="refused",
                signal_id=signal_id or "",
                outcome="refused",
                result={"reason": "no live time-sensitive signal"},
            )

        tier = self.classify(action)

        if tier == TIER_MAJOR:
            # STRUCTURAL: there is no code path below that invokes an
            # executor for a major action. Ever.
            escalation = Escalation(
                id=f"esc-{uuid.uuid4().hex[:12]}",
                action_id=action.id,
                kind=action.kind,
                target=action.target,
                tier=tier,
                signal_id=signal.id,
                reason=(
                    "major-tier action (architecture / irreversible / security / "
                    "founder-level / ambiguous): never auto — escalated to Chauncey"
                ),
            )
            _append_jsonl(self.escalation_path, asdict(escalation))
            self._audit(
                {
                    "event": "escalated",
                    "action_id": action.id,
                    "kind": action.kind,
                    "target": action.target,
                    "tier": tier,
                    "signal_id": signal.id,
                    "escalation_id": escalation.id,
                }
            )
            return Receipt(
                id=f"rcpt-{uuid.uuid4().hex[:12]}",
                action_id=action.id,
                tier=tier,
                signal_id=signal.id,
                outcome="escalated",
                result={"escalation_id": escalation.id},
            )

        executor = _Executors.get(action.kind.strip().lower())
        if executor is None:
            # Shouldn't happen for known minor/mid kinds, but fail closed.
            self._audit(
                {
                    "event": "refused",
                    "action_id": action.id,
                    "kind": action.kind,
                    "tier": tier,
                    "signal_id": signal.id,
                    "reason": "no registered executor for this kind",
                }
            )
            return Receipt(
                id=f"rcpt-{uuid.uuid4().hex[:12]}",
                action_id=action.id,
                tier=tier,
                signal_id=signal.id,
                outcome="refused",
                result={"reason": "no registered executor"},
            )

        # Six-gate chain, recorded (consequential acts).
        gates: Dict[str, Any] = {
            "plan": {
                "kind": action.kind,
                "target": action.target,
                "description": action.description,
                "tier": tier,
            },
            "preview": {"expected": f"{action.kind} on {action.target}"},
            # Permission for autonomous minor/mid acts IS the standing grant
            # (Chauncey, 2026-09-17). Labeled honestly: not per-action approval.
            "permission": {"basis": AUTHORITY_GRANT, "trigger": signal.id},
            "execute": {"at": _utcnow()},
        }
        try:
            result = executor(action)
            gates["execute"]["ok"] = bool(result.get("ok", False))
        except Exception as exc:  # executors must never take down the framework
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            gates["execute"]["ok"] = False
        gates["verify"] = {
            "self_check": "executor-reported",
            "ok": bool(result.get("ok", False)),
        }
        receipt = Receipt(
            id=f"rcpt-{uuid.uuid4().hex[:12]}",
            action_id=action.id,
            tier=tier,
            signal_id=signal.id,
            outcome="executed",
            gates=gates,
            result=result,
        )
        gates["receipt"] = {"receipt_id": receipt.id}
        self._audit(
            {
                "event": "executed",
                "action_id": action.id,
                "kind": action.kind,
                "target": action.target,
                "tier": tier,
                "signal_id": signal.id,
                "signal_source": signal.source,
                "receipt_id": receipt.id,
                "ok": bool(result.get("ok", False)),
                "gates": gates,
            }
        )
        return receipt

    # -- escalations --------------------------------------------------------
    def pending_escalations(self) -> List[Dict[str, Any]]:
        return [
            e for e in _read_jsonl(self.escalation_path) if e.get("status") == "open"
        ]

    def resolve_escalation(self, escalation_id: str, resolution: str) -> bool:
        records = _read_jsonl(self.escalation_path)
        changed = False
        for rec in records:
            if rec.get("id") == escalation_id and rec.get("status") == "open":
                rec["status"] = "resolved"
                rec["resolved_at"] = _utcnow()
                rec["resolution"] = resolution
                changed = True
        if changed:
            self.escalation_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.escalation_path, "w", encoding="utf-8") as fh:
                for rec in records:
                    fh.write(json.dumps(rec, default=str) + "\n")
            self._audit(
                {
                    "event": "escalation_resolved",
                    "escalation_id": escalation_id,
                    "resolution": resolution,
                }
            )
        return changed

    def audit_tail(self, n: int = 20) -> List[Dict[str, Any]]:
        return _read_jsonl(self.audit_path)[-n:]

    def status(self) -> Dict[str, Any]:
        live = [s for s in self._signals.values() if s.is_live()]
        return {
            "posture": POSTURE,
            "grant": AUTHORITY_GRANT,
            "tiers": {
                "minor": "full auto (reversible, low-risk)",
                "mid": "auto with full audit trail + receipt",
                "major": "NEVER auto — escalates to Chauncey",
            },
            "trigger": "a live time-sensitive sensed signal is required for any autonomous action",
            "live_signals": len(live),
            "pending_escalations": len(self.pending_escalations()),
            "audit_entries": len(_read_jsonl(self.audit_path)),
        }


# --- CLI ---------------------------------------------------------------------


def _engine() -> AuthorityEngine:
    return AuthorityEngine()


def cli_main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="levi demand --authority")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Authority policy + live signals + counts")

    p_audit = sub.add_parser("audit", help="Show recent audit entries")
    p_audit.add_argument("-n", type=int, default=20)

    sub.add_parser("escalations", help="List open escalations for Chauncey")

    p_res = sub.add_parser("resolve", help="Mark an escalation resolved")
    p_res.add_argument("escalation_id")
    p_res.add_argument("--note", default="", help="Resolution note")

    p_sense = sub.add_parser("sense", help="Record a time-sensitivity signal")
    p_sense.add_argument("--source", required=True)
    p_sense.add_argument("--evidence", default="")
    p_sense.add_argument("--confidence", type=float, default=0.6)
    p_sense.add_argument("--ttl", type=int, default=3600)

    p_prop = sub.add_parser("propose", help="Classify (and optionally run) an action")
    p_prop.add_argument("--kind", required=True)
    p_prop.add_argument("--target", required=True)
    p_prop.add_argument("--desc", default="")
    p_prop.add_argument("--signal", default=None, help="Signal id (required to run)")
    p_prop.add_argument("--param", action="append", default=[], help="key=value params")
    p_prop.add_argument("--execute", action="store_true", help="Run under authority")

    args = ap.parse_args(argv)
    eng = _engine()

    if args.cmd == "status":
        print(json.dumps(eng.status(), indent=2))
    elif args.cmd == "audit":
        for entry in eng.audit_tail(args.n):
            print(json.dumps(entry, default=str))
    elif args.cmd == "escalations":
        pending = eng.pending_escalations()
        if not pending:
            print("No open escalations.")
        for esc in pending:
            print(
                f"{esc['id']} [{esc['tier']}] {esc['kind']} on {esc['target']} — {esc['reason'][:80]}"
            )
    elif args.cmd == "resolve":
        ok = eng.resolve_escalation(args.escalation_id, args.note)
        print("Resolved." if ok else "Escalation not found or already resolved.")
        return 0 if ok else 1
    elif args.cmd == "sense":
        try:
            sig = eng.sense(args.source, args.evidence, args.confidence, args.ttl)
        except ValueError as exc:
            print(f"Signal rejected: {exc}", file=sys.stderr)
            return 1
        print(f"Signal [{sig.id}] live={sig.is_live()} confidence={sig.confidence}")
    elif args.cmd == "propose":
        params: Dict[str, Any] = {}
        for pair in args.param:
            if "=" in pair:
                k, v = pair.split("=", 1)
                params[k.strip()] = v
        action = Action(
            id=f"act-{uuid.uuid4().hex[:12]}",
            kind=args.kind,
            target=args.target,
            description=args.desc,
            params=params,
        )
        tier = eng.classify(action)
        print(f"Action [{action.id}] kind={action.kind} target={action.target} tier={tier}")
        if args.execute:
            receipt = eng.run(action, signal_id=args.signal)
            print(f"Outcome: {receipt.outcome} (receipt {receipt.id})")
            if receipt.outcome == "escalated":
                print(f"Escalation: {receipt.result.get('escalation_id')} — nothing executed.")
            if receipt.outcome == "refused":
                print(f"Refused: {receipt.result.get('reason')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli_main())
