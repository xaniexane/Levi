"""Per-item audience grants — the Google+ Circles revival (``levi.circles.audience``).

The dead mechanism: Google+ (2011-2019) gave every post its own ACL —
circles plus named individuals, independent of the follow graph; roughly
two-thirds of consumed content was private. Meta/X never adopted
per-post ACLs because uniform audiences monetize better. The mechanism
died with the product, not from a flaw in the mechanism.

LEVI's port: ``AudienceStore`` extends the circles store (Path circles,
Dunbar caps — see :mod:`levi.circles.model`) with per-item grants on
share receipts:

- ``grant(post_id, circles=[...], individuals=[...])`` — resolve the
  named circles + named individuals to an explicit member snapshot and
  record the grant. The snapshot is the receipt: who could see it, when.
- ``revoke(post_id)`` — explicit, permanent, recorded. Revoked grants
  are kept, never deleted.
- ``can_see(post_id, member_id)`` — the gate: deny-closed.
- ``audience_of(post_id)`` — the audit of who saw what: spec + snapshot
  + revocation state.

Invariants (law -> guard -> prove; the tests are the proof):
1. Per-post, not per-graph — the audience is named on the item;
   membership in a circle is neither necessary nor sufficient beyond
   what the grant says.
2. Snapshot semantics — the grant records the resolved member list at
   grant time, so the audit is stable even as circles change later.
3. Revoke is explicit and permanent — a revoked grant admits nobody;
   the revoked record stays in the audit trail (nothing thrown away).
4. Deny-closed — an unknown post id, or a post with no live grant,
   is visible to no one.
5. Named individuals must be real members — you cannot grant an
   audience to someone who is not in your circles; the store raises
   rather than recording a phantom.

Persistence lives beside the circles store (``audience.json``, dir
0700 / file 0600 — the same privacy as the circles map). Stdlib only.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import CircleError
from .model import CircleStore, cap_for

__all__ = [
    "AudienceGrant",
    "AudienceStore",
    "CircleError",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AudienceGrant:
    """One post's audience: the spec plus the resolved snapshot."""

    post_id: str
    spec_circles: List[str] = field(default_factory=list)
    spec_individuals: List[str] = field(default_factory=list)
    member_ids: List[str] = field(default_factory=list)  # resolved snapshot
    granted_at: str = field(default_factory=_now)
    revoked: bool = False
    revoked_at: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "AudienceGrant":
        return cls(
            post_id=str(d.get("post_id", "")),
            spec_circles=[str(x) for x in d.get("spec_circles", [])],
            spec_individuals=[str(x) for x in d.get("spec_individuals", [])],
            member_ids=[str(x) for x in d.get("member_ids", [])],
            granted_at=str(d.get("granted_at", "")),
            revoked=bool(d.get("revoked", False)),
            revoked_at=str(d.get("revoked_at", "")),
        )


class AudienceStore:
    """Per-item audience grants, persisted beside the circles store."""

    def __init__(self, home: Optional[Path] = None) -> None:
        base = Path(home) if home is not None else Path.home() / ".levi"
        self._dir = base / "circles"
        self._file = self._dir / "audience.json"
        self._grants: Dict[str, AudienceGrant] = {}
        self._load()

    # -- persistence -----------------------------------------------------
    def _load(self) -> None:
        if not self._file.is_file():
            return
        try:
            raw = json.loads(self._file.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise CircleError("audience store unreadable: %s" % exc) from exc
        grants = raw.get("grants", {})
        if not isinstance(grants, dict):
            raise CircleError("audience store corrupt: 'grants' not an object")
        for gd in grants.values():
            if isinstance(gd, dict) and gd.get("post_id"):
                self._grants[str(gd["post_id"])] = AudienceGrant.from_dict(gd)

    def _save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self._dir, 0o700)
        tmp = self._file.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(
                {"grants": {g.post_id: g.to_dict() for g in self._grants.values()}},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._file)
        os.chmod(self._file, 0o600)

    # -- grants ----------------------------------------------------------
    def grant(
        self,
        post_id: str,
        circles: CircleStore,
        layers: Optional[List[str]] = None,
        individuals: Optional[List[str]] = None,
    ) -> AudienceGrant:
        """Name this post's audience: circle layers + named individuals.

        Resolves to an explicit member snapshot immediately. Raises
        :class:`CircleError` on unknown layers, unknown individuals, or
        an empty audience (a grant that names nobody is a refusal to
        record a phantom audience).
        """
        post_id = (post_id or "").strip()
        if not post_id:
            raise CircleError("grant needs a post_id")
        if post_id in self._grants and not self._grants[post_id].revoked:
            raise CircleError(
                "post %r already has a live grant — revoke it first" % post_id
            )
        layers = list(layers or [])
        individuals = list(individuals or [])
        for layer in layers:
            cap_for(layer)  # validates the layer exists
        known = {m.id for m in circles.members()}
        for person in individuals:
            if person not in known:
                raise CircleError(
                    "cannot grant audience to %r: not in your circles" % person
                )
        resolved = set()
        for layer in layers:
            resolved.update(m.id for m in circles.members(layer))
        resolved.update(individuals)
        if not resolved:
            raise CircleError(
                "grant for post %r names nobody — refusing to record "
                "an empty audience" % post_id
            )
        grant = AudienceGrant(
            post_id=post_id,
            spec_circles=sorted(layers),
            spec_individuals=sorted(individuals),
            member_ids=sorted(resolved),
        )
        self._grants[post_id] = grant
        self._save()
        return grant

    def revoke(self, post_id: str) -> AudienceGrant:
        """Revoke a post's audience. Explicit, permanent, recorded."""
        grant = self._grants.get(post_id)
        if grant is None:
            raise CircleError("no grant for post %r" % post_id)
        if not grant.revoked:
            grant.revoked = True
            grant.revoked_at = _now()
            self._save()
        return grant

    def can_see(self, post_id: str, member_id: str) -> bool:
        """Deny-closed gate: unknown or revoked posts are visible to none."""
        grant = self._grants.get(post_id)
        if grant is None or grant.revoked:
            return False
        return member_id in grant.member_ids

    def audience_of(self, post_id: str) -> Dict:
        """The who-saw-what audit for one post."""
        grant = self._grants.get(post_id)
        if grant is None:
            raise CircleError("no grant for post %r" % post_id)
        return {
            "post_id": grant.post_id,
            "spec_circles": list(grant.spec_circles),
            "spec_individuals": list(grant.spec_individuals),
            "member_ids": list(grant.member_ids),
            "granted_at": grant.granted_at,
            "revoked": grant.revoked,
            "revoked_at": grant.revoked_at,
        }

    def grants(self) -> List[AudienceGrant]:
        return [self._grants[k] for k in sorted(self._grants)]
