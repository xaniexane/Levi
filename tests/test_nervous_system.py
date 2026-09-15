"""Real, executable tests for the persona nervous system (workstream 1).

Covers: scoring determinism under fixed seed, hysteresis (borderline
scores don't flap), wall-clock decay math, explainability factor
invariants, backward-compatible loading of old persisted JSON, and
blend-weight structure. Hermetic: every NervousSystem gets an explicit
tmp path — no HOME writes.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from levi.persona.nervous_system import (
    AFFINITY_SEED,
    AFFECT_DIMS,
    DIMENSIONS,
    NervousSystem,
)


@pytest.fixture(autouse=True)
def _no_external_biases(monkeypatch):
    """Hermetic scoring: the control daemon and monotropism tracker read
    real HOME state, which would make these tests environment-dependent.
    Neutralize them — these tests target the nervous system itself."""
    monkeypatch.setattr(NervousSystem, "_external_biases", lambda self: (None, None))


def make_ns(tmp_path, seed=7, noise=0.0, persona_ids=("normal", "strategist")):
    return NervousSystem(
        path=tmp_path / "nervous.json",
        persona_ids=list(persona_ids),
        noise=noise,
        seed=seed,
    )


def flat_affinities(ns):
    """Zero all weights and uses so scores are exactly baselines (deterministic)."""
    for aff in ns.affinities.values():
        for k in list(vars(aff)):
            if k.startswith("w_"):
                setattr(aff, k, 0.0)
        aff.uses = 50  # momentum + overuse both capped → identical for all personas


# ── determinism ───────────────────────────────────────────────────


def test_scoring_deterministic_under_fixed_seed(tmp_path, monkeypatch):
    import levi.persona.nervous_system as ns_mod

    class _FrozenClock:
        @staticmethod
        def now(tz=None):
            return datetime(2026, 9, 15, 7, 0, 0, tzinfo=timezone.utc)

        @staticmethod
        def fromisoformat(s):
            return datetime.fromisoformat(s)

    monkeypatch.setattr(ns_mod, "datetime", _FrozenClock)
    ns1 = NervousSystem(path=tmp_path / "a.json", seed=123, noise=0.08)
    ns2 = NervousSystem(path=tmp_path / "b.json", seed=123, noise=0.08)
    ns1.sense("urgent deadline build it now")
    ns2.sense("urgent deadline build it now")
    assert ns1.score_matrix() == ns2.score_matrix()


def test_scoring_varies_with_seed_or_noise(tmp_path):
    ns1 = NervousSystem(path=tmp_path / "a.json", seed=1, noise=0.08)
    ns2 = NervousSystem(path=tmp_path / "b.json", seed=999, noise=0.08)
    assert ns1.score_matrix() != ns2.score_matrix()


# ── hysteresis ────────────────────────────────────────────────────


def test_hysteresis_unit_margin_and_dwell(tmp_path):
    ns = NervousSystem(
        path=tmp_path / "unit.json",
        seed=1,
        noise=0.0,
        persona_ids=["normal", "strategist"],
    )
    scores = {"normal": 0.50, "strategist": 0.53}  # gap 0.03 < margin 0.06
    ns._last_selected = "normal"
    ns._incumbent_turns = 5
    pick, switched = ns._hysteresis_pick(scores)
    assert pick == "normal" and not switched

    scores = {"normal": 0.50, "strategist": 0.60}  # gap 0.10 > margin
    pick, switched = ns._hysteresis_pick(scores)
    assert pick == "strategist" and switched

    # inside the dwell window: margin alone is not enough
    ns._last_selected = "normal"
    ns._incumbent_turns = 0
    pick, switched = ns._hysteresis_pick({"normal": 0.50, "strategist": 0.57})
    assert pick == "normal" and not switched

    # dwell override gap forces the switch even inside the window
    pick, switched = ns._hysteresis_pick({"normal": 0.50, "strategist": 0.90})
    assert pick == "strategist" and switched


def test_hysteresis_no_flap_across_repeated_selects(tmp_path):
    ns = make_ns(tmp_path)
    flat_affinities(ns)
    # strategist wins the first race and becomes incumbent
    ns.affinities["strategist"].baseline = 0.60
    ns.affinities["normal"].baseline = 0.50
    first = ns.select("hello")
    assert first == "strategist"

    # normal now leads by 0.03 — below the 0.06 margin: no flap, repeatedly
    ns.affinities["normal"].baseline = 0.63
    picks = {ns.select("hello again") for _ in range(6)}
    assert picks == {"strategist"}, f"flapped: {picks}"

    # a decisive lead (> margin, dwell satisfied) displaces the incumbent
    ns.affinities["normal"].baseline = 0.75
    assert ns.select("hello once more") == "normal"


def test_hysteresis_respects_crisis_veto(tmp_path):
    ns = make_ns(tmp_path, persona_ids=["normal", "manic_pixie"])
    flat_affinities(ns)
    ns.affinities["manic_pixie"].baseline = 0.80  # incumbent, playful
    assert ns.select("hey") == "manic_pixie"
    # crisis text must displace it despite hysteresis
    chosen = ns.select("I just got terrible news, someone died, I need help")
    assert chosen != "manic_pixie"


# ── wall-clock decay ──────────────────────────────────────────────


def test_wallclock_decay_moves_affect_toward_baseline(tmp_path):
    ns = make_ns(tmp_path)
    ns.affect.stress = 0.95
    ns.affect.arousal = 0.95
    ns.affect.valence = 0.05
    ns.affect.updated_at = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    ns.sense("")  # triggers decay; homeostasis then multiplies slightly
    assert ns.affect.stress < 0.5
    assert ns.affect.arousal < 0.5
    assert ns.affect.valence > 0.3  # drifted back toward the 0.55 setpoint
    # bond persists much longer than arousal
    ns2 = NervousSystem(
        path=tmp_path / "nervous2.json", seed=8, persona_ids=("normal", "strategist")
    )
    ns2.affect.bond = 0.9
    ns2.affect.updated_at = (
        datetime.now(timezone.utc) - timedelta(hours=6)
    ).isoformat()
    ns2.sense("")
    assert ns2.affect.bond > 0.6


def test_no_decay_when_no_time_passed(tmp_path):
    ns = make_ns(tmp_path)
    ns.affect.stress = 0.80
    ns.sense("ok")
    # only per-turn homeostasis applies (0.92 multiplier), not wall-clock collapse
    assert 0.70 < ns.affect.stress <= 0.80


# ── explainability ────────────────────────────────────────────────


def test_explain_factors_sum_to_score(tmp_path):
    ns = NervousSystem(path=tmp_path / "e.json", seed=42, noise=0.08)
    ns.sense("urgent deadline, please build this now")
    expl = ns.explain_scores(top_n=5)
    assert len(expl) == 5
    for _pid, entry in expl.items():
        assert set(entry.keys()) == {"score", "factors"}
        assert abs(sum(entry["factors"].values()) - entry["score"]) < 1e-9
    # the example shape from the spec renders
    pid = next(iter(expl))
    line = ns.format_explanation(pid, expl[pid])
    assert pid in line and "=" in line


def test_explain_includes_new_dimensions(tmp_path):
    ns = NervousSystem(path=tmp_path / "e2.json", seed=3, noise=0.0)
    ns.sense("I'm exhausted and this is impossible")
    expl = ns.explain_scores(top_n=17)
    labels = set()
    for entry in expl.values():
        labels.update(entry["factors"].keys())
    assert any(label.startswith("fatigue×") for label in labels)
    assert any(label.startswith("dominance×") for label in labels)
    assert any(label.startswith("valence×") for label in labels)


# ── backward compatibility ────────────────────────────────────────

OLD_FORMAT = {
    "affect": {
        "stress": 0.9,
        "anxiety": 0.8,
        "workload": 0.7,
        "energy": 0.2,
        "bond": 0.4,
        "arousal": 0.6,
        "turns": 12,
        "updated_at": "2026-01-01T00:00:00+00:00",
    },
    "affinities": {"normal": {"uses": 5, "last_used_at": None}},
    "locked_persona": None,
    "last_selected": "normal",
}


def test_load_old_format_json_migrates_sensibly(tmp_path):
    p = tmp_path / "old.json"
    p.write_text(json.dumps(OLD_FORMAT), encoding="utf-8")
    ns = NervousSystem(path=p, seed=1)
    a = ns.affect
    # old six dimensions preserved
    assert a.stress == 0.9 and a.energy == 0.2 and a.turns == 12
    # new dimensions migrated, not crashed/zeroed blindly
    assert a.valence == 0.55
    assert a.dominance == 0.50
    assert a.fatigue == pytest.approx(1.0 - 0.2)  # slow envelope of low energy
    assert a.bond_strain == pytest.approx(max(0.0, 0.35 - 0.4))
    # and the system still scores/selects fine afterwards
    assert ns.select("hello") in ns.affinities


def test_roundtrip_new_format(tmp_path):
    p = tmp_path / "new.json"
    ns = NervousSystem(path=p, seed=1)
    ns.sense("thanks, this is great")
    ns.select("thanks")
    ns2 = NervousSystem(path=p, seed=1)
    for dim in AFFECT_DIMS:
        assert getattr(ns2.affect, dim) == pytest.approx(getattr(ns.affect, dim))
    assert ns2._last_selected == ns._last_selected
    assert ns2._incumbent_turns == ns._incumbent_turns


# ── blending ─────────────────────────────────────────────────────


def test_blend_weights_structure(tmp_path):
    ns = NervousSystem(path=tmp_path / "b.json", seed=5, noise=0.0)
    blend = ns.blend_weights(top_n=3)
    assert len(blend) == 3
    assert abs(sum(r["weight"] for r in blend) - 1.0) < 1e-9
    scores = ns.score_matrix()
    top = max(scores, key=scores.get)
    assert blend[0]["persona"] == top  # blend leader == score leader
    st = ns.status()
    assert "blend" in st and "hysteresis" in st
    assert st["blend"][0]["persona"] == top


def test_lock_still_wins_over_everything(tmp_path):
    ns = make_ns(tmp_path, persona_ids=["normal", "strategist", "manic_pixie"])
    flat_affinities(ns)
    ns.affinities["manic_pixie"].baseline = 0.99
    ns.lock("normal")
    assert ns.select("whatever") == "normal"
    ns.unlock()
    assert ns.select("whatever") == "manic_pixie"


def test_dimension_definitions_present():
    assert len(AFFECT_DIMS) == 10
    assert len(DIMENSIONS) == 10
    assert all(isinstance(d, str) and d for _, d in DIMENSIONS)


def test_affinity_seed_count_honest():
    assert len(AFFINITY_SEED) == 17
