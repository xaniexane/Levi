"""Tironian notes: personal shorthand abbreviation expander.

History: Rome's shorthand, conventionally attributed to Cicero's secretary
Marcus Tullius Tiro (attribution is tradition, not documented fact) — a
*productive* compression system of word/root signs with compounding rules for
improvising new signs on the fly. Expanded in Carolingian monasteries; died
with the scribal-school tradition that carried it.

In LEVI: a personal shorthand layer over your vocabulary. :class:`Shorthand`
maps compressed tokens to expansions, expands them word-boundary-safe in
text, supports compounding rules (prefix/suffix affixes you define), and can
propose new abbreviations from your actual phrases. Deny-closed: ambiguous
or colliding tokens are rejected; expansion is deterministic (longest token
first); cycles are impossible because expansion is single-pass over the
original text.

Honesty: USEFUL PATTERN — the productive-compounding idea transfers; the
4,000-sign training burden does not (yours is learned from your own typing).
"""

from __future__ import annotations

import re


class Shorthand:
    """Token -> expansion map with compounding rules and safe expansion."""

    def __init__(self):
        self.tokens: dict[str, str] = {}
        self.compounds: dict[
            str, str
        ] = {}  # affix marker -> template, e.g. "-q" -> "{x} with quarterly review"

    # ---- lexicon ---------------------------------------------------------
    def define(self, token: str, expansion: str) -> None:
        """Define a token. Deny-closed: collisions and unsafe tokens rejected."""
        token = token.strip()
        expansion = expansion.strip()
        if not token or not expansion:
            raise ValueError("token and expansion must be non-empty")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", token):
            raise ValueError(
                f"token {token!r} must be alphanumeric (may contain ._- inside)"
            )
        if token in self.tokens and self.tokens[token] != expansion:
            raise ValueError(
                f"token {token!r} already defined as {self.tokens[token]!r}"
            )
        # no token may be a prefix-with-boundary of an existing one in a way
        # that creates ambiguity: reject if one token is a strict prefix of another
        for existing in self.tokens:
            if existing != token and (
                existing.startswith(token) or token.startswith(existing)
            ):
                raise ValueError(
                    f"token {token!r} collides with existing {existing!r} (prefix ambiguity)"
                )
        self.tokens[token] = expansion

    def undefine(self, token: str) -> None:
        if token not in self.tokens:
            raise KeyError(f"no token {token!r}")
        del self.tokens[token]

    def define_compound(self, marker: str, template: str) -> None:
        """A compounding rule: ``marker`` + base token expands via template.

        E.g. marker ``"-q"`` with template ``"{x} with quarterly review"`` lets
        ``mtg-q`` expand using the base token ``mtg``.
        """
        if not marker or not template or "{x}" not in template:
            raise ValueError("marker must be non-empty and template must contain {x}")
        self.compounds[marker] = template

    # ---- expansion -------------------------------------------------------
    def expand_token(self, text: str) -> str:
        """Expand one token (with compound rules), or return it unchanged."""
        if text in self.tokens:
            return self.tokens[text]
        for marker, template in self.compounds.items():
            if text.endswith(marker):
                base = text[: -len(marker)]
                if base in self.tokens:
                    return template.format(x=self.tokens[base])
        return text

    def expand(self, text: str) -> str:
        """Expand all shorthand tokens in ``text``. Single pass over the
        original text — each chunk is expanded at most once, so cycles can't
        happen. Compound markers (``mtg-q``) and plain tokens are both
        handled; anything unrecognized passes through unchanged."""
        if not self.tokens and not self.compounds:
            return text
        return re.sub(r"[A-Za-z0-9._-]+", lambda m: self.expand_token(m.group(0)), text)

    # ---- learning --------------------------------------------------------
    @staticmethod
    def suggest(phrase: str, existing: set[str] | None = None) -> str:
        """Propose a Tironian-style abbreviation: first letters of each word,
        lowercased; falls back to consonant skeleton on collision."""
        words = [w for w in re.findall(r"[A-Za-z0-9]+", phrase.lower()) if w]
        if not words:
            raise ValueError("phrase has no usable words")
        existing = existing or set()
        candidate = "".join(w[0] for w in words)
        if candidate not in existing and len(candidate) >= 2:
            return candidate
        # compounding fallback: consonant skeleton of the phrase
        skeleton = re.sub(r"[aeiou]", "", "".join(words))[:6]
        n = 1
        base = skeleton or candidate
        while f"{base}{n}" in existing:
            n += 1
        return f"{base}{n}"

    def to_dict(self) -> dict:
        return {"tokens": self.tokens, "compounds": self.compounds}

    @classmethod
    def from_dict(cls, data: dict) -> "Shorthand":
        sh = cls()
        for marker, template in data.get("compounds", {}).items():
            sh.define_compound(marker, template)
        for token, expansion in data.get("tokens", {}).items():
            sh.define(token, expansion)
        return sh
