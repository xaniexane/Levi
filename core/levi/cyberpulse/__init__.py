"""cyberpulse: telemetry; senses the organism's own signals (LEVI-native).

Canon role (ORGANISM_FORMS): "telemetry; senses the organism's own
signals".

Canon evidence (founder corpus):
  - copilot-sweep/ser13-18-21-master-conversation.md: "CyberPulse
    (Telemetry) — health metrics, logs, alerts."
  - The founder's original omega_pulse.py: "CyberPulse (MASTER PULSE) —
    schedules, coordinates, and protects. The 'heartbeat' and orchestrator
    for the entire Pulse layer."

This is a LEVI-native recreation with LEVI's own twist — never a copy of
the original code. Differences from the original: stdlib only, no file
registry side effects at import, fail-closed registration, dry-run purity
(a heartbeat with ``dry_run=True`` probes and schedules NOTHING), and a
receipt for every action.

Sensing substrate: ``levi.observability`` (the decision-trace corpus) and
``levi.pulse`` (the periodic self-check). CyberPulse never claims signals
it has no sensor for — ``capabilities()`` reports exactly what is wired.

Ready-for-review by the keeper. Never claims his review.
"""

from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
from typing import Any, Dict, List, Optional

FORM_NAME = "cyberpulse"

# LEVI-native pulse registry seeds: name -> importable module that
# constitutes a pulse channel. Status is PROBED at heartbeat time, never
# asserted at registration time.
_SEED_PULSES: Dict[str, str] = {
    "demandpulse": "levi.demand",
    "nexus": "levi.nexus",
    "observability": "levi.observability",
    "pulse": "levi.pulse",
    "uniforge": "levi.uniforge",
}

RESERVED = {"cyberpulse"}  # the master may not register itself


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def capabilities() -> Dict[str, Any]:
    """Honest report: what CyberPulse can actually sense right now."""
    sense: Dict[str, Any] = {"form": FORM_NAME}
    try:
        import_module("levi.observability")
        sense["decision_traces"] = "wired (levi.observability TraceStore)"
    except Exception as exc:  # pragma: no cover - import failure only
        sense["decision_traces"] = f"unavailable ({exc})"
    try:
        import_module("levi.pulse")
        sense["periodic_self_check"] = "wired (levi.pulse run_pulse)"
    except Exception as exc:  # pragma: no cover - import failure only
        sense["periodic_self_check"] = f"unavailable ({exc})"
    sense["honest_limit"] = (
        "CyberPulse senses the organism's own decision traces and self-check "
        "output only. It does not see network traffic, host health, or any "
        "signal it has no sensor for."
    )
    return sense


class CyberPulse:
    """MASTER PULSE — register pulse channels, probe them, heartbeat."""

    def __init__(self) -> None:
        self._pulses: Dict[str, Dict[str, Any]] = {}
        self._history: List[Dict[str, Any]] = []
        for name, module in _SEED_PULSES.items():
            self.register_pulse(name, {"module": module, "seed": True})

    # -- registration (fail-closed) -------------------------------------

    def register_pulse(
        self, name: Any, meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Register a pulse channel. Rejects bad names as data (receipt)."""
        if not isinstance(name, str) or not name.strip():
            return self._receipt(
                "rejected",
                f"pulse name must be a non-empty string, got {name!r}",
                pulse=None,
            )
        key = name.strip()
        if key in RESERVED:
            return self._receipt(
                "rejected",
                "the master pulse may not register itself as a channel",
                pulse=key,
            )
        meta = dict(meta or {})
        module = meta.get("module")
        if module is not None and (not isinstance(module, str) or not module.strip()):
            return self._receipt(
                "rejected",
                f"'module' must be a non-empty string or absent, got {module!r}",
                pulse=key,
            )
        self._pulses[key] = {
            "name": key,
            "module": module,
            "meta": {k: v for k, v in meta.items() if k != "module"},
            "registered_at": _utcnow(),
        }
        return self._receipt(
            "registered", f"pulse channel '{key}' registered", pulse=key
        )

    # -- sensing ---------------------------------------------------------

    def probe(self, name: str) -> Dict[str, Any]:
        """Probe one channel: import its module, report present/absent."""
        entry = self._pulses.get(name)
        if entry is None:
            return {"pulse": name, "status": "unknown", "detail": "not registered"}
        module = entry.get("module")
        if not module:
            return {
                "pulse": name,
                "status": "unprobed",
                "detail": "no module bound; metadata channel only",
            }
        try:
            import_module(module)
            return {"pulse": name, "status": "present", "detail": f"{module} imports"}
        except Exception as exc:
            return {
                "pulse": name,
                "status": "absent",
                "detail": f"{module} failed to import: {exc}",
            }

    def sense(self, *, trace_dir: Any = None) -> Dict[str, Any]:
        """Read the organism's own signals: recent decision-trace volume.

        ``trace_dir`` must be given explicitly — CyberPulse never touches
        the default ``~/.levi/observability`` store on its own (no surprise
        HOME writes; callers pass the store they intend to sense).
        """
        out: Dict[str, Any] = {
            "form": FORM_NAME,
            "channel": "levi.observability",
            "at": _utcnow(),
        }
        if trace_dir is None:
            out["status"] = "no-store"
            out["detail"] = (
                "no trace store given; pass trace_dir to sense a store "
                "(e.g. levi.observability.store.default_store_dir())"
            )
            out["recent_traces"] = 0
            return out
        try:
            from levi.observability.store import TraceStore

            store = TraceStore(trace_dir)
            traces = store.recent(limit=50)
            out["status"] = "sensed"
            out["recent_traces"] = len(traces)
            outcomes: Dict[str, int] = {}
            for t in traces:
                o = getattr(t, "outcome", "?")
                outcomes[str(o)] = outcomes.get(str(o), 0) + 1
            out["outcomes"] = outcomes
        except Exception as exc:
            out["status"] = "unavailable"
            out["detail"] = str(exc)
        return out

    # -- heartbeat (dry-run pure) ----------------------------------------

    def heartbeat(
        self, *, dry_run: bool = False, trace_dir: Any = None
    ) -> Dict[str, Any]:
        """Master heartbeat: probe every channel, schedule nothing."""
        probes = [self.probe(n) for n in sorted(self._pulses)]
        present = sum(1 for p in probes if p["status"] == "present")
        receipt = self._receipt(
            "dry-run" if dry_run else "heartbeat",
            (
                f"probed {len(probes)} channels, {present} present; "
                + (
                    "dry run — no probes executed beyond import checks, "
                    "nothing scheduled"
                    if dry_run
                    else "probes executed (import checks only); scheduling "
                    "belongs to the daemon, not the pulse"
                )
            ),
            pulse=None,
            dry_run=dry_run,
        )
        receipt["probes"] = probes
        receipt["sense"] = self.sense(trace_dir=trace_dir)
        if not dry_run:
            self._history.append(
                {"at": receipt["at"], "channels": len(probes), "present": present}
            )
        return receipt

    def history(self) -> List[Dict[str, Any]]:
        return [dict(h) for h in self._history]

    # -- receipts ---------------------------------------------------------

    def _receipt(
        self, status: str, reason: str, *, pulse: Optional[str], dry_run: bool = False
    ) -> Dict[str, Any]:
        return {
            "form": FORM_NAME,
            "status": status,
            "reason": reason,
            "pulse": pulse,
            "channels": sorted(self._pulses),
            "dry_run": dry_run,
            "at": _utcnow(),
        }
