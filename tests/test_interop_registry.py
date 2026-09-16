"""Hermetic tests for the capability registry (levi.interop.registry)."""

import pytest

from levi.interop.manifest import DECLARATIONS
from levi.interop.registry import Registry, RegistryError


def _fresh():
    return Registry()


def test_manifest_registers_all_modules():
    reg = _fresh()
    for name, decl in DECLARATIONS.items():
        reg.register(name, provides=decl["provides"], requires=decl["requires"])
    assert set(reg.modules()) == {
        "organs",
        "memory-store",
        "memory-retrieval",
        "rag",
        "bot-services",
        "growth",
        "academy",
        "bounty",
        "knowledge",
        "oath",
        "agent-assistant",
        # axis-3 additions (deny-closed, all must register + check)
        "methods",
        "revival",
        "galaxy",
        "lifepack",
        "bloodstream",
        "daemon",
        "perpetual",
        "archive",
        "cyber-skills",
        "factory",
        "finance",
        "forge",
        # operator + additions + research waves, 2026-09-16 sweep
        "signals",
        "creed",
        "promises",
        "decisions",
        "interruptions",
        "snapshots",
        "drift",
        "teachback",
        "energy",
        "friction",
        "sweeps",
        "premortem",
        "research",
        "ephemera",
        "feedreader",
        "packs",
        "commitments",
        "recap",
        "classifieds",
        "dials",
        "bridging",
        "communities",
        "threads",
        "charters",
        "capproto",
        "mailtriage",
        "vaults",
        "canvas",
        "discover",
        "presence",
        "honestsearch",
        "recommender",
        # games wave (fair-play additions)
        "games",
        # telegraph (perpetual-hunt wave-001: dead protocols revived)
        "telegraph",
        # feedlab (perpetual-hunt daily 2026-09-16: giant-patterns inversion)
        "feedlab",
        # copper (perpetual-hunt wave-004: scored timed choreography)
        "copper",
        # verify (perpetual-hunt wave-006: pre-digital proof rituals)
        "verify",
        # liberation (perpetual-hunt daily 2026-09-15: roach-motel inversion)
        "liberation",
        # shelf (perpetual-hunt daily 2026-09-16: fallen platforms)
        "shelf",
        # circles (perpetual-hunt daily 2026-09-16 evening: Path's cap)
        "circles",
        # analog (perpetual-hunt wave-006: pre-digital computation revived)
        "analog",
        # reveal (perpetual-hunt daily 2026-09-16b: retired software wave)
        "reveal",
        # quickdial (perpetual-hunt evening-20260916-software: dead desktop
        # software wave 3 — committed in b094858, hardcoded set lagged behind)
        "quickdial",
        # dead-networks (perpetual-hunt wave-008)
        "digest",
        "pdi",
        "boards",
        "doors",
        # craft (perpetual-hunt wave-014: lost crafts revived)
        "craft",
    }


def test_manifest_passes_check_all():
    reg = _fresh()
    for name, decl in DECLARATIONS.items():
        reg.register(name, provides=decl["provides"], requires=decl["requires"])
    reg.check_all()  # must not raise


def test_check_unknown_module_denied():
    reg = _fresh()
    with pytest.raises(RegistryError):
        reg.check("nope-not-a-module")


def test_check_unknown_requires_target_denied():
    reg = _fresh()
    reg.register("a", provides=["a.x"], requires=["ghost-module"])
    with pytest.raises(RegistryError, match="unknown requires"):
        reg.check("a")


def test_check_all_aggregates_failures():
    reg = _fresh()
    reg.register("ok-module", provides=["ok.x"])
    reg.register("bad-one", requires=["missing-a"])
    reg.register("bad-two", requires=["missing-b"])
    with pytest.raises(RegistryError) as excinfo:
        reg.check_all()
    msg = str(excinfo.value)
    assert "bad-one" in msg and "bad-two" in msg


def test_register_duplicate_denied():
    reg = _fresh()
    reg.register("a")
    with pytest.raises(RegistryError, match="already declared"):
        reg.register("a")


def test_register_malformed_caps_denied():
    reg = _fresh()
    with pytest.raises(RegistryError):
        reg.register("a", provides="not-a-list")
    with pytest.raises(RegistryError):
        reg.register("b", requires=[""])
    with pytest.raises(RegistryError):
        reg.register("c", provides=["x", "x"])  # duplicates
    with pytest.raises(RegistryError):
        reg.register("", provides=[])


def test_dependents_of_direct():
    reg = _fresh()
    reg.register("memory-store", provides=["memory.write"])
    reg.register("rag", requires=["memory-store"])
    reg.register("bot-services", requires=["rag"])
    assert reg.dependents_of("memory-store") == ["rag"]
    assert reg.dependents_of("rag") == ["bot-services"]
    assert reg.dependents_of("bot-services") == []


def test_dependents_of_transitive():
    reg = _fresh()
    reg.register("memory-store")
    reg.register("memory-retrieval", requires=["memory-store"])
    reg.register("rag", requires=["memory-retrieval"])
    reg.register("bot-services", requires=["rag"])
    assert reg.dependents_of("memory-store", transitive=True) == [
        "bot-services",
        "memory-retrieval",
        "rag",
    ]


def test_dependents_of_unknown_module_denied():
    reg = _fresh()
    with pytest.raises(RegistryError):
        reg.dependents_of("ghost")


def test_default_registry_preloaded_and_valid():
    import levi.interop.registry as regmod

    assert len(regmod.modules()) == len(DECLARATIONS)
    regmod.check_all()  # must not raise
    deps = regmod.dependents_of("memory-store", transitive=True)
    assert "rag" in deps and "bot-services" in deps


def test_manifest_memory_store_is_foundation():
    # the substrate must be required-by many and require nothing
    assert DECLARATIONS["memory-store"]["requires"] == []
    dependents = [
        name
        for name, decl in DECLARATIONS.items()
        if "memory-store" in decl["requires"]
    ]
    assert len(dependents) >= 4
