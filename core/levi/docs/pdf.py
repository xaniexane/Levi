"""LEVI-native best-effort PDF text extraction — stdlib only (``re`` + ``zlib``).

HONEST CONTRACT — read this before relying on the output
--------------------------------------------------------
This module is **text extraction only, best effort**. It:

* parses content-stream objects out of the PDF structure and decodes
  ``/FlateDecode`` streams with :mod:`zlib`;
* reads text-showing operators (``Tj`` and ``TJ``) and unescapes
  literal ``(...)`` and hex ``<...>`` strings;
* **REFUSES encrypted PDFs** (``/Encrypt`` in the trailer) with a clear
  error instead of producing garbage;
* does **not** reconstruct reading order or layout (columns, tables,
  rotated text come out as a flat fragment stream);
* does **not** OCR scanned images — a PDF made of page images yields no
  text here, and that is reported honestly, not guessed;
* does **not** handle every filter (``/LZWDecode``, ``/ASCII85Decode``
  without Flate, custom encodings) — unrecognized content is skipped,
  never fabricated;
* does **not** map glyph encodings: text encoded with custom
  ``/Encoding`` or embedded subset fonts may come out as wrong
  characters. The output is "what the bytes say", not "what the page
  shows".

Never present the result as a faithful rendering of the document. It is
an extraction aid for search/indexing, nothing more.

Everything here is written from the PDF structure itself; no other
product's code or branding is involved.
"""

from __future__ import annotations

import re
import zlib
from pathlib import Path
from typing import List, Optional, Tuple, Union

PathLike = Union[str, Path]

_OBJ_RE = re.compile(rb"(\d+)\s+(\d+)\s+obj(.*?)endobj", re.DOTALL)
_STREAM_RE = re.compile(rb"<<(.*?)>>\s*stream\r?\n(.*?)endstream", re.DOTALL)
_ENCRYPT_RE = re.compile(rb"/Encrypt\b")
_TOKEN_RE = re.compile(
    rb"\((?:\\.|[^()\\])*\)"  # literal string (...)
    rb"|<[0-9A-Fa-f\s]+>"  # hex string <...>
    rb"|\["  # TJ array open
    rb"|\]"  # TJ array close
    rb"|\bTj\b"  # text-showing operator
    rb"|\bTJ\b"  # text-showing operator (array form)
)
_OCTAL_RE = re.compile(rb"\\([0-7]{1,3})")

_ESCAPES = {
    ord("n"): "\n",
    ord("r"): "\r",
    ord("t"): "\t",
    ord("b"): "\b",
    ord("f"): "\f",
    ord("("): "(",
    ord(")"): ")",
    ord("\\"): "\\",
}


def _decode_literal(raw: bytes) -> str:
    """Decode a PDF literal string body (without the outer parens)."""
    out: List[str] = []
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == 0x5C and i + 1 < n:  # backslash
            nxt = raw[i + 1]
            if nxt in _ESCAPES:
                out.append(_ESCAPES[nxt])
                i += 2
                continue
            if ord("0") <= nxt <= ord("7"):
                m = _OCTAL_RE.match(raw, i)
                if m:
                    out.append(chr(int(m.group(1), 8)))
                    i = m.end()
                    continue
            if nxt in (0x0D, 0x0A):  # line continuation
                i += 2
                if nxt == 0x0D and i < n and raw[i] == 0x0A:
                    i += 1
                continue
            out.append(chr(nxt))
            i += 2
        else:
            out.append(chr(ch))
            i += 1
    return "".join(out)


def _decode_hex(raw: bytes) -> str:
    """Decode a PDF hex string body (without the angle brackets)."""
    cleaned = re.sub(rb"\s+", b"", raw)
    if len(cleaned) % 2:
        cleaned += b"0"
    try:
        return bytes.fromhex(cleaned.decode("ascii")).decode("latin-1")
    except (ValueError, UnicodeDecodeError):
        return ""


def _decode_token(token: bytes) -> Optional[str]:
    if token.startswith(b"("):
        return _decode_literal(token[1:-1])
    if token.startswith(b"<"):
        return _decode_hex(token[1:-1])
    return None


def _extract_from_content(data: bytes) -> List[str]:
    """Extract text fragments from one decoded content stream."""
    fragments: List[str] = []
    pending: List[str] = []  # strings seen since the last '['
    for match in _TOKEN_RE.finditer(data):
        token = match.group(0)
        if token == b"[":
            pending = []
        elif token == b"]":
            pass  # TJ flush handles the buffer; stray ']' is ignored
        elif token == b"Tj":
            if pending:
                fragments.append(pending[-1])
                pending = []
        elif token == b"TJ":
            fragments.append("".join(pending))
            pending = []
        else:
            text = _decode_token(token)
            if text is not None:
                pending.append(text)
    return fragments


def _stream_filters(dictionary: bytes) -> List[bytes]:
    filters: List[bytes] = []
    m = re.search(rb"/Filter\s*(\[[^\]]*\]|/[A-Za-z0-9]+)", dictionary)
    if not m:
        return filters
    spec = m.group(1).strip()
    if spec.startswith(b"["):
        filters.extend(re.findall(rb"/([A-Za-z0-9]+)", spec))
    else:
        filters.append(spec[1:])
    return filters


def _decode_stream(dictionary: bytes, data: bytes) -> Optional[bytes]:
    """Decode one stream's bytes; None when filters are unsupported."""
    filters = _stream_filters(dictionary)
    for name in filters:
        if name == b"FlateDecode":
            data = data.rstrip(b"\r\n")
            try:
                data = zlib.decompress(data)
            except zlib.error:
                return None
        elif name in (b"ASCII85Decode",):
            # Rare without Flate in practice; unsupported on purpose.
            return None
        else:
            return None
    return data


def _find_trailer(data: bytes) -> bytes:
    idx = data.rfind(b"trailer")
    if idx == -1:
        return b""
    return data[idx:]


def extract_fragments(path: PathLike) -> List[str]:
    """Extract raw text fragments from a PDF's content streams.

    Fragments are in content-stream order with no layout; join them for
    a flat text view (see :func:`extract_text`).

    Raises
    ------
    ValueError
        If the file is not a PDF, is encrypted (refused), or cannot be
        parsed.
    """
    src = Path(path)
    try:
        data = src.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read {src}: {exc}") from exc
    if not data.startswith(b"%PDF-"):
        raise ValueError(f"{src} is not a PDF file (missing %PDF- header)")
    if _ENCRYPT_RE.search(_find_trailer(data)):
        raise ValueError(
            f"{src} is an encrypted PDF — text extraction refused "
            "(decryption is out of scope for this best-effort extractor)"
        )
    fragments: List[str] = []
    for obj in _OBJ_RE.finditer(data):
        body = obj.group(3)
        for sm in _STREAM_RE.finditer(body):
            dictionary, stream_data = sm.group(1), sm.group(2)
            decoded = _decode_stream(dictionary, stream_data)
            if decoded is None:
                continue
            fragments.extend(_extract_from_content(decoded))
    return fragments


def extract_text(path: PathLike) -> str:
    """Best-effort flat text of a PDF: fragments joined with newlines.

    Empty string when no extractable text is found (e.g. scanned-image
    PDFs) — reported as empty, never invented.
    """
    return "\n".join(f for f in extract_fragments(path) if f)


def extract_info(path: PathLike) -> Tuple[int, int]:
    """Return ``(fragment_count, char_count)`` for a quick honest summary."""
    fragments = extract_fragments(path)
    return len(fragments), sum(len(f) for f in fragments)
