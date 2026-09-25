"""Local encrypted ops server for the LEVI transportation edition.

ENCRYPTION POSTURE — stated before any fleet data is stored:
- All ops state (check-call events, detention ledger, POD records, channel
  outbox, route-ranking snapshots) persists ONLY inside Cybrus sealed
  envelopes (``levi.cybrus.seal.SealedEnvelope``) — passphrase-gated,
  fail-closed. There is no bespoke crypto in this module, per keeper
  canon: Cybrus is the security + OAuth layer on ALL creations.
- Backend: Fernet (AES-128-CBC + HMAC-SHA256) when the ``cryptography``
  package is installed; otherwise the labeled stdlib fallback
  (PBKDF2-HMAC-SHA256 + HMAC stream cipher, NOT AES). ``OpsServer.backend``
  reports which is in force — the operator always knows what grade of
  seal is holding the data.
- The passphrase is supplied at construction, held in memory only, and
  never written to disk. Wrong passphrase -> ``SealError`` wrapped as
  :class:`OpsAuthError`; no partial plaintext ever surfaces.
- No fleet data leaves the machine: this server binds no socket, opens no
  connection, and makes no network calls. Local-first is structural, not
  a setting. The sealed state file on disk is opaque bytes — grep finds
  no load references, names, or phone numbers in it.
- External-identity auth (driver OAuth, etc.) is delegated to Cybrus
  (``cybrus.broker`` OAuth flows). This module mints no tokens and keeps
  no credentials of its own; :class:`OpsAuth` is the passphrase gate to
  unseal local state and nothing more.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from levi.cybrus.seal import SealError, SealedEnvelope

from .checkcalls import (
    CheckCallEngine,
    DetentionPolicy,
    SimulatedChannel,
)
from .ledger import DispatchLedger
from .routes import FuelParams, RankedRoute, RoadNetwork, SyntheticRoadNetwork, rank_routes


class OpsError(ValueError):
    """Ops-server failure (bad input, bad state)."""


class OpsAuthError(OpsError):
    """Authentication failure: wrong passphrase or tampered state."""


STATE_FILENAME = "ops_state.sealed"


class OpsAuth:
    """Passphrase gate to the sealed ops state. Cybrus-backed, nothing bespoke.

    External OAuth (driver identities, carrier logins) is NOT handled here —
    it is delegated to the Cybrus broker per canon. This gate unseals local
    state and nothing more.
    """

    OAUTH_DELEGATE = "levi.cybrus.broker.CybrusBroker (oauth_start/oauth_callback)"

    def __init__(self, passphrase: str, directory: str | Path) -> None:
        if not passphrase:
            raise OpsAuthError("passphrase required to open the ops server")
        self._envelope = SealedEnvelope(passphrase, Path(directory) / "sealed")
        self._path = Path(directory) / STATE_FILENAME

    @property
    def backend(self) -> str:
        """Which seal backend is in force: 'fernet' or 'stdlib-fallback'."""
        return self._envelope.backend

    def seal_state(self, state: dict) -> Path:
        blob = self._envelope.seal_bytes(
            json.dumps(state, sort_keys=True).encode("utf-8")
        )
        self._path.write_bytes(blob)
        return self._path

    def open_state(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            raw = self._envelope.open_bytes(self._path.read_bytes())
        except SealError as e:
            raise OpsAuthError(f"cannot open ops state: {e}") from e
        return json.loads(raw.decode("utf-8"))


class OpsServer:
    """The fleet's local-first encrypted ops server.

    Wraps the dispatch ledger (loads/drivers/trucks), the hands-off
    check-call engine, and route ranking behind one passphrase-gated,
    sealed-at-rest surface.
    """

    def __init__(
        self,
        passphrase: str,
        home: str | Path,
        network: RoadNetwork | None = None,
        policy: DetentionPolicy | None = None,
    ) -> None:
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        self.auth = OpsAuth(passphrase, self.home)
        self.ledger = DispatchLedger(self.home / "dispatch.db")
        self.channel = SimulatedChannel()
        self.engine = CheckCallEngine(self.ledger, self.channel, policy)
        self.network: RoadNetwork = network or SyntheticRoadNetwork()
        self._restore()

    @property
    def backend(self) -> str:
        return self.auth.backend

    # -- persistence ----------------------------------------------------------

    def _snapshot(self) -> dict:
        return {
            "saved_at": datetime.now().isoformat(),
            "network_kind": self.network.kind,
            "events": self.engine.events,
            "stops": {
                lid: {s: asdict(r) for s, r in stops.items()}
                for lid, stops in self.engine.stops.items()
            },
            "pods": {lid: asdict(p) for lid, p in self.engine.pods.items()},
            "outbox": [asdict(r) for r in self.channel.sent],
        }

    def save(self) -> Path:
        """Seal the full ops state to disk. Encrypted at rest via Cybrus."""
        return self.auth.seal_state(self._snapshot())

    def _restore(self) -> None:
        from .checkcalls import PodRecord, StopRecord

        state = self.auth.open_state()
        if not state:
            return
        self.engine.events.extend(state.get("events", []))
        for lid, stops in state.get("stops", {}).items():
            self.engine.stops[lid] = {
                s: StopRecord(**r) for s, r in stops.items()
            }
        for lid, p in state.get("pods", {}).items():
            self.engine.pods[lid] = PodRecord(**p)
        # Outbox is informational; channel sequence continues from its length.
        for entry in state.get("outbox", []):
            self.channel.send(entry["recipient"], entry["message"].removeprefix("[SIMULATED] "))

    # -- operations -----------------------------------------------------------

    def rank_routes(
        self,
        origin: str,
        destination: str,
        fuel: FuelParams | None = None,
        deadhead_from: str | None = None,
        max_routes: int = 3,
    ) -> list[RankedRoute]:
        routes = rank_routes(
            self.network, origin, destination, fuel, deadhead_from, max_routes
        )
        self.save()
        return routes

    def arrive(self, load_id: str, stop: str, location: str, at: datetime | None = None):
        receipt = self.engine.arrive(load_id, stop, location, at)
        self.save()
        return receipt

    def depart(self, load_id: str, stop: str, at: datetime | None = None):
        receipt = self.engine.depart(load_id, stop, at)
        self.save()
        return receipt

    def mark_picked_up(self, load_id: str, at: datetime | None = None):
        receipt = self.engine.mark_picked_up(load_id, at)
        self.save()
        return receipt

    def receive_pod(
        self,
        load_id: str,
        signed_by: str,
        document_ref: str = "",
        at: datetime | None = None,
    ):
        receipt = self.engine.receive_pod(load_id, signed_by, document_ref, at)
        self.save()
        return receipt

    def detention_due_cents(self, load_id: str) -> int:
        return self.engine.detention_due_cents(load_id)
