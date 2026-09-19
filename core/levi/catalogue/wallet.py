"""Credit wallet — free credits beyond the quota, incl. the ad option.

Doctrine (Chauncey, 2026-09-18): an OPTIONAL, MODERATE ad option lets
users earn more free credits. Moderate is policy, encoded here:

* AD_GRANT_CREDITS — credits earned per ad view (25: generous, not drips).
* AD_GRANTS_PER_DAY — max ad views that pay out per user per day (2:
  the option exists without becoming the product).
* WALLET_CAP — credits never stack past this (500: generous ceiling,
  prevents hoarding-as-currency).

This module models the MECHANISM and the DOCTRINE only. There is no ad
SDK, no ad network, no tracking: ``grant_for_ad_view`` records that the
user completed one ad view (reported by the client surface) and applies
the policy. What counts as "an ad view" is the presenting creation's
business, not this module's.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, Tuple

AD_GRANT_CREDITS = 25
AD_GRANTS_PER_DAY = 2
WALLET_CAP = 500


class CreditWallet:
    """Per-user credit balances with capped ad-view grants."""

    def __init__(self) -> None:
        self._balances: Dict[str, int] = {}
        # (user_id, YYYY-MM-DD) -> ad grants paid that day
        self._ad_grants: Dict[Tuple[str, str], int] = {}

    def balance(self, user_id: str) -> int:
        return self._balances.get(user_id, 0)

    def grant(self, user_id: str, amount: int, reason: str = "") -> Dict:
        """Add credits (admin/promo grant). Respects the wallet cap."""
        if amount < 0:
            raise ValueError("grant amount cannot be negative")
        before = self.balance(user_id)
        after = min(WALLET_CAP, before + amount)
        self._balances[user_id] = after
        return {
            "user_id": user_id,
            "granted": after - before,
            "capped": before + amount > WALLET_CAP,
            "balance": after,
            "reason": reason,
        }

    def grant_for_ad_view(self, user_id: str, day: str | None = None) -> Dict:
        """Pay out one completed ad view, enforcing the moderate cap."""
        day = day or date.today().isoformat()
        key = (user_id, day)
        used = self._ad_grants.get(key, 0)
        if used >= AD_GRANTS_PER_DAY:
            return {
                "user_id": user_id,
                "granted": 0,
                "denied": True,
                "reason": f"daily ad-grant cap reached ({AD_GRANTS_PER_DAY}/day)",
                "balance": self.balance(user_id),
            }
        self._ad_grants[key] = used + 1
        result = self.grant(user_id, AD_GRANT_CREDITS, reason="ad view")
        result["denied"] = False
        result["ad_views_today"] = used + 1
        return result

    def spend(self, user_id: str, amount: int) -> bool:
        """Spend credits; True on success, False when insufficient."""
        if amount < 0:
            raise ValueError("spend amount cannot be negative")
        if self.balance(user_id) < amount:
            return False
        self._balances[user_id] -= amount
        return True

    def to_dict(self) -> Dict:
        return {
            "balances": dict(self._balances),
            "ad_grants": {f"{u}\x1f{d}": n for (u, d), n in self._ad_grants.items()},
        }

    @staticmethod
    def from_dict(raw: Dict) -> "CreditWallet":
        wallet = CreditWallet()
        raw = raw or {}
        wallet._balances = {u: int(n) for u, n in raw.get("balances", {}).items()}
        for k, n in raw.get("ad_grants", {}).items():
            parts = k.split("\x1f")
            if len(parts) == 2:
                wallet._ad_grants[(parts[0], parts[1])] = int(n)
        return wallet
