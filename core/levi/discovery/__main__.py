"""CLI entry point for the discovery harness.

Usage::

    PYTHONPATH=core python3 -m levi.discovery run --pack curiosity --target operators
    PYTHONPATH=core python3 -m levi.discovery run --pack edges --target operators:local,nano-bit
    PYTHONPATH=core python3 -m levi.discovery packs
    PYTHONPATH=core python3 -m levi.discovery findings --significance notable

LATER STEP (not wired here): a sibling owns core/levi/cli/main.py, so
this module is deliberately NOT registered there. Wiring it in is a
one-line addition of a ``levi discovery`` subcommand delegating to
:func:`main` — do it when the CLI owner confirms, to avoid clobbering
their in-flight changes.

Targets: ``operators`` | ``operators:<name,...>`` | ``pack:<name>``
(registered in-process via --pack-json) | ``dw:<hex>`` (dynasty wave
agents, anonymized labels only; registered in-process).

Stdlib only. No network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Repo-relative import of the uninstalled core package (mirrors the
# tests' convention): <repo>/core must be importable as top-level.
_REPO_CORE = Path(__file__).resolve().parents[2]
if str(_REPO_CORE) not in sys.path:
    sys.path.insert(0, str(_REPO_CORE))

from levi.discovery import (  # noqa: E402
    DiscoveryHarness,
    list_packs,
)
from levi.discovery.findings import FindingsLog  # noqa: E402


def _build_harness(args: argparse.Namespace) -> DiscoveryHarness:
    harness = DiscoveryHarness(
        seed=args.seed,
        record_findings=not args.no_record,
    )
    if args.pack_json:
        data = json.loads(Path(args.pack_json).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SystemExit("--pack-json must contain a JSON object")
        name = Path(args.pack_json).stem
        harness.register_pack(name, data)
        args.targets.append(f"pack:{name}")
    return harness


def cmd_run(args: argparse.Namespace) -> int:
    harness = _build_harness(args)
    report = harness.run(args.pack, args.targets)
    print(report.summary())
    if args.verbose:
        for outcome in report.outcomes:
            status = "PASS" if outcome["passed"] else "FAIL"
            flag = " [BEYOND SCOPE]" if outcome.get("beyond_scope") else ""
            print(f"  {status}{flag} {outcome['probe_id']} -> {outcome['target_label']}")
            print(f"    {outcome['observation'][:220]}")
        for refusal in report.network_refusals:
            print(f"  REFUSED(net) {refusal['probe_id']} -> {refusal['target_label']}")
        for skip in report.skips:
            print(f"  SKIP {skip['probe_id']} -> {skip['target_label']}: {skip['reason'][:120]}")
    if report.finding_ids:
        print(f"findings recorded: {len(report.finding_ids)}")
        for fid in report.finding_ids:
            print(f"  {fid}")
    return 0 if report.errors == 0 else 1


def cmd_packs(args: argparse.Namespace) -> int:
    harness = DiscoveryHarness(record_findings=False)
    from levi.discovery import get_pack

    for name in harness.available_packs():
        probes = get_pack(name) if name in list_packs() else []
        print(f"{name} ({len(probes)} probes)")
        if args.verbose:
            for p in probes:
                net = " [needs_network]" if p.needs_network else ""
                print(f"  - {p.id}{net}: {p.description[:100]}")
    return 0


def cmd_findings(args: argparse.Namespace) -> int:
    log = FindingsLog()
    items = log.list(significance=args.significance, target_label=args.target)
    print(f"{len(items)} findings")
    for d in items[-args.limit :]:
        print(f"- [{d.significance}] {d.id} {d.target_label} {d.probe}")
        print(f"  {d.observation[:240]}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="levi.discovery",
        description="Sanctioned self-probing rig for LEVI's own systems (no network, in-process).",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run a probe pack against targets.")
    p_run.add_argument("--pack", required=True, help="Probe pack name.")
    p_run.add_argument(
        "--target",
        dest="targets",
        action="append",
        default=[],
        help="Target spec (repeatable): operators | operators:<names> | pack:<name> | dw:<hex>.",
    )
    p_run.add_argument("--seed", type=int, default=1337)
    p_run.add_argument("--no-record", action="store_true",
                       help="Do not write findings to the JSONL log.")
    p_run.add_argument("--pack-json", default=None,
                       help="Path to a pack-dict JSON file to register as a pack target.")
    p_run.add_argument("--verbose", "-v", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_packs = sub.add_parser("packs", help="List probe packs.")
    p_packs.add_argument("--verbose", "-v", action="store_true")
    p_packs.set_defaults(func=cmd_packs)

    p_find = sub.add_parser("findings", help="List recorded findings.")
    p_find.add_argument("--significance", default=None,
                        choices=["curiosity", "notable", "significant"])
    p_find.add_argument("--target", default=None)
    p_find.add_argument("--limit", type=int, default=20)
    p_find.set_defaults(func=cmd_findings)

    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "command", None) == "run" and not args.targets and not args.pack_json:
        raise SystemExit("run needs at least one --target (or --pack-json)")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
