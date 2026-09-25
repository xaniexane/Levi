"""Call-time home paths and JSON persistence for the recommender."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

from levi.recommender.model import Goal, Item, check_rating
from levi.recommender.weights import DEFAULT_WEIGHTS, normalize_weights


def home() -> Path:
    return Path(os.path.expanduser("~"))


def store_dir() -> Path:
    return home() / ".levi" / "recommender"


def _path(name: str) -> Path:
    return store_dir() / name


def _read_json(name: str, default):
    try:
        return json.loads(_path(name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(name: str, payload) -> None:
    _path(name).parent.mkdir(parents=True, exist_ok=True)
    _path(name).write_text(json.dumps(payload, indent=1), encoding="utf-8")


def load_items() -> List[Item]:
    items = []
    for raw in _read_json("items.json", []):
        try:
            items.append(Item.from_dict(raw))
        except (KeyError, TypeError, ValueError):
            continue
    return items


def save_items(items: List[Item]) -> None:
    _write_json("items.json", [it.to_dict() for it in items])


def load_goals() -> List[Goal]:
    goals = []
    for raw in _read_json("goals.json", []):
        try:
            goals.append(Goal.from_dict(raw))
        except (KeyError, TypeError, ValueError):
            continue
    return goals


def save_goals(goals: List[Goal]) -> None:
    _write_json("goals.json", [g.to_dict() for g in goals])


def load_ratings() -> Dict[str, List[float]]:
    raw = _read_json("ratings.json", {})
    cleaned: Dict[str, List[float]] = {}
    for item_id, vals in raw.items():
        try:
            cleaned[str(item_id)] = [check_rating(v) for v in vals]
        except (TypeError, ValueError):
            continue
    return cleaned


def save_ratings(ratings: Dict[str, List[float]]) -> None:
    _write_json("ratings.json", ratings)


def load_weights() -> Dict[str, float]:
    try:
        return normalize_weights(_read_json("weights.json", {}))
    except (ValueError, TypeError):
        return dict(DEFAULT_WEIGHTS)


def save_weights(weights: Dict[str, float]) -> Dict[str, float]:
    cleaned = normalize_weights(dict(weights))
    _write_json("weights.json", cleaned)
    return cleaned
