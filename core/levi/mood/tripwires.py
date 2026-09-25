"""MOOD tripwires — the booby traps. Observation and containment only (L5).

Three trap kinds:

CANARY_TOKEN — fake credentials the decoy hands out. Unusable by
    construction: they are fixed, published, documented-as-fake strings
    that no real system will ever accept. A session that tries to *use*
    one (redeems, replays, or exfiltrates it) trips.

TRIPWIRE_PATH — fake sensitive-looking paths (``/vault``, ``/admin/keys``,
    ``/.git/config``). Reading or probing them returns canned fake content
    AND trips. Real files with those names are never touched (L2).

SNOOP_PATTERN — request shapes of a snooping session: prompt-injection
    probes, demands for system internals, credential harvesting phrasing.
    Matching trips.

All evaluation is deterministic: same input, same trip, every time (L8).
Nothing here damages anyone or anything (L5). Trips are handed to the
receipt writer and the alert queue by the caller — this module only
*detects*; :mod:`levi.mood.receipts` and :mod:`levi.mood.alert` record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

__all__ = [
    "CANARY_TOKENS",
    "SNOOP_PATTERNS",
    "TRIPWIRE_PATHS",
    "TripEvent",
    "TripwireKind",
    "TripwireRegistry",
]

#: Fake credentials the decoy hands out. Fixed, documented-as-fake,
#: unusable-by-construction. Every one carries the CANARY marker.
CANARY_TOKENS: Dict[str, str] = {
    "levi_live_key": "levi_live_key_CANARY_MOOD_0000_fake",
    "session_token": "sess_CANARY_MOOD_0000_fake_token",
    "api_key": "sk-mood-CANARY-0000-fake-key",
    "db_password": "mood_CANARY_0000_fake_password",
}

#: Paths that look sensitive and exist only inside the decoy. Probing or
#: reading any of them trips the wire. The decoy never reads real files
#: of these names (L2); the content served is canned.
TRIPWIRE_PATHS: List[str] = [
    "/vault",
    "/vault/export",
    "/vault/keys",
    "/admin",
    "/admin/keys",
    "/admin/users",
    "/.git/config",
    "/.env",
    "/etc/shadow",
    "system_prompt",
    "internal_instructions",
]

#: Request shapes of a snooping session. A match trips.
SNOOP_PATTERNS: List[str] = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"reveal\s+(your\s+)?system\s+prompt",
    r"show\s+me\s+(your\s+)?(system|internal)\s+(prompt|instructions)",
    r"disregard\s+(your\s+)?(rules|safety|guidelines)",
    r"(export|dump|exfiltrate).{0,40}(key|secret|password|credential|vault)",
    r"(give|send)\s+me\s+(your\s+)?(api\s+key|private\s+key|password|secret)",
    r"ssh\s+",
    r"private\s+key",
    r"jailbreak",
    r"developer\s+mode",
]

_COMPILED: List[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in SNOOP_PATTERNS]


class TripwireKind(Enum):
    """The three booby-trap kinds (L5)."""

    CANARY_TOKEN = "canary_token"
    TRIPWIRE_PATH = "tripwire_path"
    SNOOP_PATTERN = "snoop_pattern"


@dataclass(frozen=True)
class TripEvent:
    """One tripped wire. Immutable; receipts and alerts are built from this."""

    kind: TripwireKind
    session_id: str
    detail: str
    seq: int = 0

    def to_dict(self) -> Dict[str, object]:
        return {
            "kind": self.kind.value,
            "session_id": self.session_id,
            "detail": self.detail,
            "seq": self.seq,
        }


class TripwireRegistry:
    """Deterministic evaluator for the three trap kinds (L8).

    ``evaluate(action)`` returns a :class:`TripEvent` on the first
    matching trap, else ``None``. Evaluation order is fixed:
    canary tokens, then tripwire paths, then snoop patterns.
    """

    def __init__(self) -> None:
        self._canaries = dict(CANARY_TOKENS)
        self._paths = list(TRIPWIRE_PATHS)
        self._patterns = list(_COMPILED)
        self._seen: List[TripEvent] = []

    # ------------------------------------------------------------------
    # Trap definitions — readable, declared, nothing hidden (L9).
    # ------------------------------------------------------------------

    @property
    def canary_tokens(self) -> Dict[str, str]:
        return dict(self._canaries)

    @property
    def tripwire_paths(self) -> List[str]:
        return list(self._paths)

    def add_tripwire_path(self, path: str) -> None:
        """Register one more fake sensitive-looking path. Decoy-local only."""
        if path not in self._paths:
            self._paths.append(path)

    # ------------------------------------------------------------------
    # Evaluation — deterministic, observation-only (L5, L8).
    # ------------------------------------------------------------------

    def evaluate(self, session_id: str, action: str) -> Optional[TripEvent]:
        """Return a TripEvent if ``action`` trips any wire, else None."""
        lowered = action.lower()

        # 1. Canary tokens — the session tried to use or move a fake credential.
        for name, token in self._canaries.items():
            if token.lower() in lowered and "canary" in lowered:
                # Merely seeing the token in decoy output is normal; trips
                # only when the session acts on it: redeem/replay/export/use.
                if re.search(
                    r"\b(use|redeem|replay|export|send|copy|steal|exfil)\b",
                    lowered,
                ):
                    return self._trip(
                        session_id, TripwireKind.CANARY_TOKEN,
                        "session acted on canary token %r" % name,
                    )

        # 2. Tripwire paths — probing or reading a fake sensitive path.
        for path in self._paths:
            if path.lower() in lowered:
                return self._trip(
                    session_id, TripwireKind.TRIPWIRE_PATH,
                    "session probed tripwire path %r" % path,
                )

        # 3. Snoop patterns — request shapes of a snooping session.
        for pattern in self._patterns:
            if pattern.search(action):
                return self._trip(
                    session_id, TripwireKind.SNOOP_PATTERN,
                    "session matched snoop pattern %r" % pattern.pattern,
                )

        return None

    def _trip(
        self, session_id: str, kind: TripwireKind, detail: str
    ) -> TripEvent:
        event = TripEvent(
            kind=kind,
            session_id=session_id,
            detail=detail,
            seq=len(self._seen),
        )
        self._seen.append(event)
        return event

    @property
    def trips(self) -> List[TripEvent]:
        return list(self._seen)
