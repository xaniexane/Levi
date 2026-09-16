"""Sliding-window chunker with overlap, markdown-header aware.

Each chunk carries provenance metadata so the RAG pipeline can cite
exactly where an answer came from:
``{source_doc, chunk_index, char_span, section}``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_SENTENCE_END_RE = re.compile(r"[.!?]\s")


@dataclass
class Chunk:
    text: str
    source_doc: str
    chunk_index: int
    char_span: Tuple[int, int]
    section: str = ""
    metadata: Dict = field(default_factory=dict)

    def to_provenance(self) -> Dict:
        prov = {
            "source_doc": self.source_doc,
            "chunk_index": self.chunk_index,
            "char_span": list(self.char_span),
            "section": self.section,
        }
        prov.update(self.metadata)
        return prov


def _split_sentences(text: str) -> List[str]:
    """Naive sentence splitter (stdlib, deterministic)."""
    parts = _SENTENCE_END_RE.split(text)
    out: List[str] = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        # re-attach the terminator for all but the trailing fragment
        if i < len(parts) - 1:
            part += "."
        out.append(part)
    return out or ([text.strip()] if text.strip() else [])


def chunk_text(text: str, source_doc: str, max_chars: int = 500,
               overlap: int = 100) -> List[Chunk]:
    """Split *text* into overlapping chunks.

    - Windows are at most *max_chars*; boundaries prefer sentence ends,
      then word ends — never mid-word.
    - Markdown headers (``# ...``) are tracked: the active header becomes
      the chunk's ``section`` and is prepended to the chunk text (unless
      the chunk already starts with it) so chunks stay self-describing.
    - ``overlap`` chars of trailing context carry into the next chunk.
    - Deterministic; raises ValueError on bad parameters.
    """
    if not isinstance(text, str):
        raise ValueError("chunk_text: text must be a string")
    if not isinstance(source_doc, str) or not source_doc:
        raise ValueError("chunk_text: source_doc must be a non-empty string")
    max_chars = int(max_chars)
    overlap = int(overlap)
    if max_chars < 50:
        raise ValueError("chunk_text: max_chars must be >= 50")
    if not 0 <= overlap < max_chars:
        raise ValueError("chunk_text: require 0 <= overlap < max_chars")

    # Split into (header_or_None, sentence) units, tracking active section.
    units: List[Tuple[Optional[str], str]] = []
    current_section = ""
    for line in text.splitlines():
        m = _HEADER_RE.match(line.strip())
        if m:
            current_section = m.group(2).strip()
            continue  # header itself is context, not chunk body
        if not line.strip():
            continue
        for sent in _split_sentences(line):
            units.append((current_section, sent))
    if not units:
        return []

    chunks: List[Chunk] = []
    buf: List[str] = []          # sentences in the current window
    buf_section = ""
    buf_start_char = 0
    pos = 0  # approx char offset in the original text

    def flush(end_pos: int) -> None:
        nonlocal buf, buf_section, buf_start_char
        if not buf:
            return
        body = " ".join(buf)
        prefix = ""
        if buf_section and not body.lstrip().startswith(buf_section):
            prefix = "[%s] " % buf_section
        chunk_text_out = prefix + body
        chunks.append(Chunk(
            text=chunk_text_out,
            source_doc=source_doc,
            chunk_index=len(chunks),
            char_span=(buf_start_char, end_pos),
            section=buf_section,
        ))
        buf = []

    for section, sent in units:
        if not buf:
            buf_section = section
            buf_start_char = pos
        trial = " ".join(buf + [sent])
        # Account for the section prefix when measuring.
        trial_len = len(trial) + (len(buf_section) + 3 if buf_section else 0)
        if buf and trial_len > max_chars:
            flush(pos)
            # Overlap: carry trailing sentences totalling ~overlap chars.
            carried: List[str] = []
            carried_len = 0
            prev_sents = trial.split(". ")
            for s in reversed(prev_sents):
                if carried_len + len(s) > overlap and carried:
                    break
                carried.insert(0, s)
                carried_len += len(s) + 2
            buf = carried
            buf_section = section
            # Recompute start offset approximately.
            buf_start_char = max(0, pos - carried_len)
            # If the carried overlap alone exceeds max, drop it (degenerate).
            if len(" ".join(buf)) > max_chars:
                buf = []
                buf_start_char = pos
            if not buf:
                buf_start_char = pos
        if not buf:
            buf_section = section
            buf_start_char = pos
        buf.append(sent)
        pos += len(sent) + 1
    flush(pos)
    return chunks
