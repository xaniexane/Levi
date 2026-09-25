"""TH — Threshold Intelligence. Speaks only on the third circle.

A counter with a payload: observe() an event, and only when the count
hits the threshold does it speak — once — then resets. For patterns that
deserve attention on repetition, not on first sight.
"""

from __future__ import annotations

import time
from pathlib import Path
import json


class Threshold:
    def __init__(self, data_dir: str | Path, name: str = "default", circles: int = 3):
        self.data_dir = Path(data_dir).expanduser() / "thresholds"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / f"{name}.json"
        self.circles = circles
        if self.path.exists():
            self._state = json.loads(self.path.read_text())
        else:
            self._state = {"count": 0, "events": []}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._state))

    def observe(self, event: str) -> dict:
        """Log an event. Speaks only when the circle completes."""
        self._state["count"] += 1
        self._state["events"].append({"ts": int(time.time()), "event": event})
        if self._state["count"] >= self.circles:
            events = self._state["events"]
            self._state = {"count": 0, "events": []}
            self._save()
            return {"spoke": True,
                    "message": f"Third circle: '{event}' has repeated {self.circles}x.",
                    "events": events}
        self._save()
        return {"spoke": False,
                "message": f"circle {self._state['count']}/{self.circles} — silent"}
