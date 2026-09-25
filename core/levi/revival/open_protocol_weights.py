"""open_protocol_weights — an open protocol with no closed core behind it.

Studied from: giant-patterns-hunt-20260916-0016/report.md (Section 10).

The load-bearing idea: the honest inversion of a "free tier on top of
a closed core" is a protocol where the *entire* stack is open and
runnable locally. There is no privileged remote half that decides what
the local half is allowed to do — every capability must have a local
implementation, or it does not ship.

LEVI's take: ``OpenMesh`` is a stdlib-only message protocol (JSON
envelopes: kind, payload, sender, nonce) plus a capability registry.
Capabilities register *local* handlers — plain Python callables — and
the mesh routes messages to them without any network. The audit
``assert_no_closed_core`` walks the registry and fails if any
capability lacks a local handler, i.e. the mesh can never silently
depend on a remote service. A ``LocalWeights`` catalog lists runnable
model weights (path, size, digest, license): LEVI-native or openly
licensed, local disk only, never fetched by the protocol itself.

Honest limits: this proves local *routability*, not local *quality* —
a local handler can be weaker than a remote service it replaces, and
the catalog records what is present, it does not download or verify
weights beyond reading the digest you recorded.

This is an original, from-scratch implementation for LEVI.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

ORIGIN = "levi-revival/open-protocol-weights"


class ClosedCoreError(Exception):
    """A capability was registered with no local handler."""


class UnknownCapability(Exception):
    """A message addressed a capability the mesh does not know."""


def make_envelope(
    kind: str, payload: Dict[str, Any], sender: str = "local"
) -> Dict[str, Any]:
    """Build a protocol envelope. Pure data — stdlib json round-trips it."""
    return {
        "protocol": "levi-open-mesh/1",
        "kind": kind,
        "payload": payload,
        "sender": sender,
        "nonce": uuid.uuid4().hex,
        "timestamp": time.time(),
    }


def envelope_bytes(envelope: Dict[str, Any]) -> bytes:
    """Canonical wire form: sorted-key JSON, UTF-8. No framing magic."""
    return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")


def parse_envelope(raw: bytes) -> Dict[str, Any]:
    """Parse wire bytes back into an envelope dict."""
    envelope = json.loads(raw.decode("utf-8"))
    for key in ("protocol", "kind", "payload", "nonce"):
        if key not in envelope:
            raise ValueError(f"envelope missing required field: {key}")
    return envelope


@dataclass
class Capability:
    """One thing the mesh can do — always with a local handler."""

    name: str
    description: str
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    local: bool = True  # False means "remote-only": never allowed to ship

    def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.handler(payload)


@dataclass
class LocalWeights:
    """A runnable weights entry: present on local disk, honestly labeled."""

    name: str
    path: str
    size_bytes: int
    sha256: str
    license: str
    family: str = "levi-native"

    def present(self) -> bool:
        return os.path.exists(self.path)

    def verify_digest(self) -> bool:
        """Re-hash the file and compare to the recorded digest.

        Reads in chunks so multi-gigabyte files don't eat memory.
        Returns False (not raises) when the file is absent.
        """
        if not self.present():
            return False
        digest = hashlib.sha256()
        with open(self.path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest() == self.sha256


class OpenMesh:
    """The whole protocol: envelopes in, local handlers out. No network."""

    def __init__(self) -> None:
        self._capabilities: Dict[str, Capability] = {}
        self._weights: Dict[str, LocalWeights] = {}

    # -- capabilities -------------------------------------------------
    def register(self, capability: Capability) -> None:
        if not capability.local:
            raise ClosedCoreError(
                f"capability {capability.name!r} has no local handler — "
                "the mesh refuses remote-only capabilities"
            )
        self._capabilities[capability.name] = capability

    def capabilities(self) -> List[str]:
        return sorted(self._capabilities)

    def dispatch(self, raw: bytes) -> bytes:
        """Route one envelope to its local handler, return the reply envelope."""
        envelope = parse_envelope(raw)
        name = envelope["kind"]
        capability = self._capabilities.get(name)
        if capability is None:
            raise UnknownCapability(f"no such capability: {name!r}")
        result = capability.handle(envelope["payload"])
        reply = make_envelope(f"{name}.reply", {"result": result}, sender="mesh")
        return envelope_bytes(reply)

    def assert_no_closed_core(self) -> List[str]:
        """Audit: every registered capability must run locally.

        Returns the sorted capability names it verified. Raises
        ClosedCoreError if the registry was tampered with to include a
        remote-only entry.
        """
        for name, cap in self._capabilities.items():
            if not cap.local:
                raise ClosedCoreError(f"closed core detected: {name!r}")
        return self.capabilities()

    # -- weights catalog ----------------------------------------------
    def catalog_weights(self, weights: LocalWeights) -> None:
        self._weights[weights.name] = weights

    def weights(self) -> List[LocalWeights]:
        return [self._weights[name] for name in sorted(self._weights)]

    def open_spec(self) -> Dict[str, Any]:
        """The whole protocol, described — nothing hidden behind it."""
        return {
            "protocol": "levi-open-mesh/1",
            "envelope_fields": [
                "protocol",
                "kind",
                "payload",
                "sender",
                "nonce",
                "timestamp",
            ],
            "capabilities": {
                name: cap.description for name, cap in self._capabilities.items()
            },
            "weights": {
                w.name: {"license": w.license, "family": w.family}
                for w in self.weights()
            },
            "closed_core": False,
        }
