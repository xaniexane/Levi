"""Tests for levi.pincards -- the keeper's always-on facts."""

import json

import pytest

import levi.pincards as pincards


@pytest.fixture()
def store(tmp_path, monkeypatch):
    path = tmp_path / "cards.json"
    monkeypatch.setattr(pincards, "STORE_PATH", path)
    return path


def test_pin_list_roundtrip(store):
    card = pincards.pin(
        "Always answer in metric units.", by="keeper", scopes=["general"]
    )
    assert card["id"] == 1
    assert card["retired"] is False
    assert pincards.list_active()[0]["text"] == "Always answer in metric units."


def test_ids_never_collide_after_retire_and_purge(store):
    pincards.pin("one")
    pincards.pin("two")
    assert pincards.retire(1, reason="stale") is True
    third = pincards.pin("three")
    assert third["id"] == 3
    ids = [c["id"] for c in pincards.list_all(include_retired=True)]
    assert len(ids) == len(set(ids))


def test_retired_cards_stop_surfacing_but_stay_in_file(store):
    pincards.pin("House Wi-Fi fix steps for the router")
    pincards.retire(1)
    assert pincards.list_active() == []
    assert len(pincards.list_all(include_retired=True)) == 1
    assert pincards.surface("router wi-fi fix") == []


def test_purge_erases_entirely(store):
    pincards.pin("temporary")
    assert pincards.purge(1) is True
    assert pincards.list_all(include_retired=True) == []
    assert pincards.purge(999) is False


def test_pin_refuses_secrets(store):
    with pytest.raises(ValueError, match="never pin secrets"):
        pincards.pin("my api_key=sk-abc123 for the thing")
    with pytest.raises(ValueError, match="never pin secrets"):
        pincards.pin("SSN on file: 123-45-6789")


def test_pin_rejects_empty_and_overlong(store):
    with pytest.raises(ValueError):
        pincards.pin("   ")
    with pytest.raises(ValueError):
        pincards.pin("x" * (pincards.MAX_CARD_CHARS + 1))


def test_surface_ranks_and_scopes(store):
    pincards.pin("House Wi-Fi troubleshooting steps for the router", scopes=["home"])
    pincards.pin("Phone number format for international calls")
    hits = pincards.surface("router troubleshooting and international phone calls", k=2)
    assert len(hits) == 2
    scoped = pincards.surface("router calls", k=2, scope="home")
    assert "Wi-Fi" in scoped[0], "scope match must sort first"


def test_corrupt_store_reads_empty(store):
    store.write_text("{not json")
    assert pincards.list_all() == []


def test_no_temp_files_left_behind(store):
    pincards.pin("one")
    pincards.pin("two")
    assert list(store.parent.glob("pincards-*.tmp")) == []
    assert len(json.loads(store.read_text())) == 2
