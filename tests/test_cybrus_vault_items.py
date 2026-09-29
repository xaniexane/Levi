"""Item-vault laws (LEVI-original, Bitwarden-like Layer 3 over CredentialVault).

L1 SEALED-AT-REST — item payloads persist only inside the encrypted vault
    blob; no plaintext secret ever touches disk.
L2 NO-TRUE-DELETE — retire moves items to the retired store with provenance;
    the retired store has no delete path through this API.
L3 IDENTITY-SCOPED — one identity can never address another's items.
L4 AUDIT-METADATA-ONLY — audit records never carry secret values.
L5 FOUNDER-GATE — non-founder identities are limited to login items and
    cannot read broker-filed credentials.
L6 NO-EXPORT — no share/copy/export path exists on the vault.

Hermetic: LEVI_HOME points at a tmp dir per test (module-scoped autouse
fixture), so identity stores, vault blobs, and the audit log are isolated.
"""

import json
import os
from pathlib import Path

import pytest

from levi.cybrus.vault_items import (
    BUILD_BLOODLINE_LIMITED,
    BUILD_FOUNDER_ORIGINAL,
    FOUNDER_ONLY_TYPES,
    ITEM_TYPES,
    LOGIN_CATEGORIES,
    ItemVault,
    ItemVaultError,
    read_metering,
)

PW = "correct horse battery staple"


@pytest.fixture(autouse=True)
def _hermetic_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    yield


def _mk(identity: str, tier: str = "starter") -> ItemVault:
    from levi.cybrus.identity import IdentityStore

    store = IdentityStore()
    if not store.exists(identity):
        store.create(identity, tier=tier)
    return ItemVault(PW, identity)


def _mk_founder() -> ItemVault:
    return _mk("chauncey", tier="founder")


def _all_bytes(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and not p.name.endswith(".lock"):
            try:
                yield p, p.read_bytes()
            except OSError:
                continue


# -- L1: sealed at rest ----------------------------------------------------


def test_l1_no_plaintext_secret_on_disk(tmp_path):
    import secrets as _secrets

    v = _mk_founder()
    secret_pw = "pw-" + _secrets.token_hex(16)
    secret_note = "note-" + _secrets.token_hex(16)
    v.store_item("login", "bank", username="u1", password=secret_pw,
                 uris=["https://bank.example.com"])
    v.store_item("note", "memo", text=secret_note)
    home = Path(os.environ["LEVI_HOME"]) / ".levi" / "cybrus"
    for path, blob in _all_bytes(home):
        assert secret_pw.encode() not in blob, f"plaintext password in {path}"
        assert secret_note.encode() not in blob, f"plaintext note in {path}"


def test_l1_wrong_passphrase_fails_closed():
    v = _mk_founder()
    item_id = v.store_item("login", "svc", username="u", password="s3cret!")
    with pytest.raises(Exception):
        ItemVault("wrong-passphrase", "chauncey").get_item(item_id)


# -- L2: retire, never delete ----------------------------------------------


def test_l2_retire_moves_with_provenance_and_restores():
    v = _mk_founder()
    item_id = v.store_item("login", "oldsvc", username="u", password="p")
    meta = v.retire_item(item_id, reason="rotated")
    assert meta["retired_at"] and meta["retire_reason"] == "rotated"
    with pytest.raises(ItemVaultError):
        v.get_item(item_id)
    assert all(m["id"] != item_id for m in v.list_items())
    retired = v.list_items(include_retired=True)
    assert any(m["id"] == item_id and m.get("retired_at") for m in retired)
    # Non-founder handles cannot even see the retired index.
    limited = _mk("bob")
    assert all(m["id"] != item_id for m in limited.list_items(include_retired=True))
    restored = v.restore_item(item_id)
    assert restored["id"] == item_id and "retired_at" not in restored
    assert v.get_item(item_id)["fields"]["password"] == "p"


def test_l2_retired_store_has_no_delete_path():
    assert not hasattr(ItemVault, "delete_retired")
    assert not hasattr(ItemVault, "purge_retired")
    assert not hasattr(ItemVault, "delete_item")


# -- L3: identity scoping ---------------------------------------------------


def test_l3_identities_cannot_address_each_other():
    alice = _mk("alice")
    bob = _mk("bob")
    item_id = alice.store_item("login", "alice-svc", username="a", password="p")
    assert all(m["id"] != item_id for m in bob.list_items())
    with pytest.raises(ItemVaultError):
        bob.get_item(item_id)
    with pytest.raises(ItemVaultError):
        bob.retire_item(item_id)


# -- L4: audit metadata only -------------------------------------------------


def test_l4_audit_never_carries_secrets():
    import secrets as _secrets

    v = _mk_founder()
    secret_pw = "audit-" + _secrets.token_hex(16)
    item_id = v.store_item("login", "svc", username="u", password=secret_pw)
    v.get_item(item_id)
    v.retire_item(item_id)
    audit_log = Path(os.environ["LEVI_HOME"]) / ".levi" / "cybrus" / "audit.jsonl"
    assert audit_log.exists()
    text = audit_log.read_text(encoding="utf-8")
    assert secret_pw not in text
    # But the metadata events are there.
    assert "items.stored" in text and "items.retired" in text


# -- L5: founder gate --------------------------------------------------------


def test_l5_founder_gets_all_types_and_broker_filing():
    v = _mk_founder()
    assert v.is_full
    login_id = v.store_item("login", "svc", username="u", password="p")
    note_id = v.store_item("note", "n", text="hello")
    ident_id = v.store_item("identity", "me", first_name="Chauncey")
    card_id = v.store_item("card", "visa", cardholder="C", number="4111")
    assert {login_id, note_id, ident_id, card_id} == {
        m["id"] for m in v.list_items()
    }
    filed = v.file_broker_credential("example.com", "bot", "s3cret",
                                     uris=["https://example.com"])
    rec = v.get_item(filed)
    assert rec["broker_created"] is True
    assert rec["fields"]["password"] == "s3cret"


def test_l5_limited_identity_login_only_no_privileged_types():
    v = _mk("carol")
    assert not v.is_full
    login_id = v.store_item("login", "svc", username="u", password="p")
    assert v.get_item(login_id)["fields"]["username"] == "u"
    for itype in FOUNDER_ONLY_TYPES:
        kwargs = (
            {"first_name": "X"} if itype == "identity"
            else {"cardholder": "X", "number": "1"}
        )
        with pytest.raises(ItemVaultError):
            v.store_item(itype, "x", **kwargs)
    # Notes are also beyond the limited vault (logins only).
    with pytest.raises(ItemVaultError):
        v.store_item("note", "n", text="t")


def test_l5_limited_identity_cannot_file_or_read_broker_credentials():
    founder = _mk_founder()
    filed = founder.file_broker_credential("example.com", "bot", "s3cret")
    limited = _mk("dave")
    with pytest.raises(ItemVaultError):
        limited.file_broker_credential("example.com", "x", "y")
    with pytest.raises(ItemVaultError):
        limited.get_item(filed)
    assert all(m["id"] != filed for m in limited.list_items())
    with pytest.raises(ItemVaultError):
        limited.retire_item(filed)


def test_l5_unknown_identity_treated_as_limited():
    v = ItemVault(PW, "stranger")  # no identity record at all
    assert not v.is_full
    login_id = v.store_item("login", "svc", username="u", password="p")
    assert v.get_item(login_id)["type"] == "login"
    with pytest.raises(ItemVaultError):
        v.store_item("card", "c", cardholder="X", number="1")


# -- L6: no export ------------------------------------------------------------


def test_l6_no_share_copy_export_path():
    for name in ("export", "share", "copy_item", "dump", "backup_items"):
        assert not hasattr(ItemVault, name), f"unexpected export path: {name}"


# -- Bitwarden-like behavior --------------------------------------------------


def test_folders_organize_and_refuse_nonempty_delete():
    v = _mk_founder()
    fid = v.create_folder("Work")
    item_id = v.store_item("login", "mail", username="u", password="p", folder_id=fid)
    with pytest.raises(ItemVaultError):
        v.delete_folder(fid)
    v.update_item(item_id, folder_id=None)
    v.delete_folder(fid)
    assert v.list_folders() == []
    with pytest.raises(ItemVaultError):
        v.create_folder("Work")
        v.create_folder("Work")  # duplicate name refused


def test_search_matches_metadata_not_secret_values():
    v = _mk_founder()
    v.store_item("login", "GitHub", username="octocat", password="unfindable-xyz",
                 uris=["https://github.com"])
    assert len(v.search("github")) == 1
    assert len(v.search("octocat")) == 1
    assert v.search("unfindable-xyz") == []
    assert len(v.search("GITHUB")) == 1  # case-insensitive


def test_match_uri_local_host_comparison():
    v = _mk_founder()
    v.store_item("login", "bank", username="u", password="p",
                 uris=["https://bank.example.com/login"])
    hits = v.match_uri("https://bank.example.com/other")
    assert len(hits) == 1 and hits[0]["name"] == "bank"
    # Subdomain of a stored host matches.
    hits = v.match_uri("https://secure.bank.example.com/")
    assert len(hits) == 1
    assert v.match_uri("https://evil.com/") == []
    assert v.match_uri("https://bank.example.com.evil.com/") == []


def test_update_bumps_revision_and_favorite_filter():
    v = _mk_founder()
    item_id = v.store_item("login", "svc", username="u", password="p")
    meta = v.update_item(item_id, favorite=True, password="p2")
    assert meta["revision"] == 2 and meta["favorite"] is True
    assert v.get_item(item_id)["fields"]["password"] == "p2"
    assert [m["id"] for m in v.list_items(favorites_only=True)] == [item_id]


def test_generate_and_store_login_returns_password_once(tmp_path, capsys):
    v = _mk_founder()
    out = v.generate_and_store_login("svc", "u", length=20)
    assert len(out["password"]) >= 20
    assert v.get_item(out["item_id"])["fields"]["password"] == out["password"]
    captured = capsys.readouterr()
    assert out["password"] not in captured.out  # never printed


def test_item_types_known():
    assert set(ITEM_TYPES) == {"login", "note", "identity", "card", "api_key"}
    assert set(FOUNDER_ONLY_TYPES) <= set(ITEM_TYPES)


# -- His plan: dating / creator / companion platform categories --------------


def test_login_categories_cover_his_planned_services():
    # His words: "dating service", "skip the games like escort service",
    # "onlyfans digital creator content monetization service",
    # "companion playground / chat on ai nsfw style".
    # Originals: docs/CREATOR_PLATFORM.md, docs/PLAIGROUND_PRODUCTION.md.
    assert set(LOGIN_CATEGORIES) == {"general", "dating", "creator", "companion"}


def test_category_stored_searchable_and_filterable():
    v = _mk_founder()
    d = v.store_item("login", "datesvc", username="u", password="p",
                     category="dating")
    c = v.store_item("login", "creatorsvc", username="u", password="p",
                     category="creator")
    p = v.store_item("login", "companionsvc", username="u", password="p",
                     category="companion")
    g = v.store_item("login", "mailsvc", username="u", password="p")
    assert v.get_item(d)["fields"]["category"] == "dating"
    assert v.get_item(g)["fields"]["category"] == "general"  # default
    assert [m["id"] for m in v.list_items(category="dating")] == [d]
    assert [m["id"] for m in v.list_items(category="creator")] == [c]
    assert [m["id"] for m in v.list_items(category="companion")] == [p]
    assert [m["id"] for m in v.list_items(category="general")] == [g]
    with pytest.raises(ItemVaultError):
        v.store_item("login", "x", username="u", password="p", category="nope")
    with pytest.raises(ItemVaultError):
        v.list_items(category="nope")


def test_category_is_metadata_only_and_limited_users_may_use_it():
    # Category changes nothing about sealing or the founder gate: limited
    # identities may tag their own logins; broker-filed categorized items
    # stay founder-only.
    limited = _mk("erin")
    item_id = limited.store_item("login", "datesvc", username="u", password="p",
                                 category="dating")
    assert limited.get_item(item_id)["fields"]["category"] == "dating"
    founder = _mk_founder()
    filed = founder.file_broker_credential("creatorsite.example", "bot", "s3cret",
                                           category="creator")
    assert founder.get_item(filed)["fields"]["category"] == "creator"
    with pytest.raises(ItemVaultError):
        limited.get_item(filed)


# -- Bloodline distribution law: metering hooks, not just on/off -----------


def test_build_profile_bloodline():
    founder = _mk_founder()
    fp = founder.build_profile()
    assert fp["build"] == BUILD_FOUNDER_ORIGINAL
    assert set(fp["abilities"]["item_types"]) == set(ITEM_TYPES)
    assert fp["abilities"]["broker_file"] is True
    assert fp["metered"] is True

    limited = _mk("fred")
    lp = limited.build_profile()
    assert lp["build"] == BUILD_BLOODLINE_LIMITED
    assert lp["abilities"]["item_types"] == ["login"]
    assert lp["abilities"]["broker_file"] is False
    assert lp["abilities"]["broker_filed_read"] is False
    assert lp["metered"] is True


def test_metering_records_grants_and_refusals():
    limited = _mk("gina")
    item_id = limited.store_item("login", "svc", username="u", password="p")
    limited.get_item(item_id)
    with pytest.raises(ItemVaultError):
        limited.store_item("note", "n", text="t")  # refused
    with pytest.raises(ItemVaultError):
        limited.file_broker_credential("x.example", "u", "p")  # refused
    records = read_metering()
    by_ability = {(r["identity"], r["ability"]): r["decision"] for r in records}
    assert by_ability[("gina", "items.store.login")] == "granted"
    assert by_ability[("gina", "items.read")] == "granted"
    assert by_ability[("gina", "items.store.note")] == "refused"
    assert by_ability[("gina", "items.broker_file")] == "refused"
    # Metadata only — no secret values in the metering store.
    assert all("p" != r.get("ability") for r in records)
    blob = json.dumps(records)
    assert '"s3cret"' not in blob


def test_metering_is_hermetic_and_best_effort():
    assert read_metering(limit=5) == [] or isinstance(read_metering(limit=5), list)


# -- api_key item type (his spec 2026-09-27: vault saves API keys) -----------


def test_api_key_round_trip_sealed():
    v = _mk_founder()
    item_id = v.store_item(
        "api_key", "stripe-live",
        key="sk-live-abc123", service="stripe", scopes=["read", "write"],
    )
    rec = v.get_item(item_id)
    assert rec["type"] == "api_key"
    assert rec["fields"]["key"] == "sk-live-abc123"
    assert rec["fields"]["service"] == "stripe"
    assert rec["fields"]["scopes"] == ["read", "write"]
    # Metadata-only listing surfaces the service label, never the key.
    meta = next(m for m in v.list_items() if m["id"] == item_id)
    assert meta["service"] == "stripe"
    assert "sk-live-abc123" not in json.dumps(meta)


def test_api_key_validation():
    v = _mk_founder()
    with pytest.raises(ItemVaultError):
        v.store_item("api_key", "bad", key="  ")
    with pytest.raises(ItemVaultError):
        v.store_item("api_key", "bad", key="k", scopes="not-a-list")
    with pytest.raises(ItemVaultError):
        v.store_item("api_key", "bad", key="k", scopes=["ok", ""])
    # Service is optional; scopes default to [].
    item_id = v.store_item("api_key", "bare", key="k-only")
    rec = v.get_item(item_id)
    assert rec["fields"]["service"] == ""
    assert rec["fields"]["scopes"] == []


def test_l5_limited_identity_cannot_store_api_key():
    v = _mk("erin")
    assert not v.is_full
    with pytest.raises(ItemVaultError):
        v.store_item("api_key", "k", key="secret")
    records = read_metering()
    assert ("erin", "items.store.api_key") in {
        (r["identity"], r["ability"]) for r in records
    }


def test_l1_no_plaintext_api_key_on_disk(tmp_path):
    import secrets as _secrets

    v = _mk_founder()
    secret_key = "sk-" + _secrets.token_hex(24)
    v.store_item("api_key", "svc", key=secret_key, service="svc")
    home = Path(os.environ["LEVI_HOME"]) / ".levi" / "cybrus"
    for path, blob in _all_bytes(home):
        assert secret_key.encode() not in blob, f"plaintext API key in {path}"


def test_broker_files_api_key_founder_only():
    founder = _mk_founder()
    item_id = founder.file_broker_api_key(
        "acme-api", "ak-xyz", scopes=["read"])
    rec = founder.get_item(item_id)
    assert rec["type"] == "api_key"
    assert rec["broker_created"] is True
    assert rec["fields"]["key"] == "ak-xyz"
    limited = _mk("frank")
    with pytest.raises(ItemVaultError):
        limited.file_broker_api_key("acme-api", "ak-xyz")
    with pytest.raises(ItemVaultError):
        limited.get_item(item_id)
