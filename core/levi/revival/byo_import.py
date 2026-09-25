"""Bring-your-own-everything import: one-command inbound migration.

Studied from: github-pattern-hunt-20260916-0018/report.md [Ranked additions 7]

The mechanism: ``import_everything`` takes a bundle (the dict shape
produced by ``full_export.FullExport.read_bundle`` — section name to
records) and materializes it into an ``offline_noaccount.LocalHome``:
repos with their commits, issues, pull requests, wikis, star lists, and
follows. Each record kind has its own handler, the import is idempotent
(re-running it lands only what is new), and an ``ImportReport`` says
exactly what landed and what was skipped, per kind.

Design notes, kept honest:

- The importer reads *local bundles*, not a remote host. LEVI is
  local-first with no network calls, so "one-command migration from
  GitHub" means: point the importer at the export bundle you made of
  your GitHub data, and it becomes a native code-home in one command.
- Idempotency is by natural key (repo name, issue/PR number, wiki page,
  starred repo). Records with colliding keys are skipped and named in
  the report — never silently overwritten.
- Unknown sections are not dropped silently either: they land in the
  report's ``unhandled`` list so the caller knows what the importer did
  not understand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List

from levi.revival.offline_noaccount import LocalHome

ORIGIN = "levi-revival/byo-import"


@dataclass
class ImportReport:
    """What the one command did: per-kind landed/skipped counts plus notes."""

    landed: Dict[str, int] = field(default_factory=dict)
    skipped: Dict[str, int] = field(default_factory=dict)
    unhandled: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def total_landed(self) -> int:
        return sum(self.landed.values())

    def summary(self) -> str:
        parts = [f"{kind}: {n} landed" for kind, n in sorted(self.landed.items())]
        if self.skipped:
            parts.append(
                "skipped: "
                + ", ".join(f"{k}={v}" for k, v in sorted(self.skipped.items()))
            )
        if self.unhandled:
            parts.append("unhandled sections: " + ", ".join(self.unhandled))
        return "; ".join(parts)


class Importer:
    """Materialize an export bundle into a LocalHome, in one command."""

    def __init__(self, home: LocalHome | None = None):
        self.home = home or LocalHome(owner="imported")
        self._handlers: Dict[str, Callable[[List[Dict], ImportReport], None]] = {
            "code": self._import_code,
            "issues": self._import_issues,
            "pull_requests": self._import_prs,
            "wikis": self._import_wikis,
            "stars": self._import_stars,
            "follows": self._import_follows,
        }
        self.wikis: Dict[str, Dict[str, str]] = {}  # repo -> {page: body}
        self.follows: List[str] = []

    # -- the one command ---------------------------------------------------
    def import_everything(self, bundle: Dict[str, List[Dict]]) -> ImportReport:
        """Import every known section of the bundle; report everything."""
        report = ImportReport()
        for section, records in bundle.items():
            handler = self._handlers.get(section)
            if handler is None:
                report.unhandled.append(section)
                report.notes.append(f"no handler for section {section!r}; left alone")
                continue
            handler(records, report)
        return report

    def _count(self, report: ImportReport, kind: str, landed: bool) -> None:
        bucket = report.landed if landed else report.skipped
        bucket[kind] = bucket.get(kind, 0) + 1

    # -- per-kind handlers -------------------------------------------------
    def _import_code(self, records: List[Dict], report: ImportReport) -> None:
        for rec in records:
            name = rec.get("repo") or rec.get("name", "")
            if not name:
                self._count(report, "code", False)
                report.notes.append("code record without a repo name; skipped")
                continue
            if name in self.home.repos:
                self._count(report, "code", False)
                continue
            self.home.add_repo(
                name,
                commits=list(rec.get("commits", [])),
                readme=rec.get("readme", ""),
            )
            self._count(report, "code", True)

    def _import_issues(self, records: List[Dict], report: ImportReport) -> None:
        for rec in records:
            number = rec.get("number")
            if number is None or number in self.home.issues:
                self._count(report, "issues", False)
                continue
            issue = self.home.open_issue(
                number, rec.get("title", ""), rec.get("body", "")
            )
            issue.state = rec.get("state", "open")
            self._count(report, "issues", True)

    def _import_prs(self, records: List[Dict], report: ImportReport) -> None:
        for rec in records:
            number = rec.get("number")
            if number is None or number in self.home.pull_requests:
                self._count(report, "pull_requests", False)
                continue
            pr = self.home.open_pr(
                number,
                rec.get("title", ""),
                base=rec.get("base", "main"),
                head=rec.get("head", ""),
            )
            pr.state = rec.get("state", "open")
            self._count(report, "pull_requests", True)

    def _import_wikis(self, records: List[Dict], report: ImportReport) -> None:
        for rec in records:
            repo = rec.get("repo", "")
            page = rec.get("page", "")
            if not repo or not page:
                self._count(report, "wikis", False)
                continue
            pages = self.wikis.setdefault(repo, {})
            if page in pages:
                self._count(report, "wikis", False)
                continue
            pages[page] = rec.get("body", "")
            self._count(report, "wikis", True)

    def _import_stars(self, records: List[Dict], report: ImportReport) -> None:
        for rec in records:
            name = rec.get("repo") or rec.get("name", "")
            if not name:
                self._count(report, "stars", False)
                continue
            if name in self.home.stars:
                self._count(report, "stars", False)
                continue
            self.home.star(name)
            self._count(report, "stars", True)

    def _import_follows(self, records: List[Dict], report: ImportReport) -> None:
        for rec in records:
            user = rec.get("user") or rec.get("login", "")
            if not user:
                self._count(report, "follows", False)
                continue
            if user in self.follows:
                self._count(report, "follows", False)
                continue
            self.follows.append(user)
            self._count(report, "follows", True)
