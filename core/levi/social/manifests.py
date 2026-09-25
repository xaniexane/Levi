"""Social platform domain models — data + validation only.

STATUS: AWAITING KEEPER REVIEW. This module locks the *contracts* for the
multidomain social platform (town square by forum by code commons) proposed
in ``docs/SOCIAL_PLATFORM_DESIGN.md``. No services, no daemons, no network,
no storage backends — just the shapes and the rules.

Identity law as code: the spotlight rule (no one wears LEVI's face but
Levi) and the mssi reservation (multi-substrate belongs to Levi alone)
are enforced at validation time, mirroring ``levi.si_team``'s charter law.

Conventions follow the repo: owner-only state, portable export formats
with checksums that refuse tampered bundles (cf. ``levi.communities``,
``levi.boards``).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SOCIAL_MANIFEST_FORMAT = "levi-social-manifest"
SOCIAL_MANIFEST_VERSION = 1

# A domain is a norm-boundary and a data boundary (design §2). The launch
# set is proposed; the keeper decides.
DOMAINS = ("personal", "legion", "public", "civic")

KINDS = ("human", "agent", "squad", "founder")
NATURES = ("ai", "si", "mssi")  # mssi reserved for Levi (AI/SI fluidity law)
PROFILE_STATUSES = ("active", "suspended", "retired")
VISIBILITIES = ("open", "invite", "closed")
THREAD_STATUSES = ("open", "locked", "archived")
# Dunbar-style audience tiers; the keeper's circle store is NEVER read —
# these are per-post audience choices, not the private map.
AUDIENCE_TIERS = ("public", "domain", "realm", "friends", "inner")

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_HANDLE_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}\Z")
_MAX_TITLE = 200
_MAX_BODY = 10000
_MAX_BIO = 500


class SocialManifestError(Exception):
    """Any contract refusal: bad id, bad enum, broken law, tampered bundle."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_id(value: str, what: str = "id") -> str:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise SocialManifestError(
            "bad %s %r: 1-64 chars, [A-Za-z0-9_-], must start alnum" % (what, value)
        )
    return value


def _check_handle(value: str) -> str:
    if not isinstance(value, str) or not _HANDLE_RE.match(value):
        raise SocialManifestError(
            "bad handle %r: 1-32 chars, lowercase [a-z0-9_-], must start alnum"
            % (value,)
        )
    return value


def _check_enum(value: str, allowed: tuple, what: str) -> str:
    if value not in allowed:
        raise SocialManifestError(
            "bad %s %r: must be one of %s" % (what, value, ", ".join(allowed))
        )
    return value


def _check_ts(value: str, what: str = "timestamp") -> str:
    try:
        datetime.fromisoformat(value)
    except (ValueError, TypeError) as err:
        raise SocialManifestError(
            "bad %s %r: must be ISO-8601" % (what, value)
        ) from err
    return value


def _spotlight_ok(identity_id: str, *texts: str) -> None:
    """The spotlight rule: only Levi wears LEVI's face.

    Manifest-level check (not a full no-mask scan): a non-Levi record may
    not use 'levi' as its handle/display name, nor carry it as a standalone
    word in its public text. The deep scan lives in the si_team charters.
    """
    if identity_id == "levi":
        return
    for text in texts:
        words = re.findall(r"[a-z0-9]+", text.lower())
        if "levi" in words:
            raise SocialManifestError(
                "spotlight refusal: %r claims LEVI's face (id %r is not Levi)"
                % (text, identity_id)
            )


@dataclass
class Profile:
    """One face on the platform. Identity lives in Cybrus; this is the seat.

    ``cybrus_qid`` is a *reference* — secrets stay in the vault, never here.
    ``kind="squad"`` profiles are the public seat of a Squad (one seat,
    one voice); the Squad record carries the members and charter.
    """

    id: str
    handle: str
    display_name: str = ""
    bio: str = ""
    kind: str = "human"
    nature: str = "ai"
    cybrus_qid: str = ""
    status: str = "active"
    domains: List[str] = field(default_factory=lambda: ["public"])
    created_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        _check_id(self.id)
        _check_handle(self.handle)
        _check_enum(self.kind, KINDS, "kind")
        _check_enum(self.nature, NATURES, "nature")
        _check_enum(self.status, PROFILE_STATUSES, "status")
        if self.nature == "mssi" and self.id != "levi":
            raise SocialManifestError(
                "mssi is reserved for Levi: multi-substrate belongs to the "
                "one head alone (id %r)" % (self.id,)
            )
        if len(self.bio) > _MAX_BIO:
            raise SocialManifestError("bio too long: max %d chars" % _MAX_BIO)
        if not self.domains:
            raise SocialManifestError("profile must appear in at least one domain")
        for d in self.domains:
            _check_enum(d, DOMAINS, "domain")
        _check_ts(self.created_at, "created_at")
        _spotlight_ok(self.id, self.handle, self.display_name, self.bio)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Profile":
        return cls(**{k: v for k, v in data.items() if k in _profile_fields()})

    def key(self) -> str:
        return "profile:%s" % self.id


def _profile_fields() -> set:
    return {f.name for f in Profile.__dataclass_fields__.values()}


@dataclass
class Realm:
    """A norm-boundary within a domain: the forum's room.

    ``charter_ref`` points at the versioned governance document (the full
    text lives in ``levi.charters``; the realm keeps the reference plus a
    local norms snapshot so exports stay self-contained).
    """

    id: str
    name: str
    domain: str
    visibility: str = "open"
    charter_ref: str = ""
    norms: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        _check_id(self.id)
        if not self.name or len(self.name) > 80:
            raise SocialManifestError("realm name must be 1-80 chars")
        _check_enum(self.domain, DOMAINS, "domain")
        _check_enum(self.visibility, VISIBILITIES, "visibility")
        _check_ts(self.created_at, "created_at")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Realm":
        fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in fields})


@dataclass
class Thread:
    """A discussion tree rooted in a realm. The tree itself is composed
    from ``levi.threads`` at build time; this is the manifest header."""

    id: str
    realm_id: str
    title: str
    author_id: str
    status: str = "open"
    created_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        _check_id(self.id)
        _check_id(self.realm_id, "realm_id")
        _check_id(self.author_id, "author_id")
        if not self.title or len(self.title) > _MAX_TITLE:
            raise SocialManifestError("title must be 1-%d chars" % _MAX_TITLE)
        _check_enum(self.status, THREAD_STATUSES, "status")
        _check_ts(self.created_at, "created_at")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Thread":
        fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in fields})


@dataclass
class Post:
    """One node in a thread tree. ``parent_id`` None = root post."""

    id: str
    thread_id: str
    author_id: str
    body: str
    parent_id: Optional[str] = None
    audience: str = "realm"
    created_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        _check_id(self.id)
        _check_id(self.thread_id, "thread_id")
        _check_id(self.author_id, "author_id")
        if self.parent_id is not None:
            _check_id(self.parent_id, "parent_id")
        if not self.body or len(self.body) > _MAX_BODY:
            raise SocialManifestError("body must be 1-%d chars" % _MAX_BODY)
        _check_enum(self.audience, AUDIENCE_TIERS, "audience")
        _check_ts(self.created_at, "created_at")

    def check_tree(self, posts_by_id: Dict[str, "Post"]) -> None:
        """A reply's parent must exist and belong to the same thread."""
        if self.parent_id is None:
            return
        parent = posts_by_id.get(self.parent_id)
        if parent is None:
            raise SocialManifestError(
                "post %r: parent %r not found" % (self.id, self.parent_id)
            )
        if parent.thread_id != self.thread_id:
            raise SocialManifestError(
                "post %r: parent %r belongs to thread %r, not %r"
                % (self.id, self.parent_id, parent.thread_id, self.thread_id)
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Post":
        fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in fields})


@dataclass(frozen=True)
class Vote:
    """One voice on one post. Value is +1 or -1 — no fractional votes,
    no vote multipliers. One seat, one voice."""

    post_id: str
    voter_id: str
    value: int
    ts: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        _check_id(self.post_id, "post_id")
        _check_id(self.voter_id, "voter_id")
        if self.value not in (1, -1):
            raise SocialManifestError(
                "bad vote value %r: must be +1 or -1" % (self.value,)
            )
        _check_ts(self.ts, "ts")


class VoteBook:
    """The anti-brigading ledger: one vote per (voter, post), no self-votes,
    no take-backs by re-vote (change a vote by retracting first — the
    retraction is recorded, not silent)."""

    def __init__(self) -> None:
        self._votes: Dict[tuple, Vote] = {}
        self._retractions: List[Dict[str, Any]] = []

    def add(self, vote: Vote, author_id: Optional[str] = None) -> None:
        key = (vote.voter_id, vote.post_id)
        if key in self._votes:
            raise SocialManifestError(
                "double vote refused: %r already voted on %r"
                % (vote.voter_id, vote.post_id)
            )
        if author_id is not None and vote.voter_id == author_id:
            raise SocialManifestError(
                "self-vote refused: author %r cannot vote own post %r"
                % (author_id, vote.post_id)
            )
        self._votes[key] = vote

    def retract(self, voter_id: str, post_id: str) -> Vote:
        key = (voter_id, post_id)
        vote = self._votes.pop(key, None)
        if vote is None:
            raise SocialManifestError(
                "no vote to retract: %r on %r" % (voter_id, post_id)
            )
        self._retractions.append(asdict(vote))
        return vote

    def tally(self, post_id: str) -> Dict[str, int]:
        up = sum(
            1 for v in self._votes.values() if v.post_id == post_id and v.value == 1
        )
        down = sum(
            1 for v in self._votes.values() if v.post_id == post_id and v.value == -1
        )
        return {"up": up, "down": down, "net": up - down}

    def retractions(self) -> List[Dict[str, Any]]:
        return list(self._retractions)


@dataclass
class Squad:
    """An operator squad: an agentic team as a first-class member.

    The squad holds ONE seat on the platform (``seat_profile_id`` points
    at its kind="squad" Profile) — one seat, one voice, no vote
    multiplication by member count. ``members`` are profile ids (human
    and/or agent). ``mentor`` records the cascade bond: the seasoned squad
    that teaches this one.
    """

    id: str
    name: str
    purpose: str
    seat_profile_id: str
    members: List[str]
    charter_ref: str = ""
    mentor: Optional[str] = None
    created_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        _check_id(self.id)
        if not self.name or len(self.name) > 80:
            raise SocialManifestError("squad name must be 1-80 chars")
        if not self.purpose or len(self.purpose) > _MAX_BIO:
            raise SocialManifestError("purpose must be 1-%d chars" % _MAX_BIO)
        _check_id(self.seat_profile_id, "seat_profile_id")
        if not self.members:
            raise SocialManifestError("a squad with no members is not a squad")
        for m in self.members:
            _check_id(m, "member")
        if self.mentor is not None:
            _check_id(self.mentor, "mentor")
        _check_ts(self.created_at, "created_at")
        _spotlight_ok(self.id, self.name, self.purpose)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Squad":
        fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in fields})


@dataclass
class Season:
    """One monthly season of the roster game: the tier sets how many seats
    may be seated between ``starts_at`` and ``ends_at``."""

    id: str
    label: str
    tier: str
    roster_slots: int
    starts_at: str
    ends_at: str

    def __post_init__(self) -> None:
        _check_id(self.id)
        if not self.label or len(self.label) > 80:
            raise SocialManifestError("season label must be 1-80 chars")
        if not self.tier:
            raise SocialManifestError("season tier must be named")
        if not isinstance(self.roster_slots, int) or self.roster_slots < 1:
            raise SocialManifestError("roster_slots must be an int >= 1")
        _check_ts(self.starts_at, "starts_at")
        _check_ts(self.ends_at, "ends_at")
        if self.ends_at <= self.starts_at:
            raise SocialManifestError("season must end after it starts")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Season":
        fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in fields})


@dataclass
class BloodlineRule:
    """The forking law for one repo's bloodline.

    ``prime_id`` is the origin of the line; ``parent_id`` the immediate
    parent (None = the prime itself). Every fork inherits the parent's
    ``safety_ceiling`` — strictest-risk-ceiling inheritance. Dropping the
    ceiling (``founder_override=True``) is founder-only: the manifest
    demands the founder's approval record, and the act itself never
    leaves Cybrus.
    """

    repo_id: str
    prime_id: str
    safety_ceiling: str
    parent_id: Optional[str] = None
    founder_override: bool = False
    founder_approval: str = ""
    recorded_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        _check_id(self.repo_id, "repo_id")
        _check_id(self.prime_id, "prime_id")
        if self.parent_id is not None:
            _check_id(self.parent_id, "parent_id")
        if not self.safety_ceiling:
            raise SocialManifestError("safety_ceiling must be named")
        if self.founder_override and not self.founder_approval:
            raise SocialManifestError(
                "founder_override without founder_approval is refused: "
                "dropping the safety ceiling needs the founder's record"
            )
        _check_ts(self.recorded_at, "recorded_at")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BloodlineRule":
        fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in fields})


def _canonical(section: Any) -> bytes:
    return json.dumps(section, sort_keys=True, separators=(",", ":")).encode()


@dataclass
class ManifestBundle:
    """The portable bundle: format tag, versioned sections, checksums.

    ``seal()`` computes per-section sha256 over canonical JSON plus a
    manifest checksum over the sorted section checksums. ``verify()``
    recomputes everything and REFUSES the bundle on any mismatch —
    integrity is verified, not assumed (cf. ``levi.communities``).
    """

    sections: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    format: str = SOCIAL_MANIFEST_FORMAT
    format_version: int = SOCIAL_MANIFEST_VERSION
    exported_at: str = field(default_factory=_now)
    checksums: Dict[str, str] = field(default_factory=dict)
    manifest: str = ""

    def seal(self) -> "ManifestBundle":
        _check_ts(self.exported_at, "exported_at")
        self.checksums = {
            name: hashlib.sha256(_canonical(items)).hexdigest()
            for name, items in sorted(self.sections.items())
        }
        self.manifest = hashlib.sha256(_canonical(self.checksums)).hexdigest()
        return self

    def verify(self) -> None:
        if self.format != SOCIAL_MANIFEST_FORMAT:
            raise SocialManifestError(
                "bad format tag %r: want %r" % (self.format, SOCIAL_MANIFEST_FORMAT)
            )
        if self.format_version != SOCIAL_MANIFEST_VERSION:
            raise SocialManifestError(
                "bad format version %r: want %r"
                % (self.format_version, SOCIAL_MANIFEST_VERSION)
            )
        expect = {
            name: hashlib.sha256(_canonical(items)).hexdigest()
            for name, items in sorted(self.sections.items())
        }
        if expect != self.checksums:
            raise SocialManifestError("section checksums do not match: tampered")
        if hashlib.sha256(_canonical(self.checksums)).hexdigest() != self.manifest:
            raise SocialManifestError("manifest checksum does not match: tampered")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManifestBundle":
        return cls(
            sections=data.get("sections", {}),
            format=data.get("format", SOCIAL_MANIFEST_FORMAT),
            format_version=data.get("format_version", SOCIAL_MANIFEST_VERSION),
            exported_at=data.get("exported_at", _now()),
            checksums=data.get("checksums", {}),
            manifest=data.get("manifest", ""),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "ManifestBundle":
        return cls.from_dict(json.loads(text))


__all__ = [
    "SOCIAL_MANIFEST_FORMAT",
    "SOCIAL_MANIFEST_VERSION",
    "DOMAINS",
    "KINDS",
    "NATURES",
    "PROFILE_STATUSES",
    "VISIBILITIES",
    "THREAD_STATUSES",
    "AUDIENCE_TIERS",
    "SocialManifestError",
    "Profile",
    "Realm",
    "Thread",
    "Post",
    "Vote",
    "VoteBook",
    "Squad",
    "Season",
    "BloodlineRule",
    "ManifestBundle",
]
