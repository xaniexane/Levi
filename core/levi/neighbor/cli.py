"""NeighborOS CLI — `levi neighbor`.

The Site Lift's operator surface: post work, register workers, match
transparently, run the proof-of-work stream, settle on the ledger,
export portable passports. Consequential commands need `--yes`
(Permission step) and print their preview first.
"""

from __future__ import annotations

import argparse
import json

from . import (
    academy,
    admin,
    lift,
    liquidity,
    monetize,
    notify,
    pay,
    post,
    pwa,
    rails,
    supply,
    twins,
    waitlist,
    work,
)
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
    # module law checks (laws → guard → prove)
    law_modules = {
        "waitlist": waitlist,
        "admin": admin,
        "twins": twins,
        "supply": supply,
        "academy": academy,
        "liquidity": liquidity,
        "rails": rails,
        "notify": notify,
    }
    law_ok = True
    store = _store(args)
    for name, mod in law_modules.items():
        try:
            res = mod.check_laws(store)
        except Exception as exc:  # noqa: BLE001 — report, don't crash
            res = {"ok": False, "error": str(exc)}
        print(f"{'OK ' if res['ok'] else 'FAIL'}  laws:{name}")
        law_ok = law_ok and res["ok"]
    try:
        pwa_res = pwa.check_laws(store)
    except Exception as exc:  # noqa: BLE001
        pwa_res = {"ok": False, "error": str(exc)}
    print(f"{'OK ' if pwa_res['ok'] else 'FAIL'}  laws:pwa")
    law_ok = law_ok and pwa_res["ok"]
    ok = report["ok"] and law_ok
    print(f"\noverall: {'OK' if ok else 'FAILED'}")
    return 0 if ok else 1


# -- waitlist ---------------------------------------------------------------
def _cmd_waitlist(args) -> int:
    store = _store(args)
    if args.waitlist_cmd == "add":
        e = waitlist.add_to_waitlist(
            store, args.name, args.contact, args.role, args.cell
        )
        print(f"waitlisted {e['id']} — {e['name']} ({e['role']}, {e['neighborhood_cell']})")
    elif args.waitlist_cmd == "invite":
        e = waitlist.mint_invite(store, args.entry, args.operator)
        print(f"invite minted for {e['id']}: {e['invite_code']} (by {args.operator})")
    elif args.waitlist_cmd == "redeem":
        e = waitlist.redeem_invite(store, args.code)
        print(f"{e['id']} onboarded — clear to register as {e['role']}")
    elif args.waitlist_cmd == "decline":
        e = waitlist.decline(store, args.entry)
        print(f"{e['id']} declined (recorded, never deleted)")
    elif args.waitlist_cmd == "depth":
        d = waitlist.waitlist_depth(store, args.cell)
        print(f"{d['cell']}: {d['total']} waiting — {d['by_role']}")
    return 0


# -- admin ------------------------------------------------------------------
def _cmd_admin(args) -> int:
    store = _store(args)
    if args.admin_cmd == "stage":
        print(f"stage: {admin.stage(store)}")
    elif args.admin_cmd == "checklist":
        c = admin.stage_checklist(store, args.for_stage or admin.stage(store))
        print(f"checklist for {c['stage']}: {c['done']}/{c['total']} complete")
        for i in c["items"]:
            print(f"  [{'x' if i.get('done') else ' '}] {i.get('id')} — {i.get('note','')}")
    elif args.admin_cmd == "advance":
        admin.advance_stage(store, args.operator, confirm=args.yes)
        print(f"advanced to {admin.stage(store)}")
    elif args.admin_cmd == "override":
        admin.override_stage(store, args.to, args.operator, args.reason, confirm=args.yes)
        print(f"stage overridden to {admin.stage(store)} (logged)")
    elif args.admin_cmd == "history":
        for h in admin.stage_history(store):
            print(f"{h['ts']}: {h['from']} → {h['to']} by {h['operator']} — {h['note']}")
    elif args.admin_cmd == "readiness":
        r = admin.launch_readiness(store, args.cell)
        print(f"launch readiness {r['cell']}: {r['score']}/100")
        for name, comp in r["components"].items():
            print(f"  {name}: {comp['points']} pts")
    elif args.admin_cmd == "disputes":
        q = admin.dispute_queue(store)
        if not q:
            print("no open disputes")
        for row in q:
            d = row["dispute"]
            print(f"{d['id']}: gig {d['gig_id']} '{row['gig_title']}' — {d['reason']} (by {d['raised_by']})")
    elif args.admin_cmd == "nudges":
        for n in admin.pull_nudges(store):
            print(f"[{n['kind']}] {n['message']}")
    return 0


# -- notify ------------------------------------------------------------------
def _notifier(store) -> "notify.Notifier":
    from . import policies as policies_mod

    cfg = policies_mod.load_policies(store).get("notify", {})
    return notify.Notifier(config=cfg, state_dir=store.base)


def _cmd_notify(args) -> int:
    store = _store(args)
    n = _notifier(store)
    if args.notify_cmd == "status":
        st = n.status()
        print(f"backends: {', '.join(st['backends'])}")
        for b in ("app_push", "webhook", "whatsapp", "console", "file"):
            info = st[b]
            extra = info.get("detail") or info.get("setup") or ""
            print(f"  {b}: {info['status']}" + (f" — {extra}" if extra else ""))
        return 0
    if args.notify_cmd == "drain":
        receipt = admin.drain_nudges(store, n)
        print(
            f"drained={receipt['drained']} sent={len(receipt['sent'])} "
            f"retried={len(receipt['retried'])}"
        )
        for b, states in receipt["statuses"].items():
            print(f"  {b}: {', '.join(states)}")
        # echo the sent nudge bodies: the cron run's final message is the
        # actual phone push, so the bodies must be visible here
        latest: dict[str, dict] = {}
        for rec in store.read_all("nudges"):
            latest[rec["id"]] = rec
        for nid in receipt["sent"]:
            rec = latest.get(nid, {})
            print(f"[{rec.get('kind')}] {rec.get('message')}")
        return 0
    if args.notify_cmd == "test":
        statuses = n.send(
            {
                "id": f"probe-{store.next_id('probe')}",
                "title": "NeighborOS notify probe",
                "body": args.message,
                "kind": "probe",
                "cell": None,
            }
        )
        for b, s in statuses.items():
            print(f"  {b}: {s}")
        return 0
    return 2


# -- twins ------------------------------------------------------------------
def _cmd_twins(args) -> int:
    store = _store(args)
    if args.twins_cmd == "register":
        twins.register_property(store, args.id, args.address, args.owner, args.cell,
                                property_type=args.type)
        print(f"twin created for property {args.id}")
    elif args.twins_cmd == "system":
        twins.set_system(store, args.id, args.system, args.condition,
                         install_year=args.install_year, notes=args.notes or "")
        print(f"{args.id}: {args.system} condition {args.condition}/100 recorded")
    elif args.twins_cmd == "maintenance":
        twins.log_maintenance(store, args.id, args.system, args.action, cost=args.cost)
        print(f"{args.id}: maintenance logged on {args.system}")
    elif args.twins_cmd == "health":
        t = twins.load_twin(store, args.id)
        h = twins.health_score(t)
        print(f"{args.id}: health {h['score']}/100 over {h['systems']} systems")
        if h["flagged"]:
            print(f"  flagged: {', '.join(h['flagged'])}")
    elif args.twins_cmd == "reminders":
        for r in twins.reminders(store, args.id, args.year):
            print(f"[{r['level']}] {r['message']}")
    elif args.twins_cmd == "roi":
        for s in twins.roi_suggestions(store, args.id):
            print(f"{s['system']}: {s['upgrade']} — {s['arithmetic']}")
    elif args.twins_cmd == "export":
        res = twins.export_twin(store, args.id, dest=args.dest)
        print(f"twin exported → {res['path']}")
    return 0


# -- supply -----------------------------------------------------------------
def _cmd_supply(args) -> int:
    store = _store(args)
    if args.supply_cmd == "register":
        s = supply.register_supplier(store, args.name, args.contact,
                                     [c.strip() for c in (args.categories or "").split(",") if c.strip()],
                                     args.cell)
        print(f"supplier {s['id']} — {s['name']}")
    elif args.supply_cmd == "refer":
        r = supply.refer(store, args.supplier, (args.items or "").split(","),
                         gig_id=args.gig, requester=args.requester,
                         quoted_amount=args.quote, referred_by=args.by or "")
        print(f"referral {r['id']} → {r['supplier_name']} (quote recorded, no money moved)")
    elif args.supply_cmd == "close":
        supply.close_referral(store, args.referral, args.outcome, rating=args.rating)
        print(f"referral {args.referral} closed: {args.outcome}")
    elif args.supply_cmd == "rating":
        r = supply.supplier_rating(store, args.supplier)
        print(f"{args.supplier}: {r['average']}★ over {r['ratings_count']} rated referrals")
    return 0


# -- academy ----------------------------------------------------------------
def _cmd_academy(args) -> int:
    store = _store(args)
    if args.academy_cmd == "course":
        c = academy.create_course(store, args.title, args.category,
                                  (args.outline or "").split(";"), args.instructor)
        print(f"course {c['id']} — {c['title']}")
    elif args.academy_cmd == "enroll":
        academy.enroll(store, args.course, args.worker)
        print(f"{args.worker} enrolled in {args.course}")
    elif args.academy_cmd == "complete":
        res = academy.complete(store, args.course, args.worker, passed=not args.failed)
        print(f"{args.worker}: {res['status']} in {args.course}"
              + (" (credential claim added)" if res["status"] == "passed" else ""))
    elif args.academy_cmd == "roster":
        for e in academy.course_roster(store, args.course):
            print(f"{e['worker_id']}: {e['status']}")
    return 0


# -- crews ------------------------------------------------------------------
def _cmd_crew(args) -> int:
    store = _store(args)
    if args.crew_cmd == "create":
        members = [m.strip() for m in (args.members or "").split(",") if m.strip()]
        c = work.create_crew(store, args.name, args.lead, members)
        print(f"crew {c['id']} — {c['name']} (lead {c['lead_worker_id']}, {len(c['members'])} members)")
    elif args.crew_cmd == "add":
        c = work.add_crew_member(store, args.crew, args.worker)
        print(f"{args.worker} joined {c['id']} ({len(c['members'])} members)")
    elif args.crew_cmd == "claim":
        g = work.crew_claim(store, args.gig, args.crew, confirm=args.yes)
        print(f"{args.gig} claimed by crew {args.crew} (status: {g['status']})")
    return 0


# -- tiers / revenue ----------------------------------------------------------
def _cmd_tiers(args) -> int:
    store = _store(args)
    from . import policies as policies_mod
    policies = policies_mod.load_policies(store)
    if args.tiers_cmd == "list":
        for t in monetize.tiers(policies):
            band = f" (band ${t['band'][0]}–${t['band'][1]})" if t.get("band") else ""
            print(f"{t['id']}: {t['name']} — ${t['monthly_price']}/mo{band}")
    elif args.tiers_cmd == "subscribe":
        s = monetize.subscribe(store, args.tier, args.subscriber, args.operator)
        print(f"subscription {s['id']}: {s['tier_name']} for {s['subscriber']}")
    elif args.tiers_cmd == "cancel":
        s = monetize.cancel_subscription(store, args.subscription)
        print(f"{s['id']} cancelled (recorded)")
    elif args.tiers_cmd == "revenue":
        r = monetize.revenue_report(store)
        print(f"revenue (ledger records): total ${r['total']:.2f}")
        for name, amount in r["streams"].items():
            print(f"  {name}: ${amount:.2f} ({r['concentrations'][name]*100:.1f}%)")
        for w in r["warnings"]:
            print(f"  WARNING: {w} above 35% concentration")
        for f in r["flags"]:
            print(f"  FLAG: {f} above 40% concentration — diversify revenue")
    return 0


# -- liquidity ----------------------------------------------------------------
def _cmd_liquidity(args) -> int:
    store = _store(args)
    if args.liquidity_cmd == "report":
        rep = liquidity.liquidity_report(store, args.cell)
        for row in rep["categories"]:
            thin = " (thin data)" if row["thin_data"] else ""
            dpw = "∞" if row["demand_per_worker"] is None else f"{row['demand_per_worker']}"
            print(f"{row['category']}: {row['open_jobs']} jobs / {row['active_workers']} workers "
                  f"({dpw}/worker) — {row['state']}{thin}")
    elif args.liquidity_cmd == "nudge":
        ns = liquidity.queue_recruiting_nudges(store, args.cell, args.operator)
        print(f"queued {len(ns)} recruiting nudges (pull with `admin nudges`)")
    elif args.liquidity_cmd == "hot":
        hot = liquidity.priority_dispatch(store, args.cell)
        print(f"hot categories: {', '.join(hot) or 'none'}")
    return 0


# -- rails --------------------------------------------------------------------
def _cmd_rails(args) -> int:
    store = _store(args)
    if args.rails_cmd == "list":
        for r in rails.declared_rails(store):
            print(f"{r['name']}: {r['label']} — {r.get('instructions','')[:60]}")
    elif args.rails_cmd == "declare":
        rails.declare_rail(store, args.name, args.label, args.instructions, args.operator)
        print(f"rail {args.name} declared (reference only — no money moves here)")
    return 0


# -- pwa ----------------------------------------------------------------------
def _cmd_pwa(args) -> int:
    store = _store(args)
    res = pwa.export_pwa(store, dest=args.dest)
    print(f"PWA shell exported → {res['dir']} ({res['app_name']})")
    print("serve the directory statically, or open index.html — no network calls")
    return 0


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

    wl = cmds.add_parser("waitlist", help="recruiting waitlist + invite codes")
    wlc = wl.add_subparsers(dest="waitlist_cmd")
    wa = wlc.add_parser("add"); wa.add_argument("--name", required=True)
    wa.add_argument("--contact", required=True); wa.add_argument("--role", required=True,
        choices=["customer","worker","business","property_manager","supplier"])
    wa.add_argument("--cell", required=True)
    wi = wlc.add_parser("invite"); wi.add_argument("--entry", required=True)
    wi.add_argument("--operator", required=True)
    wr = wlc.add_parser("redeem"); wr.add_argument("--code", required=True)
    wd = wlc.add_parser("decline"); wd.add_argument("--entry", required=True)
    wdep = wlc.add_parser("depth"); wdep.add_argument("--cell", required=True)

    ad = cmds.add_parser("admin", help="Admin Command Center: gates, readiness, nudges")
    adc = ad.add_subparsers(dest="admin_cmd")
    adc.add_parser("stage")
    ac = adc.add_parser("checklist"); ac.add_argument("--for-stage", default=None)
    aadv = adc.add_parser("advance"); aadv.add_argument("--operator", required=True)
    aadv.add_argument("--yes", action="store_true")
    aov = adc.add_parser("override"); aov.add_argument("--to", required=True)
    aov.add_argument("--operator", required=True); aov.add_argument("--reason", required=True)
    aov.add_argument("--yes", action="store_true")
    adc.add_parser("history")
    ar = adc.add_parser("readiness"); ar.add_argument("--cell", required=True)
    adc.add_parser("disputes")
    adc.add_parser("nudges")

    tw = cmds.add_parser("twins", help="property digital twins")
    twc = tw.add_subparsers(dest="twins_cmd")
    tr = twc.add_parser("register"); tr.add_argument("--id", required=True)
    tr.add_argument("--address", required=True); tr.add_argument("--owner", required=True)
    tr.add_argument("--cell", required=True); tr.add_argument("--type", default="single_family")
    ts = twc.add_parser("system"); ts.add_argument("--id", required=True)
    ts.add_argument("--system", required=True); ts.add_argument("--condition", type=int, required=True)
    ts.add_argument("--install-year", type=int, default=None); ts.add_argument("--notes", default="")
    tm = twc.add_parser("maintenance"); tm.add_argument("--id", required=True)
    tm.add_argument("--system", required=True); tm.add_argument("--action", required=True)
    tm.add_argument("--cost", type=float, default=None)
    for name in ("health", "roi"):
        sp = twc.add_parser(name); sp.add_argument("--id", required=True)
    trem = twc.add_parser("reminders"); trem.add_argument("--id", required=True)
    trem.add_argument("--year", type=int, required=True)
    te = twc.add_parser("export"); te.add_argument("--id", required=True)
    te.add_argument("--dest", default=None)

    sp_ = cmds.add_parser("supply", help="supplier portal")
    spc = sp_.add_subparsers(dest="supply_cmd")
    sr = spc.add_parser("register"); sr.add_argument("--name", required=True)
    sr.add_argument("--contact", required=True); sr.add_argument("--categories", default="")
    sr.add_argument("--cell", required=True)
    sref = spc.add_parser("refer"); sref.add_argument("--supplier", required=True)
    sref.add_argument("--items", default=""); sref.add_argument("--gig", default=None)
    sref.add_argument("--requester", default=None); sref.add_argument("--quote", type=float, default=None)
    sref.add_argument("--by", default="")
    scl = spc.add_parser("close"); scl.add_argument("--referral", required=True)
    scl.add_argument("--outcome", required=True, choices=["fulfilled","partial","failed","cancelled"])
    scl.add_argument("--rating", type=int, default=None)
    srat = spc.add_parser("rating"); srat.add_argument("--supplier", required=True)

    acd = cmds.add_parser("academy", help="Academy & Credential Network")
    acc = acd.add_subparsers(dest="academy_cmd")
    accc = acc.add_parser("course"); accc.add_argument("--title", required=True)
    accc.add_argument("--category", required=True); accc.add_argument("--outline", default="")
    accc.add_argument("--instructor", required=True)
    ace = acc.add_parser("enroll"); ace.add_argument("--course", required=True)
    ace.add_argument("--worker", required=True)
    accp = acc.add_parser("complete"); accp.add_argument("--course", required=True)
    accp.add_argument("--worker", required=True); accp.add_argument("--failed", action="store_true")
    acr = acc.add_parser("roster"); acr.add_argument("--course", required=True)

    cr = cmds.add_parser("crew", help="business contractor crews")
    crc = cr.add_subparsers(dest="crew_cmd")
    crcr = crc.add_parser("create"); crcr.add_argument("--name", required=True)
    crcr.add_argument("--lead", required=True); crcr.add_argument("--members", default="")
    crca = crc.add_parser("add"); crca.add_argument("--crew", required=True)
    crca.add_argument("--worker", required=True)
    crcl = crc.add_parser("claim"); crcl.add_argument("--gig", required=True)
    crcl.add_argument("--crew", required=True); crcl.add_argument("--yes", action="store_true")

    ti = cmds.add_parser("tiers", help="paid-layer tiers + revenue report")
    tic = ti.add_subparsers(dest="tiers_cmd")
    tic.add_parser("list")
    tsub = tic.add_parser("subscribe"); tsub.add_argument("--tier", required=True)
    tsub.add_argument("--subscriber", required=True); tsub.add_argument("--operator", required=True)
    tcan = tic.add_parser("cancel"); tcan.add_argument("--subscription", required=True)
    tic.add_parser("revenue")

    lq = cmds.add_parser("liquidity", help="Neighborhood Liquidity Engine")
    lqc = lq.add_subparsers(dest="liquidity_cmd")
    lr = lqc.add_parser("report"); lr.add_argument("--cell", required=True)
    ln = lqc.add_parser("nudge"); ln.add_argument("--cell", required=True)
    ln.add_argument("--operator", required=True)
    lh = lqc.add_parser("hot"); lh.add_argument("--cell", required=True)

    rl = cmds.add_parser("rails", help="external payment rail plug-in registry")
    rlc = rl.add_subparsers(dest="rails_cmd")
    rlc.add_parser("list")
    rd = rlc.add_parser("declare"); rd.add_argument("--name", required=True)
    rd.add_argument("--label", required=True); rd.add_argument("--instructions", required=True)
    rd.add_argument("--operator", required=True)

    pw = cmds.add_parser("pwa", help="export the static PWA shell")
    pw.add_argument("--dest", default=None)

    nt = cmds.add_parser("notify", help="push plumbing: drain nudges, backend status")
    ntc = nt.add_subparsers(dest="notify_cmd")
    ntc.add_parser("drain", help="send queued nudges through the notifier")
    ntc.add_parser("status", help="per-backend availability, honest statuses")
    ntt = ntc.add_parser("test", help="send a probe notification")
    ntt.add_argument("--message", default="NeighborOS notify test ping")


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
        "waitlist": _cmd_waitlist,
        "admin": _cmd_admin,
        "twins": _cmd_twins,
        "supply": _cmd_supply,
        "academy": _cmd_academy,
        "crew": _cmd_crew,
        "tiers": _cmd_tiers,
        "liquidity": _cmd_liquidity,
        "rails": _cmd_rails,
        "pwa": _cmd_pwa,
        "notify": _cmd_notify,
    }.get(cmd)
    if handler is None:
        print(
            "neighbor: post|worker|match|offer|accept|proof|settle|dispute|passport|gates|integrity|"
            "waitlist|admin|twins|supply|academy|crew|tiers|liquidity|rails|pwa|notify"
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
