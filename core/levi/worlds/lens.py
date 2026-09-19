"""The seven worlds: definitions, classification, check-ins."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

# Identity first — the ordering law: World 7 is not the last world.
WORLDS: Dict[str, Dict[str, str]] = {
    "identity": {
        "name": "Identity World",
        "domain": "who you are across all worlds and all eras",
        "role": "the core — source of all other worlds",
    },
    "physical": {
        "name": "Physical World",
        "domain": "home, work, errands, body, physical tasks",
        "role": "grounds identity in reality",
    },
    "digital": {
        "name": "Digital World",
        "domain": "files, apps, accounts, devices",
        "role": "unifies all digital responsibilities",
    },
    "internal": {
        "name": "Internal World",
        "domain": "stress, energy, mood, cognitive load",
        "role": "enables stress-adaptive responses",
    },
    "social": {
        "name": "Social World",
        "domain": "relationships, communication, social identity",
        "role": "maintains social coherence across contexts",
    },
    "opportunity": {
        "name": "Opportunity World",
        "domain": "goals, paths, future states, income",
        "role": "trajectory identity — where you are going",
    },
    "frontier": {
        "name": "Frontier World",
        "domain": "augmented layers, spatial identity, hybrid environments",
        "role": "the frontier layer — physical meets digital",
    },
}

_KEYWORDS: Dict[str, List[str]] = {
    "identity": [
        "identity",
        "values",
        "purpose",
        "legacy",
        "who i am",
        "principles",
        "creed",
    ],
    "physical": [
        "home",
        "errand",
        "grocer",
        "clean",
        "repair",
        "health",
        "doctor",
        "exercise",
        "sleep",
        "house",
        "car",
        "yard",
    ],
    "digital": [
        "file",
        "app",
        "account",
        "password",
        "email",
        "backup",
        "phone",
        "laptop",
        "repo",
        "server",
        "browser",
    ],
    "internal": [
        "stress",
        "tired",
        "energy",
        "mood",
        "anxiet",
        "overwhelm",
        "burnout",
        "rest",
        "calm",
        "focus",
    ],
    "social": [
        "friend",
        "family",
        "call",
        "text",
        "message",
        "meet",
        "party",
        "relationship",
        "people",
        "mom",
        "dad",
    ],
    "opportunity": [
        "job",
        "interview",
        "application",
        "goal",
        "income",
        "gig",
        "career",
        "money",
        "future",
        "plan",
        "business",
    ],
    "frontier": ["ar", "vr", "spatial", "augmented", "hologram", "metaverse", "xr"],
}


def classify(text: str) -> List[str]:
    """Rule-based: which worlds does this text touch? Ordered identity-first."""
    low = text.lower()
    hits = [w for w, kws in _KEYWORDS.items() if any(k in low for k in kws)]
    return hits


def _checkin_path() -> Path:
    base = Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
    return base / "worlds" / "checkins.jsonl"


def checkin(world: str, note: str) -> Dict[str, str]:
    """Log a note against one world. Unknown world ids are refused."""
    if world not in WORLDS:
        raise ValueError(f"unknown world {world!r}; choose from {sorted(WORLDS)}")
    p = _checkin_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    entry = {"world": world, "note": note, "ts": datetime.now(timezone.utc).isoformat()}
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return entry


def recent(world: str, limit: int = 10) -> List[Dict[str, str]]:
    """Latest check-ins for a world, newest first."""
    p = _checkin_path()
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("world") == world:
            rows.append(row)
    return rows[-limit:][::-1]
