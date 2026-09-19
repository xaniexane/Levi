"""Forge registry tests — the manifest ledger for the dynasty's recreations.

Every recreation in the Forge program is one manifest: name, the *idea* it
recreates (never a product as identity), LEVI's native twist, module path,
ring placement, proving-bar status. These tests pin the registry's law:

- every static seat validates (schema, rings, proving-bar statuses)
- import-time validation is honest (live modules -> import_ok True,
  not-yet-landed modules -> import_ok False with a named error)
- the NeighborOS seat stays a recorded-only reservation
- discovery picks up later workers' self-declared manifests on re-run
- the registry is re-runnable (refresh / load_registry any time)
"""

import importlib
import json
import sys
import types

import pytest

from levi.forge import registry
from levi.forge.registry import (
    DISCOVERY_ROOTS,
    RINGS,
    STATUSES,
    Manifest,
    by_ring,
    by_status,
    discover_manifests,
    get,
    load_registry,
    refresh,
)


# -- the ledger itself ------------------------------------------------------


def test_registry_loads_and_every_seat_validates():
    reg = load_registry()
    assert len(reg) >= 11, "expected the full dynasty seat list, got %d" % len(reg)
    for m in reg.values():
        m.validate()  # must not raise


def test_manifest_schema_fields():
    for m in registry.all_manifests():
        assert m.name and isinstance(m.name, str)
        assert m.status in STATUSES, m.name
        if m.status == "reserved":
            assert m.ring is None, m.name
        else:
            assert m.ring in RINGS, m.name
            assert m.idea.strip(), "seat %r must name the recreated idea" % m.name
            assert m.twist.strip(), "seat %r must state LEVI's twist" % m.name


def test_sibling_worker_seats_are_present():
    """The other five workers' tracks each have a seat in the ledger."""
    assert get("forge-datastore").worker == "worker-2"
    assert get("forge-flow").worker == "worker-2"
    assert get("forge-computer").worker == "worker-3"
    assert get("forge-browser").worker == "worker-3"
    assert get("forge-revival").worker == "worker-4"
    assert get("forge-social").worker == "worker-5"
    assert get("forge-content").worker == "worker-6"
    assert get("forge-neighboros").worker == "worker-7"


# -- proving bar ------------------------------------------------------------


def test_forge_code_seat_is_green_and_honest():
    """The code forge ships green: tests pass, stdlib-only, no stubs."""
    m = get("forge-code")
    assert m is not None
    assert m.idea == "code collaboration"  # the idea, not a product identity
    assert m.ring == "open"
    assert m.status == "green"
    assert m.module == "levi.forge"
    assert m.import_ok is True, "levi.forge must import: %s" % m.import_error
    # green is not keeper-reviewed: the keeper has not reviewed it yet
    assert m.status != "keeper-reviewed"


def test_import_time_validation_is_honest():
    """Missing modules are recorded, not crashed on.

    Written against the LIVE tree: import_ok must match reality, whether
    worker 4 has landed the yard yet or not.
    """
    import importlib.util

    yard = get("forge-revival")
    assert yard.module == "levi.revival.yard"
    expected = importlib.util.find_spec("levi.revival.yard") is not None
    assert yard.import_ok is expected
    if not expected:
        assert "levi.revival.yard" in yard.import_error
    missing = {m.name for m in registry.seats_missing_modules()}
    assert ("forge-revival" in missing) is (not expected)


def test_proving_summary_counts():
    summary = registry.proving_summary()
    assert sum(summary["status"].values()) == len(registry.all_manifests())
    assert summary["status"]["green"] >= 1
    assert summary["status"]["in-flight"] >= 1  # the Site Lift is building
    assert summary["reserved"] == 0  # no seats on reserve right now


# -- the active Site Lift seat ----------------------------------------------


def test_neighboros_seat_is_active():
    """The Site Lift (keeper's cut 50e2979): NeighborOS is ACTIVE, in-flight,
    built by worker 7 in core/levi/neighbor/ per docs/NEIGHBOROS_SPEC.md."""
    m = get("forge-neighboros")
    assert m.status == "in-flight"
    assert m.ring == "open"
    assert m.module == "levi.neighbor"
    assert m.worker == "worker-7"
    assert m.idea == "gig dispatch"  # the idea, honestly named
    assert "90%" in m.twist  # worker_keep_floor = 0.90, the fairtrade number
    assert "50e2979" in m.notes
    m.validate()
    # import-time honesty: import_ok tracks the live tree — False until
    # worker 7's modules land, True the moment they do.
    import importlib.util

    expected = importlib.util.find_spec("levi.neighbor") is not None
    assert m.import_ok is expected


def test_reserved_seat_rejects_ring_placement():
    bad = Manifest(
        name="x",
        idea="(reserved — not named, not designed)",
        twist="(reserved — not stated)",
        module=None,
        ring="open",
        status="reserved",
    )
    with pytest.raises(ValueError):
        bad.validate()


# -- validation law ---------------------------------------------------------


def test_validate_rejects_bad_manifests():
    with pytest.raises(ValueError):
        Manifest("x", "idea", "twist", None, "open", "nope").validate()
    with pytest.raises(ValueError):
        Manifest("x", "idea", "twist", None, "plaza", "planned").validate()
    with pytest.raises(ValueError):
        Manifest("x", "idea", "twist", None, None, "planned").validate()
    with pytest.raises(ValueError):
        Manifest("x", "  ", "twist", None, "open", "planned").validate()
    with pytest.raises(ValueError):
        Manifest("x", "idea", "  ", None, "open", "planned").validate()
    with pytest.raises(ValueError):
        Manifest("", "idea", "twist", None, "open", "planned").validate()


def test_queries():
    assert {m.name for m in by_ring("open")} >= {
        "forge-code",
        "forge-datastore",
        "forge-social",
    }
    assert {m.name for m in by_status("green")} == {"forge-code"}
    assert {m.name for m in by_status("in-flight")} == {"forge-neighboros"}
    assert by_status("reserved") == []
    assert get("no-such-seat") is None


def test_as_json_is_serializable():
    payload = registry.as_json()
    text = json.dumps(payload)
    assert "forge-code" in text
    assert "code collaboration" in text


# -- discovery: later workers get picked up on re-run -----------------------


def _write_pkg(tmp_path, monkeypatch, pkg_name, modules):
    """Build a fake dynasty root package in tmp and put it on sys.path."""
    pkg_dir = tmp_path / pkg_name
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    for mod_name, body in modules.items():
        (pkg_dir / (mod_name + ".py")).write_text(body)
    monkeypatch.syspath_prepend(str(tmp_path))
    return pkg_name


def test_discovery_picks_up_self_declared_manifest(tmp_path, monkeypatch):
    root = _write_pkg(
        tmp_path,
        monkeypatch,
        "fake_forge_dynasty",
        {
            "newrecreation": (
                "FORGE_MANIFEST = {\n"
                '    "name": "forge-fake",\n'
                '    "idea": "fake idea",\n'
                '    "twist": "fake twist",\n'
                '    "ring": "open",\n'
                '    "status": "in-flight",\n'
                '    "worker": "worker-9",\n'
                "}\n"
            ),
        },
    )
    found = {m.name: m for m in discover_manifests(roots=(root,))}
    assert "forge-fake" in found
    m = found["forge-fake"]
    assert m.discovered is True
    assert m.import_ok is True
    assert m.worker == "worker-9"


def test_discovery_ignores_malformed_declarations(tmp_path, monkeypatch):
    root = _write_pkg(
        tmp_path,
        monkeypatch,
        "fake_forge_dynasty2",
        {
            "broken": "FORGE_MANIFEST = {'name': 'forge-broken'}\n",  # bad ring
            "notadict": "FORGE_MANIFEST = 42\n",
            "plain": "X = 1\n",  # no declaration at all
        },
    )
    found = {m.name: m for m in discover_manifests(roots=(root,))}
    assert "forge-broken" not in found
    assert len(found) == 0


def test_discovery_overrides_static_seat_on_name_clash(tmp_path, monkeypatch):
    root = _write_pkg(
        tmp_path,
        monkeypatch,
        "fake_forge_dynasty3",
        {
            "code": (
                "FORGE_MANIFEST = {\n"
                '    "name": "forge-code",\n'
                '    "idea": "code collaboration",\n'
                '    "twist": "declared twist wins",\n'
                '    "ring": "open",\n'
                '    "status": "ready-for-review",\n'
                "}\n"
            ),
        },
    )
    reg = load_registry(roots=DISCOVERY_ROOTS + (root,))
    m = reg["forge-code"]
    assert m.discovered is True
    assert m.twist == "declared twist wins"
    assert m.status == "ready-for-review"


def test_refresh_is_rerunnable():
    first = refresh()
    second = refresh()
    assert isinstance(first, dict) and isinstance(second, dict)
    assert set(first) == set(second)
    assert {m.name for m in by_status("green")} == {"forge-code"}


def test_load_registry_does_not_touch_global():
    before = {m.name for m in registry.all_manifests()}
    reg = load_registry(roots=("levi.forge",))
    assert set(reg) >= before  # static seats always present
    assert {m.name for m in registry.all_manifests()} == before
