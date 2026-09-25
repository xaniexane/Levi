"""Teachback verification: is the taught material represented in the data?

Teachback is a *data-side* check, never a capability claim. Given a probe
set (synthetic fixtures in ``levi.teach.probes``: topic + keywords), it
measures how many probes have their vocabulary covered by the prepared
training texts: a probe is "covered" when at least ``threshold`` of its
keywords appear (case-insensitive substring on word-normalized text) in
at least one training doc.

A probe set passing teachback means the prepared data *contains* the
material's vocabulary. It says nothing about what a model trained on the
data can do. Reports state this explicitly.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from levi.teach.probes import PROBES, Probe

__all__ = [
    "coverage",
    "teachback_report",
    "TeachbackError",
]

_WS_RE = re.compile(r"\s+")


class TeachbackError(RuntimeError):
    """Teachback could not run (missing data or probes)."""


def _norm(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").lower())


def coverage(
    texts: Iterable[str],
    probes: Iterable[Probe | dict] | None = None,
    *,
    threshold: float = 0.5,
) -> dict:
    """Keyword coverage of ``texts`` per probe.

    Returns ``{"probes": [...], "n_probes", "n_covered", "coverage",
    "threshold"}``. Each probe row carries ``matched`` keywords.
    """
    if not 0.0 < threshold <= 1.0:
        raise TeachbackError(f"threshold must be in (0, 1], got {threshold!r}")
    probes = list(PROBES if probes is None else probes)
    if not probes:
        raise TeachbackError("no probes supplied")
    normed = [_norm(t) for t in texts]
    rows = []
    for p in probes:
        if isinstance(p, dict):
            pid, topic = p.get("id", "?"), p.get("topic", "?")
            keywords = [str(k) for k in p.get("keywords", [])]
        else:
            pid, topic, keywords = p.id, p.topic, list(p.keywords)
        kw = [k.lower().strip() for k in keywords if str(k).strip()]
        if not kw:
            continue
        matched = [k for k in kw if any(k in t for t in normed)]
        rows.append(
            {
                "id": pid,
                "topic": topic,
                "keywords": len(kw),
                "matched": len(matched),
                "coverage": round(len(matched) / len(kw), 3),
                "covered": (len(matched) / len(kw)) >= threshold,
                "missing": [k for k in kw if k not in matched],
            }
        )
    covered = sum(1 for r in rows if r["covered"])
    return {
        "probes": rows,
        "n_probes": len(rows),
        "n_covered": covered,
        "coverage": round(covered / len(rows), 3) if rows else 0.0,
        "threshold": threshold,
    }


def teachback_report(
    prepared_dir: str | Path,
    *,
    probes: Iterable[Probe | dict] | None = None,
    threshold: float = 0.5,
    split: str = "train",
) -> dict:
    """Run teachback against a ``teach prepare`` output directory.

    Reads ``corpora/<split>.jsonl``. Returns the coverage dict plus an
    explicit data-side disclaimer.
    """
    d = Path(prepared_dir)
    corpus_file = d / "corpora" / f"{split}.jsonl"
    if not corpus_file.is_file():
        raise TeachbackError(f"no prepared {split} corpus at {corpus_file}")
    texts: list[str] = []
    for line in corpus_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("text"), str):
            texts.append(obj["text"])
    if not texts:
        raise TeachbackError(f"{corpus_file} holds no texts")
    result = coverage(texts, probes, threshold=threshold)
    result["split"] = split
    result["n_texts"] = len(texts)
    result["disclaimer"] = (
        "Data-side check only: coverage means the prepared training texts "
        "contain the probe vocabulary. It is NOT a claim that a model "
        "trained on this data learned, understands, or can answer anything."
    )
    return result
