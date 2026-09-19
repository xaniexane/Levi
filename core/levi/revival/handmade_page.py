"""A handmade profile page: full HTML/CSS identity, user-authored.

Studied from: fallen-platforms-hunt-20260916/report.md [4. MySpace's handmade page]

The studied shape: a profile you *build* — full custom HTML and CSS,
hand-placed sections, identity as self-expression rather than a
uniform card the platform designed for you.

LEVI-native re-expression: a profile page as a structured document —
user-authored sections, a custom stylesheet, and a layout map — with
an honest, paranoid sanitizer for any raw HTML pasted in (no scripts,
no event handlers, no remote URLs) and a plain-text render for
terminals. The *expression* is preserved; the *attack surface* is not.

Honest limits: no JavaScript, ever — inline scripts and on* handlers
are stripped; remote resources (images, fonts, iframes) are dropped,
not fetched; the renderer emits static HTML/CSS only, never executed.
This is a composition model, not a browser.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field
from typing import List

ORIGIN = "levi-revival/handmade-page"

# Tags that express structure/content without behavior. Everything else is dropped.
_ALLOWED_TAGS = {
    "p",
    "br",
    "hr",
    "h1",
    "h2",
    "h3",
    "h4",
    "b",
    "i",
    "u",
    "strong",
    "em",
    "code",
    "pre",
    "ul",
    "ol",
    "li",
    "blockquote",
    "div",
    "span",
    "a",
    "table",
    "tr",
    "td",
    "th",
}
# url(...) and @import can smuggle remote fetches into otherwise-safe CSS.
_CSS_BLACKLIST = re.compile(r"url\s*\(|@import|expression\s*\(", re.IGNORECASE)
_TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)(\s[^<>]*)?>")
_ATTR_RE = re.compile(r'\s([a-zA-Z-]+)\s*=\s*(".*?"|\'.*?\'|[^\s>]+)')


class PageError(Exception):
    """Raised for bad sections, styles, or layout misuse."""


def sanitize_html(raw: str) -> str:
    """Keep structure, drop behavior: strip scripts, handlers, remote refs.

    Returns safe HTML where unknown tags are escaped (visible, not
    executed) and event-handler attributes are removed.
    """
    if "<script" in raw.lower():
        # Cut the whole script element rather than trying to clean it.
        raw = re.sub(
            r"<script.*?>.*?</script>", "", raw, flags=re.IGNORECASE | re.DOTALL
        )

    def _clean_tag(m: re.Match) -> str:
        closing, tag, attrs = m.group(1), m.group(2).lower(), (m.group(3) or "")
        if tag not in _ALLOWED_TAGS:
            return _html.escape(m.group(0))
        if tag == "a":
            kept = []
            for am in _ATTR_RE.finditer(attrs):
                name, val = am.group(1).lower(), am.group(2)
                if name == "href" and re.match(r"^(['\"]?)(#|mailto:)", val.strip()):
                    kept.append(f"href={val}")
            return f"<{closing}{tag}{''.join(' ' + k for k in kept)}>"
        # No attributes at all on other tags: simplest honest policy.
        return f"<{closing}{tag}>"

    return _TAG_RE.sub(_clean_tag, raw)


def sanitize_css(raw: str) -> str:
    """Drop remote-fetching and behavior-capable CSS; keep the rest."""
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("/*") or stripped.startswith("//"):
            continue
        if _CSS_BLACKLIST.search(stripped):
            continue  # dropped, not fetched — never a network call
        lines.append(stripped)
    return "\n".join(lines)


@dataclass
class Section:
    """One hand-placed block of a profile page."""

    name: str
    html: str  # raw; sanitized on render
    order: int = 0


@dataclass
class HandmadePage:
    """A full user-authored profile: sections, CSS, layout."""

    owner: str
    title: str = "my page"
    sections: List[Section] = field(default_factory=list)
    custom_css: str = ""
    layout: List[str] = field(default_factory=list)  # section names, top to bottom

    def add_section(self, name: str, html: str) -> Section:
        name = name.strip()
        if not name:
            raise PageError("section name may not be blank")
        if any(s.name.lower() == name.lower() for s in self.sections):
            raise PageError(f"duplicate section: {name!r}")
        section = Section(name=name, html=html, order=len(self.sections))
        self.sections.append(section)
        self.layout.append(name)
        return section

    def restack(self, names: List[str]) -> None:
        """Reorder the page top-to-bottom by section name."""
        have = {s.name for s in self.sections}
        if set(names) != have:
            raise PageError("restack must name every section exactly once")
        self.layout = list(names)

    def set_css(self, css: str) -> str:
        """Store the sanitized stylesheet; returns what survived."""
        self.custom_css = sanitize_css(css)
        return self.custom_css

    def render(self) -> str:
        """Emit static HTML: sanitized sections in layout order + CSS."""
        by_name = {s.name: s for s in self.sections}
        blocks = []
        for name in self.layout:
            section = by_name[name]
            blocks.append(
                f'<section data-name="{_html.escape(name)}">'
                f"{sanitize_html(section.html)}</section>"
            )
        css = f"<style>\n{self.custom_css}\n</style>" if self.custom_css.strip() else ""
        return (
            f'<!DOCTYPE html>\n<html>\n<head><meta charset="utf-8">'
            f"<title>{_html.escape(self.title)}</title>\n{css}</head>\n"
            f"<body>\n" + "\n".join(blocks) + "\n</body>\n</html>"
        )

    def render_text(self) -> str:
        """Plain-text fallback for terminals: title + section names."""
        lines = [self.title, "=" * max(1, len(self.title))]
        for name in self.layout:
            by_name = {s.name: s for s in self.sections}
            text = re.sub(r"<[^>]+>", "", by_name[name].html)
            lines.append(f"\n[{name}]\n{text.strip()}")
        return "\n".join(lines)
