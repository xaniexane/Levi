# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Forgehand graft tests — signed sandboxed graft API.

Hermetic: no network, no daemons. Tests cover the manifest model
(create/sign/verify), tampered-signature rejection, the registry's
verify-AND-policy install gate, idempotent reinstalls, upgrades,
downgrade refusal, and sandbox policy violations (net without
consent, fs.write without scope, unknown capabilities).
"""

from __future__ import annotations

import json

import pytest

from levi.dynasty.wave.forgehand_grafts import (
    CAPABILITIES,
    GraftError,
    GraftRegistry,
    canonical_json,
    create,
    policy_check,
    sign,
    verify,
)


KEY = b"forgehand-test-key-001"
OTHER_KEY = b"a-different-key-999"


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    home = tmp_path / "levi-home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    return home


def _manifest(**over):
    m = create(
        "graft-echo",
        "1.2.0",
        ["fs.read", "clock"],
        "echo:main",
    )
    m.update(over)
    return m


# -- manifest model -----------------------------------------------------


def test_create_manifest_shape(tmp_home):
    m = create("graft-x", "1.0", ["clock"], "x:run")
    assert m["kind"] == "levi-graft"
    assert m["name"] == "graft-x"
    assert m["version"] == "1.0"
    assert m["permissions"] == ["clock"]
    assert m["entry"] == "x:run"
    assert m["net_consent"] is False
    assert m["fs_scope"] == []
    assert policy_check(m) == []


def test_create_rejects_unknown_capability(tmp_home):
    with pytest.raises(GraftError):
        create("g", "1.0", ["teleport"], "g:run")
    with pytest.raises(GraftError):
        create("g", "1.0", [123], "g:run")


def test_create_rejects_malformed_fields(tmp_home):
    with pytest.raises(GraftError):
        create("", "1.0", [], "g:run")
    with pytest.raises(GraftError):
        create("g", "", [], "g:run")
    with pytest.raises(GraftError):
        create("g", "1.0-beta", [], "g:run")
    with pytest.raises(GraftError):
        create("g", "1.0", [], "")
    with pytest.raises(GraftError):
        create("g", "1.0", [], "g:run", net_consent="yes")
    with pytest.raises(GraftError):
        create("g", "1.0", [], "g:run", fs_scope=["ok", 5])


def test_create_dedups_permissions(tmp_home):
    m = create("g", "1.0", ["clock", "clock"], "g:run")
    assert m["permissions"] == ["clock"]


# -- signing / verification ----------------------------------------------


def test_sign_verify_round_trip(tmp_home):
    m = _manifest()
    sig = sign(m, KEY)
    assert verify(m, sig, KEY) is True
    # str keys work the same
    assert sign(m, "forgehand-test-key-001") == sig


def test_canonical_json_is_deterministic(tmp_home):
    m1 = create("g", "1.0", ["clock"], "g:run")
    m2 = create("g", "1.0", ["clock"], "g:run")
    assert canonical_json(m1) == canonical_json(m2)
    # key order in the dict does not matter — canonical form sorts
    jumbled = dict(reversed(list(m1.items())))
    assert canonical_json(jumbled) == canonical_json(m1)


def test_tampered_manifest_fails_verify(tmp_home):
    m = _manifest()
    sig = sign(m, KEY)
    for poison in ("name", "version", "permissions", "entry", "net_consent"):
        tampered = dict(m)
        tampered[poison] = "EVIL" if poison != "permissions" else ["net"]
        assert verify(tampered, sig, KEY) is False


def test_wrong_key_fails_verify(tmp_home):
    m = _manifest()
    sig = sign(m, KEY)
    assert verify(m, sig, OTHER_KEY) is False


def test_signature_replay_across_keys_fails(tmp_home):
    m = _manifest()
    assert verify(m, sign(m, OTHER_KEY), KEY) is False


def test_malformed_signature_inputs(tmp_home):
    m = _manifest()
    with pytest.raises(GraftError):
        verify(m, "", KEY)
    with pytest.raises(GraftError):
        verify(m, None, KEY)
    with pytest.raises(GraftError):
        sign(m, b"")
    with pytest.raises(GraftError):
        sign(m, 42)
    with pytest.raises(GraftError):
        sign("not-a-dict", KEY)


def test_signature_is_bound_to_exact_bytes(tmp_home):
    m = _manifest()
    sig = sign(m, KEY)
    # re-encoding with different whitespace still verifies (canonical)
    blob = json.dumps(m, sort_keys=True, separators=(",", ":"))
    reparsed = json.loads(blob)
    assert verify(reparsed, sig, KEY) is True


# -- sandbox policy -------------------------------------------------------


def test_policy_net_requires_consent(tmp_home):
    m = create("netg", "1.0", ["net"], "n:run")
    assert policy_check(m) == ["capability 'net' requires explicit user consent"]
    m2 = create("netg", "1.0", ["net"], "n:run", net_consent=True)
    assert policy_check(m2) == []


def test_policy_fswrite_requires_scope(tmp_home):
    m = create("fsw", "1.0", ["fs.write"], "f:run")
    assert policy_check(m) == ["capability 'fs.write' requires a declared fs_scope"]
    m2 = create("fsw", "1.0", ["fs.write"], "f:run", fs_scope=["scratch/"])
    assert policy_check(m2) == []


def test_policy_flags_foreign_capabilities(tmp_home):
    m = _manifest()
    m["permissions"] = ["clock", "root.all"]
    assert "undeclared capability: 'root.all'" in policy_check(m)


def test_policy_rejects_malformed_manifest(tmp_home):
    assert policy_check("nope") == ["manifest must be a dict"]
    assert "manifest kind must be 'levi-graft'" in policy_check({"kind": "x"})
    m = _manifest()
    m["permissions"] = "clock"
    assert "permissions must be a list" in policy_check(m)


def test_capability_set_is_closed(tmp_home):
    assert CAPABILITIES == frozenset(
        {"fs.read", "fs.write", "net", "clock", "shell.exec"}
    )


# -- registry ---------------------------------------------------------------


def test_install_and_list(tmp_home):
    reg = GraftRegistry()
    m = _manifest()
    installed = reg.install(m, sign(m, KEY), KEY)
    assert installed == m
    listed = reg.list_grafts()
    assert len(listed) == 1
    assert listed[0]["name"] == "graft-echo"
    # listed copies can't mutate the registry
    listed[0]["name"] = "corrupted"
    assert reg.get("graft-echo")["name"] == "graft-echo"


def test_install_rejects_bad_signature(tmp_home):
    reg = GraftRegistry()
    m = _manifest()
    tampered = dict(m)
    tampered["permissions"] = ["net"]  # widened after signing
    with pytest.raises(GraftError):
        reg.install(tampered, sign(m, KEY), KEY)
    assert reg.list_grafts() == []


def test_install_rejects_policy_violations(tmp_home):
    reg = GraftRegistry()
    m = create("netg", "1.0", ["net"], "n:run")  # no consent
    with pytest.raises(GraftError):
        reg.install(m, sign(m, KEY), KEY)
    assert reg.list_grafts() == []


def test_reinstall_same_version_is_idempotent(tmp_home):
    reg = GraftRegistry()
    m = _manifest()
    sig = sign(m, KEY)
    reg.install(m, sig, KEY)
    again = reg.install(dict(m), sig, KEY)
    assert again["version"] == "1.2.0"
    assert len(reg.list_grafts()) == 1


def test_version_upgrade_replaces(tmp_home):
    reg = GraftRegistry()
    v1 = create("up", "1.0.0", ["clock"], "up:run")
    reg.install(v1, sign(v1, KEY), KEY)
    v2 = create("up", "1.1.0", ["clock", "fs.read"], "up:run")
    reg.install(v2, sign(v2, KEY), KEY)
    assert reg.get("up")["version"] == "1.1.0"
    assert reg.get("up")["permissions"] == ["clock", "fs.read"]
    assert len(reg.list_grafts()) == 1


def test_downgrade_refused(tmp_home):
    reg = GraftRegistry()
    v2 = create("up", "2.0", ["clock"], "up:run")
    reg.install(v2, sign(v2, KEY), KEY)
    v1 = create("up", "1.9", ["clock"], "up:run")
    with pytest.raises(GraftError):
        reg.install(v1, sign(v1, KEY), KEY)
    assert reg.get("up")["version"] == "2.0"


def test_uninstall(tmp_home):
    reg = GraftRegistry()
    m = _manifest()
    reg.install(m, sign(m, KEY), KEY)
    reg.uninstall("graft-echo")
    assert reg.list_grafts() == []
    assert reg.get("graft-echo") is None
    with pytest.raises(GraftError):
        reg.uninstall("graft-echo")


def test_registry_holds_multiple_grafts(tmp_home):
    reg = GraftRegistry()
    for name in ("alpha", "beta", "gamma"):
        m = create(name, "1.0", ["clock"], f"{name}:run")
        reg.install(m, sign(m, KEY), KEY)
    assert sorted(g["name"] for g in reg.list_grafts()) == ["alpha", "beta", "gamma"]
    reg.uninstall("beta")
    assert sorted(g["name"] for g in reg.list_grafts()) == ["alpha", "gamma"]
