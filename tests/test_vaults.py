"""Hermetic tests for levi.vaults: tmp HOME, no network."""

import time

import pytest

from levi.memory.types import MemoryType
from levi.vaults import SHELF
from levi.vaults.transfer import export_vault, import_vault
from levi.vaults.vault import Vault, VaultError, Vaults


@pytest.fixture()
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LEVI_HOME", raising=False)
    return tmp_path / ".levi" / "vaults"


@pytest.fixture()
def manager(home):
    return Vaults(home)


def test_shelf_shape():
    assert SHELF["name"] and SHELF["summary"] and len(SHELF["items"]) >= 3


def test_create_list_get(manager):
    manager.create("alpha")
    assert manager.list() == ["alpha"]
    v = manager.get("alpha")
    assert v.name == "alpha"
    with pytest.raises(VaultError):
        manager.create("alpha")  # collision fails closed
    with pytest.raises(VaultError):
        manager.create("../evil")  # path traversal refused
    with pytest.raises(VaultError):
        manager.get("nope")


def test_vault_dir_is_owner_only(manager, home):
    manager.create("alpha")
    assert (home / "alpha").stat().st_mode & 0o777 == 0o700


def test_add_get_search(manager):
    v = manager.create("alpha")
    e = v.add(
        MemoryType.SEMANTIC, "levi runs local-first", importance=0.9, tags=["fact"]
    )
    assert v.get(e.id).content == "levi runs local-first"
    assert v.search("local-first")[0].id == e.id
    assert v.search("nothing-here") == []
    assert v.stats()["total"] == 1


def test_cross_vault_isolation(manager):
    """The core guarantee: vault B can never see vault A's contents."""
    a = manager.create("vault-a")
    b = manager.create("vault-b")
    secret = "s3cr3t-project-alpha-token-xyz"
    a.add(MemoryType.SEMANTIC, f"the token is {secret}", importance=1.0)
    # every query surface on B must be blind to A's secret
    assert b.search("s3cr3t") == []
    assert b.search("token") == []
    assert b.list() == []
    assert b.get("anything") is None
    assert b.stats()["total"] == 0
    # and A's own queries still work
    assert len(a.search("s3cr3t")) == 1
    # a fresh Vault object for B (re-read from disk) is equally blind
    b2 = Vault("vault-b", home=manager.home)
    assert b2.search("s3cr3t") == []


def test_ttl_expiry(manager):
    v = manager.create("alpha")
    v.set_policy(ttl_by_type={"working": 1}, max_entries=100)
    v.add(MemoryType.WORKING, "short-lived note")
    v.add(MemoryType.SEMANTIC, "long-lived fact")
    assert v.stats()["total"] == 2
    report = v.purge(now=time.time() + 3600)
    assert report == {"expired": 1, "over_cap": 0}
    assert v.stats()["total"] == 1
    assert v.stats()["by_type"] == {"semantic": 1}


def test_max_entries_eviction(manager):
    v = manager.create("alpha")
    v.set_policy(max_entries=2)
    v.add(MemoryType.WORKING, "low", importance=0.1)
    v.add(MemoryType.WORKING, "mid", importance=0.5)
    v.add(MemoryType.WORKING, "high", importance=0.9)
    contents = [e.content for e in v.list()]
    assert contents == ["high", "mid"]  # lowest importance evicted


def test_policy_validation(manager):
    v = manager.create("alpha")
    with pytest.raises(VaultError):
        v.set_policy(ttl_by_type={"nonsense": 10})
    with pytest.raises(VaultError):
        v.set_policy(ttl_by_type={"working": -5})
    with pytest.raises(VaultError):
        v.set_policy(max_entries=0)


def test_policy_persists_and_applies(manager):
    manager.create("alpha").set_policy(ttl_by_type={"working": 5})
    v2 = Vault("alpha", home=manager.home)
    assert v2.policy["ttl_by_type"]["working"] == 5.0


def test_export_import_roundtrip(manager, tmp_path):
    v = manager.create("alpha")
    v.set_policy(ttl_by_type={"working": 86400}, max_entries=50)
    v.add(MemoryType.SEMANTIC, "portable fact", tags=["x"])
    v.add(MemoryType.WORKING, "portable note")
    bundle = tmp_path / "alpha.levi-vault.tar.gz"
    export_vault(v, bundle)
    assert bundle.exists()
    manager.delete("alpha")
    imported = import_vault(manager, bundle)
    assert imported.name == "alpha"
    assert imported.stats()["total"] == 2
    assert imported.policy["ttl_by_type"]["working"] == 86400.0
    assert len(imported.search("portable")) == 2


def test_import_collision_fails_closed(manager, tmp_path):
    v = manager.create("alpha")
    v.add(MemoryType.WORKING, "original")
    bundle = tmp_path / "a.tar.gz"
    export_vault(v, bundle)
    with pytest.raises(VaultError):
        import_vault(manager, bundle)  # name taken, no merge
    merged = import_vault(manager, bundle, merge=True)
    assert merged.stats()["total"] == 1  # same id dedupes
    renamed = import_vault(manager, bundle, name="alpha-copy")
    assert renamed.name == "alpha-copy"
    assert renamed.stats()["total"] == 1


def test_delete(manager):
    manager.create("alpha")
    assert manager.delete("alpha") is True
    assert manager.list() == []
    assert manager.delete("alpha") is False


def test_cli_roundtrip(manager, home, capsys, monkeypatch):
    from levi.vaults.__main__ import main

    monkeypatch.setenv("LEVI_HOME", str(home.parent))
    assert main(["create", "cli"]) == 0
    assert main(["policy", "cli", "--ttl", "working=60", "--max-entries", "10"]) == 0
    assert '"working": 60.0' in capsys.readouterr().out
    assert main(["add", "cli", "hello vault", "--type", "semantic"]) == 0
    out = capsys.readouterr().out
    eid = out.split("added ")[1].split(" ")[0]
    assert main(["search", "cli", "hello"]) == 0
    assert "hello vault" in capsys.readouterr().out
    assert main(["get", "cli", eid]) == 0
    assert main(["purge", "cli"]) == 0
    assert "purged 0 expired" in capsys.readouterr().out
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0
