"""Hermetic tests for levi.brain.train.v2.curriculum (stdlib only)."""

import pytest

from levi.brain.train.v2 import curriculum as cu
from levi.brain.train.v2.corpus_manager import Doc, doc_sha256


def _doc(text):
    return Doc(id=doc_sha256(text), text=text)


def test_simple_before_complex():
    simple = _doc("the cat sat")
    complex_ = _doc(
        "photosynthesis supercalifragilisticexpialidocious mitochondria "
        "quantum chromodynamics antidisestablishmentarianism epistemology "
        "sesquipedalian defenestration grandiloquence floccinaucinihilipilification "
        "pneumonoultramicroscopicsilicovolcanoconiosis juxtaposition synecdoche "
        "antediluvian crepuscular petrichor sonder apophatic liminal oneiric"
    )
    medium = _doc("the quick brown fox jumps over the lazy dog today")
    m = cu.build_curriculum([complex_, medium, simple], name="t", n_stages=2)
    assert m.order == [simple.id, medium.id, complex_.id]


def test_difficulty_in_unit_range_and_monotone():
    docs = [_doc("a b c"), _doc("x " * 50 + "zyzzyva qwertyuiop"), _doc("hello world")]
    scores = cu.difficulty_scores(docs)
    assert all(0.0 <= v <= 1.0 for v in scores.values())
    ordered = sorted(docs, key=lambda d: scores[d.id])
    assert ordered[0].text == "hello world" or ordered[0].text == "a b c"


def test_deterministic_ordering():
    docs = [_doc(f"doc {i} " + "word " * (i % 7)) for i in range(30)]
    a = cu.build_curriculum(docs, name="t")
    b = cu.build_curriculum(docs, name="t")
    assert a.order == b.order
    assert a.stage_of == b.stage_of


def test_stages_contiguous_and_cover_all():
    docs = [_doc(f"document number {i}") for i in range(10)]
    m = cu.build_curriculum(docs, name="t", n_stages=4)
    assert set(m.stage_of) == set(m.order) == {d.id for d in docs}
    stages = [m.stage_of[d] for d in m.order]
    assert stages == sorted(stages)  # contiguous in curriculum order
    assert set(stages) <= {0, 1, 2, 3}
    # stage 0 docs are all easier than stage 3 docs
    s0 = cu.stage_docs(m, 0)
    s3 = cu.stage_docs(m, 3)
    assert max(m.difficulty[d] for d in s0) <= min(m.difficulty[d] for d in s3)


def test_stage_docs_in_curriculum_order():
    docs = [_doc(f"text {i}") for i in range(8)]
    m = cu.build_curriculum(docs, name="t", n_stages=2)
    for s in range(2):
        ids = cu.stage_docs(m, s)
        positions = [m.order.index(d) for d in ids]
        assert positions == sorted(positions)


def test_empty_curriculum():
    m = cu.build_curriculum([], name="empty")
    assert m.order == [] and m.stage_of == {} and m.difficulty == {}


def test_invalid_n_stages():
    with pytest.raises(ValueError, match="n_stages"):
        cu.build_curriculum([_doc("x")], name="t", n_stages=0)


def test_save_load_roundtrip(tmp_path):
    docs = [_doc("short"), _doc("a much longer document with rarer words zyzzyva")]
    m = cu.build_curriculum(docs, name="t", source_manifests=["courses@2026-09-15"])
    p = cu.save_curriculum(m, tmp_path / "curr.json")
    back = cu.load_curriculum(p)
    assert back.name == "t"
    assert back.order == m.order
    assert back.stage_of == m.stage_of
    assert back.source_manifests == ["courses@2026-09-15"]
    assert back.difficulty.keys() == m.difficulty.keys()


def test_describe_stages(tmp_path):
    docs = [_doc(f"doc {i} " + "w " * i) for i in range(12)]
    m = cu.build_curriculum(docs, name="t", n_stages=3)
    desc = cu.describe_stages(m)
    assert [d["stage"] for d in desc] == [0, 1, 2]
    assert sum(d["n_docs"] for d in desc) == 12
    assert desc[0]["difficulty_min"] <= desc[2]["difficulty_max"]


def test_rarity_drives_ordering():
    # Same length, different vocabulary rarity.
    common = _doc("the the the the the and and and")
    rare = _doc("zyzzyva qwertyuiop asdfghjkl zxcvbnm")
    m = cu.build_curriculum([rare, common], name="t", n_stages=1)
    assert m.order[0] == common.id
