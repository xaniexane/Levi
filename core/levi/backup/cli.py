"""``levi backup`` CLI: snapshot / sync / status / configure / restore."""

from __future__ import annotations

import argparse

from .config import (
    load_config,
    load_state,
    rclone_available,
    save_config,
)
from .daily import run_daily
from .restore import restore_snapshot
from .snapshot import create_snapshot, list_snapshots, prune_local
from .sync import configured_remote, sync_snapshot, verify_remote


def register_backup_parser(sub) -> None:
    bk = sub.add_parser(
        "backup", help="encrypted off-machine backups of LEVI state (rclone)"
    )
    cmds = bk.add_subparsers(dest="backup_cmd")

    now_p = cmds.add_parser("now", help="snapshot now; sync if a remote is configured")
    now_p.add_argument("--remote", default=None, help="rclone crypt remote override")
    now_p.add_argument("--label", default=None, help="label appended to snapshot id")

    cmds.add_parser("status", help="show backup status")

    cfg_p = cmds.add_parser(
        "configure",
        help="set/verify the encrypted remote (Google Drive + crypt overlay; "
        "see docs/BACKUP.md for setup)",
    )
    cfg_p.add_argument("--remote", required=True, help="rclone crypt remote name")

    cmds.add_parser("daily", help="daily job: snapshot always, sync when configured")

    r_p = cmds.add_parser("restore", help="verify + stage (or apply) a snapshot")
    r_p.add_argument("--snapshot", required=True, help="snapshot id (timestamp)")
    r_p.add_argument(
        "--from-remote", action="store_true", help="download from the remote first"
    )
    r_p.add_argument("--apply", action="store_true", help="write into live state")
    r_p.add_argument("--yes", action="store_true", help="skip confirmation prompt")


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def cmd_backup(args: argparse.Namespace) -> int:
    cmd = getattr(args, "backup_cmd", None) or "status"
    if cmd == "now":
        return _cmd_now(args)
    if cmd == "status":
        return _cmd_status()
    if cmd == "configure":
        return _cmd_configure(args)
    if cmd == "daily":
        return _cmd_daily()
    if cmd == "restore":
        return _cmd_restore(args)
    print(f"unknown backup command: {cmd}")
    return 2


def _cmd_now(args: argparse.Namespace) -> int:
    snap = create_snapshot(label=getattr(args, "label", None))
    pruned = prune_local()
    print(
        f"snapshot {snap['snapshot_id']}: {snap['files']} files, "
        f"{_fmt_bytes(snap['total_bytes'])} -> {snap['tarball']}"
    )
    if pruned:
        print(f"pruned {len(pruned)} old snapshot(s), keeping the newest 14")

    remote = getattr(args, "remote", None) or configured_remote()
    if not remote:
        print(
            "no remote configured — snapshot kept locally only "
            "(levi backup configure --remote NAME)"
        )
        return 0
    res = sync_snapshot(snap["tarball"], snap["manifest"], remote=remote)
    print(res["message"])
    return 0 if res["ok"] else 1


def _cmd_status() -> int:
    state = load_state()
    cfg = load_config()
    print("LEVI backup status")
    print(
        f"  rclone: {'available' if rclone_available() else 'NOT INSTALLED (snapshots stay local)'}"
    )
    print(f"  configured remote: {cfg.get('remote') or '(none)'}")
    if cfg.get("remote"):
        ok, why = verify_remote()
        print(f"  remote check: {'OK — ' + why if ok else 'FAIL — ' + why}")
    last = state.get("last_snapshot")
    if last:
        print(
            f"  last snapshot: {last['snapshot_id']} "
            f"({last['files']} files, {_fmt_bytes(last['total_bytes'])})"
        )
    else:
        print("  last snapshot: (none yet — run: levi backup now)")
    if state.get("last_sync_utc"):
        print(f"  last successful sync: {state['last_sync_utc']}")
    elif state.get("last_sync_attempt_utc"):
        print(
            f"  last sync attempt: {state['last_sync_attempt_utc']} "
            f"— FAILED: {state.get('last_sync_error', '')[:120]}"
        )
    else:
        print("  last sync: (never)")
    snaps = list_snapshots()
    print(f"  local snapshots kept: {len(snaps)}")
    return 0


def _cmd_configure(args: argparse.Namespace) -> int:
    ok, why = verify_remote(args.remote)
    cfg = load_config()
    if ok:
        cfg["remote"] = args.remote
        save_config(cfg)
        print(f"configured remote '{args.remote}': {why}")
        return 0
    print(f"cannot configure '{args.remote}': {why}")
    print("See docs/BACKUP.md for the crypt-overlay setup walkthrough.")
    return 1


def _cmd_daily() -> int:
    report = run_daily()
    snap = report.get("snapshot")
    if snap:
        print(
            f"daily backup: snapshot {snap['snapshot_id']} "
            f"({snap['files']} files, {_fmt_bytes(snap['total_bytes'])})"
        )
    else:
        print(f"daily backup: snapshot FAILED — {report.get('snapshot_error')}")
        return 1
    if report.get("pruned"):
        print(f"pruned {len(report['pruned'])} old snapshot(s)")
    sync = report.get("sync") or {}
    print(f"sync: {sync.get('message', '(no sync info)')}")
    return 0 if snap else 1


def _cmd_restore(args: argparse.Namespace) -> int:
    try:
        res = restore_snapshot(
            args.snapshot,
            from_remote=args.from_remote,
            apply=args.apply,
            yes=args.yes,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"restore failed: {exc}")
        return 1
    print(res["message"])
    if res.get("applied"):
        print(f"safety snapshot: {res['safety_snapshot']}")
    return 0
