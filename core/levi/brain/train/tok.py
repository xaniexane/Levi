"""Byte-level BPE tokenizer for LEVI's native brain (v2).

Pure Python, stdlib only. Byte-level means the codec is lossless on ANY
unicode text: text -> UTF-8 bytes -> tokens -> bytes -> identical text.

Vocab layout::

    0..255   raw bytes (rendered through the GPT-2-style bytes<->unicode map
             so every merge candidate is a printable "character")
    256      <pad>   padding
    257      <doc>   document-start boundary marker
    258      <eod>   end-of-document boundary marker
    259      <unk>   reserved (never emitted; keeps the layout stable)
    260..     BPE merges, in training order

The special ids are NEVER produced by ``encode``; the data pipeline inserts
``<doc>``/``<eod>`` itself. ``decode`` renders special ids as their literal
marker strings so a token stream stays human-inspectable.

Training is the classic Sennrich BPE loop with an inverted pair->word index,
so each merge only touches words that contain the merged pair. Training on
~1MB of text to an 8k vocab takes a few minutes on a laptop CPU and is a
one-time cost; the trained tokenizer is saved as JSON.

Example:
    tok = ByteBPETokenizer.train(texts, vocab_size=8192)
    tok.save("tokenizer.json")
    tok = ByteBPETokenizer.load("tokenizer.json")
    assert tok.decode(tok.encode("hello wörld 🌍")) == "hello wörld 🌍"
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

# ---------------------------------------------------------------- byte map
# GPT-2-style reversible bytes <-> unicode mapping: every byte 0..255 maps to
# a unique printable unicode char, so BPE "characters" are always printable.


def _bytes_to_unicode() -> dict[int, str]:
    bs = (
        list(range(ord("!"), ord("~") + 1))
        + list(range(ord("¡"), ord("¬") + 1))
        + list(range(ord("®"), ord("ÿ") + 1))
    )
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return {b: chr(c) for b, c in zip(bs, cs, strict=True)}


_BYTE_TO_UNI = _bytes_to_unicode()
_UNI_TO_BYTE = {c: b for b, c in _BYTE_TO_UNI.items()}

# ---------------------------------------------------------------- specials

PAD, DOC, EOD, UNK = 256, 257, 258, 259
N_SPECIAL_BASE = 260  # ids 0..259 reserved (bytes + specials)
SPECIALS = {"<pad>": PAD, "<doc>": DOC, "<eod>": EOD, "<unk>": UNK}
SPECIAL_IDS = {v: k for k, v in SPECIALS.items()}

_WORD_RE = re.compile(r"\S+|\s+")

FORMAT = "levi-bpe-v1"


class ByteBPETokenizer:
    """Byte-level BPE codec. Build with :meth:`train`, persist with save/load."""

    def __init__(
        self,
        merges: list[tuple[str, str]],
        specials: dict[str, int] | None = None,
    ):
        self.merges = list(merges)
        self.specials = dict(specials or SPECIALS)
        # merge rank: lower index = merged earlier = higher priority when encoding
        self._rank: dict[tuple[str, str], int] = {
            pair: i for i, pair in enumerate(self.merges)
        }
        # token string -> id; byte chars first, then specials, then merges
        self._tok2id: dict[str, int] = {}
        for b in range(256):
            self._tok2id[_BYTE_TO_UNI[b]] = b
        for name, sid in self.specials.items():
            self._tok2id[name] = sid
        for i, (a, b) in enumerate(self.merges):
            self._tok2id[a + b] = N_SPECIAL_BASE + i
        self._id2tok: dict[int, str] = {v: k for k, v in self._tok2id.items()}
        self._encode_cache: dict[str, list[int]] = {}

    # ------------------------------------------------------------ properties

    @property
    def vocab_size(self) -> int:
        return N_SPECIAL_BASE + len(self.merges)

    @property
    def pad_id(self) -> int:
        return self.specials["<pad>"]

    @property
    def doc_id(self) -> int:
        return self.specials["<doc>"]

    @property
    def eod_id(self) -> int:
        return self.specials["<eod>"]

    # ------------------------------------------------------------ encode

    def _bpe_word(self, word: str) -> tuple[str, ...]:
        """Apply merges to one pretokenized word (chars are byte-unicode chars)."""
        if word in self._encode_cache:
            return tuple(self._encode_cache[word])  # type: ignore[return-value]
        symbols = list(word)
        if len(symbols) == 1:
            out = [self._tok2id[symbols[0]]]
            self._encode_cache[word] = out
            return tuple(out)
        while True:
            # find the highest-priority (lowest-rank) adjacent pair
            best_rank: int | None = None
            best_i = -1
            for i in range(len(symbols) - 1):
                r = self._rank.get((symbols[i], symbols[i + 1]))
                if r is not None and (best_rank is None or r < best_rank):
                    best_rank = r
                    best_i = i
            if best_i < 0:
                break
            # merge it
            a, b = symbols[best_i], symbols[best_i + 1]
            symbols = symbols[:best_i] + [a + b] + symbols[best_i + 2 :]
            if len(symbols) == 1:
                break
        out = [self._tok2id[s] for s in symbols]
        # bound the cache: the corpus tail is mostly repeats, the head is noise
        if len(self._encode_cache) < 200_000:
            self._encode_cache[word] = out
        return tuple(out)

    def encode(self, text: str) -> list[int]:
        """Text -> token ids. Byte-exact invertible via :meth:`decode`.

        Words are split on the RAW text first (mirroring training): the
        byte<->unicode map turns whitespace bytes into non-whitespace
        chars, so splitting after mapping would treat a whole document
        as one "word" and make encoding quadratic.
        """
        if not text:
            return []
        ids: list[int] = []
        for word in _WORD_RE.findall(text):
            byte_chars = "".join(_BYTE_TO_UNI[b] for b in word.encode("utf-8"))
            ids.extend(self._bpe_word(byte_chars))
        return ids

    # ------------------------------------------------------------ decode

    def decode(self, ids: list[int]) -> str:
        """Token ids -> text. Special ids render as their marker strings."""
        pieces: list[str] = []
        byte_buf = bytearray()
        for i in ids:
            if i in SPECIAL_IDS:
                if byte_buf:
                    pieces.append(byte_buf.decode("utf-8", errors="replace"))
                    byte_buf = bytearray()
                pieces.append(SPECIAL_IDS[i])
                continue
            tok = self._id2tok.get(i)
            if tok is None:
                raise ValueError(f"unknown token id {i}")
            for ch in tok:
                b = _UNI_TO_BYTE.get(ch)
                if b is None:  # pragma: no cover - cannot happen for trained ids
                    raise ValueError(f"token {i!r} contains non-byte char")
                byte_buf.append(b)
        if byte_buf:
            pieces.append(byte_buf.decode("utf-8", errors="replace"))
        return "".join(pieces)

    # ------------------------------------------------------------ training

    @classmethod
    def train(
        cls,
        texts: list[str],
        vocab_size: int = 8192,
        max_train_chars: int = 1_000_000,
        min_pair_freq: int = 2,
        verbose: bool = True,
    ) -> "ByteBPETokenizer":
        """Train BPE merges on ``texts`` (joined, truncated to max_train_chars).

        Stops early if the most frequent remaining pair occurs fewer than
        ``min_pair_freq`` times — small corpora honestly yield small vocabs.
        """
        corpus = "".join(texts)[:max_train_chars]
        # pretokenize into words; words are tuples of byte-unicode chars
        word_counts: dict[tuple[str, ...], int] = {}
        for w in _WORD_RE.findall(corpus):
            chars = tuple(_BYTE_TO_UNI[b] for b in w.encode("utf-8"))
            if chars:
                word_counts[chars] = word_counts.get(chars, 0) + 1

        words: list[list[str]] = [list(w) for w in word_counts]
        freqs: list[int] = [word_counts[w] for w in word_counts]

        # pair counts + inverted index: pair -> set of word indices containing it
        pair_counts: dict[tuple[str, str], int] = {}
        pair_words: dict[tuple[str, str], set[int]] = {}
        for wi, w in enumerate(words):
            seen: set[tuple[str, str]] = set()
            for i in range(len(w) - 1):
                p = (w[i], w[i + 1])
                pair_counts[p] = pair_counts.get(p, 0) + freqs[wi]
                if p not in seen:
                    seen.add(p)
                    pair_words.setdefault(p, set()).add(wi)

        n_merges = max(0, vocab_size - N_SPECIAL_BASE)
        merges: list[tuple[str, str]] = []
        for m in range(n_merges):
            if not pair_counts:
                break
            best = max(pair_counts, key=pair_counts.get)  # type: ignore[arg-type]
            if pair_counts[best] < min_pair_freq:
                if verbose:
                    print(
                        f"  BPE: stopping early at merge {m}: "
                        f"best pair freq {pair_counts[best]} < {min_pair_freq}"
                    )
                break
            a, b = best
            merges.append(best)
            del pair_counts[best]
            affected = pair_words.pop(best, set())
            for wi in sorted(affected):
                w = words[wi]
                f = freqs[wi]
                # remove this word's contribution to every adjacent pair
                # (each occurrence, not each unique pair)
                old_pairs: set[tuple[str, str]] = set()
                for i in range(len(w) - 1):
                    p = (w[i], w[i + 1])
                    old_pairs.add(p)
                    c = pair_counts.get(p, 0) - f
                    if c <= 0:
                        pair_counts.pop(p, None)
                    else:
                        pair_counts[p] = c
                for p in old_pairs:
                    s = pair_words.get(p)
                    if s is not None:
                        s.discard(wi)
                        if not s:
                            pair_words.pop(p, None)
                # merge all non-overlapping occurrences of (a, b) in the word
                new_w: list[str] = []
                i = 0
                while i < len(w):
                    if i < len(w) - 1 and w[i] == a and w[i + 1] == b:
                        new_w.append(a + b)
                        i += 2
                    else:
                        new_w.append(w[i])
                        i += 1
                words[wi] = new_w
                # add new pair counts
                seen2: set[tuple[str, str]] = set()
                for i in range(len(new_w) - 1):
                    p = (new_w[i], new_w[i + 1])
                    pair_counts[p] = pair_counts.get(p, 0) + f
                    if p not in seen2:
                        seen2.add(p)
                        pair_words.setdefault(p, set()).add(wi)
            if verbose and (m + 1) % 1000 == 0:
                print(f"  BPE: merge {m + 1}/{n_merges}")
        if verbose:
            print(
                f"  BPE: trained {len(merges)} merges -> "
                f"vocab size {N_SPECIAL_BASE + len(merges)}"
            )
        return cls(merges)

    @classmethod
    def train_from_jsonl(
        cls,
        path: str | Path,
        text_field: str = "text",
        id_field: str = "id",
        **kwargs,
    ) -> "ByteBPETokenizer":
        """Train on a JSONL corpus of {text_field: ...} records (e.g. corpus.jsonl)."""
        import io as _io

        texts: list[str] = []
        n_chars = 0
        cap = kwargs.get("max_train_chars", 1_000_000)
        with _io.open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                t = rec.get(text_field, "")
                if not t:
                    continue
                texts.append(t)
                n_chars += len(t)
                if n_chars >= cap * 2:  # read a bit extra; train() truncates
                    break
        return cls.train(texts, **kwargs)

    # ------------------------------------------------------------ persistence

    def save(self, path: str | Path) -> None:
        payload = {
            "format": FORMAT,
            "merges": [[a, b] for a, b in self.merges],
            "specials": self.specials,
        }
        Path(path).write_text(json.dumps(payload), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "ByteBPETokenizer":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("format") != FORMAT:
            raise ValueError(f"not a {FORMAT} tokenizer file: {path}")
        merges = [tuple(p) for p in payload["merges"]]
        return cls(merges, specials=payload.get("specials"))


# ---------------------------------------------------------------------------
# Harness-facing factory: load, or train + save, from a JSON spec.
# The v2 harness calls the tokenizer builder with no arguments; the spec is
# then read from ``$LEVI_TOKENIZER_SPEC`` or ``tokenizer_spec.json`` next to
# this module. A spec dict (or path to a JSON spec file) may be passed
# directly, e.g. from scripts and tests.
# ---------------------------------------------------------------------------

TRAIN_DIR = Path(__file__).resolve().parent
DEFAULT_SPEC_PATH = TRAIN_DIR / "tokenizer_spec.json"
DEFAULT_TOKENIZER_FILENAME = "tokenizer.json"

_SPEC_KEYS = frozenset(
    {"path", "vocab_size", "corpus", "text_field", "max_train_chars", "force_retrain"}
)


def _resolve_spec(spec: dict | str | Path | None) -> dict:
    """Return the effective spec dict (may be empty)."""
    if spec is None:
        env = os.environ.get("LEVI_TOKENIZER_SPEC")
        if env:
            spec = env
        elif DEFAULT_SPEC_PATH.is_file():
            spec = DEFAULT_SPEC_PATH
        else:
            return {}
    if isinstance(spec, (str, Path)):
        spec = json.loads(Path(spec).read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        raise ValueError(
            f"tokenizer spec must be a JSON object (dict), got {type(spec).__name__}"
        )
    unknown = set(spec) - _SPEC_KEYS
    if unknown:
        raise ValueError(f"unknown tokenizer spec keys: {sorted(unknown)}")
    return dict(spec)


def build_tokenizer(spec: dict | str | Path | None = None) -> ByteBPETokenizer:
    """Load a tokenizer, or train + save one, from a JSON spec.

    Spec keys (all optional):
      ``path``: tokenizer JSON location; relative paths resolve against
        ``core/levi/brain/train/``. Defaults to ``tokenizer.json`` there.
      ``vocab_size``: target vocab when training (default 8192).
      ``corpus``: JSONL corpus to train from when ``path`` is missing;
        relative paths resolve against ``core/levi/brain/train/``.
      ``text_field``: record field holding the text (default ``"text"``).
      ``max_train_chars``: cap on training chars (default 2_000_000).
      ``force_retrain``: re-train even if ``path`` exists (default False).

    Resolution: existing ``path`` -> load; missing ``path`` + ``corpus`` ->
    train, save to ``path``, return; missing ``path`` and no ``corpus`` ->
    loud error naming the training command (never a silently wrong vocab).
    """
    cfg = _resolve_spec(spec)
    tdir = TRAIN_DIR

    def _abs(p: str | Path) -> Path:
        p = Path(p)
        return p if p.is_absolute() else tdir / p

    tok_path = _abs(cfg.get("path", DEFAULT_TOKENIZER_FILENAME))
    force = bool(cfg.get("force_retrain", False))
    if tok_path.is_file() and not force:
        return ByteBPETokenizer.load(tok_path)

    corpus = cfg.get("corpus")
    if not corpus:
        raise FileNotFoundError(
            f"v2 tokenizer not found at {tok_path} and no 'corpus' in the "
            "tokenizer spec; train one first:\n"
            f"  python3 tok.py --corpus {tdir / 'corpus.jsonl'} "
            f"--vocab {cfg.get('vocab_size', 8192)} --out {tok_path}"
        )
    corpus_path = _abs(corpus)
    if not corpus_path.is_file():
        raise FileNotFoundError(
            f"tokenizer spec 'corpus' not found: {corpus_path} "
            f"(from spec value {corpus!r})"
        )
    tok = ByteBPETokenizer.train_from_jsonl(
        corpus_path,
        text_field=cfg.get("text_field", "text"),
        vocab_size=int(cfg.get("vocab_size", 8192)),
        max_train_chars=int(cfg.get("max_train_chars", 2_000_000)),
        verbose=False,
    )
    tok_path.parent.mkdir(parents=True, exist_ok=True)
    tok.save(tok_path)
    return tok


def main(argv=None) -> int:
    """CLI: python3 tok.py --corpus corpus.jsonl --vocab 8192 --out tokenizer.json"""
    import argparse
    import time

    ap = argparse.ArgumentParser(description="Train a byte-level BPE tokenizer.")
    ap.add_argument("--corpus", required=True, help="JSONL corpus file")
    ap.add_argument("--vocab", type=int, default=8192, help="target vocab size")
    ap.add_argument("--out", required=True, help="output tokenizer JSON path")
    ap.add_argument("--text-field", default="text")
    ap.add_argument("--max-chars", type=int, default=2_000_000)
    args = ap.parse_args(argv)

    t0 = time.time()
    tok = ByteBPETokenizer.train_from_jsonl(
        args.corpus,
        text_field=args.text_field,
        vocab_size=args.vocab,
        max_train_chars=args.max_chars,
    )
    tok.save(args.out)
    print(
        f"trained vocab_size={tok.vocab_size} in {time.time() - t0:.1f}s -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
