"""CLI: python -m levi.forge <cmd> ...   (also wired as `levi forge`)

LEVI Forge — your code home, on your machine.

OWNERSHIP GUARANTEE: LEVI Forge never transmits your code anywhere.
There is no telemetry, no training corpus, no account, no cloud.
Nothing leaves localhost unless YOU push it. Everything works offline.
"""

from __future__ import annotations

import argparse
import json
import sys

from levi.forge import browse as _browse
from levi.forge import ci as _ci
from levi.forge import export as _export
from levi.forge import issues as _issues
from levi.forge import prs as _prs
from levi.forge import repos as _repos
from levi.forge import server as _server
from levi.forge import stars as _stars
from levi.forge.gitx import GitError, git_version
from levi.forge.home import forge_home

EPILOG = (
    "OWNERSHIP GUARANTEE: LEVI Forge never transmits your code anywhere. "
    "There is no telemetry, no training corpus, no account, no cloud. "
    "Nothing leaves localhost unless you push it. Fully offline."
)


def _err(msg) -> int:
    print("forge: %s" % msg, file=sys.stderr)
    return 2


def _ok(msg) -> int:
    print(msg)
    return 0


# -- serve -------------------------------------------------------------


def cmd_serve(args, home) -> int:
    try:
        _server.serve_forever(home=home, bind=args.bind, port=args.port)
    except (GitError, ValueError) as e:
        return _err(str(e))
    return 0


# -- repos -------------------------------------------------------------


def cmd_repos(args, home) -> int:
    try:
        if args.repos_action == "create":
            r = _repos.create_repo(home, args.name, description=args.desc or "")
            return _ok("created repo %r at %s" % (r["name"], r["path"]))
        if args.repos_action == "delete":
            if not args.yes:
                return _err("refusing: pass --yes to permanently delete %r" % args.name)
            _repos.delete_repo(home, args.name)
            return _ok("deleted repo %r (and its forge metadata)" % args.name)
        repos = _repos.list_repos(home)
        if args.json:
            print(json.dumps(repos, indent=2))
        elif not repos:
            print("no repos yet — `levi forge repos create <name>` to start")
        else:
            for r in repos:
                star = " ★" if _stars.is_starred(home, r["name"]) else ""
                print("%-24s %-8s %s%s" % (
                    r["name"], r["default_branch"] or "—",
                    r["description"] or "", star))
        return 0
    except (GitError, ValueError) as e:
        return _err(str(e))


# -- browse / log / stat -----------------------------------------------


def cmd_browse(args, home) -> int:
    try:
        if args.path and not args.path.endswith("/"):
            try:
                print(_browse.read_file(home, args.repo, rev=args.rev, path=args.path),
                      end="")
                return 0
            except GitError:
                pass  # fall through to tree listing
        entries = _browse.tree(home, args.repo, rev=args.rev, path=args.path or "")
        for e in entries:
            mark = "d" if e["type"] == "tree" else "-"
            print("%s %s" % (mark, e["name"]))
        return 0
    except (GitError, ValueError) as e:
        return _err(str(e))


def cmd_log(args, home) -> int:
    try:
        commits = _browse.log(home, args.repo, rev=args.rev, limit=args.limit)
    except (GitError, ValueError) as e:
        return _err(str(e))
    if args.json:
        print(json.dumps(commits, indent=2))
    else:
        for c in commits:
            print("%s  %s  %s  %s" % (c["sha"][:12], c["date"][:16],
                                      c["author"], c["subject"]))
    return 0


def cmd_stat(args, home) -> int:
    try:
        commits = _browse.log(home, args.repo, limit=100000)
    except (GitError, ValueError) as e:
        return _err(str(e))
    authors = {}
    for c in commits:
        authors[c["author"]] = authors.get(c["author"], 0) + 1
    stat = {
        "repo": args.repo,
        "commits": len(commits),
        "authors": authors,
        "issues_open": len(_issues.list_issues(home, args.repo, state="open")),
        "issues_closed": len(_issues.list_issues(home, args.repo, state="closed")),
        "prs_open": len(_prs.list_prs(home, args.repo, state="open")),
        "prs_merged": len(_prs.list_prs(home, args.repo, state="merged")),
        "starred": _stars.is_starred(home, args.repo),
        "ci_runs": len(_ci.list_runs(home, args.repo)),
    }
    if args.json:
        print(json.dumps(stat, indent=2))
    else:
        print("repo      %s" % stat["repo"])
        print("commits   %d (%d authors)" % (stat["commits"], len(authors)))
        print("issues    %d open / %d closed"
              % (stat["issues_open"], stat["issues_closed"]))
        print("prs       %d open / %d merged" % (stat["prs_open"], stat["prs_merged"]))
        print("starred   %s" % ("yes ★" if stat["starred"] else "no"))
        print("ci runs   %d" % stat["ci_runs"])
    return 0


# -- issues ------------------------------------------------------------


def cmd_issue(args, home) -> int:
    try:
        act = args.issue_action
        if act == "list":
            rows = _issues.list_issues(home, args.repo, state=args.state)
            if args.json:
                print(json.dumps(rows, indent=2))
            else:
                for i in rows:
                    print("#%-4d %-7s %s" % (i["id"], i["state"], i["title"]))
        elif act == "open":
            i = _issues.open_issue(home, args.repo, args.title,
                                   body=args.body or "",
                                   labels=args.label or [])
            print("opened issue #%d: %s" % (i["id"], i["title"]))
        elif act == "show":
            i = _issues.get_issue(home, args.repo, args.id)
            if i is None:
                return _err("no such issue: %s" % args.id)
            if args.json:
                print(json.dumps(i, indent=2))
            else:
                print("#%d %s [%s]" % (i["id"], i["title"], i["state"]))
                print("labels: %s" % ", ".join(i.get("labels", [])))
                print("opened %s by %s" % (i["created"][:16], i["author"]))
                if i["body"]:
                    print("\n%s" % i["body"])
                for c in i.get("comments", []):
                    print("\n--- %s (%s) ---\n%s" % (c["author"], c["at"][:16], c["body"]))
        elif act == "close":
            i = _issues.close_issue(home, args.repo, args.id)
            print("closed issue #%d" % i["id"])
        elif act == "reopen":
            i = _issues.reopen_issue(home, args.repo, args.id)
            print("reopened issue #%d" % i["id"])
        elif act == "comment":
            _issues.comment_issue(home, args.repo, args.id, args.body or "")
            print("comment added to #%d" % args.id)
        return 0
    except (GitError, ValueError) as e:
        return _err(str(e))


# -- pull requests -----------------------------------------------------


def cmd_pr(args, home) -> int:
    try:
        act = args.pr_action
        if act == "list":
            rows = _prs.list_prs(home, args.repo, state=args.state)
            if args.json:
                print(json.dumps(rows, indent=2))
            else:
                for p in rows:
                    print("#%-4d %-7s %s -> %s : %s"
                          % (p["id"], p["state"], p["head"], p["base"], p["title"]))
        elif act == "open":
            p = _prs.open_pr(home, args.repo, args.title, head=args.head,
                             base=args.base, body=args.body or "")
            print("opened PR #%d: %s (%s -> %s)"
                  % (p["id"], p["title"], p["head"], p["base"]))
        elif act == "show":
            p = _prs.get_pr(home, args.repo, args.id)
            if p is None:
                return _err("no such PR: %s" % args.id)
            if args.json:
                print(json.dumps(p, indent=2))
            else:
                print("#%d %s [%s]" % (p["id"], p["title"], p["state"]))
                print("%s -> %s" % (p["head"], p["base"]))
                if p["body"]:
                    print("\n%s" % p["body"])
                if p.get("merge_commit"):
                    print("merged as %s" % p["merge_commit"][:12])
        elif act == "merge":
            p = _prs.merge_pr(home, args.repo, args.id)
            print("merged PR #%d as %s" % (p["id"], p["merge_commit"][:12]))
        elif act == "close":
            p = _prs.close_pr(home, args.repo, args.id)
            print("closed PR #%d" % p["id"])
        return 0
    except (GitError, ValueError) as e:
        return _err(str(e))


# -- stars -------------------------------------------------------------


def cmd_star(args, home) -> int:
    try:
        if args.remove:
            print("unstarred %r" % args.repo if _stars.unstar(home, args.repo)
                  else "%r was not starred" % args.repo)
        else:
            _stars.star(home, args.repo)
            print("starred %r ★ (travels with exports)" % args.repo)
        return 0
    except (GitError, ValueError) as e:
        return _err(str(e))


def cmd_stars(args, home) -> int:
    for name in sorted(_stars.starred(home)):
        print("★ %s" % name)
    return 0


# -- export / import ---------------------------------------------------


def cmd_export(args, home) -> int:
    try:
        dest = _export.export_repo(home, args.repo, args.out or
                                   ("%s-forge-export" % args.repo))
        return _ok("exported %r -> %s (format %s)"
                   % (args.repo, dest, _export.FORMAT))
    except (GitError, ValueError) as e:
        return _err(str(e))


def cmd_import(args, home) -> int:
    try:
        r = _export.import_repo(home, args.src, name=args.name)
        return _ok("imported %r from %s" % (r["name"], r["imported_from"]))
    except (GitError, ValueError) as e:
        return _err(str(e))


# -- ci ----------------------------------------------------------------


def cmd_ci(args, home) -> int:
    try:
        act = args.ci_action
        if act == "init":
            pipe = _ci.init_pipeline(home, args.repo)
            print("wrote default pipeline (%d steps) for %r"
                  % (len(pipe["steps"]), args.repo))
        elif act == "show":
            pipe = _ci.load_pipeline(home, args.repo)
            if args.json:
                print(json.dumps(pipe, indent=2))
            else:
                for i, s in enumerate(pipe["steps"], 1):
                    print("%d. %s — %s" % (i, s["name"], s["run"]))
        elif act == "run":
            rec = _ci.run_pipeline(home, args.repo)
            for s in rec["steps"]:
                print("[%s] %s (rc=%d, %.1fs)"
                      % ("PASS" if s["rc"] == 0 else "FAIL",
                         s["name"], s["rc"], s["elapsed"]))
            print("run %s: %s" % (rec["id"], "PASS" if rec["ok"] else "FAIL"))
            return 0 if rec["ok"] else 1
        elif act == "runs":
            runs = _ci.list_runs(home, args.repo)[: args.limit]
            if args.json:
                print(json.dumps(runs, indent=2))
            else:
                for r in runs:
                    print("%s  %s  %s" % (r["id"],
                                          "PASS" if r["ok"] else "FAIL",
                                          r["started"][:16]))
        return 0
    except (GitError, ValueError) as e:
        return _err(str(e))


# -- parser ------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="levi forge",
        description="LEVI Forge — your local-first code home. " + EPILOG,
        epilog=EPILOG,
    )
    ap.add_argument("--version", action="store_true", help="print git version and exit")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("serve", help="serve git smart-HTTP + web UI on localhost")
    p.add_argument("--port", type=int, default=8741)
    p.add_argument("--bind", default="127.0.0.1",
                   help="localhost only (anything else is refused)")
    p.set_defaults(fn=cmd_serve)

    p = sub.add_parser("repos", help="create/list/delete repositories")
    p.add_argument("repos_action", nargs="?", default="list",
                   choices=["create", "list", "delete"])
    p.add_argument("name", nargs="?", default=None)
    p.add_argument("--desc", default="")
    p.add_argument("--yes", action="store_true",
                   help="confirm permanent deletion")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_repos)

    p = sub.add_parser("browse", help="file tree / file contents of a repo")
    p.add_argument("repo")
    p.add_argument("--rev", default=None, help="revision (default HEAD)")
    p.add_argument("--path", default="", help="path inside the repo")
    p.set_defaults(fn=cmd_browse)

    p = sub.add_parser("log", help="commit history")
    p.add_argument("repo")
    p.add_argument("--rev", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_log)

    p = sub.add_parser("stat", help="repo at a glance: commits, issues, PRs, stars, CI")
    p.add_argument("repo")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_stat)

    p = sub.add_parser("issue", help="issues (local JSONL)")
    p.add_argument("repo")
    p.add_argument("issue_action",
                   choices=["list", "open", "show", "close", "reopen", "comment"])
    p.add_argument("id", nargs="?", type=int, default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--body", default=None)
    p.add_argument("--label", action="append", default=[])
    p.add_argument("--state", default=None, choices=["open", "closed"])
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_issue)

    p = sub.add_parser("pr", help="pull requests (local JSONL)")
    p.add_argument("repo")
    p.add_argument("pr_action", choices=["list", "open", "show", "merge", "close"])
    p.add_argument("id", nargs="?", type=int, default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--body", default=None)
    p.add_argument("--head", default=None)
    p.add_argument("--base", default=None)
    p.add_argument("--state", default=None,
                   choices=["open", "merged", "closed"])
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_pr)

    p = sub.add_parser("star", help="star a repo (portable reputation, exports with the repo)")
    p.add_argument("repo")
    p.add_argument("--remove", action="store_true")
    p.set_defaults(fn=cmd_star)
    p = sub.add_parser("stars", help="list starred repos")
    p.set_defaults(fn=cmd_stars)

    p = sub.add_parser("export", help="one-command full export (bundle, issues, PRs, stars, CI, graph)")
    p.add_argument("repo")
    p.add_argument("--out", default=None, help="destination dir (must not exist)")
    p.set_defaults(fn=cmd_export)

    p = sub.add_parser("import", help="verify + rebuild a repo from a forge export")
    p.add_argument("src", help="export directory")
    p.add_argument("--name", default=None, help="repo name (default: from export)")
    p.set_defaults(fn=cmd_import)

    p = sub.add_parser("ci", help="local-first CI: pipelines run on this machine")
    p.add_argument("repo")
    p.add_argument("ci_action", choices=["init", "show", "run", "runs"])
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_ci)

    return ap


def main(argv=None, home=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.version:
        print("LEVI Forge / %s" % git_version())
        return 0
    if not getattr(args, "cmd", None):
        ap.print_help()
        return 2
    # Guard: sub-subcommands that need a repo name
    for attr in ("name", "repo"):
        if hasattr(args, attr) and getattr(args, attr) in (None, ""):
            if args.cmd in ("repos",) and attr == "name" and \
                    getattr(args, "repos_action", "list") == "list":
                continue
            return _err("%s requires a repo name" % args.cmd)
    if args.cmd == "repos" and args.repos_action in ("create", "delete") and not args.name:
        return _err("repos %s requires a name" % args.repos_action)
    if args.cmd == "issue" and args.issue_action == "open" and not args.title:
        return _err("issue open requires --title")
    if args.cmd == "pr" and args.pr_action == "open" and \
            not (args.title and args.head and args.base):
        return _err("pr open requires --title, --head and --base")
    if args.cmd == "issue" and args.issue_action in ("show", "close", "reopen", "comment") \
            and args.id is None:
        return _err("issue %s requires an id" % args.issue_action)
    if args.cmd == "issue" and args.issue_action == "comment" and not args.body:
        return _err("issue comment requires --body")
    if args.cmd == "pr" and args.pr_action in ("show", "merge", "close") and args.id is None:
        return _err("pr %s requires an id" % args.pr_action)
    try:
        return args.fn(args, home)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
