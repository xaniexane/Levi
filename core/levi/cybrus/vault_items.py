"""Bitwarden-like item vault — Layer 3 over :class:`CredentialVault` (LEVI-original).

His design, verbatim (``docs/CYBRUS_VAULT.md``):

    "Like Bitwarden or Google Passwords — but better." Better means:
    **local-first, no cloud, no account, no sync server, no telemetry.**
    Your secrets never leave this machine. The vault is the platform's
    vault, not a consumer password-manager clone: no browser extension,
    no mobile autofill — those are out of scope by design.

And from his ``lock-and-key-vault-genesis.zip`` lineage
(``docs/UPLOADS_VEIL.md``): "an encrypted local vault (Bitwarden-style)".

What this layer adds, additively (``vault.py`` untouched):

* Item types Bitwarden users expect: **login** (username/password/URIs),
  **secure note**, **identity** (personal details), **card** (payment card).
* **Folders** for organization, **favorites**, **search** (metadata only),
  **URI matching** (local lookup — no autofill, per his design).
* **Retire, never delete**: removals move the item to a retired store with
  provenance (``retired_at``, ``reason``) — the nothing-thrown-away law.
* **Broker filing**: broker-created 3rd-party accounts land here as sealed
  login items via :meth:`ItemVault.file_broker_credential` — the shared
  contract with the broker lane.
* **Founder gate**: the full vault is the founder's; other identities get a
  limited vault (logins only, no broker-filed credentials, no PII types).

LAWS (machine-checked in ``tests/test_cybrus_vault_items.py``):

* **L1 SEALED-AT-REST.** Item payloads persist only inside the encrypted
  ``CredentialVault`` blob. No plaintext item file ever touches disk.
* **L2 NO-TRUE-DELETE.** :meth:`retire_item` moves the item to the retired
  store with ``retired_at`` + ``reason``; the retired store has no delete
  path through this API.
* **L3 IDENTITY-SCOPED.** Items live under ``cybrus.items.<identity>`` —
  one identity can never address another identity's items.
* **L4 AUDIT-METADATA-ONLY.** Audit records carry item ids, names, types,
  folders — never secret values.
* **L5 FOUNDER-GATE.** Non-founder identities are limited to login-type
  items and cannot read ``broker_created`` items; privileged types are
  refused with a clear error. Per the bloodline distribution law
  (2026-09-27), the gate is not just on/off: every gated decision is
  metered into a usage ledger (:func:`read_metering`), and each handle
  reports its bloodline build profile (:meth:`ItemVault.build_profile`) —
  ``founder-original`` vs ``bloodline-limited`` — so the full capability
  can be offered as a service he provides or meters.
* **L6 NO-EXPORT.** There is no share, copy, or export path. The only way
  a secret leaves the vault is :meth:`get_item` into the owning identity's
  own process.

Login items carry a ``category`` (``general``/``dating``/``creator``/
``companion``) from his plan — docs/CREATOR_PLATFORM.md ("dating + digital
creator services", "'skip the games'-style adult dating/classifieds
module") and docs/PLAIGROUND_PRODUCTION.md ("the NSFW adult companion
track"). Category is metadata only: it changes nothing about sealing,
gating, or audit. The adult-content gates live in the creator/plaiground
modules — this vault stores credentials, not content.

HONEST LIMITS:

* No browser extension, no mobile autofill, no cloud sync — his design
  rules those out; this module does not smuggle them back in.
* Search matches metadata (name, username, URIs, folder) — secret *values*
  (passwords, note bodies, card numbers) are never part of the match text.
* URI matching is local host comparison only; it does not fetch or
  validate anything on the network.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from levi.cybrus.vault import (
    CredentialVault,
    IdentityVault,
    VaultError,
    _audit_vault,
    _sanitize,
    generate_password,
)

# Re-exported for the broker lane's convenience (single import surface).
#: Bloodline distribution builds (his law, 2026-09-27): the founder gets
#: the ORIGINAL with full capability; every other user's version spawns off
#: it as a derived, LIMITED build.
BUILD_FOUNDER_ORIGINAL = "founder-original"
BUILD_BLOODLINE_LIMITED = "bloodline-limited"

#: Metering store name (usage ledger for his metered-service model).
_METERING_STORE = "vault_metering"
_METERING_CAP = 10_000


def _meter(identity: str, tier: Optional[str], ability: str, decision: str) -> None:
    """Append a metering record: who used (or was refused) which gated
    ability, when. This is the usage ledger behind his metered-service
    model — the gate is not just on/off, every gated decision is metered.
    Writes are best-effort: metering must never break the vault operation
    it measures."""
    try:
        from levi.cybrus._paths import load_json_store, save_json_store, store_lock, store_path

        path = store_path(_METERING_STORE)
        with store_lock(path):
            records = load_json_store(path) or []
            if not isinstance(records, list):
                records = []
            records.append(
                {
                    "ts": _utcnow_iso(),
                    "identity": str(identity),
                    "tier": tier,
                    "ability": ability,
                    "decision": decision,  # "granted" | "refused"
                }
            )
            del records[: max(0, len(records) - _METERING_CAP)]
            save_json_store(path, records)
    except Exception:
        pass  # metering is best-effort; the vault operation stands


def read_metering(limit: int = 200) -> list:
    """Read the most recent metering records (newest last). Metadata only —
    no secret values ever enter the metering store."""
    from levi.cybrus._paths import load_json_store, store_path

    records = load_json_store(store_path(_METERING_STORE)) or []
    if not isinstance(records, list):
        return []
    return records[-max(1, int(limit)):]


__all__ = [
    "ItemVaultError",
    "ItemVault",
    "ITEM_TYPES",
    "FOUNDER_ONLY_TYPES",
    "LOGIN_CATEGORIES",
    "BUILD_FOUNDER_ORIGINAL",
    "BUILD_BLOODLINE_LIMITED",
    "read_metering",
    "generate_password",
]

_ITEMS_NS = "cybrus.items"
_RETIRED_NS = "cybrus.items.retired"
_FOLDERS_NS = "cybrus.folders"

#: Bitwarden's four item types, plus Cybrus's fifth: API keys — the vault is
#: Bitwarden-like but broker-capable, and broker-created third-party
#: credentials include API keys (his spec 2026-09-27).
ITEM_TYPES = ("login", "note", "identity", "card", "api_key")

#: Types carrying PII/payment data — founder-only, per the founder gate.
FOUNDER_ONLY_TYPES = ("identity", "card")

#: Login credential categories, from his plan (docs/CREATOR_PLATFORM.md:
#: "Creator Platform — dating + digital creator services"; "a 'skip the
#: games'-style adult dating/classifieds module"; docs/PLAIGROUND_PRODUCTION.md:
#: "Plaiground is the NSFW adult companion track"). "Escort"/classifieds-style
#: listings fall under "dating" per the originals' "adult dating/classifieds"
#: module. Category is metadata only — it changes nothing about sealing,
#: gating, or audit; the adult-content gates live in the creator/plaiground
#: modules, not here (this vault stores credentials, not content).
LOGIN_CATEGORIES = ("general", "dating", "creator", "companion")

#: Metadata keys that are safe to surface in listings/search/audit.
_META_KEYS = (
    "id",
    "type",
    "name",
    "folder_id",
    "folder",
    "favorite",
    "username",
    "uris",
    "service",
    "category",
    "broker_created",
    "created_at",
    "updated_at",
    "revision",
    "retired_at",
    "retire_reason",
)


class ItemVaultError(VaultError):
    """Item-vault errors: gate refusals, unknown items, bad input."""


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


def _tier_of(identity: str) -> Optional[str]:
    """Identity tier, or None when the identity has no record."""
    try:
        from levi.cybrus.identity import IdentityStore

        rec = IdentityStore().get(identity)
        return rec.get("tier") if rec else None
    except Exception:
        return None


def _is_founder(identity: str, tier: Optional[str]) -> bool:
    if tier == "founder":
        return True
    try:
        from levi.cybrus.identity import is_founder_identity

        return bool(is_founder_identity(identity))
    except Exception:
        return False


def _clean_text(value: Any, what: str, max_len: int = 256) -> str:
    if not isinstance(value, str):
        raise ItemVaultError(f"{what} must be a string")
    text = value.strip()
    if not text or len(text) > max_len:
        raise ItemVaultError(f"{what} must be 1-{max_len} chars")
    return text


def _clean_uris(uris: Any) -> List[str]:
    if uris is None:
        return []
    if not isinstance(uris, (list, tuple)):
        raise ItemVaultError("uris must be a list of strings")
    out = []
    for u in uris:
        if not isinstance(u, str) or not u.strip() or len(u) > 512:
            raise ItemVaultError("each uri must be a 1-512 char string")
        out.append(u.strip())
    return out


def _host_of(uri: str) -> str:
    """Host of a URI, lowercased; empty string when unparseable."""
    try:
        host = urlparse(uri if "://" in uri else "https://" + uri).hostname or ""
        return host.lower()
    except Exception:
        return ""


class ItemVault:
    """Bitwarden-like credentials vault for one identity.

    ``ItemVault(passphrase, identity)`` — entries are sealed under the
    identity's namespace (``cybrus.items.<identity>``) inside the encrypted
    ``CredentialVault`` blob. The founder gets the full vault; every other
    identity gets the limited vault (login items only, no broker-filed
    credentials, no identity/card types).
    """

    def __init__(
        self,
        passphrase: str,
        identity: str,
        directory: Optional[Path] = None,
    ):
        self.identity = _sanitize(identity, "identity")
        self._tier = _tier_of(self.identity)
        self._founder = _is_founder(self.identity, self._tier)
        # IdentityVault gives per-identity scoping by construction (L3).
        self._vault = IdentityVault(passphrase, self.identity, directory=directory)

    # -- gate ------------------------------------------------------------

    @property
    def tier(self) -> Optional[str]:
        """The identity's tier (None when the identity has no record)."""
        return self._tier

    @property
    def is_full(self) -> bool:
        """True when this handle carries the full (founder) vault."""
        return self._founder

    def _require_type(self, item_type: str) -> None:
        if item_type not in ITEM_TYPES:
            raise ItemVaultError(
                f"unknown item type {item_type!r}; valid: {list(ITEM_TYPES)}"
            )
        # L5 FOUNDER-GATE: the full vault is the founder's. Other identities
        # get the limited vault — login items only (no notes, no PII types,
        # no API keys). The refusal is metered (bloodline law: not just on/off).
        if not self._founder and item_type != "login":
            _meter(self.identity, self._tier, f"items.store.{item_type}", "refused")
            raise ItemVaultError(
                f"item type {item_type!r} is founder-only: "
                f"identity {self.identity!r} (tier {self._tier!r}) is limited "
                "to login items"
            )

    def _check_broker_read(self, record: dict) -> None:
        if record.get("broker_created") and not self._founder:
            raise ItemVaultError(
                "broker-filed credentials are founder-only: "
                f"identity {self.identity!r} may not read this item"
            )

    # -- internal record plumbing ----------------------------------------

    def _load_record(self, item_id: str) -> dict:
        try:
            raw = self._vault.get("items", item_id)
        except KeyError:
            raise ItemVaultError(f"no such item: {item_id!r}") from None
        try:
            record = json.loads(raw)
        except ValueError as exc:
            raise ItemVaultError("stored item is corrupt") from exc
        if not isinstance(record, dict) or record.get("id") != item_id:
            raise ItemVaultError("stored item is corrupt")
        return record

    def _save_record(self, record: dict) -> None:
        self._vault.store("items", record["id"], json.dumps(record, sort_keys=True))

    def _load_retired(self, item_id: str) -> dict:
        try:
            raw = self._vault.get("retired", item_id)
        except KeyError:
            raise ItemVaultError(f"no such retired item: {item_id!r}") from None
        try:
            record = json.loads(raw)
        except ValueError as exc:
            raise ItemVaultError("stored retired item is corrupt") from exc
        if not isinstance(record, dict):
            raise ItemVaultError("stored retired item is corrupt")
        return record

    def _metadata(self, record: dict) -> dict:
        """Metadata-only view of a record (L4) — never secret values."""
        meta = {k: record.get(k) for k in _META_KEYS if k in record}
        fields = record.get("fields") or {}
        # Login metadata that is safe to surface (never the password).
        if record.get("type") == "login":
            meta["username"] = fields.get("username", "")
            meta["uris"] = list(fields.get("uris") or [])
            meta["category"] = fields.get("category", "general")
        # API-key metadata safe to surface (never the key itself).
        if record.get("type") == "api_key":
            meta["service"] = fields.get("service", "")
        folder_id = record.get("folder_id")
        meta["folder"] = self._folder_name(folder_id) if folder_id else None
        return meta

    # -- folders ----------------------------------------------------------

    def _load_folders(self) -> dict:
        try:
            raw = self._vault.get("folders", "index")
        except KeyError:
            return {}
        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise ItemVaultError("stored folder index is corrupt") from exc
        return data if isinstance(data, dict) else {}

    def _save_folders(self, folders: dict) -> None:
        self._vault.store("folders", "index", json.dumps(folders, sort_keys=True))

    def _folder_name(self, folder_id: Optional[str]) -> Optional[str]:
        if not folder_id:
            return None
        return self._load_folders().get(folder_id, {}).get("name")

    def create_folder(self, name: str) -> str:
        """Create a folder; returns its id."""
        name = _clean_text(name, "folder name", 128)
        folders = self._load_folders()
        if any(f.get("name") == name for f in folders.values()):
            raise ItemVaultError(f"folder {name!r} already exists")
        folder_id = _new_id()
        folders[folder_id] = {"name": name, "created_at": _utcnow_iso()}
        self._save_folders(folders)
        _audit_vault("items.folder_created", self.identity, {"folder": name})
        return folder_id

    def rename_folder(self, folder_id: str, name: str) -> None:
        name = _clean_text(name, "folder name", 128)
        folders = self._load_folders()
        if folder_id not in folders:
            raise ItemVaultError(f"no such folder: {folder_id!r}")
        folders[folder_id]["name"] = name
        self._save_folders(folders)
        _audit_vault("items.folder_renamed", self.identity, {"folder": name})

    def delete_folder(self, folder_id: str) -> None:
        """Delete an empty folder. Refuses when items still reference it —
        move them out first (nothing is silently orphaned)."""
        folders = self._load_folders()
        if folder_id not in folders:
            raise ItemVaultError(f"no such folder: {folder_id!r}")
        for meta in self.list_items():
            if meta.get("folder_id") == folder_id:
                raise ItemVaultError(
                    "folder is not empty: move its items out before deleting"
                )
        name = folders.pop(folder_id)["name"]
        self._save_folders(folders)
        _audit_vault("items.folder_deleted", self.identity, {"folder": name})

    def list_folders(self) -> list:
        """Folders as ``[{"id": ..., "name": ...}]`` (metadata only)."""
        folders = self._load_folders()
        return sorted(
            ({"id": fid, "name": f["name"]} for fid, f in folders.items()),
            key=lambda f: f["name"].lower(),
        )

    # -- items -------------------------------------------------------------

    @staticmethod
    def _validate_fields(item_type: str, fields: dict) -> dict:
        """Type-check the type-specific payload. Returns cleaned fields."""
        if item_type == "login":
            username = _clean_text(fields.get("username", ""), "username", 256)
            password = fields.get("password", "")
            if not isinstance(password, str) or not password:
                raise ItemVaultError("login password must be a non-empty string")
            category = fields.get("category", "general")
            if category not in LOGIN_CATEGORIES:
                raise ItemVaultError(
                    f"unknown login category {category!r}; "
                    f"valid: {list(LOGIN_CATEGORIES)}"
                )
            return {
                "username": username,
                "password": password,
                "uris": _clean_uris(fields.get("uris")),
                "category": category,
            }
        if item_type == "note":
            return {"text": _clean_text(fields.get("text", ""), "note text", 8192)}
        if item_type == "identity":
            out = {}
            for key in (
                "first_name",
                "last_name",
                "email",
                "phone",
                "address",
                "city",
                "state",
                "postal",
                "country",
                "company",
            ):
                val = fields.get(key, "")
                if val is None:
                    val = ""
                if not isinstance(val, str) or len(val) > 256:
                    raise ItemVaultError(f"identity field {key!r} must be a short string")
                out[key] = val.strip()
            if not any(out.values()):
                raise ItemVaultError("identity item needs at least one field")
            return out
        if item_type == "card":
            cardholder = _clean_text(fields.get("cardholder", ""), "cardholder", 128)
            number = fields.get("number", "")
            if not isinstance(number, str) or not number.strip():
                raise ItemVaultError("card number must be a non-empty string")
            exp = str(fields.get("exp", "")).strip()
            cvv = str(fields.get("cvv", "")).strip()
            return {
                "cardholder": cardholder,
                "brand": _clean_text(fields.get("brand", ""), "brand", 64)
                if fields.get("brand")
                else "",
                "number": number.strip(),
                "exp": exp,
                "cvv": cvv,
            }
        if item_type == "api_key":
            key = fields.get("key", "")
            if not isinstance(key, str) or not key.strip():
                raise ItemVaultError("API key must be a non-empty string")
            service = fields.get("service", "")
            if service is None:
                service = ""
            if not isinstance(service, str) or len(service) > 128:
                raise ItemVaultError("API key service must be a short string")
            scopes = fields.get("scopes", [])
            if not isinstance(scopes, list) or any(
                not isinstance(s, str) or not s.strip() or len(s) > 128
                for s in scopes
            ):
                raise ItemVaultError("API key scopes must be a list of short strings")
            return {
                "key": key.strip(),
                "service": service.strip(),
                "scopes": [s.strip() for s in scopes],
            }
        raise ItemVaultError(f"unknown item type {item_type!r}")  # pragma: no cover

    def store_item(
        self,
        item_type: str,
        name: str,
        *,
        folder_id: Optional[str] = None,
        favorite: bool = False,
        broker_created: bool = False,
        **fields: Any,
    ) -> str:
        """Store a new item; returns its id. ``broker_created`` is honored
        only on founder handles — it marks broker-filed credentials."""
        self._require_type(item_type)
        name = _clean_text(name, "item name", 256)
        if folder_id is not None and folder_id not in self._load_folders():
            raise ItemVaultError(f"no such folder: {folder_id!r}")
        if broker_created and not self._founder:
            raise ItemVaultError(
                "only the founder may file broker-created credentials"
            )
        now = _utcnow_iso()
        item_id = _new_id()
        record = {
            "id": item_id,
            "type": item_type,
            "name": name,
            "folder_id": folder_id,
            "favorite": bool(favorite),
            "fields": self._validate_fields(item_type, fields),
            "broker_created": bool(broker_created),
            "created_at": now,
            "updated_at": now,
            "revision": 1,
        }
        self._save_record(record)
        _audit_vault(
            "items.stored",
            self.identity,
            {"item_id": item_id, "type": item_type, "name": name},
        )
        _meter(self.identity, self._tier, f"items.store.{item_type}", "granted")
        return item_id

    def get_item(self, item_id: str) -> dict:
        """Full item record, secrets included — to the owning identity only.

        Broker-filed items additionally require a founder handle (L5).
        """
        record = self._load_record(item_id)
        self._check_broker_read(record)
        _audit_vault(
            "items.accessed",
            self.identity,
            {"item_id": item_id, "type": record.get("type"), "name": record.get("name")},
        )
        _meter(self.identity, self._tier, "items.read", "granted")
        return record

    def update_item(self, item_id: str, **fields: Any) -> dict:
        """Update mutable attributes (name, folder, favorite, type fields).
        Bumps ``revision`` and ``updated_at``. Returns metadata."""
        record = self._load_record(item_id)
        self._check_broker_read(record)
        if "name" in fields:
            record["name"] = _clean_text(fields.pop("name"), "item name", 256)
        if "folder_id" in fields:
            folder_id = fields.pop("folder_id")
            if folder_id is not None and folder_id not in self._load_folders():
                raise ItemVaultError(f"no such folder: {folder_id!r}")
            record["folder_id"] = folder_id
        if "favorite" in fields:
            record["favorite"] = bool(fields.pop("favorite"))
        if fields:
            # Remaining kwargs are type-specific field updates (merged).
            merged = dict(record["fields"])
            merged.update(fields)
            record["fields"] = self._validate_fields(record["type"], merged)
        record["updated_at"] = _utcnow_iso()
        record["revision"] = int(record.get("revision", 1)) + 1
        self._save_record(record)
        _audit_vault(
            "items.updated",
            self.identity,
            {
                "item_id": item_id,
                "type": record.get("type"),
                "revision": record["revision"],
            },
        )
        return self._metadata(record)

    def retire_item(self, item_id: str, reason: str = "") -> dict:
        """Retire an item: moved to the retired store with provenance
        (``retired_at``, ``reason``). Nothing is ever truly deleted (L2)."""
        record = self._load_record(item_id)
        self._check_broker_read(record)
        reason = _clean_text(reason, "retire reason", 512) if reason else ""
        record["retired_at"] = _utcnow_iso()
        record["retire_reason"] = reason
        # Move: write to retired store, then remove from active.
        self._vault.store("retired", item_id, json.dumps(record, sort_keys=True))
        self._vault.delete("items", item_id)
        _audit_vault(
            "items.retired",
            self.identity,
            {"item_id": item_id, "type": record.get("type"), "name": record.get("name")},
        )
        _meter(self.identity, self._tier, "items.retire", "granted")
        return self._metadata(record)

    def restore_item(self, item_id: str) -> dict:
        """Restore a retired item to the active store."""
        record = self._load_retired(item_id)
        self._require_type(record.get("type", "login"))
        record.pop("retired_at", None)
        record.pop("retire_reason", None)
        record["updated_at"] = _utcnow_iso()
        record["revision"] = int(record.get("revision", 1)) + 1
        self._save_record(record)
        self._vault.delete("retired", item_id)
        _audit_vault(
            "items.restored",
            self.identity,
            {"item_id": item_id, "type": record.get("type"), "name": record.get("name")},
        )
        return self._metadata(record)

    def list_items(
        self,
        *,
        folder_id: Optional[str] = None,
        item_type: Optional[str] = None,
        category: Optional[str] = None,
        favorites_only: bool = False,
        include_retired: bool = False,
    ) -> list:
        """Metadata-only listing (L4). Broker-filed items are invisible to
        non-founder handles."""
        if category is not None and category not in LOGIN_CATEGORIES:
            raise ItemVaultError(
                f"unknown login category {category!r}; "
                f"valid: {list(LOGIN_CATEGORIES)}"
            )
        out = []
        for item_id in self._iter_item_ids():
            try:
                record = self._load_record(item_id)
            except ItemVaultError:
                continue
            if record.get("broker_created") and not self._founder:
                continue
            if folder_id is not None and record.get("folder_id") != folder_id:
                continue
            if item_type is not None and record.get("type") != item_type:
                continue
            if category is not None and (record.get("fields") or {}).get(
                "category", "general"
            ) != category:
                continue
            if favorites_only and not record.get("favorite"):
                continue
            out.append(self._metadata(record))
        if include_retired and self._founder:
            for item_id in self._iter_retired_ids():
                try:
                    record = self._load_retired(item_id)
                except ItemVaultError:
                    continue
                out.append(self._metadata(record))
        return sorted(out, key=lambda m: (str(m.get("name", "")).lower(), str(m.get("id"))))

    def _iter_item_ids(self) -> list:
        try:
            entries = self._vault._vault._load_entries()
        except VaultError:
            return []
        # IdentityVault namespaces this identity's "items" service as
        # cybrus.id.<identity>.items; item ids are the usernames under it.
        service = f"cybrus.id.{self.identity}.items"
        return sorted(entries.get(service, {}).keys())

    def _iter_retired_ids(self) -> list:
        try:
            entries = self._vault._vault._load_entries()
        except VaultError:
            return []
        service = f"cybrus.id.{self.identity}.retired"
        return sorted(entries.get(service, {}).keys())

    def search(self, query: str) -> list:
        """Metadata search over name, username, URIs, and folder name.

        Secret *values* (passwords, note bodies, card numbers) are never
        part of the match text — documented honest limit."""
        q = _clean_text(query, "search query", 128).lower()
        hits = []
        for meta in self.list_items():
            haystack = " ".join(
                str(meta.get(k) or "")
                for k in ("name", "username", "folder")
            )
            haystack += " " + " ".join(meta.get("uris") or [])
            if q in haystack.lower():
                hits.append(meta)
        return hits

    def match_uri(self, uri: str) -> list:
        """Login items whose stored URIs match ``uri``'s host (local host
        comparison only — no network, no autofill)."""
        want = _host_of(_clean_text(uri, "uri", 512))
        if not want:
            return []
        hits = []
        for meta in self.list_items(item_type="login"):
            for stored in meta.get("uris") or []:
                host = _host_of(stored)
                if host and (want == host or want.endswith("." + host)):
                    hits.append(meta)
                    break
        return hits

    # -- broker contract ---------------------------------------------------

    def file_broker_credential(
        self,
        platform: str,
        username: str,
        password: str,
        *,
        uris: Optional[list] = None,
        category: str = "general",
        folder_id: Optional[str] = None,
    ) -> str:
        """File a broker-created 3rd-party account as a sealed login item.

        THE shared contract with the broker lane: the broker calls this
        after provisioning an account so the credential lands in the vault
        sealed under keeper-held keys. Founder-only, both to file and to
        read (L5) — other users never see brokered credentials.

        ``category`` tags the platform kind per his plan ("dating",
        "creator", "companion", "general") — see LOGIN_CATEGORIES.
        """
        if not self._founder:
            _meter(self.identity, self._tier, "items.broker_file", "refused")
            raise ItemVaultError(
                "filing broker credentials is founder-only: "
                f"identity {self.identity!r} is limited"
            )
        platform = _sanitize(platform, "platform")
        item_id = self.store_item(
            "login",
            platform,
            username=username,
            password=password,
            uris=_clean_uris(uris),
            category=category,
            folder_id=folder_id,
            broker_created=True,
        )
        _audit_vault(
            "items.broker_filed",
            self.identity,
            {"item_id": item_id, "platform": platform, "username": username},
        )
        _meter(self.identity, self._tier, "items.broker_file", "granted")
        return item_id

    def file_broker_api_key(
        self,
        platform: str,
        api_key: str,
        *,
        scopes: Optional[list] = None,
        folder_id: Optional[str] = None,
    ) -> str:
        """File a broker-provisioned API key as a sealed api_key item.

        Sibling of :meth:`file_broker_credential` for third-party accounts
        that issue API keys instead of passwords. Same contract: the broker
        calls this after provisioning so the key lands in the vault sealed
        under keeper-held keys. Founder-only, both to file and to read
        (L5) — other users never see brokered credentials.
        """
        if not self._founder:
            _meter(self.identity, self._tier, "items.broker_file", "refused")
            raise ItemVaultError(
                "filing broker credentials is founder-only: "
                f"identity {self.identity!r} is limited"
            )
        platform = _sanitize(platform, "platform")
        item_id = self.store_item(
            "api_key",
            platform,
            key=api_key,
            service=platform,
            scopes=scopes or [],
            folder_id=folder_id,
            broker_created=True,
        )
        _audit_vault(
            "items.broker_filed",
            self.identity,
            {"item_id": item_id, "platform": platform, "kind": "api_key"},
        )
        _meter(self.identity, self._tier, "items.broker_file", "granted")
        return item_id

    def generate_and_store_login(
        self,
        name: str,
        username: str,
        *,
        length: int = 24,
        uris: Optional[list] = None,
        category: str = "general",
        folder_id: Optional[str] = None,
        favorite: bool = False,
    ) -> dict:
        """Generate a CSPRNG password and store a login item with it.

        Returns ``{"item_id": ..., "password": ...}`` — the password is
        shown ONCE to the caller, never logged, never audited."""
        password = generate_password(length)
        item_id = self.store_item(
            "login",
            name,
            username=username,
            password=password,
            uris=_clean_uris(uris),
            category=category,
            folder_id=folder_id,
            favorite=favorite,
        )
        return {"item_id": item_id, "password": password}

    @property
    def backend(self) -> str:
        """Which crypto backend unlocked this vault (honest label)."""
        return self._vault.backend

    def build_profile(self) -> dict:
        """Bloodline distribution profile (his law, 2026-09-27).

        The founder holds the ORIGINAL with full capability; every other
        identity's vault is a derived, LIMITED build spawned off it. The
        full capability is offered as a service he provides or meters —
        this profile plus the metering ledger (see :func:`read_metering`)
        are the hooks for that, not just an on/off gate.
        """
        full = self._founder
        return {
            "identity": self.identity,
            "tier": self._tier,
            "build": BUILD_FOUNDER_ORIGINAL if full else BUILD_BLOODLINE_LIMITED,
            "abilities": {
                "item_types": list(ITEM_TYPES) if full else ["login"],
                "login_categories": list(LOGIN_CATEGORIES),
                "folders": True,
                "search": True,
                "favorites": True,
                "broker_file": full,
                "broker_filed_read": full,
                "restore_retired": full,
            },
            "metered": True,
        }
