"""XI — Gremlin Intelligence. The field lab for impossible-at-zero-cost turns.

Not a model: an experiment ledger for nano-operations — trivial,
composable turns (a 16-byte-ish state delta: what changed, nothing more).
Log the op, its measured cost, and what it proved. Bulk over cleverness:
ten thousand trivial turns beat one brilliant one when each costs ~nothing.

The Mogwai rule lives here as process: the gremlin stays small and
harmless-looking; it changes only when fed underestimation — i.e. every
time someone assumes a trivial turn can't matter, log that turn.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


class GremlinLab:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "gremlin_lab.jsonl"
        self.path.touch(exist_ok=True)

    def experiment(self, name: str, op: str, cost_note: str, result: str) -> dict:
        """Log one nano-operation experiment."""
        record = {
            "ts": int(time.time()),
            "name": name,
            "op": op,              # the trivial turn, stated plainly
            "cost": cost_note,     # measured, not theorized
            "result": result,      # what it proved
        }
        with self.path.open("a") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def ledger(self) -> list[dict]:
        return [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()]

    def summary(self) -> dict:
        entries = self.ledger()
        return {"experiments": len(entries),
                "names": sorted({e["name"] for e in entries})}
