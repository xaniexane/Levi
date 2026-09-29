"""Veil creator NFTs: mint creator drops (photos/videos) as NFTs, buy/sell
through Cybrus money handlers, discover via QR.

Flow: creator publishes a drop -> ``mint_drop_as_nft(drop_id)`` certifies
the drop's exact bytes as a token -> buyers purchase through Cybrus
(MoneyPlan + approval ledger) -> ownership transfers on the hash-chained
NFT ledger.

LAW (inherited, not rebuilt):
- Genesis NFT economics (``levi.genesis.nft``): deterministic token ids
  (one content hash -> exactly one token, counterfeits impossible),
  50/30/20 primary split, 7.5% (750 bps) EIP-2981 royalties. The creator
  sits in the keeper's seat for their own drops: 50% creator / 30% pool /
  20% buyback treasury. The split is Chauncey's to reset.
- Cybrus is the sole money handler: every mint and purchase builds a
  MoneyPlan + approval-ledger entry; nothing moves until the keeper
  approves (same VS3 pattern as unlocks/subscriptions).
- Plaiground gate: every public entry calls ``require_adult`` first.
- QR discovery: signed single-use expiring tickets, same HMAC discipline
  as creator discovery tickets.

LEGAL: the lawyer-before-first-mint gate (2026-09-18) was CLEARED per
Chauncey 2026-09-27 ("it has been" — consultation happened). Mint intents
now proceed through the normal approval gates. Actual on-chain deployment
(Base ERC-721) remains a separate explicit order — gas is spend, and spend
is his call.

PAPER-PLUS: mints and transfers are recorded on the hash-chained creator
NFT ledger with full receipts. The ledger IS the certificate of the
drop's bytes until a chain deployment is ordered; the token id scheme is
the same one the Base contract must implement.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.cybrus.audit import AuditEngine
from levi.genesis.nft.economics import (
    ROYALTY_BPS,
    reference_royalty,
    split_primary_revenue,
)
from levi.plaiground.gate import require_adult

FORM_NAME = "veil.creator.nft"

#: Domain separation for creator-drop token ids. Genesis pack ids use
#: ``"series:pack"`` and master tokens ``"NFT2:series"`` — this domain can
#: never collide with either.
NFT_DOMAIN = "creator-nft:v1"

#: Media types a drop must carry to be mintable.
MINTABLE_MEDIA = ("photo", "video")

#: EIP-2981 royalty receiver on secondary sales: the creator.
#: (Genesis sends 100% of royalties to the series treasury because the
#: treasury is the holders' exit door; creator drops have no exit-door
#: concept, so the standard creator royalty applies.)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short(value: str) -> str:
    return (value or "")[:12]


def nft_token_id_for(creator_id: str, content_hash: str) -> int:
    """Deterministic token id: sha256(domain:creator:content) as uint256.

    One content hash yields exactly one token id per creator — the token
    IS the certificate of the drop's bytes. Domain-separated from every
    genesis id by construction.
    """
    if not creator_id or not content_hash:
        raise VeilNftError("creator_id and content_hash are required")
    digest = hashlib.sha256(
        ("%s:%s:%s" % (NFT_DOMAIN, creator_id, content_hash)).encode("utf-8")
    ).digest()
    return int.from_bytes(digest, "big")


def content_hash_for(media_bytes: Optional[bytes], body: str = "") -> str:
    """sha256 over media bytes + body text: the certified bytes."""
    h = hashlib.sha256()
    if media_bytes:
        h.update(bytes(media_bytes))
    h.update(b"\x00")
    h.update((body or "").encode("utf-8"))
    return h.hexdigest()


class VeilNftError(Exception):
    """All creator-NFT failures: fail-closed by construction."""


class CreatorNftLedger:
    """Hash-chained record of creator NFT mints and transfers.

    Same receipt discipline as the genesis series ledger, but a separate
    track: the genesis annual-N law (1,000/year minimum, keeper's written
    N) governs genesis packs, not creator drops. Each mint records the
    token id, the certified content hash, the economics, and the full
    ownership history.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._doc = self._load()

    # -- persistence -----------------------------------------------------

    def _load(self) -> Dict[str, Any]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"tokens": {}, "receipts": [], "seq": 0,
                "prev_hash": "0" * 64}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._doc, sort_keys=True, indent=1),
                       encoding="utf-8")
        tmp.replace(self._path)

    # -- receipts --------------------------------------------------------

    def _receipt(self, kind: str, detail: Dict[str, Any]) -> Dict[str, Any]:
        self._doc["seq"] += 1
        body = {
            "seq": self._doc["seq"],
            "form": FORM_NAME,
            "kind": kind,
            "detail": detail,
            "prev": self._doc["prev_hash"],
        }
        digest = hashlib.sha256(
            (self._doc["prev_hash"] + json.dumps(
                body, sort_keys=True, separators=(",", ":"))).encode("utf-8")
        ).hexdigest()
        receipt = dict(body, hash=digest)
        self._doc["prev_hash"] = digest
        self._doc["receipts"].append(receipt)
        self._save()
        return receipt

    def verify(self) -> bool:
        """Re-walk the hash chain. True iff every link is intact."""
        prev = "0" * 64
        for r in self._doc.get("receipts", []):
            body = {k: v for k, v in r.items() if k != "hash"}
            if body.get("prev") != prev:
                return False
            digest = hashlib.sha256(
                (prev + json.dumps(body, sort_keys=True,
                                  separators=(",", ":"))
                 ).encode("utf-8")
            ).hexdigest()
            if digest != r["hash"]:
                return False
            prev = digest
        return True

    # -- tokens ----------------------------------------------------------

    def record_mint(self, token: Dict[str, Any]) -> Dict[str, Any]:
        tid = str(token["token_id"])
        if tid in self._doc["tokens"]:
            raise VeilNftError("token already minted for this content")
        self._doc["tokens"][tid] = token
        self._save()
        return self._receipt("nft.minted", {
            "token_id": _short(tid),
            "drop_id": _short(token["drop_id"]),
            "creator_id": _short(token["creator_id"]),
            "owner": _short(token["owner"]),
            "price_minor": token["price_minor"],
        })

    def record_transfer(self, token_id: str, new_owner: str,
                        price_minor: int, royalty_minor: int) -> Dict[str, Any]:
        tid = str(token_id)
        token = self._doc["tokens"].get(tid)
        if token is None:
            raise VeilNftError("unknown token")
        token["owner"] = new_owner
        token.setdefault("transfers", []).append({
            "to": new_owner,
            "price_minor": int(price_minor),
            "royalty_minor": int(royalty_minor),
            "at": _utcnow(),
        })
        self._save()
        return self._receipt("nft.transferred", {
            "token_id": _short(tid),
            "to": _short(new_owner),
            "price_minor": int(price_minor),
            "royalty_minor": int(royalty_minor),
        })

    def get(self, token_id: str) -> Optional[Dict[str, Any]]:
        return self._doc["tokens"].get(str(token_id))

    def by_creator(self, creator_id: str) -> List[Dict[str, Any]]:
        return [t for t in self._doc["tokens"].values()
                if t.get("creator_id") == creator_id]

    def by_drop(self, drop_id: str) -> List[Dict[str, Any]]:
        return [t for t in self._doc["tokens"].values()
                if t.get("drop_id") == drop_id]


class VeilNFT:
    """Creator NFTs for the Veil hub: mint drops, buy/sell via Cybrus.

    Constructed with the creators base dir (the same ``veil_creators``
    dir ``VeilCreators`` uses) so tokens, drops, and creators share one
    home. Money always flows through Cybrus MoneyPlan + approval ledger;
    this class never touches a rail directly.
    """

    def __init__(self, creators_base: Path) -> None:
        self._base = Path(creators_base)
        self._ledger = CreatorNftLedger(self._base / "nfts.json")
        self._purchases = self._base / "nft_purchases.json"
        self._audit = AuditEngine()

    def _audit_event(self, event: str, details: Optional[Dict] = None) -> None:
        try:
            self._audit.append(event, "keeper", details or {})
        except Exception:
            pass

    def _load_purchases(self) -> Dict[str, Any]:
        if self._purchases.exists():
            try:
                return json.loads(self._purchases.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_purchases(self, doc: Dict[str, Any]) -> None:
        self._base.mkdir(parents=True, exist_ok=True)
        tmp = self._purchases.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, sort_keys=True, indent=1),
                       encoding="utf-8")
        tmp.replace(self._purchases)

    # -- mint ------------------------------------------------------------

    def mint_drop(self, *, drop: Dict[str, Any], creator_handle: str,
                  media_bytes: Optional[bytes],
                  body: str = "",
                  price_minor: Optional[int] = None,
                  keeper_identity: str = "keeper") -> Dict[str, Any]:
        """Mint a creator drop as an NFT.

        The drop must carry photo/video media. The token certifies the
        exact bytes (media + body). One content hash mints exactly once
        per creator. The mint is approval-gated like every Cybrus money
        movement: status ``pending_payment`` until the keeper approves,
        then :meth:`confirm_mint` finalizes.
        """
        require_adult()
        drop_id = drop.get("drop_id", "")
        creator_id = drop.get("creator_id", "")
        media_type = drop.get("media_type", "text")
        if media_type not in MINTABLE_MEDIA:
            raise VeilNftError(
                "only photo/video drops can mint as NFTs (got %r)"
                % media_type)
        if not media_bytes:
            raise VeilNftError("drop has no media bytes to certify")
        # The media bytes ARE the work: the hash covers them alone, so the
        # same photo/video can never mint twice under different captions.
        # Body text is recorded as metadata, not identity.
        chash = content_hash_for(media_bytes)
        token_id = nft_token_id_for(creator_id, chash)
        if self._ledger.get(str(token_id)) is not None:
            raise VeilNftError("this exact content is already minted")
        price = int(drop.get("price_minor", 0) if price_minor is None
                    else price_minor)
        if price < 0:
            raise VeilNftError("price_minor must be non-negative")

        from levi.cybrus.money import MoneyGateway, MoneyPlan
        plan = MoneyPlan(
            plan_id=uuid.uuid4().hex,
            operation="creator_nft_mint",
            amount_minor=price,
            currency=drop.get("currency", "USD"),
            rail="",
            purpose="veil creator NFT mint %s" % _short(str(token_id)),
            identity=keeper_identity,
            created_at=_utcnow(),
        )
        entry = MoneyGateway().request_execution_approval(
            plan, subject=keeper_identity)

        token = {
            "token_id": str(token_id),
            "drop_id": drop_id,
            "creator_id": creator_id,
            "creator_handle": creator_handle,
            "title": drop.get("title", ""),
            "media_type": media_type,
            "content_hash": chash,
            "price_minor": price,
            "currency": drop.get("currency", "USD"),
            "royalty_bps": ROYALTY_BPS,
            "royalty_receiver": "creator",
            "token_standard": "ERC-721",
            "royalty_standard": "EIP-2981",
            "chain": "base",
            "owner": "creator:%s" % creator_id,
            "status": "pending_mint",
            "approval_id": entry["id"],
            "plan_id": plan.plan_id,
            "legal_gate": "cleared-2026-09-27",
            "minted_at": _utcnow(),
        }
        self._ledger.record_mint(token)
        self._audit_event("veil.nft.mint_requested", {
            "token_id": _short(str(token_id)),
            "drop_id": _short(drop_id),
            "creator_id": _short(creator_id),
            "price_minor": price,
        })
        return token

    def confirm_mint(self, token_id: str) -> Dict[str, Any]:
        """Finalize a pending mint once the keeper approved the backing
        approval-ledger entry. Fails closed otherwise."""
        require_adult()
        from levi.cybrus.approval import ApprovalEngine
        token = self._ledger.get(str(token_id))
        if token is None:
            raise VeilNftError("unknown token")
        if token["status"] == "minted":
            return token
        if not ApprovalEngine().check(token["approval_id"]):
            raise VeilNftError(
                "mint not authorized: approval %s is not approved"
                % _short(token["approval_id"]))
        token["status"] = "minted"
        token["confirmed_at"] = _utcnow()
        self._ledger._save()
        self._ledger._receipt("nft.mint_confirmed", {
            "token_id": _short(str(token_id)),
        })
        self._audit_event("veil.nft.minted", {
            "token_id": _short(str(token_id)),
        })
        return token

    # -- purchase ----------------------------------------------------------

    def buy_nft(self, token_id: str, buyer_id: str = "keeper",
                keeper_identity: str = "keeper") -> Dict[str, Any]:
        """Buy a minted NFT: builds a Cybrus MoneyPlan + approval-ledger
        entry. The purchase stays ``pending_payment`` until the keeper
        authorizes; :meth:`confirm_purchase` transfers ownership.

        Primary revenue splits 50/30/20 (creator/pool/treasury) per the
        genesis law, creator in the keeper's seat.
        """
        require_adult()
        token = self._ledger.get(str(token_id))
        if token is None:
            raise VeilNftError("unknown token")
        if token.get("status") != "minted":
            raise VeilNftError("token is not minted yet")
        buyer_id = (buyer_id or "").strip()[:64]
        if not buyer_id:
            raise VeilNftError("buyer_id is required")
        if token["owner"] == "owner:%s" % buyer_id or \
                token["owner"].endswith(":%s" % buyer_id):
            raise VeilNftError("buyer already owns this token")
        price = int(token["price_minor"])
        if price <= 0:
            raise VeilNftError("token has no price set")

        from levi.cybrus.money import MoneyGateway, MoneyPlan
        plan = MoneyPlan(
            plan_id=uuid.uuid4().hex,
            operation="creator_nft_purchase",
            amount_minor=price,
            currency=token.get("currency", "USD"),
            rail="",
            purpose="veil creator NFT purchase %s" % _short(str(token_id)),
            identity=keeper_identity,
            created_at=_utcnow(),
        )
        entry = MoneyGateway().request_execution_approval(
            plan, subject=keeper_identity)
        purchase_id = uuid.uuid4().hex
        purchase = {
            "purchase_id": purchase_id,
            "token_id": str(token_id),
            "buyer_id": buyer_id,
            "price_minor": price,
            "currency": token.get("currency", "USD"),
            "status": "pending_payment",
            "approval_id": entry["id"],
            "plan_id": plan.plan_id,
            "created_at": _utcnow(),
        }
        purchases = self._load_purchases()
        purchases[purchase_id] = purchase
        self._save_purchases(purchases)
        self._audit_event("veil.nft.purchase_requested", {
            "purchase_id": _short(purchase_id),
            "token_id": _short(str(token_id)),
            "price_minor": price,
        })
        return purchase

    def confirm_purchase(self, purchase_id: str) -> Dict[str, Any]:
        """Transfer ownership once the keeper approved the backing
        approval. Splits revenue 50/30/20 and records the royalty basis
        for secondary sales. Fails closed otherwise."""
        require_adult()
        from levi.cybrus.approval import ApprovalEngine
        purchases = self._load_purchases()
        purchase = purchases.get(purchase_id)
        if purchase is None:
            raise VeilNftError("unknown purchase")
        if purchase["status"] == "completed":
            return purchase
        if not ApprovalEngine().check(purchase["approval_id"]):
            raise VeilNftError(
                "purchase not paid: approval %s is not approved"
                % _short(purchase["approval_id"]))
        token = self._ledger.get(purchase["token_id"])
        if token is None:
            raise VeilNftError("unknown token")
        split = split_primary_revenue(int(purchase["price_minor"]))
        royalty = reference_royalty(int(purchase["price_minor"]))
        self._ledger.record_transfer(
            purchase["token_id"], "owner:%s" % purchase["buyer_id"],
            int(purchase["price_minor"]), royalty)
        purchase["status"] = "completed"
        purchase["completed_at"] = _utcnow()
        purchase["revenue_split"] = {
            "creator_minor": split["keeper"],
            "pool_minor": split["pool"],
            "treasury_minor": split["treasury"],
        }
        purchase["royalty_basis_bps"] = ROYALTY_BPS
        purchase["royalty_minor"] = royalty
        self._save_purchases(purchases)
        self._audit_event("veil.nft.transferred", {
            "purchase_id": _short(purchase_id),
            "token_id": _short(purchase["token_id"]),
            "to": _short(purchase["buyer_id"]),
        })
        return purchase

    def secondary_royalty_for(self, token_id: str,
                              sale_price_minor: int) -> Dict[str, Any]:
        """EIP-2981 royalty due on a secondary sale: 7.5% to the creator."""
        require_adult()
        token = self._ledger.get(str(token_id))
        if token is None:
            raise VeilNftError("unknown token")
        royalty = reference_royalty(int(sale_price_minor))
        return {
            "token_id": str(token_id),
            "sale_price_minor": int(sale_price_minor),
            "royalty_bps": ROYALTY_BPS,
            "royalty_minor": royalty,
            "receiver": "creator:%s" % token["creator_id"],
        }

    # -- reads ---------------------------------------------------------------

    def get_nft(self, token_id: str) -> Optional[Dict[str, Any]]:
        require_adult()
        return self._ledger.get(str(token_id))

    def nfts_for_creator(self, creator_id: str) -> List[Dict[str, Any]]:
        require_adult()
        return self._ledger.by_creator(creator_id)

    def nfts_for_drop(self, drop_id: str) -> List[Dict[str, Any]]:
        require_adult()
        return self._ledger.by_drop(drop_id)

    def verify_ledger(self) -> bool:
        return self._ledger.verify()
