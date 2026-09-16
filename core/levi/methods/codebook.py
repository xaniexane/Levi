"""Commercial telegraph codebooks: phrase<->code compression with edition control.

History: the 19th–early-20th-century compression layer for expensive
cables — five-letter or numeric tokens stood for whole domain-specific
phrases ("BYLLA" = "the cargo has been discharged…"), sometimes with
error-detection (tokens chosen to differ by multiple letters) and a
secrecy side-effect. The mechanism was *shared lossy compression with a
synchronized dictionary*: both parties pre-agree the token→phrase map, the
wire carries tokens, the endpoints expand. Its power and its failure mode
were both the synchronization — when the two parties' editions diverged,
ambiguity followed. Cheap direct communication (telex, then email) killed
it; the idea survives in airline PNR codes and stock tickers.

In LEVI: a personal (or team) codebook between you and your frequent
correspondents — recurring phrases compress to tokens in drafts, expanded
on send; shared codebooks for status updates with LEVI as the
synchronized edition-keeper. Editions are versioned and checksummed, and
:func:`check_sync` detects the historical failure mode (edition
divergence) before it bites. Collisions are rejected at add-time, never
merged silently. Codebooks persist as JSON under ``~/.levi/methods/``.

Honesty: USEFUL PATTERN — the compression is real; the "secrecy" was
always a side-effect, never a guarantee, and this module offers none.
"""

from __future__ import annotations

import hashlib
import json
import re

from . import _persist

_CODE_RE = re.compile(r"^[A-Z0-9]{2,12}$")


class CodebookError(Exception):
    """Base class for codebook failures."""


class CollisionError(CodebookError):
    """A code already maps to a different phrase (or vice versa where
    forbidden). The existing mapping is kept; nothing is overwritten."""


class UnknownCode(CodebookError):
    """Decoding hit a token with no mapping."""


class Codebook:
    """A versioned, checksummed phrase<->code dictionary."""

    def __init__(self, name: str, store: str | None = None):
        if not name or not name.strip():
            raise ValueError("codebook name must be non-empty")
        self.name = name.strip()
        self._codes: dict[str, str] = {}  # code -> phrase (unique)
        self._phrases: dict[str, set[str]] = {}  # phrase -> codes (aliases allowed)
        self.edition = 0
        self._store = _persist.store_path(store or f"codebook-{_slug(self.name)}")
        self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> None:
        data = _persist.load_json(self._store)
        if not data:
            return
        if data.get("name") != self.name:
            raise _persist.CorruptStoreError(
                f"codebook store {self._store} does not match {self.name!r}"
            )
        self.edition = int(data.get("edition", 0))
        for code, phrase in data.get("codes", {}).items():
            self._codes[code] = phrase
            self._phrases.setdefault(phrase, set()).add(code)

    def save(self) -> None:
        _persist.save_json(
            self._store,
            {"name": self.name, "edition": self.edition, "codes": self._codes},
        )

    # -- editing (deny-closed: collisions rejected) --------------------------
    def add(self, code: str, phrase: str) -> None:
        """Map ``code`` -> ``phrase``. A code already mapped to a *different*
        phrase raises :class:`CollisionError`; re-adding the identical
        mapping is a no-op."""
        if not isinstance(code, str) or not _CODE_RE.match(code):
            raise ValueError(
                f"code must match {_CODE_RE.pattern} (uppercase alnum, 2-12 chars)"
            )
        if not phrase or not phrase.strip():
            raise ValueError("phrase must be non-empty")
        phrase = phrase.strip()
        existing = self._codes.get(code)
        if existing is not None:
            if existing == phrase:
                return  # idempotent
            raise CollisionError(
                f"code {code!r} already maps to {existing!r}; "
                f"refusing to remap to {phrase!r}"
            )
        self._codes[code] = phrase
        self._phrases.setdefault(phrase, set()).add(code)
        self.edition += 1

    def remove(self, code: str) -> None:
        try:
            phrase = self._codes.pop(code)
        except KeyError:
            raise UnknownCode(f"no such code {code!r}") from None
        codes = self._phrases.get(phrase)
        if codes:
            codes.discard(code)
            if not codes:
                del self._phrases[phrase]
        self.edition += 1

    # -- the compression layer -----------------------------------------------
    def encode(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        """Replace known phrases with codes (longest phrase first).

        Returns ``(encoded_text, substitutions)`` where substitutions lists
        ``(phrase, code)`` pairs applied. Unknown text passes through
        untouched — the wire carries tokens only where agreed.
        """
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        out = text
        applied: list[tuple[str, str]] = []
        for phrase in sorted(self._phrases, key=len, reverse=True):
            code = sorted(self._phrases[phrase])[0]  # canonical: first alias
            if phrase in out:
                out = out.replace(phrase, code)
                applied.append((phrase, code))
        return out, applied

    def decode(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        """Expand known codes back to phrases (longest code first)."""
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        out = text
        applied: list[tuple[str, str]] = []
        for code in sorted(self._codes, key=len, reverse=True):
            # token-boundary aware: only replace standalone tokens
            pattern = re.compile(r"(?<![A-Z0-9])" + re.escape(code) + r"(?![A-Z0-9])")
            new_out, n = pattern.subn(self._codes[code], out)
            if n:
                out = new_out
                applied.append((code, self._codes[code]))
        return out, applied

    def lookup(self, code: str) -> str:
        """Expand one code; raises :class:`UnknownCode` if unmapped."""
        try:
            return self._codes[code]
        except KeyError:
            raise UnknownCode(f"no such code {code!r}") from None

    # -- edition control (the historical failure mode) -------------------------
    def digest(self) -> str:
        """Checksum of the canonical mapping — the edition fingerprint."""
        canonical = json.dumps(self._codes, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def check_sync(self, other: "Codebook") -> list[str]:
        """Compare editions with another codebook; list divergences.

        Empty list means the editions are synchronized. Any entry is the
        historical failure mode made visible: two parties about to talk
        past each other.
        """
        divergences = []
        for code in sorted(set(self._codes) | set(other._codes)):
            mine, theirs = self._codes.get(code), other._codes.get(code)
            if mine is None:
                divergences.append(f"code {code!r} missing here (theirs: {theirs!r})")
            elif theirs is None:
                divergences.append(f"code {code!r} missing there (ours: {mine!r})")
            elif mine != theirs:
                divergences.append(
                    f"code {code!r} diverges: ours {mine!r} vs theirs {theirs!r}"
                )
        return divergences

    def codes(self) -> dict[str, str]:
        return dict(self._codes)

    def __len__(self) -> int:
        return len(self._codes)


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower())[:40].strip("-")


__all__ = [
    "CodebookError",
    "CollisionError",
    "UnknownCode",
    "Codebook",
]
