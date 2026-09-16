"""CLI: python -m levi.vaults — per-project memory vaults.

Subcommands:
  create NAME            create a vault
  list                   list vaults
  delete NAME            delete a vault and all its entries
  policy NAME [--ttl type=seconds ...] [--max-entries N] [--show]
  add NAME TEXT --type working [--importance F] [--tags a,b]
  get NAME ID            show one entry
  search NAME QUERY      keyword search inside ONE vault (never cross-vault)
  ls NAME [--type T]     list entries in one vault
  purge NAME             enforce retention now (reports counts)
  export NAME DEST       export vault to a .tar.gz bundle
  import SRC [--name NAME] [--merge] [--policy-from-bundle]

Home resolves at call time from --home, LEVI_HOME, or ~/.levi/vaults.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from levi.memory.types import MemoryType
from levi.vaults.transfer import export_vault, import_vault
from levi.vaults.vault import VaultError, Vaults, default_home


def _manager(a) -> Vaults:
    home = Path(a.home) if a.home else default_home()
    return Vaults(home)


def _fmt(e) -> str:
    return (f"[{e.id[:8]}] {e.memory_type.value} importance={e.importance:.2f} "
            f"{e.created_at[:10]} tags={','.join(e.tags)}\n  {e.content[:300]}")


def cmd_create(a) -> int:
    try:
        _manager(a).create(a.name)
    except VaultError as exc:
        print(f"create refused: {exc}", file=sys.stderr)
        return 1
    print(f"created vault {a.name!r}")
    return 0


def cmd_list(a) -> int:
    names = _manager(a).list()
    print("no vaults." if not names else "\n".join(names))
    return 0


def cmd_delete(a) -> int:
    if _manager(a).delete(a.name):
        print(f"deleted vault {a.name!r}")
        return 0
    print(f"unknown vault {a.name!r}", file=sys.stderr)
    return 1


def cmd_policy(a) -> int:
    m = _manager(a)
    try:
        vault = m.get(a.name)
    except VaultError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if a.show or (not a.ttl and a.max_entries is None):
        print(json.dumps(vault.policy, indent=2))
        return 0
    ttl_by_type = {}
    for item in a.ttl:
        if "=" not in item:
            print(f"bad --ttl {item!r}; use type=seconds", file=sys.stderr)
            return 2
        ttype, secs = item.split("=", 1)
        try:
            ttl_by_type[ttype] = float(secs)
        except ValueError:
            print(f"bad --ttl {item!r}; seconds must be a number", file=sys.stderr)
            return 2
    try:
        policy = vault.set_policy(ttl_by_type=ttl_by_type or None,
                                  max_entries=a.max_entries)
    except VaultError as exc:
        print(f"policy refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(policy, indent=2))
    return 0


def cmd_add(a) -> int:
    try:
        mtype = MemoryType(a.type)
    except ValueError:
        print(f"invalid --type {a.type!r}", file=sys.stderr)
        return 2
    try:
        vault = _manager(a).get(a.name)
    except VaultError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    tags = [t.strip() for t in a.tags.split(",") if t.strip()]
    try:
        e = vault.add(mtype, a.text, importance=a.importance, tags=tags or None)
    except ValueError as exc:
        print(f"add refused: {exc}", file=sys.stderr)
        return 1
    print(f"added {e.id} to vault {a.name!r}")
    return 0


def cmd_get(a) -> int:
    try:
        e = _manager(a).get(a.name).get(a.id)
    except VaultError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if e is None:
        print(f"no entry {a.id!r} in vault {a.name!r}", file=sys.stderr)
        return 1
    print(_fmt(e))
    return 0


def cmd_search(a) -> int:
    try:
        hits = _manager(a).get(a.name).search(a.query, limit=a.limit)
    except VaultError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("no matches in this vault." if not hits else "\n".join(_fmt(e) for e in hits))
    return 0


def cmd_ls(a) -> int:
    try:
        vault = _manager(a).get(a.name)
        mtype = MemoryType(a.type) if a.type else None
    except (VaultError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    entries = vault.list(memory_type=mtype, limit=a.limit)
    print("vault is empty." if not entries else "\n".join(_fmt(e) for e in entries))
    return 0


def cmd_purge(a) -> int:
    try:
        report = _manager(a).get(a.name).purge()
    except VaultError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"purged {report['expired']} expired, {report['over_cap']} over-cap "
          f"in vault {a.name!r}")
    return 0


def cmd_export(a) -> int:
    try:
        vault = _manager(a).get(a.name)
        dest = export_vault(vault, Path(a.dest))
    except VaultError as exc:
        print(f"export refused: {exc}", file=sys.stderr)
        return 1
    print(f"exported vault {a.name!r} -> {dest}")
    return 0


def cmd_import(a) -> int:
    try:
        vault = import_vault(_manager(a), Path(a.src), name=a.name,
                             merge=a.merge, policy_from_bundle=a.policy_from_bundle)
    except VaultError as exc:
        print(f"import refused: {exc}", file=sys.stderr)
        return 1
    print(f"imported into vault {vault.name!r} ({vault.stats()['total']} entries)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.vaults",
        description="per-project memory vaults — isolated scopes, explicit retention",
    )
    ap.add_argument("--home", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    types = [t.value for t in MemoryType]

    p = sub.add_parser("create", help="create a vault"); p.add_argument("name"); p.set_defaults(func=cmd_create)
    p = sub.add_parser("list", help="list vaults"); p.set_defaults(func=cmd_list)
    p = sub.add_parser("delete", help="delete a vault"); p.add_argument("name"); p.set_defaults(func=cmd_delete)

    p = sub.add_parser("policy", help="show/set retention policy")
    p.add_argument("name"); p.add_argument("--show", action="store_true")
    p.add_argument("--ttl", action="append", default=[], help="type=seconds, repeatable")
    p.add_argument("--max-entries", type=int, default=None)
    p.set_defaults(func=cmd_policy)

    p = sub.add_parser("add", help="add an entry to a vault")
    p.add_argument("name"); p.add_argument("text")
    p.add_argument("--type", default="working", choices=types)
    p.add_argument("--importance", type=float, default=0.5)
    p.add_argument("--tags", default="")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("get", help="show one entry")
    p.add_argument("name"); p.add_argument("id"); p.set_defaults(func=cmd_get)

    p = sub.add_parser("search", help="search inside ONE vault")
    p.add_argument("name"); p.add_argument("query")
    p.add_argument("--limit", type=int, default=20); p.set_defaults(func=cmd_search)

    p = sub.add_parser("ls", help="list a vault's entries")
    p.add_argument("name"); p.add_argument("--type", default=None, choices=types)
    p.add_argument("--limit", type=int, default=50); p.set_defaults(func=cmd_ls)

    p = sub.add_parser("purge", help="enforce retention now")
    p.add_argument("name"); p.set_defaults(func=cmd_purge)

    p = sub.add_parser("export", help="export a vault to a bundle")
    p.add_argument("name"); p.add_argument("dest"); p.set_defaults(func=cmd_export)

    p = sub.add_parser("import", help="import a bundle")
    p.add_argument("src"); p.add_argument("--name", default=None)
    p.add_argument("--merge", action="store_true")
    p.add_argument("--policy-from-bundle", action="store_true")
    p.set_defaults(func=cmd_import)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
