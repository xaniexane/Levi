# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Gamemaster — the wave's AI gaming agent.

Owns "AI gaming". Runs deterministic automated mini-games (agents as
players and opponents), keeps a receipted competition ladder, and
schedules the ladder's fixtures from the sealed receipt chain itself:
the chain's own gravity deals the next match. Money stays paper at
this stage — entry fees and prizes are modeled, receipted, and never
real funds.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from levi.dynasty.dna import AgentError, DynastyAgent, scrub_text

__all__ = ["Gamemaster"]

_MAX_NAME_LEN = 64
_MAX_ROUNDS = 101
_FIXTURE_SALT = "gravity-fixture"


def _home() -> Path:
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".ladder-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, sort_keys=True, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.chmod(path, 0o600)


def _check_player_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise AgentError("player names must be non-empty strings")
    clean = name.strip()
    if len(clean) > _MAX_NAME_LEN:
        raise AgentError(f"player name too long (>{_MAX_NAME_LEN} chars)")
    if any(ord(c) < 32 for c in clean):
        raise AgentError("player name carries control characters")
    return scrub_text(clean)


def _check_seed(seed: Any) -> int:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise AgentError("seed must be an int")
    if not 0 <= seed <= 2**31 - 1:
        raise AgentError("seed out of range 0..2**31-1")
    return seed


def _check_rounds(rounds: Any) -> int:
    if isinstance(rounds, bool) or not isinstance(rounds, int):
        raise AgentError("rounds must be an int")
    if not 1 <= rounds <= _MAX_ROUNDS:
        raise AgentError(f"rounds out of range 1..{_MAX_ROUNDS}")
    return rounds


class Gamemaster(DynastyAgent):
    """Runs the games, keeps the ladder, deals the fixtures."""

    agent_id = "gamemaster"
    display_name = "Gamemaster"
    owns = "AI gaming"
    first_milestone = "first automated game + ladder"
    proficiency = {"gaming": 10, "ladders": 9, "general": 6}
    specialties = [
        "automated agent-vs-agent mini-games",
        "receipted competition ladders",
        "paper-mode entry fees and prizes",
    ]
    attributes = [
        {
            "name": "gravity fixture",
            "assertion": (
                "the ladder's next official fixture is dealt by the sealed "
                "receipt chain itself, not by any scheduler or hand: the "
                "same sealed history always deals the same fixture, a "
                "different history deals a different one, and there is no "
                "setter — fixtures cannot be assigned, only read."
            ),
        }
    ]

    def __init__(self, home: Optional[Path] = None) -> None:
        super().__init__(home)
        self._ladder_path = (
            (home or _home()) / "dynasty" / "agents" / self.agent_id / "ladder.json"
        )
        self._ladder_lock = threading.Lock()
        # PURGE-1: the shared receipt minter is not thread-safe (concurrent
        # minters can duplicate sequence numbers). Serialize task sealing
        # per agent instance until the DNA owns a lock of its own.
        self._task_lock = threading.Lock()

    def do_task(
        self,
        kind: str,
        payload: Dict[str, Any],
        task: str = "",
        verify: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        with self._task_lock:
            return super().do_task(kind, payload, task=task, verify=verify)

    # -- ladder state -------------------------------------------------
    def _read_ladder(self) -> Dict[str, Any]:
        if not self._ladder_path.exists():
            return {"players": {}, "matches": [], "last_receipt": None}
        try:
            data = json.loads(self._ladder_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise AgentError(f"ladder unreadable: {exc}") from exc
        if not isinstance(data, dict):
            raise AgentError("ladder corrupt: not a dict")
        data.setdefault("players", {})
        data.setdefault("matches", [])
        data.setdefault("last_receipt", None)
        return data

    def _write_ladder(self, data: Dict[str, Any]) -> None:
        _atomic_write_json(self._ladder_path, data)

    # -- the game: seeded dice duel -----------------------------------
    @staticmethod
    def _simulate(
        player_a: str, player_b: str, seed: int, rounds: int
    ) -> Dict[str, Any]:
        rng = random.Random(f"dice-duel|{seed}|{player_a}|{player_b}")
        a_wins = b_wins = 0
        rounds_log: List[Dict[str, Any]] = []
        for n in range(1, rounds + 1):
            roll_a = rng.randint(1, 6) + rng.randint(1, 6)
            roll_b = rng.randint(1, 6) + rng.randint(1, 6)
            if roll_a > roll_b:
                a_wins += 1
                winner: Optional[str] = player_a
            elif roll_b > roll_a:
                b_wins += 1
                winner = player_b
            else:
                winner = None
            rounds_log.append({"round": n, "a": roll_a, "b": roll_b, "winner": winner})
        if a_wins > b_wins:
            match_winner: Optional[str] = player_a
        elif b_wins > a_wins:
            match_winner = player_b
        else:
            match_winner = None
        return {
            "game": "dice-duel",
            "player_a": player_a,
            "player_b": player_b,
            "seed": seed,
            "rounds": rounds,
            "a_wins": a_wins,
            "b_wins": b_wins,
            "winner": match_winner,
            "round_log": rounds_log,
        }

    def play_match(
        self, player_a: str, player_b: str, seed: int = 0, rounds: int = 7
    ) -> Dict[str, Any]:
        """Play a deterministic dice duel, record it on the ladder."""
        a = _check_player_name(player_a)
        b = _check_player_name(player_b)
        if a == b:
            raise AgentError("a match needs two distinct players")
        seed = _check_seed(seed)
        rounds = _check_rounds(rounds)
        match = self._simulate(a, b, seed, rounds)
        with self._ladder_lock:
            ladder = self._read_ladder()
            players = ladder["players"]
            for name in (a, b):
                players.setdefault(
                    name, {"wins": 0, "losses": 0, "draws": 0, "gravity": 0}
                )
            if match["winner"] is None:
                players[a]["draws"] += 1
                players[b]["draws"] += 1
            else:
                loser = b if match["winner"] == a else a
                players[match["winner"]]["wins"] += 1
                players[loser]["losses"] += 1
                # chain weight: beating a proven contender pulls harder
                players[match["winner"]]["gravity"] += 1 + players[loser]["wins"]
            match_id = hashlib.sha256(
                json.dumps(match, sort_keys=True).encode("utf-8")
            ).hexdigest()[:16]
            ladder["matches"].append(
                {
                    "match_id": match_id,
                    "game": match["game"],
                    "player_a": a,
                    "player_b": b,
                    "seed": seed,
                    "rounds": rounds,
                    "winner": match["winner"],
                    "a_wins": match["a_wins"],
                    "b_wins": match["b_wins"],
                    "receipt": None,
                }
            )
            self._write_ladder(ladder)
        self.note(f"match played: {a} vs {b} seed={seed} winner={match['winner']}")
        return {k: v for k, v in match.items() if k != "round_log"} | {
            "match_id": match_id
        }

    def _note_fixture_receipt(self, receipt_hash: str) -> None:
        """Pin the sealed receipt that the next fixture derives from."""
        with self._ladder_lock:
            ladder = self._read_ladder()
            ladder["last_receipt"] = receipt_hash
            if ladder["matches"]:
                ladder["matches"][-1]["receipt"] = receipt_hash
            self._write_ladder(ladder)

    # -- the gravity fixture ------------------------------------------
    def next_pairing(self) -> Dict[str, str]:
        """Deal the ladder's next fixture from the sealed chain head.

        No arguments, no setter: the fixture is a read-only derivative
        of the sealed receipt history plus the contender set.
        """
        with self._ladder_lock:
            ladder = self._read_ladder()
        contenders = sorted(ladder["players"])
        if len(contenders) < 2:
            raise AgentError("need at least two contenders for a fixture")
        head = ladder.get("last_receipt")
        if not head:
            raise AgentError("no sealed match yet — play one first")
        digest = hashlib.sha256(
            f"{_FIXTURE_SALT}|{head}|{'|'.join(contenders)}".encode("utf-8")
        ).hexdigest()
        rotation = int(digest, 16) % len(contenders)
        order = contenders[rotation:] + contenders[:rotation]
        return {
            "player_a": order[0],
            "player_b": order[1],
            "derived_from": head,
        }

    def standings(self) -> List[Dict[str, Any]]:
        """Ladder standings, ordered by chain gravity, then wins."""
        with self._ladder_lock:
            players = self._read_ladder()["players"]
        rows = [{"player": name, **stats} for name, stats in players.items()]
        rows.sort(key=lambda r: (-r["gravity"], -r["wins"], r["player"]))
        return rows

    # -- domain dispatch ----------------------------------------------
    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        shape = task.get("shape", "echo")
        if shape == "play_match":
            players = task.get("players")
            if not isinstance(players, list) or len(players) != 2:
                raise AgentError("play_match needs players: [a, b]")
            return self.play_match(
                players[0],
                players[1],
                seed=task.get("seed", 0),
                rounds=task.get("rounds", 7),
            )
        if shape == "ladder":
            return {"standings": self.standings()}
        if shape == "next_pairing":
            return self.next_pairing()
        return super().handle(task)

    def act(self, task: Dict[str, Any]) -> Dict[str, Any]:
        receipt = super().act(task)
        if isinstance(task, dict) and task.get("shape") == "play_match":
            self._note_fixture_receipt(receipt["receipt_hash"])
        return receipt

    # -- first green task ----------------------------------------------
    def first_task(self) -> Dict[str, Any]:
        match = self.play_match("spar-one", "spar-two", seed=20260918, rounds=7)

        def verify(payload: Dict[str, Any]) -> None:
            rerun = self._simulate(
                match["player_a"], match["player_b"], match["seed"], match["rounds"]
            )
            if rerun["winner"] != match["winner"]:
                raise AgentError("match not reproducible from its seed")
            if payload.get("match", {}).get("match_id") != match["match_id"]:
                raise AgentError("match id drifted between play and seal")

        receipt = self.do_task(
            "wave.first_task",
            {
                "game": "dice-duel",
                "match": match,
                "ladder": self.standings(),
                "paper_mode": True,
            },
            task="gamemaster:first",
            verify=verify,
        )
        self._note_fixture_receipt(receipt["receipt_hash"])
        return receipt
