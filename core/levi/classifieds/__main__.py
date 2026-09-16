"""CLI: python -m levi.classifieds — trust-graph classifieds, local only."""

from __future__ import annotations

import argparse
import json
import sys

from levi.classifieds.classifieds import ClassifiedsError, ClassifiedsStore


def _store() -> ClassifiedsStore:
    return ClassifiedsStore()


def cmd_add(args) -> int:
    try:
        r = _store().add(args.title, description=args.description or "",
                         price=args.price or "", category=args.category,
                         lister=args.lister, contact=args.contact or "")
    except ClassifiedsError as exc:
        print("classifieds: %s" % exc, file=sys.stderr)
        return 1
    print("listed [%s] %s" % (r["id"], r["title"]))
    return 0


def _fmt_trust(t) -> str:
    if not t["mutuals"]:
        return "trust 0.000 (no mutual vouches — unknown to your graph)"
    via = ", ".join("%s(%.2f)" % (m["via"], m["weight"]) for m in t["mutuals"])
    return "trust %.3f via %s" % (t["score"], via)


def cmd_browse(args) -> int:
    rows = _store().listings_with_trust(category=args.category,
                                        query=args.query)
    if not rows:
        print("no listings match.")
    for r in rows:
        price = " — %s" % r["price"] if r["price"] else ""
        print("[%s] %s%s [%s] by %s" % (r["id"], r["title"], price,
                                        r["category"], r["lister"]))
        print("    %s" % _fmt_trust(r["trust"]))
        if r["description"]:
            print("    %s" % r["description"][:120])
    return 0


def cmd_trust(args) -> int:
    t = _store().trust(args.lister)
    print("trust for %s: %.3f" % (t["lister"], t["score"]))
    print("formula: %s" % t["formula"])
    for m in t["mutuals"]:
        print("  mutual via %s (weight %.3f)" % (m["via"], m["weight"]))
    if not t["mutuals"]:
        print("  (no mutual vouches in your contacts — treat as unknown)")
    return 0


def cmd_vouch(args) -> int:
    try:
        r = _store().vouch(args.contact, args.for_id, args.weight)
    except ClassifiedsError as exc:
        print("classifieds: %s" % exc, file=sys.stderr)
        return 1
    print("recorded: %s vouches for %s (weight %.2f)" % (
        r["contact"], r["for"], r["weight"]))
    return 0


def cmd_contacts_init(args) -> int:
    st = _store()
    data = {
        "me": args.me,
        "my_vouches": {},
        "contacts": [{"id": c, "name": c, "vouches": {}} for c in args.contact],
    }
    st.save_contacts(data)
    print("contacts initialized for '%s' with %d contact(s)" % (args.me, len(args.contact)))
    print("edit ~/.levi/classifieds/contacts.json to set vouch weights, or use:")
    print("  python -m levi.classifieds vouch CONTACT --for ID --weight 0.8")
    return 0


def cmd_mark(args) -> int:
    try:
        r = _store().mark(args.id, args.status)
    except ClassifiedsError as exc:
        print("classifieds: %s" % exc, file=sys.stderr)
        return 1
    print("[%s] now %s" % (r["id"], r["status"]))
    return 0


def cmd_export(args) -> int:
    bundle = _store().export()
    text = json.dumps(bundle, indent=2)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(text)
        print("wrote %s (%d listings, %d attestations)" % (
            args.out, len(bundle["listings"]), len(bundle["attestations"])))
    else:
        print(text)
    return 0


def cmd_import(args) -> int:
    try:
        bundle = json.loads(open(args.file, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError) as exc:
        print("classifieds: %s" % exc, file=sys.stderr)
        return 1
    try:
        n = _store().import_bundle(bundle)
        v = _store().verify_export(bundle)
    except ClassifiedsError as exc:
        print("classifieds: %s" % exc, file=sys.stderr)
        return 1
    print("imported %d listing(s); %d/%d attestations intact (own key)" % (
        n, v["intact"], v["attestations"]))
    print("note: trust scores recomputed against YOUR contacts on browse")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.classifieds",
        description="Trust-graph classifieds — local, auditable, portable.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="post a listing")
    p.add_argument("title")
    p.add_argument("--description", default="")
    p.add_argument("--price", default="")
    p.add_argument("--category", default="misc")
    p.add_argument("--lister", default="me")
    p.add_argument("--contact", default="")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("browse", help="browse with trust scores")
    p.add_argument("--category", default=None)
    p.add_argument("--query", default=None)
    p.set_defaults(func=cmd_browse)

    p = sub.add_parser("trust", help="explain a lister's trust score")
    p.add_argument("lister")
    p.set_defaults(func=cmd_trust)

    p = sub.add_parser("vouch", help="record a contact's vouch")
    p.add_argument("contact")
    p.add_argument("--for", dest="for_id", required=True)
    p.add_argument("--weight", type=float, default=1.0)
    p.set_defaults(func=cmd_vouch)

    p = sub.add_parser("contacts-init", help="initialize your contacts file")
    p.add_argument("--me", default="me")
    p.add_argument("--contact", action="append", default=[])
    p.set_defaults(func=cmd_contacts_init)

    p = sub.add_parser("mark", help="mark sold/withdrawn/active")
    p.add_argument("id")
    p.add_argument("status", choices=["active", "sold", "withdrawn"])
    p.set_defaults(func=cmd_mark)

    p = sub.add_parser("export", help="export portable bundle")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("import", help="import a bundle")
    p.add_argument("file")
    p.set_defaults(func=cmd_import)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
