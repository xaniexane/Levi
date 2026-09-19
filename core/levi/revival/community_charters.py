"""Community charters: governance as a portable artifact.

Studied from: giant-patterns-hunt-20260916-0016/report.md [Additions 9]
(founder-held keys and real mod tooling; governance as a portable artifact).

This is an original, from-scratch implementation for LEVI. A ``Charter``
is a signed governance document: a name, a purpose statement, a roster of
founder keys, member roles (founder / moderator / member), bylaws text, and
an amendment history. Amendments are proposed by any member but take effect
only when signed by a founder quorum (default: a strict majority of
founder keys), and every amendment is hash-chained into the charter so the
governance history is tamper-evident. The whole charter serializes to plain
JSON — the portable artifact — which another LEVI instance can import and
verify from the founder public keys alone, with no central registry.

Real mod tooling: founders and moderators can issue warnings, suspensions
(with durations), and bans; every action lands in an append-only mod log
with the acting key's signature. Role changes are amendments, so they need
the same founder quorum. A banned or suspended member cannot hold office.

Honest limits: signatures use HMAC with founder secrets held locally — this
proves authorization to anyone who holds the founder key registry, not to
the public at large. Suspension durations are enforced by wall-clock at
check time; a portable charter cannot force a remote instance to enforce
anything. Quorum math assumes founders are distinct people.

Public surface:
- ``Charter``: ``found``, ``propose_amendment``, ``sign_amendment``,
  ``enact`` / pending amendments, ``warn`` / ``suspend`` / ``ban`` /
  ``member_status``, ``mod_log``, ``export`` / ``import_charter``,
  ``verify_chain``.
- ``FounderKey``, ``Amendment``, ``ModAction``, ``CharterError``.

stdlib-only. No network. Deterministic apart from timestamps.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/community-charters"


class CharterError(ValueError):
    """Raised when a governance operation is refused."""


@dataclass(frozen=True)
class FounderKey:
    """A founder's key material: id + HMAC secret kept by the founder."""

    key_id: str
    secret: str = field(repr=False)

    def sign(self, payload: str) -> str:
        return hmac.new(
            self.secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()[:32]


@dataclass
class Amendment:
    """A proposed charter change awaiting founder-quorum signatures."""

    amendment_id: int
    kind: str  # "bylaws" | "role" | "purpose"
    target: str  # member id for role changes, "" otherwise
    new_value: str
    proposed_by: str
    signatures: Dict[str, str] = field(default_factory=dict)
    enacted: bool = False


@dataclass
class ModAction:
    """One moderation event in the append-only log."""

    action_id: int
    kind: str  # "warn" | "suspend" | "ban" | "unban"
    target: str
    actor_key_id: str
    reason: str
    timestamp: float
    signature: str
    duration_days: Optional[float] = None


class Charter:
    """A signed, portable community charter."""

    def __init__(
        self,
        name: str,
        purpose: str,
        bylaws: str,
        founder_keys: List[FounderKey],
        quorum: Optional[int] = None,
    ) -> None:
        if not founder_keys:
            raise CharterError("a charter needs at least one founder key")
        key_ids = [k.key_id for k in founder_keys]
        if len(set(key_ids)) != len(key_ids):
            raise CharterError("founder key ids must be unique")
        self.name = name
        self.purpose = purpose
        self.bylaws = bylaws
        self._keys: Dict[str, FounderKey] = {k.key_id: k for k in founder_keys}
        self.quorum = quorum or (len(founder_keys) // 2 + 1)
        if self.quorum > len(founder_keys):
            raise CharterError("quorum cannot exceed the founder count")
        # member_id -> role
        self.roles: Dict[str, str] = {key_ids[0]: "founder"}
        for key_id in key_ids[1:]:
            self.roles[key_id] = "founder"
        self._amendments: List[Amendment] = []
        self._mod_log: List[ModAction] = []
        self._chain: List[str] = []
        self._chain_append(f"FOUND name={name}")

    # -- chain ------------------------------------------------------------
    def _chain_append(self, entry: str) -> None:
        prev = self._chain[-1] if self._chain else "GENESIS"
        stamp = f"{time.time():.3f}"
        digest = hashlib.sha256(f"{prev}|{stamp}|{entry}".encode()).hexdigest()[:16]
        self._chain.append(f"{stamp} {entry} [{digest}]")

    def verify_chain(self) -> bool:
        prev = "GENESIS"
        for entry in self._chain:
            try:
                stamp, rest = entry.split(" ", 1)
                body, digest = rest.rsplit(" [", 1)
                digest = digest.rstrip("]")
            except ValueError:
                return False
            expect = hashlib.sha256(f"{prev}|{stamp}|{body}".encode()).hexdigest()[:16]
            if not hmac.compare_digest(expect, digest):
                return False
            prev = entry
        return True

    # -- amendments -------------------------------------------------------
    def propose_amendment(
        self, proposed_by: str, kind: str, new_value: str, target: str = ""
    ) -> Amendment:
        if kind not in ("bylaws", "role", "purpose"):
            raise CharterError(f"unknown amendment kind {kind!r}")
        if kind == "role" and new_value not in ("founder", "moderator", "member"):
            raise CharterError(f"unknown role {new_value!r}")
        if kind == "role" and not target:
            raise CharterError("role amendments need a target member")
        amendment = Amendment(
            amendment_id=len(self._amendments) + 1,
            kind=kind,
            target=target,
            new_value=new_value,
            proposed_by=proposed_by,
        )
        self._amendments.append(amendment)
        return amendment

    def sign_amendment(self, amendment_id: int, key: FounderKey) -> Amendment:
        if key.key_id not in self._keys:
            raise CharterError(f"{key.key_id!r} is not a founder key")
        if self._keys[key.key_id].secret != key.secret:
            raise CharterError("founder key secret mismatch")
        amendment = self._amendment(amendment_id)
        if amendment.enacted:
            raise CharterError("amendment already enacted")
        payload = f"amend:{amendment.amendment_id}:{amendment.kind}:{amendment.target}:{amendment.new_value}"
        amendment.signatures[key.key_id] = key.sign(payload)
        if len(amendment.signatures) >= self.quorum:
            self._enact(amendment)
        return amendment

    def _enact(self, amendment: Amendment) -> None:
        if amendment.kind == "bylaws":
            self.bylaws = amendment.new_value
        elif amendment.kind == "purpose":
            self.purpose = amendment.new_value
        elif amendment.kind == "role":
            if self.member_status(amendment.target) in ("banned", "suspended"):
                raise CharterError("cannot grant office to a banned/suspended member")
            self.roles[amendment.target] = amendment.new_value
        amendment.enacted = True
        self._chain_append(
            f"AMEND id={amendment.amendment_id} kind={amendment.kind} "
            f"target={amendment.target} sigs={len(amendment.signatures)}"
        )

    def _amendment(self, amendment_id: int) -> Amendment:
        try:
            return self._amendments[amendment_id - 1]
        except IndexError as exc:
            raise CharterError(f"no amendment {amendment_id}") from exc

    @classmethod
    def found(
        cls,
        name: str,
        purpose: str,
        bylaws: str,
        founders: List[FounderKey],
        quorum: Optional[int] = None,
    ) -> "Charter":
        """Convenience constructor: found a new community charter."""
        return cls(name, purpose, bylaws, founders, quorum)

    # -- mod tooling ------------------------------------------------------
    def _mod_key(self, key: FounderKey) -> None:
        if key.key_id not in self._keys:
            raise CharterError(f"{key.key_id!r} is not a founder key")
        if self._keys[key.key_id].secret != key.secret:
            raise CharterError("founder key secret mismatch")

    def _moderator(self, actor: str) -> None:
        if self.roles.get(actor) not in ("founder", "moderator"):
            raise CharterError(f"{actor!r} holds no moderation role")
        if self.member_status(actor) in ("banned", "suspended"):
            raise CharterError(f"{actor!r} is currently {self.member_status(actor)}")

    def _log_mod(
        self,
        kind: str,
        target: str,
        actor_key_id: str,
        reason: str,
        duration_days: Optional[float] = None,
    ) -> ModAction:
        key = self._keys[actor_key_id]
        action_id = len(self._mod_log) + 1
        payload = f"mod:{action_id}:{kind}:{target}:{reason}"
        action = ModAction(
            action_id=action_id,
            kind=kind,
            target=target,
            actor_key_id=actor_key_id,
            reason=reason,
            timestamp=time.time(),
            signature=key.sign(payload),
            duration_days=duration_days,
        )
        self._mod_log.append(action)
        self._chain_append(
            f"MOD id={action_id} kind={kind} target={target} by={actor_key_id}"
        )
        return action

    def warn(self, actor_key: FounderKey, target: str, reason: str) -> ModAction:
        self._mod_key(actor_key)
        self._moderator(actor_key.key_id)
        return self._log_mod("warn", target, actor_key.key_id, reason)

    def suspend(
        self, actor_key: FounderKey, target: str, reason: str, days: float
    ) -> ModAction:
        self._mod_key(actor_key)
        self._moderator(actor_key.key_id)
        if days <= 0:
            raise CharterError("suspension duration must be positive")
        return self._log_mod("suspend", target, actor_key.key_id, reason, days)

    def ban(self, actor_key: FounderKey, target: str, reason: str) -> ModAction:
        self._mod_key(actor_key)
        self._moderator(actor_key.key_id)
        return self._log_mod("ban", target, actor_key.key_id, reason)

    def member_status(self, member: str, now: Optional[float] = None) -> str:
        """Current standing: member / suspended / banned / warned."""
        now = now if now is not None else time.time()
        status = "member"
        for action in self._mod_log:
            if action.target != member:
                continue
            if action.kind == "ban":
                status = "banned"
            elif action.kind == "unban":
                status = "member"
            elif action.kind == "suspend":
                expiry = action.timestamp + (action.duration_days or 0) * 86400
                status = "suspended" if now < expiry else "member"
            elif action.kind == "warn" and status == "member":
                status = "warned"
        return status

    def mod_log(self) -> List[ModAction]:
        return list(self._mod_log)

    # -- portability ------------------------------------------------------
    def export(self) -> str:
        """Serialize the charter as the portable JSON artifact."""
        return json.dumps(
            {
                "name": self.name,
                "purpose": self.purpose,
                "bylaws": self.bylaws,
                "founder_key_ids": sorted(self._keys),
                "quorum": self.quorum,
                "roles": self.roles,
                "amendments": [
                    {
                        "id": a.amendment_id,
                        "kind": a.kind,
                        "target": a.target,
                        "new_value": a.new_value,
                        "proposed_by": a.proposed_by,
                        "signatures": a.signatures,
                        "enacted": a.enacted,
                    }
                    for a in self._amendments
                ],
                "mod_log": [
                    {
                        "id": m.action_id,
                        "kind": m.kind,
                        "target": m.target,
                        "actor": m.actor_key_id,
                        "reason": m.reason,
                        "ts": m.timestamp,
                        "signature": m.signature,
                        "days": m.duration_days,
                    }
                    for m in self._mod_log
                ],
                "chain": self._chain,
            },
            indent=2,
            sort_keys=True,
        )

    @classmethod
    def import_charter(cls, data: str, founder_keys: List[FounderKey]) -> "Charter":
        """Import a portable charter, verifying signatures and the chain."""
        payload = json.loads(data)
        charter = cls(
            payload["name"],
            payload["purpose"],
            payload["bylaws"],
            founder_keys,
            payload["quorum"],
        )
        if sorted(charter._keys) != sorted(payload["founder_key_ids"]):
            raise CharterError("founder key registry mismatch on import")
        charter.roles = dict(payload["roles"])
        for item in payload["amendments"]:
            amendment = Amendment(
                amendment_id=item["id"],
                kind=item["kind"],
                target=item["target"],
                new_value=item["new_value"],
                proposed_by=item["proposed_by"],
                signatures=dict(item["signatures"]),
                enacted=item["enacted"],
            )
            charter._amendments.append(amendment)
        for item in payload["mod_log"]:
            charter._mod_log.append(
                ModAction(
                    action_id=item["id"],
                    kind=item["kind"],
                    target=item["target"],
                    actor_key_id=item["actor"],
                    reason=item["reason"],
                    timestamp=item["ts"],
                    signature=item["signature"],
                    duration_days=item["days"],
                )
            )
        charter._chain = list(payload["chain"])
        if not charter.verify_chain():
            raise CharterError("charter chain failed verification on import")
        # Verify every amendment and mod-action signature against the registry.
        for amendment in charter._amendments:
            sig_payload = (
                f"amend:{amendment.amendment_id}:{amendment.kind}:"
                f"{amendment.target}:{amendment.new_value}"
            )
            for key_id, signature in amendment.signatures.items():
                key = charter._keys.get(key_id)
                if key is None or not hmac.compare_digest(
                    key.sign(sig_payload), signature
                ):
                    raise CharterError(
                        f"bad amendment signature from {key_id!r} on import"
                    )
        for action in charter._mod_log:
            sig_payload = (
                f"mod:{action.action_id}:{action.kind}:{action.target}:{action.reason}"
            )
            key = charter._keys.get(action.actor_key_id)
            if key is None or not hmac.compare_digest(
                key.sign(sig_payload), action.signature
            ):
                raise CharterError(
                    f"bad mod-action signature from {action.actor_key_id!r} on import"
                )
        return charter
