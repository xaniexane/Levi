"""``levi sentinel`` CLI: defensive blue-team host tooling.

Read-only by default. Containment subcommands are dry-run previews
unless ``--confirm`` is given explicitly.
"""

from __future__ import annotations

import argparse
import json

from . import contain, forensics, integrity, triage, watch


def register_sentinel_parser(sub) -> None:
    sn = sub.add_parser(
        "sentinel",
        help="defensive host security: watch, integrity, triage, forensics",
    )
    cmds = sn.add_subparsers(dest="sentinel_cmd")

    w_p = cmds.add_parser("watch", help="run read-only detection sensors")
    w_p.add_argument("--log", default=None, help="auth log path override")

    i_p = cmds.add_parser("integrity", help="file-integrity baselines")
    i_p.add_argument(
        "action", choices=["create", "verify"], help="create or verify a baseline"
    )
    i_p.add_argument("--root", required=True, help="directory tree to baseline")
    i_p.add_argument(
        "--manifest", required=True, help="manifest file path (create or verify)"
    )

    t_p = cmds.add_parser("triage", help="defensive file triage scan")
    t_p.add_argument("--path", required=True, help="directory to scan")
    t_p.add_argument("--json", action="store_true", help="machine-readable output")

    c_p = cmds.add_parser("case", help="forensic case management")
    c_p.add_argument(
        "action",
        choices=["create", "log", "hash", "summary"],
        help="create a case / log custody event / hash evidence / write summary",
    )
    c_p.add_argument("--name", default=None, help="case name (create)")
    c_p.add_argument("--dir", default=None, help="case dir (log/hash/summary)")
    c_p.add_argument("--event", default=None, help="custody event text (log)")
    c_p.add_argument("--target", default=None, help="path to hash (hash)")

    k_p = cmds.add_parser("contain", help="HITL-gated defensive containment")
    k_p.add_argument(
        "action",
        choices=["block-ip", "terminate"],
        help="temporary IP block / process termination",
    )
    k_p.add_argument("--target", required=True, help="IPv4 address or PID")
    k_p.add_argument(
        "--confirm",
        action="store_true",
        help="explicit human confirmation — WITHOUT this, only a preview prints",
    )
    k_p.add_argument("--reason", default="", help="rationale recorded in the plan")


def cmd_sentinel(args: argparse.Namespace) -> int:
    cmd = getattr(args, "sentinel_cmd", None) or "watch"

    if cmd == "watch":
        report = watch.run_watch(getattr(args, "log", None))
        for sensor in report["sensors"]:
            status = "OK " if sensor["ok"] else "ALERT"
            print(f"[{status}] {sensor['sensor']}")
            for alert in sensor["alerts"]:
                print(f"       ! {alert}")
        print(
            f"\n{report['alert_count']} alert(s). Detection only — nothing was changed."
        )
        return 0

    if cmd == "integrity":
        action = args.action
        if action == "create":
            summary = integrity.create_baseline(args.root, args.manifest)
            print(f"baseline: {summary['files']} files → {summary['manifest']}")
            if summary["skipped"]:
                print(f"skipped: {summary['skipped']}")
            return 0
        diff = integrity.verify_baseline(args.root, args.manifest)
        if diff.clean:
            print("integrity: clean — no differences")
            return 0
        for rel in diff.added:
            print(f"  ADDED   {rel}")
        for rel in diff.removed:
            print(f"  REMOVED {rel}")
        for rel in diff.changed:
            print(f"  CHANGED {rel}")
        print("integrity: differences detected — triage before acting")
        return 2

    if cmd == "triage":
        report = triage.triage_scan(args.path)
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "scanned": report.scanned,
                        "hashed_only": report.hashed_only,
                        "by_severity": report.by_severity,
                        "findings": [
                            {
                                "path": f.path,
                                "rule": f.rule_id,
                                "severity": f.severity,
                                "note": f.note,
                                "sha256": f.sha256,
                            }
                            for f in report.findings
                        ],
                        "errors": report.errors,
                    },
                    indent=2,
                )
            )
            return 0
        print(
            f"triage: {report.scanned} files scanned ({report.hashed_only} hashed only)"
        )
        for finding in report.findings:
            print(f"  [{finding.severity.upper():6}] {finding.rule_id}: {finding.path}")
            print(f"           {finding.note}")
        if not report.findings:
            print("no signature hits — triage leads: none")
        return 0

    if cmd == "case":
        action = args.action
        if action == "create":
            if not args.name:
                print("usage: levi sentinel case create --name <name>")
                return 1
            case = forensics.create_case(args.name)
            print(f"case created: {case.path}")
            return 0
        if not args.dir:
            print("usage: levi sentinel case <log|hash|summary> --dir <case-dir>")
            return 1
        case = forensics.open_case(args.dir)
        if action == "log":
            case.log(args.event or "operator note")
            print("custody event recorded")
            return 0
        if action == "hash":
            if not args.target:
                print("usage: levi sentinel case hash --dir <case-dir> --target <path>")
                return 1
            hashes = case.hash_path(args.target)
            print(f"hashed {len(hashes)} file(s) into case exports")
            return 0
        summary = case.write_summary()
        print(f"summary written: {summary}")
        return 0

    if cmd == "contain":
        action = args.action
        target = args.target
        confirm = bool(getattr(args, "confirm", False))
        reason = getattr(args, "reason", "") or ""
        if action == "block-ip":
            plan = contain.plan_block_ip(target, rationale=reason)
        else:
            try:
                pid = int(target)
            except ValueError:
                print(f"not a PID: {target!r}")
                return 1
            plan = contain.plan_terminate_process(pid, rationale=reason)
        print(plan.preview())
        if not confirm:
            print("\nNo action taken (dry run). Re-run with --confirm to execute.")
            return 0
        try:
            receipt = contain.apply_plan(plan, confirm=True)
        except PermissionError as exc:
            print(str(exc))
            return 1
        print("\nreceipt:")
        print(json.dumps(receipt, indent=2))
        return 0 if receipt["verified"] else 3

    print(f"unknown sentinel command: {cmd}")
    return 1
