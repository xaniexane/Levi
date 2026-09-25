"""LEVI bot brief — a plain-text briefing card with a hard line budget.

A briefing that doesn't fit the screen is a briefing that doesn't get
read. ``render_brief`` takes a title and ordered sections and renders a
deterministic plain-text card that never exceeds ``max_lines``: headings
are never dropped, body lines fill in section order, and anything that
doesn't fit is counted and disclosed in a held-back note rather than
silently truncated.

Deny-closed: malformed titles, sections, headings, or budgets are refused
with a named error, never coerced. Same inputs → same card, every time.

Usage::

    from levi.bot.brief import render_brief

    card = render_brief(
        "Morning brief",
        [("Pulse", ["3 services up", "growth tick at 06:00"]),
         ("Watch", ["disk at 71%", "journal over budget"])],
        max_lines=12,
    )
    print(card.text)   # card.dropped tells you what was held back
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple, Union

__all__ = ["BriefError", "BriefResult", "render_brief", "SHELF"]


class BriefError(ValueError):
    """Raised when brief inputs fail validation."""


#: A section is (heading, lines) or {"heading": ..., "lines": [...]}.
Section = Union[Tuple[str, Sequence[str]], Dict[str, object]]


@dataclass(frozen=True)
class BriefResult:
    """The rendered card plus honest accounting of what fit."""

    text: str
    lines: int  # rendered line count (always <= max_lines of the call)
    dropped: int  # body lines held back for lack of budget
    sections: int  # section headings rendered (always all of them)


SHELF = {
    "name": "bot-brief",
    "summary": (
        "Plain-text briefing cards with a hard line budget: headings never "
        "dropped, body lines fill in order, held-back lines counted and "
        "disclosed. Deterministic."
    ),
    "items": [
        {
            "id": "bot.brief.render",
            "kind": "function",
            "summary": "Render a titled, sectioned brief within max_lines.",
            "invoke": "from levi.bot.brief import render_brief",
        },
    ],
}


def _validate_title(title: object) -> str:
    if not isinstance(title, str) or not title.strip():
        raise BriefError("brief: 'title' must be a non-empty str")
    return title.strip()


def _validate_sections(sections: object) -> List[Tuple[str, List[str]]]:
    if not isinstance(sections, (list, tuple)) or not sections:
        raise BriefError("brief: 'sections' must be a non-empty list")
    cleaned: List[Tuple[str, List[str]]] = []
    for i, section in enumerate(sections):
        if isinstance(section, dict):
            heading, lines = section.get("heading"), section.get("lines")
        elif isinstance(section, (list, tuple)) and len(section) == 2:
            heading, lines = section
        else:
            raise BriefError(
                f"brief: sections[{i}] must be (heading, lines) or "
                "{'heading': ..., 'lines': [...]}"
            )
        if not isinstance(heading, str) or not heading.strip():
            raise BriefError(f"brief: sections[{i}] heading must be a non-empty str")
        if not isinstance(lines, (list, tuple)) or not all(
            isinstance(line, str) for line in lines
        ):
            raise BriefError(f"brief: sections[{i}] lines must be a list of str")
        cleaned.append((heading.strip(), [line.rstrip() for line in lines]))
    return cleaned


def _validate_budget(max_lines: object) -> int:
    if isinstance(max_lines, bool) or not isinstance(max_lines, int):
        raise BriefError("brief: 'max_lines' must be an int")
    if max_lines < 4:
        raise BriefError("brief: 'max_lines' must be >= 4 (title + one section)")
    return max_lines


def render_brief(
    title: str,
    sections: Sequence[Section],
    max_lines: int = 40,
) -> BriefResult:
    """Render a briefing card within a hard line budget.

    Returns :class:`BriefResult`. Headings are never dropped; body lines
    fill in section order until the budget runs out. Dropped lines are
    counted and disclosed in a trailing held-back note.
    """
    clean_title = _validate_title(title)
    clean_sections = _validate_sections(sections)
    budget = _validate_budget(max_lines)

    # Headings are never dropped: the minimum viable card is the title
    # plus every heading. If the budget cannot hold even that, the
    # budget — not the headings — is the malformed input.
    min_lines = 2 + 2 * len(clean_sections)
    if min_lines > budget:
        raise BriefError(
            f"brief: max_lines={budget} too small for {len(clean_sections)} "
            f"section(s) — needs >= {min_lines} (title + every heading)"
        )

    out: List[str] = [clean_title, "=" * len(clean_title)]
    for heading, _lines in clean_sections:
        out.extend([heading, "-" * len(heading)])

    total_body = sum(len(lines) for _h, lines in clean_sections)
    body_budget = budget - len(out)
    dropped = max(0, total_body - body_budget)
    # The held-back note takes one body slot, never a heading's.
    fill = body_budget - (1 if dropped else 0)

    for _heading, lines in clean_sections:
        for line in lines:
            if fill <= 0:
                break
            out.append(f"  {line}" if line else "")
            fill -= 1
        if fill <= 0:
            break

    if dropped:
        out.append(f"[{dropped} line(s) held back — ask for the next page]")

    text = "\n".join(out)
    return BriefResult(
        text=text,
        lines=len(out),
        dropped=dropped,
        sections=len(clean_sections),
    )
