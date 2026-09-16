"""CLI: python -m levi.backup

Thin entry point over the off-machine backup pipeline (snapshots of
~/.levi into hash-manifested tarballs, shipped via rclone crypt
overlay). Mirrors ``levi backup``.

Safety: `restore --apply` requires explicit --yes and stages a
safety snapshot first; without it the restore is verify+stage only.
"""

from __future__ import annotations

import argparse


def cmd_status(args) -> int:
    from levi.backup.snapshot import list_snapshots

    snaps = list_snapshots()
    print(f"local snapshots: {len(snaps)}")
    for s in snaps[:10]:
        print(
            f"  {s.get('snapshot_id')}: {s.get('total_bytes', 0)} bytes "
            f"{'complete' if s.get('complete') else 'INCOMPLETE'}"
        )
    return 0


def cmd_now(args) -> int:
    from levi.backup.snapshot import create_snapshot

    report = create_snapshot(label=args.label)
    print(
        f"snapshot {report['snapshot_id']} created "
        f"({report['total_bytes']} bytes, {report['files']} files)"
    )
    print(f"  tarball: {report['tarball']}")
    return 0


def cmd_daily(args) -> int:
    from levi.backup.daily import run_daily

    report = run_daily()
    snap = report.get("snapshot") or {}
    print(f"daily: snapshot={snap.get('snapshot_id') or report.get('snapshot_error')}")
    print(f"  pruned: {report.get('pruned')}")
    print(f"  sync: {report.get('sync')}")
    return 0


def cmd_verify(args) -> int:
    from levi.backup.snapshot import verify_snapshot

    ok, problems = verify_snapshot(args.snapshot)
    if ok:
        print(f"snapshot {args.snapshot}: OK")
        return 0
    print(f"snapshot {args.snapshot}: FAILED")
    for p in problems:
        print(f"  - {p}")
    return 1


def cmd_restore(args) -> int:
    from levi.backup.restore import restore_snapshot

    if args.apply and not args.yes:
        print(
            "restore --apply refused: pass --yes to confirm overwriting live state.",
        )
        return 2
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.backup",
        description="LEVI off-machine backup — snapshots via rclone crypt "
        "(mirrors `levi backup`)",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="list local snapshots").set_defaults(func=cmd_status)

    p_now = sub.add_parser("now", help="snapshot now (syncs if configured)")
    p_now.add_argument("--label", default=None)
    p_now.set_defaults(func=cmd_now)

    sub.add_parser("daily", help="the once-a-day job").set_defaults(func=cmd_daily)

    p_ver = sub.add_parser("verify", help="verify a snapshot's manifest")
    p_ver.add_argument("snapshot")
    p_ver.set_defaults(func=cmd_verify)

    p_res = sub.add_parser("restore", help="verify + stage (or apply) a snapshot")
    p_res.add_argument("snapshot")
    p_res.add_argument("--from-remote", action="store_true")
    p_res.add_argument(
        "--apply", action="store_true", help="apply to live state (needs --yes)"
    )
    p_res.add_argument(
        "--yes", action="store_true", help="explicit confirmation for --apply"
    )
    p_res.set_defaults(func=cmd_restore)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
