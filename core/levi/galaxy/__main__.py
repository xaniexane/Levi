"""`python -m levi.galaxy` — command-line management of the Galaxy ecosystem.

Subcommands:
    list                installed packages and their ports/verbs
    search <q>          search installed packages by id/name/description/verb
    install <source>    install a package from a directory, tarball, or git URL
    info <id>           full detail for one installed package
    remove <id>         uninstall a package (directory + registry + files)
    services            the live service directory (ports -> verbs)

Two stores, one truth: the install registry (levi.galaxy.registry) records
*what is installed*; the service directory (levi.galaxy.service) is the
runtime view of *what is callable*. Read commands sync the directory from
the registry first, so the two can never silently disagree.

Exit codes: 0 on success, 1 on any failure (error on stderr).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from levi.galaxy import trust as galaxy_trust
from levi.galaxy.install import GalaxyInstallError
from levi.galaxy.registry import GalaxyRegistry
from levi.galaxy.service import (
    GalaxyError,
    GalaxyServices,
    UnknownPackage,
    default_store_dir,
)


def _levi_home() -> Path:
    return Path.home() / ".levi"


def _services(*, sync: bool = False) -> GalaxyServices:
    svc = GalaxyServices(store_dir=default_store_dir())
    if sync:
        result = svc.sync_from_registry(home=_levi_home())
        for skipped in result["skipped"]:
            print(f"levi.galaxy: warning: skipped {skipped}", file=sys.stderr)
    return svc


def _fail(message: str) -> int:
    print(f"levi.galaxy: error: {message}", file=sys.stderr)
    return 1


def cmd_list(_args: argparse.Namespace) -> int:
    svc = _services(sync=True)
    directory = svc.list_services()
    if not directory:
        print("no galaxy packages installed")
        return 0
    for port, entry in directory.items():
        status = f" [BROKEN: {entry['broken']}]" if entry["broken"] else ""
        print(f"{entry['package']}  {entry['version']}  ({entry['kind']}){status}")
        if entry["description"]:
            print(f"  {entry['description']}")
        verbs = ", ".join(entry["verbs"]) if entry["verbs"] else "(no verbs)"
        print(f"  port {port}: {verbs}")
        print(f"  pin  {entry['pin'][:16]}...")
    return 0


def cmd_services(_args: argparse.Namespace) -> int:
    svc = _services(sync=True)
    directory = svc.list_services()
    if not directory:
        print("service directory is empty")
        return 0
    for port, entry in directory.items():
        if entry["broken"]:
            print(f"{port}: BROKEN ({entry['broken']})")
        else:
            print(f"{port}: {', '.join(entry['verbs'])}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    hits = GalaxyRegistry(_levi_home()).search(args.query)
    if not hits:
        print(f"no packages match {args.query!r}")
        return 0
    for rec in hits:
        caps = ", ".join(rec.get("capabilities", [])[:4])
        print(f"{rec['id']}  {rec['version']}  ({rec.get('kind', '?')})")
        print(f"  {rec.get('description') or '(no description)'}")
        if caps:
            print(f"  capabilities: {caps}")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    from levi.galaxy import install as galaxy_install

    try:
        record = galaxy_install.install(args.source, home=_levi_home(), policy=None)
    except GalaxyInstallError as exc:
        return _fail(f"{type(exc).__name__}: {exc}")
    svc = _services()
    try:
        pkg = svc.register_installed(record, home=_levi_home())
    except GalaxyError as exc:
        return _fail(f"{type(exc).__name__}: {exc}")
    print(f"installed {pkg.id} {pkg.version}")
    print(f"  port: {pkg.port}")
    print(f"  verbs: {', '.join(sorted(pkg.entry_points))}")
    print(f"  pin: {pkg.pin}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    svc = _services(sync=True)
    try:
        pkg = svc.info(args.id)
    except UnknownPackage as exc:
        return _fail(str(exc))
    print(f"id:          {pkg.id}")
    print(f"name:         {pkg.name}")
    print(f"version:      {pkg.version}")
    print(f"kind:         {pkg.kind}")
    print(f"author:       {pkg.author or '(unknown)'}")
    print(f"description:  {pkg.description or '(none)'}")
    print(f"port:         {pkg.port}")
    print(f"pin:          {pkg.pin}")
    print(f"source:       {pkg.source or '(unknown)'}")
    print(f"installed_at: {pkg.installed_at}")
    if pkg.broken:
        print(f"broken:       {pkg.broken}")
    else:
        print("entry_points:")
        for verb, target in sorted(pkg.entry_points.items()):
            print(f"  {verb}: {target}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    svc = _services()
    found = False
    try:
        pkg = svc.remove(args.id)
        found = True
        print(f"removed {pkg.id} (port {pkg.port} unregistered)")
    except UnknownPackage:
        print(f"not in service directory: {args.id}")
    registry = GalaxyRegistry(_levi_home())
    record = registry.get(args.id)
    if record is not None:
        found = True
        registry.remove(args.id)
        shutil.rmtree(
            galaxy_trust.install_dir(_levi_home(), record), ignore_errors=True
        )
        print(f"uninstalled {args.id} (registry record and files removed)")
    if not found:
        return _fail(f"no package installed as {args.id!r}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m levi.galaxy",
        description="LEVI Galaxy ecosystem: install and inspect third-party skill/tool/service packages.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="list installed packages")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("services", help="show the live service directory")
    p.set_defaults(func=cmd_services)

    p = sub.add_parser("search", help="search installed packages")
    p.add_argument("query", help="substring to match against id/name/description/verbs")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser(
        "install", help="install a package from a directory, tarball, or git URL"
    )
    p.add_argument("source", help="package directory, .tar.gz/.zip file, or git URL")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("info", help="show detail for one package")
    p.add_argument("id", help="package id")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("remove", help="uninstall a package")
    p.add_argument("id", help="package id")
    p.set_defaults(func=cmd_remove)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except GalaxyError as exc:
        return _fail(f"{type(exc).__name__}: {exc}")
    except Exception as exc:  # never die with a bare traceback on a CLI path
        return _fail(f"unexpected {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    sys.exit(main())
