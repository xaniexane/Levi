"""Void Box platform — dating: profiles, prefs, mutual-opt-in.

FORMED: profile data model + validation, matching preferences, the
like/pass record, and the mutual-opt-in gate (contact is issued ONLY
when both sides have opted in — one-way interest never unlocks contact).

NOT_WIRED (scaffolded, raises NotWiredError): the matching/ranking
algorithm (``match_score``, discovery feed). Compatibility scoring is a
product decision Chauncey has not specified; no placeholder algorithm
ships here.

SI side: every public entry point calls ``require_adult()`` FIRST —
adult-only, default OFF. No explicit content in code, tests, or
docstrings; profiles hold user-driven text at runtime only.

LAWS (declared here, enforced by guards, machine-checked by the
invariant tests — honestly named, never "formally proven")
---------------------------------------------------------------
- L1 — Adult gate: every public entry point calls require_adult()
  first — default OFF, minors hard-locked out; every refusal names its
  remedy. (WIRED)
- L2 — Validated profiles: handles are unique and shaped
  ([a-z0-9._-], 3-32); display names 1-64 chars; bios capped at 500;
  interests capped (20 tags x 32 chars); prefs validated against a
  fixed enum. Bad input fails closed. (WIRED)
- L3 — Mutual-opt-in before contact: a contact grant is issued ONLY
  when both profiles have an active like on each other; one-way likes
  never unlock contact; withdrawn likes break mutuality. (WIRED)
- L4 — No silent matching: the ranking/matching algorithm is NOT_WIRED
  — match_score() raises NotWiredError naming what is missing (a
  Chauncey-specified compatibility model). (NOT_WIRED)
- L5 — Nothing thrown away: unlikes and profile deactivations mark
  state; records persist. (WIRED)

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from levi.voidbox.platform import (
    JsonStore,
    NotMutualError,
    NotWiredError,
    ProfileNotFoundError,
    utcnow,
    valid_handle,
    valid_id,
    valid_text,
)

#: The declared laws, machine-readable.
LAWS = (
    ("L1", "Adult gate: every public entry point calls require_adult() first — default OFF, minors hard-locked out; every refusal names its remedy. (WIRED)"),
    ("L2", "Validated profiles: unique shaped handles; display names 1-64; bios <= 500; interests <= 20x32; prefs against a fixed enum; bad input fails closed. (WIRED)"),
    ("L3", "Mutual-opt-in before contact: contact grants issue ONLY on mutual active likes; one-way likes never unlock contact; withdrawn likes break mutuality. (WIRED)"),
    ("L4", "No silent matching: the ranking/matching algorithm is NOT_WIRED — match_score() raises NotWiredError naming the missing compatibility model. (NOT_WIRED)"),
    ("L5", "Nothing thrown away: unlikes and deactivations mark state; records persist. (WIRED)"),
)

_LOOKING_FOR = ("connection", "friendship", "dating", "community")

_MAX_INTERESTS = 20
_MAX_INTEREST_LEN = 32
_MAX_BIO_LEN = 500


def wiring_report() -> list[tuple[str, bool, str]]:
    """Machine-readable WIRED / NOT_WIRED declaration per capability."""
    return [
        ("adult_gate", True, "require_adult() first on every public entry."),
        ("profile_model", True, "create/update/get with validation."),
        ("matching_prefs", True, "prefs validated against a fixed enum."),
        ("like_pass", True, "one-way like/pass records, withdrawable."),
        ("mutual_opt_in_gate", True, "contact grants only on mutual likes."),
        (
            "match_score",
            False,
            "ranking/matching algorithm: needs a Chauncey-specified "
            "compatibility model; no placeholder ships.",
        ),
        (
            "discovery_feed",
            False,
            "recommendation feed: depends on match_score; not wired.",
        ),
    ]


def _validate_prefs(prefs: object) -> dict:
    if prefs is None:
        return {"looking_for": [], "interests": []}
    if not isinstance(prefs, dict):
        _bad("prefs must be a dict.")
    looking_for = prefs.get("looking_for", [])
    if not isinstance(looking_for, list) or any(
        lf not in _LOOKING_FOR for lf in looking_for
    ):
        _bad(
            "prefs.looking_for must be a list drawn from %s." % (_LOOKING_FOR,)
        )
    interests = prefs.get("interests", [])
    if not isinstance(interests, list) or len(interests) > _MAX_INTERESTS:
        _bad("prefs.interests must be a list of at most %d tags." % _MAX_INTERESTS)
    clean = []
    for tag in interests:
        if not isinstance(tag, str) or not tag.strip():
            _bad("interest tags must be non-empty text.")
        if len(tag.strip()) > _MAX_INTEREST_LEN:
            _bad("interest tag %r exceeds %d chars." % (tag, _MAX_INTEREST_LEN))
        clean.append(tag.strip().lower())
    unknown = set(prefs) - {"looking_for", "interests"}
    if unknown:
        _bad("unknown prefs keys: %s." % sorted(unknown))
    return {"looking_for": list(looking_for), "interests": clean}


def _bad(msg: str):  # fail-closed helper
    from levi.voidbox.platform import PlatformError

    raise PlatformError(msg)


class DatingStore(JsonStore):
    """Dating profiles + mutual-opt-in. Owner-only JSON store."""

    _FILENAME = "dating.json"

    def __init__(self, home: Optional[Path] = None):
        super().__init__(home)

    # -- profiles ------------------------------------------------------

    def create_profile(
        self,
        profile_id: str,
        handle: str,
        display_name: str,
        bio: str = "",
        prefs: Optional[dict] = None,
    ) -> dict:
        """Create a dating profile. Handle must be unique store-wide."""
        self._require_adult()
        profile_id = valid_id(profile_id, "profile_id")
        handle = valid_handle(handle)
        display_name = valid_text(display_name, "display_name", max_len=64)
        bio = valid_text(bio, "bio", max_len=_MAX_BIO_LEN, allow_empty=True)
        clean_prefs = _validate_prefs(prefs)
        data = self._load()
        profiles = data.setdefault("profiles", {})
        if profile_id in profiles:
            _bad("profile %r already exists." % profile_id)
        if any(p["handle"] == handle for p in profiles.values()):
            _bad("handle %r is already taken." % handle)
        profiles[profile_id] = {
            "profile_id": profile_id,
            "handle": handle,
            "display_name": display_name,
            "bio": bio,
            "prefs": clean_prefs,
            "active": True,
            "created_at": utcnow(),
        }
        self._save(data)
        return dict(profiles[profile_id])

    def update_profile(self, profile_id: str, **fields) -> dict:
        """Update display_name / bio / prefs. Handle is immutable."""
        self._require_adult()
        profile_id = valid_id(profile_id, "profile_id")
        allowed = {"display_name", "bio", "prefs", "active"}
        unknown = set(fields) - allowed
        if unknown:
            _bad("cannot update fields: %s." % sorted(unknown))
        data = self._load()
        profile = self._get(data, profile_id)
        if "display_name" in fields:
            profile["display_name"] = valid_text(
                fields["display_name"], "display_name", max_len=64
            )
        if "bio" in fields:
            profile["bio"] = valid_text(
                fields["bio"], "bio", max_len=_MAX_BIO_LEN, allow_empty=True
            )
        if "prefs" in fields:
            profile["prefs"] = _validate_prefs(fields["prefs"])
        if "active" in fields:
            if not isinstance(fields["active"], bool):
                _bad("active must be a bool.")
            profile["active"] = fields["active"]  # marked, never deleted (L5)
        profile["updated_at"] = utcnow()
        self._save(data)
        return dict(profile)

    def get_profile(self, profile_id: str) -> dict:
        """Fetch a profile by id."""
        self._require_adult()
        profile_id = valid_id(profile_id, "profile_id")
        return dict(self._get(self._load(), profile_id))

    @staticmethod
    def _get(data: dict, profile_id: str) -> dict:
        profile = data.get("profiles", {}).get(profile_id)
        if profile is None:
            raise ProfileNotFoundError("no dating profile %r." % profile_id)
        return profile

    # -- likes: one-way interest, withdrawable -------------------------

    def like(self, liker_id: str, liked_id: str) -> dict:
        """Record one-way interest. Does NOT unlock contact (L3)."""
        self._require_adult()
        liker_id = valid_id(liker_id, "liker_id")
        liked_id = valid_id(liked_id, "liked_id")
        if liker_id == liked_id:
            _bad("a profile cannot like itself.")
        data = self._load()
        self._get(data, liker_id)
        liked = self._get(data, liked_id)
        if not liked.get("active", True):
            _bad("profile %r is deactivated." % liked_id)
        likes = data.setdefault("likes", {}).setdefault(liker_id, {})
        likes[liked_id] = {"at": utcnow(), "withdrawn": False}
        self._save(data)
        return {"liker_id": liker_id, "liked_id": liked_id,
                "mutual": self.is_mutual(liker_id, liked_id)}

    def unlike(self, liker_id: str, liked_id: str) -> dict:
        """Withdraw a like. Marked withdrawn, never deleted (L5)."""
        self._require_adult()
        liker_id = valid_id(liker_id, "liker_id")
        liked_id = valid_id(liked_id, "liked_id")
        data = self._load()
        rec = data.get("likes", {}).get(liker_id, {}).get(liked_id)
        if rec is None:
            _bad("no like from %r to %r to withdraw." % (liker_id, liked_id))
        rec["withdrawn"] = True
        rec["withdrawn_at"] = utcnow()
        self._save(data)
        return {"liker_id": liker_id, "liked_id": liked_id, "withdrawn": True}

    # -- mutual-opt-in gate --------------------------------------------

    def is_mutual(self, a_id: str, b_id: str) -> bool:
        """True only when both sides hold an ACTIVE like on each other."""
        self._require_adult()
        data = self._load()
        likes = data.get("likes", {})
        a_likes_b = likes.get(a_id, {}).get(b_id, {})
        b_likes_a = likes.get(b_id, {}).get(a_id, {})
        return bool(
            a_likes_b and not a_likes_b.get("withdrawn")
            and b_likes_a and not b_likes_a.get("withdrawn")
        )

    def mutual_matches(self, profile_id: str) -> list[dict]:
        """Profiles with mutual active likes — the only contactable set."""
        self._require_adult()
        profile_id = valid_id(profile_id, "profile_id")
        data = self._load()
        self._get(data, profile_id)
        out = []
        for other_id, profile in data.get("profiles", {}).items():
            if other_id != profile_id and self.is_mutual(profile_id, other_id):
                out.append(dict(profile))
        return out

    def request_contact(self, a_id: str, b_id: str) -> dict:
        """Issue a contact grant — ONLY on mutual opt-in (L3).

        The grant is a capability token the Messenger worker consumes to
        open a 1:1 thread; it carries no contact details itself (those
        live with the users). One-way interest raises NotMutualError.
        """
        self._require_adult()
        a_id = valid_id(a_id, "a_id")
        b_id = valid_id(b_id, "b_id")
        if not self.is_mutual(a_id, b_id):
            raise NotMutualError(
                "contact refused: %r and %r have not mutually opted in. "
                "Both sides must like each other first." % (a_id, b_id)
            )
        import secrets as _secrets

        return {
            "grant": "contact_" + _secrets.token_hex(8),
            "a_id": a_id,
            "b_id": b_id,
            "mutual": True,
            "issued_at": utcnow(),
        }

    # -- NOT_WIRED ------------------------------------------------------

    def match_score(self, a_id: str, b_id: str) -> float:
        """Compatibility score — NOT_WIRED. No placeholder algorithm
        ships; Chauncey has not specified the compatibility model."""
        self._require_adult()
        raise NotWiredError(
            capability="dating.match_score",
            missing="a Chauncey-specified compatibility model — the "
            "ranking/matching algorithm is not wired; no placeholder "
            "scores are produced.",
        )

    def discovery_feed(self, profile_id: str, limit: int = 20) -> list[dict]:
        """Recommendation feed — NOT_WIRED (depends on match_score)."""
        self._require_adult()
        raise NotWiredError(
            capability="dating.discovery_feed",
            missing="dating.match_score — the discovery feed needs the "
            "matching algorithm first.",
        )
