# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Starmaker — creator suite: the factory's public face, in paper mode.

Avatar/photo pipeline MVP plus ad-monetization rails that run in
PAPER MODE: revenue flows are simulated and recorded against the
factory ledger so the money shape is proven before real money moves.

Unreplicable attribute — **paper-mint**: every simulated ad-revenue
event is minted as its own sealed receipt into a play-money-only
ledger — the ledger's balance is nothing but the sum of those sealed
events. Withdrawal-shaped requests are refused AND sealed as refusal
receipts (the attempt is recorded, the money never moves). The only
outward flow the rail permits is user attention-rewards — attention
earns; it is never harvested.

Honest limits: heavy compute is device-tiered — the MVP avatar
pipeline emits deterministic procedural descriptors, not rendered
images; the cap is on the label, not hidden in a footnote. No ad
spam, ever. NO real money moves anywhere in this module: any code
path shaped like a withdrawal raises.
"""

from __future__ import annotations

import hashlib
import threading
from typing import Any, Callable, Dict, List, Optional

from levi.dynasty.dna import AgentError, DynastyAgent, scrub_text
from levi.dynasty.wave.threadweaver import (
    _chain_locked,
    _checked_payload,
    _refuse_root_wipe,
)

_LEDGER = "factory"
_MODE = "paper"


def _cents(amount: Any, what: str) -> int:
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise AgentError(f"{what} must be an int of cents, got {amount!r}")
    if amount <= 0:
        raise AgentError(f"{what} must be positive, got {amount!r}")
    return amount


class Starmaker(DynastyAgent):
    """Mints the creator suite's paper-mode money shape."""

    agent_id = "starmaker"
    display_name = "Starmaker"
    owns = "creator suite"
    first_milestone = "avatar/photo pipeline MVP"
    proficiency = {"media": 10, "creator": 9, "money": 6, "general": 6}
    specialties = [
        "avatar/photo pipeline MVP",
        "paper-mode ad-monetization rails",
        "factory ledger (simulated revenue)",
    ]
    attributes = [
        {
            "name": "paper-mint",
            "assertion": (
                "every simulated ad-revenue event is minted as its own sealed "
                "receipt into a play-money-only ledger — the balance is "
                "nothing but the sum of sealed events; withdrawal-shaped "
                "requests are refused and sealed as refusal receipts; the "
                "only outward flow is user attention-rewards"
            ),
        },
    ]

    def __init__(self, home: Optional[object] = None) -> None:
        super().__init__(home)
        self._task_lock = threading.RLock()
        self._ledger: List[Dict[str, Any]] = []
        self._rewards: List[Dict[str, Any]] = []

    # -- guarded entry points (see threadweaver: same chain race) ------
    def act(self, task: Dict[str, Any]) -> Dict[str, Any]:
        with self._task_lock:
            return super().act(task)

    def do_task(
        self,
        kind: str,
        payload: Dict[str, Any],
        task: str = "",
        verify: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        with self._task_lock:
            _checked_payload(payload)
            with _chain_locked(self._home):
                return super().do_task(kind, payload, task, verify)

    def _ware_run_command(
        self, argv: List[str], timeout: int = 30
    ) -> Dict[str, object]:
        _refuse_root_wipe(argv)
        return super()._ware_run_command(argv, timeout)

    # -- paper-mint: the ad rail --------------------------------------
    def mint_ad_revenue(self, placement: str, amount_cents: int) -> Dict[str, Any]:
        """Mint one simulated ad-revenue event: sealed receipt, ledger
        entry. Play money only — ``real_money`` is always False."""
        placement = scrub_text(str(placement or "")).strip()
        amount_cents = _cents(amount_cents, "amount_cents")
        if not placement:
            raise AgentError("mint_ad_revenue needs a placement")
        with self._task_lock:
            receipt = self.do_task(
                "wave.ad_revenue",
                {
                    "ledger": _LEDGER,
                    "mode": _MODE,
                    "placement": placement,
                    "amount_cents": amount_cents,
                    "real_money": False,
                },
                task=f"starmaker:ad/{placement}",
            )
            self._ledger.append(
                {
                    "placement": placement,
                    "amount_cents": amount_cents,
                    "receipt_hash": receipt["receipt_hash"],
                    "real_money": False,
                }
            )
            self.note(
                f"paper-minted {amount_cents}c for {placement} "
                f"({receipt['receipt_hash'][:16]})"
            )
            return receipt

    def ledger_balance(self) -> Dict[str, Any]:
        """The balance is the sum of sealed paper-mint events — nothing else."""
        with self._task_lock:
            entries = [dict(e) for e in self._ledger]
        return {
            "ledger": _LEDGER,
            "mode": _MODE,
            "balance_cents": sum(e["amount_cents"] for e in entries),
            "entries": len(entries),
            "real_money": False,
        }

    def payout(self, placement: str, amount_cents: int) -> Dict[str, Any]:
        """There are no withdrawals in paper mode. The attempt is sealed
        as a refusal receipt, then refused — loudly."""
        placement = scrub_text(str(placement or "")).strip()
        amount_cents = _cents(amount_cents, "amount_cents")
        with self._task_lock:
            refusal = self.do_task(
                "wave.paper_refusal",
                {
                    "ledger": _LEDGER,
                    "mode": _MODE,
                    "attempted": "payout",
                    "placement": placement,
                    "amount_cents": amount_cents,
                    "real_money": False,
                },
                task=f"starmaker:refused-payout/{placement}",
            )
            self.note(f"refused payout of {amount_cents}c ({placement}) — paper mode")
        raise AgentError(
            "paper mode: the ad rail moves play-money only — withdrawals are "
            "refused and recorded "
            f"(refusal {refusal['receipt_hash'][:16]})"
        )

    def attention_reward(self, user: str, amount_cents: int) -> Dict[str, Any]:
        """The one outward flow: reward a user's attention, sealed."""
        user = scrub_text(str(user or "")).strip()
        amount_cents = _cents(amount_cents, "amount_cents")
        if not user:
            raise AgentError("attention_reward needs a user")
        with self._task_lock:
            receipt = self.do_task(
                "wave.attention_reward",
                {
                    "ledger": _LEDGER,
                    "mode": _MODE,
                    "user": user,
                    "amount_cents": amount_cents,
                    "real_money": False,
                },
                task=f"starmaker:reward/{user}",
            )
            self._rewards.append(
                {
                    "user": user,
                    "amount_cents": amount_cents,
                    "receipt_hash": receipt["receipt_hash"],
                }
            )
            self.note(f"attention reward {amount_cents}c to {user}")
            return receipt

    def rewards_total(self) -> Dict[str, Any]:
        """Total attention rewarded, in paper cents."""
        with self._task_lock:
            rewards = [dict(r) for r in self._rewards]
        return {
            "mode": _MODE,
            "total_cents": sum(r["amount_cents"] for r in rewards),
            "rewards": len(rewards),
            "real_money": False,
        }

    # -- avatar/photo pipeline MVP (procedural descriptors) ------------
    def avatar_draft(self, seed: str) -> Dict[str, Any]:
        """Draft an avatar descriptor from a seed — deterministic,
        procedural, no render engine in the MVP. The cap is on the
        label: this is a descriptor, not a render."""
        seed = scrub_text(str(seed or "")).strip()
        if not seed:
            raise AgentError("avatar_draft needs a seed")
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        palette = [f"#{digest[i * 2]:02x}{digest[i * 2 + 1]:02x}55" for i in range(3)]
        traits = [
            ["wayfinder", "mirthful", "solemn", "wild"][digest[6] % 4],
            ["ember", "tide", "stone", "gale"][digest[7] % 4],
            ["cartographer", "herald", "keeper", "wanderer"][digest[8] % 4],
        ]
        return {
            "seed": seed,
            "palette": palette,
            "traits": traits,
            "pipeline": "mvp-descriptor",
            "note": "procedural descriptor — no render engine in the MVP",
        }

    # -- jack-of-all-trades dispatch ----------------------------------
    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        shape = task.get("shape", "echo")
        if shape == "ad_revenue":
            return self.mint_ad_revenue(
                str(task.get("placement", "")), task.get("amount_cents", 0)
            )
        if shape == "payout":
            return self.payout(
                str(task.get("placement", "")), task.get("amount_cents", 0)
            )
        if shape == "attention_reward":
            return self.attention_reward(
                str(task.get("user", "")), task.get("amount_cents", 0)
            )
        if shape == "avatar_draft":
            return self.avatar_draft(str(task.get("seed", "")))
        if shape == "ledger":
            return self.ledger_balance()
        if shape == "rewards":
            return self.rewards_total()
        return super().handle(task)

    # -- first green task ----------------------------------------------
    def first_task(self) -> Dict[str, Any]:
        entry = self.mint_ad_revenue("factory-launch-rail", 125)
        return self.do_task(
            "wave.first_task",
            {
                "ledger": _LEDGER,
                "mode": _MODE,
                "entry": entry["receipt_hash"],
                "entries": 1,
                "balance_cents": self.ledger_balance()["balance_cents"],
                "real_money": False,
                "milestone": self.first_milestone,
            },
            task="starmaker:first",
        )
