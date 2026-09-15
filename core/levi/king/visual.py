"""Visual checkpoint URLs — string construction only, NEVER the request.

Blueprint §4: for a URL-based image service (Pollinations-style), King
builds the URL string and stops there. The image resolves lazily if and
when a human opens the URL in a real browser. This keeps King's test
suite network-free by construction: these are pure functions of their
arguments (seed defaults to a stable hash of the prompt).

No ``urllib.request``, no ``socket``, no subprocess — nothing in this
module can touch the network. ``levi king`` surfaces a visual
checkpoint via the returned URL string only.
"""

from __future__ import annotations

import hashlib
import urllib.parse
from typing import Dict, List

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"


def _seed_for(prompt: str, seed: int | None) -> int:
    if seed is not None:
        return int(seed)
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8]
    return int(digest, 16)


def checkpoint_url(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    seed: int | None = None,
    model: str = "flux",
    nologo: bool = True,
) -> str:
    """Build a Pollinations-style image URL. Pure function; no HTTP."""
    clean = (prompt or "").strip()
    if not clean:
        raise ValueError("checkpoint_url needs a non-empty prompt")
    encoded = urllib.parse.quote(clean, safe="")
    params = (
        f"width={int(width)}&height={int(height)}"
        f"&seed={_seed_for(clean, seed)}&model={urllib.parse.quote(str(model), safe='')}"
    )
    if nologo:
        params += "&nologo=true"
    return f"{POLLINATIONS_BASE}/{encoded}?{params}"


def checkpoint_urls(prompts: Dict[str, str], **kwargs) -> Dict[str, str]:
    """Batch builder: {checkpoint_name: prompt} -> {name: url}."""
    return {name: checkpoint_url(p, **kwargs) for name, p in prompts.items()}


def visual_checkpoint_for_ledger(summary: Dict[str, object]) -> List[Dict[str, str]]:
    """Deterministic checkpoint URLs describing ledger state.

    Used by ``levi king status --visual``: one URL per rank milestone
    reached, so an operator can open a visual receipt of progression in
    a real browser. Still just strings — no fetch.
    """
    rank = str(summary.get("rank", "D2"))
    words = int(summary.get("total_words", 0) or 0)
    banks = int(summary.get("total_banks", 0) or 0)
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
