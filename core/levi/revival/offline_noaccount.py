"""Offline-without-account operation: a code-home that needs nobody's server.

Studied from: github-pattern-hunt-20260916-0018/report.md [Ranked additions 5]

The mechanism: a ``LocalHome`` holds repositories, issues, pull requests,
and stars as plain local data keyed by a locally-generated ``Identity``
(no account, no signup, no token). Everything works with the machine
alone. When two machines meet, ``sync_with_peer`` merges their state as a
peer operation — union of records, last-writer-wins on conflicts, and a
conflict log that names every decision instead of hiding it.

Design notes, kept honest:

- The peer sync here runs in-process between two ``LocalHome`` objects;
  the merge rules are written so the same logic applies over a wire —
  ``peer_snapshot`` / ``apply_peer_snapshot`` split the merge into a
  serializable exchange and a local apply. No network is performed.
- Last-writer-wins resolves by ``updated_at`` timestamps, which peers can
  lie about. The conflict log makes every resolution visible so a human
  can audit it; this is a convenience merge, not Byzantine agreement.
- Identity is a random fingerprint. It proves nothing about a person;
  it only lets a home name itself without asking a server.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, List

ORIGIN = "levi-revival/offline-noaccount"


@dataclass(frozen=True)
class Identity:
    """A self-made identity: random, local, answerable to no registry."""

    fingerprint: str

    @staticmethod
    def generate(label: str = "") -> "Identity":
        seed = secrets.token_hex(16) + label
        return Identity(fingerprint=hashlib.sha256(seed.encode()).hexdigest()[:32])

    def short(self) -> str:
        return self.fingerprint[:12]


@dataclass
class Repo:
    name: str
    commits: List[Dict] = field(default_factory=list)  # {sha, message, at}
    readme: str = ""
    updated_at: float = field(default_factory=time.time)


@dataclass
class Issue:
    number: int
    title: str
    body: str = ""
    state: str = "open"  # open | closed
    updated_at: float = field(default_factory=time.time)


@dataclass
class PullRequest:
    number: int
    title: str
    base: str = "main"
    head: str = ""
    state: str = "open"
    updated_at: float = field(default_factory=time.time)


@dataclass
class Conflict:
    """A merge decision that was made for you, written down for audit."""

    kind: str  # repo | issue | pull_request
    key: str
    chosen: str  # "local" | "peer"
    detail: str


class LocalHome:
    """A complete code-home on one machine. No account. No connectivity."""

    def __init__(self, owner: str = ""):
        self.identity = Identity.generate(owner)
        self.owner = owner or self.identity.short()
        self.repos: Dict[str, Repo] = {}
        self.issues: Dict[int, Issue] = {}
        self.pull_requests: Dict[int, PullRequest] = {}
        self.stars: List[str] = []
        self._conflicts: List[Conflict] = []

    # -- local operations: everything works offline ----------------------
    def add_repo(
        self, name: str, commits: List[Dict] | None = None, readme: str = ""
    ) -> Repo:
        repo = Repo(name=name, commits=commits or [], readme=readme)
        self.repos[name] = repo
        return repo

    def commit(self, repo_name: str, sha: str, message: str) -> None:
        repo = self.repos[repo_name]
        repo.commits.append({"sha": sha, "message": message, "at": time.time()})
        repo.updated_at = time.time()

    def open_issue(self, number: int, title: str, body: str = "") -> Issue:
        issue = Issue(number=number, title=title, body=body)
        self.issues[number] = issue
        return issue

    def open_pr(
        self, number: int, title: str, base: str = "main", head: str = ""
    ) -> PullRequest:
        pr = PullRequest(number=number, title=title, base=base, head=head)
        self.pull_requests[number] = pr
        return pr

    def star(self, repo_name: str) -> None:
        if repo_name not in self.stars:
            self.stars.append(repo_name)

    def conflicts(self) -> List[Conflict]:
        return list(self._conflicts)

    # -- peer sync: the wire-shaped half ---------------------------------
    def peer_snapshot(self) -> Dict:
        """The serializable half of sync: everything a peer needs to merge."""
        return {
            "identity": self.identity.fingerprint,
            "owner": self.owner,
            "repos": {
                name: {
                    "commits": r.commits,
                    "readme": r.readme,
                    "updated_at": r.updated_at,
                }
                for name, r in self.repos.items()
            },
            "issues": {
                n: {
                    "title": i.title,
                    "body": i.body,
                    "state": i.state,
                    "updated_at": i.updated_at,
                }
                for n, i in self.issues.items()
            },
            "pull_requests": {
                n: {
                    "title": p.title,
                    "base": p.base,
                    "head": p.head,
                    "state": p.state,
                    "updated_at": p.updated_at,
                }
                for n, p in self.pull_requests.items()
            },
            "stars": list(self.stars),
        }

    def apply_peer_snapshot(self, snap: Dict) -> List[Conflict]:
        """Merge a peer's snapshot into this home; return the conflicts found."""
        new_conflicts: List[Conflict] = []

        for name, rdata in snap["repos"].items():
            local = self.repos.get(name)
            if local is None:
                self.repos[name] = Repo(
                    name=name,
                    commits=rdata["commits"],
                    readme=rdata["readme"],
                    updated_at=rdata["updated_at"],
                )
            else:
                known = {c["sha"] for c in local.commits}
                fresh = [c for c in rdata["commits"] if c["sha"] not in known]
                if fresh:
                    local.commits.extend(fresh)
                    local.commits.sort(key=lambda c: c.get("at", 0))
                if (
                    rdata["updated_at"] > local.updated_at
                    and rdata["readme"] != local.readme
                ):
                    new_conflicts.append(
                        Conflict(
                            kind="repo",
                            key=name,
                            chosen="peer",
                            detail="peer readme was newer; took peer version",
                        )
                    )
                    local.readme = rdata["readme"]
                local.updated_at = max(local.updated_at, rdata["updated_at"])

        new_conflicts.extend(
            self._merge_records(
                snap["issues"], self.issues, "issue", lambda n, d: Issue(n, **d)
            )
        )
        new_conflicts.extend(
            self._merge_records(
                snap["pull_requests"],
                self.pull_requests,
                "pull_request",
                lambda n, d: PullRequest(n, **d),
            )
        )

        for star in snap["stars"]:
            if star not in self.stars:
                self.stars.append(star)

        self._conflicts.extend(new_conflicts)
        return new_conflicts

    def _merge_records(
        self, peer: Dict, local: Dict, kind: str, build
    ) -> List[Conflict]:
        found: List[Conflict] = []
        for key, pdata in peer.items():
            existing = local.get(key)
            if existing is None:
                local[key] = build(key, pdata)
                continue
            if pdata["updated_at"] <= existing.updated_at:
                continue
            # Peer is newer: check whether it actually differs.
            differs = any(
                pdata.get(f) != getattr(existing, f)
                for f in ("title", "body", "state", "base", "head")
                if f in pdata
            )
            if differs:
                found.append(
                    Conflict(
                        kind=kind,
                        key=str(key),
                        chosen="peer",
                        detail=f"peer version newer (at {pdata['updated_at']:.0f}); took peer",
                    )
                )
                local[key] = build(key, pdata)
            else:
                existing.updated_at = pdata["updated_at"]
        return found

    def sync_with_peer(self, peer: "LocalHome") -> Dict[str, object]:
        """Full peer sync: both homes exchange snapshots and merge.

        Returns a report of what moved and what conflicted. Either side
        can initiate; the merge is symmetric.
        """
        mine, theirs = self.peer_snapshot(), peer.peer_snapshot()
        my_conflicts = self.apply_peer_snapshot(theirs)
        peer_conflicts = peer.apply_peer_snapshot(mine)
        return {
            "peer": peer.identity.short(),
            "my_conflicts": [c.__dict__ for c in my_conflicts],
            "peer_conflicts": [c.__dict__ for c in peer_conflicts],
            "repos": sorted(self.repos),
            "issues": sorted(self.issues),
            "pull_requests": sorted(self.pull_requests),
            "stars": sorted(self.stars),
        }
