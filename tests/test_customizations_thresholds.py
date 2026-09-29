"""Proof for the thresholds customizations: deny-closed keeper-tuned gates."""

import json
import os
import stat

import pytest

from levi.customizations import thresholds


@pytest.fixture()
def store(tmp_path):
    return tmp_path / "thresholds.json"


def test_defaults_ship_with_no_store(store):
    assert thresholds.get("keel.band", store=store) == pytest.approx(0.10)
    assert thresholds.get("keel.persistence", store=store) == 3
    assert thresholds.get("router.min_confidence", store=store) == pytest.approx(0.35)
    assert thresholds.get("digest.max_items", store=store) == 25
    assert not store.exists()  # reading a default never creates the file


def test_set_and_get_roundtrip(store):
    assert thresholds.set("keel.band", 0.15, store=store) == pytest.approx(0.15)
    assert thresholds.get("keel.band", store=store) == pytest.approx(0.15)
    data = json.loads(store.read_text())
    assert data == {"keel.band": 0.15}  # overrides only, no defaults written


def test_reset_restores_default(store):
    thresholds.set("keel.band", 0.15, store=store)
    assert thresholds.reset("keel.band", store=store) == pytest.approx(0.10)
    assert thresholds.get("keel.band", store=store) == pytest.approx(0.10)


def test_deny_closed_unknown_gate(store):
    with pytest.raises(thresholds.ThresholdsError):
        thresholds.get("levi.overdrive", store=store)
    with pytest.raises(thresholds.ThresholdsError):
        thresholds.set("levi.overdrive", 1, store=store)


def test_deny_closed_out_of_range(store):
    with pytest.raises(thresholds.ThresholdsError):
        thresholds.set("keel.band", 2.0, store=store)
    with pytest.raises(thresholds.ThresholdsError):
        thresholds.set("keel.persistence", 0, store=store)
    with pytest.raises(thresholds.ThresholdsError):
        thresholds.set("digest.max_items", 9999, store=store)


def test_deny_closed_wrong_type(store):
    with pytest.raises(thresholds.ThresholdsError):
        thresholds.set("keel.persistence", 3.5, store=store)
    with pytest.raises(thresholds.ThresholdsError):
        thresholds.set("keel.band", "wide", store=store)
    with pytest.raises(thresholds.ThresholdsError):
        thresholds.set("keel.band", True, store=store)


def test_deny_closed_corrupt_store(store):
    store.write_text("{not json")
    with pytest.raises(thresholds.ThresholdsError):
        thresholds.get("keel.band", store=store)


def test_store_is_owner_only(store):
    thresholds.set("keel.band", 0.15, store=store)
    mode = stat.S_IMODE(os.stat(store).st_mode)
    assert mode == 0o600


def test_list_gates_reports_source(store):
    rows = {r["name"]: r for r in thresholds.list_gates(store=store)}
    assert set(rows) == set(thresholds.iter_known())
    assert rows["keel.band"]["source"] == "default"
    thresholds.set("keel.band", 0.2, store=store)
    rows = {r["name"]: r for r in thresholds.list_gates(store=store)}
    assert rows["keel.band"]["source"] == "override"
    assert rows["keel.band"]["value"] == pytest.approx(0.2)
    assert rows["keel.band"]["range"] == [0.0, 1.0]
