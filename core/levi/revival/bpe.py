"""Byte-pair encoding tokenizer, trained from scratch.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.8)

Functional description: learns a BPE vocabulary by repeatedly finding the
most frequent adjacent pair of symbols in the training corpus and merging
it into a new symbol, recording the merge rules in order. Encoding applies
the ordered rules greedily to byte-level input; decoding concatenates the
byte pieces. Byte fallback means every possible input is encodable — the
base vocabulary is the 256 byte values, so no character is ever unknown.
Token healing: when a generation would start mid-token, ``heal_prefix``
backs up to the last token boundary that the trained merges respect, so
decoding stays aligned.

Pure Python, stdlib only. No provider branding, no LLaMA. Not artificial
— synthetic.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

ORIGIN = "levi-revival/bpe"


@dataclass
class BPETokenizer:
    vocab_size: int = 512
    merges: List[Tuple[bytes, bytes]] = field(default_factory=list)
    vocab: Dict[bytes, int] = field(default_factory=dict)
    inv_vocab: Dict[int, bytes] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.vocab:
            # byte fallback base: all 256 bytes always present
            for i in range(256):
                piece = bytes([i])
                self.vocab[piece] = i
                self.inv_vocab[i] = piece
            # end-of-word marker is not a byte; it must exist on its own so
            # unseen words still encode (training always merges it away).
            self.vocab[b"</w>"] = 256
            self.inv_vocab[256] = b"</w>"

    # -- training --------------------------------------------------------
    def train(self, texts: Sequence[str]) -> None:
        """Repeated most-frequent-pair merging until vocab_size is reached."""
        # corpus as list of byte-symbol lists, split on whitespace first
        words: List[List[bytes]] = []
        for text in texts:
            for word in text.split():
                syms = [bytes([b]) for b in word.encode("utf-8")]
                if syms:
                    words.append(syms + [b"</w>"])
        target = self.vocab_size
        while len(self.vocab) < target:
            pairs: Counter[Tuple[bytes, bytes]] = Counter()
            for syms in words:
                for a, b in zip(syms, syms[1:], strict=False):
                    pairs[(a, b)] += 1
            if not pairs:
                break
            (a, b), count = pairs.most_common(1)[0]
            if count < 2:
                break  # nothing left worth merging
            merged = a + b
            new_id = len(self.vocab)
            self.vocab[merged] = new_id
            self.inv_vocab[new_id] = merged
            self.merges.append((a, b))
            # apply merge everywhere
            new_words: List[List[bytes]] = []
            for syms in words:
                out: List[bytes] = []
                i = 0
                while i < len(syms):
                    if i + 1 < len(syms) and syms[i] == a and syms[i + 1] == b:
                        out.append(merged)
                        i += 2
                    else:
                        out.append(syms[i])
                        i += 1
                new_words.append(out)
            words = new_words

    # -- encode / decode ---------------------------------------------------
    def _apply_merges(self, syms: List[bytes]) -> List[bytes]:
        for a, b in self.merges:
            merged = a + b
            out: List[bytes] = []
            i = 0
            while i < len(syms):
                if i + 1 < len(syms) and syms[i] == a and syms[i + 1] == b:
                    out.append(merged)
                    i += 2
                else:
                    out.append(syms[i])
                    i += 1
            syms = out
        return syms

    def encode(self, text: str) -> List[int]:
        ids: List[int] = []
        for word in text.split():
            syms: List[bytes] = [bytes([b]) for b in word.encode("utf-8")]
            syms.append(b"</w>")
            for piece in self._apply_merges(syms):
                ids.append(self.vocab[piece])
        return ids

    def decode(self, ids: Sequence[int]) -> str:
        raw = b"".join(self.inv_vocab[i] for i in ids)
        return raw.replace(b"</w>", b" ").decode("utf-8", errors="replace").strip()

    # -- token healing ------------------------------------------------------
    def heal_prefix(self, partial: bytes) -> bytes:
        """Back up to the last boundary the merge rules respect.

        Given trailing bytes of a generation that may cut a merged token in
        half, return the longest prefix that decodes to whole tokens only.
        """
        for cut in range(len(partial), -1, -1):
            prefix = partial[:cut]
            try:
                ids = self.encode(prefix.decode("utf-8", errors="strict"))
                if self.decode(ids).encode("utf-8") == prefix:
                    return prefix
            except (UnicodeDecodeError, KeyError):
                continue
        return b""

    def token_boundary_ok(self, text: str) -> bool:
        """True when text round-trips through encode/decode unchanged."""
        return self.decode(self.encode(text)) == text
