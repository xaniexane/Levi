"""NEXUS native SI engine — the authoritative router.

This is the heart of the nexus: pure stdlib, no network, no
providers, no borrowed machinery. It owns:

- the organ registry (persisted, LEVI-local),
- per-organ inboxes (in-memory),
- the dead-letter store (persisted),
- the routing law (validate -> TTL -> address -> deliver, receipt at
  every step),
- an append-only JSONL journal of receipts.

Everything here is data handling. The engine never evaluates payload
content: payloads are data, never instructions.

Home resolution: ``LEVI_HOME`` env var, else ``~/.levi``; all nexus
state lives under ``<home>/nexus/``. Pass ``journal=False`` (or a
custom ``home``) for hermetic use.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..envelope import Envelope, Receipt, validate

Handler = Callable[[Envelope], None]


def resolve_home(explicit: Optional[Path] = None) -> Path:
    """LEVI_HOME-overridable home; nexus state lives under <home>/nexus."""
    if explicit is not None:
        return Path(explicit)
    return Path(os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi"))


class NexusEngine:
    """Authoritative in-memory router with optional durable journal."""

    def __init__(self, home: Optional[Path] = None, journal: bool = True) -> None:
        self.home = resolve_home(home) / "nexus"
        self.journal_enabled = journal
        self._organs: Dict[str, Optional[Handler]] = {}
        self._inboxes: Dict[str, List[Envelope]] = {}
        self._dead: List[Dict[str, Any]] = []
        if journal:
            self.home.mkdir(parents=True, exist_ok=True)
        self._load_registry()
        self._load_dead()

    # -- paths ---------------------------------------------------------
    @property
    def registry_path(self) -> Path:
        return self.home / "organs.json"

    @property
    def dead_path(self) -> Path:
        return self.home / "dead_letters.json"

    @property
    def journal_path(self) -> Path:
        return self.home / "journal.jsonl"

    # -- organ registry -------------------------------------------------
    def register_organ(self, name: str, handler: Optional[Handler] = None) -> bool:
        """Register an organ; True if newly registered, False if known."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("organ name must be a non-empty string")
        name = name.strip()
        new = name not in self._organs
        self._organs[name] = handler
        self._inboxes.setdefault(name, [])
        self._save_registry()
        return new

    def organs(self) -> List[str]:
        return sorted(self._organs)

    def is_registered(self, name: str) -> bool:
        return name in self._organs

    # -- routing law ----------------------------------------------------
    def route(self, envelope: Envelope) -> Receipt:
        """Route one envelope; always returns a Receipt. Never raises
        for routing outcomes (unknown organ, TTL expiry, poison)."""
        problem = validate(envelope)
        if problem is not None:
            return self._receipt(envelope, "rejected", envelope.to_organ, problem)
        if envelope.expired():
            return self.dead_letter(
                envelope,
                "TTL expired: age %.1fs exceeded ttl %.1fs"
                % (envelope.age(), envelope.ttl),
            )
        dest = envelope.to_organ
        if dest is None:
            return self._receipt(
                envelope,
                "accepted",
                None,
                "broadcast intent: use broadcast() to fan out",
            )
        if dest not in self._organs:
            return self.dead_letter(
                envelope, "unknown organ %r: no route, dead-lettered" % dest
            )
        self._inboxes[dest].append(envelope)
        receipt = self._receipt(
            envelope, "routed", dest, "delivered to %r inbox" % dest
        )
        handler = self._organs.get(dest)
        if handler is not None:
            try:
                handler(envelope)
            except Exception as exc:  # organ-side failure, never silent
                receipt.detail = "handler raised %s: %s" % (
                    type(exc).__name__,
                    exc,
                )
        return receipt

    def broadcast(
        self, envelope: Envelope, exclude: Optional[str] = None
    ) -> List[Receipt]:
        """Fan one envelope out to every registered organ (minus sender).

        The envelope itself is cloned per organ (fresh ids, same
        trace_id) so each delivery is independently traceable."""
        problem = validate(envelope)
        if problem is not None:
            return [self._receipt(envelope, "rejected", None, problem)]
        if envelope.expired():
            return [
                self.dead_letter(
                    envelope,
                    "TTL expired before broadcast: age %.1fs" % envelope.age(),
                )
            ]
        targets = [o for o in self.organs() if o != exclude]
        if not targets:
            return [
                self.dead_letter(envelope, "broadcast to no organs: registry empty")
            ]
        receipts = []
        for organ in targets:
            clone = Envelope(
                from_organ=envelope.from_organ,
                to_organ=organ,
                kind=envelope.kind,
                payload=dict(envelope.payload),
                ttl=envelope.ttl,
                trace_id=envelope.trace_id,
                created_at=envelope.created_at,
            )
            receipts.append(self.route(clone))
        return receipts

    def dead_letter(self, envelope: Envelope, reason: str) -> Receipt:
        """Record a dead letter and return its receipt."""
        entry = {
            "envelope": envelope.to_dict(),
            "reason": reason,
            "dead_at": time.time(),
        }
        self._dead.append(entry)
        self._save_dead()
        return self._receipt(envelope, "dead-lettered", envelope.to_organ, reason)

    def dead_letters(self) -> List[Dict[str, Any]]:
        return list(self._dead)

    # -- inbox access ---------------------------------------------------
    def inbox(self, organ: str) -> List[Envelope]:
        return list(self._inboxes.get(organ, []))

    def drain(self, organ: str) -> List[Envelope]:
        """Take and clear an organ's inbox."""
        box = self._inboxes.get(organ, [])
        self._inboxes[organ] = []
        return box

    # -- receipts / journal ----------------------------------------------
    def _receipt(
        self, envelope: Envelope, status: str, organ: Optional[str], reason: str
    ) -> Receipt:
        receipt = Receipt(
            status=status,
            envelope_id=envelope.id,
            trace_id=envelope.trace_id,
            organ=organ,
            reason=reason,
        )
        if self.journal_enabled:
            self._append_journal(receipt, envelope)
        return receipt

    def _append_journal(self, receipt: Receipt, envelope: Envelope) -> None:
        line = json.dumps(
            {
                "type": "receipt",
                "at": time.time(),
                "receipt": receipt.to_dict(),
                "envelope_kind": envelope.kind,
                "envelope_from": envelope.from_organ,
            }
        )
        with open(self.journal_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def read_journal(self) -> List[Dict[str, Any]]:
        """Read the journal back (hermetic-home friendly)."""
        if not self.journal_path.exists():
            return []
        entries = []
        with open(self.journal_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    # -- persistence ------------------------------------------------------
    def _load_registry(self) -> None:
        if not self.registry_path.exists():
            return
        try:
            names = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for name in names:
            if isinstance(name, str) and name.strip():
                self._organs.setdefault(name.strip(), None)
                self._inboxes.setdefault(name.strip(), [])

    def _save_registry(self) -> None:
        if not self.journal_enabled:
            return
        self.home.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(
            json.dumps(sorted(self._organs), indent=2), encoding="utf-8"
        )

    def _load_dead(self) -> None:
        if not self.dead_path.exists():
            return
        try:
            entries = json.loads(self.dead_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if isinstance(entries, list):
            self._dead = entries

    def _save_dead(self) -> None:
        if not self.journal_enabled:
            return
        self.home.mkdir(parents=True, exist_ok=True)
        self.dead_path.write_text(
            json.dumps(self._dead, indent=2, default=str), encoding="utf-8"
        )
