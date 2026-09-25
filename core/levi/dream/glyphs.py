"""Glyph compression for the dream imagery corpus.

Chauncey's build order (2026-09-22): the whole imagery corpus is
glyph-compressed and indexed for offline retrieval. This module is the
deterministic glyph tokenizer: frequent tokens (curated common words +
dream/imagination-domain words) map to short ASCII glyph codes, with a
versioned codebook file living beside the corpus.

Design notes (originals-first):

- ``core/levi/memory/hierarchy.py`` names the path
  COMPRESSED -> GLYPH -> WORLD MODEL and marks glyph representation as
  *future*. This module builds that future layer for the dream imagery
  corpus — it does not invent a conflicting scheme.
- The codebook is FIXED and deterministic (canonical vocabulary, codes
  assigned in vocab order). No clocks, no dict-order dependence, no
  retraining: the codebook is the only decode key, and every stored
  record names its codebook version.

Encoding scheme (all ASCII, spreadsheet-safe):

- Each codebook token maps to a 2-character code; in text it appears as
  ``~<code>~``. The escape character is ``~`` itself: every literal
  ``~`` in the source is doubled to ``~~`` BEFORE token substitution,
  so decode is unambiguous and byte-identical.
- Only lowercase ``[a-z0-9]+`` runs are substituted; anything else
  (capitalized words, punctuation, unicode, unknown words) passes
  through untouched. Unknown words are never an error.

INVARIANTS (declared, guarded in code, proven in tests):

1. "decode(encode(x)) == x for every x" — round-trip is byte-identical,
   including tildes, code-like patterns, and unicode.
2. "The codebook is deterministic" — same construction always yields
   the same codes; the codebook carries a fixed version.
3. "Unknown words pass through untouched" — encoding never fails and
   never invents a mapping for a word outside the codebook.

PROOF (honest): property tests over the invariants in
``tests/test_dream_imagine.py`` — randomized round-trips including
adversarial tilde/code patterns — not a formal proof.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CODEBOOK_VERSION = "1"

#: Marker/escape character. Doubled (``~~``) for literals.
ESC = "~"

_CODE_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _code_for(index: int) -> str:
    """Deterministic 2-char code for vocab position ``index``."""
    base = len(_CODE_ALPHABET)
    return _CODE_ALPHABET[index // base] + _CODE_ALPHABET[index % base]


#: Canonical frequent vocabulary: common English function/content words
#: plus dream/imagination-domain words. Order is the code assignment
#: order — NEVER reorder; append only (with a version bump).
BASE_VOCAB: Tuple[str, ...] = (
    # function words
    "the", "a", "an", "of", "and", "to", "in", "is", "it", "that",
    "with", "for", "as", "on", "at", "by", "from", "this", "be",
    "are", "was", "were", "has", "have", "had", "not", "but", "or",
    "its", "their", "they", "them", "he", "she", "we", "you", "my",
    "your", "our", "his", "her", "all", "one", "like", "into", "out",
    "over", "under", "between", "through", "during", "each", "more",
    "most", "some", "such", "than", "then", "when", "where", "which",
    "while", "who", "will", "would", "there", "here", "what", "how",
    # visual / imagination domain
    "vivid", "vividly", "imagine", "imagined", "imagination", "image",
    "picture", "render", "rendered", "rendering", "color", "colors",
    "colours", "colour", "light", "lights", "lighting", "shadow",
    "shadows", "dark", "bright", "brightness", "glow", "glowing",
    "texture", "textured", "form", "shape", "shapes", "line", "lines",
    "curve", "curves", "edge", "edges", "surface", "surfaces", "scale",
    "large", "small", "tiny", "huge", "vast", "motion", "moving",
    "still", "flow", "flowing", "wave", "waves", "sky", "night",
    "day", "sun", "moon", "star", "stars", "water", "fire", "earth",
    "air", "dream", "dreams", "dreaming", "vision", "detail",
    "details", "detailed", "scene", "background", "foreground",
    "center", "edge", "soft", "sharp", "warm", "cool", "red", "blue",
    "green", "yellow", "orange", "purple", "gold", "silver", "black",
    "white", "gray", "grey", "pink", "brown", "circle", "square",
    "triangle", "spiral", "grid", "pattern", "symmetry", "depth",
    "horizon", "silhouette", "reflection", "mist", "smoke", "dust",
)


def make_codebook() -> Dict[str, object]:
    """Build the deterministic codebook dict.

    Returns ``{"version", "token_to_code", "code_to_token"}``. Same call,
    same result, always.
    """
    token_to_code: Dict[str, str] = {}
    for i, token in enumerate(BASE_VOCAB):
        if token in token_to_code:
            continue  # vocab lists a word twice — first position wins
        token_to_code[token] = _code_for(i)
    code_to_token = {c: t for t, c in token_to_code.items()}
    assert len(code_to_token) == len(token_to_code), "code collision"
    return {
        "version": CODEBOOK_VERSION,
        "token_to_code": token_to_code,
        "code_to_token": code_to_token,
    }


def encode(text: str, codebook: Optional[Dict[str, object]] = None) -> str:
    """Glyph-encode ``text``. Deterministic; unknown words pass through."""
    if not isinstance(text, str):
        raise TypeError("encode: text must be str, got %s" % type(text).__name__)
    cb = codebook or make_codebook()
    mapping = cb["token_to_code"]
    # 1. escape the marker
    escaped = text.replace(ESC, ESC + ESC)

    # 2. substitute known tokens (single pass — inserted markers are
    #    produced by the replacement function, never rescanned)
    def _sub(m: "re.Match[str]") -> str:
        token = m.group(0)
        code = mapping.get(token)
        if code is None:
            return token
        return ESC + code + ESC

    return _TOKEN_RE.sub(_sub, escaped)


_MARKER_RE = re.compile(r"~~|~[a-z0-9]{2}~|~")


def decode(text: str, codebook: Optional[Dict[str, object]] = None) -> str:
    """Inverse of :func:`encode`. Byte-identical round-trip guaranteed."""
    if not isinstance(text, str):
        raise TypeError("decode: text must be str, got %s" % type(text).__name__)
    cb = codebook or make_codebook()
    reverse = cb["code_to_token"]

    def _sub(m: "re.Match[str]") -> str:
        hit = m.group(0)
        if hit == ESC + ESC:
            return ESC
        if hit.startswith(ESC) and hit.endswith(ESC) and len(hit) == 4:
            token = reverse.get(hit[1:3])
            if token is not None:
                return token
        return hit  # lone marker — literal, tolerated

    return _MARKER_RE.sub(_sub, text)


def codebook_path(corpus_dir: "str | Path") -> Path:
    """Versioned codebook file living beside the corpus."""
    return Path(corpus_dir) / "codebook.json"


def write_codebook(corpus_dir: "str | Path") -> Path:
    """Persist the versioned codebook beside the corpus.

    Shape: ``{"current": <version>, "versions": {<version>: {...}}}`` —
    old versions are kept so old records always decode.
    """
    path = codebook_path(corpus_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    cb = make_codebook()
    payload: Dict[str, object] = {"current": cb["version"], "versions": {}}
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                payload = {"current": cb["version"], "versions": {}}
        except (OSError, json.JSONDecodeError):
            payload = {"current": cb["version"], "versions": {}}
    versions = payload.setdefault("versions", {})
    assert isinstance(versions, dict)
    versions[str(cb["version"])] = {
        "token_to_code": cb["token_to_code"],
        "code_to_token": cb["code_to_token"],
    }
    payload["current"] = cb["version"]
    path.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    return path


def load_codebook(corpus_dir: "str | Path", version: Optional[str] = None) -> Dict[str, object]:
    """Load a codebook version from beside the corpus (default: current)."""
    path = codebook_path(corpus_dir)
    payload = json.loads(path.read_text(encoding="utf-8"))
    versions = payload.get("versions", {})
    ver = version or payload.get("current") or CODEBOOK_VERSION
    entry = versions.get(str(ver))
    if not isinstance(entry, dict):
        raise KeyError("codebook version %r not found in %s" % (ver, path))
    return {
        "version": str(ver),
        "token_to_code": dict(entry.get("token_to_code", {})),
        "code_to_token": dict(entry.get("code_to_token", {})),
    }


def compression_stats(text: str, codebook: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    """Honest numbers: glyph-encoded size vs source size."""
    encoded = encode(text, codebook)
    return {
        "raw_chars": len(text),
        "glyph_chars": len(encoded),
        "ratio": round(len(encoded) / len(text), 4) if text else 1.0,
    }


__all__: List[str] = [
    "CODEBOOK_VERSION",
    "BASE_VOCAB",
    "make_codebook",
    "encode",
    "decode",
    "codebook_path",
    "write_codebook",
    "load_codebook",
    "compression_stats",
]
