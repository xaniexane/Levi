"""Teletext pages: the numbered-page store and 40x24 grid renderer.

The Ceefax page was a 40-column by 24-row grid of text. Pages were
numbered 100-899; the first digit was the magazine. This module keeps the
grid and the namespace, clean-roomed, stdlib-only.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterator, List, Mapping, Optional, Tuple

COLS = 40
ROWS = 24
MIN_PAGE = 100
MAX_PAGE = 899
BODY_ROWS = ROWS - 4  # header + title + blank + footer

__all__ = [
    "COLS",
    "ROWS",
    "MIN_PAGE",
    "MAX_PAGE",
    "Page",
    "PageStore",
    "pages_from_mapping",
    "render_frame",
    "valid_page_number",
]


def valid_page_number(number: int) -> bool:
    return isinstance(number, int) and MIN_PAGE <= number <= MAX_PAGE


@dataclass
class Page:
    """One numbered teletext page.

    body is wrapped to 40 columns at render time; subpages rotate under
    one number (page 302/01, 302/02, ...) like Ceefax's subpage cycle.
    """

    number: int
    title: str
    body: List[str] = field(default_factory=list)
    subpage: int = 1
    subpages: int = 1

    def __post_init__(self) -> None:
        if not valid_page_number(self.number):
            raise ValueError(
                f"teletext page number must be {MIN_PAGE}-{MAX_PAGE}, got {self.number}"
            )
        if not 1 <= self.subpage <= max(1, self.subpages):
            raise ValueError(f"bad subpage {self.subpage}/{self.subpages}")
        self.title = str(self.title)[:COLS]


class PageStore:
    """The broadcast carousel's source of truth: numbered pages in order."""

    def __init__(self) -> None:
        self._pages: Dict[Tuple[int, int], Page] = {}
        self._order: List[Tuple[int, int]] = []

    def add(self, page: Page) -> Page:
        key = (page.number, page.subpage)
        if key not in self._pages:
            self._order.append(key)
        self._pages[key] = page
        return page

    def get(self, number: int, subpage: int = 1) -> Optional[Page]:
        return self._pages.get((number, subpage))

    def numbers(self) -> List[int]:
        return sorted({n for (n, _s) in self._order})

    def carousel(self, order: Optional[List[int]] = None) -> Iterator[Page]:
        """Endless broadcast loop over the pages, in number order.

        Mirrors the Ceefax transmission cycle: every page comes around in
        turn, forever. The receiver does the waiting, not the requesting.
        """
        seq = order if order is not None else [n for (n, _s) in self._order]
        if not seq:
            return
        while True:
            for number in seq:
                for (n, s) in self._order:
                    if n == number:
                        yield self._pages[(n, s)]

    def __len__(self) -> int:
        return len(self._pages)


def pages_from_mapping(
    title: str, mapping: Mapping[str, str], start: int = 100
) -> List[Page]:
    """Paginate a key/value mapping across numbered pages, like a Ceefax index.

    Each line is 'key .... value', wrapped to 40 columns; pages hold
    BODY_ROWS lines each.
    """
    lines: List[str] = []
    for key, value in mapping.items():
        line = f"{key}: {value}"
        lines.extend(textwrap.wrap(line, COLS) or [""])
    pages: List[Page] = []
    number = start
    for i in range(0, max(1, len(lines)), BODY_ROWS):
        pages.append(
            Page(number=number, title=title, body=lines[i : i + BODY_ROWS])
        )
        number += 1
    return pages


def render_frame(page: Page, clock: Optional[datetime] = None) -> str:
    """Render a page to the 40x24 grid, plain-text.

    Header row carries the page number and the clock, the way Ceefax's
    header row did — the viewer always knows what page they're on and
    that the carousel is alive.
    """
    now = clock or datetime.now()
    header = f"P{page.number:03d}".ljust(8) + "LEVI-PAGES".center(16) + now.strftime("%a %d %b %H:%M").rjust(16)
    sub = f" ({page.subpage}/{page.subpages})" if page.subpages > 1 else ""
    title = (page.title + sub)[:COLS]
    grid: List[str] = [header[:COLS], title, ""]
    for line in page.body[:BODY_ROWS]:
        grid.extend(textwrap.wrap(str(line), COLS) or [""])
    grid = grid[: ROWS - 1]
    grid += [""] * (ROWS - 1 - len(grid))
    grid.append("<<< 100-899 >>>".center(COLS))
    return "\n".join(line.ljust(COLS)[:COLS] for line in grid)
