"""Issues — local-first JSONL. One line per issue, plain JSON, human-readable,
append-friendly, greppable. Same atomic-write discipline as the Archive store.

Issue record::

    {
      "id": 1,                      # sequential per repo, never reused
      "title": "...", "body": "...",
      "state": "open" | "closed",
      "labels": ["bug", ...],
      "author": "local",             # no accounts; forge is single-user local
      "created": "<iso>", "updated": "<iso>", "closed": "<iso>" | null,
      "comments": [{"author": ..., "at": ..., "body": ...}]
    }
"""

from __future__ import annotations

from datetime import datetime, timezone

from .home import forge_home, validate_name
from .jsonl import read_jsonl, write_jsonl
from .repos import repo_exists


def _path(home, name):
    return forge_home(home) / "issues" / (validate_name(name) + ".jsonl")


def _require_repo(home, name) -> str:
    name = validate_name(name)
    if not repo_exists(home, name):
        raise ValueError("no such repo: %r" % name)
    return name


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_issues(home, name, state: "str | None" = None):
    name = _require_repo(home, name)
    issues = read_jsonl(_path(home, name))
    if state:
        issues = [i for i in issues if i.get("state") == state]
    return sorted(issues, key=lambda i: i["id"])


def get_issue(home, name, issue_id: int):
    for i in list_issues(home, name):
        if i["id"] == issue_id:
            return i
    return None


def open_issue(
    home, name, title: str, body: str = "", labels=(), author: str = "local"
) -> dict:
    name = _require_repo(home, name)
    title = title.strip()
    if not title:
        raise ValueError("issue title is required")
    issues = list_issues(home, name)
    issue = {
        "id": max([i["id"] for i in issues], default=0) + 1,
        "title": title,
        "body": body or "",
        "state": "open",
        "labels": list(labels or []),
        "author": author,
        "created": _now(),
        "updated": _now(),
        "closed": None,
        "comments": [],
    }
    issues.append(issue)
    write_jsonl(_path(home, name), issues)
    return issue


def _save(home, name, issues, updated: dict) -> dict:
    for idx, i in enumerate(issues):
        if i["id"] == updated["id"]:
            issues[idx] = updated
            break
    else:
        raise ValueError("no such issue: %s" % updated["id"])
    write_jsonl(_path(home, name), issues)
    return updated


def close_issue(home, name, issue_id: int) -> dict:
    issue = get_issue(home, name, issue_id)
    if issue is None:
        raise ValueError("no such issue: %s" % issue_id)
    issue["state"] = "closed"
    issue["closed"] = _now()
    issue["updated"] = _now()
    return _save(home, name, list_issues(home, name), issue)


def reopen_issue(home, name, issue_id: int) -> dict:
    issue = get_issue(home, name, issue_id)
    if issue is None:
        raise ValueError("no such issue: %s" % issue_id)
    issue["state"] = "open"
    issue["closed"] = None
    issue["updated"] = _now()
    return _save(home, name, list_issues(home, name), issue)


def comment_issue(home, name, issue_id: int, body: str, author: str = "local") -> dict:
    issue = get_issue(home, name, issue_id)
    if issue is None:
        raise ValueError("no such issue: %s" % issue_id)
    if not body.strip():
        raise ValueError("comment body is required")
    issue["comments"].append({"author": author, "at": _now(), "body": body})
    issue["updated"] = _now()
    return _save(home, name, list_issues(home, name), issue)
