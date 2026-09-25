"""Wave Pulse engine assets — named content-generation engines.

Each engine is a self-contained prompt spec stored verbatim as a Markdown
asset (Chauncey's own restored material). Engines are offline data: loading
one performs no network calls and touches no live platform API. The creating
agent runs the prompt; Wave Pulse only supplies it with context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

_ENGINES: Dict[str, Dict[str, str]] = {
    "facebook-elite-viral": {
        "file": "facebook_elite_viral.md",
        "label": "Facebook Elite Viral Engine",
        "platforms": "Facebook × X × Reddit × TikTok",
        "kind": "4-platform fused viral post generator",
    },
}


def list_engines() -> List[str]:
    """Engine keys, sorted."""
    return sorted(_ENGINES)


def engine_info(name: str) -> Dict[str, str]:
    """Metadata for an engine; raises KeyError on unknown names."""
    try:
        return dict(_ENGINES[name])
    except KeyError:
        raise KeyError(
            f"unknown engine {name!r}; available: {', '.join(list_engines())}"
        ) from None


def load_engine_prompt(name: str) -> str:
    """Load an engine's prompt spec verbatim. Raises KeyError on unknown."""
    info = engine_info(name)  # validates the name first
    path = Path(__file__).with_name(info["file"])
    return path.read_text(encoding="utf-8")
