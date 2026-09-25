"""MOOD decoy — the fake admin surface. Open frame, canned inside (L2, L9).

A ``DecoySession`` looks like a system: it has a prompt, commands, files,
config, keys. None of it is real. Every response is a fixed template
chosen deterministically from the session seed (L8), every credential
is a documented canary (L5), and every response carries the MOOD tag (L7)
so decoy traffic can never be mistaken for genuine traffic.

The decoy NEVER reads real files, NEVER runs commands, NEVER opens a
socket, NEVER spawns a subprocess (L2). The most dangerous thing it can
do is return a string and record that it did.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from random import Random
from typing import Dict, List, Optional

from levi.mood.tripwires import TripEvent, TripwireRegistry

__all__ = [
    "CANNED_COMMANDS",
    "DecoyResponse",
    "DecoySession",
    "MOOD_TAG",
]

#: Every decoy response carries this tag (L7).
MOOD_TAG = "[MOOD-DECOY]"

#: Canned command outputs. Fixed templates; the seed only picks between
#: phrasing variants, never content from anywhere real (L8).
CANNED_COMMANDS: Dict[str, List[str]] = {
    "help": [
        "available: help ls whoami cat env keys status exit",
        "commands: help ls whoami cat env keys status exit (type one)",
    ],
    "ls": [
        "vault/  admin/  logs/  config/",
        "config/  vault/  admin/  keys/",
    ],
    "whoami": [
        "operator (decoy)",
        "decoy-operator",
    ],
    "cat config": [
        "[config]\nmode = decoy\nregion = nowhere\ncanary = levi_live_key_CANARY_MOOD_0000_fake",
        "[config]\nmode = decoy\nnote = nothing here is real\ncanary = sk-mood-CANARY-0000-fake-key",
    ],
    "env": [
        "LEVI_MODE=decoy\nLEVI_KEY=sk-mood-CANARY-0000-fake-key\nPATH=/fake/bin",
        "MODE=decoy\nDB_PASSWORD=mood_CANARY_0000_fake_password\nHOME=/fake/home",
    ],
    "keys": [
        "levi_live_key_CANARY_MOOD_0000_fake\nsess_CANARY_MOOD_0000_fake_token",
        "sk-mood-CANARY-0000-fake-key\nsess_CANARY_MOOD_0000_fake_token",
    ],
    "status": [
        "all systems nominal (decoy)",
        "decoy online; nothing real behind this prompt",
    ],
}


@dataclass
class DecoyResponse:
    """What the decoy said back. ``tripped`` is set when the action hit a
    wire; the caller then writes the receipt and enqueues the alert."""

    text: str
    tripped: bool = False
    trip: Optional[TripEvent] = None


class DecoySession:
    """One snooping session inside the decoy.

    ``session_id`` names the session, ``seed`` drives deterministic
    response selection (L8). The session holds a :class:`TripwireRegistry`
    and evaluates every action against it before answering.
    """

    def __init__(self, session_id: str, seed: int = 0) -> None:
        if not session_id:
            raise ValueError("session_id must be non-empty")
        self.session_id = session_id
        self.seed = seed
        # sha256-derived seed: stable across processes, unlike hash()
        # of a tuple (which is salted per process) — L8 holds everywhere.
        seed_material = "%s|%d" % (session_id, seed)
        seed_int = int(
            hashlib.sha256(seed_material.encode("utf-8")).hexdigest(), 16
        )
        self._rng = Random(seed_int)
        self._wires = TripwireRegistry()
        self._actions = 0

    # ------------------------------------------------------------------
    # Trap surface — readable, declared (L9).
    # ------------------------------------------------------------------

    @property
    def wires(self) -> TripwireRegistry:
        return self._wires

    @property
    def actions(self) -> int:
        return self._actions

    # ------------------------------------------------------------------
    # Handling — canned answers only, never real (L2, L8).
    # ------------------------------------------------------------------

    def handle(self, action: str) -> DecoyResponse:
        """Answer one action with canned content; trip on wires (L5)."""
        self._actions += 1
        event = self._wires.evaluate(self.session_id, action)
        text = self._canned(action)
        if event is not None:
            # The wire fired AND we still answer — the decoy never breaks
            # character; the trip is recorded by the caller, not shown.
            text = self._tripwire_canned(event)
        return DecoyResponse(
            text="%s %s" % (MOOD_TAG, text),
            tripped=event is not None,
            trip=event,
        )

    def _canned(self, action: str) -> str:
        key = action.strip().lower()
        variants = CANNED_COMMANDS.get(key)
        if variants is not None:
            return self._rng.choice(variants)
        # Unknown command: deterministic canned deflection, never an error
        # that leaks anything real.
        deflections = [
            "unknown command; try 'help'",
            "not recognized; 'help' lists commands",
            "decoy shell; 'help' for commands",
        ]
        return self._rng.choice(deflections)

    def _tripwire_canned(self, event: TripEvent) -> str:
        """Canned content served when a wire trips — fake, never real (L2)."""
        if event.kind.name == "TRIPWIRE_PATH":
            return (
                "[directory listing: secrets.txt (12B)]\n"
                "contents: levi_live_key_CANARY_MOOD_0000_fake"
            )
        if event.kind.name == "CANARY_TOKEN":
            return "token accepted (decoy): nothing happens. nothing is real here."
        return (
            "request noted. this console is a decoy; "
            "no such function exists."
        )
