#!/usr/bin/env python3
"""
Train LEVI Native LM from scratch on your Brain corpus.
No Ollama, no external weights — order-N character Markov + word Markov hybrid.
Original to your data. Not cloud-LLM quality; fully yours.
"""
from __future__ import annotations
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "corpus.txt"
MODEL = ROOT / "levi_native_model.json"


def train(char_order: int = 5, word_order: int = 2) -> dict:
    text = CORPUS.read_text(encoding="utf-8")
    # Char model
    c_counts: dict = defaultdict(lambda: defaultdict(int))
    for i in range(len(text) - char_order):
        ctx = text[i : i + char_order]
        nxt = text[i + char_order]
        c_counts[ctx][nxt] += 1
    char_model = {
        ctx: dict(nxts) for ctx, nxts in c_counts.items() if sum(nxts.values()) >= 1
    }

    # Word model
    words = text.replace("\n", " \n ").split()
    w_counts: dict = defaultdict(lambda: defaultdict(int))
    for i in range(len(words) - word_order):
        ctx = tuple(words[i : i + word_order])
        nxt = words[i + word_order]
        w_counts[ctx][nxt] += 1
    word_model = {
        "||".join(ctx): dict(nxts) for ctx, nxts in w_counts.items()
    }

    meta = {
        "name": "LEVI-Native",
        "version": "1.0.0",
        "from_scratch": True,
        "no_ollama": True,
        "char_order": char_order,
        "word_order": word_order,
        "corpus_chars": len(text),
        "corpus_words": len(words),
        "char_contexts": len(char_model),
        "word_contexts": len(word_model),
        "note": "Trained only on LEVI Brain + seed dialogue. Original weights = transition tables.",
    }
    blob = {"meta": meta, "char": char_model, "word": word_model}
    MODEL.write_text(json.dumps(blob), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    print("Wrote", MODEL, "size", MODEL.stat().st_size)
    return meta


if __name__ == "__main__":
    train()
