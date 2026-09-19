"""levi exodus — the Exit Button. Usage:

  python -m levi.exodus catalog            list the exit-hostility catalog
  python -m levi.exodus drill --platform X # show a sample drill template
  python -m levi.exodus audit <takeout.zip|dir>  audit a data export
"""

from __future__ import annotations

import argparse
import sys


def _cmd_catalog(_args) -> int:
    from .catalog import HOSTILITY_CATALOG
    for e in HOSTILITY_CATALOG:
        print("%s (%s, %d) [%s]" % (e.platform, e.giant, e.year, e.pattern))
        print("  refused exit: %s" % e.refused_exit)
        print("  signals: %s" % "; ".join(e.enclosure_signals))
        print("  record: %s" % e.record_id)
        print()
    return 0


def _cmd_drill(args) -> int:
    from .plan import Dependency, build_plan, lock_in_score, plan_to_markdown
    deps = [
        Dependency(name="post history", platform=args.platform, kind="data",
                   runway_days=None, local_substitute="local archive index"),
        Dependency(name="scheduled posts", platform=args.platform, kind="api",
                   runway_days=None, local_substitute="levi automation scheduler"),
        Dependency(name="login with platform", platform=args.platform, kind="login",
                   runway_days=None, local_substitute="local account store"),
    ]
    plan = build_plan(args.platform, deps)
    print(plan_to_markdown(plan))
    for d in deps:
        print("lock-in %s: %d/5" % (d.name, lock_in_score(d)))
    return 0


def _cmd_audit(args) -> int:
    from .audit import audit_export, audit_to_text
    print(audit_to_text(audit_export(args.path)))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="levi exodus")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("catalog", help="list the exit-hostility catalog")
    drill = sub.add_parser("drill", help="show a departure drill template")
    drill.add_argument("--platform", default="X (Twitter)")
    audit = sub.add_parser("audit", help="audit a takeout export")
    audit.add_argument("path")
    args = parser.parse_args(argv)
    handlers = {"catalog": _cmd_catalog, "drill": _cmd_drill, "audit": _cmd_audit}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
