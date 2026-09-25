# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Vaultkeeper release tests — reproducible builds, deltas, 12% cut.

Hermetic: no network, no daemons. Tests cover release manifests
(create/verify, source-tree binding), tampered-source and
swapped-artifact rejection, the delta planner/apply round-trip
(change, extension, truncation, identical inputs), corrupt-delta
refusal (bad hashes, missing chunks, stray chunks), and the
platform-cut calculator (exact splits, remainder-to-developer,
fail-closed on non-int/zero/negative amounts).
"""

from __future__ import annotations

import hashlib

import pytest

from levi.dynasty.wave.vaultkeeper_releases import (
    DEFAULT_CHUNK_SIZE,
    PLATFORM_CUT_PERCENT,
    CutError,
    ReleaseError,
    apply_delta,
    create_release,
    plan_delta,
    platform_cut,
    verify_reproducible,
)


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    home = tmp_path / "levi-home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    return home


def _sources():
    return {
        "main.py": b"print('hello vault')\n",
        "lib/util.py": b"def twice(x): return x * 2\n",
    }


def _artifact():
    return b"VAULT-BUILD\x00" + bytes(range(64))


# -- release manifests -------------------------------------------------------


def test_create_release_shape(tmp_home):
    src = _sources()
    art = _artifact()
    m = create_release(src, art)
    assert m["kind"] == "levi-release"
    assert m["file_count"] == 2
    assert m["artifact_len"] == len(art)
    assert m["artifact_sha256"] == hashlib.sha256(art).hexdigest()
    assert m["files"]["main.py"] == hashlib.sha256(src["main.py"]).hexdigest()
    assert len(m["source_tree_sha256"]) == 64
    assert verify_reproducible(m, src, art) is True


def test_source_tree_hash_is_order_independent(tmp_home):
    src = _sources()
    art = _artifact()
    rev = dict(reversed(list(src.items())))
    assert (
        create_release(src, art)["source_tree_sha256"]
        == create_release(rev, art)["source_tree_sha256"]
    )


def test_tampered_source_fails_verify(tmp_home):
    src = _sources()
    art = _artifact()
    m = create_release(src, art)
    evil = dict(src)
    evil["main.py"] = b"print('pwned')\n"
    assert verify_reproducible(m, evil, art) is False
    # added or removed files also break the tree binding
    extra = dict(src)
    extra["backdoor.py"] = b"import os\n"
    assert verify_reproducible(m, extra, art) is False
    fewer = {k: v for k, v in src.items() if k != "lib/util.py"}
    assert verify_reproducible(m, fewer, art) is False


def test_swapped_artifact_fails_verify(tmp_home):
    m = create_release(_sources(), _artifact())
    assert verify_reproducible(m, _sources(), b"different bytes") is False


def test_tampered_manifest_fails_verify(tmp_home):
    m = create_release(_sources(), _artifact())
    forged = dict(m)
    forged["artifact_sha256"] = hashlib.sha256(b"different bytes").hexdigest()
    assert verify_reproducible(forged, _sources(), _artifact()) is False


def test_create_release_rejects_malformed_inputs(tmp_home):
    with pytest.raises(ReleaseError):
        create_release({}, b"x")
    with pytest.raises(ReleaseError):
        create_release({"a.py": "not-bytes"}, b"x")
    with pytest.raises(ReleaseError):
        create_release({"": b"x"}, b"x")
    with pytest.raises(ReleaseError):
        create_release("not-a-dict", b"x")
    with pytest.raises(ReleaseError):
        create_release(_sources(), "not-bytes")
    with pytest.raises(ReleaseError):
        verify_reproducible("nope", _sources(), _artifact())


def test_empty_artifact_round_trip(tmp_home):
    m = create_release(_sources(), b"")
    assert m["artifact_len"] == 0
    assert verify_reproducible(m, _sources(), b"") is True


# -- delta planner -------------------------------------------------------------


def _apply_plan(old, new, chunk_size=DEFAULT_CHUNK_SIZE):
    plan = plan_delta(old, new, chunk_size)
    new_chunks = [new[i : i + chunk_size] for i in range(0, len(new), chunk_size)]
    supplied = {
        entry["index"]: new_chunks[entry["index"]]
        for entry in plan
        if entry["sha256"] != ""
    }
    rebuilt = apply_delta(old, plan, supplied, chunk_size)
    assert rebuilt == new
    return plan


def test_delta_round_trip_change(tmp_home):
    old = bytes(range(256)) * 40
    new = bytearray(old)
    new[5000] ^= 0xFF
    new[9000:9010] = b"0123456789"
    plan = _apply_plan(bytes(old), bytes(new))
    assert all(isinstance(e["index"], int) for e in plan)
    # only the touched chunks ship
    assert {e["index"] for e in plan} == {5000 // 4096, 9000 // 4096}


def test_delta_round_trip_extension(tmp_home):
    old = b"A" * 5000
    new = old + b"B" * 3000
    plan = _apply_plan(old, new)
    assert plan  # the new tail must ship


def test_delta_round_trip_truncation(tmp_home):
    # same chunk count, shorter tail: the tail folds into a changed
    # final chunk — no removal entry needed, round-trip is exact
    old = b"A" * 5000 + b"B" * 3000
    new = b"A" * 5000
    plan = _apply_plan(old, new)
    assert {e["index"] for e in plan} == {1}
    # true chunk removal: fewer chunks in new than old
    old3 = b"A" * 4096 + b"B" * 4096 + b"C" * 100
    new2 = b"A" * 4096 + b"B" * 4096
    plan2 = plan_delta(old3, new2)
    assert any(e["sha256"] == "" for e in plan2)  # dropped chunks marked
    assert apply_delta(old3, plan2, {}, DEFAULT_CHUNK_SIZE) == new2


def test_delta_round_trip_identical(tmp_home):
    old = b"same bytes" * 100
    plan = plan_delta(old, old)
    assert plan == []
    assert apply_delta(old, plan, {}, DEFAULT_CHUNK_SIZE) == old


def test_delta_round_trip_small_chunk_size(tmp_home):
    old = b"abcdefghij"
    new = b"abcXefghijY"
    plan = _apply_plan(old, new, chunk_size=4)
    assert {e["index"] for e in plan} == {0, 2}


def test_delta_corrupt_chunk_refused(tmp_home):
    old = b"A" * 9000
    new = b"A" * 4096 + b"CHANGED" + b"A" * (9000 - 4096 - 7)
    plan = plan_delta(old, new)
    assert len(plan) == 1
    idx = plan[0]["index"]
    with pytest.raises(ReleaseError):
        apply_delta(old, plan, {idx: b"WRONG BYTES"}, DEFAULT_CHUNK_SIZE)


def test_delta_missing_chunk_refused(tmp_home):
    old = b"A" * 9000
    new = b"B" * 9000
    plan = plan_delta(old, new)
    with pytest.raises(ReleaseError):
        apply_delta(old, plan, {}, DEFAULT_CHUNK_SIZE)


def test_delta_stray_chunk_refused(tmp_home):
    old = b"A" * 9000
    with pytest.raises(ReleaseError):
        apply_delta(old, [], {7: b"stray"}, DEFAULT_CHUNK_SIZE)


def test_delta_malformed_plan_refused(tmp_home):
    old = b"abc"
    with pytest.raises(ReleaseError):
        apply_delta(old, [{"index": -1, "sha256": "a" * 64}], {}, DEFAULT_CHUNK_SIZE)
    with pytest.raises(ReleaseError):
        apply_delta(old, [{"index": 0, "sha256": "zz"}], {}, DEFAULT_CHUNK_SIZE)
    with pytest.raises(ReleaseError):
        apply_delta(old, "not-a-list", {}, DEFAULT_CHUNK_SIZE)
    with pytest.raises(ReleaseError):
        apply_delta("not-bytes", [], {}, DEFAULT_CHUNK_SIZE)
    with pytest.raises(ReleaseError):
        plan_delta(b"a", b"b", chunk_size=0)
    with pytest.raises(ReleaseError):
        plan_delta("a", b"b")


# -- platform cut ---------------------------------------------------------------


def test_platform_cut_exact(tmp_home):
    assert PLATFORM_CUT_PERCENT == 12
    assert platform_cut(100) == (12, 88)
    assert platform_cut(10_000) == (1200, 8800)


def test_platform_cut_remainder_goes_to_developer(tmp_home):
    for amount in (1, 3, 7, 99, 101, 999):
        platform, developer = platform_cut(amount)
        assert platform == (amount * 12) // 100
        assert developer == amount - platform
        assert developer >= amount - platform  # developer keeps the remainder
        assert platform + developer == amount
    # 99 cents: 12% = 11.88 -> platform 11, developer 88
    assert platform_cut(99) == (11, 88)
    # 1 cent: platform gets 0, developer keeps everything
    assert platform_cut(1) == (0, 1)


def test_platform_cut_fail_closed(tmp_home):
    with pytest.raises(CutError):
        platform_cut(0)
    with pytest.raises(CutError):
        platform_cut(-100)
    with pytest.raises(CutError):
        platform_cut(99.99)
    with pytest.raises(CutError):
        platform_cut("100")
    with pytest.raises(CutError):
        platform_cut(True)
    with pytest.raises(CutError):
        platform_cut(None)
