"""Curated app catalog — a reviewed marketplace before the App Store.

Studied from: dead-networks-20260916, report.md [Danger Hiptop /
Sidekick] — the Danger app catalog, the first curated app marketplace:
submissions pass human review before they reach users.

This module models that pattern: developers ``submit`` apps into a
review queue; a curator ``approve``s or ``reject``s with a note; only
approved listings appear in the public catalog. Apps carry versions,
so updates re-enter review. Search ranks approved apps by name/description
match. Local data structures only — no installs, no signing, no devices.

Honesty: the "review" is a human decision recorded by the caller, not
an automated safety check — the module cannot vet code. The preserved
pattern is curation-as-gate: a single trusted catalog where the default
listing is *reviewed*, not unfiltered.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

ORIGIN = "levi-revival/app-catalog"


class ReviewStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class App:
    """One app listing: identity, content, and review state."""

    app_id: str
    name: str
    developer: str
    description: str
    version: str
    status: ReviewStatus = ReviewStatus.PENDING
    review_note: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("app name must not be empty")


class Catalog:
    """The curated marketplace: queue in, reviewed catalog out."""

    def __init__(self) -> None:
        self._apps: Dict[str, App] = {}

    def submit(self, app: App) -> App:
        """Submit a new app (or a new version) for review."""
        existing = self._apps.get(app.app_id)
        if existing is not None and existing.version == app.version:
            raise ValueError(
                f"{app.app_id!r} version {app.version!r} already submitted"
            )
        app.status = ReviewStatus.PENDING
        app.review_note = ""
        self._apps[app.app_id] = app
        return app

    def approve(self, app_id: str, note: str = "") -> App:
        """A curator approves the pending submission."""
        app = self._get(app_id)
        if app.status != ReviewStatus.PENDING:
            raise ValueError(f"{app_id!r} is not pending review")
        app.status = ReviewStatus.APPROVED
        app.review_note = note
        return app

    def reject(self, app_id: str, note: str) -> App:
        """A curator rejects the pending submission with a reason."""
        app = self._get(app_id)
        if app.status != ReviewStatus.PENDING:
            raise ValueError(f"{app_id!r} is not pending review")
        app.status = ReviewStatus.REJECTED
        app.review_note = note
        return app

    def withdraw(self, app_id: str) -> None:
        """Remove a listing entirely (developer takedown)."""
        self._get(app_id)
        del self._apps[app_id]

    def listing(self, app_id: str) -> App:
        """The public listing: only approved apps are visible."""
        app = self._get(app_id)
        if app.status != ReviewStatus.APPROVED:
            raise ValueError(f"{app_id!r} is not publicly listed")
        return app

    def browse(self) -> List[App]:
        """Every approved app, sorted by name."""
        return sorted(
            (a for a in self._apps.values() if a.status == ReviewStatus.APPROVED),
            key=lambda a: a.name.lower(),
        )

    def pending(self) -> List[App]:
        """The review queue."""
        return [a for a in self._apps.values() if a.status == ReviewStatus.PENDING]

    def search(self, query: str) -> List[App]:
        """Keyword search over approved apps, name weighted first."""
        q = query.strip().lower()
        if not q:
            return []
        scored = []
        for app in self.browse():
            name_hit = q in app.name.lower()
            desc_hit = q in app.description.lower()
            if name_hit or desc_hit:
                scored.append((0 if name_hit else 1, app.name.lower(), app))
        scored.sort()
        return [app for _, _, app in scored]

    def _get(self, app_id: str) -> App:
        app = self._apps.get(app_id)
        if app is None:
            raise ValueError(f"unknown app {app_id!r}")
        return app
