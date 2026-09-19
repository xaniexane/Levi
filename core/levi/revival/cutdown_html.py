"""cutdown_html — repurpose the real web instead of forking it.

Studied from: dead-networks-20260916/report.md (i-mode: cut-down
HTML, c-HTML — existing sites repurposed for mobile instead of
authoring a parallel mobile universe).

The load-bearing idea: do not ask the world to write a second web.
Take ordinary HTML and *reduce* it to a safe, tiny subset the
constrained client can render: keep structure and links, drop
scripts, styles, forms, and presentational noise. One universe,
graded by capability.

LEVI's take: ``cutdown(html)`` parses with ``html.parser`` and
emits a reduced markup document using only the allowed tag set
(a, p, br, b, i, strong, em, ul, ol, li, h1-h3, img). Everything
else is unwrapped or dropped per the policy; removed elements are
counted and reported in ``CutdownResult``. This is an original,
from-scratch implementation for LEVI.

Honest limits: heuristic reduction, not a validator — malformed
HTML is handled on a best-effort basis. ``img`` tags keep only
``src``/``alt``. The output is a simplified markup string, not a
guarantee any particular device renders it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List

ORIGIN = "levi-revival/cutdown-html"

# Tags that survive, mapped to the tag emitted (same tag here).
ALLOWED = {
    "a",
    "p",
    "br",
    "b",
    "i",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "img",
}
# Tags whose entire subtree is dropped (no text kept).
DROPPED_WHOLE = {"script", "style", "form", "iframe", "object", "embed", "noscript"}
# Tags unwrapped: tag removed, text content kept.
VOID = {"br", "img"}


@dataclass
class CutdownResult:
    """The reduced document plus what was removed."""

    markup: str
    original_chars: int
    removed_tags: Dict[str, int] = field(default_factory=dict)
    kept_links: int = 0

    @property
    def reduction_ratio(self) -> float:
        if self.original_chars == 0:
            return 0.0
        return 1.0 - len(self.markup) / self.original_chars


class _Reducer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.removed: Dict[str, int] = {}
        self.kept_links = 0
        self._drop_depth = 0
        self._open: List[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        tag = tag.lower()
        if self._drop_depth:
            self._drop_depth += 1
            return
        if tag in DROPPED_WHOLE:
            self._drop_depth = 1
            self.removed[tag] = self.removed.get(tag, 0) + 1
            return
        if tag not in ALLOWED:
            self.removed[tag] = self.removed.get(tag, 0) + 1
            return  # unwrapped: keep children
        if tag == "br":
            self.parts.append("<br>")
            return
        if tag == "img":
            kept = {k: v for k, v in attrs if k in ("src", "alt")}
            attr = "".join(f' {k}="{v}"' for k, v in kept.items())
            self.parts.append(f"<img{attr}>")
            return
        if tag == "a":
            href = next((v for k, v in attrs if k == "href"), "")
            self.parts.append(f'<a href="{href}">')
            self.kept_links += 1
        else:
            self.parts.append(f"<{tag}>")
        self._open.append(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._drop_depth:
            self._drop_depth -= 1
            return
        if tag in ALLOWED and tag not in VOID:
            # close only tags we actually opened (best effort)
            if tag in self._open:
                while self._open:
                    opened = self._open.pop()
                    self.parts.append(f"</{opened}>")
                    if opened == tag:
                        break

    def handle_data(self, data: str) -> None:
        if self._drop_depth:
            return
        self.parts.append(data)


def cutdown(html: str, collapse_whitespace: bool = True) -> CutdownResult:
    """Reduce ``html`` to the cut-down subset."""
    reducer = _Reducer()
    reducer.feed(html)
    reducer.close()
    markup = "".join(reducer.parts)
    if collapse_whitespace:
        markup = " ".join(markup.split())
    return CutdownResult(
        markup=markup,
        original_chars=len(html),
        removed_tags=dict(reducer.removed),
        kept_links=reducer.kept_links,
    )


def demo() -> dict:
    """Reduce a bloated sample page."""
    html = """
    <html><head><style>body{color:red}</style>
    <script>alert('hi')</script></head>
    <body><div class="chrome"><h1>Real News</h1>
    <p>Read <a href="/more"><b>more</b></a> here.</p>
    <form><input type="text"></form>
    <img src="pic.png" alt="a picture" onclick="x()">
    </div></body></html>
    """
    result = cutdown(html)
    return {
        "markup": result.markup,
        "removed": result.removed_tags,
        "kept_links": result.kept_links,
        "reduction_ratio": round(result.reduction_ratio, 3),
    }
