"""Proof for Eden laws: containment, quarantine, receipts, isolation."""

import os

import pytest

from levi.eden import ClearanceError, Eden, ZoneError


def _eden(tmp_path):
    return Eden(str(tmp_path / "eden-base"))


def test_zone_write_and_read_stays_inside(tmp_path):
    eden = _eden(tmp_path)
    zone = eden.open_zone("lab")
    rel = zone.write("notes/exp.txt", "hello")
    assert rel == os.path.join("notes", "exp.txt")
    with open(os.path.join(zone.root, rel), encoding="utf-8") as fh:
        assert fh.read() == "hello"


def test_path_escapes_refused(tmp_path):
    eden = _eden(tmp_path)
    zone = eden.open_zone("lab")
    with pytest.raises(ZoneError):
        zone.write("../escape.txt", "nope")
    with pytest.raises(ZoneError):
        zone.write("/abs/path.txt", "nope")
    with pytest.raises(ZoneError):
        zone.write("a/../../escape.txt", "nope")


def test_run_seals_receipt_and_quarantines(tmp_path):
    eden = _eden(tmp_path)
    eden.open_zone("lab")

    def experiment(zone):
        zone.write("out/result.txt", "42")
        return "computed the answer"

    receipt = eden.run("lab", "compute", experiment)
    assert receipt.ok
    assert receipt.files == [os.path.join("out", "result.txt")]
    assert receipt.cleared is False  # Law 2: quarantined by default
    assert len(receipt.seal) == 64
    check = eden.verify_receipts()
    assert check == {"ok": True, "receipts": 1}


def test_failed_run_still_seals_receipt(tmp_path):
    eden = _eden(tmp_path)
    eden.open_zone("lab")

    def boom(zone):
        raise RuntimeError("hypothesis exploded")

    receipt = eden.run("lab", "doomed", boom)
    assert not receipt.ok
    assert "exploded" in receipt.detail
    with pytest.raises(ClearanceError):
        eden.clear(receipt.run_id, "chauncey")


def test_clearance_releases_with_record(tmp_path):
    eden = _eden(tmp_path)
    eden.open_zone("lab")
    receipt = eden.run("lab", "ok-exp", lambda zone: "fine")
    cleared = eden.clear(receipt.run_id, "chauncey")
    assert cleared.cleared is True
    assert cleared.cleared_by == "chauncey"
    # Original receipt untouched; clearance is a new sealed receipt.
    originals = [r for r in eden.receipts() if r["run_id"] == receipt.run_id]
    assert any(not r["cleared"] for r in originals)
    assert any(r["cleared"] for r in originals)
    with pytest.raises(ClearanceError):
        eden.clear(receipt.run_id, "")


def test_zones_are_isolated(tmp_path):
    eden = _eden(tmp_path)
    za = eden.open_zone("a")
    zb = eden.open_zone("b")
    za.write("secret.txt", "zone a only")
    assert not os.path.exists(os.path.join(zb.root, "secret.txt"))
    with pytest.raises(ZoneError):
        eden.run("missing", "x", lambda zone: "x")


def test_receipt_tamper_detected(tmp_path):
    eden = _eden(tmp_path)
    eden.open_zone("lab")
    receipt = eden.run("lab", "x", lambda zone: "x")
    receipt.detail = "edited after the fact"
    check = eden.verify_receipts()
    assert not check["ok"]
    assert check["run_id"] == receipt.run_id
