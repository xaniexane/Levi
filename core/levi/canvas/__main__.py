"""CLI: python -m levi.canvas — local workbench canvas.

Subcommands:
  new ID --type doc|code|plan --title T [--file F | --text T]
  edit ID [--file F | --text T] [--note NOTE]   append a new version
  show ID [--version N] [--file F]              print (or write) a version
  versions ID                                  list versions
  diff ID A B                                  unified diff between versions
  rename ID --title T
  list                                         list artifacts
  delete ID
  export ID DEST                               full bundle (all versions + manifest)

Home resolves at call time from --home, LEVI_HOME, or ~/.levi/canvas.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from levi.canvas.artifacts import ARTIFACT_TYPES, ArtifactStore, CanvasError, default_home


def _store(a) -> ArtifactStore:
    return ArtifactStore(Path(a.home) if a.home else default_home())


def _content(a) -> str:
    if a.file:
        return Path(a.file).read_text(encoding="utf-8")
    return a.text or ""


def cmd_new(a) -> int:
    try:
        meta = _store(a).create(a.id, a.type, a.title, content=_content(a))
    except (CanvasError, OSError) as exc:
        print(f"new refused: {exc}", file=sys.stderr)
        return 1
    print(f"created {meta['id']!r} [{meta['type']}] v1")
    return 0


def cmd_edit(a) -> int:
    try:
        n = _store(a).edit(a.id, _content(a), note=a.note or "")
    except (CanvasError, OSError) as exc:
        print(f"edit refused: {exc}", file=sys.stderr)
        return 1
    print(f"{a.id!r} -> v{n}")
    return 0


def cmd_show(a) -> int:
    try:
        got = _store(a).get(a.id, version=a.version)
    except CanvasError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if a.file:
        Path(a.file).write_text(got["content"], encoding="utf-8")
        print(f"wrote v{got['version']['n']} to {a.file}")
    else:
        print(f"=== {got['title']} [{got['type']}] v{got['version']['n']} ===")
        print(got["content"])
    return 0


def cmd_versions(a) -> int:
    try:
        versions = _store(a).versions(a.id)
    except CanvasError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    for v in versions:
        note = f" — {v['note']}" if v.get("note") else ""
        print(f"v{v['n']}: {v['chars']} chars{note}")
    return 0


def cmd_diff(a) -> int:
    try:
        print(_store(a).diff(a.id, a.a, a.b))
    except CanvasError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def cmd_rename(a) -> int:
    try:
        _store(a).rename(a.id, a.title)
    except CanvasError as exc:
        print(f"rename refused: {exc}", file=sys.stderr)
        return 1
    print(f"renamed {a.id!r}")
    return 0


def cmd_list(a) -> int:
    items = _store(a).list()
    if not items:
        print("no artifacts.")
        return 0
    for it in items:
        print(f"{it['id']:20} [{it['type']:4}] v{it['versions']:3}  {it['title']}")
    return 0


def cmd_delete(a) -> int:
    print("deleted" if _store(a).delete(a.id) else f"unknown artifact {a.id!r}")
    return 0


def cmd_export(a) -> int:
    try:
        dest = _store(a).export(a.id, Path(a.dest))
    except (CanvasError, OSError) as exc:
        print(f"export refused: {exc}", file=sys.stderr)
        return 1
    print(f"exported {a.id!r} -> {dest}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.canvas",
        description="local workbench canvas — versioned, exportable artifacts",
    )
    ap.add_argument("--home", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def _src(p):
        p.add_argument("--file", default=None, help="read content from file")
        p.add_argument("--text", default=None, help="content as argument")

    p = sub.add_parser("new", help="create an artifact")
    p.add_argument("id"); p.add_argument("--type", required=True, choices=ARTIFACT_TYPES)
    p.add_argument("--title", required=True); _src(p)
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("edit", help="append a new version")
    p.add_argument("id"); p.add_argument("--note", default=""); _src(p)
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("show", help="print a version")
    p.add_argument("id"); p.add_argument("--version", type=int, default=None)
    p.add_argument("--file", default=None, help="write to file instead")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("versions", help="list versions")
    p.add_argument("id"); p.set_defaults(func=cmd_versions)

    p = sub.add_parser("diff", help="diff two versions")
    p.add_argument("id"); p.add_argument("a", type=int); p.add_argument("b", type=int)
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("rename", help="rename an artifact")
    p.add_argument("id"); p.add_argument("--title", required=True)
    p.set_defaults(func=cmd_rename)

    p = sub.add_parser("list", help="list artifacts"); p.set_defaults(func=cmd_list)

    p = sub.add_parser("delete", help="delete an artifact")
    p.add_argument("id"); p.set_defaults(func=cmd_delete)

    p = sub.add_parser("export", help="export all versions + manifest")
    p.add_argument("id"); p.add_argument("dest"); p.set_defaults(func=cmd_export)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
