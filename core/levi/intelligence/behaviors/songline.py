"""Songline — whale long-range acoustic protocol (class WHL, organ echo).

Real mechanism: humpback song carries over kilometers of ocean; low
bandwidth, high redundancy — themes repeat, units are stereotyped, and
the message survives a noisy channel because it is built to be heard
through water. Translated: a message codec with repetition redundancy —
encode a payload into repeated symbol phrases, decode by majority vote,
so the signal survives corruption the way song survives the sea.
"""

from __future__ import annotations

import random
from typing import List


def encode(message: str, repeats: int = 3) -> List[str]:
    """Encode a message as repeated symbol phrases (the song)."""
    assert repeats >= 1
    phrase = [f"unit:{ord(c):03d}" for c in message]
    song: List[str] = []
    for _ in range(repeats):
        song.extend(phrase)
        song.append("phrase_end")
    return song


def corrupt(song: List[str], flip_rate: float, seed: int = 0) -> List[str]:
    """Simulate a noisy ocean: randomly flip symbols (not phrase marks)."""
    rng = random.Random(seed)
    out = []
    for sym in song:
        if sym == "phrase_end" or rng.random() >= flip_rate:
            out.append(sym)
        else:
            out.append(f"unit:{rng.randint(0, 127):03d}")
    return out


def decode(song: List[str]) -> str:
    """Recover the message by majority vote across repeated phrases."""
    phrases: List[List[str]] = []
    current: List[str] = []
    for sym in song:
        if sym == "phrase_end":
            if current:
                phrases.append(current)
                current = []
        else:
            current.append(sym)
    if current:
        phrases.append(current)
    if not phrases:
        return ""
    width = max(len(p) for p in phrases)
    chars = []
    for i in range(width):
        votes = [p[i] for p in phrases if i < len(p) and p[i] != "phrase_end"]
        if not votes:
            continue
        winner = max(set(votes), key=votes.count)
        try:
            chars.append(chr(int(winner.split(":")[1])))
        except (ValueError, IndexError):
            continue
    return "".join(chars)
