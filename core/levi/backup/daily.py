"""The once-a-day backup job: snapshot always, sync only when a remote is
configured. Sync failures are logged in state and retried on the next run;
nothing here ever raises out to the scheduler.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .config import load_state, save_state
from .snapshot import create_snapshot, prune_local
from .sync import configured_remote, rclone_available, sync_snapshot


def run_daily() -> dict:
    """Run the daily backup. Returns a report dict; never raises."""
    report: dict = {
        "ran_at_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot": None,
        "pruned": [],
        "sync": None,
    }
    try:
        snap = create_snapshot()
        report["snapshot"] = {
            "snapshot_id": snap["snapshot_id"],
            "files": snap["files"],
            "total_bytes": snap["total_bytes"],
        }
        report["pruned"] = prune_local()
    except Exception as exc:  # snapshot failure must not kill the job
        report["snapshot_error"] = str(exc)[:300]
        _record_daily(report)
        return report

    remote = configured_remote()
    if remote and rclone_available():
        try:
            report["sync"] = sync_snapshot(snap["tarball"], snap["manifest"])
        except Exception as exc:
            report["sync"] = {
                "ok": False,
                "synced": False,
                "message": f"sync raised: {exc}"[:300],
            }
    else:
        report["sync"] = {
            "ok": True,
            "synced": False,
            "message": "skipped: no remote configured or rclone missing "
            "(snapshot kept locally)",
        }
    _record_daily(report)
    return report


def _record_daily(report: dict) -> None:
    state = load_state()
    state["last_daily_utc"] = report["ran_at_utc"]
    state["last_daily_report"] = {k: v for k, v in report.items() if k != "ran_at_utc"}
    save_state(state)
