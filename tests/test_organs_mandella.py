"""organs/mandella tests: phantoms haunt — unresolved-stake ledger.

Proving bar: run_mandella returns the unchosen options as phantoms (excluding
the recommended stake, deterministic haunt text); the in-memory stake ledger
records, lists oldest-first, and fail-closes on unknown/double resolution;
haunt_check surfaces phantoms for open stakes only; format_mandella appends
the phantoms section; and the pre-existing run_mandella behavior
(recommendation rotation, unknown-domain fallback) is unchanged.

This file covers the organ; test_form_mandella.py covers the identity
reconstruction MandellaEngine — no overlap.
"""

import pytest

from levi.organs import mandella
from levi.organs.mandella import (
    format_mandella,
    haunt_check,
    list_open_stakes,
    record_stake,
    resolve_stake,
    run_mandella,
)


@pytest.fixture(autouse=True)
def _clean_ledger():
    mandella._stake_ledger.clear()
    yield
    mandella._stake_ledger.clear()


def _decision(seed="s1", domain="crisis"):
    r = run_mandella(domain, seed=seed)
    return {
        "domain": r["domain"],
        "chosen": r["recommended"],
        "phantoms": r["phantoms"],
        "ts": "2026-09-18T19:45:00-05:00",
        "seed": seed,
    }


# --- phantoms ----------------------------------------------------------------


def test_phantoms_exclude_recommended():
    r = run_mandella("crisis", seed="abc")
    assert r["recommended"] == r["options"][0]["label"]
    labels = [p["label"] for p in r["phantoms"]]
    assert r["recommended"] not in labels
    assert len(r["phantoms"]) == len(r["options"]) - 1
    assert set(labels) | {r["recommended"]} == {o["label"] for o in r["options"]}


def test_phantom_shape_and_risk_note():
    r = run_mandella("security", seed="z")
    for p in r["phantoms"]:
        assert set(p.keys()) == {"label", "risk", "note", "haunt"}
        assert p["risk"] in ("low", "medium", "high")


def test_haunt_text_deterministic():
    a = run_mandella("resource", seed="det")["phantoms"]
    b = run_mandella("resource", seed="det")["phantoms"]
    assert [p["haunt"] for p in a] == [p["haunt"] for p in b]
    for p in a:
        # templated from label + note, nothing invented beyond the template
        assert p["label"] in p["haunt"]
        assert p["note"] in p["haunt"]
        assert (
            p["haunt"] == f"Ignoring '{p['label']}' forfeits its promise: {p['note']}."
        )


# --- ledger ------------------------------------------------------------------


def test_ledger_record_list_resolve_round_trip():
    sid = record_stake(_decision(seed="r1"))
    assert isinstance(sid, str) and len(sid) == 16
    opens = list_open_stakes()
    assert len(opens) == 1
    assert opens[0]["id"] == sid
    assert opens[0]["chosen"] == run_mandella("crisis", seed="r1")["recommended"]
    assert opens[0]["resolved"] is None
    resolved = resolve_stake(sid, "the reserve was spent and held")
    assert resolved["resolved"] is True
    assert resolved["outcome"] == "the reserve was spent and held"
    assert list_open_stakes() == []


def test_record_id_deterministic_from_content():
    assert record_stake(_decision(seed="d1")) == record_stake(_decision(seed="d1"))
    assert len(list_open_stakes()) == 1  # re-recorded, not duplicated
    assert record_stake(_decision(seed="d2")) != record_stake(_decision(seed="d1"))


def test_list_open_oldest_first():
    for seed in ("o1", "o2", "o3"):
        record_stake(_decision(seed=seed))
    ids = [s["id"] for s in list_open_stakes()]
    assert ids == [
        record_stake(_decision(seed="o1")),
        record_stake(_decision(seed="o2")),
        record_stake(_decision(seed="o3")),
    ]
    # resolving the middle one drops it; order of the rest is preserved
    resolve_stake(ids[1], "cut scope instead")
    assert [s["id"] for s in list_open_stakes()] == [ids[0], ids[2]]


def test_resolve_unknown_id_raises():
    with pytest.raises(ValueError):
        resolve_stake("deadbeefdeadbeef", "nope")


def test_double_resolve_raises():
    sid = record_stake(_decision(seed="dr"))
    resolve_stake(sid, "first")
    with pytest.raises(ValueError):
        resolve_stake(sid, "second")


def test_haunt_check_open_stake():
    r = run_mandella("security", seed="h1")
    sid = record_stake(_decision(seed="h1", domain="security"))
    hc = haunt_check(sid)
    assert hc["stake_id"] == sid
    assert hc["domain"] == "security"
    assert hc["chosen"] == r["recommended"]
    assert [p["label"] for p in hc["phantoms"]] == [p["label"] for p in r["phantoms"]]
    assert isinstance(hc["pressure"], str)
    assert "\n" not in hc["pressure"]
    assert r["recommended"] in hc["pressure"]
    assert hc["phantoms"][0]["label"] in hc["pressure"]


def test_haunt_check_unknown_raises():
    with pytest.raises(ValueError):
        haunt_check("deadbeefdeadbeef")


def test_haunt_check_resolved_raises():
    sid = record_stake(_decision(seed="hr"))
    resolve_stake(sid, "done")
    with pytest.raises(ValueError):
        haunt_check(sid)


def test_record_stake_rejects_bad_decision():
    with pytest.raises(ValueError):
        record_stake({"domain": "crisis"})  # missing keys
    with pytest.raises(ValueError):
        record_stake("not a dict")


# --- format ------------------------------------------------------------------


def test_format_appends_phantoms_section():
    r = run_mandella("crisis", seed="f1")
    out = format_mandella(r)
    assert "Phantoms (unresolved):" in out
    for p in r["phantoms"]:
        assert p["label"] in out
        assert p["haunt"] in out
    # original lines identical: phantoms section comes after the commit line
    assert out.index("Commit is yours") < out.index("Phantoms (unresolved):")


def test_format_without_phantoms_is_unchanged():
    r = run_mandella("crisis", seed="f2")
    del r["phantoms"]
    out = format_mandella(r)
    assert "Phantoms (unresolved):" not in out
    assert f"=== Mandella [{r['domain']}] ===" in out
    assert f"Premise: {r['premise']}" in out
    assert f"Recommended stake: {r['recommended']}" in out


# --- existing behavior unchanged ----------------------------------------------


def test_recommended_rotation_unchanged():
    # rotation is a pure function of seed+domain; pin it against known pairs
    a = run_mandella("crisis", seed="pin1")["recommended"]
    assert a == run_mandella("crisis", seed="pin1")["recommended"]
    assert run_mandella("crisis", seed="pin1")["recommended"] == a
    seen = {run_mandella("crisis", seed=f"pin{i}")["recommended"] for i in range(6)}
    assert len(seen) > 1  # rotation actually moves emphasis


def test_unknown_domain_falls_back_to_build():
    r = run_mandella("not-a-domain", seed="u1")
    assert r["domain"] == "build"
    assert r["premise"] == mandella.DOMAINS["build"]
    assert r["recommended"] == r["options"][0]["label"]


def test_non_string_inputs_raise():
    with pytest.raises(ValueError):
        run_mandella(123)
    with pytest.raises(ValueError):
        run_mandella("crisis", seed=7)
