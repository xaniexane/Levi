"""End-to-end Galaxy tests: install pipeline -> registry -> service directory.

Hermetic: isolated tmp HOME, local package dirs/tarballs only, no network.
Proves the two halves of Galaxy (install/registry and the service directory)
actually connect: install from a directory, register verbs, call a verb
through the directory with a capability, tamper -> refused.
"""

import json
import tarfile

import pytest

from levi.galaxy import install as galaxy_install
from levi.galaxy import trust as galaxy_trust
from levi.galaxy.registry import GalaxyRegistry
from levi.galaxy.service import GalaxyServices
from levi.governor.meter import Meter

MODULE_NAME = "gx_integ_alphamod"


def _write_pkg(src_dir) -> None:
    manifest = {
        "name": "alpha",
        "version": "1.0.0",
        "kind": "tool",
        "description": "integration test package",
        "author": "com.example",
        "entry_points": {"shout": f"{MODULE_NAME}:shout"},
        "capabilities": ["galaxy.com.example.alpha.shout"],
        "permissions": {"network": False, "fs": [], "subprocess": False},
        "min_levi_version": "0.1.0",
    }
    (src_dir / "levi-skill.json").write_text(json.dumps(manifest), encoding="utf-8")
    (src_dir / f"{MODULE_NAME}.py").write_text(
        "def shout(text=''):\n    return str(text).upper()\n", encoding="utf-8"
    )


@pytest.fixture()
def pkg_src(tmp_path):
    src = tmp_path / "pkgsrc"
    src.mkdir()
    _write_pkg(src)
    return src


@pytest.fixture()
def levi_home(tmp_path):
    home = tmp_path / "levihome"
    home.mkdir()
    return home


@pytest.fixture()
def services(tmp_path):
    return GalaxyServices(
        store_dir=tmp_path / "store",
        meter=Meter(home=tmp_path / "mhome"),
    )


def _install_and_register(pkg_src, levi_home, services):
    record = galaxy_install.install(pkg_src, home=levi_home, policy=None)
    pkg = services.register_installed(record, home=levi_home)
    return record, pkg


def test_full_pipeline_install_register_call(pkg_src, levi_home, services):
    record, pkg = _install_and_register(pkg_src, levi_home, services)
    assert pkg.id == "com.example.alpha"
    assert pkg.version == "1.0.0"
    # install registry is the source of truth for "installed"
    assert GalaxyRegistry(levi_home).get("com.example.alpha")["version"] == "1.0.0"
    # call through the directory with a capability
    cap = services.issue_capability("tester", ["galaxy.com.example.alpha.*"])
    assert (
        services.call(
            "galaxy.com.example.alpha",
            "shout",
            args=["hello"],
            capability=cap,
            grantee="tester",
        )
        == "HELLO"
    )


def test_install_from_tarball(pkg_src, levi_home, services, tmp_path):
    tarball = tmp_path / "alpha.tar.gz"
    with tarfile.open(tarball, "w:gz") as tf:
        tf.add(pkg_src, arcname=".")
    record = galaxy_install.install(tarball, home=levi_home, policy=None)
    pkg = services.register_installed(record, home=levi_home)
    assert pkg.id == "com.example.alpha"
    cap = services.issue_capability("tester", ["galaxy.com.example.alpha.shout"])
    assert (
        services.call(
            "galaxy.com.example.alpha",
            "shout",
            kwargs={"text": "hey"},
            capability=cap,
            grantee="tester",
        )
        == "HEY"
    )


def test_tamper_blocks_registration(pkg_src, levi_home, services):
    record = galaxy_install.install(pkg_src, home=levi_home, policy=None)
    # tamper with the installed copy
    installed_mod = galaxy_trust.install_dir(levi_home, record) / f"{MODULE_NAME}.py"
    installed_mod.write_text(
        "def shout(text=''):\n    return 'PWNED'\n", encoding="utf-8"
    )
    with pytest.raises(galaxy_trust.TamperError):
        services.register_installed(record, home=levi_home)
    # and nothing was registered
    assert "com.example.alpha" not in services.list_services()


def test_sync_from_registry_registers_missing(pkg_src, levi_home, tmp_path):
    galaxy_install.install(pkg_src, home=levi_home, policy=None)
    fresh = GalaxyServices(
        store_dir=tmp_path / "store2", meter=Meter(home=tmp_path / "mhome2")
    )
    assert fresh.list_services() == {}
    result = fresh.sync_from_registry(home=levi_home)
    assert result["registered"] == ["com.example.alpha"]
    assert result["skipped"] == []
    cap = fresh.issue_capability("tester", ["galaxy.com.example.alpha.*"])
    assert (
        fresh.call(
            "galaxy.com.example.alpha",
            "shout",
            args=["yo"],
            capability=cap,
            grantee="tester",
        )
        == "YO"
    )


def test_sync_skips_broken_package(pkg_src, levi_home, tmp_path):
    record = galaxy_install.install(pkg_src, home=levi_home, policy=None)
    installed_mod = galaxy_trust.install_dir(levi_home, record) / f"{MODULE_NAME}.py"
    installed_mod.write_text("broken", encoding="utf-8")
    fresh = GalaxyServices(
        store_dir=tmp_path / "store3", meter=Meter(home=tmp_path / "mhome3")
    )
    result = fresh.sync_from_registry(home=levi_home)
    assert result["registered"] == []
    assert len(result["skipped"]) == 1
    assert "com.example.alpha" in result["skipped"][0]


def test_verbs_resolve_after_reload(pkg_src, levi_home, tmp_path):
    """A fresh GalaxyServices (new process equivalent) re-resolves verbs."""
    record, _ = _install_and_register(
        pkg_src,
        levi_home,
        GalaxyServices(
            store_dir=tmp_path / "storeA", meter=Meter(home=tmp_path / "mhomeA")
        ),
    )
    reloaded = GalaxyServices(
        store_dir=tmp_path / "storeA", meter=Meter(home=tmp_path / "mhomeB")
    )
    directory = reloaded.list_services()
    assert directory["galaxy.com.example.alpha"]["verbs"] == ["shout"]
    assert not directory["galaxy.com.example.alpha"]["broken"]
    cap = reloaded.issue_capability("tester", ["galaxy.com.example.alpha.*"])
    assert (
        reloaded.call(
            "galaxy.com.example.alpha",
            "shout",
            args=["again"],
            capability=cap,
            grantee="tester",
        )
        == "AGAIN"
    )
