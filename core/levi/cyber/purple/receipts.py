"""Hash-chained run receipts. Every attempt leaves exactly one receipt.

Receipt kinds: DENIED (gate refused), STARTED, PHASE (per technique),
KILLED (kill-switch abort), COMPLETED, FINDING (summary counts only —
finding bodies live in the ExerciseResult, not the chain).

Each receipt embeds the sha256 of the previous receipt; verify() replays
the chain. Tampering with any receipt breaks every later hash.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


def _canonical(detail: dict) -> str:
    return json.dumps(detail, sort_keys=True, separators=(",", ":"))


def _hash(
    prev_hash: str, seq: int, kind: str, exercise_id: str, detail: dict, at: int
) -> str:
    body = "|".join(
        (prev_hash, str(seq), kind, exercise_id, _canonical(detail), str(at))
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Receipt:
    seq: int
    prev_hash: str
    hash: str
    kind: str
    exercise_id: str
    detail: dict
    at: int


class ReceiptLog:
    """Append-only receipt log. path=None keeps receipts in memory only."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._receipts: list[Receipt] = []
        if self._path is not None and self._path.exists():
            self._load()

    def _load(self) -> None:
        assert self._path is not None
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            self._receipts.append(Receipt(**record))

    def _persist(self, receipt: Receipt) -> None:
        assert self._path is not None
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "seq": receipt.seq,
                        "prev_hash": receipt.prev_hash,
                        "hash": receipt.hash,
                        "kind": receipt.kind,
                        "exercise_id": receipt.exercise_id,
                        "detail": receipt.detail,
                        "at": receipt.at,
                    },
                    sort_keys=True,
                )
                + "\n"
            )

    def append(self, kind: str, exercise_id: str, detail: dict, at: int) -> Receipt:
        prev_hash = self._receipts[-1].hash if self._receipts else "GENESIS"
        seq = len(self._receipts)
        receipt = Receipt(
            seq=seq,
            prev_hash=prev_hash,
            hash=_hash(prev_hash, seq, kind, exercise_id, detail, at),
            kind=kind,
            exercise_id=exercise_id,
            detail=detail,
            at=at,
        )
        self._receipts.append(receipt)
        if self._path is not None:
            self._persist(receipt)
        return receipt

    def verify(self) -> bool:
        """Replay the chain. True iff every hash links correctly."""
        prev = "GENESIS"
        for seq, receipt in enumerate(self._receipts):
            if receipt.seq != seq or receipt.prev_hash != prev:
                return False
            expect = _hash(
                receipt.prev_hash,
                receipt.seq,
                receipt.kind,
                receipt.exercise_id,
                receipt.detail,
                receipt.at,
            )
            if receipt.hash != expect:
                return False
            prev = receipt.hash
        return True

    def __len__(self) -> int:
        return len(self._receipts)

    def __iter__(self):
        return iter(self._receipts)
