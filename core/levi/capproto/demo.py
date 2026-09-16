"""Demo service + client for capproto/1: the ``kvnote`` service.

A tiny local key/value note service whose four verbs (put/get/list/del)
are each gated by their own capability action (``kvnote.put`` etc.). The
demo shows the protocol's whole story in one screen:

1. The issuer mints a broad token (all four verbs).
2. It is ATTENUATED to read-only (get/list) with a short TTL and handed
   to the "client".
3. The client succeeds at reads and is REFUSED at writes — by the
   protocol, not by policy prose.
4. The attenuated token is revoked; reads then fail too.

Run :func:`run_demo` or ``python -m levi.capproto demo``.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.revival.telescript import issue, verify

from .protocol import ServiceSpec
from .tokens import MintLedger, attenuate, default_home
from .transport import CapClient, CapServer

__all__ = ["build_kvnote_service", "run_demo"]


class _NoteStore:
    def __init__(self) -> None:
        self._notes: Dict[str, str] = {}
        self._lock = threading.Lock()

    def put(self, key: str, value: str) -> Dict[str, Any]:
        with self._lock:
            self._notes[key] = value
        return {"key": key, "stored": True}

    def get(self, key: str) -> Dict[str, Any]:
        with self._lock:
            if key not in self._notes:
                raise KeyError(f"no note {key!r}")
            return {"key": key, "value": self._notes[key]}

    def list(self) -> Dict[str, Any]:
        with self._lock:
            return {"keys": sorted(self._notes)}

    def delete(self, key: str) -> Dict[str, Any]:
        with self._lock:
            if key not in self._notes:
                raise KeyError(f"no note {key!r}")
            del self._notes[key]
        return {"key": key, "deleted": True}


def build_kvnote_service(ledger: Optional[MintLedger] = None) -> ServiceSpec:
    store = _NoteStore()
    spec = ServiceSpec("kvnote")
    spec.add_verb("put", store.put, required_args=["key", "value"],
                  summary="store a note (needs kvnote.put)")
    spec.add_verb("get", store.get, required_args=["key"],
                  summary="read a note (needs kvnote.get)")
    spec.add_verb("list", store.list, summary="list note keys (needs kvnote.list)")
    spec.add_verb("del", store.delete, required_args=["key"],
                  summary="delete a note (needs kvnote.del)")
    spec.ledger = ledger
    return spec


def run_demo(home: Optional[Path] = None) -> List[str]:
    """Run the full in-process demo over a real local socket. Returns log lines."""
    log: List[str] = []
    home = Path(home) if home else default_home()
    ledger = MintLedger(home)
    spec = build_kvnote_service(ledger)
    server = CapServer(spec, home=home).start()
    client = CapClient(home=home, name="kvnote").connect()
    try:
        log.append(f"endpoint: {server.endpoint}")
        desc = client.hello("demo-client")
        log.append(f"hello -> verbs: {sorted(desc['service']['verbs'])}")

        # 1. Issuer mints a broad token for the whole service.
        broad = issue("local-issuer", "demo-client",
                      ["kvnote.put", "kvnote.get", "kvnote.list", "kvnote.del"],
                      ttl_seconds=600)
        ledger.record_issued(broad)
        client.call("kvnote", "put", broad, {"key": "idea", "value": "capabilities beat APIs"})
        log.append("broad token: put OK")

        # 2. Attenuate to read-only, 60s TTL — this is what the client keeps.
        read_only = attenuate(broad, actions=["kvnote.get", "kvnote.list"], ttl_seconds=60, ledger=ledger)
        log.append("attenuated to read-only (kvnote.get, kvnote.list), ttl=60s")

        # 3. Reads succeed, writes are refused by the protocol.
        log.append(f"read-only get -> {client.call('kvnote', 'get', read_only, {'key': 'idea'})}")
        try:
            client.call("kvnote", "put", read_only, {"key": "x", "value": "y"})
            log.append("ERROR: write with read-only token was NOT refused")
        except Exception as exc:
            log.append(f"read-only put refused as designed: {exc}")

        # 4. Widening is refused at attenuate time, before anything is minted.
        try:
            attenuate(read_only, actions=["kvnote.get", "kvnote.del"])
            log.append("ERROR: widening attenuation was NOT refused")
        except Exception as exc:
            log.append(f"widening attenuation refused: {type(exc).__name__}")

        # 5. Revoke; reads now fail too.
        client.revoke(read_only)
        try:
            client.call("kvnote", "get", read_only, {"key": "idea"})
            log.append("ERROR: revoked token was NOT refused")
        except Exception as exc:
            log.append(f"revoked token refused: {exc}")

        log.append(f"ledger holds {len(ledger.entries())} events "
                   f"({', '.join(e['event'] for e in ledger.entries())})")
    finally:
        client.close()
        server.stop()
    return log


if __name__ == "__main__":
    for line in run_demo():
        print(line)
