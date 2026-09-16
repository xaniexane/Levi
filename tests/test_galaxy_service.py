"""Hermetic tests for the Galaxy services layer (levi.galaxy.service).

No network, no daemons, no user HOME writes: every GalaxyServices under
test gets an isolated store_dir and an injected governor Meter pointed at
a tmp HOME.
"""

import os
import sys
import types

import pytest

from levi.galaxy.service import (
    ActionRefused,
    ExpiredToken,
    GalaxyServices,
    InstallError,
    InvalidSignature,
    ManifestError,
    UnknownPackage,
    UnknownPort,
    UnknownVerb,
    WrongGrantee,
)
from levi.governor.meter import Meter
from levi.revival import telescript


# ---------------------------------------------------------------------------
# Fake third-party packages (never on disk: injected into sys.modules)
# ---------------------------------------------------------------------------


def _make_module(name: str, **functions) -> types.ModuleType:
    module = types.ModuleType(name)
    for fname, fn in functions.items():
        setattr(module, fname, fn)
    sys.modules[name] = module
    return module


def _alpha_module():
    def greet(name="world"):
        return f"hello, {name}"

    def add(a, b):
        return a + b

    return _make_module("fake_galaxy_alpha", greet=greet, add=add)


def _beta_module():
    def shout(text):
        return str(text).upper()

    def via_directory(directory, capability, name):
        # Skill B calling skill A's verb THROUGH the directory — it never
        # imports fake_galaxy_alpha itself.
        return directory.call(
            "galaxy.acme.alpha",
            "greet",
            args=[name],
            capability=capability,
            grantee="beta-executor",
        )

    return _make_module(
        "fake_galaxy_beta", shout=shout, via_directory=via_directory
    )


@pytest.fixture()
def alpha_manifest():
    _alpha_module()
    return {
        "id": "acme.alpha",
        "name": "Alpha demo",
        "version": "1.0.0",
        "description": "fake skill package for tests",
        "author": "acme",
        "kind": "skill",
        "entry_points": {
            "greet": "fake_galaxy_alpha:greet",
            "add": "fake_galaxy_alpha:add",
        },
    }


@pytest.fixture()
def beta_manifest():
    _beta_module()
    return {
        "id": "acme.beta",
        "name": "Beta demo",
        "version": "2.1.0",
        "kind": "tool",
        "entry_points": {
            "shout": "fake_galaxy_beta:shout",
            "via_directory": "fake_galaxy_beta:via_directory",
        },
    }


@pytest.fixture()
def services(tmp_path):
    home = tmp_path / "home"
    svc = GalaxyServices(
        store_dir=tmp_path / "store",
        meter=Meter(home=home),
    )
    return svc


@pytest.fixture()
def installed(services, alpha_manifest):
    return services.install(alpha_manifest, source="test")


@pytest.fixture()
def cap_all(services):
    return services.issue_capability(
        "test-executor", ["galaxy.acme.alpha.*", "galaxy.acme.beta.*"]
    )


# ---------------------------------------------------------------------------
# Install / directory
# ---------------------------------------------------------------------------


def test_install_registers_verbs_on_named_port(services, installed):
    directory = services.list_services()
    assert "galaxy.acme.alpha" in directory
    entry = directory["galaxy.acme.alpha"]
    assert entry["verbs"] == ["add", "greet"]
    assert entry["version"] == "1.0.0"
    assert entry["broken"] is None
    assert len(entry["pin"]) == 64


def test_install_rejects_malformed_manifest(services):
    with pytest.raises(ManifestError):
        services.install({"id": "bad id!!", "entry_points": {"x": "m:f"}})
    with pytest.raises(ManifestError):
        services.install({"id": "ok.id", "entry_points": {}})
    with pytest.raises(ManifestError):
        services.install(
            {"id": "ok.id", "entry_points": {"x": "not-a-valid-target"}}
        )


def test_install_rejects_unresolvable_entry_point(services):
    with pytest.raises(InstallError):
        services.install(
            {
                "id": "ghost.pkg",
                "entry_points": {"x": "no_such_module_xyz:fn"},
            }
        )
    # all-or-nothing: nothing was registered
    assert "galaxy.ghost.pkg" not in services.list_services()


def test_install_duplicate_id_refused(services, alpha_manifest, installed):
    with pytest.raises(InstallError):
        services.install(alpha_manifest)


def test_remove_unregisters_port(services, installed):
    removed = services.remove("acme.alpha")
    assert removed.id == "acme.alpha"
    assert "galaxy.acme.alpha" not in services.list_services()
    with pytest.raises(UnknownPackage):
        services.info("acme.alpha")
    with pytest.raises(UnknownPackage):
        services.remove("acme.alpha")


def test_search_finds_by_description_and_verb(services, installed, beta_manifest):
    services.install(beta_manifest)
    assert [p.id for p in services.search("demo")] == [
        "acme.alpha",
        "acme.beta",
    ]
    assert [p.id for p in services.search("shout")] == ["acme.beta"]
    assert services.search("   ") == []
    assert services.search("zzz-no-match") == []


# ---------------------------------------------------------------------------
# Call path: capability gate first, metering attached
# ---------------------------------------------------------------------------


def test_call_with_valid_capability_succeeds(services, installed, cap_all):
    assert (
        services.call(
            "galaxy.acme.alpha",
            "greet",
            args=["Levi"],
            capability=cap_all,
            grantee="test-executor",
        )
        == "hello, Levi"
    )
    assert (
        services.call(
            "galaxy.acme.alpha",
            "add",
            kwargs={"a": 2, "b": 3},
            capability=cap_all,
            grantee="test-executor",
        )
        == 5
    )


def test_call_narrow_capability_grant_succeeds(services, installed):
    cap = services.issue_capability("narrow", ["galaxy.acme.alpha.greet"])
    assert (
        services.call(
            "galaxy.acme.alpha",
            "greet",
            capability=cap,
            grantee="narrow",
        )
        == "hello, world"
    )


def test_call_action_not_permitted_refused(services, installed):
    cap = services.issue_capability("narrow", ["galaxy.acme.alpha.greet"])
    with pytest.raises(ActionRefused):
        services.call(
            "galaxy.acme.alpha", "add", args=[1, 2],
            capability=cap, grantee="narrow",
        )


def test_call_tampered_capability_refused(services, installed, cap_all):
    payload, sig = cap_all.split(".")
    tampered = payload[:-1] + ("A" if payload[-1] != "A" else "B") + "." + sig
    with pytest.raises(InvalidSignature):
        services.call(
            "galaxy.acme.alpha", "greet",
            capability=tampered, grantee="test-executor",
        )


def test_call_expired_capability_refused(services, installed):
    cap = services.issue_capability("old", ["galaxy.*"], ttl_seconds=-1)
    with pytest.raises(ExpiredToken):
        services.call(
            "galaxy.acme.alpha", "greet", capability=cap, grantee="old"
        )


def test_call_wrong_grantee_refused(services, installed):
    cap = services.issue_capability("alice", ["galaxy.*"])
    with pytest.raises(WrongGrantee):
        services.call(
            "galaxy.acme.alpha", "greet", capability=cap, grantee="bob"
        )


def test_call_revoked_capability_refused(services, installed):
    cap = services.issue_capability("temp", ["galaxy.*"])
    services.revoke(cap)
    with pytest.raises(telescript.RevokedToken):
        services.call(
            "galaxy.acme.alpha", "greet", capability=cap, grantee="temp"
        )


def test_call_requires_a_capability(services, installed):
    with pytest.raises(telescript.MalformedToken):
        services.call("galaxy.acme.alpha", "greet", capability=None)


def test_call_unknown_verb(services, installed, cap_all):
    with pytest.raises(UnknownVerb):
        services.call(
            "galaxy.acme.alpha", "nope",
            capability=cap_all, grantee="test-executor",
        )


def test_call_unknown_port(services, cap_all):
    wide = services.issue_capability("test-executor", ["galaxy.*"])
    with pytest.raises(UnknownPort):
        services.call(
            "galaxy.nonexistent", "greet",
            capability=wide, grantee="test-executor",
        )
    with pytest.raises(UnknownPort):
        services.call(
            "memory", "store",
            capability=wide, grantee="test-executor",
        )


def test_cross_package_call_through_directory(services, installed, beta_manifest):
    services.install(beta_manifest)
    beta_cap = services.issue_capability(
        "beta-executor", ["galaxy.acme.beta.*", "galaxy.acme.alpha.greet"]
    )
    result = services.call(
        "galaxy.acme.beta",
        "via_directory",
        kwargs={
            "directory": services,
            "capability": beta_cap,
            "name": "Levi",
        },
        capability=beta_cap,
        grantee="beta-executor",
    )
    assert result == "hello, Levi"
    # The beta module never touched the alpha module directly.
    assert not hasattr(sys.modules["fake_galaxy_beta"], "fake_galaxy_alpha")


def test_cross_package_call_respects_inner_capability(services, installed, beta_manifest):
    # Beta's own capability does NOT cover alpha's greet: the inner call
    # through the directory must be refused, not silently permitted.
    services.install(beta_manifest)
    beta_cap = services.issue_capability("beta-executor", ["galaxy.acme.beta.*"])
    with pytest.raises(ActionRefused):
        services.call(
            "galaxy.acme.beta",
            "via_directory",
            kwargs={
                "directory": services,
                "capability": beta_cap,
                "name": "Levi",
            },
            capability=beta_cap,
            grantee="beta-executor",
        )


# ---------------------------------------------------------------------------
# Metering seam
# ---------------------------------------------------------------------------


def test_calls_are_metered(tmp_path, installed, cap_all, services):
    # one success + one refusal: both land on the governor ledger
    services.call(
        "galaxy.acme.alpha", "greet",
        capability=cap_all, grantee="test-executor",
    )
    bad = services.issue_capability("narrow", ["galaxy.acme.alpha.greet"])
    with pytest.raises(ActionRefused):
        services.call(
            "galaxy.acme.alpha", "add", args=[1, 2],
            capability=bad, grantee="narrow",
        )
    recs = services._meter.query(provider="galaxy")
    by_tool = {r.tool_name: r for r in recs}
    assert by_tool["galaxy.acme.alpha.greet"].error is None
    assert by_tool["galaxy.acme.alpha.greet"].agent_id == "test-executor"
    assert by_tool["galaxy.acme.alpha.add"].error == "ActionRefused"


# ---------------------------------------------------------------------------
# Persistence: hash pin + reload
# ---------------------------------------------------------------------------


def test_install_persists_and_reloads(tmp_path, alpha_manifest):
    store = tmp_path / "store"
    svc = GalaxyServices(store_dir=store, meter=Meter(home=tmp_path / "h1"))
    pkg = svc.install(alpha_manifest, source="test")
    pin = pkg.pin
    # fresh instance over the same store: re-resolves and re-registers
    svc2 = GalaxyServices(store_dir=store, meter=Meter(home=tmp_path / "h2"))
    entry = svc2.list_services()["galaxy.acme.alpha"]
    assert entry["pin"] == pin
    assert entry["verbs"] == ["add", "greet"]
    cap = svc2.issue_capability("e", ["galaxy.acme.alpha.greet"])
    assert svc2.call("galaxy.acme.alpha", "greet", capability=cap, grantee="e") == "hello, world"


def test_tampered_store_marks_package_broken(tmp_path, alpha_manifest):
    store = tmp_path / "store"
    svc = GalaxyServices(store_dir=store, meter=Meter(home=tmp_path / "h1"))
    svc.install(alpha_manifest)
    # attacker edits the stored record: pin no longer matches
    store_file = store / "packages.json"
    raw = store_file.read_text(encoding="utf-8")
    tampered = raw.replace('"version":"1.0.0"', '"version":"9.9.9"')
    assert tampered != raw
    store_file.write_text(tampered, encoding="utf-8")
    svc2 = GalaxyServices(store_dir=store, meter=Meter(home=tmp_path / "h2"))
    entry = svc2.list_services()["galaxy.acme.alpha"]
    assert entry["broken"] is not None
    assert "pin" in entry["broken"]
    assert entry["verbs"] == []
    cap = svc2.issue_capability("e", ["galaxy.*"])
    with pytest.raises(UnknownPort):
        svc2.call("galaxy.acme.alpha", "greet", capability=cap, grantee="e")
