# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Keystone bus tests — graft contract, event bus, lifecycle.

Hermetic: pure in-memory structures, no home dir, no network. The
bus never touches disk.

Covers: contract validation collecting every violation (never
fail-fast), manifest normalization; subscribe/publish/drain with
per-subscriber receipts; unknown-topic publish as a documented no-op;
lifecycle gating of deliveries (disabled/suspended grafts get no
inbox deliveries); the disabled -> enabled -> suspended -> enabled
state machine and every illegal transition; malformed inputs.
"""

from __future__ import annotations

import pytest

from levi.dynasty.dna import AgentError
from levi.dynasty.wave.keystone_bus import (
    KNOWN_PERMISSIONS,
    ContractViolation,
    EventBus,
    LifecycleError,
    validate_graft_manifest,
)


def good_manifest(**overrides):
    manifest = {
        "name": "echo-graft",
        "version": "1.2.3",
        "permissions": ["fs.read", "clock"],
        "entry_point": "echo_graft:main",
        "sandbox": True,
    }
    manifest.update(overrides)
    return manifest


# -- contract validation ------------------------------------------------


def test_validate_good_manifest_normalizes():
    out = validate_graft_manifest(
        good_manifest(permissions=["clock", "fs.read", "clock"])
    )
    assert out == {
        "name": "echo-graft",
        "version": "1.2.3",
        "permissions": ["clock", "fs.read"],
        "entry_point": "echo_graft:main",
        "sandbox": True,
    }


def test_validate_known_permission_set():
    assert KNOWN_PERMISSIONS == {"fs.read", "fs.write", "net", "clock", "shell.exec"}


def test_validate_collects_all_violations_not_fail_fast():
    manifest = {
        "name": "  ",
        "version": "v1",
        "permissions": ["fs.read", "exec.everything", "net.admin"],
        "entry_point": "",
        "sandbox": False,
    }
    with pytest.raises(ContractViolation) as exc:
        validate_graft_manifest(manifest)
    violations = exc.value.violations
    # name, version, 2 unknown permissions, entry_point, sandbox
    assert len(violations) == 6
    joined = " ".join(violations)
    for marker in (
        "name",
        "version",
        "exec.everything",
        "net.admin",
        "entry_point",
        "sandbox",
    ):
        assert marker in joined


def test_validate_non_dict_manifest():
    for bad in (None, "manifest", ["name"], 42):
        with pytest.raises(ContractViolation) as exc:
            validate_graft_manifest(bad)
        assert exc.value.violations == ["manifest must be a dict"]


def test_validate_single_unknown_permission_named():
    with pytest.raises(ContractViolation) as exc:
        validate_graft_manifest(good_manifest(permissions=["fs.read", "root"]))
    assert len(exc.value.violations) == 1
    assert "root" in exc.value.violations[0]


def test_validate_permissions_must_be_strings():
    with pytest.raises(ContractViolation) as exc:
        validate_graft_manifest(good_manifest(permissions="fs.read"))
    assert any("permissions" in v for v in exc.value.violations)


def test_validate_version_shapes():
    assert validate_graft_manifest(good_manifest(version="2.0"))["version"] == "2.0"
    for bad in ("1", "1.2.3.4", "v1.2", "1.x", ""):
        with pytest.raises(ContractViolation):
            validate_graft_manifest(good_manifest(version=bad))


def test_validate_violation_is_typed_agent_error():
    with pytest.raises(AgentError):
        validate_graft_manifest(good_manifest(sandbox="yes"))


# -- event bus -----------------------------------------------------------


def test_bus_publish_and_drain():
    bus = EventBus()
    bus.subscribe("a", "ticks")
    bus.subscribe("b", "ticks")
    receipts = bus.publish("ticks", {"n": 1})
    assert receipts == [
        {"graft": "a", "topic": "ticks", "delivered": True},
        {"graft": "b", "topic": "ticks", "delivered": True},
    ]
    assert bus.drain("a") == [{"topic": "ticks", "payload": {"n": 1}}]
    assert bus.drain("a") == []  # drained
    assert bus.drain("b") == [{"topic": "ticks", "payload": {"n": 1}}]


def test_bus_unknown_topic_publish_is_noop():
    bus = EventBus()
    bus.subscribe("a", "ticks")
    assert bus.publish("no-such-topic", {"n": 1}) == []
    assert bus.drain("a") == []


def test_bus_subscribe_idempotent():
    bus = EventBus()
    bus.subscribe("a", "ticks")
    bus.subscribe("a", "ticks")
    assert bus.subscribers("ticks") == ["a"]
    receipts = bus.publish("ticks", {})
    assert len(receipts) == 1  # no double delivery


def test_bus_unsubscribe():
    bus = EventBus()
    bus.subscribe("a", "ticks")
    bus.unsubscribe("a", "ticks")
    assert bus.publish("ticks", {}) == []
    bus.unsubscribe("a", "ticks")  # no-op, no error


def test_bus_payload_is_deep_copied():
    bus = EventBus()
    bus.subscribe("a", "ticks")
    payload = {"n": [1, 2]}
    bus.publish("ticks", payload)
    payload["n"].append(999)
    assert bus.drain("a") == [{"topic": "ticks", "payload": {"n": [1, 2]}}]


def test_bus_drain_unknown_graft():
    bus = EventBus()
    assert bus.drain("never-heard-of-it") == []


def test_bus_bad_idents():
    bus = EventBus()
    for op in (
        lambda: bus.subscribe("", "t"),
        lambda: bus.subscribe("g", ""),
        lambda: bus.unsubscribe("g", None),
        lambda: bus.publish("", {}),
        lambda: bus.drain("  "),
        lambda: bus.state(None),
        lambda: bus.subscribers(""),
    ):
        with pytest.raises(AgentError):
            op()


def test_bus_topics_and_subscribers_introspection():
    bus = EventBus()
    bus.subscribe("b", "zeta")
    bus.subscribe("a", "zeta")
    bus.subscribe("a", "alpha")
    assert bus.topics() == ["alpha", "zeta"]
    assert bus.subscribers("zeta") == ["b", "a"]  # subscription order


# -- lifecycle ------------------------------------------------------------


def test_lifecycle_full_machine():
    bus = EventBus()
    assert bus.state("g") == "disabled"  # unknown reads disabled
    assert bus.enable("g") == "enabled"
    assert bus.suspend("g") == "suspended"
    assert bus.enable("g") == "enabled"
    assert bus.disable("g") == "disabled"
    assert bus.enable("g") == "enabled"  # disabled -> enabled again


def test_lifecycle_suspended_to_disabled():
    bus = EventBus()
    bus.subscribe("g", "t")  # first subscribe enables
    bus.suspend("g")
    assert bus.disable("g") == "disabled"


@pytest.mark.parametrize(
    "setup,op",
    [
        (lambda b: None, lambda b: b.suspend("g")),  # disabled -> suspended
        (lambda b: None, lambda b: b.disable("g")),  # disabled -> disabled
        (lambda b: b.enable("g"), lambda b: b.enable("g")),  # already enabled
        (
            lambda b: (b.enable("g"), b.suspend("g")),
            lambda b: b.suspend("g"),  # already suspended
        ),
    ],
)
def test_lifecycle_illegal_transitions(setup, op):
    bus = EventBus()
    setup(bus)
    with pytest.raises(LifecycleError):
        op(bus)


def test_lifecycle_error_is_typed_agent_error():
    bus = EventBus()
    with pytest.raises(AgentError):
        bus.suspend("g")


def test_disabled_graft_gets_no_delivery():
    bus = EventBus()
    bus.subscribe("a", "ticks")
    bus.subscribe("b", "ticks")
    bus.disable("a")
    receipts = bus.publish("ticks", {"n": 5})
    by_graft = {r["graft"]: r for r in receipts}
    assert by_graft["a"]["delivered"] is False
    assert by_graft["b"]["delivered"] is True
    assert bus.drain("a") == []
    assert bus.drain("b") != []


def test_suspended_graft_gets_no_delivery():
    bus = EventBus()
    bus.subscribe("a", "ticks")
    bus.suspend("a")
    receipts = bus.publish("ticks", {"n": 5})
    assert receipts == [{"graft": "a", "topic": "ticks", "delivered": False}]
    assert bus.drain("a") == []
    # Re-enable and deliveries resume.
    bus.enable("a")
    receipts = bus.publish("ticks", {"n": 6})
    assert receipts == [{"graft": "a", "topic": "ticks", "delivered": True}]
    assert bus.drain("a") == [{"topic": "ticks", "payload": {"n": 6}}]


def test_first_subscribe_enables_graft():
    bus = EventBus()
    assert bus.subscribe("g", "t") == "enabled"
    assert bus.state("g") == "enabled"
