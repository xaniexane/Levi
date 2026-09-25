"""Self-assigned addressing: conflict-probed address selection.

Studied from: protocols-hunt-20260916-0041 (Find 4 - AppleTalk section of report.md).
AppleTalk's AARP lets a new node pick its own address with no server and
no DHCP: it chooses an address at random, broadcasts conflict-probe
packets, and claims the address only if nobody objects. Collisions are
resolved by picking again.

This module simulates that dance on a local shared link: a Link models
the broadcast medium, nodes probe before claiming, and claiming an
address that survived the probe window is exclusive. Randomness is
seedable for deterministic tests; probe outcomes are synchronous, which
is the documented simulation boundary.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

__all__ = [
    "AddressError",
    "AddressInUse",
    "NoAddressAvailable",
    "Link",
    "SelfAddressedNode",
]

ORIGIN = "levi-revival/appletalk-aarp"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AddressError(Exception):
    """Base class for self-addressing failures."""


class AddressInUse(AddressError):
    """Another node already holds the probed address."""


class NoAddressAvailable(AddressError):
    """Too many collisions; the node gave up claiming an address."""


# ---------------------------------------------------------------------------
# Link: the shared broadcast medium
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Claim:
    node: str
    address: int


class Link:
    """The simulated shared link: a registry of claimed addresses.

    Probing is synchronous here: ``probe(address)`` returns True when some
    other claimant holds the address (a conflict), False when it is free.
    """

    def __init__(self, address_min: int = 1, address_max: int = 254) -> None:
        if address_min > address_max:
            raise ValueError("address_min must not exceed address_max")
        self._min = address_min
        self._max = address_max
        self._claims: dict[int, Claim] = {}

    @property
    def address_range(self) -> tuple[int, int]:
        return (self._min, self._max)

    def probe(self, address: int) -> bool:
        """True if the address is already claimed (a conflict was heard)."""
        return address in self._claims

    def claim(self, node: str, address: int) -> None:
        """Claim a probed-free address. Raises AddressInUse on a race."""
        if not (self._min <= address <= self._max):
            raise ValueError(f"address {address} outside link range")
        if address in self._claims:
            raise AddressInUse(
                f"address {address} already held by {self._claims[address].node!r}"
            )
        self._claims[address] = Claim(node=node, address=address)

    def release(self, node: str, address: int) -> None:
        claim = self._claims.get(address)
        if claim is not None and claim.node == node:
            del self._claims[address]

    def claimed(self) -> dict[int, str]:
        """Snapshot: address -> holding node name."""
        return {addr: claim.node for addr, claim in self._claims.items()}


# ---------------------------------------------------------------------------
# Node: pick, probe, claim, retry
# ---------------------------------------------------------------------------


class SelfAddressedNode:
    """A node that self-assigns an address on a Link via probe-and-claim."""

    def __init__(
        self,
        name: str,
        link: Link,
        max_attempts: int = 10,
        seed: int | None = None,
    ) -> None:
        if not name:
            raise ValueError("node name must be non-empty")
        self.name = name
        self.link = link
        self.max_attempts = max_attempts
        self.address: int | None = None
        self.probes_made = 0
        self._rng = random.Random(seed)

    def join(self) -> int:
        """Probe random addresses until one is free, then claim it.

        Raises NoAddressAvailable after ``max_attempts`` collisions.
        """
        if self.address is not None:
            return self.address
        lo, hi = self.link.address_range
        for _ in range(self.max_attempts):
            candidate = self._rng.randint(lo, hi)
            self.probes_made += 1
            if not self.link.probe(candidate):
                try:
                    self.link.claim(self.name, candidate)
                except AddressInUse:
                    continue  # lost a race; probe again
                self.address = candidate
                return candidate
        raise NoAddressAvailable(
            f"{self.name!r} failed to self-assign after {self.max_attempts} probes"
        )

    def leave(self) -> None:
        """Release the claimed address back to the link."""
        if self.address is not None:
            self.link.release(self.name, self.address)
            self.address = None
