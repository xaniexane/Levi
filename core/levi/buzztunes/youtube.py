"""YouTube seam — the honest integration point for real playback.

The Buzz Tunes engine orders, queues, receipts, and scores; it does NOT
render audio (see engine.py). This module is the clean seam where real
playback will land later. It is deliberately NOT a stub that pretends:

  * ``configured()`` reports False until a real YouTube linkage exists.
  * ``play()`` / ``search()`` raise :class:`YouTubeNotConfigured` with
    a plain-speech explanation — never a silent no-op, never faked audio.
  * The future contract is documented here: access arrives via the
    Secure Vault (never pasted, never stored in files), and playback
    goes through the provider-universal interface (providers.py), so the
    core never imports a YouTube SDK or API client (law L1 holds).

Chauncey's ruling (2026-09-27): YouTube, not Spotify. The Spotify seam
was removed-and-stored (stored/2026-09-27-buzztunes-spotify-seam/).

What "configured" will mean when Chauncey links YouTube:
  1. His YouTube access is connected (his hands — OAuth/API key, Secure
     Vault holds it).
  2. A ``youtube`` provider plugin is registered in ProviderRegistry
     speaking the ProviderPlugin interface (search/resolve).
  3. This seam's ``play()`` hands the provider's audio URL/ref to the
     phone's audio sink.

Until then: ``buzz play`` shows and queues — real audio waits on him.
"""

from __future__ import annotations

from dataclasses import dataclass  # noqa: F401  (kept for seam parity)
from typing import Dict, List

from .providers import Track


class YouTubeNotConfigured(RuntimeError):
    """Raised when playback is attempted without a linked YouTube access."""


def configured() -> bool:
    """Is real YouTube playback available? Honest answer: not yet."""
    return False


def status() -> Dict:
    return {
        "configured": False,
        "needs": [
            "Chauncey links his YouTube access (his hands, via Secure Vault)",
            "a 'youtube' ProviderPlugin registered (search/resolve)",
            "phone audio sink wired to the provider's audio ref",
        ],
        "note": ("until then, 'buzz play' queues and shows the play order; "
                 "no audio is faked"),
    }


def play(track: Track) -> Dict:
    """Play a track through YouTube. Raises until configured."""
    raise YouTubeNotConfigured(
        f"can't play {track.artist} — {track.title} yet: YouTube isn't "
        f"linked. {status()['note']}")


def search(query: str, limit: int = 25) -> List[Track]:
    """Search YouTube's catalog. Raises until configured."""
    raise YouTubeNotConfigured(
        f"can't search YouTube for {query!r} yet: YouTube isn't linked.")
