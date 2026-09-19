"""NeighborOS CLI — `levi neighbor`.

The Site Lift's operator surface: post work, register workers, match
transparently, run the proof-of-work stream, settle on the ledger,
export portable passports. Consequential commands need `--yes`
(Permission step) and print their preview first.
"""

from __future__ import annotations

import argparse
import json

from . import lift, monetize, pay, policies as policies_mod, post, work
from .store import Store


def _store(args) -> Store:
    return Store(getattr(args, "dir", None))


def _emit(obj) -> int:
    if isinstance(obj, str):
        print(obj)
    else:
        print(json.dumps(obj, indent=2, sort_keys=True, default=str))
    return 0


# -- post -----------------------------------------------------------------
def _cmd_post(args) -> int:
    store = _store(args)
    gig = post.draft_gig(
        title=args.title,
        category=args.category,
        description=args.description or "",
        requester=args.requester,
        requester_contact=args.contact,
        neighborhood_cell=args.cell,
        estimate=args.estimate,
    )
    print(post.preview_gig(store, gig))
    if not args.yes:
        print("\n(dry run — pass --yes to publish)")
        return 0
    published = post.publish_gig(store, gig, confirm=True)
    print(f"published {published['id']} (status: open)")
    return 0


# -- worker ---------------------------------------------------------------
def _cmd_worker(args) -> int:
    store = _store(args)
    if args.worker_cmd == "register":
        w = work.register_worker(
            store,
            name=args.name,
            contact=args.contact,
            categories=[
                c.strip() for c in (args.categories or "").split(",") if c.strip()
            ],
            home_cell=args.cell,
        )
        print(f"registered {w['id']} — {w['name']} <{w['contact']}>")
        return 0
    if args.worker_cmd == "credential":
        claim = {
            "type": args.type,
            "issuer": args.issuer,
            "evidence": args.evidence or "",
        }
        w = work.add_credential(store, args.worker, claim)
        print(
            f"credential recorded as claim with provenance on {w['id']} (verified_by_us: false)"
        )
        return 0
    if args.worker_cmd == "available":
        w = work.set_availability(store, args.worker, args.on)
        print(f"{w['id']} available={w['available']}")
        return 0
    return 2


# -- dispatch (the Lift) ----------------------------------------------------
def _cmd_match(args) -> int:
    store = _store(args)
    for c in lift.explain_dispatch(store, args.gig, limit=args.limit):
        print(
            f"\n{c['worker_name']} ({c['worker_id']}) <{c['worker_contact']}> — {c['score']}/{c['max_score']}"
        )
        for b in c["breakdown"]:
            mark = "+" if b["matched"] else "·"
            print(f"  {mark} {b['rule']}: {b['explanation']}")
    return 0


def _cmd_offer(args) -> int:
    store = _store(args)
    try:
        receipt = lift.offer(
            store,
            args.gig,
            args.worker,
            operator=args.operator,
            confirm=args.yes,
            override_gate=args.override_gate,
        )
    except PermissionError as exc:
        print(f"refused: {exc}")
        return 2
    print(receipt["preview"])
    print(
        f"\noffer executed and verified: {receipt['verified']} (gate: {receipt['gate']['stage']})"
    )
    return 0


def _cmd_accept(args) -> int:
    store = _store(args)
    g = lift.accept_offer(store, args.gig, args.worker)
    print(f"{args.gig} accepted by {args.worker} (status: {g['status']})")
    return 0


# -- proof of work ------------------------------------------------------------
def _cmd_proof(args) -> int:
    store = _store(args)
    if args.proof_cmd == "checkin":
        work.check_in(store, args.gig, args.worker)
        print(f"{args.gig}: checked in (in_progress)")
    elif args.proof_cmd == "checkout":
        work.check_out(store, args.gig, args.worker)
        print(f"{args.gig}: checked out — awaiting customer sign-off")
    elif args.proof_cmd == "signoff":
        work.sign_off(
            store, args.gig, args.requester, args.rating, final_amount=args.amount
        )
        print(f"{args.gig}: signed off, rating {args.rating}/5 (done)")
    return 0


# -- pay ----------------------------------------------------------------------
def _cmd_settle(args) -> int:
    store = _store(args)
    plan = pay.plan_settlement(
        store, args.gig, args.amount, emergency=args.emergency, pro_worker=args.pro
    )
    print(pay.preview_settlement(plan))
    if not args.yes:
        print("\n(dry run — pass --yes to write the settlement)")
        return 0
    entry = pay.settle(
        store,
        args.gig,
        args.amount,
        rail=args.rail,
        rail_reference=args.ref,
        confirm=True,
        emergency=args.emergency,
        pro_worker=args.pro,
    )
    print()
    print(pay.receipt_text(store, entry))
    return 0


def _cmd_dispute(args) -> int:
    store = _store(args)
    if args.dispute_cmd == "raise":
        d = work.dispute(store, args.gig, args.by, args.reason)
        print(
            f"dispute {d['id']} opened — settlement on {args.gig} FROZEN, routed to human"
        )
    elif args.dispute_cmd == "resolve":
        d = work.resolve_dispute(
            store, args.dispute, args.outcome, args.by, note=args.note or ""
        )
        print(
            f"dispute {args.dispute} resolved: {args.outcome} (decided by {args.by}, a human)"
        )
    elif args.dispute_cmd == "list":
        for d in work.open_disputes(store):
            print(
                f"{d['id']}: gig {d['gig_id']} — {d['reason']} (raised by {d['raised_by']})"
            )
    return 0


# -- lift: passport / gates / integrity -----------------------------------------
def _cmd_passport(args) -> int:
    store = _store(args)
    if args.passport_cmd == "export":
        result = lift.export_passport(store, args.worker, dest=args.dest)
        print(f"passport exported → {result['path']}")
        print(f"content hash: {result['passport']['content_hash']}")
        print("the worker owns this file — portable, never held hostage")
    elif args.passport_cmd == "verify":
        data = lift.import_passport(args.path)
        print(f"passport verified: {data['worker']['name']} ({data['worker']['id']})")
        print(
            f"jobs completed: {data['proof_of_work']['jobs_completed']}, "
            f"rating: {data['proof_of_work']['average_rating']}"
        )
    return 0


def _cmd_gates(args) -> int:
    return _emit(lift.gates_status(_store(args)))


def _cmd_integrity(args) -> int:
    report = lift.platform_integrity_report(_store(args))
    for name, check in report["checks"].items():
        print(f"{'OK ' if check['ok'] else 'FAIL'}  {name}")
        for key, val in check.items():
            if key != "ok" and val:
                print(f"        {key}: {val}")
    print(f"\nplatform integrity: {'OK' if report['ok'] else 'FAILED'}")
    return 0 if report["ok"] else 1


def _register_commands(cmds) -> None:
    """Register post/worker/match/… on an argparse subparsers action."""

    p = cmds.add_parser("post", help="draft, preview, and publish a gig")
    p.add_argument("--title", required=True)
    p.add_argument("--category", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--requester", required=True)
    p.add_argument(
        "--contact", required=True, help="requester contact — plain, shown to worker"
    )
    p.add_argument("--cell", required=True, help="neighborhood cell")
    p.add_argument("--estimate", type=float, default=None)
    p.add_argument("--yes", action="store_true", help="Permission: publish it")

    w = cmds.add_parser("worker", help="worker registry")
    wc = w.add_subparsers(dest="worker_cmd")
    wr = wc.add_parser("register", help="register a worker")
    wr.add_argument("--name", required=True)
    wr.add_argument(
        "--contact", required=True, help="worker contact — plain, shown to requester"
    )
    wr.add_argument("--categories", default="")
    wr.add_argument("--cell", required=True)
    wcr = wc.add_parser(
        "credential", help="record a credential claim (with provenance)"
    )
    wcr.add_argument("--worker", required=True)
    wcr.add_argument("--type", required=True)
    wcr.add_argument("--issuer", required=True)
    wcr.add_argument("--evidence", default="")
    wa = wc.add_parser("available", help="set availability")
    wa.add_argument("--worker", required=True)
    wa.add_argument("--on", action=argparse.BooleanOptionalAction, default=True)

    m = cmds.add_parser(
        "match", help="transparent dispatch: ranked, explained candidates"
    )
    m.add_argument("--gig", required=True)
    m.add_argument("--limit", type=int, default=5)

    o = cmds.add_parser("offer", help="offer a gig to a worker (Plan→…→Receipt)")
    o.add_argument("--gig", required=True)
    o.add_argument("--worker", required=True)
    o.add_argument("--operator", required=True)
    o.add_argument("--yes", action="store_true", help="Permission: execute the offer")
    o.add_argument("--override-gate", action="store_true", help="logged gate override")

    a = cmds.add_parser("accept", help="worker accepts an offer")
    a.add_argument("--gig", required=True)
    a.add_argument("--worker", required=True)

    pr = cmds.add_parser("proof", help="proof-of-work stream")
    prc = pr.add_subparsers(dest="proof_cmd")
    for name in ("checkin", "checkout"):
        sp = prc.add_parser(name)
        sp.add_argument("--gig", required=True)
        sp.add_argument("--worker", required=True)
    so = prc.add_parser("signoff", help="customer sign-off (Verify)")
    so.add_argument("--gig", required=True)
    so.add_argument("--requester", required=True)
    so.add_argument("--rating", type=int, required=True)
    so.add_argument("--amount", type=float, default=None, help="final paid amount")

    s = cmds.add_parser("settle", help="NeighborPay settlement ledger entry")
    s.add_argument("--gig", required=True)
    s.add_argument("--amount", type=float, required=True)
    s.add_argument(
        "--rail", required=True, help="EXTERNAL plug-in that moved the money"
    )
    s.add_argument("--ref", required=True, help="the rail's reference")
    s.add_argument(
        "--yes", action="store_true", help="Permission: write the settlement"
    )
    s.add_argument("--emergency", action="store_true")
    s.add_argument("--pro", action="store_true", help="pro worker commission reduction")

    d = cmds.add_parser("dispute", help="disputes freeze settlement, route to a human")
    dc = d.add_subparsers(dest="dispute_cmd")
    dr = dc.add_parser("raise")
    dr.add_argument("--gig", required=True)
    dr.add_argument("--by", required=True)
    dr.add_argument("--reason", required=True)
    dres = dc.add_parser("resolve")
    dres.add_argument("--dispute", required=True)
    dres.add_argument("--outcome", required=True, choices=["release", "void"])
    dres.add_argument("--by", required=True, help="human decider")
    dres.add_argument("--note", default="")
    dc.add_parser("list")

    pp = cmds.add_parser("passport", help="portable worker reputation")
    ppc = pp.add_subparsers(dest="passport_cmd")
    pe = ppc.add_parser("export")
    pe.add_argument("--worker", required=True)
    pe.add_argument("--dest", default=None)
    pv = ppc.add_parser("verify")
    pv.add_argument("--path", required=True)

    cmds.add_parser("gates", help="activation gate status")
    cmds.add_parser("integrity", help="check the four un-hedged invariants")


def register_neighbor_parser(sub) -> None:
    """Hook for the levi CLI: `levi neighbor …`."""
    nb = sub.add_parser("neighbor", help="NeighborOS gig dispatch + the Site Lift")
    nb.add_argument("--dir", default=None, help="state dir (default ~/.levi/neighbor)")
    _register_commands(nb.add_subparsers(dest="neighbor_cmd"))


def cmd_neighbor(args: argparse.Namespace) -> int:
    cmd = getattr(args, "neighbor_cmd", None)
    handler = {
        "post": _cmd_post,
        "worker": _cmd_worker,
        "match": _cmd_match,
        "offer": _cmd_offer,
        "accept": _cmd_accept,
        "proof": _cmd_proof,
        "settle": _cmd_settle,
        "dispute": _cmd_dispute,
        "passport": _cmd_passport,
        "gates": _cmd_gates,
        "integrity": _cmd_integrity,
    }.get(cmd)
    if handler is None:
        print(
            "neighbor: post|worker|match|offer|accept|proof|settle|dispute|passport|gates|integrity"
        )
        return 2
    try:
        return handler(args)
    except (ValueError, KeyError, PermissionError) as exc:
        print(f"neighbor {cmd} failed: {exc}")
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="levi neighbor")
    parser.add_argument(
        "--dir", default=None, help="state dir (default ~/.levi/neighbor)"
    )
    _register_commands(parser.add_subparsers(dest="neighbor_cmd"))
    args = parser.parse_args(argv)
    return cmd_neighbor(args)
