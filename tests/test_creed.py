"""Tests for levi.creed — laws, tone masks, and the promotion rule.

All hermetic: HOME is pointed at tmp_path (masks persist under the
fake home) and the promotion tracker gets an injected MemoryStore, so
the real ~/.levi is never touched.
"""

from __future__ import annotations

import dataclasses

import pytest

from levi.creed import laws as creed_laws
from levi.creed import masks as creed_masks
from levi.creed.promotion import (
    PROMOTED,
    PROMOTION_THRESHOLD,
    PROVISIONAL,
    PromotionTracker,
    consolidation_corroboration_hook,
)
from levi.growth.consolidate import consolidate
from levi.growth.reflect import Learning
from levi.memory.store import MemoryStore
from levi.memory.types import MemoryType


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _tmp_home(tmp_path, monkeypatch):
    """Point LEVI home at tmp for every test in this module."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LEVI_HOME", raising=False)
    creed_masks.reset_default_manager()
    yield
    creed_masks.reset_default_manager()


@pytest.fixture()
def store(tmp_path):
    return MemoryStore(data_dir=tmp_path / "memory")


@pytest.fixture()
def tracker(store):
    return PromotionTracker(store=store)


# ---------------------------------------------------------------------------
# laws: immutable by construction
# ---------------------------------------------------------------------------


def test_laws_are_frozen_records():
    assert isinstance(creed_laws.LAWS, tuple)
    assert len(creed_laws.LAWS) >= 7
    for law in creed_laws.LAWS:
        assert isinstance(law, creed_laws.Law)
        with pytest.raises(dataclasses.FrozenInstanceError):
            law.text = "rewritten"  # type: ignore[misc]
    with pytest.raises(TypeError):
        creed_laws.LAWS[0] = creed_laws.LAWS[0]  # type: ignore[index]


def test_laws_cover_the_binding_set():
    ids = {law.id for law in creed_laws.get_laws()}
    assert {
        "local-first",
        "free-core-forever",
        "stdlib-only-kernel",
        "honest-everything",
        "consequential-acts",
        "user-data-stays-home",
        "waymaker-prime",
    } <= ids


def test_get_laws_returns_fresh_list():
    a = creed_laws.get_laws()
    b = creed_laws.get_laws()
    assert a == b and a is not b


def test_laws_digest_stable():
    assert creed_laws.laws_digest() == creed_laws.laws_digest()
    assert len(creed_laws.laws_digest()) == 64


# ---------------------------------------------------------------------------
# masks: tone only, laws never altered
# ---------------------------------------------------------------------------


def test_default_mask_is_steady(tmp_path):
    mgr = creed_masks.MaskManager()
    assert mgr.get_mask().id == "steady"


def test_mask_switch_never_alters_laws(tmp_path):
    mgr = creed_masks.MaskManager()
    before = creed_laws.laws_digest()
    for mask in creed_masks.list_masks():
        mgr.set_mask(mask.id)
        assert mgr.get_mask().id == mask.id
        mgr.assert_laws_intact()
    assert creed_laws.laws_digest() == before


def test_verify_laws_intact_tripwire():
    mgr = creed_masks.MaskManager()
    mgr.assert_laws_intact()  # no raise
    with pytest.raises(RuntimeError):
        creed_masks.verify_laws_intact("0" * 64)


def test_set_mask_rejects_unknown_id_and_keeps_state(tmp_path):
    mgr = creed_masks.MaskManager()
    mgr.set_mask("drill")
    with pytest.raises(ValueError):
        mgr.set_mask("nope")
    assert mgr.get_mask().id == "drill"


def test_mask_state_persists_under_tmp_home(tmp_path):
    mgr = creed_masks.MaskManager()
    mgr.set_mask("terse")
    state_file = tmp_path / "creed" / "mask.json"
    assert state_file.exists()
    assert "terse" in state_file.read_text(encoding="utf-8")
    # a fresh manager on the same home sees it
    assert creed_masks.MaskManager().get_mask().id == "terse"


def test_module_level_set_get_mask_roundtrip(tmp_path):
    creed_masks.set_mask("candid")
    assert creed_masks.get_mask().id == "candid"


def test_masks_have_distinct_levi_names_and_registers():
    masks = creed_masks.list_masks()
    ids = [m.id for m in masks]
    assert set(ids) == {"steady", "drill", "architect", "mirror", "terse", "candid"}
    # adaptation over the persona package: every mask leans on a real register
    from levi.persona import levi as registers

    for m in masks:
        assert registers.get(m.suggested_register) is not None, m.id
        assert m.tone.strip()


def test_system_prompt_leads_with_laws_then_mask_tone(tmp_path):
    prompt = creed_masks.system_prompt("architect")
    laws_text = creed_laws.laws_block()
    assert prompt.startswith(laws_text)
    assert "ACTIVE TONE MASK" in prompt
    assert "Architect" in prompt
    # the mask's tone section comes after the full law block
    assert prompt.index(laws_text) < prompt.index("ACTIVE TONE MASK")


# ---------------------------------------------------------------------------
# promotion rule
# ---------------------------------------------------------------------------


def test_propose_starts_provisional(tracker):
    fid = tracker.propose("The owner reviews security diffs before merging.")
    st = tracker.status(fid)
    assert st["status"] == PROVISIONAL
    assert st["reinforcements"] == 0
    assert st["promoted"] is False
    assert st["threshold"] == PROMOTION_THRESHOLD == 3


def test_two_reinforcements_stays_provisional(tracker):
    fid = tracker.propose("Facts earn trust slowly and lose it fast.")
    tracker.reinforce(fid)
    st = tracker.reinforce(fid)
    assert st["reinforcements"] == 2
    assert st["status"] == PROVISIONAL
    assert st["promoted"] is False


def test_third_reinforcement_promotes(tracker, store):
    fid = tracker.propose("Slow trust beats fast trust in long-running agents.")
    tracker.reinforce(fid)
    tracker.reinforce(fid)
    st = tracker.reinforce(fid)
    assert st["reinforcements"] == 3
    assert st["status"] == PROMOTED
    assert st["promoted"] is True
    assert st["promoted_at"]
    entry = store.get(fid)
    assert "creed-promoted" in entry.tags
    assert "creed-provisional" not in entry.tags
    assert entry in tracker.promoted_facts()
    assert entry not in tracker.provisional_facts()


def test_reinforce_past_threshold_is_noop(tracker):
    fid = tracker.propose("Never silently drop a user's explicit instruction.")
    for _ in range(3):
        tracker.reinforce(fid)
    st = tracker.reinforce(fid)
    assert st["reinforcements"] == 3  # capped, no runaway count
    assert st["promoted"] is True


def test_explicit_promote_works_immediately(tracker):
    fid = tracker.propose("The owner said this is creed now.")
    st = tracker.promote(fid)
    assert st["promoted"] is True
    assert st["reinforcements"] == 0  # explicit path needs no counting
    assert st["promoted_at"]


def test_unknown_fact_id_errors_or_none(tracker):
    with pytest.raises(ValueError):
        tracker.reinforce("no-such-fact")
    with pytest.raises(ValueError):
        tracker.promote("no-such-fact")
    assert tracker.status("no-such-fact") is None
    assert tracker.status("") is None


def test_propose_rejects_empty_content(tracker):
    with pytest.raises(ValueError):
        tracker.propose("   ")


def test_propose_dedups_same_content(tracker):
    fid1 = tracker.propose("Duplicate candidate facts collapse into one.")
    fid2 = tracker.propose("Duplicate candidate facts collapse into one!")
    assert fid1 == fid2


def test_non_creed_entries_are_not_facts(tracker, store):
    other = store.add(
        memory_type=MemoryType.SEMANTIC, content="just a memory", tags=["notes"]
    )
    with pytest.raises(ValueError):
        tracker.reinforce(other.id)
    assert tracker.status(other.id) is None


def test_persistence_roundtrip(tmp_path):
    mem_dir = tmp_path / "memory"
    t1 = PromotionTracker(store=MemoryStore(data_dir=mem_dir))
    fid = t1.propose("Persistence means the creed survives restarts.")
    t1.reinforce(fid)
    # a brand-new tracker over the same home sees the count
    t2 = PromotionTracker(store=MemoryStore(data_dir=mem_dir))
    st = t2.status(fid)
    assert st["reinforcements"] == 1
    assert st["status"] == PROVISIONAL
    t2.promote(fid)
    t3 = PromotionTracker(store=MemoryStore(data_dir=mem_dir))
    assert t3.status(fid)["promoted"] is True


# ---------------------------------------------------------------------------
# growth adapter: corroboration feeds the promotion tracker
# ---------------------------------------------------------------------------


def _growth_learning(text: str) -> Learning:
    return Learning(
        kind="fact",
        content=text,
        confidence=0.8,
        provenance={"mode": "rules"},
    )


def _seed_growth_entry(store, text: str):
    return store.add(
        memory_type=MemoryType.SEMANTIC,
        content=text,
        importance=0.5,
        source="growth",
        tags=["growth", "levi-learned", "fact"],
        metadata={"status": "provisional", "corroborated_count": 0},
    )


def test_consolidate_hook_feeds_reinforcement(store):
    _seed_growth_entry(store, "The owner debugs network issues with tcpdump first.")
    tracker = PromotionTracker(store=store)
    report = consolidate(
        [
            _growth_learning(
                "The owner debugs network issues with tcpdump before other tools"
            )
        ],
        cycle_id="c1",
        store=store,
        on_corroborate=consolidation_corroboration_hook,
    )
    assert report["corroborated"] == 1
    prov = tracker.provisional_facts()
    assert len(prov) == 1
    st = tracker.status(prov[0].id)
    assert st["reinforcements"] == 1
    assert st["status"] == PROVISIONAL


def test_three_corroborations_promote_via_hook(store):
    _seed_growth_entry(store, "The owner prefers terse commit messages in the repo.")
    tracker = PromotionTracker(store=store)
    similar = "The owner prefers terse commit messages for the repo work"
    for cycle in ("c1", "c2", "c3"):
        consolidate(
            [_growth_learning(similar)],
            cycle_id=cycle,
            store=store,
            on_corroborate=consolidation_corroboration_hook,
        )
    promoted = tracker.promoted_facts()
    assert len(promoted) == 1
    assert tracker.status(promoted[0].id)["reinforcements"] == 3


def test_hook_ignores_non_growth_entries(store):
    plain = store.add(
        memory_type=MemoryType.SEMANTIC, content="unrelated note", tags=["notes"]
    )
    assert consolidation_corroboration_hook(plain.id, store) is None
    assert consolidation_corroboration_hook("missing-id", store) is None
    tracker = PromotionTracker(store=store)
    assert tracker.provisional_facts() == []


def test_consolidate_without_hook_still_works(store):
    _seed_growth_entry(store, "The owner runs tests before every single commit.")
    report = consolidate(
        [
            _growth_learning(
                "The owner runs tests before each single commit in the project"
            )
        ],
        cycle_id="c1",
        store=store,
    )
    assert report["corroborated"] == 1
    tracker = PromotionTracker(store=store)
    assert tracker.provisional_facts() == []  # no hook → no creed fact


def test_failing_hook_never_breaks_consolidation(store, capsys):
    _seed_growth_entry(store, "The owner documents every public function carefully.")

    def boom(entry_id, store):  # noqa: ANN001, ANN202
        raise RuntimeError("hook exploded")

    report = consolidate(
        [
            _growth_learning(
                "The owner documents every public function with care and detail"
            )
        ],
        cycle_id="c1",
        store=store,
        on_corroborate=boom,
    )
    assert report["corroborated"] == 1
    assert "hook failed" in capsys.readouterr().out
