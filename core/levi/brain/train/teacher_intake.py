"""Teacher intake: the curator seat of the tag-team training pipeline.

Chauncey pastes teacher output from the nine trainers — Muse (Rex),
Gemini, ChatGPT, Claude, Grok, Qwen, DeepSeek, Mistral, Kimi — as JSONL
records ``{"teacher": ..., "prompt": ..., "response": ...}``. This module
normalizes every record into the checkpoint's character vocabulary
(deterministic transliteration for common out-of-vocab characters, the
rest dropped with a count), runs the identity-law spot checks, and emits
clean training records in the ``User:``/``LEVI:`` turn format that
``continue.py`` consumes.

Every record carries a stable content ID (sha256 of the curated text),
the raw paste verbatim, and a provenance trail (teacher, round,
timestamp). The intake dedupes within a run and the pipeline dedupes
across rounds: same content in, one record out, with one provenance
event per sighting.

The checkpoint vocab is char-level (162 chars) and ``continue.py``
ABORTS on any out-of-vocab character — so the normalizer is a hard gate,
not a suggestion.

``--mode bpe`` keeps the full raw text for subword tokenization instead:
no transliteration, no dropping (byte-level BPE is lossless on any
unicode). The identity-law spot checks still run in both modes.

Stdlib only. Deterministic: fixed order, no randomness.

Usage:
    python3 teacher_intake.py --in pastes.jsonl --out records.jsonl \\
        --ckpt ../weights/tiny-gpt.pt
    python3 teacher_intake.py --in pastes.jsonl --out bpe_records.jsonl \\
        --mode bpe
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

# The nine trainers on the tag team. "muse" is Rex's own seat.
TEACHERS = (
    "muse",
    "gemini",
    "chatgpt",
    "claude",
    "grok",
    "qwen",
    "deepseek",
    "mistral",
    "kimi",
)

# Record modalities. "text" is the historical default: old pastes carry no
# modality key and intake as text. "photo"/"video" records come from the
# HQ3-MM generator — their responses are generation SPECS (image specs /
# shot-list scripts), never rendered pixels or clips.
MODALITIES = ("text", "photo", "video")
# Deterministic transliteration: common out-of-vocab characters mapped to
# their closest in-vocab ASCII equivalent. Everything not in the map and
# not in the vocab is dropped (counted, never silently kept).
TRANSLITERATE = {
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote
    "\u201a": "'",
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u201e": '"',
    "\u00ab": '"',
    "\u00bb": '"',
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2212": "-",
    "\u2026": "...",  # ellipsis
    "\u00a0": " ",  # non-breaking space
    "\u2009": " ",  # thin space
    "\u200a": " ",
    "\u202f": " ",
    "\u200b": "",  # zero-width space: removed
    "\u200c": "",
    "\u200d": "",
    "\ufeff": "",  # BOM
    "\u2192": "->",
    "\u2190": "<-",
    "\u00d7": "x",
    "\u00f7": "/",
    "\u2264": "<=",
    "\u2265": ">=",
    "\u2260": "!=",
    "\u2248": "~",
    "\u00b0": "deg",
    "\u2022": "-",  # bullet
    "\u00b7": "-",
    "\u2713": "ok",
    "\u2717": "x",
    "\u00e9": "e",  # common accented latin -> ascii
    "\u00e8": "e",
    "\u00ea": "e",
    "\u00eb": "e",
    "\u00e0": "a",
    "\u00e1": "a",
    "\u00e2": "a",
    "\u00e4": "a",
    "\u00e7": "c",
    "\u00ec": "i",
    "\u00ed": "i",
    "\u00ee": "i",
    "\u00ef": "i",
    "\u00f2": "o",
    "\u00f3": "o",
    "\u00f4": "o",
    "\u00f6": "o",
    "\u00f9": "u",
    "\u00fa": "u",
    "\u00fb": "u",
    "\u00fc": "u",
    "\u00f1": "n",
    "\u00df": "ss",
    "\u00c9": "E",
    "\u00c0": "A",
    "\u00c8": "E",
    "\u00d1": "N",
    "\u00d6": "O",
    "\u00dc": "U",
}

# Identity-law spot checks on the LEVI turn: must never appear as a CLAIM.
# (Same law as build_dialogue_corpus.py; negations stating the law are
# exempt via _negated().)
FORBIDDEN = [
    r"\bi feel\b",
    r"\bi felt\b",
    r"\bconscious\b",
    r"\bsentient\b",
    r"\bmy feelings\b",
    r"\bi'm alive\b",
    r"\bi am alive\b",
]

_NEGATION_RE = re.compile(
    r"\b(never|not|no|don't|do not|isn't|is not|aren't|are not|without)\b"
    r"[^.]{0,60}?(conscious|sentient|feelings|alive)\b",
    re.I,
)

USER_TAG = "User: "
LEVI_TAG = "LEVI: "

MIN_TURNS_CHARS = 4
MAX_RECORD_CHARS = 4000

RECORD_ID_PREFIX = "tch-"
RECORD_ID_HEX = 16  # 64 bits: enough for the corpus scale, stays readable


def record_id_for(text: str) -> str:
    """Stable content ID for a curated record.

    Deterministic on the curated training text alone — so the same content
    pasted again next round (or by another teacher) maps to the same ID and
    dedupes to one record. Mode needs no separate slot: char mode crushes
    unicode while bpe mode keeps it, so the texts already differ.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:RECORD_ID_HEX]
    return f"{RECORD_ID_PREFIX}{digest}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Rejected(Exception):
    """A pasted record failed the curator gate."""


def load_vocab_chars(ckpt_path: Path) -> list[str]:
    """Load the checkpoint's character vocabulary (the hard gate)."""
    import torch

    ckpt = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    chars = ckpt["chars"]
    if not chars:
        raise Rejected("checkpoint has empty vocab")
    return list(chars)


def normalize(text: str, vocab: set[str]) -> tuple[str, int, int]:
    """Map text into the vocab. Returns (clean, n_mapped, n_dropped).

    Deterministic: transliteration map first, then drop anything still
    outside the vocab. Whitespace runs collapse to single spaces.
    """
    mapped = 0
    dropped = 0
    out: list[str] = []
    for ch in text:
        if ch in vocab:
            out.append(ch)
        elif ch in TRANSLITERATE:
            rep = TRANSLITERATE[ch]
            for rch in rep:
                if rch in vocab:
                    out.append(rch)
                else:
                    dropped += 1
            mapped += 1
        else:
            dropped += 1
    clean = re.sub(r"[ \t]+", " ", "".join(out))
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    return clean, mapped, dropped


def normalize_bpe(text: str) -> str:
    """Light cleanup for BPE mode: whitespace only, zero loss.

    Byte-level BPE is lossless on any unicode, so nothing is transliterated
    or dropped — curly quotes, emoji, CJK all survive verbatim.
    """
    clean = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", clean).strip()


def _negated(text: str) -> bool:
    return bool(_NEGATION_RE.search(text))


def check_identity_law(levi_turn: str) -> None:
    """Raise Rejected if the LEVI turn violates the identity law."""
    low = levi_turn.lower()
    for pat in FORBIDDEN:
        for m in re.finditer(pat, low):
            # exempt when the match sits inside a negation stating the law
            window = low[max(0, m.start() - 60) : m.end() + 10]
            if not _negated(window):
                raise Rejected(f"identity-law violation: {pat!r}")


def intake_record(
    teacher: str,
    prompt: str,
    response: str,
    vocab: set[str] | None = None,
    topic: str = "",
    mode: str = "char",
    round: str = "",
    ts: str | None = None,
    modality: str = "text",
) -> tuple[dict, dict]:
    """Curate one pasted teacher record.

    ``mode="char"`` (default): normalize into the checkpoint's character
    vocab (requires ``vocab``); transliteration + drops counted.
    ``mode="bpe"``: keep the full raw text for subword tokenization —
    no mapping, no drops.

    ``round`` names the collection round (e.g. "round-1"); ``ts`` is the
    collection timestamp (ISO-8601, defaults to now UTC). Both land in the
    record's provenance so every record is traceable to its source
    teacher, round, and timestamp.

    ``modality`` is "text" (default, backward-compatible: old pastes
    carry no modality), "photo", or "video". It is validated and stored
    on the record; the text/shape of the record is unchanged.

    Returns (record, stats). Raises Rejected when the record fails the gate.
    """
    teacher = teacher.strip().lower()
    if teacher not in TEACHERS:
        raise Rejected(f"unknown teacher: {teacher!r}")
    modality = (modality or "text").strip().lower()
    if modality not in MODALITIES:
        raise Rejected(f"unknown modality: {modality!r}")
    if mode == "bpe":
        user_text = normalize_bpe(prompt)
        levi_text = normalize_bpe(response)
        n_map_u = n_drop_u = n_map_l = n_drop_l = 0
    elif mode == "char":
        if vocab is None:
            raise Rejected("char mode needs a checkpoint vocab")
        user_text, n_map_u, n_drop_u = normalize(prompt, vocab)
        levi_text, n_map_l, n_drop_l = normalize(response, vocab)
    else:
        raise Rejected(f"unknown intake mode: {mode!r}")
    if len(user_text) < MIN_TURNS_CHARS:
        raise Rejected("user turn too short after normalization")
    if len(levi_text) < MIN_TURNS_CHARS:
        raise Rejected("LEVI turn too short after normalization")
    if len(user_text) + len(levi_text) > MAX_RECORD_CHARS:
        raise Rejected("record too long")
    check_identity_law(levi_text)
    text = f"{USER_TAG}{user_text}\n{LEVI_TAG}{levi_text}"
    record = {
        "record_id": record_id_for(text),
        "text": text,
        "kind": "dialogue",
        "modality": modality,
        "source": f"teacher:{teacher}",
        "topic": topic,
        "register": "levi",
        # raw-output preservation: the paste verbatim, before any
        # normalization, so future vocabs can re-curate from the original.
        "raw": {"prompt": prompt, "response": response},
        # provenance is a list: dedup merges one event per sighting, so a
        # record seen in several rounds stays traceable to each of them.
        "provenance": [{"teacher": teacher, "round": round, "ts": ts or utc_now_iso()}],
    }
    if mode == "bpe":
        record["tokenizer"] = "levi-bpe-v1"
    stats = {
        "teacher": teacher,
        "mapped": n_map_u + n_map_l,
        "dropped": n_drop_u + n_drop_l,
    }
    return record, stats


def _merge_provenance(record: dict, event: dict) -> None:
    """Append a provenance event unless an identical one is already listed."""
    events = record.setdefault("provenance", [])
    if event not in events:
        events.append(event)


def run(
    in_path: Path,
    out_path: Path,
    vocab: set[str] | None = None,
    mode: str = "char",
    round: str = "",
) -> dict:
    """Run the intake over a pastes JSONL file. Returns the report.

    Deterministic cross-round dedup: records are keyed by their stable
    content ID, so the same content pasted twice (same file or a later
    round) yields one record. The surviving record keeps one provenance
    event per sighting. Paste lines may carry optional ``"round"`` and
    ``"ts"`` fields; they default to the run's ``round`` and now-UTC.
    """
    report = {
        "in": str(in_path),
        "out": str(out_path),
        "mode": mode,
        "round": round,
        "records_in": 0,
        "records_out": 0,
        "rejected": 0,
        "duplicates": 0,
        "chars_mapped": 0,
        "chars_dropped": 0,
        "per_teacher": {t: 0 for t in TEACHERS},
        "per_modality": {m: 0 for m in MODALITIES},
        "rejections": [],
        "duplicate_ids": [],
    }
    by_id: dict[str, dict] = {}
    ordered: list[dict] = []
    with open(in_path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            report["records_in"] += 1
            try:
                obj = json.loads(line)
                rec, stats = intake_record(
                    obj.get("teacher", ""),
                    obj.get("prompt", ""),
                    obj.get("response", ""),
                    vocab,
                    topic=obj.get("topic", ""),
                    mode=mode,
                    round=obj.get("round", "") or round,
                    ts=obj.get("ts"),
                    modality=obj.get("modality", "text"),
                )
            except (Rejected, KeyError, TypeError, AttributeError) as exc:
                report["rejected"] += 1
                report["rejections"].append(f"line {lineno}: {exc}")
                continue
            rid = rec["record_id"]
            if rid in by_id:
                _merge_provenance(by_id[rid], rec["provenance"][0])
                report["duplicates"] += 1
                report["duplicate_ids"].append(rid)
                continue
            by_id[rid] = rec
            ordered.append(rec)
            report["records_out"] += 1
            report["chars_mapped"] += stats["mapped"]
            report["chars_dropped"] += stats["dropped"]
            report["per_teacher"][stats["teacher"]] += 1
            report["per_modality"][rec["modality"]] += 1
    with open(out_path, "w", encoding="utf-8") as fh:
        for rec in ordered:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return report


def verify_provenance(records: list[dict]) -> list[str]:
    """Check every record is traceable: stable ID, intact text, provenance.

    Recomputes each record_id from the record's text (catches tampering or
    hand-edited corpora) and requires a non-empty provenance list whose
    events each name a known teacher. Returns a list of problem strings;
    empty means clean.
    """
    problems: list[str] = []
    for i, rec in enumerate(records):
        where = f"record {i} ({rec.get('record_id', '?')})"
        text = rec.get("text", "")
        expected = record_id_for(text) if text else ""
        if not rec.get("record_id"):
            problems.append(f"{where}: missing record_id")
        elif rec["record_id"] != expected:
            problems.append(
                f"{where}: record_id mismatch — text was altered after intake"
            )
        events = rec.get("provenance")
        if not isinstance(events, list) or not events:
            problems.append(f"{where}: missing or empty provenance")
        else:
            for ev in events:
                if not isinstance(ev, dict):
                    problems.append(f"{where}: malformed provenance event")
                    continue
                teacher = ev.get("teacher", "")
                if teacher not in TEACHERS:
                    problems.append(
                        f"{where}: unknown teacher in provenance: {teacher!r}"
                    )
                if "round" not in ev or "ts" not in ev:
                    problems.append(f"{where}: provenance event missing round/ts")
        if not isinstance(rec.get("raw"), dict) or not rec["raw"].get("response"):
            problems.append(f"{where}: raw output not preserved")
        mod = rec.get("modality", "text")  # old records predate the field
        if mod not in MODALITIES:
            problems.append(f"{where}: unknown modality: {mod!r}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Curate teacher pastes into clean training records."
    )
    ap.add_argument("--in", dest="in_path", required=True, help="pastes JSONL file")
    ap.add_argument(
        "--out", dest="out_path", required=True, help="clean records JSONL output"
    )
    ap.add_argument(
        "--ckpt",
        default="",
        help="checkpoint .pt (vocab source; required in char mode)",
    )
    ap.add_argument(
        "--mode",
        choices=("char", "bpe"),
        default="char",
        help="char: crush into the checkpoint's 162-char vocab (default). "
        "bpe: keep full raw text for subword tokenization (levi-bpe-v1), "
        "no transliteration, no drops.",
    )
    ap.add_argument(
        "--report", default="", help="write JSON report here (default: stdout)"
    )
    ap.add_argument(
        "--round",
        default="",
        help="collection round label stamped into provenance (e.g. round-1); "
        'paste lines may also carry their own "round"/"ts" fields',
    )
    args = ap.parse_args(argv)

    vocab: set[str] | None = None
    if args.mode == "char":
        if not args.ckpt:
            print("ABORT: char mode needs --ckpt (vocab source)", flush=True)
            return 2
        vocab = set(load_vocab_chars(Path(args.ckpt)))
    report = run(
        Path(args.in_path), Path(args.out_path), vocab, mode=args.mode, round=args.round
    )
    text = json.dumps(report, indent=2)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
