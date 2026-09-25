"""Real-name, paid-membership community with seeded hosts.

Studied from: dead-networks-20260916/report.md [EchoNYC]
(real-name, paid-membership text community; intentional seeding with strong
hosts; membership fee as commitment device against drive-by toxicity).

This is an original, from-scratch implementation for LEVI. A ``Commons``
requires real identity (name + affiliation attestation) and a paid membership
fee. The fee is a *commitment device*: cheap to a serious participant,
expensive to a drive-by troll. Founders *seed* the space by inviting strong
hosts first — the hosts' presence sets the tone before the general membership
arrives. Hosts can vouch for applicants (accelerating them) and suspend
members; members accrue standing through tenure, vouches, and sustained
participation. Members in poor standing can be put on probation; repeated
probations lapse the membership.

Real identity here is a mechanism, not a value judgment: it binds reputation
to a persistent person so that good behavior compounds and bad behavior has
a cost. The module stores only what the community operator records (names,
affiliations, payment receipts as opaque tokens) — it does no identity
verification itself.

Public surface:
- ``Commons``: ``seed_host``, ``apply``, ``vouch``, ``admit``,
  ``suspend`` / ``reinstate``, ``probate`` / ``lapse``, ``standing()``,
  ``census()``.
- ``Member``, ``CommonsError`` for embedding.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Mapping, Optional

ORIGIN = "levi-revival/paid-community"


class CommonsError(ValueError):
    """Raised when a commons operation cannot be honored."""


@dataclass
class Member:
    """One person in the commons: real name, fee receipt, host flag."""

    member_id: str
    name: str
    affiliation: str
    fee_paid: bool = False
    is_host: bool = False
    vouches: int = 0
    joined_at: str = ""
    probations: int = 0
    suspended: bool = False
    posts: int = 0

    def __post_init__(self) -> None:
        if not self.member_id or not self.name:
            raise CommonsError("member_id and name must be non-empty")


class Commons:
    """A paid, real-name commons with seeded hosts."""

    # Membership fee in fee-units; a commitment device, not a revenue model.
    FEE_UNITS = 1

    def __init__(self, name: str, max_probations: int = 2) -> None:
        if not name:
            raise CommonsError("commons name must be non-empty")
        self.name = name
        self.max_probations = max_probations
        self._members: Dict[str, Member] = {}
        self._applications: Dict[str, Dict[str, object]] = {}
        self._ledger: List[str] = []

    # -- ledger -----------------------------------------------------------
    def _log(self, entry: str) -> None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._ledger.append(f"{stamp} {entry}")

    def ledger(self) -> List[str]:
        return list(self._ledger)

    # -- seeding -----------------------------------------------------------
    def seed_host(self, member_id: str, name: str, affiliation: str) -> Member:
        """Invite a strong host: fee waived, host from day one."""
        if member_id in self._members:
            raise CommonsError(f"member {member_id!r} already exists")
        member = Member(
            member_id=member_id,
            name=name,
            affiliation=affiliation,
            fee_paid=True,  # seed waiver recorded as paid-by-sponsor
            is_host=True,
            joined_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._members[member_id] = member
        self._log(f"SEED host={member_id} name={name!r}")
        return member

    # -- membership --------------------------------------------------------
    def apply(
        self, member_id: str, name: str, affiliation: str
    ) -> Mapping[str, object]:
        """Record an application; requires identity + fee receipt."""
        if member_id in self._members:
            raise CommonsError(f"member {member_id!r} already exists")
        if member_id in self._applications:
            raise CommonsError(f"application for {member_id!r} already pending")
        if not name or not affiliation:
            raise CommonsError("real name and affiliation are required")
        self._applications[member_id] = {
            "name": name,
            "affiliation": affiliation,
            "fee_paid": False,
            "vouches": 0,
        }
        self._log(f"APPLY id={member_id} name={name!r}")
        return {"member_id": member_id, "status": "pending"}

    def pay_fee(self, member_id: str, receipt: str) -> None:
        """Record fee payment (receipt is an opaque token, never verified)."""
        app = self._applications.get(member_id)
        if app is None:
            raise CommonsError(f"no pending application for {member_id!r}")
        if not receipt:
            raise CommonsError("fee receipt must be non-empty")
        app["fee_paid"] = True
        self._log(f"FEE id={member_id}")

    def vouch(self, member_id: str, host_id: str) -> int:
        """A host vouches for an applicant; returns the vouch count."""
        app = self._applications.get(member_id)
        if app is None:
            raise CommonsError(f"no pending application for {member_id!r}")
        host = self._members.get(host_id)
        if host is None or not host.is_host or host.suspended:
            raise CommonsError(f"{host_id!r} is not an active host")
        app["vouches"] = int(app["vouches"]) + 1
        self._log(f"VOUCH id={member_id} by={host_id}")
        return int(app["vouches"])

    def admit(self, member_id: str, by_host: str) -> Member:
        """Admit an applicant: fee paid and (1 vouch or host approval)."""
        app = self._applications.get(member_id)
        if app is None:
            raise CommonsError(f"no pending application for {member_id!r}")
        host = self._members.get(by_host)
        if host is None or not host.is_host or host.suspended:
            raise CommonsError(f"{by_host!r} is not an active host")
        if not app["fee_paid"]:
            raise CommonsError(f"application {member_id!r} has not paid the fee")
        if int(app["vouches"]) < 1:
            raise CommonsError(
                f"application {member_id!r} needs at least one host vouch"
            )
        member = Member(
            member_id=member_id,
            name=str(app["name"]),
            affiliation=str(app["affiliation"]),
            fee_paid=True,
            vouches=int(app["vouches"]),
            joined_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._members[member_id] = member
        del self._applications[member_id]
        self._log(f"ADMIT id={member_id} by={by_host}")
        return member

    def promote_host(self, member_id: str, by_host: str) -> None:
        member = self._require_active(member_id)
        self._require_host(by_host)
        member.is_host = True
        self._log(f"PROMOTE id={member_id} to-host by={by_host}")

    # -- discipline ----------------------------------------------------------
    def record_post(self, member_id: str) -> None:
        member = self._require_active(member_id)
        member.posts += 1

    def probate(
        self, member_id: str, by_host: str, reason: str
    ) -> Mapping[str, object]:
        """Put a member on probation; at the limit, the membership lapses."""
        member = self._require_active(member_id)
        self._require_host(by_host)
        if member.is_host:
            raise CommonsError("hosts cannot be put on probation; suspend instead")
        member.probations += 1
        self._log(f"PROBATE id={member_id} count={member.probations} reason={reason!r}")
        if member.probations > self.max_probations:
            member.suspended = True
            self._log(f"LAPSE id={member_id} probations-exceeded")
            return {"status": "lapsed", "probations": member.probations}
        return {"status": "probation", "probations": member.probations}

    def suspend(self, member_id: str, by_host: str, reason: str) -> None:
        member = self._require_active(member_id, allow_suspended=True)
        self._require_host(by_host)
        member.suspended = True
        self._log(f"SUSPEND id={member_id} by={by_host} reason={reason!r}")

    def reinstate(self, member_id: str, by_host: str) -> None:
        self._require_host(by_host)
        member = self._members.get(member_id)
        if member is None:
            raise CommonsError(f"unknown member {member_id!r}")
        if not member.suspended:
            raise CommonsError(f"member {member_id!r} is not suspended")
        member.suspended = False
        member.probations = 0
        self._log(f"REINSTATE id={member_id} by={by_host}")

    # -- queries -------------------------------------------------------------
    def member(self, member_id: str) -> Optional[Member]:
        return self._members.get(member_id)

    def standing(self, member_id: str) -> int:
        """Standing score: hosts +10, each vouch +2, every 10 posts +1, each probation −5."""
        member = self._members.get(member_id)
        if member is None or member.suspended:
            return -1
        score = member.vouches * 2 + member.posts // 10 - member.probations * 5
        if member.is_host:
            score += 10
        return score

    def census(self) -> Mapping[str, int]:
        hosts = sum(1 for m in self._members.values() if m.is_host and not m.suspended)
        active = sum(1 for m in self._members.values() if not m.suspended)
        suspended = len(self._members) - active
        return {
            "members": len(self._members),
            "active": active,
            "hosts": hosts,
            "suspended": suspended,
            "pending_applications": len(self._applications),
        }

    def _require_active(self, member_id: str, allow_suspended: bool = False) -> Member:
        member = self._members.get(member_id)
        if member is None:
            raise CommonsError(f"unknown member {member_id!r}")
        if member.suspended and not allow_suspended:
            raise CommonsError(f"member {member_id!r} is suspended")
        return member

    def _require_host(self, host_id: str) -> Member:
        host = self._require_active(host_id)
        if not host.is_host:
            raise CommonsError(f"{host_id!r} is not a host")
        return host
