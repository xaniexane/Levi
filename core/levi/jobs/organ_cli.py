"""LEVI job organ — CLI surface (``levi jobs organ ...``).

The universal organ CLI. Dry-run is the default everywhere: nothing is
written and no gate touches a real human unless ``--live`` is passed.
Live runs still gate every consequential step through the six hitl
kinds, resolved interactively on stdin.

A profile is required for engine work (``--profile NAME``); the organ
never invents personal data — unset profile fields simply degrade
scoring honestly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from levi.automation.hitl import GateKind, GateRequest, auto_approve

from . import apply as apply_engine
from . import chains as chains_engine
from . import gig as gig_engine
from . import intel as intel_engine
from . import prep as prep_engine
from . import sourcing as sourcing_engine
from . import triage as triage_engine
from .modes import describe as describe_mode, parse_mode, require
from .profiles import PROFILE_FIELDS, ProfileStore
from .store import Warehouse, import_workbook


# -- interactive (live) responder ------------------------------------------


def stdin_responder(request: GateRequest) -> Dict[str, Any]:
    """Resolve a gate with the human on stdin. Fail closed on EOF."""
    print(f"\n--- gate: {request.kind.value} ---")
    print(request.prompt)
    try:
        if request.kind is GateKind.NOTIFICATION:
            return {"decision": "noted"}
        if request.kind is GateKind.DIALOG:
            answer = input("your reply: ")
            return {"decision": "noted", "note": answer}
        if request.kind is GateKind.ACKNOWLEDGE:
            input("press enter to acknowledge: ")
            return {"decision": "acknowledged"}
        if request.kind in (GateKind.APPROVAL, GateKind.CONFIRM):
            answer = input("approve? [y/N]: ").strip().lower()
            if answer in ("y", "yes"):
                return {"decision": "approved"}
            return {"decision": "denied", "note": "human said no"}
        if request.kind is GateKind.EDIT_APPROVE:
            print("(empty edit keeps the draft as-is)")
            edit = input("edited text (or empty): ")
            answer = input("approve? [y/N]: ").strip().lower()
            if answer not in ("y", "yes"):
                return {"decision": "denied", "note": "human said no"}
            if edit.strip():
                return {"decision": "edited", "edited_payload": {"text": edit}}
            return {"decision": "approved"}
    except EOFError:
        return {"decision": "denied", "note": "no input (EOF) — fail closed"}
    return {"decision": "denied", "note": "unhandled gate kind"}


# -- context ----------------------------------------------------------------


class Organ:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.mode = parse_mode(getattr(args, "mode", None))
        self.dry_run = not bool(getattr(args, "live", False))
        self.responder = stdin_responder if not self.dry_run else auto_approve
        self.warehouse = Warehouse()
        self.profiles = ProfileStore()

    def profile(self):
        name = getattr(self.args, "profile", None)
        if not name:
            raise SystemExit("a profile is required: pass --profile NAME")
        return self.profiles.get(name)

    def check(self, capability: str) -> None:
        try:
            require(self.mode, capability)
        except PermissionError as exc:
            raise SystemExit(f"jobs organ: {exc}") from exc


def _ok(msg: str) -> int:
    print(msg)
    return 0


# -- profile -----------------------------------------------------------------


def _profile_create(o: Organ) -> int:
    o.check("write")
    name = o.args.name
    prof = o.profiles.scaffold(name) if o.args.scaffold else o.profiles.create(name)
    return _ok(
        f"profile {prof.name!r} created ({'scaffolded' if o.args.scaffold else 'empty'})"
    )


def _profile_set(o: Organ) -> int:
    o.check("write")
    prof = o.profiles.set_field(o.args.name, o.args.field, o.args.value)
    return _ok(f"profile {prof.name!r}: {o.args.field} = {prof.get(o.args.field)!r}")


def _profile_show(o: Organ) -> int:
    prof = o.profiles.get(o.args.name)
    print(f"profile: {prof.name}  (updated {prof.updated_at})")
    for key in PROFILE_FIELDS:
        print(f"  {key}: {prof.get(key)!r}")
    return 0


def _profile_list(o: Organ) -> int:
    names = o.profiles.list()
    print("\n".join(names) if names else "no profiles")
    return 0


# -- workbook -----------------------------------------------------------------


def _workbook_import(o: Organ) -> int:
    o.check("ingest")
    counts = import_workbook(o.args.path, o.warehouse)
    for table, n in counts.items():
        print(f"  {table}: {n}")
    return 0


# -- sourcing ------------------------------------------------------------------


def _sourcing_ingest(o: Organ) -> int:
    o.check("ingest")
    path = Path(o.args.file)
    listings = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(listings, list):
        raise SystemExit("listings file must be a JSON array")
    report = sourcing_engine.ingest_listings(
        o.warehouse,
        listings,
        source_board=o.args.board or "manual",
        dry_run=o.dry_run,
    )
    tag = "WOULD stage" if o.dry_run else "staged"
    print(
        f"{tag}: {report['staged']}  refreshed: {report['refreshed']}  "
        f"blacklist-rejected: {report['rejected_blacklist']}  "
        f"restriction-rejected: {report['rejected_restriction']}"
    )
    for r in report["rejections"]:
        print(f"  rejected: {r.get('listing')} — {r.get('reason')}")
    return 0


# -- triage ---------------------------------------------------------------------


def _triage_run(o: Organ) -> int:
    o.check("triage")
    report = triage_engine.triage_buffer(
        o.warehouse, o.profile(), threshold=o.args.threshold, dry_run=o.dry_run
    )
    tag = "WOULD promote" if o.dry_run else "promoted"
    print(
        f"scored: {report['scored']}  {tag}: {report['promoted']}  "
        f"parked: {report['parked']}  (threshold {report['threshold']})"
    )
    for item in report["items"]:
        flags = f" [{', '.join(item['flags'])}]" if item["flags"] else ""
        print(
            f"  {item['score']}/10 {item['title']} @ {item['company']} — {item['action']}{flags}"
        )
    return 0


def _triage_score(o: Organ) -> int:
    listing = {
        "job_title": o.args.title,
        "company": o.args.company,
        "pay_range": o.args.pay or "",
        "location_remote": o.args.location or "",
        "equipment_provided": o.args.equipment or "",
        "notes": o.args.notes or "",
    }
    result = triage_engine.score_listing(listing, o.profile())
    print(f"score: {result['score']}/10" + ("  (capped)" if result["capped"] else ""))
    for k, v in result["breakdown"].items():
        print(f"  {k}: {v}")
    for f in result["flags"]:
        print(f"  flag: {f}")
    return 0


# -- apply -----------------------------------------------------------------------


def _apply_draft(o: Organ) -> int:
    o.check("draft")
    packet = apply_engine.build_packet(
        o.warehouse,
        o.profile(),
        o.args.queue_id,
        with_cover_letter=not o.args.no_cover,
        dry_run=o.dry_run,
        responder=o.responder,
    )
    print(
        f"packet for queue #{o.args.queue_id}: {packet['job_title']} @ {packet['company']}"
    )
    print(f"  resume: {packet['resume_version'] or '(none on file)'}")
    cover = packet.get("cover_letter_draft")
    if cover:
        print(f"  cover letter draft ({cover['template_name']}):\n")
        print(cover["text"])
    else:
        print("  cover letter: (none — no template on file)")
    if o.dry_run:
        print("\n[dry-run: nothing written]")
    return 0


def _apply_authorize(o: Organ) -> int:
    o.check("gates")
    try:
        out = apply_engine.authorize_submission(
            o.warehouse, o.args.queue_id, o.responder, dry_run=o.dry_run
        )
    except Exception as exc:
        print(f"not authorized: {exc}")
        return 1
    print(f"authorized: {out['decision']}" + ("  [dry-run]" if o.dry_run else ""))
    print("The organ never submits. Take the packet and submit it yourself,")
    print("then run: levi jobs organ --profile NAME apply log --queue-id N")
    return 0


def _apply_log(o: Organ) -> int:
    o.check("gates")
    out = apply_engine.log_submission(
        o.warehouse,
        o.args.queue_id,
        o.responder,
        dry_run=o.dry_run,
        confirmation=o.args.confirmed,
    )
    if out["logged"]:
        print(f"logged in Application Log (row {out['application_log_id']})")
    else:
        print(
            f"not logged: {out.get('reason', 'gate denied')}"
            + ("  [dry-run]" if o.dry_run else "")
        )
    return 0


def _apply_respond(o: Organ) -> int:
    o.check("write")
    row = apply_engine.record_response(
        o.warehouse,
        o.args.log_id,
        o.args.type,
        current_status=o.args.status or "",
        notes=o.args.notes or "",
    )
    print(
        f"application log #{o.args.log_id}: response={row['response_type']} status={row['current_status']}"
    )
    return 0


# -- intel ------------------------------------------------------------------------


def _intel_company_add(o: Organ) -> int:
    o.check("write")
    row = intel_engine.add_company(o.warehouse, o.args.name)
    return _ok(f"company intel added: {row['company_name']} (id {row['id']})")


def _intel_blacklist_add(o: Organ) -> int:
    o.check("write")
    row = intel_engine.add_blacklist(
        o.warehouse,
        o.args.etype,
        o.args.name,
        reason=o.args.reason or "",
        severity=o.args.severity,
    )
    return _ok(f"blacklisted {row['entry_type']}: {row['name']} (id {row['id']})")


def _intel_restrict_add(o: Organ) -> int:
    o.check("write")
    row = intel_engine.add_restriction(
        o.warehouse,
        o.args.rtype,
        o.args.detail,
        severity=o.args.severity,
        reason=o.args.reason or "",
    )
    return _ok(f"restriction added: {row['restriction_detail']} [{row['severity']}]")


def _intel_check(o: Organ) -> int:
    blocked, reason = intel_engine.check_blacklist(
        o.warehouse, company=o.args.company or "", role=o.args.title or ""
    )
    print(f"blacklist: {'BLOCKED — ' + reason if blocked else 'clear'}")
    hits = intel_engine.check_restrictions(
        o.warehouse,
        {
            "job_title": o.args.title or "",
            "company": o.args.company or "",
            "notes": o.args.notes or "",
        },
    )
    for h in hits:
        print(f"restriction [{h['severity']}]: {h['detail']} — {h['reason']}")
    if not hits:
        print("restrictions: none fired")
    return 0


def _intel_watch(o: Organ) -> int:
    for row in intel_engine.watchlist(o.warehouse):
        print(f"  {row.get('company_name')} — {row.get('notes') or ''}")
    return 0


# -- prep --------------------------------------------------------------------------


def _prep_packet(o: Organ) -> int:
    o.check("draft")
    pkt = prep_engine.build_prep_packet(
        o.warehouse,
        o.args.title,
        o.args.company,
        interview_date=o.args.date or "",
        dry_run=o.dry_run,
    )
    print(
        f"prep packet: {pkt['job_title']} @ {pkt['company']} "
        f"[{pkt['prep_status']}]" + ("  [dry-run]" if o.dry_run else "")
    )
    print("Fill the STAR stories before the interview:")
    print("  levi jobs organ --profile NAME prep fill --id N --story1 '...' ...")
    return 0


def _prep_fill(o: Organ) -> int:
    o.check("write")
    fields = {
        k: v
        for k, v in {
            "star_story_1": o.args.story1,
            "star_story_2": o.args.story2,
            "star_story_3": o.args.story3,
            "skills_to_highlight": o.args.skills,
            "company_research_notes": o.args.research,
            "questions_to_ask": o.args.questions,
            "prep_status": o.args.status,
        }.items()
        if v
    }
    row = prep_engine.update_prep(o.warehouse, o.args.id, **fields)
    return _ok(f"prep #{o.args.id} updated (status: {row.get('prep_status')})")


def _prep_template_add(o: Organ) -> int:
    o.check("write")
    row = prep_engine.add_template(
        o.warehouse,
        o.args.name,
        target_role_type=o.args.role or "",
        opening_hook=o.args.hook or "",
        core_value_prop=o.args.value or "",
        closing_line=o.args.close or "",
    )
    return _ok(f"cover template added: {row['template_name']} (id {row['id']})")


def _prep_cover(o: Organ) -> int:
    row = o.warehouse.get_row("apply_queue", o.args.queue_id)
    template = None
    if o.args.template:
        found = o.warehouse.find("cover_letter_bank", template_id=o.args.template)
        template = found[0] if found else None
    if template is None:
        template = prep_engine.pick_template(
            o.warehouse, str(row.get("job_title") or "")
        )
    if template is None:
        raise SystemExit("no cover-letter template on file — add one first")
    draft = prep_engine.compose_cover_letter(
        o.profile(),
        {"job_title": row.get("job_title"), "company": row.get("company")},
        template,
    )
    print(draft["text"])
    print("\n[draft only — approval happens at the apply gate]")
    return 0


# -- gig ----------------------------------------------------------------------------


def _gig_offer_add(o: Organ) -> int:
    o.check("write")
    row = gig_engine.add_offer(
        o.warehouse,
        o.args.platform,
        o.args.title,
        pay=o.args.pay,
        distance_mi=o.args.distance,
        window_start=o.args.start or "",
        window_end=o.args.end or "",
        location=o.args.location or "",
    )
    return _ok(f"gig offer added: {row['title']} @ {row['platform']} (id {row['id']})")


def _gig_evaluate(o: Organ) -> int:
    rules: Dict[str, Any] = {}
    if o.args.min_pay is not None:
        rules["min_pay"] = o.args.min_pay
    if o.args.max_dist is not None:
        rules["max_distance_mi"] = o.args.max_dist
    if o.args.platforms:
        rules["platforms"] = [p.strip() for p in o.args.platforms.split(",")]
    report = gig_engine.evaluate_offers(o.warehouse, rules, dry_run=o.dry_run)
    tag = "WOULD accept" if o.dry_run else "would-accept"
    print(f"evaluated: {report['evaluated']}  {tag}: {report['would_accept']}")
    for item in report["items"]:
        print(f"  {item['verdict']}: {item['title']} — {'; '.join(item['reasons'])}")
    return 0


def _gig_accept(o: Organ) -> int:
    o.check("gates")
    try:
        gig_engine.accept_offer(o.warehouse, o.args.id, o.responder, dry_run=o.dry_run)
    except Exception as exc:
        print(f"not accepted: {exc}")
        return 1
    print("offer approved for grab" + ("  [dry-run]" if o.dry_run else ""))
    print("Now grab it in the gig app — the organ never touches the platform.")
    return 0


def _gig_income_add(o: Organ) -> int:
    o.check("write")
    row = gig_engine.log_income(
        o.warehouse,
        o.args.platform,
        o.args.desc,
        o.args.amount,
        hours_worked=o.args.hours or 0.0,
    )
    return _ok(f"income logged: ${row['amount']} @ {row['platform']} (id {row['id']})")


def _gig_income(o: Organ) -> int:
    s = gig_engine.income_summary(o.warehouse)
    print(
        f"gigs: {s['gigs']}  total: ${s['total']}  hours: {s['hours']}  "
        f"per-hour: ${s['per_hour']}"
    )
    for plat, amt in s["by_platform"].items():
        print(f"  {plat}: ${amt}")
    return 0


# -- chains ----------------------------------------------------------------------------


def _chain_list(o: Organ) -> int:
    for c in chains_engine.list_chains():
        print(f"  {c.id}: {c.name} — {c.description}")
        print(f"    trigger: {c.trigger} | gate: {c.gate_kind.value}")
    return 0


def _chain_run(o: Organ) -> int:
    ctx: Dict[str, Any] = {"mode": o.mode}
    if o.args.listings:
        ctx["listings"] = json.loads(Path(o.args.listings).read_text(encoding="utf-8"))
    for key in (
        "queue_id",
        "job_title",
        "company",
        "interview_date",
        "threshold",
        "source_board",
        "with_cover_letter",
    ):
        val = getattr(o.args, key, None)
        if val is not None:
            ctx[key] = val
    if o.args.gig_rules:
        ctx["gig_rules"] = json.loads(o.args.gig_rules)
    receipt = chains_engine.run_chain(
        o.warehouse,
        o.profile(),
        o.args.chain_id,
        ctx,
        responder=o.responder,
        dry_run=o.dry_run,
    )
    print(
        f"chain {receipt['chain_id']}: {receipt['status']}"
        + ("  [dry-run]" if o.dry_run else "")
    )
    for c in receipt["conditions"]:
        print(f"  condition [{c['label']}]: {'pass' if c['passed'] else 'FAIL'}")
    for a in receipt["actions"]:
        print(
            f"  action {a['action']}: {'ok' if a['ok'] else 'FAIL ' + a.get('reason', '')}"
        )
    if receipt.get("gate"):
        print(f"  gate: {receipt['gate']['kind']} -> {receipt['gate']['decision']}")
    if receipt.get("verification"):
        for c in receipt["verification"]["checks"]:
            print(f"  verify [{c['check']}]: {'pass' if c['passed'] else 'FAIL'}")
    return 0 if receipt["status"] == "ok" else 1


def _chain_flow(o: Organ) -> int:
    print(chains_engine.chain_mermaid(o.args.chain_id))
    return 0


# -- dashboard ----------------------------------------------------------------------------


def _dash(o: Organ) -> int:
    wh = o.warehouse
    buffer = wh.list_rows("review_buffer")
    queue = wh.list_rows("apply_queue")
    log = wh.list_rows("application_log")
    interviews = wh.list_rows("interviews")
    offers = wh.list_rows("offers_decisions")
    gigs = [r for r in wh.list_rows("gig_offers") if r.get("status") == "open"]
    income = gig_engine.income_summary(wh)
    print(f"mode: {o.mode.value} — {describe_mode(o.mode)}")
    print(
        f"review buffer: {len(buffer)} ({sum(1 for r in buffer if r.get('match_score') in (None, '', 0))} unscored)"
    )
    print(
        f"apply queue: {len([r for r in queue if r.get('completed') != 'Y'])} pending / {len(queue)} total"
    )
    print(f"applications logged: {len(log)}")
    print(f"interviews: {len(interviews)}   offers/decisions: {len(offers)}")
    print(
        f"gig offers open: {len(gigs)}   gig income: ${income['total']} ({income['gigs']} gigs)"
    )
    print(
        f"restrictions active: {len(intel_engine.check_restrictions(wh, {})) or sum(1 for _ in wh.list_rows('restrictions_filters'))}"
    )
    print(f"blacklist entries: {len(wh.list_rows('blacklist'))}")
    if o.dry_run:
        print("[dry-run default: add --live to execute writes]")
    return 0


# -- parser -------------------------------------------------------------------------------


def register_organ_parser(sub) -> None:
    org = sub.add_parser("organ", help="universal job-search organ (dry-run default)")
    org.add_argument("--profile", default=None, help="profile name to work as")
    org.add_argument(
        "--mode",
        default=None,
        choices=["full", "light", "low-data", "offline"],
        help="run mode (default: full)",
    )
    org.add_argument(
        "--live", action="store_true", help="execute for real (default is dry-run)"
    )
    eng = org.add_subparsers(dest="organ_engine")

    # profile
    p = eng.add_parser("profile", help="user profiles (never hardcoded)")
    psub = p.add_subparsers(dest="profile_cmd")
    pc = psub.add_parser("create", help="create a profile")
    pc.add_argument("name")
    pc.add_argument(
        "--scaffold", action="store_true", help="pre-fill all schema fields blank"
    )
    ps = psub.add_parser("set", help="set one profile field")
    ps.add_argument("name")
    ps.add_argument("field", choices=list(PROFILE_FIELDS))
    ps.add_argument("value")
    psh = psub.add_parser("show", help="show a profile")
    psh.add_argument("name")
    psub.add_parser("list", help="list profiles")

    # workbook
    wb = eng.add_parser("workbook", help="workbook-backed warehouse")
    wsub = wb.add_subparsers(dest="workbook_cmd")
    wi = wsub.add_parser("import", help="import the V2 xlsx into the warehouse")
    wi.add_argument("--path", required=True)

    # sourcing
    s = eng.add_parser("sourcing", help="ENGINE 1 / sourcing")
    ssub = s.add_subparsers(dest="sourcing_cmd")
    si = ssub.add_parser("ingest", help="stage listings into the review buffer")
    si.add_argument("--file", required=True, help="JSON array of listing dicts")
    si.add_argument("--board", default="manual")

    # triage
    t = eng.add_parser("triage", help="ENGINE 2 / triage + 1-10 scoring")
    tsub = t.add_subparsers(dest="triage_cmd")
    tr = tsub.add_parser("run", help="score buffer, promote to apply queue")
    tr.add_argument("--threshold", type=int, default=7)
    ts = tsub.add_parser("score", help="score one listing on the spot")
    ts.add_argument("--title", required=True)
    ts.add_argument("--company", default="")
    ts.add_argument("--pay", default="")
    ts.add_argument("--location", default="")
    ts.add_argument("--equipment", default="")
    ts.add_argument("--notes", default="")

    # apply
    a = eng.add_parser("apply", help="ENGINE 3 / apply (human submits)")
    asub = a.add_subparsers(dest="apply_cmd")
    ad = asub.add_parser("draft", help="build the submission packet")
    ad.add_argument("--queue-id", type=int, required=True)
    ad.add_argument("--no-cover", action="store_true")
    aa = asub.add_parser("authorize", help="human authorizes a submission")
    aa.add_argument("--queue-id", type=int, required=True)
    al = asub.add_parser("log", help="log a human-confirmed submission")
    al.add_argument("--queue-id", type=int, required=True)
    al.add_argument(
        "--confirmed",
        action="store_true",
        help="you already submitted this (skips the confirm gate)",
    )
    ar = asub.add_parser("respond", help="record an employer response")
    ar.add_argument("--log-id", type=int, required=True)
    ar.add_argument(
        "--type",
        required=True,
        choices=["interview", "rejection", "offer", "screening", "other"],
    )
    ar.add_argument("--status", default="")
    ar.add_argument("--notes", default="")

    # intel
    it = eng.add_parser("intel", help="ENGINE 4 / company intel + exclusions")
    itsub = it.add_subparsers(dest="intel_cmd")
    ic = itsub.add_parser("company-add", help="add company intel")
    ic.add_argument("name")
    ib = itsub.add_parser("blacklist-add", help="blacklist a company/role/board")
    ib.add_argument("etype", choices=["company", "role", "board"])
    ib.add_argument("name")
    ib.add_argument("--reason", default="")
    ib.add_argument("--severity", default="hard", choices=["hard", "soft"])
    ir = itsub.add_parser("restrict-add", help="add a restriction/filter")
    ir.add_argument("rtype")
    ir.add_argument("detail")
    ir.add_argument("--severity", default="hard", choices=["hard", "soft"])
    ir.add_argument("--reason", default="")
    ick = itsub.add_parser("check", help="screen a listing against intel")
    ick.add_argument("--company", default="")
    ick.add_argument("--title", default="")
    ick.add_argument("--notes", default="")
    itsub.add_parser("watch", help="show watchlisted companies")

    # prep
    pr = eng.add_parser("prep", help="ENGINE 5 / prep + cover letters")
    prsub = pr.add_subparsers(dest="prep_cmd")
    pp = prsub.add_parser("packet", help="scaffold an interview prep packet")
    pp.add_argument("--title", required=True)
    pp.add_argument("--company", required=True)
    pp.add_argument("--date", default="")
    pf = prsub.add_parser("fill", help="fill prep packet fields")
    pf.add_argument("--id", type=int, required=True)
    pf.add_argument("--story1", default=None)
    pf.add_argument("--story2", default=None)
    pf.add_argument("--story3", default=None)
    pf.add_argument("--skills", default=None)
    pf.add_argument("--research", default=None)
    pf.add_argument("--questions", default=None)
    pf.add_argument("--status", default=None)
    pt = prsub.add_parser("template-add", help="add a cover-letter template")
    pt.add_argument("name")
    pt.add_argument("--role", default="")
    pt.add_argument("--hook", default="")
    pt.add_argument("--value", default="")
    pt.add_argument("--close", default="")
    pcv = prsub.add_parser("cover", help="compose a cover-letter draft")
    pcv.add_argument("--queue-id", type=int, required=True)
    pcv.add_argument("--template", default=None)

    # gig
    g = eng.add_parser("gig", help="gig / fast-cash parallel track")
    gsub = g.add_subparsers(dest="gig_cmd")
    go = gsub.add_parser("offer-add", help="stage a gig offer")
    go.add_argument("--platform", required=True)
    go.add_argument("--title", required=True)
    go.add_argument("--pay", type=float, default=0.0)
    go.add_argument("--distance", type=float, default=0.0)
    go.add_argument("--start", default="")
    go.add_argument("--end", default="")
    go.add_argument("--location", default="")
    ge = gsub.add_parser("evaluate", help="evaluate open offers against rules")
    ge.add_argument("--min-pay", type=float, default=None)
    ge.add_argument("--max-dist", type=float, default=None)
    ge.add_argument("--platforms", default=None)
    ga = gsub.add_parser("accept", help="human approves a block grab")
    ga.add_argument("--id", type=int, required=True)
    gd = gsub.add_parser("decline", help="decline a gig offer")
    gd.add_argument("--id", type=int, required=True)
    gd.add_argument("--reason", default="")
    gi = gsub.add_parser("income-add", help="log gig income")
    gi.add_argument("--platform", required=True)
    gi.add_argument("--desc", required=True)
    gi.add_argument("--amount", type=float, required=True)
    gi.add_argument("--hours", type=float, default=0.0)
    gsub.add_parser("income", help="income summary")

    # chains
    ch = eng.add_parser("chain", help="chained workflows (trigger->...->receipt)")
    chsub = ch.add_subparsers(dest="chain_cmd")
    chsub.add_parser("list", help="list chains")
    cr = chsub.add_parser("run", help="run a chain")
    cr.add_argument("chain_id", choices=[c.id for c in chains_engine.list_chains()])
    cr.add_argument(
        "--listings", default=None, help="JSON file of listings (morning-sweep)"
    )
    cr.add_argument("--queue-id", type=int, default=None)
    cr.add_argument("--job-title", default=None)
    cr.add_argument("--company", default=None)
    cr.add_argument("--interview-date", default=None)
    cr.add_argument("--threshold", type=int, default=None)
    cr.add_argument("--source-board", default=None)
    cr.add_argument("--with-cover-letter", action="store_true", default=None)
    cr.add_argument(
        "--gig-rules", default=None, help="JSON object of auto-accept rules"
    )
    cf = chsub.add_parser("flow", help="print the chain's flow manifest (mermaid)")
    cf.add_argument("chain_id", choices=[c.id for c in chains_engine.list_chains()])

    # dashboard
    eng.add_parser("dash", help="organ dashboard")


_HANDLERS = {
    ("profile", "create"): _profile_create,
    ("profile", "set"): _profile_set,
    ("profile", "show"): _profile_show,
    ("profile", "list"): _profile_list,
    ("workbook", "import"): _workbook_import,
    ("sourcing", "ingest"): _sourcing_ingest,
    ("triage", "run"): _triage_run,
    ("triage", "score"): _triage_score,
    ("apply", "draft"): _apply_draft,
    ("apply", "authorize"): _apply_authorize,
    ("apply", "log"): _apply_log,
    ("apply", "respond"): _apply_respond,
    ("intel", "company-add"): _intel_company_add,
    ("intel", "blacklist-add"): _intel_blacklist_add,
    ("intel", "restrict-add"): _intel_restrict_add,
    ("intel", "check"): _intel_check,
    ("intel", "watch"): _intel_watch,
    ("prep", "packet"): _prep_packet,
    ("prep", "fill"): _prep_fill,
    ("prep", "template-add"): _prep_template_add,
    ("prep", "cover"): _prep_cover,
    ("gig", "offer-add"): _gig_offer_add,
    ("gig", "evaluate"): _gig_evaluate,
    ("gig", "accept"): _gig_accept,
    ("gig", "decline"): lambda o: _ok(
        f"declined: {gig_engine.decline_offer(o.warehouse, o.args.id, o.args.reason or '')['id']}"
    ),
    ("gig", "income-add"): _gig_income_add,
    ("gig", "income"): _gig_income,
    ("chain", "list"): _chain_list,
    ("chain", "run"): _chain_run,
    ("chain", "flow"): _chain_flow,
}


def cmd_organ(args: argparse.Namespace) -> int:
    engine = getattr(args, "organ_engine", None)
    if engine == "dash":
        return _dash(Organ(args))
    sub_attr = f"{engine}_cmd"
    cmd = getattr(args, sub_attr, None)
    handler = _HANDLERS.get((engine, cmd))
    if handler is None:
        print(f"unknown organ command: {engine} {cmd}")
        return 2
    try:
        return handler(Organ(args))
    except SystemExit:
        raise
    except (ValueError, KeyError, PermissionError) as exc:
        print(f"organ {engine} {cmd} failed: {exc}")
        return 2
