"""Hermetic tests for levi.classifieds.

No network, no real HOME: ClassifiedsStore() resolves paths at call
time, so monkeypatched HOME isolates everything.
"""

from __future__ import annotations

import json

import pytest

from levi.classifieds.__main__ import main as cli_main
from levi.classifieds.classifieds import (
    ClassifiedsError,
    ClassifiedsStore,
    trust_score,
)


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    return ClassifiedsStore()


_CONTACTS = {
    "me": "chauncey",
    "my_vouches": {"ana": 1.0, "bob": 0.8},
    "contacts": [
        {"id": "ana", "name": "Ana", "vouches": {"cara": 1.0, "dan": 0.5}},
        {"id": "bob", "name": "Bob", "vouches": {"cara": 0.6}},
        {"id": "zed", "name": "Zed", "vouches": {"mallory": 1.0}},
    ],
}


def _with_contacts(st):
    st.save_contacts(_CONTACTS)
    return st


# --------------------------------------------------------------------------
# trust formula
# --------------------------------------------------------------------------

def test_trust_score_transparent():
    t = trust_score("cara", _CONTACTS)
    # via ana: min(1.0, 1.0)=1.0 ; via bob: min(0.8, 0.6)=0.6 ; total 1.6 / 2
    assert t["score"] == 0.8
    assert {m["via"] for m in t["mutuals"]} == {"ana", "bob"}
    assert "formula" in t and "1.600" in t["formula"]


def test_trust_unknown_lister_zero():
    t = trust_score("stranger", _CONTACTS)
    assert t["score"] == 0.0 and t["mutuals"] == []


def test_trust_no_self_vouch_leak():
    # zed vouches for mallory but I don't vouch for zed -> no score
    t = trust_score("mallory", _CONTACTS)
    assert t["score"] == 0.0


def test_trust_empty_contacts():
    t = trust_score("anyone", {})
    assert t["score"] == 0.0


# --------------------------------------------------------------------------
# listings
# --------------------------------------------------------------------------

def test_add_browse_search(monkeypatch, tmp_path):
    st = _with_contacts(_herm(monkeypatch, tmp_path))
    st.add("Bike", "old road bike", price="$200", category="sports",
           lister="cara")
    st.add("Lamp", category="home", lister="dan")
    rows = st.listings_with_trust()
    assert len(rows) == 2
    assert rows[0]["title"] == "Lamp"  # newest first
    assert rows[1]["trust"]["score"] == 0.8  # cara
    assert st.listings(category="sports")[0]["title"] == "Bike"
    assert st.listings(query="road bike")[0]["title"] == "Bike"
    assert st.listings(query="nope") == []


def test_add_requires_title(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    with pytest.raises(ClassifiedsError):
        st.add("   ")


def test_mark_status(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    r = st.add("Bike", lister="me")
    st.mark(r["id"], "sold")
    assert st.listings() == []  # sold hidden by default
    assert len(st.listings(include_sold=True)) == 1
    with pytest.raises(ClassifiedsError):
        st.mark(r["id"], "bogus")
    with pytest.raises(ClassifiedsError):
        st.mark("nope", "sold")


def test_vouch_records_and_reweights(monkeypatch, tmp_path):
    st = _with_contacts(_herm(monkeypatch, tmp_path))
    st.vouch("ana", "mallory", 0.5)
    t = st.trust("mallory")
    assert t["score"] == 0.25  # min(1.0, 0.5)/2
    with pytest.raises(ClassifiedsError):
        st.vouch("ghost", "x", 0.5)
    with pytest.raises(ClassifiedsError):
        st.vouch("ana", "x", 1.5)


# --------------------------------------------------------------------------
# export / import
# --------------------------------------------------------------------------

def test_export_verify_roundtrip_own_key(monkeypatch, tmp_path):
    st = _with_contacts(_herm(monkeypatch, tmp_path))
    st.add("Bike", lister="cara")
    bundle = st.export()
    assert bundle["format"] == "levi_classifieds_v1"
    assert len(bundle["attestations"]) == 1
    v = st.verify_export(bundle)
    assert v["intact"] == 1 and v["attestations"] == 1
    # trust recomputed against my graph
    assert v["my_trust_scores"][bundle["listings"][0]["id"]]["score"] == 0.8


def test_export_tamper_detected(monkeypatch, tmp_path):
    st = _with_contacts(_herm(monkeypatch, tmp_path))
    st.add("Bike", lister="cara")
    bundle = st.export()
    bundle["attestations"][0]["trust"]["score"] = 1.0  # tampered
    v = st.verify_export(bundle)
    assert v["intact"] == 0


def test_import_bundle_into_fresh_home(monkeypatch, tmp_path):
    st = _with_contacts(_herm(monkeypatch, tmp_path))
    st.add("Bike", lister="cara")
    bundle = st.export()

    monkeypatch.setenv("HOME", str(tmp_path / "home2"))
    st2 = ClassifiedsStore()
    assert st2.import_bundle(bundle) == 1
    assert st2.import_bundle(bundle) == 0  # idempotent, no duplicates
    rows = st2.listings_with_trust()
    assert rows[0]["title"] == "Bike"
    # fresh home has no contacts -> trust honestly recomputed as 0
    assert rows[0]["trust"]["score"] == 0.0


def test_import_rejects_bad_format(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    with pytest.raises(ClassifiedsError):
        st.import_bundle({"format": "nope"})


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def test_cli_add_browse_trust(monkeypatch, tmp_path, capsys):
    _with_contacts(_herm(monkeypatch, tmp_path))
    assert cli_main(["add", "Bike", "--price", "$200", "--category", "sports",
                     "--lister", "cara"]) == 0
    assert cli_main(["browse"]) == 0
    out = capsys.readouterr().out
    assert "Bike" in out and "trust 0.800" in out
    assert cli_main(["trust", "cara"]) == 0
    out = capsys.readouterr().out
    assert "formula" in out and "ana" in out


def test_cli_contacts_init_and_export_import(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert cli_main(["contacts-init", "--me", "chauncey",
                     "--contact", "ana"]) == 0
    assert cli_main(["add", "Lamp", "--lister", "ana"]) == 0
    bundle = tmp_path / "b.json"
    assert cli_main(["export", "--out", str(bundle)]) == 0
    assert "attestations" in capsys.readouterr().out

    monkeypatch.setenv("HOME", str(tmp_path / "home2"))
    assert cli_main(["import", str(bundle)]) == 0
    assert "imported 1" in capsys.readouterr().out


def test_cli_add_empty_title_fails(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    assert cli_main(["add", "   "]) == 1
