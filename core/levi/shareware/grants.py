"""Trial grants: issue, redeem, revoke — with a tamper-evident ledger.

A grant unlocks a set of premium-pack *features* for a bounded trial:
either a number of days, a number of uses, or both. A grant with
neither bound is refused — an unbounded "trial" is not a trial, it is
a promise nobody can price, and the honest-terms rule requires every
grant to say exactly what it is.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

TERMS_VERSION = "shareware-terms/1"


class SharewareError(Exception):
    """Any refusal: expired, revoked, exhausted, unknown feature, bad input."""


@dataclass
class TrialGrant:
    id: str
    pack: str
    features: List[str]
    issued_at: float
    expires_at: Optional[float]  # None = no time bound
    max_uses: Optional[int]  # None = no use bound
    uses: int = 0
    revoked: bool = False
    revoke_reason: str = ""
    note: str = ""
    terms_version: str = TERMS_VERSION

    def is_expired(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        return self.expires_at is not None and now >= self.expires_at

    def uses_left(self) -> Optional[int]:
        if self.max_uses is None:
            return None
        return max(0, self.max_uses - self.uses)

    def terms_text(self) -> str:
        bits = ["Trial grant %s for pack '%s'." % (self.id, self.pack)]
        feats = ", ".join(self.features) if self.features else "no features"
        bits.append("Unlocks: %s." % feats)
        bounds = []
        if self.expires_at is not None:
            bounds.append("expires at %s" % _iso(self.expires_at))
        if self.max_uses is not None:
            bounds.append("%d uses total" % self.max_uses)
        bits.append("Trial bound: %s." % ("; ".join(bounds) if bounds else "none"))
        bits.append(
            "When the trial ends, only the premium slice above locks. "
            "Your data stays yours: expiry never deletes, moves, or holds "
            "hostage anything you made. No account, no card, no network "
            "was involved in this grant."
        )
        return " ".join(bits)


def _iso(ts: float) -> str:
    import datetime

    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat()


class GrantStore:
    """Owner-only store of grants + a hash-chained receipt ledger."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root else Path.home() / ".levi" / "shareware"
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        self._grants_file = self.root / "grants.json"
        self._ledger_file = self.root / "ledger.jsonl"

    # -- persistence ------------------------------------------------------
    def _load(self) -> Dict[str, TrialGrant]:
        if not self._grants_file.exists():
            return {}
        data = json.loads(self._grants_file.read_text(encoding="utf-8"))
        return {gid: TrialGrant(**g) for gid, g in data.items()}

    def _save(self, grants: Dict[str, TrialGrant]) -> None:
        tmp = self._grants_file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {gid: asdict(g) for gid, g in grants.items()}, indent=1, sort_keys=True
            ),
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        tmp.replace(self._grants_file)
        os.chmod(self._grants_file, 0o600)

    def _ledger_append(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        prev = self._ledger_tip()
        payload = dict(entry)
        payload["prev_hash"] = prev
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        payload["hash"] = digest
        with open(self._ledger_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")
        os.chmod(self._ledger_file, 0o600)
        return payload

    def _ledger_tip(self) -> str:
        if not self._ledger_file.exists():
            return "0" * 64
        last = None
        with open(self._ledger_file, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    last = line
        if last is None:
            return "0" * 64
        return json.loads(last)["hash"]

    def _ledger_entries(self) -> List[Dict[str, Any]]:
        if not self._ledger_file.exists():
            return []
        out = []
        with open(self._ledger_file, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    # -- lifecycle --------------------------------------------------------
    def issue(
        self,
        pack: str,
        features: List[str],
        days: Optional[float] = None,
        max_uses: Optional[int] = None,
        note: str = "",
        now: Optional[float] = None,
    ) -> TrialGrant:
        if not pack or not pack.strip():
            raise SharewareError("pack name is required")
        features = [f.strip() for f in features if f and f.strip()]
        if not features:
            raise SharewareError("at least one feature is required")
        if days is None and max_uses is None:
            raise SharewareError(
                "a grant needs a bound: days, max_uses, or both "
                "(an unbounded trial is not a trial)"
            )
        if days is not None and days <= 0:
            raise SharewareError("days must be positive")
        if max_uses is not None and (not isinstance(max_uses, int) or max_uses <= 0):
            raise SharewareError("max_uses must be a positive integer")
        now = time.time() if now is None else now
        grant = TrialGrant(
            id="sw-" + uuid.uuid4().hex[:8],
            pack=pack.strip(),
            features=features,
            issued_at=now,
            expires_at=(now + days * 86400) if days is not None else None,
            max_uses=max_uses,
            note=note,
        )
        grants = self._load()
        grants[grant.id] = grant
        self._save(grants)
        self._ledger_append(
            {
                "type": "issue",
                "grant_id": grant.id,
                "pack": grant.pack,
                "features": grant.features,
                "expires_at": grant.expires_at,
                "max_uses": grant.max_uses,
                "at": now,
                "terms_version": TERMS_VERSION,
            }
        )
        return grant

    def get(self, grant_id: str) -> TrialGrant:
        grants = self._load()
        try:
            return grants[grant_id]
        except KeyError:
            raise SharewareError("no such grant: %s" % grant_id) from None

    def redeem(
        self, grant_id: str, feature: Optional[str] = None, now: Optional[float] = None
    ) -> Dict[str, Any]:
        """Use one unit of the trial. Never touches user data — only the
        grant's own counters. Returns the receipt."""
        now = time.time() if now is None else now
        grants = self._load()
        grant = grants.get(grant_id)
        if grant is None:
            raise SharewareError("no such grant: %s" % grant_id)
        if grant.revoked:
            raise SharewareError(
                "grant %s was revoked: %s"
                % (grant_id, grant.revoke_reason or "no reason given")
            )
        if grant.is_expired(now):
            raise SharewareError(
                "grant %s expired at %s — the premium slice is locked; "
                "your data is untouched" % (grant_id, _iso(grant.expires_at or 0))
            )
        if grant.max_uses is not None and grant.uses >= grant.max_uses:
            raise SharewareError(
                "grant %s is exhausted (%d/%d uses)"
                % (grant_id, grant.uses, grant.max_uses)
            )
        if feature is not None and feature not in grant.features:
            raise SharewareError(
                "grant %s does not cover feature %r "
                "(covers: %s)" % (grant_id, feature, ", ".join(grant.features))
            )
        grant.uses += 1
        grants[grant_id] = grant
        self._save(grants)
        receipt = self._ledger_append(
            {
                "type": "redeem",
                "grant_id": grant_id,
                "feature": feature,
                "at": now,
                "uses": grant.uses,
                "uses_left": grant.uses_left(),
                "expires_at": grant.expires_at,
            }
        )
        return receipt

    def revoke(
        self, grant_id: str, reason: str = "", now: Optional[float] = None
    ) -> TrialGrant:
        now = time.time() if now is None else now
        grants = self._load()
        grant = grants.get(grant_id)
        if grant is None:
            raise SharewareError("no such grant: %s" % grant_id)
        grant.revoked = True
        grant.revoke_reason = reason
        grants[grant_id] = grant
        self._save(grants)
        self._ledger_append(
            {
                "type": "revoke",
                "grant_id": grant_id,
                "reason": reason,
                "at": now,
            }
        )
        return grant

    def list(self) -> List[TrialGrant]:
        return sorted(self._load().values(), key=lambda g: g.issued_at)

    def verify(self) -> Dict[str, Any]:
        """Recompute the ledger hash chain. Returns ok + any bad indexes."""
        entries = self._ledger_entries()
        prev = "0" * 64
        bad: List[int] = []
        for i, entry in enumerate(entries):
            if entry.get("prev_hash") != prev:
                bad.append(i)
            payload = {k: v for k, v in entry.items() if k != "hash"}
            digest = hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode("utf-8")
            ).hexdigest()
            if entry.get("hash") != digest:
                bad.append(i)
            prev = entry.get("hash", "")
        return {"ok": not bad, "entries": len(entries), "bad": sorted(set(bad))}
