"""LN — Loom Router. Makes many small classes feel like one mind.

Routes a query to the class(es) that should handle it, keeps a win/loss
scoreboard per class so routing improves from experience, and degrades
honestly when offline: if a class needs the network, LN says so instead
of failing silently.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

# code, name, trigger keywords, needs_net
CLASS_SPECS = {
    "XI": ("Gremlin",   ["experiment", "try", "cheap", "bulk", "nano"], False),
    "FR": ("Friction",  ["rewrite", "like me", "my voice", "tone", "style", "fix this"], False),
    "GR": ("Gleaner",   ["where is", "find", "saw", "months ago", "connect", "remind me"], False),
    "SH": ("Shadow",    ["procrastinat", "stuck", "avoid", "quit", "abandon", "block"], False),
    "ET": ("Etch",      ["principle", "never", "always", "boundary", "value", "law", "should i"], False),
    "BT": ("Bent",      ["offline brain", "journal", "intuition", "fast answer"], False),
    "CV": ("Cadence",   ["mood", "emotion", "typing", "rhythm", "how am i"], False),
    "DR": ("Drift",     ["meant", "drift", "changed my mind", "used to"], False),
    "LN": ("Loom",      [], False),
    "RT": ("Root",      ["overnight", "morning", "shutdown", "dream"], False),
    "WC": ("Witness",   ["witness", "30 days", "silent", "observe"], False),
    "TH": ("Threshold", ["third", "threshold", "when ready", "circle"], False),
}

_WORD = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


class LoomRouter:
    """Keyword + scoreboard router. Pure stdlib, offline."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._board_path = self.data_dir / "loom_scoreboard.json"
        try:
            self._board = json.loads(self._board_path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            self._board = {}  # code -> {"win": n, "loss": n}

    def _save(self) -> None:
        self._board_path.write_text(json.dumps(self._board, indent=2))

    def record_outcome(self, code: str, won: bool) -> None:
        entry = self._board.setdefault(code, {"win": 0, "loss": 0})
        entry["win" if won else "loss"] += 1
        self._save()

    def _prior(self, code: str) -> float:
        e = self._board.get(code, {"win": 0, "loss": 0})
        total = e["win"] + e["loss"]
        if not total:
            return 0.0
        return (e["win"] - e["loss"]) / total  # -1..1

    def route(self, prompt: str, top: int = 3) -> list[tuple[str, float, str]]:
        """Return [(code, score, reason)] ranked best-first."""
        toks = _tokens(prompt)
        scored: list[tuple[str, float, str]] = []
        for code, (name, keywords, needs_net) in CLASS_SPECS.items():
            if code == "LN":
                continue
            hits = [k for k in keywords if k in prompt.lower() or any(k in t for t in toks)]
            score = len(hits) * 2.0 + self._prior(code)
            reason = f"keyword hits: {hits}" if hits else "no keyword hit; prior only"
            if needs_net:
                reason += " (needs network — offline, deprioritized)"
                score -= 5.0
            scored.append((code, score, reason))
        scored.sort(key=lambda r: r[1], reverse=True)
        return scored[:top]

    def status(self) -> dict:
        return {
            "classes": len(CLASS_SPECS),
            "scoreboard": self._board,
            "ts": int(time.time()),
        }
