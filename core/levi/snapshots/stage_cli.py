"""CLI: stage snapshots — capture/diff/restore/fork/recreate/implement/verify.

Engine ops work on any payload; the academy subcommands save the boot
camp at named stages; the service subcommands run the ops-snapshot
legion service through the standard pipeline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from levi.snapshots.stages import (
    StageError,
    StageStore,
    diff_stages,
)


def _store(args) -> StageStore:
    home = getattr(args, "home", None)
    return StageStore(home=Path(home) if home else None)


def _print_snap(s) -> None:
    print(f"{s.id}  [{s.stage_label or '-'}] {s.name}  ({s.created_at})")
    if s.parent_id:
        print(f"    fork of {s.parent_id}")
    if s.note:
        print(f"    note: {s.note}")


def cmd_snapshot(args) -> int:
    """levi snapshot <subcommand> ..."""
    cmd = getattr(args, "snapshot_cmd", None) or "list"
    try:
        store = _store(args)
    except Exception as exc:
        print(f"refused: {exc}")
        return 1

    try:
        if cmd == "list":
            items = store.list_stages()
            if not items:
                print("No stage snapshots yet.")
                return 0
            for s in items:
                _print_snap(s)
            return 0

        if cmd == "capture":
            payload = json.loads(getattr(args, "payload_json", "{}") or "{}")
            snap = store.capture_stage(
                getattr(args, "name"),
                payload,
                stage_label=getattr(args, "stage", "") or "",
                note=getattr(args, "note", "") or "",
            )
            print(f"captured {snap.id} ({snap.name})")
            return 0

        if cmd == "diff":
            a_id = getattr(args, "a_id")
            b_id = getattr(args, "b_id")
            diffs = diff_stages(store, a_id, b_id)
            if not diffs:
                print("identical")
                return 0
            for d in diffs:
                print(f"{d['kind']:8} {d['path']}")
            print(f"{len(diffs)} difference(s)")
            return 0

        if cmd == "restore":
            target = store.restore_stage(getattr(args, "snapshot_id"), Path(getattr(args, "target")))
            print(f"restored to {target}")
            return 0

        if cmd == "fork":
            snap = store.fork_stage(
                getattr(args, "snapshot_id"),
                getattr(args, "name"),
                stage_label=getattr(args, "stage", "") or "",
                note=getattr(args, "note", "") or "",
            )
            print(f"forked {snap.id} (parent {snap.parent_id})")
            return 0

        if cmd == "recreate":
            dest = getattr(args, "dest", None)
            target = store.recreate_stage(
                getattr(args, "snapshot_id"), Path(dest) if dest else None
            )
            print(f"recreated at {target}")
            return 0

        if cmd == "implement":
            # Implement runs a named recipe over the payload. Recipes are
            # deliberately small and explicit — the engine never guesses.
            recipe = getattr(args, "recipe", "report")
            payload = store.materialize(getattr(args, "snapshot_id"))

            def _report(p):
                return {"keys": sorted(p.keys()), "snapshot_of": p.get("kind")}

            def _write_payload(p):
                out = Path(getattr(args, "out", "implemented.json"))
                out.write_text(json.dumps(p, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                return {"wrote": str(out)}

            recipes = {"report": _report, "write": _write_payload}
            if recipe not in recipes:
                print(f"unknown recipe {recipe!r}; one of {sorted(recipes)}")
                return 1
            result = store.implement_stage(getattr(args, "snapshot_id"), recipes[recipe])
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0

        if cmd == "verify":
            sid = getattr(args, "snapshot_id", None)
            if sid:
                store.verify_stage(sid)
                print(f"{sid}: seal + hash + chain link OK")
            else:
                n = store.verify_chain()
                print(f"chain OK: {n} snapshot(s) verified")
            return 0

        # -- academy: boot camp stages ----------------------------------
        if cmd == "stage-capture":
            from levi.snapshots.stage_academy import snapshot_bootcamp

            snap = snapshot_bootcamp(
                getattr(args, "stage"),
                note=getattr(args, "note", "") or "",
                home=Path(getattr(args, "home")) if getattr(args, "home", None) else None,
            )
            print(f"boot camp stage captured: {snap.id} ('{getattr(args, 'stage')}')")
            return 0

        if cmd == "stage-list":
            from levi.snapshots.stage_academy import list_bootcamp_stages

            items = list_bootcamp_stages(
                Path(getattr(args, "home")) if getattr(args, "home", None) else None
            )
            if not items:
                print("No boot camp stages captured yet.")
                return 0
            for s in items:
                _print_snap(s)
            return 0

        if cmd == "stage-diff":
            from levi.snapshots.stage_academy import diff_bootcamp_stages

            home = Path(getattr(args, "home")) if getattr(args, "home", None) else None
            diffs = diff_bootcamp_stages(getattr(args, "a_id"), getattr(args, "b_id"), home=home)
            if not diffs:
                print("identical")
                return 0
            for d in diffs:
                print(f"{d['kind']:8} {d['path']}")
            print(f"{len(diffs)} difference(s)")
            return 0

        if cmd == "stage-restore":
            from levi.snapshots.stage_academy import restore_bootcamp_stage

            home = Path(getattr(args, "home")) if getattr(args, "home", None) else None
            target = restore_bootcamp_stage(getattr(args, "snapshot_id"), Path(getattr(args, "target")), home=home)
            print(f"boot camp stage restored to {target}")
            return 0

        if cmd == "stage-fork":
            from levi.snapshots.stage_academy import fork_bootcamp_stage

            home = Path(getattr(args, "home")) if getattr(args, "home", None) else None
            snap = fork_bootcamp_stage(
                getattr(args, "snapshot_id"),
                getattr(args, "stage"),
                note=getattr(args, "note", "") or "",
                home=home,
            )
            print(f"boot camp stage forked: {snap.id} (parent {snap.parent_id})")
            return 0

        # -- service: ops-snapshot through the standard pipeline ---------
        if cmd == "service-offer":
            from levi.snapshots.stage_service import offer_snapshot_service

            home = Path(getattr(args, "home")) if getattr(args, "home", None) else None
            offering = offer_snapshot_service(
                provider=getattr(args, "provider") or "levi",
                title=getattr(args, "title"),
                subject=getattr(args, "subject"),
                scope=getattr(args, "scope", "") or "",
                client=getattr(args, "client", "") or "",
                home=home,
            )
            print(f"offered {offering.offering_id} [{offering.stage}]")
            return 0

        if cmd == "service-quote":
            from levi.snapshots.stage_service import quote_snapshot_service
            from levi.services.offering import ServiceStore

            home = Path(getattr(args, "home")) if getattr(args, "home", None) else None
            offering = ServiceStore(home=home).get(getattr(args, "offering_id"))
            if offering is None:
                print(f"unknown offering {getattr(args, 'offering_id')!r}")
                return 1
            giant = getattr(args, "giant_price", None)
            offering = quote_snapshot_service(
                offering,
                giant_price=float(giant) if giant else None,
                strategy=getattr(args, "strategy", "volume") or "volume",
                home=home,
            )
            print(f"quoted {offering.offering_id} [{offering.stage}]")
            return 0

        if cmd == "service-deliver":
            from levi.snapshots.stage_service import deliver_snapshot_service
            from levi.services.offering import ServiceStore

            home = Path(getattr(args, "home")) if getattr(args, "home", None) else None
            offering = ServiceStore(home=home).get(getattr(args, "offering_id"))
            if offering is None:
                print(f"unknown offering {getattr(args, 'offering_id')!r}")
                return 1
            receipt = deliver_snapshot_service(
                offering,
                subject_dir=Path(getattr(args, "subject_dir")),
                stage_label=getattr(args, "stage"),
                note=getattr(args, "note", "") or "",
                home=home,
            )
            print(json.dumps(receipt, indent=2, sort_keys=True))
            return 0

        print(f"unknown snapshot subcommand {cmd!r}")
        return 1
    except StageError as exc:
        print(f"refused: {exc}")
        return 1
    except Exception as exc:
        print(f"failed: {exc}")
        return 1


def _register_subcommands(csub) -> None:
    csub.add_parser("list", help="list stage snapshots")

    cap = csub.add_parser("capture", help="capture a JSON payload as a stage snapshot")
    cap.add_argument("name")
    cap.add_argument("--payload-json", default="{}", help="JSON payload")
    cap.add_argument("--stage", default="", help="stage label")
    cap.add_argument("--note", default="", help="note")

    d = csub.add_parser("diff", help="diff two stage snapshots")
    d.add_argument("a_id")
    d.add_argument("b_id")

    r = csub.add_parser("restore", help="restore a snapshot into a target dir")
    r.add_argument("snapshot_id")
    r.add_argument("target")

    f = csub.add_parser("fork", help="fork-and-refine: copy a snapshot as a new child")
    f.add_argument("snapshot_id")
    f.add_argument("name")
    f.add_argument("--stage", default="", help="stage label for the fork")
    f.add_argument("--note", default="", help="note")

    rec = csub.add_parser("recreate", help="recreate a snapshot into a fresh dir")
    rec.add_argument("snapshot_id")
    rec.add_argument("--dest", default=None, help="destination dir")

    imp = csub.add_parser("implement", help="implement a snapshot via a named recipe")
    imp.add_argument("snapshot_id")
    imp.add_argument("--recipe", default="report", help="report|write")
    imp.add_argument("--out", default="implemented.json", help="output for write recipe")

    v = csub.add_parser("verify", help="verify seal + chain (one snapshot or all)")
    v.add_argument("snapshot_id", nargs="?", default=None)

    sc = csub.add_parser("stage-capture", help="save the boot camp at a named stage")
    sc.add_argument("stage")
    sc.add_argument("--note", default="", help="note")

    csub.add_parser("stage-list", help="list boot camp stage snapshots")

    sd = csub.add_parser("stage-diff", help="diff two boot camp stages")
    sd.add_argument("a_id")
    sd.add_argument("b_id")

    sr = csub.add_parser("stage-restore", help="restore a boot camp stage to a dir")
    sr.add_argument("snapshot_id")
    sr.add_argument("target")

    sf = csub.add_parser("stage-fork", help="fork-and-refine a boot camp stage")
    sf.add_argument("snapshot_id")
    sf.add_argument("stage")
    sf.add_argument("--note", default="", help="note")

    so = csub.add_parser("service-offer", help="offer an ops-snapshot service")
    so.add_argument("provider")
    so.add_argument("title")
    so.add_argument("subject")
    so.add_argument("--scope", default="")
    so.add_argument("--client", default="")

    sq = csub.add_parser("service-quote", help="quote an ops-snapshot offering via the advisor")
    sq.add_argument("offering_id")
    sq.add_argument("--giant-price", default=None, help="giant's comparable price USD")
    sq.add_argument("--strategy", default="volume", help="volume|margin")

    sdl = csub.add_parser("service-deliver", help="deliver: snapshot the subject, emit receipt")
    sdl.add_argument("offering_id")
    sdl.add_argument("subject_dir")
    sdl.add_argument("stage")
    sdl.add_argument("--note", default="")


def register_snapshot_parser(sub) -> None:
    """Hook for the top-level `levi` CLI: adds the `snapshot` command."""
    p = sub.add_parser("snapshot", help="stage snapshots: capture/diff/restore/fork + ops-snapshot service")
    p.add_argument("--home", default=None, help="scope storage under this home dir")
    _register_subcommands(p.add_subparsers(dest="snapshot_cmd"))


def main(argv=None) -> int:
    top = argparse.ArgumentParser(prog="levi snapshot")
    top.add_argument("--home", default=None, help="scope storage under this home dir")
    _register_subcommands(top.add_subparsers(dest="snapshot_cmd"))
    args = top.parse_args(argv)
    return cmd_snapshot(args)


if __name__ == "__main__":
    raise SystemExit(main())
