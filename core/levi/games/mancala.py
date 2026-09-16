"""Mancala — the game grammar, honest edition.

Revives arch-games-mancala: mancala is not a game but a GAME GRAMMAR —
topology x sowing x capture compose thousands of games. This module is a
parametric engine: rules are data, games are instances.

All state is plain lists/dicts/ints — player-owned saves stay
JSON-serializable, per Charter rules 6 (progress portable) and 8 (no kill
switch).
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

SOWING_MODES = ("single", "multilap")
CAPTURE_MODES = ("none", "opposite", "last_seed")
GOALS = ("most_seeds", "first_empty")


class RulesError(ValueError):
    """Raised when a ruleset is invalid."""


class IllegalMove(ValueError):
    """Raised when a move is not legal in the current state."""


class CycleDetected(Exception):
    """Raised by validate_variant when self-play revisits a state."""


@dataclass(frozen=True)
class MancalaRules:
    """The grammar parameters. Two ranks default (Kalah-like)."""

    ranks: int = 2
    pits_per_rank: int = 6
    seeds_per_pit: int = 4
    sowing: str = "single"  # "single" | "multilap"
    capture: str = "opposite"  # "none" | "opposite" | "last_seed"
    goal: str = "most_seeds"  # "most_seeds" | "first_empty"

    def validate(self) -> None:
        if self.ranks != 2:
            raise RulesError("only 2-rank boards are supported (got %d)" % self.ranks)
        if not (2 <= self.pits_per_rank <= 12):
            raise RulesError("pits_per_rank must be 2..12")
        if not (1 <= self.seeds_per_pit <= 12):
            raise RulesError("seeds_per_pit must be 1..12")
        if self.sowing not in SOWING_MODES:
            raise RulesError("unknown sowing mode: %r" % self.sowing)
        if self.capture not in CAPTURE_MODES:
            raise RulesError("unknown capture mode: %r" % self.capture)
        if self.goal not in GOALS:
            raise RulesError("unknown goal: %r" % self.goal)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "MancalaRules":
        return cls(**{k: d[k] for k in asdict(cls()) if k in d})


# ---------------------------------------------------------------------------
# Variants (the honest-named classics)
# ---------------------------------------------------------------------------

VARIANTS: Dict[str, MancalaRules] = {
    "kalah": MancalaRules(
        ranks=2,
        pits_per_rank=6,
        seeds_per_pit=4,
        sowing="single",
        capture="opposite",
        goal="most_seeds",
    ),
    "oware": MancalaRules(
        ranks=2,
        pits_per_rank=6,
        seeds_per_pit=4,
        sowing="single",
        capture="last_seed",
        goal="most_seeds",
    ),
    # Real Omweso is 4x8 with complex sowing; a terminal-playable honest
    # remix is 2x8 multilap — named accordingly, never claiming to be Omweso.
    "omweso_lite": MancalaRules(
        ranks=2,
        pits_per_rank=8,
        seeds_per_pit=4,
        sowing="multilap",
        capture="none",
        goal="most_seeds",
    ),
}


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def new_state(rules: MancalaRules) -> Dict:
    """Fresh game state: plain lists/dicts/ints, JSON-serializable."""
    rules.validate()
    return {
        "rules": rules.to_dict(),
        "pits": [
            [rules.seeds_per_pit] * rules.pits_per_rank,
            [rules.seeds_per_pit] * rules.pits_per_rank,
        ],
        "stores": [0, 0],
        "turn": 0,
    }


def state_key(state: Dict) -> Tuple:
    """Hashable snapshot for cycle detection."""
    return (
        tuple(tuple(row) for row in state["pits"]),
        tuple(state["stores"]),
        state["turn"],
    )


# ---------------------------------------------------------------------------
# Rules of play
# ---------------------------------------------------------------------------


def legal_moves(state: Dict) -> List[int]:
    """Pit indices (own row) the player to move may play.

    Oware-style feeding rule: if the opponent's side is empty, and some
    legal move gives the opponent seeds, only those moves are legal.
    """
    rules = MancalaRules.from_dict(state["rules"])
    turn = state["turn"]
    own = state["pits"][turn]
    moves = [i for i, n in enumerate(own) if n > 0]
    opp = state["pits"][1 - turn]
    if all(n == 0 for n in opp):
        feeding = [m for m in moves if _feeds_opponent(state, rules, turn, m)]
        if feeding:
            return feeding
    return moves


def _feeds_opponent(state: Dict, rules: MancalaRules, turn: int, move: int) -> bool:
    """Would this move sow at least one seed into the opponent's row?"""
    p = rules.pits_per_rank
    seeds = state["pits"][turn][move]
    # Positions visited after the move, in ring order (see play()).
    pos = move
    for _ in range(seeds):
        pos += 1
        ring = 2 * p + 2
        if pos % ring == 2 * p + 1:  # skip opponent store
            pos += 1
        rpos = pos % ring
        if p + 1 <= rpos <= 2 * p:
            return True
    return False


def _drop(state: Dict, rules: MancalaRules, turn: int, move: int) -> Tuple[int, bool]:
    """Sow one lap from the move pit. Returns (last_ring_pos, landed_in_store)."""
    p = rules.pits_per_rank
    ring = 2 * p + 2
    own = state["pits"][turn]
    opp = state["pits"][1 - turn]
    hand = own[move]
    own[move] = 0
    pos = move
    last_in_store = False
    while hand > 0:
        pos += 1
        rpos = pos % ring
        if rpos == 2 * p + 1:  # opponent store: skip
            pos += 1
            rpos = pos % ring
        hand -= 1
        if rpos == p:
            state["stores"][turn] += 1
            last_in_store = hand == 0
        elif rpos < p:
            own[rpos] += 1
        else:
            opp[rpos - (p + 1)] += 1
    return pos % ring, last_in_store


def _opp_index(rules: MancalaRules, own_pit: int) -> int:
    """Opposite pit across the board."""
    return rules.pits_per_rank - 1 - own_pit


def _apply_capture(state: Dict, rules: MancalaRules, turn: int, last: int) -> None:
    p = rules.pits_per_rank
    own = state["pits"][turn]
    opp = state["pits"][1 - turn]
    if rules.capture == "opposite":
        # Kalah rule: last seed lands in a previously empty own pit.
        if last < p and own[last] == 1:
            oi = _opp_index(rules, last)
            if opp[oi] > 0:
                state["stores"][turn] += own[last] + opp[oi]
                own[last] = 0
                opp[oi] = 0
    elif rules.capture == "last_seed":
        # Oware-style: landing pit now holds exactly 2 or 3 seeds;
        # capture it and chain backwards through contiguous 2-or-3 pits.
        # Grand-slam guard: never take the opponent's very last seeds.
        chain: List[Tuple[int, int]] = []  # (row, pit)
        rpos = last
        while True:
            if rpos < p:
                row, pit = turn, rpos
            elif p + 1 <= rpos <= 2 * p:
                row, pit = 1 - turn, rpos - (p + 1)
            else:
                break  # landed in a store: no capture
            count = state["pits"][row][pit]
            if count not in (2, 3):
                break
            chain.append((row, pit))
            rpos -= 1
            if rpos < 0:
                break
        if chain:
            opp_seeds_total = sum(opp)
            captured_from_opp = sum(
                state["pits"][r][pt] for r, pt in chain if r != turn
            )
            if captured_from_opp < opp_seeds_total or opp_seeds_total == 0:
                for r, pt in chain:
                    state["stores"][turn] += state["pits"][r][pt]
                    state["pits"][r][pt] = 0
            # else: grand slam — capture denied, seeds stay


def play(state: Dict, move: int) -> Dict:
    """Apply a move; returns a NEW state dict (old state untouched)."""
    rules = MancalaRules.from_dict(state["rules"])
    rules.validate()
    turn = state["turn"]
    if move not in legal_moves(state):
        raise IllegalMove("pit %d is not a legal move" % move)
    ns = {
        "rules": state["rules"],
        "pits": [list(state["pits"][0]), list(state["pits"][1])],
        "stores": list(state["stores"]),
        "turn": turn,
    }
    p = rules.pits_per_rank
    last = -1
    if rules.sowing == "single":
        last, landed_in_store = _drop(ns, rules, turn, move)
        _apply_capture(ns, rules, turn, last)
        extra_turn = landed_in_store
    else:  # multilap: keep going while the landing pit is non-empty
        extra_turn = False
        pit_move = move
        while True:
            last, landed_in_store = _drop(ns, rules, turn, pit_move)
            if landed_in_store:
                extra_turn = True
                break
            if last < p:
                landing = ns["pits"][turn][last]
            elif p + 1 <= last <= 2 * p:
                landing = ns["pits"][1 - turn][last - (p + 1)]
            else:
                break
            if landing <= 1:
                break  # landed in an empty pit (now holding 1): stop
            pit_move = last if last < p else last - (p + 1)
            if last >= p + 1:
                # Landing on the opponent's side ends the lap in this remix.
                break
        _apply_capture(ns, rules, turn, last)
    if not extra_turn:
        ns["turn"] = 1 - turn
    return ns


def is_terminal(state: Dict) -> bool:
    """The game ends when either side's pits are all empty."""
    return any(all(n == 0 for n in row) for row in state["pits"])


def winner(state: Dict) -> Optional[int]:
    """0, 1, or None (tie). Sweeps remaining seeds to their stores first."""
    if not is_terminal(state):
        return None
    rules = MancalaRules.from_dict(state["rules"])
    stores = list(state["stores"])
    emptied_by = None
    for side in (0, 1):
        if all(n == 0 for n in state["pits"][side]):
            emptied_by = side if emptied_by is None else emptied_by
    for side in (0, 1):
        stores[side] += sum(state["pits"][side])
    if rules.goal == "first_empty":
        return emptied_by
    if stores[0] > stores[1]:
        return 0
    if stores[1] > stores[0]:
        return 1
    return None


def render(state: Dict) -> str:
    """Simple two-row ASCII board."""
    p0, p1 = state["pits"]
    s0, s1 = state["stores"]
    w = 4
    top = " ".join("%*d" % (w, n) for n in reversed(p1))
    bot = " ".join("%*d" % (w, n) for n in p0)
    return "   %s\n%2d %s %2d   (turn: P%d)" % (
        top,
        s1,
        " " * len(bot),
        s0,
        state["turn"],
    )


# ---------------------------------------------------------------------------
# Variant generation + validation
# ---------------------------------------------------------------------------


def _greedy_move(state: Dict) -> Optional[int]:
    """Simple greedy policy: maximize immediate store gain, tie-break by pit."""
    turn = state["turn"]
    moves = legal_moves(state)
    if not moves:
        return None
    best, best_gain = moves[0], -1
    for m in moves:
        try:
            ns = play(state, m)
        except IllegalMove:
            continue
        gain = ns["stores"][turn] - state["stores"][turn]
        if gain > best_gain:
            best, best_gain = m, gain
    return best


def validate_variant(rules: MancalaRules, max_plies: int = 400) -> int:
    """Self-play both sides with the greedy policy.

    Returns the number of plies played. Raises CycleDetected if a state
    repeats (infinite loop) or AssertionError if max_plies is exceeded.
    """
    rules.validate()
    state = new_state(rules)
    seen = {state_key(state)}
    plies = 0
    while not is_terminal(state):
        move = _greedy_move(state)
        if move is None:
            break
        state = play(state, move)
        plies += 1
        assert plies <= max_plies, "game did not terminate in %d plies" % max_plies
        key = state_key(state)
        if key in seen:
            raise CycleDetected("self-play revisited a state after %d plies" % plies)
        seen.add(key)
    return plies


def generate_variant(seed: int) -> MancalaRules:
    """Random grammar point, retried until it self-plays cleanly.

    Generation sticks to single-lap sowing (multilap can cycle under naive
    self-play); the multilap remix lives in VARIANTS as omweso_lite.
    """
    rng = random.Random(seed)
    for _attempt in range(50):
        rules = MancalaRules(
            ranks=2,
            pits_per_rank=rng.randint(3, 8),
            seeds_per_pit=rng.randint(2, 6),
            sowing="single",
            capture=rng.choice(list(CAPTURE_MODES)),
            goal=rng.choice(list(GOALS)),
        )
        try:
            validate_variant(rules)
        except (CycleDetected, AssertionError):
            continue
        return rules
    raise RulesError("no self-play-clean variant found in 50 attempts")
