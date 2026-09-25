"""Tests for revival wave 06 — crafts (d): guilds, apprenticeship, trust
chains, metrology. Original LEVI mechanisms, stdlib only."""

import pytest
from dataclasses import FrozenInstanceError

from levi.revival import (
    bound_tiers,
    fermentation_scheduler,
    giornata_record,
    healing_mortar,
    sacrificial_layers,
    scribe_fit,
    ultramarine_filter,
    wattle_daub,
)


# ---------------------------------------------------------------- healing_mortar


def test_mortar_lay_and_get_roundtrip():
    store = healing_mortar.MortarStore()
    rec = store.lay("r1", "the wall remembers")
    assert store.get("r1")["body"] == "the wall remembers"
    assert rec["seal"]  # sealed at lay time


def test_mortar_repair_heals_tampered_record_from_reserve():
    store = healing_mortar.MortarStore()
    store.lay("r1", "original body")
    store.crack("r1", mode="tamper")
    assert store.inspect("r1") == ["seal-mismatch"]
    healed = store.repair()
    assert len(healed) == 1
    assert healed[0].source == "reserve"
    assert store.get("r1")["body"] == "original body"
    assert store.get("r1")["healed"] is True


def test_mortar_repair_heals_dropped_field():
    store = healing_mortar.MortarStore()
    store.lay("r1", "body text")
    store.crack("r1", mode="drop_field")
    cracks = store.inspect("r1")
    assert any(c.startswith("missing-field:") for c in cracks)
    store.repair()
    assert store.inspect("r1") == []
    assert store.get("r1")["body"] == "body text"


def test_mortar_survey_skips_sound_records():
    store = healing_mortar.MortarStore()
    store.lay("good", "sound")
    store.lay("bad", "will crack")
    store.crack("bad")
    survey = store.survey()
    assert survey["good"] == []
    assert survey["bad"] != []
    assert store.repair()[0].record_id == "bad"
    assert store.reserve_status()["spent"] == 1


# ------------------------------------------------------------------- scribe_fit


def _bench():
    schema = {
        "temp": scribe_fit.FieldRule(float, low=-50.0, high=60.0),
        "name": scribe_fit.FieldRule(str),
    }
    return scribe_fit.ScribeBench(schema)


def test_scribe_fits_irregular_payload_without_touching_schema():
    bench = _bench()
    before = dict(bench.schema)
    bench.scribe("furnace", offsets={"temp": -273.15}, note="kelvin probe")
    rec = bench.join("furnace", {"temp": 300.15, "name": "kiln"})
    assert rec == {"temp": 27.0, "name": "kiln"}
    assert bench.schema == before  # the inerrant reference never bends
    assert bench.misfit("furnace") > 0.0


def test_scribe_corrections_absorb_string_irregularity():
    bench = _bench()
    bench.scribe("legacy", corrections={"temp": lambda v: float(str(v).rstrip("C"))})
    rec = bench.join("legacy", {"temp": "21.5C", "name": "room"})
    assert rec["temp"] == 21.5


def test_scribe_rejects_what_no_shim_can_fix():
    bench = _bench()
    with pytest.raises(scribe_fit.ScribeError):
        bench.join("wild", {"temp": 999.0, "name": "sun"})  # above level
    with pytest.raises(scribe_fit.ScribeError):
        bench.join("wild", {"name": "no-temp"})  # missing required field
    with pytest.raises(scribe_fit.ScribeError):
        bench.join("wild", {"temp": "warm", "name": "x"})  # wrong dtype


def test_scribe_extra_keys_left_at_the_door():
    bench = _bench()
    rec = bench.join("plain", {"temp": 20.0, "name": "ok", "junk": 1})
    assert "junk" not in rec
    assert bench.misfit("plain") == 0.0


# ------------------------------------------------------------------ wattle_daub


def test_wattle_weave_link_and_walk():
    wd = wattle_daub.WattleDaub()
    a = wd.weave("indigo vat")
    b = wd.weave("weekly rhythm")
    wd.link(a.id, b.id, kind="needs")
    assert (b.id, "needs") in wd.neighbors(a.id)
    assert wd.neighbors(a.id, kind="reminds") == []


def test_wattle_press_consolidates_and_rewet_restores():
    wd = wattle_daub.WattleDaub()
    n = wd.weave("murex")
    wd.stake_note(n.id, "thousands of snails per gram")
    wd.stake_note(n.id, "binds wool without mordant")
    daub = wd.press(n.id, summary="purple dye: costly, permanent")
    assert wd.consolidated(n.id) == "purple dye: costly, permanent"
    notes = wd.rewet(n.id)
    assert len(notes) == 2
    assert any("snails" in t for t in notes)
    assert wd.nodes[n.id].daub.damp is True
    # daub sources are provenance, not the summary itself
    assert daub.source_ids and len(daub.source_ids) == 2


def test_wattle_rewet_without_daub_raises():
    wd = wattle_daub.WattleDaub()
    n = wd.weave("bare")
    with pytest.raises(KeyError):
        wd.rewet(n.id)


# ----------------------------------------------------------- sacrificial_layers


def test_thatch_recoat_lays_sacrificial_surface():
    th = sacrificial_layers.Thatch()
    th.recoat("roof", "coat-1")
    th.write("roof", "outer note")
    assert th.read("roof") == ["outer note"]
    assert th.depth("roof") == 1
    assert th.seasoned("roof") == []  # nothing beneath the first coat


def test_thatch_weather_ages_and_recoat_buries():
    th = sacrificial_layers.Thatch()
    th.recoat("roof", "coat-1")
    th.write("roof", "old note")
    th.weather("roof")
    th.weather("roof")
    assert th.erosion("roof") > 0.0
    th.recoat("roof", "coat-2")
    th.write("roof", "new note")
    assert th.read("roof", coats=2) == ["new note", "old note"]  # outside-in
    seasoned = th.seasoned("roof")
    assert len(seasoned) == 1 and not seasoned[0].sacrificial


def test_thatch_trim_folds_oldest_notes_upward():
    th = sacrificial_layers.Thatch(max_coats=2)
    th.recoat("wall", "c1")
    th.write("wall", "deepest")
    th.recoat("wall", "c2")
    th.write("wall", "middle")
    th.recoat("wall", "c3")  # c1 must fold into c2, not vanish
    assert th.depth("wall") == 2
    all_notes = th.read("wall", coats=2)
    assert "deepest" in all_notes and "middle" in all_notes


# -------------------------------------------------------------- giornata_record


def test_giornata_carbonates_and_verifies():
    j = giornata_record.FrescoJournal()
    j.begin_day("2026-09-16")
    j.paint("note", "the vat lives", now=1.0)
    rec = j.close_day()
    assert j.verify(rec.seal) is True
    assert rec.entries[0] == (1.0, "note", "the vat lives")


def test_giornata_sealed_records_are_immutable():
    j = giornata_record.FrescoJournal()
    j.begin_day("2026-09-16")
    j.paint("note", "first", now=1.0)
    rec = j.close_day()
    with pytest.raises(FrozenInstanceError):
        rec.entries = ()  # frozen dataclass: stone, not plaster


def test_giornata_revision_lays_new_layer():
    j = giornata_record.FrescoJournal()
    j.begin_day("2026-09-16")
    j.paint("note", "first", now=1.0)
    old = j.close_day()
    new = j.revise(old.seal, "2026-09-17", [("correction", "amended")])
    assert new.seal != old.seal
    assert new.supersedes == old.seal
    assert len(new.entries) == 2  # old entries carried into the new layer
    assert j.current("2026-09-16").seal == old.seal
    assert j.verify(old.seal) and j.verify(new.seal)
    assert new.prev_seal == old.seal  # chain links like plaster courses


def test_giornata_requires_open_day():
    j = giornata_record.FrescoJournal()
    with pytest.raises(ValueError):
        j.paint("note", "no plaster")
    with pytest.raises(ValueError):
        j.close_day()


# ----------------------------------------------------------- ultramarine_filter


def test_ultramarine_three_pass_separation():
    uf = ultramarine_filter.Ultramarine()
    claims = [
        ultramarine_filter.Claim("the vat is fed weekly", "dyer-a"),
        ultramarine_filter.Claim("the vat is fed weekly", "dyer-b"),
        ultramarine_filter.Claim("snails hate mondays", "gossip"),
        ultramarine_filter.Claim("   ", "noise"),
    ]
    report = uf.separate(claims)
    assert len(report["stripped"]) == 1
    assert report["facts"] and report["ash"]
    assert uf.fact_texts() == ["the vat is fed weekly"]
    assert uf.ash_texts() == ["snails hate mondays"]


def test_ultramarine_ash_never_merges_with_facts():
    uf = ultramarine_filter.Ultramarine()
    uf.separate([ultramarine_filter.Claim("a hunch", "one")])
    hunch = uf.query("a hunch")
    assert hunch is not None and not hunch.is_fact()
    assert hunch.text not in uf.fact_texts()
    # promotion moves it out of the quarantine — it never edits ash into a fact
    uf.promote("a hunch", "two")
    assert uf.query("a hunch").is_fact() is True
    assert "a hunch" not in uf.ash


def test_ultramarine_single_source_stays_ash():
    uf = ultramarine_filter.Ultramarine(fact_threshold=3)
    uf.separate(
        [
            ultramarine_filter.Claim("twice-told", "a"),
            ultramarine_filter.Claim("twice-told", "b"),
        ]
    )
    assert uf.fact_texts() == []
    assert len(uf.ash_texts()) == 1


# ----------------------------------------------------------------- bound_tiers


def test_bound_tiers_write_charges_and_binds():
    bt = bound_tiers.BoundTiers()
    bt.grant_budget(200)
    rec = bt.write("r1", "purple", "wool-batch-7", "the precious gram")
    assert rec.cost_paid == 100
    assert rec.substrate == "wool-batch-7"
    assert bt.budget == 100
    assert bt.read("r1").body == "the precious gram"


def test_bound_tiers_rebinding_always_refused():
    bt = bound_tiers.BoundTiers()
    bt.grant_budget(200)
    bt.write("r1", "shell", "wool-a", "cheap note")
    with pytest.raises(bound_tiers.BindingError):
        bt.rebind("r1", "wool-b")
    # ...and re-writing at the same or a higher tier is refused too
    with pytest.raises(bound_tiers.BindingError):
        bt.write("r1", "vat", "wool-a", "upgrade attempt")


def test_bound_tiers_downgrade_allowed_but_costly_tiers_need_budget():
    bt = bound_tiers.BoundTiers()
    bt.grant_budget(100)
    bt.write("r1", "purple", "wool-a", "precious")
    assert bt.budget == 0
    # one-way downgrade to a cheaper tier is allowed
    bt.grant_budget(5)
    rec = bt.write("r1", "shell", "wool-a", "demoted copy")
    assert rec.tier == "shell"
    # a purple write without budget is refused — the harvest is finite
    bt2 = bound_tiers.BoundTiers()
    with pytest.raises(bound_tiers.BindingError):
        bt2.write("r2", "purple", "wool-a", "unfunded")


def test_bound_tiers_purple_refuses_bulk_export():
    bt = bound_tiers.BoundTiers()
    bt.grant_budget(500)
    bt.write("p1", "purple", "wool-a", "precious-1")
    bt.write("s1", "shell", "wool-b", "common-1")
    with pytest.raises(bound_tiers.BindingError):
        bt.export("purple")
    got = bt.export("shell")
    assert [r.id for r in got] == ["s1"]
    # the same session never re-exports what it already exported
    bt.write("s2", "shell", "wool-c", "common-2")
    got2 = bt.export("shell", limit=100)
    assert [r.id for r in got2] == ["s2"]
    assert bt.export("shell") == []


# ------------------------------------------------------- fermentation_scheduler


def _extractor(item):
    return [f"note:{item.text[:8]}"] if item.text.strip() else []


def test_fermentation_digest_runs_all_four_stages():
    fs = fermentation_scheduler.FermentationScheduler(extractor=_extractor)
    a = fs.seed("the vat lives", confidence=0.95)
    fs.seed("the vat lives", confidence=0.4)  # duplicate -> dedup
    fs.seed("   ")  # husk -> compost
    log = fs.digest(now=1_000_000.0)
    assert log.deduped == 1
    assert log.reextracted >= 1
    assert log.promoted >= 1
    assert log.composted == 1
    assert len(fs.items) == 1
    survivor = fs.items[a.id]
    assert survivor.confidence >= 0.95
    assert survivor.extractions  # re-extraction happened
    assert survivor.digests_survived == 1
    assert fs.health == 100.0


def test_fermentation_neglect_decays_and_kills():
    fs = fermentation_scheduler.FermentationScheduler()
    fs.seed("body", confidence=0.5)
    fs.digest(now=0.0)
    assert fs.is_alive()
    # ten weeks of neglect: 10 * 20 decay kills the vat
    with pytest.raises(ValueError):
        fs.digest(now=10 * 7 * 24 * 3600.0)
    assert not fs.is_alive()


def test_fermentation_weekly_feeding_keeps_vat_alive():
    fs = fermentation_scheduler.FermentationScheduler()
    fs.seed("body", confidence=0.5)
    week = 7 * 24 * 3600.0
    for i in range(4):
        log = fs.digest(now=i * week)
        assert isinstance(log, fermentation_scheduler.DigestLog)
    assert fs.is_alive()
    assert len(fs.logs) == 4
    assert fs.living()[0].digests_survived == 4
