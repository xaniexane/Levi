"""The series ledger: each year's N, in writing, hash-chained.

Keeper's canon (2026-09-18): the annual NFT mint cap is 1,000 copies per
year MINIMUM — "a thousand at least". His reasoning, in his words: with
billions of people worldwide, a thousand copies stay scarce enough to be
valuable and still sell enough to be very profitable.

The keeper may set a HIGHER N for any year, in writing, before mint. N
below the floor is refused unless his explicit override is flagged ON the
ledger record itself — a sub-floor year is never silent. Each year records
exactly once: a published N is law, never re-decided.

The ledger is the gate between the decision and the mint: a series cannot
mint until its year's N is banked here (see ``treasury.Treasury``). The
published cap IS the banked N.

PAPER ONLY. Receipts are hash-chained, the same discipline as the
treasury's receipts.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .economics import ANNUAL_SERIES_CAP_MIN, NftEconomicsError, series_id_for

FORM_NAME = "genesis.nft.ledger"


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SeriesLedger:
    """Banked, hash-chained record of each year's decided N."""

    def __init__(self) -> None:
        self._years: Dict[int, Dict[str, Any]] = {}
        self._receipts: List[Dict[str, Any]] = []
        self._seq = 0
        self._prev_hash = "0" * 64

    # -- receipts --------------------------------------------------------

    def _receipt(self, kind: str, detail: Dict[str, Any]) -> Dict[str, Any]:
        self._seq += 1
        body = {
            "seq": self._seq,
            "form": FORM_NAME,
            "kind": kind,
            "detail": detail,
            "prev": self._prev_hash,
        }
        digest = hashlib.sha256(
            (self._prev_hash + _canonical(body)).encode("utf-8")
        ).hexdigest()
        receipt = dict(body, hash=digest)
        self._prev_hash = digest
        self._receipts.append(receipt)
        return receipt

    def verify_ledger(self) -> bool:
        """Re-walk the hash chain. True iff every link is intact."""
        prev = "0" * 64
        for r in self._receipts:
            body = {k: v for k, v in r.items() if k != "hash"}
            if body.get("prev") != prev:
                return False
            digest = hashlib.sha256(
                (prev + _canonical(body)).encode("utf-8")
            ).hexdigest()
            if digest != r["hash"]:
                return False
            prev = digest
        return True

    # -- the written decision ----------------------------------------------

    def record_year(
        self,
        year: int,
        n: int,
        *,
        decided_by: str = "keeper",
        decided_at: Optional[str] = None,
        override: bool = False,
        note: str = "",
    ) -> Dict[str, Any]:
        """Bank the year's N, in writing. Fail-closed.

        N below ``ANNUAL_SERIES_CAP_MIN`` is refused unless ``override`` is
        True — the override is banked ON the record (``sub_floor_override``)
        so a sub-floor year can never pass silently. Each year records once:
        a published N is never re-decided.
        """
        series_id = series_id_for(year)  # validates the year
        year = int(year)
        n = int(n)
        if year in self._years:
            raise NftEconomicsError(
                "N for %s is already banked — a published N is law, never re-decided"
                % series_id
            )
        if n <= 0:
            raise NftEconomicsError("N must be positive")
        if n < ANNUAL_SERIES_CAP_MIN and not override:
            raise NftEconomicsError(
                "N=%d is below the keeper's floor of %d for %s — "
                "refused without his explicit override" % (n, ANNUAL_SERIES_CAP_MIN, series_id)
            )
        if not decided_by:
            raise NftEconomicsError("decided_by is required — in writing means named")
        record = {
            "year": year,
            "series_id": series_id,
            "n": n,
            "decided_by": decided_by,
            "decided_at": decided_at or _utcnow(),
            "sub_floor_override": bool(override and n < ANNUAL_SERIES_CAP_MIN),
            "note": note,
        }
        self._years[year] = record
        return self._receipt("year-recorded", record)

    # -- the randomized draw -------------------------------------------------

    def record_draw_seed(self, year: int, seed: str) -> Dict[str, Any]:
        """Bank the draw seed BEFORE the draw is run.

        The seed cannot be picked to favor a pack if it is committed first.
        One seed per year; the draw itself is banked separately after it runs.
        """
        year = int(year)
        series_id = series_id_for(year)  # validates the year
        if not (seed or "").strip():
            raise NftEconomicsError("draw seed is required — banked before the draw")
        for r in self._receipts:
            if r["kind"] == "draw-seed" and r["detail"]["year"] == year:
                raise NftEconomicsError(
                    "draw seed for %s is already banked — seeds are committed once"
                    % series_id
                )
        return self._receipt("draw-seed", {"year": year, "series_id": series_id,
                                           "seed": seed})

    def record_draw(self, year: int, drawn_pack_ids: List[str],
                    keeper_reserve: Optional[str] = None) -> Dict[str, Any]:
        """Bank the draw result. The seed must already be banked, and the
        draw fills the mint exactly, no more, no fewer.

        ``keeper_reserve`` is the keeper's named copy — one per series, out
        of N not on top of it: with a reserve, ``drawn_pack_ids`` must hold
        exactly N-1 and the reserve must not be among them.
        """
        year = int(year)
        series_id = series_id_for(year)
        n = self.require_n(year)
        seed = None
        for r in self._receipts:
            if r["kind"] == "draw-seed" and r["detail"]["year"] == year:
                seed = r["detail"]["seed"]
        if seed is None:
            raise NftEconomicsError(
                "no draw seed banked for %s — the seed is committed before the draw"
                % series_id
            )
        for r in self._receipts:
            if r["kind"] == "draw-result" and r["detail"]["year"] == year:
                raise NftEconomicsError(
                    "draw for %s is already banked — one draw per year" % series_id
                )
        drawn = list(drawn_pack_ids)
        reserve = (keeper_reserve or "").strip() or None
        expected = n - 1 if reserve else n
        if reserve and reserve in drawn:
            raise NftEconomicsError(
                "keeper's reserve cannot also be in the drawn packs"
            )
        if len(drawn) != expected:
            raise NftEconomicsError(
                "draw must fill the banked N exactly: drew %d, need %d for %s%s"
                % (len(drawn), expected, series_id,
                   " (N-1 with the keeper's reserve)" if reserve else "")
            )
        if len(set(drawn)) != len(drawn):
            raise NftEconomicsError("drawn pack ids must be unique")
        return self._receipt("draw-result", {
            "year": year, "series_id": series_id, "seed": seed,
            "keeper_reserve": reserve,
            "drawn_pack_ids": drawn, "drawn_count": len(drawn),
            "minted_total": len(drawn) + (1 if reserve else 0),
        })

    def record_master_token(
        self,
        year: int,
        master_token_id_hex: str,
        registry_hash: str,
        token_count: int,
    ) -> Dict[str, Any]:
        """Bank the NFT² master token — minted last, one per year.

        The master closes the series: the draw must already be banked and
        ``token_count`` must equal the banked N, proving the registry the
        master carries is complete.
        """
        year = int(year)
        series_id = series_id_for(year)
        n = self.require_n(year)
        drew = False
        for r in self._receipts:
            if r["kind"] == "draw-result" and r["detail"]["year"] == year:
                drew = True
            if r["kind"] == "master-token" and r["detail"]["year"] == year:
                raise NftEconomicsError(
                    "master token for %s is already banked — one per year"
                    % series_id
                )
        if not drew:
            raise NftEconomicsError(
                "no draw banked for %s — the master is minted last" % series_id
            )
        if int(token_count) != n:
            raise NftEconomicsError(
                "master registry holds %d tokens, banked N is %d for %s — "
                "the master carries the complete mint" % (token_count, n, series_id)
            )
        if not (master_token_id_hex or "").strip():
            raise NftEconomicsError("master token id is required")
        if not (registry_hash or "").strip():
            raise NftEconomicsError("registry hash is required")
        return self._receipt("master-token", {
            "year": year, "series_id": series_id,
            "master_token_id_hex": master_token_id_hex,
            "registry_hash": registry_hash,
            "token_count": int(token_count),
        })

    def record_archive(
        self,
        year: int,
        pack_hashes: Dict[str, str],
    ) -> Dict[str, Any]:
        """Bank the keeper's archive — his master set of the year's packs.

        The archive is NOT tokens and NOT licenses: it is the keeper's
        permanent backup and working set (the negatives, not the prints).
        Archive copies can never be minted, sold, or transferred as tokens
        or licenses — that law protects the one-copy promise to buyers.

        Banked at series close like the master: the draw must be banked and
        the archive must cover exactly the banked N packs. One per year.
        """
        year = int(year)
        series_id = series_id_for(year)
        n = self.require_n(year)
        drew = False
        for r in self._receipts:
            if r["kind"] == "draw-result" and r["detail"]["year"] == year:
                drew = True
            if r["kind"] == "keeper-archive" and r["detail"]["year"] == year:
                raise NftEconomicsError(
                    "keeper archive for %s is already banked — one per year"
                    % series_id
                )
        if not drew:
            raise NftEconomicsError(
                "no draw banked for %s — the archive closes the series" % series_id
            )
        if not pack_hashes:
            raise NftEconomicsError("archive is empty — nothing to back up")
        if len(pack_hashes) != n:
            raise NftEconomicsError(
                "archive holds %d packs, banked N is %d for %s — "
                "the keeper backs up the whole series" % (len(pack_hashes), n, series_id)
            )
        for pack_id, h in pack_hashes.items():
            if not (pack_id or "").strip():
                raise NftEconomicsError("archive pack ids must be non-empty")
            if len(h or "") != 64 or any(
                ch not in "0123456789abcdef" for ch in (h or "").lower()
            ):
                raise NftEconomicsError(
                    "archive hash for %r must be a 64-char hex sha256" % pack_id
                )
        return self._receipt("keeper-archive", {
            "year": year, "series_id": series_id,
            "packs": {pid: h.lower() for pid, h in pack_hashes.items()},
            "pack_count": len(pack_hashes),
            "transferable": False,
            "mintable": False,
        })

    # -- reads ---------------------------------------------------------------

    def get_n(self, year: int) -> Optional[int]:
        """The banked N for a year, or None if the year is undecided."""
        rec = self._years.get(int(year))
        return rec["n"] if rec is not None else None

    def require_n(self, year: int) -> int:
        """The banked N for a year, or fail — no N on the books, no mint."""
        n = self.get_n(year)
        if n is None:
            raise NftEconomicsError(
                "no N banked for %s — the keeper sets N in writing before mint"
                % series_id_for(year)
            )
        return n

    def year_record(self, year: int) -> Optional[Dict[str, Any]]:
        """A copy of the year's banked record, or None."""
        rec = self._years.get(int(year))
        return dict(rec) if rec is not None else None

    def years(self) -> List[int]:
        """Every year with a banked N, ascending."""
        return sorted(self._years)

    def receipts(self) -> List[Dict[str, Any]]:
        """Copies of the hash-chained receipts."""
        return [dict(r) for r in self._receipts]
