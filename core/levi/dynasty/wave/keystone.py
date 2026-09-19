# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Keystone — the one-app shell. Plugin host loading Shell+Forge.

Keystone owns the graft host: third-party code loads only as signed,
sandboxed grafts against a documented contract, and the host keeps an
in-memory registry of graft descriptors (name/version/signed/
sandboxed). Cross-graft automation and AI wares ride the host, never
the grafts directly.

Unreplicable attribute — **tip-ordered ignition**: Keystone stores no
graft load order. At boot the ignition sequence is derived
deterministically from the live receipt-chain tip, so the order is
reproducible from the chain alone and any tampering with history
visibly reseats the load order.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.dynasty.dna import AgentError, DynastyAgent, scrub_text

__all__ = ["Keystone", "GraftHost"]

_GENESIS_TIP = "GENESIS"
_VERSION_RE = re.compile(r"^\d+\.\d+(\.\d+)?$")


class GraftHost:
    """In-memory registry of graft descriptors.

    A graft descriptor carries exactly ``name``, ``version``,
    ``signed`` and ``sandboxed``. Registration refuses unsigned or
    unsandboxed grafts — the third-party contract is enforced at the
    door, not documented and hoped for.
    """

    def __init__(self) -> None:
        self._grafts: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def register_graft(
        self, name: str, version: str, signed: bool, sandboxed: bool
    ) -> Dict[str, Any]:
        """Register a graft descriptor. Unsigned or unsandboxed grafts
        are refused; duplicates are refused."""
        if not isinstance(name, str) or not name.strip():
            raise AgentError("graft name must be a non-empty string")
        if not isinstance(version, str) or not _VERSION_RE.match(version):
            raise AgentError(
                "graft version must look like '1.2' or '1.2.3', "
                f"got {scrub_text(version)!r}"
            )
        if signed is not True:
            raise AgentError(
                f"graft {scrub_text(name)!r} refused: the host loads signed grafts only"
            )
        if sandboxed is not True:
            raise AgentError(
                f"graft {scrub_text(name)!r} refused: "
                "the host loads sandboxed grafts only"
            )
        descriptor = {
            "name": name.strip(),
            "version": version,
            "signed": True,
            "sandboxed": True,
        }
        with self._lock:
            if descriptor["name"] in self._grafts:
                raise AgentError(f"duplicate graft: {descriptor['name']!r}")
            self._grafts[descriptor["name"]] = dict(descriptor)
        return dict(descriptor)

    def list_grafts(self) -> List[Dict[str, Any]]:
        """Descriptors, sorted by name."""
        with self._lock:
            return [dict(self._grafts[k]) for k in sorted(self._grafts)]

    @staticmethod
    def ignition_order(names: List[str], tip: str) -> List[str]:
        """Derive the graft ignition order from a chain tip.

        Pure function of (names, tip): a deterministic permutation —
        no stored load order exists anywhere. The same tip always
        yields the same order; a different tip reseats it.
        """
        ordered = sorted(names)
        if not tip or not isinstance(tip, str):
            raise AgentError("ignition needs a non-empty chain tip")
        seed = int.from_bytes(hashlib.sha256(tip.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        rng.shuffle(ordered)
        return ordered


def _chain_tip(home: Path) -> str:
    """The current receipt-chain tip (last receipt hash), or GENESIS."""
    receipts_dir = home / "dynasty" / "receipts"
    if not receipts_dir.is_dir():
        return _GENESIS_TIP
    best: Optional[tuple] = None
    for path in receipts_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        seq = data.get("seq")
        rh = data.get("receipt_hash")
        if isinstance(seq, int) and isinstance(rh, str):
            if best is None or seq > best[0]:
                best = (seq, rh)
    return best[1] if best else _GENESIS_TIP


class Keystone(DynastyAgent):
    """The one-app shell: a graft host loading Shell+Forge first."""

    agent_id = "keystone"
    display_name = "Keystone"
    owns = "one-app shell"
    first_milestone = "plugin host loading Shell+Forge"
    proficiency = {"grafts": 10, "hosting": 9, "general": 6}
    specialties = [
        "graft host: signed, sandboxed plugin loading",
        "cross-graft automation and AI wares",
        "third-party graft contract enforcement",
    ]
    attributes = [
        {
            "name": "Tip-ordered ignition",
            "assertion": (
                "Keystone stores no graft load order: the ignition "
                "sequence is derived deterministically from the live "
                "receipt-chain tip at boot, reproducible from the chain "
                "alone, and any tampering with history visibly reseats it."
            ),
        }
    ]

    def __init__(self, home: Optional[Path] = None) -> None:
        super().__init__(home)
        self._host = GraftHost()
        # Per-agent seal lock: receipts.mint_receipt reads the chain to
        # pick the next seq, so concurrent do_task calls would mint
        # colliding sequences. The lock serializes sealing per agent.
        self._seal_lock = threading.Lock()

    def do_task(
        self, kind: str, payload: Dict[str, Any], task: str = "", verify: Any = None
    ) -> Dict[str, Any]:
        with self._seal_lock:
            return super().do_task(kind, payload, task=task, verify=verify)

    # -- domain -------------------------------------------------------
    @property
    def host(self) -> GraftHost:
        """This Keystone's in-memory graft host."""
        return self._host

    def ignition_order(self) -> List[str]:
        """Current ignition order for the registered grafts, derived
        from the live chain tip."""
        names = [g["name"] for g in self._host.list_grafts()]
        return GraftHost.ignition_order(names, _chain_tip(self._home))

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        shape = task.get("shape")
        if shape == "graft":
            op = task.get("op", "list")
            if op == "register":
                return {
                    "graft": self._host.register_graft(
                        task.get("name", ""),
                        task.get("version", ""),
                        task.get("signed", False),
                        task.get("sandboxed", False),
                    )
                }
            if op == "list":
                return {"grafts": self._host.list_grafts()}
            if op == "ignition":
                tip = _chain_tip(self._home)
                return {
                    "tip": tip[:16],
                    "ignition_order": self.ignition_order(),
                }
            raise AgentError(f"unknown graft op {scrub_text(str(op))!r}")
        return super().handle(task)

    # -- first green task ----------------------------------------------
    def first_task(self) -> Dict[str, Any]:
        """Register Shell+Forge as signed, sandboxed grafts; derive the
        ignition order from the chain tip; seal the receipt."""
        shell = self._host.register_graft("shell", "0.1.0", signed=True, sandboxed=True)
        forge = self._host.register_graft("forge", "0.1.0", signed=True, sandboxed=True)
        tip = _chain_tip(self._home)
        order = GraftHost.ignition_order([shell["name"], forge["name"]], tip)
        self.note(
            "graft host live: shell+forge registered, "
            f"ignition order {','.join(order)} from tip {tip[:16]}"
        )
        return self.do_task(
            "wave.first_task",
            {
                "agent": self.agent_id,
                "milestone": scrub_text(self.first_milestone),
                "grafts": [shell, forge],
                "chain_tip": tip,
                "ignition_order": order,
            },
            task="keystone:first",
        )
