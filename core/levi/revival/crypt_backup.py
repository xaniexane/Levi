"""Coldlocker — client-side encrypted backup economics and blinded manifests.

Studied from: hybrid-cost-cutting-combos-20260916-0006/report.md
[§7 Backup economics] (rclone crypt remote: encrypt locally, then park the
bytes on the cheapest object storage — Backblaze-style $6/TB — or on
already-paid consumer storage at $0 marginal).

This is an original, from-scratch implementation for LEVI. It has two halves:

1. ``BlindedManifest`` — the zero-knowledge shape: file paths are blinded
   with a keyed HMAC (sha256) so the remote side sees opaque blob names, and
   each blob's integrity is recorded. This is a *bookkeeping* model of the
   crypt-remote contract, not real encryption: it produces no ciphertext and
   MUST NOT be mistaken for cryptographic confidentiality. Real encryption
   would use an audited cipher library; this module only proves the manifest
   logic (name blinding, integrity binding, deterministic layout).

2. ``TierEconomics`` — the cost shape: storage tiers priced per TB-month,
   a backup set described by bytes and change rate, and honest arithmetic
   for monthly/yearly cost, the break-even horizon of a larger drive bought
   up front, and the marginal cost of using already-paid storage.

Public surface:
- ``BlindedManifest``: ``add``, ``blob_names``, ``verify``, ``total_bytes``.
- ``StorageTier``, ``BackupSet``, ``TierEconomics``: ``monthly``,
  ``yearly``, ``cheapest``, ``marginal_vs_owned``, ``breakeven_months``.
- ``BackupError`` for embedding.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/crypt_backup"


class BackupError(ValueError):
    """Raised when a backup plan or manifest operation cannot be honored."""


# ---------------------------------------------------------------------------
# 1. Blinded manifest (zero-knowledge bookkeeping model)
# ---------------------------------------------------------------------------


@dataclass
class BlobEntry:
    """One blinded remote blob: opaque name, size, integrity tag."""

    blob_name: str
    size_bytes: int
    integrity: str  # sha256 of the plaintext (recorded locally, never sent blindly)


class BlindedManifest:
    """Local-side record of what a crypt-style remote should hold.

    ``key`` blinds the paths. Keep it in the local vault; the remote never
    sees it, which is the whole point of the zero-knowledge shape.
    """

    def __init__(self, key: Optional[bytes] = None) -> None:
        self.key = key or secrets.token_bytes(32)
        self._blobs: Dict[str, BlobEntry] = {}
        self._reverse: Dict[str, str] = {}  # blob_name -> original path (local only)

    @staticmethod
    def _blind(key: bytes, path: str) -> str:
        return hmac.new(key, path.encode("utf-8"), hashlib.sha256).hexdigest()

    def add(self, path: str, data: bytes) -> BlobEntry:
        """Register a file for upload; returns its blinded blob entry."""
        if not path:
            raise BackupError("path must be non-empty")
        blob_name = self._blind(self.key, path)
        entry = BlobEntry(
            blob_name=blob_name,
            size_bytes=len(data),
            integrity=hashlib.sha256(data).hexdigest(),
        )
        self._blobs[path] = entry
        self._reverse[blob_name] = path
        return entry

    def blob_names(self) -> List[str]:
        """Opaque names the remote would see — no paths, no structure."""
        return sorted(e.blob_name for e in self._blobs.values())

    def resolve(self, blob_name: str) -> Optional[str]:
        """Map a blinded name back to its local path (local-only operation)."""
        return self._reverse.get(blob_name)

    def verify(self, path: str, data: bytes) -> bool:
        """Check live data against the recorded integrity tag."""
        entry = self._blobs.get(path)
        if entry is None:
            raise BackupError(f"no blob recorded for {path!r}")
        return hashlib.sha256(data).hexdigest() == entry.integrity

    def remove(self, path: str) -> None:
        entry = self._blobs.pop(path, None)
        if entry is None:
            raise BackupError(f"no blob recorded for {path!r}")
        self._reverse.pop(entry.blob_name, None)

    @property
    def total_bytes(self) -> int:
        return sum(e.size_bytes for e in self._blobs.values())

    @property
    def file_count(self) -> int:
        return len(self._blobs)


# ---------------------------------------------------------------------------
# 2. Tier economics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StorageTier:
    """One place bytes can live, priced per TB-month."""

    name: str
    dollars_per_tb_month: float
    egress_dollars_per_tb: float = 0.0
    notes: str = ""

    def __post_init__(self) -> None:
        if self.dollars_per_tb_month < 0:
            raise BackupError("tier price cannot be negative")
        if self.egress_dollars_per_tb < 0:
            raise BackupError("egress price cannot be negative")


@dataclass(frozen=True)
class BackupSet:
    """The bytes to protect: base size plus a monthly change rate."""

    base_tb: float
    monthly_change_tb: float = 0.0  # new/changed data retained each month
    months_retained: int = 12

    def __post_init__(self) -> None:
        if self.base_tb < 0 or self.monthly_change_tb < 0:
            raise BackupError("backup sizes cannot be negative")
        if self.months_retained < 1:
            raise BackupError("must retain at least one month")


@dataclass
class TierEconomics:
    """Honest cost arithmetic across storage tiers for one backup set."""

    backup: BackupSet
    tiers: List[StorageTier] = field(default_factory=list)

    def add_tier(self, tier: StorageTier) -> None:
        self.tiers.append(tier)

    def stored_tb(self, month: int) -> float:
        """Bytes stored in a given month (1-based), with retention applied."""
        if month < 1:
            raise BackupError("month must be >= 1")
        growth_months = min(month, self.backup.months_retained)
        return self.backup.base_tb + self.backup.monthly_change_tb * (growth_months - 1)

    def monthly(self, tier: StorageTier, month: int) -> float:
        return self.stored_tb(month) * tier.dollars_per_tb_month

    def yearly(self, tier: StorageTier, year: int = 1) -> float:
        if year < 1:
            raise BackupError("year must be >= 1")
        return sum(self.monthly(tier, (year - 1) * 12 + m) for m in range(1, 13))

    def cheapest(self, month: int = 1) -> Tuple[StorageTier, float]:
        """Cheapest tier for a given month and its cost."""
        if not self.tiers:
            raise BackupError("no tiers registered")
        priced = [(t, self.monthly(t, month)) for t in self.tiers]
        return min(priced, key=lambda p: p[1])

    def marginal_vs_owned(self, tier: StorageTier, month: int) -> float:
        """Cost of the tier minus the cost of already-paid storage ($0/TB)."""
        return self.monthly(tier, month)  # owned storage is $0 marginal

    def breakeven_months(
        self, buy_price_dollars: float, buy_tb: float, tier: StorageTier
    ) -> Optional[float]:
        """Months until buying a drive outright beats renting the tier.

        Returns None when the drive cannot hold the set or never breaks even
        within a 10-year horizon.
        """
        if buy_price_dollars <= 0 or buy_tb <= 0:
            raise BackupError("drive price and size must be positive")
        horizon = 120
        cumulative = 0.0
        for month in range(1, horizon + 1):
            if self.stored_tb(month) > buy_tb:
                return None  # outgrew the drive
            cumulative += self.monthly(tier, month)
            if cumulative >= buy_price_dollars:
                return float(month)
        return None

    def report(self, year: int = 1) -> Dict[str, float]:
        """Yearly cost per tier, for the given year."""
        return {t.name: round(self.yearly(t, year), 2) for t in self.tiers}
