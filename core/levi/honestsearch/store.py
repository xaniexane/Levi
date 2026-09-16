"""Call-time home paths and weight persistence for honestsearch."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

from levi.honestsearch.index import InvertedIndex
from levi.honestsearch.rank import DEFAULT_WEIGHTS, normalize_weights


def home() -> Path:
    return Path(os.path.expanduser("~"))


def store_dir() -> Path:
    return home() / ".levi" / "honestsearch"


def index_path() -> Path:
    return store_dir() / "index.json"


def weights_path() -> Path:
    return store_dir() / "weights.json"


def report_path() -> Path:
    return store_dir() / "crawl_report.jsonl"


def load_index() -> InvertedIndex:
    return InvertedIndex.load(index_path())


def save_index(index: InvertedIndex) -> None:
    index.save(index_path())


def load_weights() -> Dict[str, float]:
    try:
        raw = weights_path().read_text(encoding="utf-8")
        return normalize_weights(json.loads(raw))
    except (OSError, ValueError):
        return dict(DEFAULT_WEIGHTS)


def save_weights(weights: Dict[str, float]) -> Dict[str, float]:
    cleaned = normalize_weights(dict(weights))
    weights_path().parent.mkdir(parents=True, exist_ok=True)
    weights_path().write_text(json.dumps(cleaned, indent=1), encoding="utf-8")
    return cleaned


def append_report(report: Dict) -> None:
    report_path().parent.mkdir(parents=True, exist_ok=True)
    with report_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")
