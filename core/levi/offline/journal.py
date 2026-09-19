"""Interaction journal — the chain's local memory of its own turns.

Distinct from the growth journal (which logs *learnings*): this logs
*interactions* — what was asked (scrubbed), what answered, which backend,
what confidence, whether escalation was granted or denied. Local sqlite3,
stdlib only.

The studied MVP stored the same shape in SQLite but never enforced its
own retention setting; this journal enforces it: :meth:`Journal.purge`
deletes rows older than the policy's ``log_retention_days`` and returns
the count. :meth:`Journal.export_jsonl` writes a scrubbed training
corpus — secrets are scrubbed twice (at log time and at export time),
because one gate is a hope and two are a practice.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from .chain import ChainResult, scrub
from .gates import GatePolicy, default_policy

SCHEMA = """
CREATE TABLE IF NOT EXISTS offline_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    session TEXT NOT NULL DEFAULT 'default',
    prompt TEXT NOT NULL,
    context TEXT NOT NULL DEFAULT '',
    answer TEXT NOT NULL,
    backend TEXT NOT NULL,
    confidence REAL NOT NULL,
    escalated INTEGER NOT NULL DEFAULT 0,
    escalation_reason TEXT NOT NULL DEFAULT '',
    allow_cloud INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_offline_turns_ts ON offline_turns(ts);
CREATE INDEX IF NOT EXISTS idx_offline_turns_session ON offline_turns(session);
"""


class Journal:
    def __init__(self, path: str | Path, policy: Optional[GatePolicy] = None) -> None:
        self.path = Path(path)
        self.policy = policy or default_policy()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def log(
        self,
        result: ChainResult,
        prompt: str,
        context: str = "",
        session: str = "default",
        allow_cloud: bool = False,
    ) -> int:
        """Log one chain turn. Prompt/context/answer are scrubbed before write."""
        cur = self._conn.execute(
            """INSERT INTO offline_turns
               (ts, session, prompt, context, answer, backend, confidence,
                escalated, escalation_reason, allow_cloud)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                time.time(),
                session,
                scrub(prompt),
                scrub(context),
                scrub(result.answer.text),
                result.answer.backend,
                result.answer.confidence,
                1 if result.receipt.escalated else 0,
                result.receipt.escalation_reason,
                1 if allow_cloud else 0,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def purge(self, retention_days: Optional[int] = None) -> int:
        """Delete turns older than ``retention_days`` (policy default)."""
        days = (
            self.policy.log_retention_days if retention_days is None else retention_days
        )
        if days is None or days < 0:
            return 0
        cutoff = time.time() - days * 86400.0
        cur = self._conn.execute("DELETE FROM offline_turns WHERE ts < ?", (cutoff,))
        self._conn.commit()
        return cur.rowcount or 0

    def recent(self, limit: int = 20, session: Optional[str] = None) -> List[Dict]:
        q = "SELECT * FROM offline_turns"
        args: tuple = ()
        if session is not None:
            q += " WHERE session = ?"
            args = (session,)
        q += " ORDER BY id DESC LIMIT ?"
        rows = self._conn.execute(q, args + (limit,)).fetchall()
        cols = [c[1] for c in self._conn.execute("PRAGMA table_info(offline_turns)")]
        return [dict(zip(cols, r)) for r in rows]

    def export_jsonl(self, out: str | Path, limit: int = 5000) -> int:
        """Write a scrubbed fine-tune corpus: system/user/assistant messages."""
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = self._conn.execute(
            "SELECT prompt, answer FROM offline_turns ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        count = 0
        with out.open("w", encoding="utf-8") as fh:
            for prompt, answer in rows:
                rec = {
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are LEVI, a local-first synthetic intelligence.",
                        },
                        {"role": "user", "content": scrub(prompt)},
                        {"role": "assistant", "content": scrub(answer)},
                    ]
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                count += 1
        return count
