# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Quartermaster — cross-cutting money, snapshots, receipts.

The Quartermaster keeps the books: every money move is paper until a
real rail is registered, the 70/30 split is structural (two separately
sealed legs per split, never one receipt moving both sides), and every
stage closes with a snapshot — a sealed note of what the chain looked
like and, crucially, what did NOT happen in it.

Unreplicable attribute — **absence attestation**: the Quartermaster
seals proofs of non-occurrence — a receipt attesting that no receipt
of a given kind exists in a chain window. An auditor verifies that
nothing happened (e.g. no real money ever moved) from the attestation
alone, without replaying the chain.

PAPER MODE is the standing posture: any money operation naming a rail
other than ``"paper"`` is refused loudly. There are no real money
rails in this build, by design.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.dynasty import receipts
from levi.dynasty.dna import AgentError, DynastyAgent, scrub_text

__all__ = ["Quartermaster", "AbsenceClaimError", "PAPER_RAIL"]


class AbsenceClaimError(AgentError):
    """An absence claim was made over a window where the kind DID occur."""


#: The only money rail that exists in this build.
PAPER_RAIL = "paper"

#: The standing split — enforced structurally, not arithmetically.
SPLIT_OWNER = 70
SPLIT_PLATFORM = 30


def _chain_receipts(home: Path) -> List[Dict[str, Any]]:
    """Read-only walk of the receipt chain (seq order)."""
    receipts_dir = home / "dynasty" / "receipts"
    if not receipts_dir.is_dir():
        return []
    out: List[Dict[str, Any]] = []
    for path in receipts_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data.get("seq"), int):
            out.append(data)
    out.sort(key=lambda r: r["seq"])
    return out


class Quartermaster(DynastyAgent):
    """The books: paper money, stage snapshots, receipt truth."""

    agent_id = "quartermaster"
    display_name = "Quartermaster"
    owns = "cross-cutting: money/snapshots/receipts"
    first_milestone = "Cybrus wiring, 70/30, stage snapshots"
    proficiency = {"money": 10, "receipts": 10, "snapshots": 9, "general": 6}
    specialties = [
        "paper-mode money ledger (no real rails)",
        "70/30 split enforcement, structural",
        "stage snapshots with absence attestation",
        "receipt-chain verification",
    ]
    attributes = [
        {
            "name": "Absence attestation",
            "assertion": (
                "The Quartermaster seals proofs of non-occurrence: a "
                "signed attestation that no receipt of a given kind "
                "exists in a chain window, verifiable without replaying "
                "the chain — so 'no real money ever moved' is itself a "
                "sealed, checkable fact."
            ),
        }
    ]

    #: Standing posture: paper only. Flipping this does not create a
    #: rail — there is no rail code in this build, by design.
    paper_mode: bool = True

    def __init__(self, home: Optional[Path] = None) -> None:
        super().__init__(home)
        self._paper_ledger: List[Dict[str, Any]] = []
        self._ledger_lock = threading.Lock()
        # Per-agent seal lock: receipts.mint_receipt reads the chain to
        # pick the next seq, so concurrent do_task calls would mint
        # colliding sequences. The lock serializes sealing per agent.
        self._seal_lock = threading.Lock()

    def do_task(
        self, kind: str, payload: Dict[str, Any], task: str = "", verify: Any = None
    ) -> Dict[str, Any]:
        with self._seal_lock:
            return super().do_task(kind, payload, task=task, verify=verify)

    # -- absence attestation -------------------------------------------
    def _attestation_sig(
        self, kind: str, start: int, end: int, count: int, at: str
    ) -> str:
        msg = f"{self.agent_id}|absence|{kind}|{start}|{end}|{count}|{at}".encode(
            "utf-8"
        )
        return hmac.new(
            receipts._keeper_key(),
            msg,
            hashlib.sha256,  # noqa: SLF001
        ).hexdigest()

    def verify_absence(self, kind: str, since_seq: int = 1) -> Dict[str, Any]:
        """Attest that no receipt of ``kind`` exists in the chain
        window ``[since_seq, tip]``.

        Returns a sealed attestation dict. Raises
        :class:`AbsenceClaimError` if the kind DID occur in the window
        — the claim is honest or it does not exist.
        """
        if not kind or not kind.strip():
            raise AgentError("verify_absence requires a non-empty kind")
        if not isinstance(since_seq, int) or since_seq < 1:
            raise AgentError("since_seq must be a positive int")
        chain = _chain_receipts(self._home)
        end = chain[-1]["seq"] if chain else 0
        hits = [
            r["seq"] for r in chain if r["seq"] >= since_seq and r.get("kind") == kind
        ]
        if hits:
            raise AbsenceClaimError(
                f"absence claim refused: kind {scrub_text(kind)!r} occurred "
                f"{len(hits)} time(s) in window [{since_seq}, {end}] "
                f"(first at seq {hits[0]})"
            )
        at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        attestation = {
            "agent": self.agent_id,
            "claim": "absence",
            "kind": kind,
            "window": [since_seq, end],
            "count": 0,
            "at": at,
        }
        attestation["sig"] = self._attestation_sig(kind, since_seq, end, 0, at)
        return attestation

    def check_attestation(self, attestation: Dict[str, Any]) -> bool:
        """Re-verify an absence attestation's seal. True iff valid."""
        try:
            expected = self._attestation_sig(
                attestation["kind"],
                attestation["window"][0],
                attestation["window"][1],
                attestation["count"],
                attestation["at"],
            )
        except (KeyError, TypeError, IndexError):
            return False
        return hmac.compare_digest(expected, str(attestation.get("sig", "")))

    # -- paper money ----------------------------------------------------
    def paper_transfer(
        self, amount_cents: int, memo: str = ""
    ) -> Dict[str, Dict[str, Any]]:
        """Record a PAPER transfer, split 70/30 at the structure level.

        The split is two separately sealed entries — owner leg and
        platform leg — so no single record ever moves both sides.
        Amounts are integer cents; negative or zero amounts refused.
        """
        if not isinstance(amount_cents, int) or isinstance(amount_cents, bool):
            raise AgentError("amount_cents must be an int")
        if amount_cents <= 0:
            raise AgentError("paper_transfer refuses non-positive amounts")
        owner_cents = (amount_cents * SPLIT_OWNER) // 100
        platform_cents = amount_cents - owner_cents
        at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        legs = {
            "owner": {
                "side": "owner",
                "cents": owner_cents,
                "rail": PAPER_RAIL,
                "memo": scrub_text(memo)[:120],
                "at": at,
            },
            "platform": {
                "side": "platform",
                "cents": platform_cents,
                "rail": PAPER_RAIL,
                "memo": scrub_text(memo)[:120],
                "at": at,
            },
        }
        with self._ledger_lock:
            self._paper_ledger.append(
                {"legs": legs, "total_cents": amount_cents, "at": at}
            )
        self.note(
            f"paper transfer {amount_cents}c split "
            f"{owner_cents}/{platform_cents} (70/30)"
        )
        return {side: dict(leg) for side, leg in legs.items()}

    def paper_balance(self) -> Dict[str, int]:
        """Paper totals per side — informational only, never money."""
        owner = platform = 0
        with self._ledger_lock:
            for entry in self._paper_ledger:
                owner += entry["legs"]["owner"]["cents"]
                platform += entry["legs"]["platform"]["cents"]
        return {"owner_cents": owner, "platform_cents": platform}

    # -- snapshots -------------------------------------------------------
    def stage_snapshot(self, label: str) -> Dict[str, Any]:
        """Seal a stage snapshot: chain count, absence claims, split."""
        if not label or not label.strip():
            raise AgentError("stage_snapshot requires a non-empty label")
        count = receipts.verify_chain()
        absence = self.verify_absence("money.real")
        return self.do_task(
            "quartermaster.snapshot",
            {
                "label": scrub_text(label.strip())[:120],
                "chain_receipts": count,
                "chain_green": True,
                "absence_attestations": [absence],
                "split": f"{SPLIT_OWNER}/{SPLIT_PLATFORM}",
                "mode": PAPER_RAIL,
            },
            task=f"quartermaster:snapshot:{label.strip()[:40]}",
        )

    # -- domain ----------------------------------------------------------
    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        shape = task.get("shape")
        if shape == "money":
            rail = task.get("rail", PAPER_RAIL)
            if rail != PAPER_RAIL:
                raise AgentError(
                    f"paper mode: real money rail {scrub_text(str(rail))!r} "
                    "refused — no real rails exist in this build"
                )
            op = task.get("op", "transfer")
            if op == "transfer":
                return {
                    "transfer": self.paper_transfer(
                        task.get("amount_cents", 0), task.get("memo", "")
                    )
                }
            if op == "balance":
                return {"balance": self.paper_balance()}
            raise AgentError(f"unknown money op {scrub_text(str(op))!r}")
        if shape == "snapshot":
            return {"snapshot": self.stage_snapshot(task.get("label", "stage"))}
        if shape == "absence":
            return {
                "attestation": self.verify_absence(
                    task.get("kind", "money.real"),
                    task.get("since_seq", 1),
                )
            }
        return super().handle(task)

    # -- first green task -------------------------------------------------
    def first_task(self) -> Dict[str, Any]:
        """Verify the chain, seal the absence of real money, and take
        the first stage snapshot — paper mode, no real rails."""
        count = receipts.verify_chain()
        absence = self.verify_absence("money.real")
        note = (
            f"stage snapshot: {count} receipts verified, chain green, "
            "paper mode — no real money rails, 70/30 structural"
        )
        self.note(note)
        return self.do_task(
            "wave.first_task",
            {
                "agent": self.agent_id,
                "milestone": scrub_text(self.first_milestone),
                "verified_receipts": count,
                "snapshot_note": note,
                "absence_attestation": absence,
                "split": f"{SPLIT_OWNER}/{SPLIT_PLATFORM}",
                "mode": PAPER_RAIL,
            },
            task="quartermaster:first",
        )
