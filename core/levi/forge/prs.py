"""Pull requests — local-first JSONL, same atomic discipline as issues.

PR record::

    {
      "id": 1, "title": "...", "body": "...",
      "head": "feature-branch", "base": "main",
      "state": "open" | "merged" | "closed",
      "author": "local", "created": ..., "updated": ...,
      "merge_commit": "<sha>" | null
    }

Merging is done with the stock git binary: the bare repo is cloned to a
temp worktree, ``head`` is merged into ``base``, and the result is pushed
back. If the merge conflicts, nothing is pushed and the PR stays open —
Forge reports the conflict honestly instead of pretending.
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .gitx import GitError, run_git
from .home import forge_home, validate_name
from .jsonl import read_jsonl, write_jsonl
from .repos import repo_dir, repo_exists


def _path(home, name):
    return forge_home(home) / "prs" / (validate_name(name) + ".jsonl")


def _require_repo(home, name) -> str:
    name = validate_name(name)
    if not repo_exists(home, name):
        raise ValueError("no such repo: %r" % name)
    return name


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _branches(home, name):
    """Return set of branch names present in the bare repo."""
    out = run_git(
        ["for-each-ref", "--format=%(refname:short)", "refs/heads/"],
        cwd=repo_dir(home, name),
    ).stdout.decode("utf-8", "replace")
    return {l.strip() for l in out.splitlines() if l.strip()}


def list_prs(home, name, state: "str | None" = None):
    name = _require_repo(home, name)
    prs = read_jsonl(_path(home, name))
    if state:
        prs = [p for p in prs if p.get("state") == state]
    return sorted(prs, key=lambda p: p["id"])


def get_pr(home, name, pr_id: int):
    for p in list_prs(home, name):
        if p["id"] == pr_id:
            return p
    return None


def open_pr(home, name, title: str, head: str, base: str, body: str = "",
            author: str = "local") -> dict:
    name = _require_repo(home, name)
    if not title.strip():
        raise ValueError("PR title is required")
    branches = _branches(home, name)
    for label, br in (("head", head), ("base", base)):
        if br not in branches:
            raise ValueError(
                "%s branch %r does not exist in repo %r (have: %s)"
                % (label, br, name, ", ".join(sorted(branches)) or "none")
            )
    if head == base:
        raise ValueError("head and base must differ")
    prs = list_prs(home, name)
    pr = {
        "id": max([p["id"] for p in prs], default=0) + 1,
        "title": title.strip(),
        "body": body or "",
        "head": head,
        "base": base,
        "state": "open",
        "author": author,
        "created": _now(),
        "updated": _now(),
        "merge_commit": None,
    }
    prs.append(pr)
    write_jsonl(_path(home, name), prs)
    return pr


def _save(home, name, prs, updated: dict) -> dict:
    for idx, p in enumerate(prs):
        if p["id"] == updated["id"]:
            prs[idx] = updated
            break
    else:
        raise ValueError("no such PR: %s" % updated["id"])
    write_jsonl(_path(home, name), prs)
    return updated


def close_pr(home, name, pr_id: int) -> dict:
    pr = get_pr(home, name, pr_id)
    if pr is None:
        raise ValueError("no such PR: %s" % pr_id)
    if pr["state"] == "merged":
        raise ValueError("PR #%d is already merged" % pr_id)
    pr["state"] = "closed"
    pr["updated"] = _now()
    return _save(home, name, list_prs(home, name), pr)


def merge_pr(home, name, pr_id: int) -> dict:
    """Merge head into base with stock git. Conflicts -> GitError, PR untouched."""
    pr = get_pr(home, name, pr_id)
    if pr is None:
        raise ValueError("no such PR: %s" % pr_id)
    if pr["state"] != "open":
        raise ValueError("PR #%d is %s, not open" % (pr_id, pr["state"]))
    bare = repo_dir(home, name)
    tmp = Path(tempfile.mkdtemp(prefix="forge-merge-"))
    try:
        run_git(["clone", "-q", str(bare), str(tmp / "work")])
        work = tmp / "work"
        run_git(["-c", "user.name=LEVI Forge", "-c", "user.email=forge@localhost",
                 "checkout", "-q", pr["base"]], cwd=work)
        try:
            run_git(
                ["-c", "user.name=LEVI Forge", "-c", "user.email=forge@localhost",
                 "merge", "--no-ff", "-m",
                 "Merge branch '%s' (forge PR #%d)" % (pr["head"], pr["id"]),
                 "origin/" + pr["head"]],
                cwd=work,
            )
        except GitError as e:
            run_git(["merge", "--abort"], cwd=work, check=False)
            raise GitError(
                "merge of %r into %r conflicts; PR #%d left open — "
                "resolve locally and push, then merge again. %s"
                % (pr["head"], pr["base"], pr["id"], e)
            )
        run_git(["push", "-q", "origin", pr["base"]], cwd=work)
        sha = run_git(["rev-parse", "HEAD"], cwd=work).stdout.decode().strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    pr["state"] = "merged"
    pr["merge_commit"] = sha
    pr["updated"] = _now()
    return _save(home, name, list_prs(home, name), pr)
