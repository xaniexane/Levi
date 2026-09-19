"""Plaiground tailored chat — a chat session loop over a companion.

A :class:`ChatSession` binds to one companion definition and exchanges
turns. Replies are deterministic: derived from the companion's traits,
the chosen tone, the conversation history, and one Echoverse beat per
turn (the same clean taken/not-taken/wild engine the simulator uses).

Tone parameters are whitelisted to non-explicit options; there are no
explicit presets anywhere in this module, and custom tones outside the
allowlist are rejected. All dialogue content is user-driven at runtime;
the reply templates here only reflect, reframe, and branch — they add
no content of their own.

Gate-checked first: creating a session or sending a message with the
gate off raises :class:`levi.plaiground.gate.GateLockedError`.
"""

from __future__ import annotations

import hashlib
import string
from pathlib import Path
from typing import Dict, List, Optional

from levi.organs.echo import run_echo
from levi.plaiground.companions import get_companion
from levi.plaiground.gate import require_adult

# The only tones this surface ships. No explicit presets exist, and
# nothing outside this allowlist is accepted — tone stays non-explicit.
TONES = ("warm", "playful", "witty", "calm", "curious", "poetic", "grounded")

_MAX_MESSAGE_LEN = 4000
_MAX_TURNS = 200
_ALLOWED_CHARS = set(string.printable) - set("\x0b\x0c")


def _validate_message(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("message must be a string, got %s" % type(text).__name__)
    text = text.strip()
    if not text:
        raise ValueError("message must not be empty")
    if len(text) > _MAX_MESSAGE_LEN:
        raise ValueError("message must be at most %d characters" % _MAX_MESSAGE_LEN)
    if any(ch not in _ALLOWED_CHARS for ch in text):
        raise ValueError("message contains disallowed characters")
    return text


def _pick(values: tuple, salt: str, turn: int) -> str:
    digest = hashlib.sha256(("%d|%s" % (turn, salt)).encode()).hexdigest()
    return values[int(digest[:8], 16) % len(values)]


class ChatSession:
    """A gate-checked chat session bound to one companion."""

    def __init__(
        self,
        companion_name: str,
        tone: str = "warm",
        home: Optional[Path] = None,
    ) -> None:
        require_adult(home)
        if tone not in TONES:
            raise ValueError(
                "tone must be one of %s, got %r — Plaiground ships no "
                "other tone presets." % (", ".join(TONES), tone)
            )
        self._home = home
        self.companion: Dict = get_companion(companion_name, home=home)
        self.tone = tone
        self.turns: List[Dict] = []

    @property
    def name(self) -> str:
        return str(self.companion["name"])

    def _reply(self, message: str) -> str:
        turn = len(self.turns) // 2
        traits = self.companion.get("traits", ["steady"]) or ["steady"]
        trait = _pick(tuple(traits), message, turn)
        # One Echoverse beat per turn: the clean engine underneath.
        echo_result = run_echo("%s|%s|%d" % (self.name, message, turn), cycles=1)
        beat = echo_result["branches"][turn % 3]
        # Reflect the user's words back through the companion's voice; the
        # templates reframe and branch only — they contribute no content.
        quoted = message if len(message) <= 160 else message[:157] + "..."
        return (
            "%s [%s, %s] — you said: %r. "
            "Branching [%s]: %s. "
            "Boundaries I keep: %s."
            % (
                self.name,
                self.tone,
                trait,
                quoted,
                beat["kind"],
                beat["label"],
                ", ".join(str(b) for b in self.companion.get("boundaries", [])),
            )
        )

    def say(self, message: str) -> str:
        """Send one user message; returns the companion's reply."""
        require_adult(self._home)
        message = _validate_message(message)
        if len(self.turns) >= _MAX_TURNS * 2:
            raise ValueError("session turn limit reached; start a new session")
        reply = self._reply(message)
        self.turns.append({"role": "user", "text": message})
        self.turns.append({"role": "companion", "text": reply})
        return reply

    def history(self) -> List[Dict]:
        """Copy of the turn history so far."""
        require_adult(self._home)
        return [dict(t) for t in self.turns]

    def close(self) -> Dict:
        """End the session; returns a small transcript summary."""
        require_adult(self._home)
        return {
            "zone": "plaiground",
            "companion": self.name,
            "tone": self.tone,
            "turns": len(self.turns) // 2,
        }
