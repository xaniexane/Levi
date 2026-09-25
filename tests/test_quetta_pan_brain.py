"""Tests for the rebuilt QuettaPanDaVinci brain.

Honest scope: the class name, MD5->state mapping shape, coherence
range, mutation names, and the +22% figure are Chauncey's (chat 74).
Detector internals are reconstructed — these tests pin the
reconstructed behavior so future changes are deliberate.
"""

from levi.quetta_pan.brain import CLAIMED_TERNARY_GAIN, QuettaPanDaVinci


def test_phase_hash_state_range_and_determinism():
    b1 = QuettaPanDaVinci("x = 1\n")
    b2 = QuettaPanDaVinci("x = 1\n")
    assert b1.phase_hash == b2.phase_hash
    assert b1.state == b2.state
    assert 1 <= b1.state <= 13
    # different source -> (almost surely) different phase
    b3 = QuettaPanDaVinci("y = 2\n")
    assert b3.phase_hash != b1.phase_hash


def test_coherence_range():
    for src in ("a", "hello world", "def f():\n    pass\n", "x" * 1000):
        b = QuettaPanDaVinci(src)
        assert 0.96 <= b.coherence <= 1.0, src


def test_detect_ternary_inversion():
    b = QuettaPanDaVinci("")
    muts = b.detect_mutations("label = 'yes' if ok else 'no'\n", ".py")
    tern = [m for m in muts if m["name"] == "Ternary Inversion"]
    assert len(tern) == 1
    assert tern[0]["claimed_gain"] == CLAIMED_TERNARY_GAIN == "+22%"
    assert "not measured" in tern[0]["gain_note"]
    assert tern[0]["line"] == 1
    assert tern[0]["provenance"] == "reconstructed-detector"


def test_detect_entropy_lock():
    b = QuettaPanDaVinci("")
    muts = b.detect_mutations("try:\n    f()\nexcept:\n    pass\n", ".py")
    locks = [m for m in muts if m["name"] == "Entropy Lock"]
    assert locks and locks[0]["kind"] == "security"
    # bare-except is python-only: not reported for TS
    ts_muts = b.detect_mutations("try {\n f()\n} catch {\n}\n", ".ts")
    assert not [
        m
        for m in ts_muts
        if m["name"] == "Entropy Lock" and "bare except" in m["detail"]
    ]
    # TS 'any' is an entropy spot
    ts_any = b.detect_mutations("let d: any = {};\n", ".ts")
    assert any(m["name"] == "Entropy Lock" for m in ts_any)


def test_detect_harmony_refactor():
    b = QuettaPanDaVinci("")
    muts = b.detect_mutations("def f():\n\treturn 1   \n", ".py")
    harm = [m for m in muts if m["name"] == "Harmony Refactor"]
    assert len(harm) >= 2  # tab indentation + trailing whitespace
    assert all(m["provenance"] == "reconstructed-detector" for m in harm)


def test_phase_snapshot_shape():
    b = QuettaPanDaVinci("src")
    snap = b.phase()
    assert set(snap) == {"phase_hash", "state", "coherence"}
    assert len(snap["phase_hash"]) == 32
