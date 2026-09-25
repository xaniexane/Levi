"""Hermetic tests for levi.craft.hallmark — struck provenance."""

import os

import pytest

from levi.craft import hallmark


def test_strike_produces_tripartite_mark():
    mark = hallmark.strike(
        b"artifact bytes", maker="chauncey", verifier="assay-office", quality="fine"
    )
    assert mark["hallmark"] == "levi-1"
    assert mark["maker"] == "chauncey"
    assert mark["verifier"] == "assay-office"
    assert len(mark["sha256"]) == 64
    assert mark["quality"] == "fine"
    assert mark["date_letter"] in hallmark._DATE_LETTERS


def test_strike_refuses_anonymous():
    with pytest.raises(ValueError):
        hallmark.strike(b"x", maker="")


def test_strike_refuses_self_verification():
    # Maker claims and verification are structurally separated.
    with pytest.raises(ValueError, match="self-verification"):
        hallmark.strike(b"x", maker="chauncey", verifier="chauncey")


def test_strike_refuses_unknown_quality():
    with pytest.raises(ValueError, match="quality"):
        hallmark.strike(b"x", maker="chauncey", quality="mythril")


def test_verify_roundtrip():
    payload = b"the guildhall corpus entry"
    mark = hallmark.strike(payload, maker="scribe", verifier="warden")
    ok, reason = hallmark.verify(mark, payload)
    assert ok, reason


def test_verify_detects_tampering():
    mark = hallmark.strike(b"original", maker="scribe", verifier="warden")
    ok, reason = hallmark.verify(mark, b"altered")
    assert not ok
    assert "mismatch" in reason


def test_verify_rejects_non_hallmark():
    ok, _ = hallmark.verify({"nope": True}, b"x")
    assert not ok


def test_sidecar_roundtrip(tmp_path):
    target = str(tmp_path / "record.txt")
    with open(target, "w") as fh:
        fh.write("provenance matters")
    mark = hallmark.strike_file(target, maker="chauncey", verifier="assay")
    sidecar = hallmark.read_sidecar(target)
    assert sidecar == mark
    assert os.path.isfile(target + hallmark.SIDECAR_SUFFIX)


def test_read_sidecar_none_when_unstruck(tmp_path):
    assert hallmark.read_sidecar(str(tmp_path / "naked.txt")) is None


def test_require_hallmarked_deny_closed(tmp_path):
    naked = str(tmp_path / "naked.txt")
    with open(naked, "w") as fh:
        fh.write("no mark")
    with pytest.raises(hallmark.UnhallmarkedError, match="no hallmark"):
        hallmark.require_hallmarked(naked)


def test_require_hallmarked_refuses_tampered(tmp_path):
    target = str(tmp_path / "record.txt")
    with open(target, "w") as fh:
        fh.write("original")
    hallmark.strike_file(target, maker="chauncey", verifier="assay")
    with open(target, "w") as fh:
        fh.write("tampered")
    with pytest.raises(hallmark.UnhallmarkedError, match="mismatch"):
        hallmark.require_hallmarked(target)


def test_require_hallmarked_passes(tmp_path):
    target = str(tmp_path / "record.txt")
    with open(target, "w") as fh:
        fh.write("solid")
    hallmark.strike_file(target, maker="chauncey", verifier="assay")
    mark = hallmark.require_hallmarked(target)
    assert mark["maker"] == "chauncey"


def test_date_letter_cycles():
    assert hallmark.date_letter(2026) == hallmark._DATE_LETTERS[2026 % 20]
    assert hallmark.date_letter(2026) == hallmark.date_letter(2046)
