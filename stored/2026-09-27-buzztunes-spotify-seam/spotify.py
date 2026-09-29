"""Spotify seam — the honest integration point for real playback.

The Buzz Tunes engine orders, queues, receipts, and scores; it does NOT
render audio (see engine.py). This module is the clean seam where real
playback will land later. It is deliberately NOT a stub that pretends:

  * ``configured()`` reports False until a real Spotify linkage exists.
  * ``play()`` / ``search()`` raise :class:`SpotifyNotConfigured` with
    a plain-speech explanation — never a silent no-op, never faked audio.
  * The future contract is documented here: credentials arrive via the
    Secure Vault (never pasted, never stored in files), and playback
    goes through the provider-universal interface (providers.py), so the
    core never imports a Spotify SDK (law L1 holds).

What "configured" will mean when Chauncey links his account:
  1. His Spotify account is connected (his hands — OAuth on Spotify).
  2. A ``spotify`` provider plugin is registered in ProviderRegistry
     speaking the ProviderPlugin interface (search/resolve).
  3. This seam's ``play()`` hands the provider's audio URL/ref to the
     phone's audio sink.

Until then: ``buzz play`` shows and queues — real audio waits on him.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .providers import Track


class SpotifyNotConfigured(RuntimeError):
    """Raised when playback is attempted without a linked Spotify account."""


def configured() -> bool:
    """Is real Spotify playback available? Honest answer: not yet."""
    return False


def status() -> Dict:
    return {
        "configured": False,
        "needs": [
            "Chauncey links his Spotify account (OAuth, his hands)",
            "a 'spotify' ProviderPlugin registered (search/resolve)",
            "phone audio sink wired to the provider's audio ref",
        ],
        "note": ("until then, 'buzz play' queues and shows the play order; "
                 "no audio is faked"),
    }


def play(track: Track) -> Dict:
    """Play a track through Spotify. Raises until configured."""
    raise SpotifyNotConfigured(
        f"can't play {track.artist} — {track.title} yet: Spotify isn't "
        f"linked. {status()['note']}")


def search(query: str, limit: int = 25) -> List[Track]:
    """Search Spotify's catalog. Raises until configured."""
    raise SpotifyNotConfigured(
        f"can't search Spotify for {query!r} yet: Spotify isn't linked.")
