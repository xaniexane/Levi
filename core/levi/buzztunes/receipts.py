"""Honest receipts (L3) — every action leaves a record.

Append-only JSONL. Nothing is ever rewritten or deleted. A receipt
carries what happened, who did it, and a content hash so tampering
shows.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReceiptLog:
    def __init__(self, store_dir: str | Path) -> None:
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.store_dir / "receipts.jsonl"

    def emit(self, action: str, actor: str = "owner",
             details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = {
            "ts": _now_iso(),
            "action": action,
            "actor": actor,
            "details": details or {},
        }
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        body["receipt_id"] = f"bt-{digest}"
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(body) + "\n")
        return body

    def read_all(self) -> list:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def count(self) -> int:
        return len(self.read_all())
