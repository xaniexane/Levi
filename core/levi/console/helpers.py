"""Pure (I/O-free) helpers for the LEVI interactive console.

Everything in this module is a pure function over data — no ``input()``,
no printing, no network — so it can be unit-tested hermetically.
The screen handlers in :mod:`levi.console.screens` own all prompting
and rendering; they delegate to these helpers for filtering, paging,
and formatting.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

# -- demand digest ----------------------------------------------------------

#: Tier name -> ux ``color()`` foreground name.
TIER_COLORS: Dict[str, str] = {
    "high": "green",
    "watch": "yellow",
    "low": "red",
}


def tier_color(tier: str) -> str:
    """Foreground color name for a five-factor tier; unknown tiers stay plain."""
    return TIER_COLORS.get(tier, "gray")


# -- bounty recon stage inference ------------------------------------------

#: Human labels for the three recon pipeline stages (enum -> probe -> content).
STAGE_LABELS: Tuple[str, str, str] = ("enum", "probe hosts", "content")

#: Finding kind -> pipeline stage index, derived from
#: :mod:`levi.bounty.pipeline` (``subdomain`` is added in enum, port/http/tls
#: in probe, archived/js/exposure in content).
_STAGE_BY_KIND: Dict[str, int] = {
    "subdomain": 0,
    "open_port": 1,
    "http_service": 1,
    "tls_cert": 1,
    "archived_url": 2,
    "js_endpoint": 2,
    "possible_exposure": 2,
}


def stage_for_kind(kind: str) -> int:
    """Pipeline stage index (0-based) that produces findings of ``kind``.

    Unknown kinds map to the last stage — the finding landed, the bar just
    cannot place it earlier.
    """
    return _STAGE_BY_KIND.get(kind, len(STAGE_LABELS) - 1)


# -- security browser --------------------------------------------------------


#: Fields searched by :func:`search_domains`, mirroring the matching logic
#: of ``levi security search`` (name, summary, detection, hardening, concepts).
def search_domains(domains: Sequence[object], query: str) -> List[object]:
    """Filter security domains by ``query`` (case-insensitive substring).

    Matches against name, defensive_summary, detection_notes,
    hardening_notes and each key_concept — the same fields ``levi security
    search`` uses. An empty/blank query returns every domain.
    """
    q = query.strip().lower()
    if not q:
        return list(domains)
    hits = []
    for d in domains:
        texts = [
            str(getattr(d, "name", "") or ""),
            str(getattr(d, "defensive_summary", "") or ""),
            str(getattr(d, "detection_notes", "") or ""),
            str(getattr(d, "hardening_notes", "") or ""),
        ]
        concepts = getattr(d, "key_concepts", None) or []
        if q in "\n".join(texts).lower() or any(q in str(c).lower() for c in concepts):
            hits.append(d)
    return hits


def paginate(
    items: Sequence[object], page: int, per_page: int
) -> Tuple[List[object], int]:
    """Return ``(page_items, total_pages)`` for 1-based ``page``.

    ``page`` is clamped into range; ``per_page`` must be positive.
    An empty list yields ``([], 0)``.
    """
    if per_page < 1:
        raise ValueError(f"per_page must be positive, got {per_page!r}")
    total = len(items)
    total_pages = (total + per_page - 1) // per_page if total else 0
    if total_pages == 0:
        return [], 0
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    return list(items[start : start + per_page]), total_pages


#: Browser navigation actions.
_BROWSER_COMMANDS = {
    "n": "next",
    "next": "next",
    "p": "prev",
    "prev": "prev",
    "s": "search",
    "search": "search",
    "c": "clear",
    "clear": "clear",
    "b": "back",
    "back": "back",
    "q": "back",
    "quit": "back",
}


def browser_command(raw: str) -> Tuple[str, str]:
    """Parse one browser navigation line into ``(action, arg)``.

    Actions: ``next``, ``prev``, ``search``, ``clear``, ``back``, ``view``,
    ``invalid``. ``view`` carries the requested entry id/number as ``arg``;
    everything else carries ``""``. A bare ``1``-based row number on the
    current page is shorthand for ``view <n>``.
    """
    text = raw.strip().lower()
    if not text:
        return ("invalid", "")
    if text in _BROWSER_COMMANDS:
        return (_BROWSER_COMMANDS[text], "")
    parts = text.split(None, 1)
    if parts[0] in {"v", "view", "show"} and len(parts) == 2 and parts[1]:
        return ("view", parts[1].strip())
    if text.isdigit():
        return ("view", text)
    return ("invalid", "")


def resolve_view_arg(
    domains: Sequence[object], page_items: Sequence[object], arg: str
) -> object | None:
    """Resolve a ``view`` argument to a domain, or None.

    Accepts a 1-based row number on the current page (``"3"``) or a full
    domain id (``"android-security"``).
    """
    text = arg.strip().lower()
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(page_items):
            return page_items[idx]
        return None
    for d in domains:
        if str(getattr(d, "id", "") or "").lower() == text:
            return d
    return None
