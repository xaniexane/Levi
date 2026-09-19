"""Generate the eval probe set from kind-tagged corpus docs.

Probes are the capability half of the spectrum: held-out NLL measures
prediction, probes measure comprehension (topic) and next-token
precision. They are generated — not hand-written — so they stay
grounded in the actual corpus, and deterministically (fixed seed), so
every run in the bloodline is measured against the SAME probes.

Probe schema (see ``eval_harness.load_probes``):
- ``{"kind": "next_token", "prefix": "...", "expected": "..."}``
- ``{"kind": "topic", "text": "...", "choices": [{"label", "text"}...]}``
  (first choice is the correct one by fixture convention)

Usage::

    python3 core/levi/brain/train/v2/make_probes.py \
        --input runs/tiny-gpt-v2-20260916/corpora/train.jsonl \
        --output core/levi/brain/train/v2/eval/probes.jsonl \
        --seed 1337

The output starts with ``#`` provenance comments (skipped by the loader).
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
WORD_CLEAN = re.compile(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$")


def _words(sentence: str) -> list[str]:
    return [w for w in (WORD_CLEAN.sub("", t) for t in sentence.split()) if w]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_SPLIT.split(text) if s.strip()]


def make_next_token(
    docs: list[dict], rng: random.Random, per_doc: int = 1, want: int = 60
) -> list[dict]:
    """prefix = sentence minus last word, expected = last word."""
    probes: list[dict] = []
    seen: set[tuple[str, str]] = set()
    order = list(range(len(docs)))
    rng.shuffle(order)
    for di in order:
        if len(probes) >= want:
            break
        sents = [_words(s) for s in _sentences(docs[di].get("text", ""))]
        cands = [
            w for w in sents
            if 6 <= len(w) <= 40 and len(w[-1]) >= 3 and w[-1][0].isalpha()
        ]
        rng.shuffle(cands)
        added = 0
        for w in cands:
            if added >= per_doc or len(probes) >= want:
                break
            prefix, expected = " ".join(w[:-1]), w[-1]
            key = (prefix, expected)
            if key in seen:
                continue
            seen.add(key)
            probes.append(
                {"kind": "next_token", "prefix": prefix, "expected": expected}
            )
            added += 1
    return probes


def make_topic(
    docs: list[dict], rng: random.Random, want: int = 30
) -> list[dict]:
    """Classify the doc's kind from an excerpt.

    Choices are the kind words themselves; the model scores which kind-word
    most likely continues the excerpt. First choice is correct.
    """
    kinds = sorted({(d.get("meta") or {}).get("kind") for d in docs} - {None})
    if len(kinds) < 2:
        return []
    probes: list[dict] = []
    seen: set[str] = set()
    order = list(range(len(docs)))
    rng.shuffle(order)
    for di in order:
        if len(probes) >= want:
            break
        doc = docs[di]
        kind = (doc.get("meta") or {}).get("kind")
        if not kind:
            continue
        sents = [_words(s) for s in _sentences(doc.get("text", ""))]
        cands = [w for w in sents if 15 <= len(w) <= 35]
        if not cands:
            continue
        text = " ".join(rng.choice(cands))
        if text in seen:
            continue
        seen.add(text)
        others = [k for k in kinds if k != kind]
        rng.shuffle(others)
        choices = [{"label": kind, "text": kind}]
        choices += [{"label": k, "text": k} for k in others[:2]]
        probes.append({"kind": "topic", "text": text, "choices": choices})
    return probes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate eval probes from corpus docs.")
    ap.add_argument("--input", required=True, help="kind-tagged corpus JSONL")
    ap.add_argument("--output", required=True, help="probes JSONL to write")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--next-token", type=int, default=60, dest="want_nt")
    ap.add_argument("--topic", type=int, default=30, dest="want_topic")
    args = ap.parse_args(argv)

    docs = [
        json.loads(line)
        for line in Path(args.input).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rng = random.Random(args.seed)
    nt = make_next_token(docs, rng, want=args.want_nt)
    topic = make_topic(docs, rng, want=args.want_topic)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# probes for the v2 brain eval harness (generated, do not hand-edit)",
        f"# source: {args.input}",
        f"# seed: {args.seed} | docs: {len(docs)} | "
        f"next_token: {len(nt)} | topic: {len(topic)}",
        f"# regenerate: python3 core/levi/brain/train/v2/make_probes.py "
        f"--input {args.input} --seed {args.seed} --output <probes.jsonl>",
    ]
    for p in nt + topic:
        lines.append(json.dumps(p, ensure_ascii=False))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"probes -> {out}: {len(nt)} next_token, {len(topic)} topic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
