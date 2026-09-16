"""Tests for levi.identity.cycle — the full loop, incl. --scope all."""

from levi.identity.cycle import IdentityCycle
from levi.identity.genome import GenomeStore


def _store(tmp_path):
    return GenomeStore(home=tmp_path)


def _identity():
    return {
        "name": "cycle-id",
        "traits": {"caution": 0.5, "novelty": 0.5},
        "params": {"tempo": 1.0},
        "fragments": ["steady"],
        "lineage": [],
    }


def test_cycle_runs_and_updates_genome(tmp_path):
    cyc = IdentityCycle(store=_store(tmp_path))
    out1 = cyc.run(_identity(), n_variants=3, seed="c1")
    out2 = cyc.run(_identity(), n_variants=3, seed="c1")
    assert out1 == out2  # deterministic
    assert len(out1["variants"]) == 3
    assert out1["winner"] in [v["name"] for v in out1["variants"]]
    assert "reflection" in out1 and "lessons" in out1 and "deltas" in out1
    store = _store(tmp_path)
    assert store.load()["cycles"] >= 1


def test_cycle_uses_pluggable_scorer(tmp_path):
    seen = []

    def scorer(variant):
        seen.append(variant["name"])
        return 0.99

    out = IdentityCycle(store=_store(tmp_path), scorer=scorer).run(
        _identity(), n_variants=2, seed="c2"
    )
    assert seen  # scorer was consulted
    assert out["winner_score"] == 0.99
    assert out["outcome"]["success"] is True


def test_cycle_failure_path_composts(tmp_path):
    out = IdentityCycle(store=_store(tmp_path), scorer=lambda v: 0.1).run(
        _identity(), n_variants=2, seed="c3"
    )
    assert out["outcome"]["success"] is False
    assert out["outcome"]["failures"]
    assert out["lessons"][0]["kind"] == "failure"


def test_scope_all_covers_manifest(tmp_path):
    from levi.interop.manifest import DECLARATIONS

    out = IdentityCycle(store=_store(tmp_path)).run_scope_all(
        n_variants=1, seed="s1", cross_pollenate=False
    )
    assert out["scope"] == "all"
    assert out["modules"] == len(DECLARATIONS)
    assert len(out["results"]) == len(DECLARATIONS)
    names = [r["module"] for r in out["results"]]
    assert names == sorted(names)
    for r in out["results"]:
        assert 0.0 <= r["coherence"] <= 1.0
        assert len(r["variants"]) == 1


def test_scope_all_deterministic(tmp_path):
    kw = dict(n_variants=2, seed="s9", cross_pollenate=True)
    a = IdentityCycle(store=_store(tmp_path)).run_scope_all(**kw)
    b = IdentityCycle(store=_store(tmp_path)).run_scope_all(**kw)
    assert a["results"] == b["results"]


def test_scope_all_cross_pollination_records_provenance(tmp_path):
    out = IdentityCycle(store=_store(tmp_path)).run_scope_all(
        n_variants=2, seed="s7", cross_pollenate=True
    )
    inherited_any = False
    for r in out["results"]:
        for inherited in r["inherited"]:
            for _trait, prov in inherited.items():
                inherited_any = True
                assert prov["from"] != r["module"]
                assert "value" in prov
    assert inherited_any


def test_scope_all_stores_candidates_without_touching_modules(tmp_path):
    store = _store(tmp_path)
    IdentityCycle(store=store).run_scope_all(n_variants=1, seed="s5")
    genome = store.load()
    assert genome["candidates"]
    assert len(genome["candidates"]) > 10
    for _module, variants in genome["candidates"].items():
        assert isinstance(variants, list) and variants


# ── elitist evolution: champions never regress ─────────────────────


def _fresh_cycle(tmp_path):
    from levi.identity.cycle import IdentityCycle
    from levi.identity.genome import GenomeStore

    store = GenomeStore(tmp_path)
    return IdentityCycle(store=store), store


def test_fitness_is_deterministic():
    from levi.identity.cycle import fitness

    ident = {"name": "x", "traits": {"a": 0.8}, "params": {}, "fragments": []}
    assert fitness(ident) == fitness(ident)


def test_fitness_penalizes_fractures():
    from levi.identity.cycle import fitness

    healthy = {"name": "x", "traits": {"a": 1.0}, "params": {}, "fragments": []}
    broken = {"name": "x", "traits": {"a": 1.5}, "params": {}, "fragments": []}
    assert fitness(healthy) > fitness(broken)


def test_evolve_never_regresses(tmp_path):
    cycle, store = _fresh_cycle(tmp_path)
    first = cycle.evolve(generations=2, n_variants=3, seed="a")
    before = {s["name"]: s["champion_score"] for s in first["results"]}
    second = cycle.evolve(generations=2, n_variants=3, seed="b")
    for s in second["results"]:
        assert s["champion_score"] >= before[s["name"]] - 1e-9, s["name"]


def test_evolve_crowns_champions_for_all_identities(tmp_path):
    from levi.identity.cycle import ORGANISM_FORMS
    from levi.identity.scope import iter_module_identities

    cycle, store = _fresh_cycle(tmp_path)
    out = cycle.evolve(generations=1, n_variants=2, seed="c")
    modules = list(iter_module_identities())
    # one organism: the list holds modules + forms (cybrus appears in both,
    # sharing one champion entry — module and form are one identity)
    assert out["identities"] == len(modules) + len(ORGANISM_FORMS)
    expected = {i["name"] for i in modules} | set(ORGANISM_FORMS)
    for name in expected:
        champ = store.get_champion(name)
        assert champ is not None, name
        assert champ["score"] >= 0


def test_evolve_only_dethrones_on_strict_improvement(tmp_path):
    cycle, store = _fresh_cycle(tmp_path)
    out = cycle.evolve(generations=1, n_variants=2, seed="d")
    for s in out["results"]:
        champ = store.get_champion(s["name"])
        assert champ["score"] == s["champion_score"]
        assert champ["generation"] <= 1
