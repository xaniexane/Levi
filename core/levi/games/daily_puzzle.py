"""The Daily Cipher — a FOMO-free daily puzzle.

A monoalphabetic substitution cipher generated deterministically from the
date: everyone gets the same puzzle, no account, no leaderboard to buy
your way up. The anti-predatory design, point by point:

- misses never punish: any date's puzzle is catch-up-playable, forever;
- streaks only celebrate — nothing breaks, nothing locks;
- hints are free and unlimited (the pay-for-hints trade, inverted);
- no timers, no countdowns, no notifications-bait;
- fully offline, progress portable.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from levi.games.charter import GameManifest

MANIFEST = GameManifest(
    name="daily-cipher",
    progress_portable=True,
    hints_free=True,
    odds_declared=True,  # deterministic: no hidden chance at all
)

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Original phrases (written for LEVI — the cipher bank is our own words).
PHRASES = [
    "the patient machine keeps quiet time",
    "slow water carves the deepest canyon",
    "a lantern lit for no one still burns",
    "the archive remembers what the cloud forgot",
    "small hands build the tallest towers",
    "curiosity outlives every lock",
    "the garden grows whether or not you watch",
    "honest work needs no applause",
    "every map was once a blank page",
    "the river does not hurry to the sea",
    "a question asked twice is a door",
    "stars are patient with beginners",
    "the workshop hums after midnight",
    "paper remembers what screens erase",
    "kindness compounds like interest",
    "the lighthouse asks for nothing back",
    "begin again as many times as needed",
    "roots grow deepest in the dark",
    "the compass points even when ignored",
    "silence is also an answer",
]


def _rng_for(day: date) -> random.Random:
    seed = hashlib.sha256(("levi-daily-cipher|" + day.isoformat()).encode()).digest()
    return random.Random(int.from_bytes(seed, "big"))


def puzzle_for(day: date) -> Tuple[str, Dict[str, str]]:
    """Return (ciphered_text, cipher_alphabet) for a date. Deterministic."""
    rng = _rng_for(day)
    phrase = rng.choice(PHRASES).upper()
    plain = list(ALPHABET)
    ciphered = plain[:]
    rng.shuffle(ciphered)
    cipher = dict(zip(plain, ciphered, strict=True))
    ciphered_text = "".join(cipher.get(ch, ch) for ch in phrase)
    return ciphered_text, cipher


class CipherError(Exception):
    """Bad cipher input."""


@dataclass
class DailyCipher:
    day: date
    ciphered: str
    cipher: Dict[str, str]  # true mapping, plain -> cipher
    mapping: Dict[str, str] = field(default_factory=dict)  # cipher -> plain guess
    hints_used: int = 0
    guesses: int = 0

    @property
    def decoded(self) -> str:
        out = []
        for ch in self.ciphered:
            if ch in ALPHABET:
                out.append(self.mapping.get(ch, "_"))
            else:
                out.append(ch)
        return "".join(out)

    @property
    def true_plain(self) -> str:
        inv = {c: p for p, c in self.cipher.items()}
        return "".join(
            inv.get(ch, ch) if ch in ALPHABET else ch for ch in self.ciphered
        )

    def solved(self) -> bool:
        return self.decoded == self.true_plain

    def map(self, cipher_char: str, plain_char: str) -> None:
        c, p = cipher_char.upper(), plain_char.upper()
        if c not in ALPHABET or p not in ALPHABET:
            raise CipherError("map two letters, e.g. 'Q E' means Q decodes to E")
        if c not in self.ciphered:
            raise CipherError("%s does not appear in the cipher text" % c)
        self.mapping[c] = p
        self.guesses += 1

    def unmap(self, cipher_char: str) -> None:
        c = cipher_char.upper()
        if c in self.mapping:
            del self.mapping[c]

    def hint(self) -> Tuple[str, str]:
        """Reveal one true mapping. Free, unlimited — help is a kindness."""
        inv = {c: p for p, c in self.cipher.items()}
        for ch in self.ciphered:
            if ch in ALPHABET and self.mapping.get(ch) != inv[ch]:
                self.mapping[ch] = inv[ch]
                self.hints_used += 1
                return ch, inv[ch]
        raise CipherError("nothing left to hint — you have it all")

    def to_dict(self) -> Dict:
        return {
            "day": self.day.isoformat(),
            "ciphered": self.ciphered,
            "cipher": self.cipher,
            "mapping": self.mapping,
            "hints_used": self.hints_used,
            "guesses": self.guesses,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DailyCipher":
        return cls(
            day=date.fromisoformat(data["day"]),
            ciphered=data["ciphered"],
            cipher=dict(data["cipher"]),
            mapping=dict(data.get("mapping", {})),
            hints_used=int(data.get("hints_used", 0)),
            guesses=int(data.get("guesses", 0)),
        )


def new_cipher(day: Optional[date] = None) -> DailyCipher:
    day = day or date.today()
    ciphered, cipher = puzzle_for(day)
    return DailyCipher(day=day, ciphered=ciphered, cipher=cipher)


# ---------------------------------------------------------------------------
# Stats: celebrate, never punish
# ---------------------------------------------------------------------------


def _stats_path() -> Path:
    home = os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi")
    return Path(home) / "games" / "cipher_stats.jsonl"


def record_result(day: date, solved: bool, guesses: int, hints: int) -> None:
    path = _stats_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"day": day.isoformat(), "solved": solved, "guesses": guesses, "hints": hints}
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def stats() -> Dict:
    """Aggregate stats. Streaks are reported as celebration only; a missed
    day appears as nothing at all — there is no punishment to compute."""
    path = _stats_path()
    rows: List[Dict] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    solved_days = sorted(r["day"] for r in rows if r.get("solved"))
    streak = 0
    if solved_days:
        streak = 1
        for a, b in zip(reversed(solved_days), reversed(solved_days[1:]), strict=True):
            da, db = date.fromisoformat(a), date.fromisoformat(b)
            if (da - db).days == 1:
                streak += 1
            else:
                break
    return {
        "played": len(rows),
        "solved": len(solved_days),
        "current_streak": streak,  # celebration only; never a punishment
        "total_hints": sum(r.get("hints", 0) for r in rows),
    }


# ---------------------------------------------------------------------------
# Interactive play
# ---------------------------------------------------------------------------


def play(day: Optional[date] = None, store=None) -> None:
    from levi.games.saves import SaveStore

    store = store or SaveStore()
    target = day or date.today()
    slot = "cipher-" + target.isoformat()
    ciphered, cipher = puzzle_for(target)
    existing = store.list_slots("daily-cipher")
    if slot in existing:
        game = DailyCipher.from_dict(store.load("daily-cipher", slot))
    else:
        game = DailyCipher(day=target, ciphered=ciphered, cipher=cipher)

    print("DAILY CIPHER — %s" % target.isoformat())
    print(
        "A substitution cipher. Commands: map Q E | unmap Q | hint (free!) | "
        "save | quit"
    )
    print("Every date stays playable forever — miss a day, lose nothing.\n")

    while True:
        print("Cipher:  %s" % game.ciphered)
        print("Yours:   %s" % game.decoded)
        if game.solved():
            print(
                '\nSolved! "%s"  (guesses=%d, free hints=%d)'
                % (game.true_plain, game.guesses, game.hints_used)
            )
            record_result(target, True, game.guesses, game.hints_used)
            store.delete("daily-cipher", slot)
            return
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return
        parts = text.split()
        if not parts:
            continue
        cmd = parts[0].lower()
        if cmd in ("quit", "q", "exit"):
            record_result(target, False, game.guesses, game.hints_used)
            print("Saved nothing, lost nothing. The puzzle waits for you.")
            return
        if cmd == "save":
            store.save("daily-cipher", slot, game.to_dict())
            print(
                "Saved. Export any time: python -m levi.games saves export "
                "daily-cipher %s <file>" % slot
            )
            continue
        try:
            if cmd == "hint":
                c, p = game.hint()
                print("Free hint: %s decodes to %s" % (c, p))
            elif cmd == "map" and len(parts) == 3:
                game.map(parts[1], parts[2])
            elif cmd == "unmap" and len(parts) == 2:
                game.unmap(parts[1])
            else:
                print("Usage: map Q E | unmap Q | hint | save | quit")
        except CipherError as exc:
            print(exc)
