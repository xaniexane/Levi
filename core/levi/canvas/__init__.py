"""LEVI canvas — local workbench canvas with versioned, exportable artifacts.

REMIX DELTA: Anthropic's canvas splits chat from work-product — but the
artifacts live on *their* servers, in *their* format, under *their*
retention. The giant pattern: your work product is a hostage of the
platform that helped you make it. The remix: the chat/work-product split
with every artifact versioned LOCALLY — every edit is a new immutable
version, diffs via stdlib difflib, multiple artifact types (doc, code,
plan), and FULL export (a tar.gz of every version plus a manifest) so the
work can leave LEVI any time. Monopoly-minus-one: open formats, no
lock-in.

What it ADDS that the giant refuses: artifact versions are content-
addressed and immutable — history is never rewritten, only appended —
and the export bundle is a first-class operation, not an afterthought
hiding three menus deep.

Stdlib-only. Local-first: everything under ``~/.levi/canvas/``.
"""

from __future__ import annotations

__all__ = ["SHELF"]

SHELF = {
    "name": "workbench canvas",
    "summary": (
        "Local workbench canvas: versioned immutable artifacts (doc/code/plan), "
        "difflib diff views, full tar.gz export of every version + manifest. "
        "Your work product, on your disk, portable."
    ),
    "items": [
        "artifacts: ArtifactStore (immutable versions, diff, rename, delete)",
        "export: full bundle export (versions + manifest.json)",
        "CLI: new/edit/show/diff/versions/export/list/delete",
    ],
}
