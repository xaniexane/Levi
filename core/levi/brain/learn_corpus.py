"""Learning-loop corpus builder: observations -> training corpus.

Pipeline (all deterministic — same observations + same config produce
byte-identical output):

1. stable order   — sort records by (ts, prompt_sha256)
2. score+filter   — quality score per record; drop empties, out-of-bounds
   lengths, and anything below ``min_quality``
3. dedupe         — sha256 of the distillation text; keep the
   highest-scored copy, count the rest
4. vocab filter   — drop characters outside the incumbent's charset so the
   candidate trains in the same output space (counted honestly)
5. teacher weight — deterministic oversampling: a teacher with weight 2.0
   contributes each record twice (capped); weights recorded in the manifest
6. split          — seeded shuffle, then train/val split by ``val_ratio``
7. curriculum     — the train split is ordered easy -> hard by a cheap
   difficulty heuristic (length + character entropy); the difficulty score
   is stored per line so future curriculum-aware trainers can use it.
   (The bundled v1 trainer samples uniformly, so ordering is currently
   advisory — the manifest says so plainly.)

Output (never overwrites the original weights or the observation log):

    <out_dir>/train.jsonl      # {"text": ..., "source": {...}} per line
    <out_dir>/val.jsonl
    <out_dir>/manifest.json    # corpus_id, counts, hashes, config snapshot

``train.jsonl`` is directly consumable by ``train/train.py``'s
``load_corpus`` (it reads the ``text`` field of each JSONL line).
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from levi.brain.learn_obs import extract_text


class BrainLoopError(Exception):
    """Honest, specific failure from the learning loop."""


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def score_observation(
    rec: Dict[str, Any],
    *,
    min_text_chars: int = 16,
    max_text_chars: int = 8000,
) -> float:
    """Quality score in [0, 1] for one observation record.

    Deterministic and cheap: the loop must not train on garbage, but
    scoring runs over the whole log on every cycle, so it stays O(chars).
    """
    text = extract_text(rec)
    n = len(text)
    if n < min_text_chars or n > max_text_chars:
        return 0.0
    score = 0.5  # survived the basic length filters
    receipt = rec.get("receipt")
    if isinstance(receipt, dict) and receipt.get("ok") is True:
        score += 0.3
    output = rec.get("output")
    if isinstance(output, str) and output.strip():
        score += 0.2
    if rec.get("prompt_truncated"):
        score -= 0.2
    return clamp01(score)


def difficulty_score(text: str, max_text_chars: int = 8000) -> float:
    """Cheap difficulty heuristic in [0, 1]: longer + higher character
    entropy = harder. Used only for curriculum ordering, never as a
    quality judgment."""
    if not text:
        return 0.0
    length_part = clamp01(len(text) / max_text_chars)
    counts: Dict[str, int] = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(text)
    entropy = 0.0
    for c in counts.values():
        p = c / n
        entropy -= p * math.log2(p)
    max_entropy = math.log2(len(counts)) if len(counts) > 1 else 1.0
    entropy_part = clamp01(entropy / max_entropy) if max_entropy > 0 else 0.0
    return clamp01(0.5 * length_part + 0.5 * entropy_part)


def _stable_key(rec: Dict[str, Any]) -> Tuple[str, str]:
    return (str(rec.get("ts", "")), str(rec.get("prompt_sha256", "")))


def _canon(rec: Dict[str, Any]) -> str:
    return json.dumps(rec, sort_keys=True, ensure_ascii=False, default=str)


def corpus_id_for(
    records: List[Dict[str, Any]], config_snapshot: Dict[str, Any]
) -> str:
    """Content id for a corpus build: sha256 over the canonical records +
    the config that shaped them. Same inputs -> same id, always."""
    h = hashlib.sha256()
    h.update(json.dumps(config_snapshot, sort_keys=True, ensure_ascii=False).encode())
    for rec in records:
        h.update(_canon(rec).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()[:16]


def build_corpus(
    records: List[Dict[str, Any]],
    out_dir: Path,
    *,
    seed: int = 1337,
    val_ratio: float = 0.10,
    vocab_chars: Optional[List[str]] = None,
    teacher_weights: Optional[Dict[str, float]] = None,
    min_quality: float = 0.3,
    min_text_chars: int = 16,
    max_text_chars: int = 8000,
    max_copies: int = 8,
    source_path: str = "",
    source_mtime: str = "",
) -> Dict[str, Any]:
    """Build the training corpus. Returns a stats dict and writes
    train.jsonl / val.jsonl / manifest.json into ``out_dir``.

    Raises BrainLoopError with the specific reason when there is nothing
    usable to train on.
    """
    out_dir = Path(out_dir)
    weights = dict(teacher_weights or {})
    config_snapshot = {
        "seed": seed,
        "val_ratio": val_ratio,
        "min_quality": min_quality,
        "min_text_chars": min_text_chars,
        "max_text_chars": max_text_chars,
        "max_copies": max_copies,
        "teacher_weights": {k: weights[k] for k in sorted(weights)},
        "vocab_size": len(vocab_chars) if vocab_chars else None,
    }
    corpus_id = corpus_id_for(sorted(records, key=_stable_key), config_snapshot)
    vocab_set = set(vocab_chars) if vocab_chars else None

    # 1-2. stable order, score, filter
    scored: List[Tuple[float, Dict[str, Any], str]] = []
    n_observed = len(records)
    n_filtered = 0
    for rec in sorted(records, key=_stable_key):
        text = extract_text(rec)
        q = score_observation(
            rec, min_text_chars=min_text_chars, max_text_chars=max_text_chars
        )
        if q < min_quality:
            n_filtered += 1
            continue
        scored.append((q, rec, text))

    # 3. dedupe by text hash — keep the highest-scored copy
    best: Dict[str, Tuple[float, Dict[str, Any], str]] = {}
    order: List[str] = []
    for q, rec, text in scored:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        prev = best.get(digest)
        if prev is None:
            best[digest] = (q, rec, text)
            order.append(digest)
        elif q > prev[0]:
            best[digest] = (q, rec, text)
    n_deduped = len(scored) - len(best)

    # 4. vocab filter + 5. teacher oversampling
    lines: List[Dict[str, Any]] = []
    dropped_chars_total = 0
    n_vocab_dropped = 0
    per_model: Dict[str, int] = {}
    if weights:
        min_w = min(weights.values())
        min_w = min_w if min_w > 0 else 1.0
    else:
        min_w = 1.0
    for digest in order:
        q, rec, text = best[digest]
        model_id = str(rec.get("model_id", "unknown"))
        if vocab_set is not None:
            kept = "".join(ch for ch in text if ch in vocab_set)
            dropped = len(text) - len(kept)
            dropped_chars_total += dropped
            text = kept
            if len(text) < min_text_chars:
                n_vocab_dropped += 1
                continue
        weight = float(weights.get(model_id, 1.0))
        copies = max(1, min(max_copies, round(weight / min_w))) if weight > 0 else 1
        difficulty = difficulty_score(text, max_text_chars=max_text_chars)
        source = {
            "model_id": model_id,
            "arch": str(rec.get("arch", "")),
            "origin": str(rec.get("origin", "")),
            "ts": str(rec.get("ts", "")),
            "prompt_sha256": str(rec.get("prompt_sha256", "")),
            "quality": round(q, 3),
            "difficulty": round(difficulty, 4),
            "weight": weight,
            "copies": copies,
        }
        for _ in range(copies):
            lines.append({"text": text, "source": source})
        per_model[model_id] = per_model.get(model_id, 0) + copies

    if not lines:
        raise BrainLoopError(
            "corpus build: no usable records "
            f"(observed={n_observed} filtered={n_filtered} "
            f"deduped={n_deduped} vocab_dropped={n_vocab_dropped})"
        )

    # 6. seeded shuffle + split (deterministic)
    rng = random.Random(seed)
    idx = list(range(len(lines)))
    rng.shuffle(idx)
    n_val = max(1, int(round(len(lines) * val_ratio))) if len(lines) > 1 else 0
    if n_val >= len(lines):
        n_val = len(lines) - 1
    val_lines = [lines[i] for i in idx[:n_val]]
    train_lines = [lines[i] for i in idx[n_val:]]

    # 7. curriculum: train split easy -> hard (advisory for the v1 trainer;
    #    difficulty is stored per line for curriculum-aware trainers)
    train_lines.sort(key=lambda line: (line["source"]["difficulty"], line["text"]))

    out_dir.mkdir(parents=True, exist_ok=True)
    train_path = out_dir / "train.jsonl"
    val_path = out_dir / "val.jsonl"
    with train_path.open("w", encoding="utf-8") as fh:
        for line in train_lines:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    with val_path.open("w", encoding="utf-8") as fh:
        for line in val_lines:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")

    def _sha256(p: Path) -> str:
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    train_text = "\n\n".join(line["text"] for line in train_lines)
    corpus_charset = sorted(set(train_text))
    manifest = {
        "corpus_id": corpus_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_path": source_path,
        "source_mtime": source_mtime,
        "config": config_snapshot,
        "counts": {
            "observed": n_observed,
            "filtered_quality": n_filtered,
            "deduped": n_deduped,
            "vocab_dropped_records": n_vocab_dropped,
            "dropped_chars": dropped_chars_total,
            "train_lines": len(train_lines),
            "val_lines": len(val_lines),
        },
        "per_model_lines": {k: per_model[k] for k in sorted(per_model)},
        "train_chars": len(train_text),
        "val_chars": sum(len(line["text"]) for line in val_lines),
        "corpus_charset_size": len(corpus_charset),
        "vocab_filter": (
            "incumbent charset enforced" if vocab_set is not None else "none"
        ),
        "curriculum_order": "easy->hard by difficulty heuristic "
        "(advisory: bundled v1 trainer samples uniformly)",
        "files": {
            "train.jsonl": _sha256(train_path),
            "val.jsonl": _sha256(val_path),
        },
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    return {
        "corpus_id": corpus_id,
        "out_dir": str(out_dir),
        "train_path": str(train_path),
        "val_path": str(val_path),
        "manifest_path": str(manifest_path),
        "manifest": manifest,
    }
