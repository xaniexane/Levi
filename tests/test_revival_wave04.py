"""Tests for revival wave 04 — crafts (b): guilds, apprenticeship, trust chains, metrology.

capability_tokens, work_songs, master_standard, natural_standard,
centuriation, gunter_chain, ell_variants, toise_migration: each an
original, from-scratch LEVI mechanism. At least three meaningful tests
per module: construct, exercise the core mechanism, cover an edge.
"""

import pytest

from core.levi.revival import capability_tokens
from core.levi.revival import work_songs
from core.levi.revival import master_standard
from core.levi.revival import natural_standard
from core.levi.revival import centuriation
from core.levi.revival import gunter_chain
from core.levi.revival import ell_variants
from core.levi.revival import toise_migration


# ---------------------------------------------------------------------------
# capability_tokens — the Word (membership) vs the marks (competence)
# ---------------------------------------------------------------------------


def _lodge():
    return capability_tokens.Workmaster("stonecutters", word_validity_days=30.0)


def test_capability_tokens_issue_and_verify_word():
    lodge = _lodge()
    token = lodge.enroll("ada", now=1_000_000)
    assert lodge.verify_word(token, now=1_000_001) == "ada"


def test_capability_tokens_word_is_not_competence_proof():
    lodge = _lodge()
    token = lodge.enroll("ada", now=1_000_000)
    lodge.verify_word(token, now=1_000_001)
    # A verified Word says nothing about skill: no audited marks, empty report.
    assert lodge.competence_report("ada") == (0, 0, 0)
    mark = lodge.strike_mark("lintel-7", "ada", "master", now=1_000_002)
    assert mark.inspector_verdict is None
    mark.audit("upheld")
    assert lodge.competence_report("ada") == (1, 0, 0)


def test_capability_tokens_revoke_and_forgery():
    lodge = _lodge()
    token = lodge.enroll("ada", now=1_000_000)
    assert lodge.revoke("ada") == 1
    with pytest.raises(capability_tokens.RevokedTokenError):
        lodge.verify_word(token, now=1_000_001)
    forged = capability_tokens.CapabilityToken(
        member="ada",
        guild="stonecutters",
        serial=999,
        issued_at=1_000_000,
        expires_at=2_000_000,
        seal="bogus",
    )
    with pytest.raises(capability_tokens.ForgedTokenError):
        lodge.verify_word(forged, now=1_000_001)


def test_capability_tokens_expiry_and_unknown_member():
    lodge = _lodge()
    token = lodge.enroll("ada", now=1_000_000)
    with pytest.raises(capability_tokens.ExpiredTokenError):
        lodge.verify_word(token, now=1_000_000 + 31 * 86400)
    with pytest.raises(capability_tokens.UnknownMemberError):
        lodge.revoke("nobody")


# ---------------------------------------------------------------------------
# work_songs — rhythm as coordination protocol
# ---------------------------------------------------------------------------


def _song():
    grid = work_songs.BeatGrid(bpm=60.0, beats_per_bar=4, bars=4)
    song = work_songs.WorkSong("capstan shanty", grid)
    song.add_verse(
        work_songs.Verse(call="heave away", answer_offsets=[2], task="turn capstan")
    )
    song.add_verse(
        work_songs.Verse(call="heave again", answer_offsets=[2], task="turn capstan")
    )
    return song


def test_work_songs_plan_lays_calls_and_answers_on_grid():
    song = _song()
    events = song.plan()
    calls = [e for e in events if e[1] == "call"]
    answers = [e for e in events if e[1] == "answer"]
    assert [e[0] for e in calls] == [0, 4]
    assert [e[0] for e in answers] == [2, 6]
    assert events == sorted(events, key=lambda e: (e[0], 0 if e[1] == "call" else 1))


def test_work_songs_gang_tracks_drift_and_flags_off_beat():
    gang = work_songs.Gang("dock crew", _song())
    gang.muster("ada")
    gang.muster("bo")
    for beat in (2, 6, 10):
        gang.report_answer("ada", beat, 0.05)
        gang.report_answer("bo", beat, 0.9)  # chronically late
    assert gang.mean_drift("ada") == pytest.approx(0.05)
    assert gang.off_beat() == ["bo"]
    assert gang.off_beat(tolerance=2.0) == []


def test_work_songs_grievance_log_and_roll_call():
    gang = work_songs.Gang("dock crew", _song())
    gang.muster("ada")
    gang.sing_grievance("the foreman shorted our rum ration tuesday")
    assert gang.grievances == ["the foreman shorted our rum ration tuesday"]
    roll = dict((m, (d, c)) for m, d, c in gang.roll_call())
    assert roll["ada"] == (None, 0)  # no readings yet: drift honestly unknown
    with pytest.raises(ValueError):
        gang.report_answer("stranger", 2, 0.0)


# ---------------------------------------------------------------------------
# master_standard — one canonical measure, checked rods, drift watch
# ---------------------------------------------------------------------------


def _standard():
    ms = master_standard.MasterStandard("royal cubit", "cubit")
    ms.define(1.0, "length of the granite bar in the vault")
    return ms


def test_master_standard_versioned_definitions_never_edit_history():
    ms = _standard()
    v2 = ms.define(1.001, "re-cut bar after the flood")
    assert ms.current().version == 2
    assert ms.history()[0].value == 1.0
    assert v2.supersedes == 1


def test_master_standard_rod_audit_flags_drift():
    ms = _standard()
    ms.check_rod("rod-3")
    assert ms.audit_rod("rod-3", 1.0004, tolerance=0.001) is None
    alert = ms.audit_rod("rod-3", 1.005, tolerance=0.001)
    assert isinstance(alert, master_standard.DriftAlert)
    assert len(ms.alerts) == 1
    with pytest.raises(master_standard.StandardError):
        ms.audit_rod("rod-99", 1.0, tolerance=0.001)


def test_master_standard_derived_units_and_seked():
    ms = _standard()
    palm = ms.derive("palm", 1 / 7, lineage="1/7 of the master")
    assert palm == pytest.approx(1 / 7)
    # seked: run-per-rise; a 1:2 slope (rise 1, run 2) has seked 2.
    assert master_standard.seked_ratio(1.0, 2.0) == pytest.approx(2.0)
    with pytest.raises(master_standard.StandardError):
        master_standard.seked_ratio(0.0, 1.0)
    with pytest.raises(master_standard.StandardError):
        master_standard.MasterStandard("empty", "cubit").current()


# ---------------------------------------------------------------------------
# natural_standard — self-replicating measure anyone can audit
# ---------------------------------------------------------------------------


def _inch():
    return natural_standard.NaturalStandard(
        name="inch", reference_object="barleycorn", copies=3, base_unit="inch"
    )


def test_natural_standard_calibrates_from_field_sample():
    std = _inch()
    cal = std.calibrate([0.33, 0.34, 0.32, 0.33, 0.34])
    assert cal.adopted
    assert std.unit_value == pytest.approx(3 * cal.mean)
    assert cal.sample_size == 5
    assert cal.stderr < cal.stdev


def test_natural_standard_refuses_wild_samples():
    std = _inch()
    cal = std.calibrate([0.1, 0.9, 0.2, 0.8])  # spread far beyond the quorum
    assert not cal.adopted
    with pytest.raises(natural_standard.NaturalStandardError):
        _ = std.unit_value  # nothing adopted: honestly unusable
    with pytest.raises(natural_standard.NaturalStandardError):
        std.calibrate([0.33])  # a single sample is not a sample


def test_natural_standard_audit_and_grading():
    std = _inch()
    std.calibrate([0.33, 0.34, 0.32, 0.33])
    ok, deviation = std.audit([0.33, 0.34, 0.32], tolerance=0.05)
    assert ok and deviation >= 0.0
    ok, _ = std.audit([0.5, 0.5, 0.5, 0.5], tolerance=0.01)
    assert not ok
    grades = std.grade(3)
    assert [g[0] for g in grades] == [1, 2, 3]
    assert grades[2][1] == pytest.approx(3 * std.unit_value)


# ---------------------------------------------------------------------------
# centuriation — titled grid, quarantined conflicts
# ---------------------------------------------------------------------------


def _registry():
    reg = centuriation.LandRegistry()
    reg.register(
        centuriation.Parcel(
            name="century-1",
            bounds=centuriation.Rect(0, 0, 10, 10),
            holder="ada",
            surveyed="2026-01-01",
            surveyor="gaius",
        )
    )
    return reg


def test_centuriation_clean_register_and_lookup():
    reg = _registry()
    assert reg.lookup(5, 5) == ("titled", "ada")
    assert reg.lookup(50, 50) == ("open", None)


def test_centuriation_overlap_quarantines_instead_of_overwriting():
    reg = _registry()
    qs = reg.register(
        centuriation.Parcel(
            name="century-2",
            bounds=centuriation.Rect(5, 5, 15, 15),
            holder="bo",
            surveyed="2026-02-01",
            surveyor="marcus",
        )
    )
    assert len(qs) == 1
    q = qs[0]
    assert q.bounds == centuriation.Rect(5, 5, 10, 10)
    assert not q.resolved
    assert reg.lookup(7, 7) == ("disputed", None)  # the strip, quarantined
    assert reg.lookup(12, 12) == ("titled", "bo")  # bo's clean part still his
    assert reg.lookup(2, 2) == ("titled", "ada")  # ada's clean part still hers


def test_centuriation_adjudication_records_its_rule():
    reg = _registry()
    q = reg.register(
        centuriation.Parcel(
            name="century-2",
            bounds=centuriation.Rect(5, 5, 15, 15),
            holder="bo",
            surveyed="2026-02-01",
            surveyor="marcus",
        )
    )[0]
    winner = reg.adjudicate(q)  # default: earliest survey wins
    assert winner.holder == "ada"
    assert q.resolved and q.resolution_rule == "earliest survey wins"
    with pytest.raises(centuriation.LandError):
        reg.adjudicate(q)  # already adjudicated
    with pytest.raises(centuriation.LandError):
        reg.register(
            centuriation.Parcel(
                name="century-1",
                bounds=centuriation.Rect(0, 0, 1, 1),
                holder="cy",
                surveyed="2026-03-01",
                surveyor="titus",
            )
        )


# ---------------------------------------------------------------------------
# gunter_chain — decimal survey arithmetic
# ---------------------------------------------------------------------------


def test_gunter_chain_ladder_conversions():
    c = gunter_chain.Chain.from_chains(2.5)
    assert c.links == 250
    ladder = gunter_chain.ladder(c)
    assert ladder["chain"] == 5 / 2
    assert ladder["furlong"] == 1 / 4
    assert c.feet == 165  # 2.5 chains × 66 ft


def test_gunter_chain_acres_are_exact():
    # 1 chain × 1 chain = 1 square chain = exactly 1/10 acre.
    a = gunter_chain.acres(gunter_chain.Chain(100), gunter_chain.Chain(100))
    assert a == gunter_chain.Fraction(1, 10)
    # 10 chains × 1 furlong = 100 square chains = exactly 10 acres.
    b = gunter_chain.acres(gunter_chain.Chain(1000), gunter_chain.Chain(1000))
    assert b == 10
    assert isinstance(b, gunter_chain.Fraction)


def test_gunter_chain_parse_and_arithmetic():
    c = gunter_chain.parse_links("3 chains 25 links")
    assert c.links == 325
    assert (c + gunter_chain.Chain(75)).links == 400
    with pytest.raises(gunter_chain.ChainError):
        gunter_chain.parse_links("3 chains 25")  # odd word count
    with pytest.raises(gunter_chain.ChainError):
        gunter_chain.parse_links("2 leagues")  # unknown rung
    with pytest.raises(gunter_chain.ChainError):
        gunter_chain.Chain.from_chains(0.333)  # not whole links


# ---------------------------------------------------------------------------
# ell_variants — provenance over uniformity
# ---------------------------------------------------------------------------


def _ells():
    reg = ell_variants.EllRegistry()
    for name, value, place in (
        ("london", 45.0, "London"),
        ("bristol", 44.0, "Bristol"),
        ("scotch", 37.2, "Edinburgh"),
    ):
        reg.register(
            ell_variants.EllVariant(
                name=name,
                base_value=value,
                provenance=ell_variants.Provenance(
                    place=place,
                    trade="cloth",
                    date_span="c. 1500–1700",
                    source_note="merchant records",
                ),
            )
        )
    return reg


def test_ell_variants_named_conversion_only():
    reg = _ells()
    assert reg.convert(2.0, "london") == 90.0
    assert reg.convert_between(2.0, "london", "bristol") == pytest.approx(90.0 / 44.0)
    with pytest.raises(ell_variants.EllError):
        reg.variant("paris")  # no silent default ell


def test_ell_variants_divergence_report_shows_the_spread():
    reg = _ells()
    lo, hi, ratio = reg.divergence_report()
    assert lo == pytest.approx(37.2)
    assert hi == pytest.approx(45.0)
    assert ratio == pytest.approx(45.0 / 37.2)
    with pytest.raises(ell_variants.EllError):
        ell_variants.EllRegistry().divergence_report()


def test_ell_variants_alnage_stamp_certifies_claim_not_unit():
    reg = _ells()
    stamp = reg.inspect("bolt-12", "bristol", 10.0, "2026-04-01", "inspector wyatt")
    assert stamp.as_base_units(reg) == pytest.approx(440.0)
    assert stamp.variant == "bristol"  # the stamp names the variant — never "the ell"
    # contradictory entries for one name are kept, not merged.
    reg.register(
        ell_variants.EllVariant(
            name="london",
            base_value=46.0,
            provenance=ell_variants.Provenance(
                place="London",
                trade="cloth",
                date_span="c. 1700–1800",
                source_note="later survey",
            ),
        )
    )
    assert "london#2" in reg.names()
    with pytest.raises(ell_variants.EllError):
        reg.inspect("bolt-13", "paris", 10.0, "2026-04-01", "wyatt")


# ---------------------------------------------------------------------------
# toise_migration — old records stay readable after the unit dies
# ---------------------------------------------------------------------------


def _table():
    table = toise_migration.MigrationTable()
    table.enact(
        toise_migration.LegalDefinition(
            new_unit="metre",
            old_standard="Toise du Pérou",
            old_subunit="ligne",
            factor=443.296,
            authority="law of 10 December 1799",
            date="1799-12-10",
        )
    )
    return table


def test_toise_migration_translates_old_records():
    table = _table()
    rec = toise_migration.MeasureRecord(
        value=443.296,
        old_standard="Toise du Pérou",
        old_subunit="ligne",
        date="1805-01-01",
        note="survey of the meridian",
    )
    t = table.translate(rec)
    assert t.value_new == pytest.approx(1.0)
    assert t.new_unit == "metre"
    assert t.definition.authority == "law of 10 December 1799"
    assert t.original is rec


def test_toise_migration_refuses_pre_law_records():
    table = _table()
    old = toise_migration.MeasureRecord(
        value=100.0,
        old_standard="Toise du Pérou",
        old_subunit="ligne",
        date="1700-01-01",
    )
    with pytest.raises(toise_migration.MigrationError):
        table.translate(old)  # older than every law: refused, never guessed


def test_toise_migration_drift_notes_and_newest_law_wins():
    table = _table()
    table.note_drift("Toise du Pérou", "1800-01-01", "bar shows wear at the end faces")
    assert table.drift_notes("Toise du Pérou") == [
        ("1800-01-01", "bar shows wear at the end faces")
    ]
    # a later recalibration law supersedes for records after its date.
    table.enact(
        toise_migration.LegalDefinition(
            new_unit="metre",
            old_standard="Toise du Pérou",
            old_subunit="ligne",
            factor=443.300,
            authority="recalibration decree",
            date="1850-01-01",
        )
    )
    early = table.translate(
        toise_migration.MeasureRecord(443.296, "Toise du Pérou", "ligne", "1805-01-01")
    )
    late = table.translate(
        toise_migration.MeasureRecord(443.300, "Toise du Pérou", "ligne", "1860-01-01")
    )
    assert early.definition.factor == pytest.approx(443.296)
    assert late.definition.factor == pytest.approx(443.300)
    assert late.value_new == pytest.approx(1.0)
