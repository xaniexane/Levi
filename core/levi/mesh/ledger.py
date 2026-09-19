"""Contribution ledger — who gave what to the fleet.

Append-only JSONL: every accepted chunk records one ``contributed``
unit for the worker and one ``received`` unit for the farmer. Truth
lives here; it is founder-visible and never edited in place.

Contribute-to-earn: contributed units convert to free credits via
``settle_to_wallet``, using the SAME doctrine and caps as
``levi.catalogue.wallet.CreditWallet`` — the wallet's ``grant()``
enforces ``WALLET_CAP``, so mesh earnings can never overflow the
established credit policy. One unit = one accepted chunk.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Credits earned per contributed unit (one accepted chunk). Sized
# against the catalogue doctrine: an ad view pays 25; a chunk of real
# fleet work pays 5 — work outranks attention, attention stays viable.
MESH_CREDITS_PER_UNIT = 5


def default_ledger_path() -> Path:
    base = os.environ.get("LEVI_MESH_DIR", "")
    if base:
        return Path(base) / "ledger.jsonl"
    return Path.home() / ".levi" / "mesh" / "ledger.jsonl"


class ContributionLedger:
    """Append-only record of contributed/received work units."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = Path(path) if path else default_ledger_path()
        self._settled: Dict[str, int] = {}  # node_id -> units already paid out

    @property
    def path(self) -> Path:
        return self._path

    def record(
        self,
        node_id: str,
        kind: str,
        units: int,
        unit_kind: str = "compute",
        task_id: str = "",
    ) -> Dict:
        """Append one ledger entry. ``kind``: contributed | received."""
        if kind not in ("contributed", "received"):
            raise ValueError(f"bad kind {kind!r}")
        if units < 0:
            raise ValueError("units cannot be negative")
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "node_id": node_id,
            "kind": kind,
            "units": units,
            "unit_kind": unit_kind,
            "task_id": task_id,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
        return entry

    def _entries(self) -> List[Dict]:
        if not self._path.exists():
            return []
        out = []
        with open(self._path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
        return out

    def contributed(self, node_id: str) -> int:
        return sum(
            e["units"]
            for e in self._entries()
            if e["node_id"] == node_id and e["kind"] == "contributed"
        )

    def received(self, node_id: str) -> int:
        return sum(
            e["units"]
            for e in self._entries()
            if e["node_id"] == node_id and e["kind"] == "received"
        )

    def truth_view(self, founder: bool) -> List[Dict]:
        """Full raw ledger — founder-gated. Public views use the
        aggregate contributed()/received() queries instead."""
        if not founder:
            raise PermissionError("ledger truth view is founder-gated")
        return self._entries()

    def unsettled_units(self, node_id: str) -> int:
        """Contributed units not yet converted to credits."""
        return self.contributed(node_id) - self._settled.get(node_id, 0)

    def settle_to_wallet(self, wallet, user_id: str, node_id: str) -> Dict:
        """Convert unsettled contributions to wallet credits.

        ``wallet`` is a ``levi.catalogue.wallet.CreditWallet`` (duck-
        typed: needs ``grant(user_id, amount, reason)``). The wallet's
        own cap policy applies — mesh earnings respect it.
        """
        units = self.unsettled_units(node_id)
        credits = units * MESH_CREDITS_PER_UNIT
        result = wallet.grant(
            user_id, credits, reason=f"mesh contribution ({units} units)"
        )
        self._settled[node_id] = self._settled.get(node_id, 0) + units
        result["units_settled"] = units
        result["node_id"] = node_id
        return result
