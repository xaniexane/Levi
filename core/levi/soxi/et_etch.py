"""ET — Etch Intelligence. Gets more valuable the more you delete.

Write-once memory: a principle, boundary, or memory you never want to lose
is appended to a hash-chained JSONL board. It cannot be edited — only
annotated (annotations are new records pointing at the old one).

Honest limit: anyone with disk access *can* rewrite the file; the hash
chain makes tampering *detectable* via verify(), not impossible. That is
still the right guarantee for a personal conscience board.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


def _hash(record: dict) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class EtchBoard:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "etch_board.jsonl"
        self.path.touch(exist_ok=True)

    def _records(self) -> list[dict]:
        out = []
        for line in self.path.read_text().splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def _append(self, kind: str, text: str, ref: int | None = None) -> dict:
        records = self._records()
        prev = records[-1]["hash"] if records else "GENESIS"
        record = {
            "seq": len(records),
            "ts": int(time.time()),
            "kind": kind,          # "law" | "memory" | "boundary" | "annotation"
            "text": text,
            "ref": ref,            # annotations point at a seq; else None
            "prev_hash": prev,
        }
        record["hash"] = _hash({k: v for k, v in record.items() if k != "hash"})
        with self.path.open("a") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def etch(self, text: str, kind: str = "law") -> dict:
        """Carve something unchangeable. kind: law | memory | boundary."""
        if kind not in ("law", "memory", "boundary"):
            raise ValueError(f"unknown etch kind: {kind}")
        return self._append(kind, text)

    def annotate(self, seq: int, note: str) -> dict:
        """Add context to an etching without altering it."""
        records = self._records()
        if not any(r["seq"] == seq for r in records):
            raise ValueError(f"no etching with seq={seq}")
        return self._append("annotation", note, ref=seq)

    def verify(self) -> tuple[bool, int | None]:
        """Walk the chain. Returns (ok, first_bad_seq)."""
        prev = "GENESIS"
        for r in self._records():
            if r["prev_hash"] != prev:
                return False, r["seq"]
            if r["hash"] != _hash({k: v for k, v in r.items() if k != "hash"}):
                return False, r["seq"]
            prev = r["hash"]
        return True, None

    def check_decision(self, text: str) -> list[dict]:
        """Flag etched laws/boundaries that share vocabulary with a decision.

        Heuristic, not judgment: surfaces what *might* conflict so you decide.
        """
        words = {w for w in text.lower().split() if len(w) > 3}
        hits = []
        for r in self._records():
            if r["kind"] not in ("law", "boundary"):
                continue
            rw = {w for w in r["text"].lower().split() if len(w) > 3}
            shared = words & rw
            if shared:
                hits.append({"seq": r["seq"], "text": r["text"], "shared": sorted(shared)})
        return hits

    def laws(self) -> list[dict]:
        return [r for r in self._records() if r["kind"] in ("law", "boundary")]
