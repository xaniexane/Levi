"""Turn Relay — the dead multiplayer ritual, reborn as a protocol.

The dead ritual: BBS door games (TradeWars, Legend of the Red Dragon) and
play-by-mail — asynchronous multiplayer before the internet made everyone
impatient. One player moves, the world waits, the next player moves. No
servers, no matchmaking, no accounts: just turns, passed hand to hand.

This is the LEVI-native remix: a tiny stdlib protocol for async turn
passing. A relay is a JSON file anyone can carry — email it, drop it in a
shared folder, print it. Each turn envelope is chained with SHA-256 to the
previous one, so tampering is evident and history is replayable from
genesis. Any turn-based game can ride on top; the relay itself is just the
honest postman.

Two players, one file, zero servers. The ritual, minus the BBS.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from levi.games.charter import GameManifest

MANIFEST = GameManifest(
    name="turn-relay",
    progress_portable=True,  # the relay file IS the save
    odds_declared=True,
    hints_free=True,
)


class RelayError(Exception):
    """Broken chain, wrong player, tampered history."""


def _envelope_hash(seq: int, player: str, move: Any, prev: str) -> str:
    body = json.dumps(
        {"seq": seq, "player": player, "move": move, "prev": prev},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass
class Relay:
    players: List[str]
    envelopes: List[Dict[str, Any]] = field(default_factory=list)

    # -- protocol ---------------------------------------------------------
    @property
    def turn(self) -> str:
        """Whose move it is. Genesis (no envelopes) belongs to players[0]."""
        return self.players[len(self.envelopes) % len(self.players)]

    @property
    def seq(self) -> int:
        return len(self.envelopes)

    def append(self, player: str, move: Any) -> Dict[str, Any]:
        """Append a turn envelope. Enforces turn order and chain integrity."""
        if player not in self.players:
            raise RelayError(
                "unknown player %r (relay: %s)" % (player, ", ".join(self.players))
            )
        if player != self.turn:
            raise RelayError("it is %s's turn, not %s's" % (self.turn, player))
        prev = self.envelopes[-1]["hash"] if self.envelopes else "GENESIS"
        env = {
            "seq": self.seq,
            "player": player,
            "move": move,
            "prev": prev,
            "hash": _envelope_hash(self.seq, player, move, prev),
        }
        self.envelopes.append(env)
        return env

    def verify(self) -> bool:
        """Replay the whole chain from genesis. False = tampered or broken."""
        prev = "GENESIS"
        for i, env in enumerate(self.envelopes):
            if env.get("seq") != i:
                return False
            if env.get("prev") != prev:
                return False
            if env.get("player") not in self.players:
                return False
            if env.get("hash") != _envelope_hash(
                i, env["player"], env.get("move"), prev
            ):
                return False
            prev = env["hash"]
        return True

    def history(self) -> List[Dict[str, Any]]:
        return [dict(e) for e in self.envelopes]

    # -- persistence: the file is the save --------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "players": list(self.players),
            "envelopes": [dict(e) for e in self.envelopes],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Relay":
        relay = cls(players=list(data["players"]))
        for env in data.get("envelopes", []):
            relay.envelopes.append(dict(env))
        if not relay.verify():
            raise RelayError(
                "relay file failed verification — history tampered or corrupt"
            )
        return relay

    def export(self, path: str) -> str:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, sort_keys=True)
            fh.write("\n")
        return path

    @classmethod
    def import_file(cls, path: str) -> "Relay":
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))


def new_relay(players: List[str]) -> Relay:
    if len(players) < 2:
        raise RelayError("a relay needs at least 2 players")
    if len(set(players)) != len(players):
        raise RelayError("player names must be unique")
    return Relay(players=list(players))


def describe(relay: Relay) -> str:
    lines = [
        "Turn Relay — %s" % " vs ".join(relay.players),
        "turns played: %d · next: %s · chain: %s"
        % (relay.seq, relay.turn, "VALID" if relay.verify() else "BROKEN"),
    ]
    for env in relay.envelopes[-8:]:
        move = env["move"]
        move_s = json.dumps(move, sort_keys=True) if not isinstance(move, str) else move
        lines.append("  #%d %-10s %s" % (env["seq"], env["player"], move_s[:70]))
    if relay.seq > 8:
        lines.append("  ... (%d earlier turns)" % (relay.seq - 8))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------


def _load(slot: str) -> Relay:
    from levi.games.saves import SaveStore

    return Relay.from_dict(SaveStore().load("turn-relay", slot))


def _save(relay: Relay, slot: str) -> None:
    from levi.games.saves import SaveStore

    SaveStore().save("turn-relay", slot, relay.to_dict())


def cmd(args) -> int:
    """relay <new|move|show|verify|export|import>."""
    slot = args.slot
    if args.action == "new":
        relay = new_relay(args.players)
        _save(relay, slot)
        print(
            "Relay opened: %s. %s moves first." % (", ".join(args.players), relay.turn)
        )
        print("Pass turns with: relay move <player> '<json move>'")
        return 0
    if args.action == "import":
        relay = Relay.import_file(args.file)
        _save(relay, slot)
        print("Relay imported and verified: %d turns." % relay.seq)
        return 0
    try:
        relay = _load(slot)
    except Exception:
        print("no relay in slot %r — start one with: relay new <p1> <p2> [...]" % slot)
        return 2
    if args.action == "show":
        print(describe(relay))
    elif args.action == "move":
        try:
            move = json.loads(args.move)
        except json.JSONDecodeError:
            move = args.move
        try:
            env = relay.append(args.player, move)
        except RelayError as exc:
            print("refused: %s" % exc)
            return 2
        _save(relay, slot)
        print(
            "turn #%d recorded for %s (chain hash %s…)"
            % (env["seq"], env["player"], env["hash"][:12])
        )
    elif args.action == "verify":
        print(
            "chain VALID — %d turns, untampered." % relay.seq
            if relay.verify()
            else "chain BROKEN — history does not verify."
        )
    elif args.action == "export":
        path = relay.export(args.file)
        print("relay exported to %s — carry it anywhere, it verifies itself." % path)
    else:
        print("unknown relay action")
        return 2
    return 0
