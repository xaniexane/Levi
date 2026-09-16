"""Bridging-ranked discussion trees.

Data model: ``Discussion{id, title, community_id?, created_at}`` holding a
forest of ``Comment{id, discussion_id, parent_id?, author_id, text,
created_at, up[], down[]}``. ``community_id`` is an opaque string that
matches ``levi.communities`` ids by convention — the packages stay
import-decoupled.

Ranking (per discussion, computed on demand):

    quality(c)  = 0.5 * voteness(c) + 0.3 * substance(c) + 0.2 * depthness(c)
    bridging(c) = min-max normalized β_c from levi.bridging.fit_bridging
                  over the voter×comment matrix (up=+1, down=-1)
    score(c)    = w_quality * quality(c) + w_bridging * bridging(c)

- ``voteness``: net votes mapped through a saturating curve into [0, 1].
- ``substance``: length saturating at 280 chars (documented heuristic).
- ``depthness``: ``0.9 ** depth`` — replies sink slightly unless they earn
  it back through votes/bridging. Documented, editable via weights.
- ``bridging``: comments that win votes from voters who normally disagree
  (opposite latent camps) rank above factional applause. Needs ≥3
  distinct voters on the comment to count; otherwise 0.5 (neutral).

Trees render depth-first with siblings sorted by score. ``explain``
prints every component per comment.

Portable identity: ``Profile{id, display_name, bio, created_at}``.
``profile export`` emits ``{format, profile, signature}`` where the
signature is HMAC-SHA256 over canonical JSON with a local key
(``~/.levi/threads/identity.key``, owner-only 0o600). HONEST SCOPE: the
signature proves the artifact was produced by whoever holds the key —
authorship continuity across exports, portable between machines. It is
NOT a global identity system, NOT proof of personhood, and anyone
verifying needs the key (shared out-of-band). We say this plainly
because giants sell "verified identity" while meaning "platform account".
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from levi.bridging.bridging import fit_bridging  # pure math only; decoupled

PROFILE_FORMAT = "levi-profile/1"
_SUBSTANCE_CHARS = 280.0
_DEPTH_DECAY = 0.9
_MIN_VOTERS_FOR_BRIDGING = 3


def _home() -> Path:
    override = os.environ.get("LEVI_HOME")
    if override:
        return Path(override)
    return Path.home() / ".levi"


def _base() -> Path:
    return _home() / "threads"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ThreadError(ValueError):
    """Invalid thread operation."""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Comment:
    id: str
    discussion_id: str
    parent_id: Optional[str]
    author_id: str
    text: str
    created_at: str = field(default_factory=_now)
    up: List[str] = field(default_factory=list)    # voter ids
    down: List[str] = field(default_factory=list)

    @property
    def net(self) -> int:
        return len(self.up) - len(self.down)


@dataclass
class Discussion:
    id: str
    title: str
    community_id: Optional[str] = None
    created_at: str = field(default_factory=_now)


@dataclass
class Profile:
    id: str
    display_name: str
    bio: str = ""
    created_at: str = field(default_factory=_now)


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

DEFAULT_RANK_WEIGHTS = {"quality": 0.5, "bridging": 0.5}


class ThreadStore:
    def __init__(self, base: Optional[Path] = None) -> None:
        self._base = base or _base()
        self.discussions: Dict[str, Discussion] = {}
        self.comments: Dict[str, Dict[str, Comment]] = {}  # discussion_id -> {comment_id: Comment}
        self.profiles: Dict[str, Profile] = {}
        self.rank_weights: Dict[str, float] = dict(DEFAULT_RANK_WEIGHTS)
        self._load()

    # -- persistence ----------------------------------------------------
    def _path(self) -> Path:
        return self._base / "threads.json"

    def _load(self) -> None:
        try:
            raw = json.loads(self._path().read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return
        self.discussions = {d["id"]: Discussion(**d) for d in raw.get("discussions", [])}
        self.comments = {}
        for did, cmap in raw.get("comments", {}).items():
            self.comments[did] = {cid: Comment(**c) for cid, c in cmap.items()}
        self.profiles = {p["id"]: Profile(**p) for p in raw.get("profiles", [])}
        for k, v in raw.get("rank_weights", {}).items():
            if k in DEFAULT_RANK_WEIGHTS:
                self.rank_weights[k] = float(v)

    def _save(self) -> None:
        self._base.mkdir(parents=True, exist_ok=True)
        payload = {
            "discussions": [asdict(d) for d in self.discussions.values()],
            "comments": {did: {cid: asdict(c) for cid, c in cmap.items()}
                        for did, cmap in self.comments.items()},
            "profiles": [asdict(p) for p in self.profiles.values()],
            "rank_weights": self.rank_weights,
        }
        tmp = self._path().with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
        tmp.replace(self._path())

    # -- discussions & comments ------------------------------------------
    def new_discussion(self, title: str, discussion_id: Optional[str] = None,
                       community_id: Optional[str] = None) -> Discussion:
        title = title.strip()
        if not title:
            raise ThreadError("discussion title must be non-empty")
        did = (discussion_id or hashlib.sha256(f"{title}|{_now()}".encode()).hexdigest()[:12]).strip()
        if not did or did in self.discussions:
            raise ThreadError(f"discussion id {did!r} invalid or already exists")
        d = Discussion(id=did, title=title, community_id=community_id)
        self.discussions[did] = d
        self.comments[did] = {}
        self._save()
        return d

    def _get_discussion(self, discussion_id: str) -> Discussion:
        try:
            return self.discussions[discussion_id]
        except KeyError:
            raise ThreadError(f"unknown discussion {discussion_id!r}")

    def add_comment(self, discussion_id: str, author_id: str, text: str,
                    parent_id: Optional[str] = None) -> Comment:
        self._get_discussion(discussion_id)
        author_id, text = author_id.strip(), text.strip()
        if not author_id:
            raise ThreadError("author id must be non-empty")
        if not text:
            raise ThreadError("comment text must be non-empty")
        cmap = self.comments[discussion_id]
        if parent_id is not None and parent_id not in cmap:
            raise ThreadError(f"unknown parent comment {parent_id!r}")
        cid = hashlib.sha256(
            f"{discussion_id}|{parent_id}|{author_id}|{text}|{_now()}".encode()).hexdigest()[:12]
        c = Comment(id=cid, discussion_id=discussion_id, parent_id=parent_id,
                    author_id=author_id, text=text)
        cmap[cid] = c
        self._save()
        return c

    def vote(self, discussion_id: str, comment_id: str, voter_id: str,
             value: str) -> None:
        self._get_discussion(discussion_id)
        cmap = self.comments[discussion_id]
        try:
            c = cmap[comment_id]
        except KeyError:
            raise ThreadError(f"unknown comment {comment_id!r}")
        voter_id = voter_id.strip()
        if not voter_id:
            raise ThreadError("voter id must be non-empty")
        if value not in ("up", "down"):
            raise ThreadError("vote must be 'up' or 'down'")
        c.up = [v for v in c.up if v != voter_id]
        c.down = [v for v in c.down if v != voter_id]
        (c.up if value == "up" else c.down).append(voter_id)
        self._save()

    # -- ranking ----------------------------------------------------------
    def _depths(self, discussion_id: str) -> Dict[str, int]:
        cmap = self.comments[discussion_id]
        depths: Dict[str, int] = {}

        def depth(cid: str) -> int:
            if cid in depths:
                return depths[cid]
            parent = cmap[cid].parent_id
            depths[cid] = 0 if parent is None else depth(parent) + 1
            return depths[cid]

        for cid in cmap:
            depth(cid)
        return depths

    def _bridging_scores(self, discussion_id: str) -> Dict[str, float]:
        """Min-max normalized helpfulness β per comment, [0,1].

        Comments with < MIN_VOTERS_FOR_BRIDGING distinct voters get 0.5
        (neutral — not enough evidence to judge cross-camp consensus).
        """
        cmap = self.comments[discussion_id]
        ratings: Dict[str, Dict[str, float]] = {}
        for cid, c in cmap.items():
            m: Dict[str, float] = {}
            for v in c.up:
                m[v] = 1.0
            for v in c.down:
                m[v] = -1.0
            if m:
                ratings[cid] = m
        if not ratings:
            return {cid: 0.5 for cid in cmap}
        fit = fit_bridging(ratings)
        betas = {cid: fit.note_helpfulness.get(cid, 0.0) for cid in cmap}
        lo, hi = min(betas.values()), max(betas.values())
        out = {}
        for cid in cmap:
            if len(ratings.get(cid, {})) < _MIN_VOTERS_FOR_BRIDGING:
                out[cid] = 0.5
            elif hi - lo < 1e-9:
                out[cid] = 0.5
            else:
                out[cid] = (betas[cid] - lo) / (hi - lo)
        return out

    def _quality(self, c: Comment, depth: int) -> Dict[str, float]:
        voteness = c.net / (abs(c.net) + 5.0) * 0.5 + 0.5  # saturating -> [0,1]
        voteness = max(0.0, min(1.0, voteness))
        substance = min(1.0, len(c.text) / _SUBSTANCE_CHARS)
        depthness = _DEPTH_DECAY ** depth
        return {
            "voteness": voteness,
            "substance": substance,
            "depthness": depthness,
            "quality": 0.5 * voteness + 0.3 * substance + 0.2 * depthness,
        }

    def rank(self, discussion_id: str) -> List[Dict[str, Any]]:
        """Score every comment; return list of {comment, depth, quality…,
        bridging, score} sorted by score desc."""
        self._get_discussion(discussion_id)
        cmap = self.comments[discussion_id]
        depths = self._depths(discussion_id)
        bridging = self._bridging_scores(discussion_id)
        wq = self.rank_weights.get("quality", 0.5)
        wb = self.rank_weights.get("bridging", 0.5)
        total = wq + wb or 1.0
        rows = []
        for cid, c in cmap.items():
            q = self._quality(c, depths[cid])
            b = bridging[cid]
            score = (wq * q["quality"] + wb * b) / total
            rows.append({"comment": c, "depth": depths[cid], **q,
                         "bridging": b, "score": score})
        rows.sort(key=lambda r: (-r["score"], r["comment"].created_at))
        return rows

    def set_rank_weight(self, name: str, value: float) -> None:
        if name not in self.rank_weights:
            raise ThreadError(f"unknown rank weight {name!r}; known: {sorted(self.rank_weights)}")
        if not math.isfinite(value) or value < 0:
            raise ThreadError("rank weight must be a finite non-negative number")
        self.rank_weights[name] = float(value)
        self._save()

    def render_tree(self, discussion_id: str, limit: int = 50) -> str:
        d = self._get_discussion(discussion_id)
        rows = self.rank(discussion_id)
        by_id = {r["comment"].id: r for r in rows}
        children: Dict[Optional[str], List[str]] = {}
        for r in rows:
            children.setdefault(r["comment"].parent_id, []).append(r["comment"].id)
        for sibs in children.values():
            sibs.sort(key=lambda cid: -by_id[cid]["score"])
        lines = [f"=== {d.title} [{d.id}] ===",
                 f"rank weights: quality={self.rank_weights['quality']:.2f} "
                 f"bridging={self.rank_weights['bridging']:.2f}"]

        def walk(cid: str, depth: int) -> None:
            if len(lines) > limit + 2:
                return
            r = by_id[cid]
            c = r["comment"]
            indent = "  " * depth
            lines.append(f"{indent}[{c.id[:8]}] {c.author_id} "
                         f"(score={r['score']:.3f} q={r['quality']:.2f} b={r['bridging']:.2f} net={c.net:+d})")
            lines.append(f"{indent}  {c.text[:90]}")
            for child in children.get(cid, []):
                walk(child, depth + 1)

        for root in children.get(None, []):
            walk(root, 0)
        if not rows:
            lines.append("  (no comments yet)")
        return "\n".join(lines)

    # -- portable identity --------------------------------------------------
    def _identity_key(self) -> bytes:
        p = self._base / "identity.key"
        if not p.exists():
            self._base.mkdir(parents=True, exist_ok=True)
            key = os.urandom(32)
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(key)
            try:
                os.chmod(p, 0o600)
            except OSError:
                pass
        else:
            key = p.read_bytes()
        if len(key) < 16:
            raise ThreadError("identity key is corrupt (too short); delete it to rotate")
        return key

    def new_profile(self, profile_id: str, display_name: str, bio: str = "") -> Profile:
        profile_id = profile_id.strip()
        display_name = display_name.strip()
        if not profile_id:
            raise ThreadError("profile id must be non-empty")
        if not display_name:
            raise ThreadError("display name must be non-empty")
        if profile_id in self.profiles:
            raise ThreadError(f"profile {profile_id!r} already exists")
        p = Profile(id=profile_id, display_name=display_name, bio=bio.strip())
        self.profiles[profile_id] = p
        self._save()
        return p

    def export_profile(self, profile_id: str) -> Dict[str, Any]:
        try:
            p = self.profiles[profile_id]
        except KeyError:
            raise ThreadError(f"unknown profile {profile_id!r}")
        body = {"format": PROFILE_FORMAT, "profile": asdict(p)}
        sig = hmac.new(self._identity_key(),
                       json.dumps(body, sort_keys=True, separators=(",", ":")).encode(),
                       hashlib.sha256).hexdigest()
        return {**body, "signature": sig, "algorithm": "HMAC-SHA256"}

    def verify_profile(self, doc: Dict[str, Any]) -> Profile:
        """Verify a profile artifact. Returns the Profile on success.

        Honest scope: success proves the artifact was signed by the holder
        of THIS machine's identity key — authorship continuity, not
        personhood and not a global identity.
        """
        if doc.get("format") != PROFILE_FORMAT:
            raise ThreadError(f"not a LEVI profile artifact (format={doc.get('format')!r})")
        if doc.get("algorithm") != "HMAC-SHA256":
            raise ThreadError("unsupported signature algorithm")
        body = {"format": doc["format"], "profile": doc.get("profile")}
        expected = hmac.new(self._identity_key(),
                            json.dumps(body, sort_keys=True, separators=(",", ":")).encode(),
                            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, str(doc.get("signature", ""))):
            raise ThreadError("signature mismatch: artifact was not signed by this identity key")
        return Profile(**body["profile"])
