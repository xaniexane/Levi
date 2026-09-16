"""Chappe semaphore codebook: two-dimensional phrase-space addressing.

History: Claude Chappe's optical telegraph (first line Paris–Lille, 1794)
— 98 arm positions, 6 reserved for control, leaving 92 signal values. The
*codebook* held 92 pages × 92 entries = 8,464 words and phrases; each
message unit was *two signals* — page, then position ("ignorance" =
50, 87). Two telescopes per tower, an explicit setup–transmit–acknowledge
cycle, and error signals; the Condé-sur-l'Escaut victory dispatch crossed
120 miles in under an hour (August 1794). The electric telegraph — faster,
night-capable, cheaper per mile — killed it. France uniquely forced the
electric telegraph to mimic the optical code for backward compatibility,
which slowed its own transition.

In LEVI: the codebook's lesson — pre-negotiated *phrase-spaces* beat free
text for routine coordination. The assistant keeps a personal phrasebook
of your recurring communications with the two-signal idea (category +
item: "travel/hotel-preference", "meeting/decline-polite"), so routine
messages compose from two taps and full text is generated at the
endpoint; free composition is reserved for the genuinely novel 5%.
Phrasebooks persist as JSON under ``~/.levi/methods/``.

Honesty: USEFUL PATTERN. The 92×92 geometry and the (50, 87) "ignorance"
sample are historical; the control-signal labels below are a reasonable
reconstruction (exact historical assignments vary by source) and are
marked as such; the phrase entries themselves are yours to fill.
"""

from __future__ import annotations

from . import _persist

PAGES = 92
ENTRIES_PER_PAGE = 92

# The 6 reserved control positions (98 - 92). Labels are a reconstruction —
# the historical sources disagree on exact assignments, so these are
# operational placeholders, not claimed history.
CONTROL_SIGNALS: dict[int, str] = {
    93: "error — void the last signal",
    94: "rest — pause transmission",
    95: "urgent — priority dispatch",
    96: "end of dispatch",
    97: "awaiting reply",
    98: "synchronize — reset the line",
}


class ChappeError(Exception):
    """Base class for codebook failures."""


class UnknownSignal(ChappeError):
    """No phrase is registered at (page, position)."""


class UnknownPhrase(ChappeError):
    """The phrase is not in the codebook (compose it freely instead)."""


class AmbiguousPhrase(ChappeError):
    """The phrase is registered at multiple addresses."""

    def __init__(self, message: str, addresses: list[tuple[int, int]]):
        super().__init__(message)
        self.addresses = addresses


def _check_address(page: int, pos: int) -> None:
    if not (1 <= page <= PAGES):
        raise ValueError(f"page must be 1..{PAGES}")
    if not (1 <= pos <= ENTRIES_PER_PAGE):
        raise ValueError(f"position must be 1..{ENTRIES_PER_PAGE}")


class Codebook:
    """A Chappe-style phrasebook: (page, position) <-> phrase."""

    def __init__(self, name: str, store: str | None = None):
        if not name or not name.strip():
            raise ValueError("codebook name must be non-empty")
        self.name = name.strip()
        self._entries: dict[tuple[int, int], str] = {}
        self._store = _persist.store_path(store or f"chappe-{_slug(self.name)}")
        self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> None:
        data = _persist.load_json(self._store)
        if not data:
            # Seed the one historically attested sample from the report.
            self._entries[(50, 87)] = "ignorance"
            return
        if data.get("name") != self.name:
            raise _persist.CorruptStoreError(
                f"chappe store {self._store} does not match {self.name!r}"
            )
        for key, phrase in data.get("entries", {}).items():
            page, pos = (int(x) for x in key.split(","))
            self._entries[(page, pos)] = phrase

    def save(self) -> None:
        _persist.save_json(
            self._store,
            {"name": self.name,
             "entries": {f"{p},{q}": ph for (p, q), ph in self._entries.items()}},
        )

    # -- the codebook -------------------------------------------------------
    def set_entry(self, page: int, pos: int, phrase: str) -> None:
        """Register ``phrase`` at (page, position). Overwrites that address
        only — deny-closed against accidental collision: use
        :meth:`encode` first if you need uniqueness."""
        _check_address(page, pos)
        if not phrase or not phrase.strip():
            raise ValueError("phrase must be non-empty")
        self._entries[(page, pos)] = phrase.strip()

    def decode(self, page: int, pos: int) -> str:
        """Second signal resolves the phrase. Empty addresses raise."""
        _check_address(page, pos)
        try:
            return self._entries[(page, pos)]
        except KeyError:
            raise UnknownSignal(
                f"no phrase registered at ({page}, {pos})"
            ) from None

    def encode(self, phrase: str) -> tuple[int, int]:
        """Find the (page, position) of ``phrase``.

        A phrase registered at several addresses raises
        :class:`AmbiguousPhrase` — the sender must pick explicitly.
        """
        matches = [addr for addr, ph in self._entries.items() if ph == phrase]
        if not matches:
            raise UnknownPhrase(f"phrase {phrase!r} is not in the codebook")
        if len(matches) > 1:
            raise AmbiguousPhrase(
                f"phrase {phrase!r} has {len(matches)} addresses; pick one",
                sorted(matches),
            )
        return matches[0]

    # -- messages: sequences of two-signal units --------------------------------
    def encode_message(self, phrases: list[str]) -> list[tuple[int, int]]:
        """Compose a message: each phrase becomes its two-signal unit."""
        return [self.encode(p) for p in phrases]

    def decode_message(self, signals: list[tuple[int, int]]) -> list[str]:
        """Resolve a received signal sequence back to phrases."""
        return [self.decode(page, pos) for page, pos in signals]

    def control(self, signal: int) -> str:
        """Resolve a control signal (93–98)."""
        try:
            return CONTROL_SIGNALS[signal]
        except KeyError:
            raise UnknownSignal(
                f"{signal} is not a control signal (93–98)"
            ) from None

    def __len__(self) -> int:
        return len(self._entries)


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower())[:40].strip("-")


__all__ = [
    "PAGES",
    "ENTRIES_PER_PAGE",
    "CONTROL_SIGNALS",
    "ChappeError",
    "UnknownSignal",
    "UnknownPhrase",
    "AmbiguousPhrase",
    "Codebook",
]
