# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Corroboration gates — the two-agent rule, enforced for real.

:mod:`levi.dynasty.roster` states the rule (owner + independent
verifier, solo ships never). This module is the enforcement:
:class:`CorroborationGate.advance` re-verifies every signoff
cryptographically — HMAC-SHA256 over ``agent_id|milestone|at`` with
the keeper key — and refuses forged, replayed, duplicated, stale, or
tampered signoffs. On success it mints a sealed ``gate.advance``
receipt and returns it.

Nothing here trusts a signoff dict at face value. The signature is
recomputed from the fields; the fields are re-checked against the
milestone being advanced.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Collection, Dict, List, Optional

from levi.dynasty import receipts
from levi.dynasty.dna import AgentError, scrub_text

__all__ = ["GateError", "CorroborationGate"]


class GateError(AgentError):
    """A corroboration gate refused to advance. Typed, never bare."""


class CorroborationGate:
    """The two-agent rule, enforced cryptographically.

    :meth:`advance` requires at least two DISTINCT signers, the
    milestone owner among them, every signature re-verified against
    the keeper key, and every ``at`` timestamp fresh (within 24 hours
    of now, with a 60-second future skew allowance). Any violation
    raises :class:`GateError`.
    """

    #: A signoff older than this is stale and refused.
    MAX_AGE = timedelta(hours=24)
    #: A signoff this far in the future is tampered and refused.
    FUTURE_SKEW = timedelta(seconds=60)

    _REQUIRED_FIELDS = ("agent_id", "milestone", "at", "sig")

    @classmethod
    def _parse_at(cls, at: str) -> datetime:
        try:
            moment = datetime.fromisoformat(at)
        except (ValueError, TypeError) as exc:
            raise GateError(f"signoff 'at' is not ISO-8601: {at!r}") from exc
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment

    @classmethod
    def _verify_sig(cls, signoff: Dict[str, Any]) -> None:
        agent_id = signoff["agent_id"]
        milestone = signoff["milestone"]
        at = signoff["at"]
        msg = f"{agent_id}|{milestone}|{at}".encode("utf-8")
        expected = hmac.new(
            receipts._keeper_key(),
            msg,
            hashlib.sha256,  # noqa: SLF001
        ).hexdigest()
        if not hmac.compare_digest(expected, str(signoff["sig"])):
            raise GateError(
                f"forged signature from {agent_id!r}: "
                "HMAC over agent_id|milestone|at does not verify"
            )

    @classmethod
    def advance(
        cls,
        milestone: str,
        signoffs: List[Dict[str, Any]],
        owner: str,
        native_ids: Optional[Collection[str]] = None,
    ) -> Dict[str, Any]:
        """Advance ``milestone`` past the corroboration gate.

        ``signoffs`` are ``sign_milestone`` ware outputs. ``owner`` is
        the milestone owner's agent id and must be among the signers.
        ``native_ids`` optionally names the native wave agents; when
        given, at least one signer must be native — integrated
        (foreign) minds may do the work but never corroborate a ship
        on their own.

        Returns the sealed ``gate.advance`` receipt.
        """
        if not milestone or not str(milestone).strip():
            raise GateError("milestone must be a non-empty string")
        # Scrubbed once, up front: the milestone lands in the sealed
        # gate receipt, so markers must never reach it.
        milestone = scrub_text(str(milestone).strip())
        if not isinstance(signoffs, list) or not signoffs:
            raise GateError("corroboration requires signoffs; got none")
        if not owner or not str(owner).strip():
            raise GateError("corroboration requires the milestone owner")

        seen: Dict[str, Dict[str, Any]] = {}
        now = datetime.now(timezone.utc)
        for i, signoff in enumerate(signoffs):
            if not isinstance(signoff, dict):
                raise GateError(f"signoff {i} is not a dict")
            for field in cls._REQUIRED_FIELDS:
                value = signoff.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise GateError(f"signoff {i} missing non-empty field {field!r}")
            if signoff["milestone"] != milestone:
                raise GateError(
                    f"signoff {i} is for milestone "
                    f"{scrub_text(signoff['milestone'])!r}, not "
                    f"{scrub_text(milestone)!r}: replayed signoffs are refused"
                )
            agent_id = signoff["agent_id"]
            if agent_id in seen:
                raise GateError(
                    f"duplicate signoff from {agent_id!r}: "
                    "one agent agreeing with itself is not corroboration"
                )
            seen[agent_id] = signoff
            cls._verify_sig(signoff)
            moment = cls._parse_at(signoff["at"])
            if moment > now + cls.FUTURE_SKEW:
                raise GateError(
                    f"signoff from {agent_id!r} is dated in the future "
                    f"({signoff['at']!r}): tampered clock refused"
                )
            if now - moment > cls.MAX_AGE:
                raise GateError(
                    f"signoff from {agent_id!r} is stale "
                    f"({signoff['at']!r}): older than 24h refused"
                )

        if len(seen) < 2:
            raise GateError(
                f"only {len(seen)} distinct signer(s): "
                "the gate demands at least two distinct agents"
            )
        if owner not in seen:
            raise GateError(
                f"milestone owner {owner!r} is not among the signers: "
                "owner sign-off is required"
            )
        if native_ids is not None:
            native = set(native_ids)
            if not any(agent_id in native for agent_id in seen):
                raise GateError(
                    "no native wave agent among the signers: "
                    "integrated minds may not corroborate a ship alone"
                )

        signers = sorted(seen)
        try:
            receipt = receipts.mint_receipt(
                "gate.advance",
                {
                    "milestone": milestone,
                    "owner": owner,
                    "signers": signers,
                    "signoff_count": len(signers),
                },
                task=f"gate.advance:{milestone}",
            )
        except receipts.ReceiptError as exc:
            raise GateError(f"gate seal failed: {exc}") from exc
        return receipt
