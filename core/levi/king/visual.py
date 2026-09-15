"""Visual checkpoint URLs — string construction only, NEVER the request.

Blueprint §4: for a URL-based image service (reference: Pollinations —
a third-party media provider, not LEVI), King builds the URL string
and stops there. The image resolves lazily if and when a human opens
the URL in a real browser. This keeps King's test suite network-free
by construction: these are pure functions of their arguments (seed
defaults to a stable hash of the prompt).

No ``urllib.request``, no ``socket``, no subprocess — nothing in this
module can touch the network. ``levi king`` surfaces a visual
checkpoint via the returned URL string only.
"""

from __future__ import annotations

import hashlib
import urllib.parse
from typing import Dict, List

# Functional URL scheme for a third-party media provider (reference only —
# the URL must match that provider's scheme to resolve; not LEVI branding).
POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"

_DIM_MIN, _DIM_MAX = 16, 4096


def _seed_for(prompt: str, seed: int | None) -> int:
    if seed is not None:
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError(f"seed must be a non-negative int or None, got {seed!r}")
        return seed
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8]
    return int(digest, 16)


def _dim(value: int, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an int, got {value!r}")
    if not (_DIM_MIN <= value <= _DIM_MAX):
        raise ValueError(
            f"{name} must be between {_DIM_MIN} and {_DIM_MAX}, got {value}"
        )
    return value


def checkpoint_url(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    seed: int | None = None,
    model: str = "flux",
    nologo: bool = True,
) -> str:
    """Build a media-provider image URL (reference URL scheme). Pure function; no HTTP."""
    if not isinstance(prompt, str):
        raise ValueError(f"checkpoint_url needs a string prompt, got {type(prompt).__name__}")
    clean = prompt.strip()
    if not clean:
        raise ValueError("checkpoint_url needs a non-empty prompt")
    width = _dim(width, name="width")
    height = _dim(height, name="height")
    if not isinstance(model, str) or not model.strip():
        raise ValueError(f"model must be a non-empty string, got {model!r}")
    encoded = urllib.parse.quote(clean, safe="")
    params = (
        f"width={width}&height={height}"
        f"&seed={_seed_for(clean, seed)}&model={urllib.parse.quote(model.strip(), safe='')}"
    )
    if nologo:
        params += "&nologo=true"
    return f"{POLLINATIONS_BASE}/{encoded}?{params}"


def checkpoint_urls(prompts: Dict[str, str], **kwargs) -> Dict[str, str]:
    """Batch builder: {checkpoint_name: prompt} -> {name: url}."""
    if not isinstance(prompts, dict):
        raise ValueError(
            f"checkpoint_urls needs a dict of name->prompt, got {type(prompts).__name__}"
        )
    for name, p in prompts.items():
        if not isinstance(name, str) or not isinstance(p, str):
            raise ValueError(
                "checkpoint_urls keys and prompts must be strings, "
                f"got {name!r}: {type(p).__name__}"
            )
    return {name: checkpoint_url(p, **kwargs) for name, p in prompts.items()}


def visual_checkpoint_for_ledger(summary: Dict[str, object]) -> List[Dict[str, str]]:
    """Deterministic checkpoint URLs describing ledger state.

    Used by ``levi king status --visual``: one URL per rank milestone
    reached, so an operator can open a visual receipt of progression in
    a real browser. Still just strings — no fetch.
    """
    rank = str(summary.get("rank", "D2")) if isinstance(summary, dict) else "D2"
    words = summary.get("total_words", 0) if isinstance(summary, dict) else 0
    banks = summary.get("total_banks", 0) if isinstance(summary, dict) else 0
    try:
        words = max(0, int(words or 0))
        banks = max(0, int(banks or 0))
    except (TypeError, ValueError):
        words, banks = 0, 0
    prompt = (
        f"Abstract literary sigil for rank {rank}: {words} words banked "
        f"across {banks} continuity units, dark ink on parchment, "
        "minimalist emblem, no text"
    )
    return [
        {
            "name": f"king-{rank.lower()}",
            "prompt": prompt,
            "url": checkpoint_url(prompt, seed=_seed_for(prompt, None)),
        }
    ]
