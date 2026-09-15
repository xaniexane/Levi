"""Decision & execution ledger — Enterprise Phase 2 (blueprint §15).

Structured operational telemetry in SQLite (stdlib ``sqlite3``) at
``~/.levi/ledger/ledger.db``. This is NOT a chain-of-thought store: the
``decision_summary`` column holds a concise rationale or structured
explanation, never private hidden reasoning.

Schema (blueprint §15 fields):

* ``tasks`` — task id, user/tenant scope, objective, plan version, status,
  cost/latency totals.
* ``steps`` — one row per agent step: agent, category, model + version,
  tools used, decision summary, action, expected/actual result,
  verification result, error + recovery, outcome, cost, latency.
* ``feedback`` — user ratings / corrections per task.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks(
  task_id      TEXT PRIMARY KEY,
  user_id      TEXT NOT NULL DEFAULT 'local',
  tenant_id    TEXT NOT NULL DEFAULT 'local',
  objective    TEXT NOT NULL DEFAULT '',
  plan_version TEXT NOT NULL DEFAULT '1',
  status       TEXT NOT NULL DEFAULT 'running',
  cost_units   REAL NOT NULL DEFAULT 0,
  latency_ms   REAL NOT NULL DEFAULT 0,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS steps(
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id          TEXT NOT NULL,
  agent            TEXT NOT NULL DEFAULT '',
  category         TEXT NOT NULL DEFAULT '',
  task_class       TEXT NOT NULL DEFAULT '',
  model            TEXT NOT NULL DEFAULT '',
  model_version    TEXT NOT NULL DEFAULT '',
  tools_used       TEXT NOT NULL DEFAULT '[]',
  decision_summary TEXT NOT NULL DEFAULT '',
  action           TEXT NOT NULL DEFAULT '',
  expected_result  TEXT NOT NULL DEFAULT '',
  actual_result    TEXT NOT NULL DEFAULT '',
  verification     TEXT NOT NULL DEFAULT '{}',
  error            TEXT NOT NULL DEFAULT '',
  recovery         TEXT NOT NULL DEFAULT '',
  outcome          TEXT NOT NULL DEFAULT '',
  cost_units       REAL NOT NULL DEFAULT 0,
  latency_ms       REAL NOT NULL DEFAULT 0,
  created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_steps_task ON steps(task_id);
CREATE INDEX IF NOT EXISTS idx_steps_model_cat ON steps(model, category);
CREATE TABLE IF NOT EXISTS feedback(
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id    TEXT NOT NULL,
  rating     INTEGER NOT NULL DEFAULT 0,
  comment    TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_task ON feedback(task_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ledger_dir(home: Optional[Path] = None) -> Path:
    d = (home or Path.home()) / ".levi" / "ledger"
    d.mkdir(parents=True, exist_ok=True)
    return d


class LedgerWriter:
    """Append/query structured decision telemetry. Connections are
    short-lived (open per call) so readers and writers in different
    processes and threads stay safe."""

    def __init__(self, home: Optional[Path] = None) -> None:
        self._path = _ledger_dir(home) / "ledger.db"
        self._init()

    @property
    def path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            # Forward-compatible: older DBs gain new columns lazily.
            for ddl in (
                "ALTER TABLE steps ADD COLUMN task_class TEXT NOT NULL DEFAULT ''",
            ):
                try:
                    conn.execute(ddl)
                except sqlite3.OperationalError:
                    pass  # column already exists

    # -- writes ----------------------------------------------------------

    def record_task(self, task_id: str, objective: str = "",
                    user_id: str = "local", tenant_id: str = "local",
                    plan_version: str = "1",
                    status: str = "running") -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO tasks(task_id, user_id, tenant_id, objective,
                                     plan_version, status, created_at,
                                     updated_at)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(task_id) DO UPDATE SET
                     status=excluded.status, updated_at=excluded.updated_at""",
                (task_id, user_id, tenant_id, objective, plan_version,
                 status, now, now),
            )

    def set_task_status(self, task_id: str, status: str,
                        cost_units: float = 0.0,
                        latency_ms: float = 0.0) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE tasks SET status=?, cost_units=cost_units+?,
                   latency_ms=latency_ms+?, updated_at=? WHERE task_id=?""",
                (status, cost_units, latency_ms, _now(), task_id),
            )

    def record_step(self, task_id: str, *,
                    agent: str = "", category: str = "",
                    task_class: str = "",
                    model: str = "", model_version: str = "",
                    tools_used: Optional[List[str]] = None,
                    decision_summary: str = "", action: str = "",
                    expected_result: str = "", actual_result: str = "",
                    verification: Optional[Dict[str, Any]] = None,
                    error: str = "", recovery: str = "",
                    outcome: str = "", cost_units: float = 0.0,
                    latency_ms: float = 0.0) -> int:
        """Record one decision step.

        ``decision_summary`` is a concise rationale — never hidden
        chain-of-thought. Keep it to what a reviewer needs to understand
        why this action was chosen.
        """
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO steps(task_id, agent, category, task_class,
                                     model, model_version, tools_used,
                                     decision_summary, action,
                                     expected_result, actual_result,
                                     verification, error, recovery, outcome,
                                     cost_units, latency_ms, created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (task_id, agent, category, task_class, model, model_version,
                 json.dumps(tools_used or []),
                 decision_summary[:2000], action[:4000],
                 expected_result[:2000], actual_result[:4000],
                 json.dumps(verification or {}),
                 error[:2000], recovery[:2000], outcome,
                 cost_units, latency_ms, _now()),
            )
            return int(cur.lastrowid)

    def record_feedback(self, task_id: str, rating: int = 0,
                        comment: str = "") -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO feedback(task_id, rating, comment, created_at)"
                " VALUES(?,?,?,?)",
                (task_id, rating, comment[:2000], _now()),
            )
            return int(cur.lastrowid)

    # -- reads -----------------------------------------------------------

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                return None
            task = dict(row)
            steps = [dict(r) for r in conn.execute(
                "SELECT * FROM steps WHERE task_id=? ORDER BY id",
                (task_id,))]
            for s in steps:
                s["tools_used"] = json.loads(s["tools_used"])
                s["verification"] = json.loads(s["verification"])
            task["steps"] = steps
            task["feedback"] = [dict(r) for r in conn.execute(
                "SELECT * FROM feedback WHERE task_id=? ORDER BY id",
                (task_id,))]
            return task

    def stats(self) -> Dict[str, Any]:
        with self._connect() as conn:
            n_tasks = conn.execute(
                "SELECT COUNT(*) c FROM tasks").fetchone()["c"]
            n_steps = conn.execute(
                "SELECT COUNT(*) c FROM steps").fetchone()["c"]
            agg = conn.execute(
                "SELECT COALESCE(SUM(cost_units),0) cost,"
                " COALESCE(AVG(latency_ms),0) lat FROM steps").fetchone()
            outcomes = {
                r["outcome"]: r["c"] for r in conn.execute(
                    "SELECT outcome, COUNT(*) c FROM steps GROUP BY outcome")
            }
            by_model = {
                r["model"]: r["c"] for r in conn.execute(
                    "SELECT model, COUNT(*) c FROM steps GROUP BY model")
            }
            return {
                "tasks": n_tasks,
                "steps": n_steps,
                "total_cost_units": round(agg["cost"], 2),
                "avg_latency_ms": round(agg["lat"], 1),
                "outcomes": outcomes,
                "steps_by_model": by_model,
                "db": str(self._path),
            }

    def model_category_stats(self) -> List[Dict[str, Any]]:
        """Aggregates the AI router learns from: per (model, category)
        runs, success rate, and average cost. Only outcomes recorded as
        ``ok`` / ``ok_after_retry`` / ``completed`` count as success."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT model, category, task_class, COUNT(*) runs,
                          COALESCE(AVG(cost_units),0) avg_cost,
                          SUM(CASE WHEN outcome IN
                              ('ok','ok_after_retry','completed')
                              THEN 1 ELSE 0 END) successes
                   FROM steps
                   WHERE model != ''
                   GROUP BY model, category, task_class""").fetchall()
            return [dict(r) for r in rows]

    def recent_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT task_id, objective, status, cost_units, created_at"
                " FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,))]
