"""Tests for dual-reality files and the seven-worlds lens."""

import sys

sys.path.insert(0, "core")

from levi.dual import create, read, seal, verify, verify_seal  # noqa: E402
from levi.worlds import WORLDS, checkin, classify, recent  # noqa: E402


def _tmp(tmp_path, name="thing.dual.md"):
    return tmp_path / name


def test_dual_create_and_read(tmp_path):
    p = create(
        _tmp(tmp_path),
        "Engine X",
        physical="runs the nightly scan and writes receipts",
        canon="Engine X exists so the nightly scan is receipted",
    )
    df = read(p.path)
    assert df.title == "Engine X"
    assert "nightly scan" in df.physical
    assert "receipted" in df.canon


def test_dual_requires_both_sides(tmp_path):
    try:
        create(_tmp(tmp_path), "Half", physical="", canon="doctrine")
    except ValueError:
        pass
    else:
        raise AssertionError("empty physical side should be refused")


def test_dual_verify_in_sync(tmp_path):
    p = create(
        _tmp(tmp_path),
        "Engine X",
        physical="runs the nightly scan and writes receipts",
        canon="Engine X exists so the nightly scan is receipted",
    )
    report = verify(p.path)
    assert report["in_sync"], report["issues"]


def test_dual_verify_flags_vocab_drift(tmp_path):
    p = create(
        _tmp(tmp_path),
        "Engine X",
        physical="runs the nightly scan and writes receipts",
        canon="completely unrelated doctrine about baking bread",
    )
    report = verify(p.path)
    assert not report["in_sync"]
    assert any("vocabulary" in i for i in report["issues"])


def test_dual_seal_and_drift(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    p = create(
        _tmp(tmp_path),
        "Engine X",
        physical="runs the nightly scan and writes receipts",
        canon="Engine X exists so the nightly scan is receipted",
    )
    seal(p.path)
    assert verify_seal(p.path)["sealed"] is True
    # drift: rewrite the file with changed content
    p.path.write_text(p.path.read_text().replace("nightly scan", "weekly sweep"))
    res = verify_seal(p.path)
    assert res["sealed"] is False and res["drifted"] is True


def test_dual_refuses_seal_when_out_of_sync(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    p = create(
        _tmp(tmp_path),
        "Engine X",
        physical="runs the nightly scan and writes receipts",
        canon="completely unrelated doctrine about baking bread",
    )
    try:
        seal(p.path)
    except ValueError:
        pass
    else:
        raise AssertionError("sealing an out-of-sync file should be refused")


def test_worlds_seven_and_identity_first():
    assert len(WORLDS) == 7
    assert list(WORLDS)[0] == "identity"


def test_worlds_classify():
    assert "opportunity" in classify("job interview tomorrow morning")
    assert "physical" in classify("clean the house and fix the car")
    assert "social" in classify("call mom tonight")


def test_worlds_checkin_and_recent(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    checkin("internal", "low energy today")
    rows = recent("internal")
    assert len(rows) == 1 and rows[0]["note"] == "low energy today"
    try:
        checkin("netherworld", "nope")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown world should be refused")
