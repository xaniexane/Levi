"""LEVI's stationery drawer: canned replies as a first-class feature.

Studied from: desktop-casualties-20260916 / report.md [3. Eudora]
(Canned replies.)

The studied shape treated a good reply like a good letterhead: kept,
named, and ready to write on. This module rebuilds that as LEVI's own
stationery drawer. Each piece of stationery is a named template with a
subject line and body; ``{placeholders}`` are filled in at send time,
so the same reply stays personal without being retyped.

What this is NOT: mail merge with logic, conditionals, or loops. The
drawer does string substitution and nothing cleverer — deliberately.
If a template needs a value it wasn't given, rendering refuses loudly
instead of sending a half-filled letter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Set


ORIGIN = "levi-revival/stationery"


_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


@dataclass
class Stationery:
    """One named piece of stationery: a subject and a body template.

    ``placeholders`` is derived automatically from both templates —
    the set of ``{names}`` a render must be given.
    """

    name: str
    subject: str
    body: str
    placeholders: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        found = set(_PLACEHOLDER.findall(self.subject))
        found |= set(_PLACEHOLDER.findall(self.body))
        self.placeholders = found

    def render(self, values: Dict[str, str]) -> Dict[str, str]:
        """Fill the templates. Raises on missing or unknown values.

        Unknown values are rejected rather than silently ignored — a
        typo in a value name is more likely than an intentional extra.
        """
        missing = self.placeholders - set(values)
        if missing:
            raise KeyError(f"missing values for {sorted(missing)}")
        extra = set(values) - self.placeholders
        if extra:
            raise KeyError(f"unknown values for {sorted(extra)}")

        def fill(template: str) -> str:
            def sub(match: re.Match) -> str:
                return values[match.group(1)]

            return _PLACEHOLDER.sub(sub, template)

        return {"subject": fill(self.subject), "body": fill(self.body)}


class StationeryDrawer:
    """The drawer itself: named stationery, added, listed, rendered."""

    def __init__(self) -> None:
        self._pieces: Dict[str, Stationery] = {}

    def add(self, name: str, subject: str, body: str) -> Stationery:
        """File a new piece of stationery. Names are unique."""
        if name in self._pieces:
            raise ValueError(f"stationery already exists: {name!r}")
        piece = Stationery(name=name, subject=subject, body=body)
        self._pieces[name] = piece
        return piece

    def remove(self, name: str) -> None:
        """Throw a piece away."""
        if name not in self._pieces:
            raise KeyError(f"no such stationery: {name!r}")
        del self._pieces[name]

    def rename(self, old: str, new: str) -> Stationery:
        """Rename a piece. The new name must be free."""
        if old not in self._pieces:
            raise KeyError(f"no such stationery: {old!r}")
        if new in self._pieces:
            raise ValueError(f"stationery already exists: {new!r}")
        piece = self._pieces.pop(old)
        piece.name = new
        self._pieces[new] = piece
        return piece

    def names(self) -> List[str]:
        """Every piece in the drawer, alphabetical."""
        return sorted(self._pieces)

    def get(self, name: str) -> Stationery:
        return self._pieces[name]

    def render(self, name: str, values: Dict[str, str]) -> Dict[str, str]:
        """Render a piece straight from the drawer."""
        return self._pieces[name].render(values)

    def compose_with(
        self,
        mail_client,
        account: str,
        stationery: str,
        to: List[str],
        values: Dict[str, str],
        cc: List[str] | None = None,
    ):
        """Draft a message on a LEVI mail client from a stationery piece.

        Takes anything with a ``compose(account, to, subject, body, cc)``
        method — the built-in mail client qualifies. Returns the draft.
        """
        rendered = self.render(stationery, values)
        return mail_client.compose(
            account, to, rendered["subject"], rendered["body"], cc=cc
        )
