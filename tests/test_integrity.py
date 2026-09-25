"""Hermetic tests for LEVI integrity fingerprints (defensive only).

No HOME writes (HOME sandboxed), no network, no randomness.
"""

from levi.security.integrity import (
    INTEGRITY_SKILLS,
    fnv1a_32,
    gate_pack,
    triple_fingerprint,
    verify_fingerprint,
)


def test_fnv1a_32_known_vectors():
    assert fnv1a_32("") == "811c9dc5"
    assert fnv1a_32("foobar") == "bf9cf968"


def test_fnv1a_32_rejects_non_str():
    try:
        fnv1a_32(123)  # type: ignore[arg-type]
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_fnv1a_32_deterministic_and_avalanche():
    assert fnv1a_32("levi") == fnv1a_32("levi")
    assert fnv1a_32("levi") != fnv1a_32("Levi")


def test_triple_fingerprint_shape():
    fp = triple_fingerprint("abc")
    assert len(fp) == 24
    assert all(c in "0123456789abcdef" for c in fp)


def test_triple_fingerprint_tamper_sensitive():
    a = triple_fingerprint({"id": "pack", "version": "1"})
    b = triple_fingerprint({"id": "pack", "version": "2"})
    c = triple_fingerprint({"id": "pack", "version": "1", "x": 0})
    assert a != b and a != c


def test_verify_fingerprint_roundtrip():
    obj = {"serials": ["KB-1"]}
    expected = triple_fingerprint(obj)
    assert verify_fingerprint(obj, expected)["ok"] is True
    assert verify_fingerprint(obj, "00" * 12)["ok"] is False
    assert verify_fingerprint(obj, "")["ok"] is False


def test_gate_pack_valid_manifest():
    pack = {"id": "p1", "version": "1", "serials": ["KB-1"]}
    pack["fingerprint"] = triple_fingerprint(
        {"id": "p1", "version": "1", "serials": ["KB-1"]}
    )
    assert gate_pack(pack)["ok"] is True


def test_gate_pack_tamper_refused():
    pack = {"id": "p1", "version": "1", "serials": ["KB-1"], "fingerprint": "00" * 12}
    verdict = gate_pack(pack)
    assert verdict["ok"] is False
    assert "tamper" in verdict["reason"]


def test_gate_pack_no_fingerprint_passes_with_note():
    verdict = gate_pack({"id": "p1"})
    assert verdict["ok"] is True
    assert "unverified" in verdict["note"]


def test_gate_pack_invalid_manifest():
    assert gate_pack({})["ok"] is False
    assert gate_pack("nope")["ok"] is False  # type: ignore[arg-type]


def test_integrity_skills_registered():
    ids = {s.id for s in INTEGRITY_SKILLS}
    assert {"security_fingerprint", "security_gate_pack"} <= ids
    for s in INTEGRITY_SKILLS:
        assert s.risk_level.name == "INFO"
        assert s.requires_confirmation is False


def test_skill_fingerprint_handler():
    h = next(s for s in INTEGRITY_SKILLS if s.id == "security_fingerprint").handler
    assert h({"text": "abc"}) == triple_fingerprint("abc")


def test_skill_gate_handler():
    h = next(s for s in INTEGRITY_SKILLS if s.id == "security_gate_pack").handler
    assert "ok=True" in h({"pack": {"id": "p1"}})
