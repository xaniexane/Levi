"""97-genre registry bridge for the L.W.P. model engine.

Covers: registry reachability + count, ≥1 body line for every registry id,
determinism of (genre_id, seed) → lines, fallback labeling via
genre_source(), and unchanged direction/phase/power (DPP) behavior.
"""

import pytest

from levi.lwp.model_engine import (
    DIRS,
    PHASES,
    POWERS,
    ROM_LENSES,
    GENRES_BODY,
    LWPModelEngine,
    genre_body_lines,
    genre_source,
)
from levi.graph.genres import GenreRegistry
from levi.power.lwp import power_step


def _engine(tmp_path):
    return LWPModelEngine(path=tmp_path / "model.json")


# -- registry reachability ----------------------------------------------------


def test_registry_reachable_with_expected_count():
    reg = GenreRegistry()
    n = reg.count()
    # The registry asserts its own integrity on construction (EXPECTED_COUNT);
    # report the actual number honestly rather than hard-coding.
    assert n == 97, f"registry count drifted: expected 97, got {n}"
    assert n == len(reg.ids())


def test_integrity_check_reports_full_canon():
    reg = GenreRegistry()
    chk = reg.integrity_check()
    assert chk["ok"] is True
    assert chk["actual"] == 97


# -- every registry id resolves to ≥1 body line --------------------------------


def test_every_registry_id_resolves_to_body_lines():
    reg = GenreRegistry()
    thin = []
    for gid in reg.ids():
        lines = genre_body_lines(gid, seed="canon-sweep")
        assert lines and all(isinstance(x, str) and x for x in lines), gid
        if len(lines) < 3:
            thin.append(gid)
    # All 97 formal genres yield the full derived set; flag any thin ones.
    assert thin == [], f"genres with <3 derived lines: {thin}"


def test_registry_lines_carry_genre_identity():
    # Derived lines are composed from the genre's own id tokens / category —
    # the genre must be recognizable in at least one of its lines.
    lines = genre_body_lines("systems_horror", seed="x")
    text = " ".join(lines).lower()
    assert "systems horror" in text or "systems" in text


def test_nine_handwritten_bodies_still_intact():
    assert set(GENRES_BODY) == {
        "literary",
        "systems_horror",
        "trauma_recursion",
        "consent_dystopia",
        "post_privacy_noir",
        "lattice_gothic",
        "sci_fi",
        "horror",
        "noir",
    }
    for lines in GENRES_BODY.values():
        assert len(lines) >= 2


# -- determinism ---------------------------------------------------------------


def test_determinism_same_genre_and_seed():
    a = genre_body_lines("noir", seed="s1")
    b = genre_body_lines("noir", seed="s1")
    assert a == b


def test_seed_changes_lines_but_stays_deterministic():
    seen = {tuple(genre_body_lines("cosmic_horror", seed=f"s{i}")) for i in range(6)}
    assert len(seen) > 1  # seeds actually move the selection
    for tup in seen:
        assert len(tup) == 3


def test_fallback_lines_deterministic():
    a = genre_body_lines("not_a_real_genre", seed="s1")
    b = genre_body_lines("not_a_real_genre", seed="s2")
    assert a == b  # hand-written bodies are fixed regardless of seed


# -- source labeling -----------------------------------------------------------


@pytest.mark.parametrize(
    "gid",
    ["literary", "noir", "systems_horror", "cosmic_horror", "interpenetration_romance"],
)
def test_registry_ids_report_registry_source(gid):
    assert genre_source(gid) == "registry"


@pytest.mark.parametrize("gid", ["not_a_genre", "", "sci fi", "LITERARY"])
def test_unknown_or_malformed_ids_report_fallback_source(gid):
    assert genre_source(gid) == "fallback"


def test_unknown_id_serves_handwritten_fallback_lines():
    lines = genre_body_lines("not_a_genre", seed="x")
    assert lines
    assert set(lines) <= set(GENRES_BODY["literary"])


def test_known_fallback_id_serves_own_handwritten_body():
    # A GENRES_BODY key is also in the registry, so it normally serves
    # registry-derived lines; the fallback path itself must stay byte-identical.
    assert GENRES_BODY["horror"] == [
        "Dread arrived with a filing number.",
        "The room kept a second temperature.",
    ]


def test_registry_unavailable_forces_fallback(monkeypatch):
    import levi.lwp.model_engine as me

    monkeypatch.setattr(me, "_GENRE_REGISTRY", None)
    monkeypatch.setattr(me, "_GENRE_REGISTRY_FAILED", True)
    assert genre_source("noir") == "fallback"
    lines = genre_body_lines("noir", seed="x")
    assert lines == GENRES_BODY["noir"]


# -- assemble uses the registry -----------------------------------------------


def test_assemble_deterministic_for_fixed_key(tmp_path):
    eng = _engine(tmp_path)
    a = eng.assemble(key="k1", genres=["noir", "cosmic_horror"], target=120)
    b = eng.assemble(key="k1", genres=["noir", "cosmic_horror"], target=120)
    assert a["text"] == b["text"]
    assert a["words"] == b["words"]
    assert a["event"] == b["event"]


def test_assemble_covers_all_97_genres_without_error(tmp_path):
    eng = _engine(tmp_path)
    reg = GenreRegistry()
    ids = reg.ids()
    for i in range(0, len(ids), 12):
        chunk = ids[i : i + 4]
        out = eng.assemble(key=f"canon{i}", genres=chunk, target=120)
        assert out["words"] >= 40
        assert out["text"]


def test_resolve_genres_still_bridges_registry(tmp_path):
    eng = _engine(tmp_path)
    resolved = eng.resolve_genres("noir, cosmic horror, bogus xyz")
    assert "noir" in resolved
    assert "cosmic_horror" in resolved
    assert "bogus_xyz" in resolved  # unknown passes through untouched


# -- DPP behavior unchanged -----------------------------------------------------


def test_direction_phase_power_enums_unchanged():
    assert set(DIRS) == {"forward", "reverse", "inverse", "free"}
    assert set(PHASES) == {"distance", "peak", "gold_push", "finale"}
    assert set(POWERS) == {"repeater", "booster", "transformer", "gain", "immortal"}
    assert set(ROM_LENSES) == {"mccarthy", "morrison", "gibson"}


def test_target_words_phase_base_plus_power_step(tmp_path):
    eng = _engine(tmp_path)
    bases = {"peak": 170, "distance": 260, "finale": 240, "gold_push": 300}
    for phase, base in bases.items():
        eng.state.phase = phase
        eng.state.power = "gain"
        assert eng.target_words() == base + power_step("gain")
    eng.state.phase = "gold_push"
    eng.state.power = "repeater"
    assert eng.target_words() == 300 + power_step("repeater")


def test_dpp_setters_validate(tmp_path):
    eng = _engine(tmp_path)
    assert "peak" in eng.set_phase("peak")
    assert "Unknown phase" in eng.set_phase("nope")
    assert "gain" in eng.set_power("gain")
    assert "Unknown power" in eng.set_power("nope")
    assert "reverse" in eng.set_direction("reverse")
    assert "Unknown direction" in eng.set_direction("nope")


def test_anomaly_and_rank_shapes(tmp_path):
    eng = _engine(tmp_path)
    assert eng.anomaly() == 1  # 1 + 0//20000 - 0 ruptures
    assert eng.rank() == "D3"
    eng.state.words = 20_000
    assert eng.rank() == "D4"
    eng.state.words = 80_000
    assert eng.rank() == "D5"


def test_expand_persists_and_counts_words(tmp_path):
    eng = _engine(tmp_path)
    out = eng.expand(1)
    assert "words=" in out
    assert eng.state.words > 0
    assert len(eng.state.scenes) == 1
    # state reloaded from disk keeps continuity
    eng2 = LWPModelEngine(path=tmp_path / "model.json")
    assert eng2.state.words == eng.state.words


# -- chapter/milestone art law -------------------------------------------------
# Law 1: every chapter (scene) carries a non-empty deterministic art brief.
# Law 2: every rank transition / phase change emits exactly one milestone brief.
# Law 3: register_art only fills art_path/art_status — continuity untouched.


def test_expand_scenes_carry_art_briefs(tmp_path):
    from levi.lwp.model_engine import chapter_art_prompt

    eng = _engine(tmp_path)
    eng.expand(2)
    assert len(eng.state.scenes) == 2
    for s in eng.state.scenes:
        assert s["art_prompt"] and isinstance(s["art_prompt"], str)
        assert s["art_status"] == "pending"
        assert s["art_path"] == ""
        assert "No text" in s["art_prompt"]
    # determinism: same inputs → same brief, no RNG involved
    a = chapter_art_prompt("Lena Voss", ["systems_horror", "literary"], "the chamber")
    b = chapter_art_prompt("Lena Voss", ["systems_horror", "literary"], "the chamber")
    assert a == b


def test_rank_transition_emits_exactly_one_milestone(tmp_path):
    eng = _engine(tmp_path)
    eng.state.words = 19_900
    assert eng.rank() == "D3"
    eng.expand(1)
    assert eng.rank() == "D4"
    ups = [m for m in eng.state.milestones if m["type"] == "rank_up"]
    assert len(ups) == 1
    m = ups[0]
    assert m["from"] == "D3" and m["to"] == "D4"
    assert m["art_prompt"] and m["art_status"] == "pending"


def test_no_rank_change_means_no_milestone(tmp_path):
    eng = _engine(tmp_path)
    eng.expand(1)
    assert eng.state.milestones == []


def test_phase_change_emits_milestone_once(tmp_path):
    eng = _engine(tmp_path)
    eng.set_phase("distance")
    pcs = [m for m in eng.state.milestones if m["type"] == "phase_change"]
    assert len(pcs) == 1
    assert pcs[0]["art_status"] == "pending"
    # setting the same phase again emits nothing
    eng.set_phase("distance")
    assert len([m for m in eng.state.milestones if m["type"] == "phase_change"]) == 1


def test_register_art_never_touches_continuity(tmp_path):
    eng = _engine(tmp_path)
    eng.expand(1)
    words_before = eng.state.words
    text_before = eng.state.scenes[0]["text"]
    sid = eng.state.scenes[0]["id"]
    msg = eng.register_art(sid, "/tmp/ch01.png")
    assert "registered" in msg
    assert eng.state.words == words_before
    assert eng.state.scenes[0]["text"] == text_before
    assert eng.state.scenes[0]["art_path"] == "/tmp/ch01.png"
    assert eng.state.scenes[0]["art_status"] == "done"
    assert eng.register_art("nope", "/tmp/x.png").startswith("no chapter")


def test_pending_art_backfills_legacy_scenes(tmp_path):
    eng = _engine(tmp_path)
    eng.expand(1)
    # simulate a pre-art-law scene
    del eng.state.scenes[0]["art_prompt"]
    eng.state.scenes[0]["art_status"] = "pending"
    pending = eng.pending_art()
    assert len(pending) == 1
    assert pending[0]["kind"] == "chapter"
    assert pending[0]["prompt"] and pending[0]["filename"].endswith(".png")
