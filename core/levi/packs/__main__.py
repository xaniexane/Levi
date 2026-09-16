"""CLI: python -m levi.packs — scoped knowledge packs, all local."""

from __future__ import annotations

import argparse
import json
import sys

from levi.packs.packs import PackError, PackStore


def _store() -> PackStore:
    return PackStore()


def cmd_init(args) -> int:
    scope = {}
    if args.scope_always:
        scope["always"] = True
    if args.scope_project:
        scope["projects"] = args.scope_project
    if args.scope_tag:
        scope["tags"] = args.scope_tag
    try:
        d = _store().init(args.name, args.description or "", scope or None)
    except PackError as exc:
        print("packs: %s" % exc, file=sys.stderr)
        return 1
    print("pack created: %s" % d)
    print(
        "edit instructions.md, drop reference files in content/, then "
        "tune scope in manifest.json"
    )
    return 0


def cmd_list(args) -> int:
    packs = _store().list_packs()
    if not packs:
        print("no packs — create one with: python -m levi.packs init NAME")
    for p in packs:
        s = p.scope
        rules = []
        if s["always"]:
            rules.append("always")
        for k in ("projects", "paths", "tags"):
            if s[k]:
                rules.append("%s=%s" % (k, ",".join(s[k])))
        print(
            "%-20s v%-8s scope: %s"
            % (p.name, p.manifest.get("version", "?"), "; ".join(rules) or "none")
        )
    return 0


def cmd_show(args) -> int:
    try:
        p = _store().get(args.name)
    except PackError as exc:
        print("packs: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps(p.manifest, indent=2))
    print("\ninstructions:")
    for fname, _ in p.instructions():
        print("  " + fname)
    print("content:")
    for fname, _ in p.content_files():
        print("  " + fname)
    return 0


def cmd_assemble(args) -> int:
    asm = _store().assemble(project=args.project, cwd=args.cwd, tags=args.tag or [])
    names = ", ".join(p["name"] + "(%s)" % p["rule"] for p in asm["packs"])
    print("attached: %s" % (names or "none"))
    if asm["truncated"]:
        print("truncated: %s" % ", ".join(asm["truncated"]), file=sys.stderr)
    print()
    print(asm["text"])
    return 0


def cmd_validate(args) -> int:
    ok = True
    for p in _store().list_packs():
        print("ok: %s" % p.name)
    # also surface broken packs
    from levi.packs.packs import packs_home

    for d in sorted(packs_home().iterdir()):
        if d.is_dir() and not (d / "manifest.json").exists():
            print("BROKEN (no manifest.json): %s" % d.name, file=sys.stderr)
            ok = False
    return 0 if ok else 1


def cmd_delete(args) -> int:
    try:
        _store().delete(args.name)
    except PackError as exc:
        print("packs: %s" % exc, file=sys.stderr)
        return 1
    print("deleted pack: %s" % args.name)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.packs",
        description="Scoped knowledge packs — user-owned persistent context.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create a pack")
    p.add_argument("name")
    p.add_argument("--description", default="")
    p.add_argument("--scope-always", action="store_true")
    p.add_argument("--scope-project", action="append", default=None)
    p.add_argument("--scope-tag", action="append", default=None)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("list", help="list packs")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="show a pack")
    p.add_argument("name")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("assemble", help="assemble scoped context")
    p.add_argument("--project", default=None)
    p.add_argument("--cwd", default=None)
    p.add_argument("--tag", action="append", default=None)
    p.set_defaults(func=cmd_assemble)

    p = sub.add_parser("validate", help="validate all packs")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("delete", help="delete a pack")
    p.add_argument("name")
    p.set_defaults(func=cmd_delete)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
