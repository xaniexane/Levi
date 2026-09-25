"""CLI: python -m levi.soxi.return_loop

Thin entry point over the SOXI return loop. Commands:

    intake  --file batch.jsonl [--manifest batch.manifest.json]
    verify  --batch <batch_id>
    refine  --batch <batch_id>
    promote --batch <batch_id>
    revert  --promotion <promotion_id>
    status
    sync-pack          # build the cloud-sync package (run when due)
    sync-status        # due? cadence, version vector
    cadence --days 3   # Chauncey's dial: 3 default, 1 for daily
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys


def cmd_intake(args) -> int:
    from levi.soxi.return_loop import intake

    rec = intake(args.file)
    print("intake: batch %s (%d bytes, teacher %s)" % (
        rec["batch_id"], rec["bytes"], rec["teacher"]))
    return 0


def cmd_verify(args) -> int:
    from levi.soxi.return_loop import verify_batch

    rec = verify_batch(args.batch)
    print("verify: %s -> %s (%d lessons, %d corrections, %d malformed)" % (
        rec["batch_id"], rec["verdict"], rec["lesson_count"],
        len(rec["corrections_needed"]), len(rec["malformed"])))
    if args.json:
        print(json.dumps(rec, indent=2))
    return 0


def cmd_refine(args) -> int:
    from levi.soxi.return_loop import refine_batch

    out = refine_batch(args.batch)
    print("refine: %s -> %d corrections" % (out["batch_id"], out["corrections"]))
    return 0


def cmd_promote(args) -> int:
    from levi.soxi.return_loop import promote_batch

    out = promote_batch(args.batch)
    print("promote: %s -> %s, %d lessons" % (
        out["batch_id"], out["promotion_id"], out["lessons_promoted"]))
    return 0


def cmd_revert(args) -> int:
    from levi.soxi.return_loop import revert_promotion

    out = revert_promotion(args.promotion)
    print("revert: %s, %d lessons reverted" % (
        out["promotion_id"], out["lessons_reverted"]))
    return 0


def cmd_status(args) -> int:
    from levi.soxi.return_loop import (
        base_dir, ready_batches, store_count, version_vector, get_config,
    )

    base = base_dir()
    print("return loop: %s" % base)
    print("store: %s" % store_count())
    print("cadence: every %s day(s)" % get_config()["cadence_days"])
    ready = ready_batches()
    print("batches awaiting verification: %d" % len(ready))
    for r in ready:
        print("  %s (%d bytes)" % (r["batch_id"], r["bytes"]))
    print("version vector: %s" % json.dumps(version_vector()))
    return 0


def cmd_sync_status(args) -> int:
    from levi.soxi.return_loop import sync_due

    due, info = sync_due()
    print("sync due: %s" % due)
    print(json.dumps(info, indent=2))
    return 0


def cmd_sync_pack(args) -> int:
    from levi.soxi.return_loop import build_package, roundtrip_ok
    from levi.soxi.return_loop import sync as _sync

    out = build_package()
    ok, msg = _sync.roundtrip_ok(out["path"])
    print("sync package: %s -> %s (%d deltas) [%s: %s]" % (
        out["package_id"], out["path"], out["delta_count"],
        "roundtrip ok" if ok else "ROUNDTRIP FAILED", msg))
    return 0 if ok else 1


def cmd_cadence(args) -> int:
    from levi.soxi.return_loop import set_cadence_days

    cfg = set_cadence_days(args.days)
    print("sync cadence: every %d day(s)" % cfg["cadence_days"])
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m levi.soxi.return_loop")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("intake")
    p.add_argument("--file", required=True)
    p.set_defaults(fn=cmd_intake)

    p = sub.add_parser("verify")
    p.add_argument("--batch", required=True)
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("refine")
    p.add_argument("--batch", required=True)
    p.set_defaults(fn=cmd_refine)

    p = sub.add_parser("promote")
    p.add_argument("--batch", required=True)
    p.set_defaults(fn=cmd_promote)

    p = sub.add_parser("revert")
    p.add_argument("--promotion", required=True)
    p.set_defaults(fn=cmd_revert)

    p = sub.add_parser("status")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("sync-status")
    p.set_defaults(fn=cmd_sync_status)

    p = sub.add_parser("sync-pack")
    p.set_defaults(fn=cmd_sync_pack)

    p = sub.add_parser("cadence")
    p.add_argument("--days", type=int, required=True)
    p.set_defaults(fn=cmd_cadence)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
