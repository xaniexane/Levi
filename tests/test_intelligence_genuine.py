"""Tests for the ten genuine natural intelligence classes.

Every class must prove its mechanism: descriptors pass the schema, the
behavior module is importable and actually works (seeded, deterministic),
organ mapping covers all five organs, and Hatter carries at least three
real behaviors. Genuine means machinery, not names.
"""

import importlib

import pytest

from levi.agent.hemisphere import (
    HEMISPHERE_DOCTRINE,
    LEFT,
    RIGHT,
    make_hemisphere,
)
from levi.intelligence import (
    NATURAL_CLASSES,
    NATURAL_CODES,
    NATURAL_ORGANS,
    NATURAL_REQUIRED_FIELDS,
    describe,
    get_natural,
    intelligences_for,
    is_declared_class,
    is_natural_class,
    natural_for_organ,
    organ_of,
    all_mappings,
)
from levi.intelligence.behaviors import (
    clonal,
    conjugation,
    corvid,
    cuttlefish,
    hatter,
    mycelium,
    octopus,
    physarum,
    songline,
    stigmergy,
    waggle,
)


def test_ten_codes_declared():
    assert NATURAL_CODES == (
        "ANT",
        "CRV",
        "BEE",
        "WHL",
        "MYC",
        "SLM",
        "IMM",
        "BCT",
        "OCT",
        "CUT",
    )
    assert set(NATURAL_CLASSES) == set(NATURAL_CODES)


def test_every_class_carries_required_fields():
    for code in NATURAL_CODES:
        rec = NATURAL_CLASSES[code]
        for field in NATURAL_REQUIRED_FIELDS:
            assert field in rec, f"{code} missing {field}"
        assert rec["code"] == code
        assert rec["status"] == "genuine"
        assert rec["organ"] in NATURAL_ORGANS, f"{code} bad organ"
        assert len(rec["capabilities"]) >= 3, f"{code} thin capabilities"
        assert len(rec["limits"]) >= 3, f"{code} missing honest limits"
        for text_field in ("source", "mechanism", "name", "behavior"):
            assert isinstance(rec[text_field], str) and rec[text_field].strip()


def test_behavior_modules_importable():
    for code in NATURAL_CODES:
        module_path = NATURAL_CLASSES[code]["behavior"]
        mod = importlib.import_module(module_path)
        assert mod is not None, code


def test_get_natural_and_predicates():
    assert get_natural("ANT")["name"] == "Stigmergic Intelligence"
    assert get_natural("CUT")["name"] == "Cuttlefish Intelligence"
    for code in NATURAL_CODES:
        assert is_natural_class(code)
        assert is_declared_class(code)
    assert not is_natural_class("OE")
    assert not is_natural_class("XI")
    with pytest.raises(KeyError):
        get_natural("ZZ")


def test_describe_unified_registry():
    assert describe("OE")["name"] == "Omen Intelligence"  # scaffolded
    assert describe("ANT")["name"] == "Stigmergic Intelligence"  # genuine
    assert describe("OCT")["organ"] == "hatter"
    with pytest.raises(KeyError):
        describe("NOPE")


def test_organ_mapping_covers_all_five_organs():
    covered = {organ_of(code) for code in NATURAL_CODES}
    assert covered == set(NATURAL_ORGANS), covered
    for organ in NATURAL_ORGANS:
        pairs = intelligences_for(organ)
        assert len(pairs) >= 1, f"{organ} has no intelligences"
        for code, justification in pairs:
            assert code in NATURAL_CODES
            assert justification.strip()
            assert organ_of(code) == organ
    assert natural_for_organ("hatter") == ["OCT", "CUT"]
    assert set(all_mappings()) == set(NATURAL_ORGANS)
    with pytest.raises(KeyError):
        intelligences_for("nope")


def test_hatter_first_class_standing():
    assert "hatter" in NATURAL_ORGANS
    assert len(intelligences_for("hatter")) == 2
    # at least three real behaviors under hatter
    assert callable(hatter.diagonal_search)
    assert callable(hatter.NoiseInjector)
    assert hatter.ParadoxHolder is cuttlefish.ParadoxHolder


def test_doctrine_entries_for_all_ten():
    for code in NATURAL_CODES:
        assert code in HEMISPHERE_DOCTRINE, f"no doctrine for {code}"
        for hemi in (LEFT, RIGHT):
            d = HEMISPHERE_DOCTRINE[code][hemi]
            assert d["role"] and d["character"]
    left = make_hemisphere("left", "a1", "ANT", "t1")
    assert "ANT" in left.mind_descriptor
    right = make_hemisphere("right", "a1", "OCT", "t1")
    assert "OCT" in right.mind_descriptor


# ---------------------------------------------------------------------------
# Mechanism proofs — every behavior must actually work.


def test_stigmergy_gradient_guides_walkers_to_target():
    field = stigmergy.PheromoneField(10, 10, seed=7)
    # trail laid home: increasing deposits toward the target
    for x in range(10):
        field.deposit(x, 5, 0.5 + x * 0.5)
    x, y = 0, 5
    for _ in range(12):
        x, y = field.follow(x, y)
    assert (x, y) == (9, 5)  # walked the gradient to the target
    field.evaporate()
    assert field.sense(9, 5) < 5.0  # evaporation forgets


def test_waggle_round_trip():
    dance = waggle.encode(90.0, 600.0, 0.5)
    vec = waggle.decode(dance, sun_azimuth_deg=0.0)
    assert waggle.angular_error(vec["bearing_deg"], 90.0) < 1e-9
    assert vec["distance_m"] == pytest.approx(600.0)
    assert vec["quality"] == pytest.approx(0.5)


def test_physarum_prunes_the_long_tube():
    net = physarum.TubeNetwork(
        ["A", "B", "C", "D"],
        [("A", "B", 1.0), ("B", "C", 1.0), ("C", "D", 1.0), ("A", "D", 10.0)],
        prune_below=0.05,
    )
    for _ in range(40):
        net.pulse("A", "D")
    edges = net.surviving_edges()
    assert ("A", "D") not in edges  # the long way composted
    assert ("A", "B") in edges and ("C", "D") in edges


def test_mycelium_decomposes_and_reroutes():
    net = mycelium.Mycelium()
    net.grow("dead", "hub", 5.0)
    net.grow("hub", "sink", 5.0)
    net.grow("dead", "sink", 1.0)
    assert net.decompose("dead", 4.0) == 4.0
    net.sever("dead", "sink")  # damage: direct link cut
    assert net.route("dead", "sink") == pytest.approx(4.0)  # via hub
    net.decompose("dead", 3.0)
    net.sever("hub", "sink")  # total isolation
    assert net.route("dead", "sink") == 0.0
    net.grow("dead", "sink", 1.0)  # regrow a thin hypha
    assert net.route("dead", "sink") == pytest.approx(1.0)  # capped


def test_clonal_selection_improves_affinity():
    best, best_fit, history = clonal.clonal_select(
        fitness=lambda g: float(sum(g)),
        genome_length=12,
        population=20,
        generations=40,
        seed=3,
    )
    assert history[-1] > history[0]  # affinity maturation is real
    assert best_fit >= 10.0  # near-perfect binder from a random start
    assert sum(best) == int(best_fit)


def test_conjugation_spreads_the_winning_plasmid():
    rng_seed = 11
    pop = []
    for i in range(10):
        genome = [0] * 8
        plasmids = [[1] + [0] * 7] if i < 2 else []
        pop.append(conjugation.Carrier(genome, plasmids))
    before = conjugation.trait_frequency(pop, 0, 1)
    pop, history = conjugation.conjugate(
        fitness=lambda g: float(g[0]),
        population=pop,
        rounds=10,
        seed=rng_seed,
    )
    after = conjugation.trait_frequency(pop, 0, 1)
    assert after > before
    assert history[-1] >= history[0]


def test_octopus_arms_decide_locally_with_central_veto():
    arms = [
        octopus.Arm(0, lambda s: ("grab", s["prey"])),
        octopus.Arm(1, lambda s: ("grab", s["prey"])),
    ]
    beast = octopus.Octopus(
        arms, veto=lambda arm_id, prop: "hold" if arm_id == 1 else None
    )
    actions = beast.step([{"prey": "crab"}, {"prey": "crab"}])
    assert actions[0] == ("grab", "crab")  # local decision stands
    assert actions[1] == "hold"  # center vetoed
    assert arms[1].vetoed == 1


def test_cuttlefish_holds_paradox_then_resolves():
    holder = cuttlefish.ParadoxHolder("court", "threaten")
    assert holder.act() == ("court", "threaten")  # both flanks live
    holder.observe(supports_a=1.0, supports_b=0.0)
    holder.observe(supports_a=1.0, supports_b=0.0)
    assert holder.resolved == "A"
    assert holder.act() == "court"


def test_corvid_finds_two_step_tool_chain():
    start = corvid.ToolWorld(reachable=frozenset(), tools=frozenset({"short_stick"}))
    chain = corvid.plan_tool_chain(start, "food_grub")
    # two valid shortest chains exist (long_stick or hook_wire second)
    assert chain is not None and len(chain) == 2
    assert chain[0] == "short_stick" and chain[1] in ("long_stick", "hook_wire")
    assert corvid.plan_tool_chain(start, "moon") is None


def test_songline_survives_the_noisy_ocean():
    song = songline.encode("hi", repeats=3)
    noisy = songline.corrupt(song, flip_rate=0.3, seed=5)
    assert songline.decode(noisy) == "hi"
    assert songline.decode([]) == ""


def test_hatter_diagonal_search_leaps_not_crawls():
    space = list(range(100))
    best_i, best_f, history = hatter.diagonal_search(
        space, fitness=lambda v: float(v), jumps=20, seed=9
    )
    assert all(b >= a for a, b in zip(history, history[1:], strict=False))
    assert best_f > history[0]
    assert best_i != 0  # it left the start behind


def test_hatter_noise_is_replayable_chaos():
    n1 = hatter.NoiseInjector(seed=42, amplitude=2.0)
    n2 = hatter.NoiseInjector(seed=42, amplitude=2.0)
    gusts1 = [n1.gust() for _ in range(5)]
    assert [n2.gust() for _ in range(5)] == gusts1
    assert all(-2.0 <= g <= 2.0 for g in gusts1)
    n1.reset()
    assert [n1.gust() for _ in range(5)] == gusts1
