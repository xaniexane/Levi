"""WC — Witness Intelligence. Powerful because it says nothing for 30 days.

Append-only observation log. reveal() returns None until 30 days have
passed since the first entry — then the whole record, unedited. It is a
commitment device against recency bias: your past self testifying without
interruption from your present self.
"""

from __future__ import annotations

import time
from pathlib import Path

REVEAL_AFTER_S = 30 * 86400


class WitnessLog:
    def __init__(self, data_dir: str | Path, reveal_after_s: int = REVEAL_AFTER_S):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "witness.log"
        self.path.touch(exist_ok=True)
        self.reveal_after_s = reveal_after_s

    def observe(self, text: str) -> None:
        with self.path.open("a") as f:
            f.write(f"{int(time.time())} | {text}\n")

    def _entries(self) -> list[tuple[int, str]]:
        out = []
        for line in self.path.read_text().splitlines():
            if "|" in line:
                ts, text = line.split("|", 1)
                try:
                    out.append((int(ts.strip()), text.strip()))
                except ValueError:
                    continue
        return out

    def reveal(self) -> dict:
        """Return the record only after the silence period; else the countdown."""
        entries = self._entries()
        if not entries:
            return {"revealed": False, "reason": "nothing witnessed yet"}
        first = entries[0][0]
        now = int(time.time())
        if now - first < self.reveal_after_s:
            days_left = (self.reveal_after_s - (now - first)) / 86400
            return {"revealed": False,
                    "reason": f"silent for {days_left:.1f} more days",
                    "entries": len(entries)}
        return {"revealed": True, "entries": entries}
