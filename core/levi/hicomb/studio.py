"""Hicomb Studio: the single-file web IDE.

The studio UI is ONE self-contained HTML file — no build step, no CDN,
no network at runtime. It opens from file:// on Chauncey's phone and
works fully offline.

LAWS:
  I6 SELF-CONTAINED  check_self_contained() must report zero violations:
                     no http(s) URLs in src/href, no @import, no url(http),
                     no protocol-relative //cdn references.
  I7 PANELS-PRESENT  every id in REQUIRED_IDS exists in the document.

This module is the machine-checkable guard for both laws; the tests in
tests/test_hicomb_studio.py run it against the shipped file.
"""

from __future__ import annotations

import re
from pathlib import Path

STUDIO_DIR = Path(__file__).resolve().parent / "web"
STUDIO_HTML = STUDIO_DIR / "hicomb-studio.html"

# Every major surface the studio promises. If the HTML drops one, the
# guard fails the build.
REQUIRED_IDS = (
    "nameplate",      # card title bar
    "filetree",       # file tree panel
    "tabstrip",       # editor tabs
    "editor",         # the editing surface (textarea)
    "gutter",         # line numbers
    "ghost",          # inline ghost-text completion layer
    "aipanel",        # AI pair-programmer sidebar
    "aichat",         # AI chat log
    "aiinput",        # AI chat input
    "palette",        # command palette overlay
    "dock",           # bottom dock (terminal / problems / output)
    "pane-terminal",  # studio console pane
    "problems",       # problems view
    "statusbar",      # card edition stamp strip
    "settings",       # settings modal
)

# Patterns that would break offline-from-file:// or pull remote code.
EXTERNAL_PATTERNS = (
    re.compile(r'''\bsrc\s*=\s*["']https?://''', re.IGNORECASE),
    re.compile(r'''\bhref\s*=\s*["']https?://''', re.IGNORECASE),
    re.compile(r'''url\(\s*["']?https?://''', re.IGNORECASE),
    re.compile(r'''@import\s+["']https?://''', re.IGNORECASE),
    re.compile(r'''\bsrc\s*=\s*["']//(?!/)''', re.IGNORECASE),
    re.compile(r'''\bhref\s*=\s*["']//(?!/)''', re.IGNORECASE),
    re.compile(r'''\bfrom\s+["']https?://''', re.IGNORECASE),  # es module import
)


def _read_html(path: str | Path | None) -> tuple[Path, str]:
    """Read the studio HTML. Unreadable files raise as a guard failure."""
    target = Path(path) if path else STUDIO_HTML
    try:
        return target, target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"studio guard cannot read {target}: {exc}") from exc


def check_self_contained(path: str | Path | None = None) -> list[str]:
    """Return a list of external-reference violations (empty = clean)."""
    target, text = _read_html(path)
    violations: list[str] = []
    for i, line in enumerate(text.split("\n"), 1):
        for pat in EXTERNAL_PATTERNS:
            if pat.search(line):
                violations.append(f"L{i}: {line.strip()[:100]}")
                break
    return violations


def check_panels(path: str | Path | None = None) -> list[str]:
    """Return the REQUIRED_IDS missing from the document (empty = all present).

    Id matching is quote-agnostic: id="x" and id='x' both count.
    """
    target, text = _read_html(path)
    missing = [
        pid
        for pid in REQUIRED_IDS
        if not re.search(rf'id\s*=\s*["\']{re.escape(pid)}["\']', text)
    ]
    return missing


def studio_manifest() -> dict:
    """What the studio ships: panels, laws, offline contract."""
    return {
        "name": "Hicomb Studio",
        "file": str(STUDIO_HTML),
        "panels": list(REQUIRED_IDS),
        "laws": [
            "I1 pollen-abort: formatter failure aborts the write",
            "I4 honest-source: completions labeled local until a model is seated",
            "I5 gbc-geometry: angular, corner_radius 0",
            "I6 self-contained: zero external references, works from file://",
        ],
        "offline": True,
    }
