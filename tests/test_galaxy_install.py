"""Hermetic tests for the Galaxy registry + install + trust layer.

No network, no daemons, no real HOME writes: every test uses an isolated
tmp HOME. Sources are local directories / tarballs / zips only.
"""

import json
import tarfile
import zipfile
from pathlib import Path

import pytest

from levi.galaxy import install as ginstall
from levi.galaxy import registry as gregistry
from levi.galaxy import trust as gtrust
from levi.galaxy.install import (
    CollisionRefused,
    PermissionDenied,
    SourceError,
    install,
)
from levi.galaxy.package import PackageError
from levi.galaxy.registry import GalaxyRegistry
from levi.galaxy.trust import TamperError
from levi.revival import telescript


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def make_package(
    root: Path,
    *,
    name: str = "demo",
    author: str = "com.example",
    version: str = "1.0.0",
    kind: str = "skill",
    description: str = "A demo package for hermetic install tests",
    capabilities=("demo.run",),
    permissions: dict | None = None,
    extra_files: dict | None = None,
) -> Path:
    """Build a valid package dir with levi-skill.json + entry-point script."""
    pkg = root / f"{name}-{version}"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "run.sh").write_text("#!/bin/sh\necho demo\n", encoding="utf-8")
    (pkg / "data").mkdir(exist_ok=True)
    (pkg / "data" / "seed.txt").write_text("seed", encoding="utf-8")
    for rel, content in (extra_files or {}).items():
        p = pkg / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    manifest = {
        "name": name,
        "version": version,
        "kind": kind,
        "description": description,
        "author": author,
        "entry_points": {"run": "run.sh"},
        "capabilities": list(capabilities),
        "permissions": permissions
        if permissions is not None
        else {"network": False, "fs": [], "subprocess": False},
        "min_levi_version": "0.1.0",
    }
    (pkg / "levi-skill.json").write_text(json.dumps(manifest), encoding="utf-8")
    return pkg


def make_tarball(pkg_dir: Path, dest: Path) -> Path:
    out = dest / (pkg_dir.name + ".tar.gz")
    with tarfile.open(out, "w:gz") as tar:
        tar.add(pkg_dir, arcname=".")
    return out


def make_zip(pkg_dir: Path, dest: Path) -> Path:
    out = dest / (pkg_dir.name + ".zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in pkg_dir.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(pkg_dir).as_posix())
    return out


# ---------------------------------------------------------------------------
# install from local dir
# ---------------------------------------------------------------------------


def test_install_from_dir(tmp_path):
    home = tmp_path / "home"
    pkg = make_package(tmp_path / "src")
    record = install(pkg, home=home, policy=None)

    assert record["id"] == "com.example.demo"
    assert record["version"] == "1.0.0"
    assert record["kind"] == "skill"
    assert record["author"] == "com.example"
    assert record["granted"] == {"network": False, "fs": [], "subprocess": False}
    assert len(record["root_sha256"]) == 64
    assert record["installed_at"]

    dest = home / "galaxy" / "packages" / "com.example.demo" / "1.0.0"
    assert (dest / "levi-skill.json").is_file()
    assert (dest / "run.sh").is_file()

    # registry round-trip
    reg = GalaxyRegistry(home)
    assert reg.get("com.example.demo")["root_sha256"] == record["root_sha256"]
    assert len(reg.list()) == 1

    # hash pin verifies cleanly
    assert gtrust.verify_install(home, record) is True
    assert gtrust.pin(record) == record["root_sha256"]


def test_install_from_tarball(tmp_path):
    home = tmp_path / "home"
    pkg = make_package(tmp_path / "src")
    ball = make_tarball(pkg, tmp_path)
    record = install(ball, home=home, policy=None)
    assert record["id"] == "com.example.demo"
    assert gtrust.verify_install(home, record) is True


def test_install_from_zip(tmp_path):
    home = tmp_path / "home"
    pkg = make_package(tmp_path / "src")
    zf = make_zip(pkg, tmp_path)
    record = install(zf, home=home, policy=None)
    assert record["id"] == "com.example.demo"
    assert gtrust.verify_install(home, record) is True


def test_install_missing_source(tmp_path):
    with pytest.raises(SourceError):
        install(tmp_path / "nope", home=tmp_path / "home", policy=None)


def test_install_bad_manifest(tmp_path):
    home = tmp_path / "home"
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "levi-skill.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(PackageError):
        install(bad, home=home, policy=None)
    # nothing recorded, nothing staged
    assert GalaxyRegistry(home).list() == []
    assert not (home / "galaxy" / "packages").exists()


# ---------------------------------------------------------------------------
# permission policy
# ---------------------------------------------------------------------------


def test_permission_violation_refused_default_policy(tmp_path):
    home = tmp_path / "home"
    pkg = make_package(
        tmp_path / "src",
        permissions={"network": True, "fs": [], "subprocess": False},
    )
    with pytest.raises(PermissionDenied, match="network"):
        install(pkg, home=home, policy=None)
    assert GalaxyRegistry(home).list() == []


def test_permission_violation_subprocess(tmp_path):
    home = tmp_path / "home"
    pkg = make_package(
        tmp_path / "src",
        permissions={"network": False, "fs": [], "subprocess": True},
    )
    with pytest.raises(PermissionDenied, match="subprocess"):
        install(pkg, home=home, policy=None)


def test_permission_violation_fs_outside_policy(tmp_path):
    home = tmp_path / "home"
    pkg = make_package(
        tmp_path / "src",
        permissions={"network": False, "fs": ["data"], "subprocess": False},
    )
    # default policy allows no fs paths at all
    with pytest.raises(PermissionDenied, match="fs"):
        install(pkg, home=home, policy=None)


def test_explicit_policy_allows_requested(tmp_path):
    home = tmp_path / "home"
    pkg = make_package(
        tmp_path / "src",
        permissions={"network": True, "fs": ["data"], "subprocess": False},
    )
    record = install(
        pkg,
        home=home,
        policy={"network": True, "fs": ["data"], "subprocess": False},
    )
    assert record["granted"]["network"] is True
    assert record["granted"]["fs"] == ["data"]
    assert record["granted"]["subprocess"] is False
    assert gtrust.verify_install(home, record) is True


# ---------------------------------------------------------------------------
# collisions
# ---------------------------------------------------------------------------


def test_collision_refused_same_version(tmp_path):
    home = tmp_path / "home"
    pkg = make_package(tmp_path / "src")
    install(pkg, home=home, policy=None)
    with pytest.raises(CollisionRefused, match="already installed"):
        install(pkg, home=home, policy=None)
    assert len(GalaxyRegistry(home).list()) == 1


def test_collision_refused_different_author(tmp_path):
    # same namespaced id "com.example.evil.demo" claimed by two authors:
    # author="com.example.evil"/name="demo" vs author="com.example"/name="evil.demo"
    home = tmp_path / "home"
    install(
        make_package(tmp_path / "a", name="demo", author="com.example.evil"),
        home=home,
        policy=None,
    )
    evil = make_package(tmp_path / "b", name="evil.demo", author="com.example")
    with pytest.raises(CollisionRefused, match="claimed by"):
        install(evil, home=home, policy=None)


def test_upgrade_allowed_for_higher_version(tmp_path):
    home = tmp_path / "home"
    install(make_package(tmp_path / "v1", version="1.0.0"), home=home, policy=None)
    record = install(
        make_package(tmp_path / "v2", version="1.1.0"), home=home, policy=None
    )
    assert record["version"] == "1.1.0"
    reg = GalaxyRegistry(home)
    assert len(reg.list()) == 1  # replaced, not duplicated
    assert not (home / "galaxy" / "packages" / "com.example.demo" / "1.0.0").exists()
    assert gtrust.verify_install(home, record) is True


def test_downgrade_refused(tmp_path):
    home = tmp_path / "home"
    install(make_package(tmp_path / "v2", version="2.0.0"), home=home, policy=None)
    with pytest.raises(CollisionRefused, match="downgrade"):
        install(make_package(tmp_path / "v1", version="1.0.0"), home=home, policy=None)


# ---------------------------------------------------------------------------
# tamper detection
# ---------------------------------------------------------------------------


def test_tamper_detected_after_modifying_installed_file(tmp_path):
    home = tmp_path / "home"
    pkg = make_package(tmp_path / "src")
    record = install(pkg, home=home, policy=None)
    assert gtrust.verify_install(home, record) is True

    target = home / "galaxy" / "packages" / "com.example.demo" / "1.0.0" / "run.sh"
    target.write_text("#!/bin/sh\necho pwned\n", encoding="utf-8")
    with pytest.raises(TamperError, match="tamper detected"):
        gtrust.verify_install(home, record)


def test_tamper_detected_after_adding_file(tmp_path):
    home = tmp_path / "home"
    record = install(make_package(tmp_path / "src"), home=home, policy=None)
    (
        home / "galaxy" / "packages" / "com.example.demo" / "1.0.0" / "evil.sh"
    ).write_text("x", encoding="utf-8")
    with pytest.raises(TamperError):
        gtrust.verify_install(home, record)


def test_tamper_detected_after_removing_file(tmp_path):
    home = tmp_path / "home"
    record = install(make_package(tmp_path / "src"), home=home, policy=None)
    (
        home
        / "galaxy"
        / "packages"
        / "com.example.demo"
        / "1.0.0"
        / "data"
        / "seed.txt"
    ).unlink()
    with pytest.raises(TamperError):
        gtrust.verify_install(home, record)


def test_verify_missing_install_dir(tmp_path):
    home = tmp_path / "home"
    record = install(make_package(tmp_path / "src"), home=home, policy=None)
    import shutil

    shutil.rmtree(home / "galaxy" / "packages")
    with pytest.raises(TamperError, match="missing"):
        gtrust.verify_install(home, record)


# ---------------------------------------------------------------------------
# capability tokens (telescript reuse)
# ---------------------------------------------------------------------------


def test_capability_token_least_privilege(tmp_path):
    home = tmp_path / "home"
    record = install(
        make_package(
            tmp_path / "src",
            permissions={"network": True, "fs": ["data"], "subprocess": False},
        ),
        home=home,
        policy={"network": True, "fs": ["data"], "subprocess": False},
    )
    token = ginstall.issue_capability(record["id"], record["granted"])
    assert ginstall.verify_capability(token, "galaxy.net.fetch", record["id"]) is True
    assert (
        ginstall.verify_capability(token, "galaxy.fs.read:data/seed.txt", record["id"])
        is True
    )
    # not granted => refused
    assert (
        ginstall.verify_capability(token, "galaxy.subprocess.run", record["id"])
        is False
    )
    assert (
        ginstall.verify_capability(token, "galaxy.net.fetch", "someone.else") is False
    )


def test_guarded_package_call_refuses_unpermitted(tmp_path):
    home = tmp_path / "home"
    record = install(make_package(tmp_path / "src"), home=home, policy=None)
    token = ginstall.issue_capability(record["id"], record["granted"])
    with pytest.raises(telescript.ActionRefused):
        ginstall.guarded_package_call(
            token, "galaxy.net.fetch", lambda: "nope", expected_grantee=record["id"]
        )
    # a permitted action runs the function
    token2 = ginstall.issue_capability(
        record["id"], {"network": True, "fs": [], "subprocess": False}
    )
    assert (
        ginstall.guarded_package_call(
            token2, "galaxy.net.ping", lambda: "ran", expected_grantee=record["id"]
        )
        == "ran"
    )


def test_empty_grant_permits_nothing(tmp_path):
    token = ginstall.issue_capability(
        "com.example.demo", {"network": False, "fs": [], "subprocess": False}
    )
    assert (
        ginstall.verify_capability(token, "galaxy.net.fetch", "com.example.demo")
        is False
    )


# ---------------------------------------------------------------------------
# registry behavior
# ---------------------------------------------------------------------------


def test_registry_search(tmp_path):
    home = tmp_path / "home"
    install(
        make_package(
            tmp_path / "a", name="weather", description="hyperlocal weather forecasts"
        ),
        home=home,
        policy=None,
    )
    install(
        make_package(
            tmp_path / "b",
            name="stocks",
            author="org.data",
            description="market data",
            capabilities=("finance.quote.*",),
        ),
        home=home,
        policy=None,
    )
    reg = GalaxyRegistry(home)
    assert [r["id"] for r in reg.search("weather")] == ["com.example.weather"]
    assert [r["id"] for r in reg.search("FINANCE")] == ["org.data.stocks"]
    assert [r["id"] for r in reg.search("org.data")] == ["org.data.stocks"]
    assert reg.search("nothing-matches-this") == []
    assert reg.search("") == []


def test_registry_corrupted_lines_quarantined(tmp_path):
    home = tmp_path / "home"
    install(make_package(tmp_path / "src"), home=home, policy=None)
    reg = GalaxyRegistry(home)
    with reg.path.open("a", encoding="utf-8") as fh:
        fh.write("{this is not json\n")
        fh.write('["not", "a", "dict"]\n')
    # read still works; bad lines quarantined, not fatal
    records = reg.list()
    assert [r["id"] for r in records] == ["com.example.demo"]
    quarantined = reg.quarantined()
    assert len(quarantined) == 2
    # subsequent reads don't re-quarantine duplicates
    assert [r["id"] for r in reg.list()] == ["com.example.demo"]
    assert len(reg.quarantined()) == 2


def test_registry_remove(tmp_path):
    home = tmp_path / "home"
    install(make_package(tmp_path / "src"), home=home, policy=None)
    reg = GalaxyRegistry(home)
    assert reg.remove("com.example.demo") is True
    assert reg.remove("com.example.demo") is False
    assert reg.get("com.example.demo") is None
    assert reg.list() == []


def test_registry_atomic_write_survives_crash_midway(tmp_path):
    # simulate: add() rewrites via tmp+rename, so a failed write leaves the
    # previous file intact
    home = tmp_path / "home"
    reg = GalaxyRegistry(home)
    rec = {
        "id": "com.example.demo",
        "version": "1.0.0",
        "kind": "skill",
        "author": "com.example",
        "source": "/tmp/x",
        "root_sha256": "ab" * 32,
        "installed_at": "2026-09-15T00:00:00+00:00",
        "granted": {"network": False, "fs": [], "subprocess": False},
    }
    reg.add(rec)
    before = reg.path.read_bytes()
    with pytest.raises(_RegistryError := gregistry.RegistryError):
        reg.add({"id": "bad"})  # missing fields -> validated before any write
    assert reg.path.read_bytes() == before
    assert reg.get("com.example.demo")["version"] == "1.0.0"


def test_oath_signature_hook_absent_by_default(tmp_path):
    home = tmp_path / "home"
    record = install(make_package(tmp_path / "src"), home=home, policy=None)
    # no signature on the record -> advisory hook returns None, never raises
    assert gtrust.verify_oath_signature(record) is None
    payload = gtrust.signature_payload(record)
    assert payload.startswith(b"galaxy-install-v1\ncom.example.demo\n1.0.0\n")
