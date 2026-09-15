"""King's Wyrd-ROM: session rupture-locks, distinct from the manuscript engine's."""
import os
import stat

from levi.king.ledger import ContinuityLedger
from levi.king.rom import SessionRom


def _rom(tmp_path):
    return SessionRom(data_dir=tmp_path / "king")


def test_division_is_documented():
    # The two ROMs must not be silently collapsed: this module's header
    # must name the manuscript engine's rupture as the distinct concept.
    import levi.king.rom as rom_mod

    header = rom_mod.__doc__ or ""
    assert "LWPModelEngine.wyrd_rupture" in header
    assert "rupture_session" in header


def test_rupture_session_locks_fingerprint(tmp_path):
    led = ContinuityLedger(data_dir=tmp_path / "king")
    led.harvest("model_engine", 500, 2, "expand")
    rom = _rom(tmp_path)
    lock = rom.rupture_session("test lock", led.fingerprint())
    assert lock["scope"] == "king-session"
    assert lock["engine_scope"] == "multi-engine"
    assert lock["ledger_fingerprint"] == led.fingerprint()
    assert rom.count() == 1
    assert rom.latest()["id"] == lock["id"]


def test_verify_lock(tmp_path):
    rom = _rom(tmp_path)
    lock = rom.rupture_session("r", "abc123")
    assert rom.verify(lock["id"], "abc123") is True
    assert rom.verify(lock["id"], "different") is False
    assert rom.verify("rom.nope", "abc123") is False


def test_locks_are_append_only_and_persist(tmp_path):
    rom = _rom(tmp_path)
    a = rom.rupture_session("first", "fp1")
    b = rom.rupture_session("second", "fp2")
    rom2 = SessionRom(data_dir=tmp_path / "king")
    assert rom2.count() == 2
    assert [lock["id"] for lock in rom2.locks] == [a["id"], b["id"]]
    # latest() is the most recent, not a mutation of the first
    assert rom2.latest()["reason"] == "second"


def test_rom_file_is_owner_only(tmp_path):
    rom = _rom(tmp_path)
    rom.rupture_session("r", "fp")
    mode = stat.S_IMODE(os.stat(rom.path).st_mode)
    assert mode == 0o600, f"rom.json mode is {oct(mode)}, expected 0o600"


def test_corrupt_rom_starts_clean(tmp_path):
    d = tmp_path / "king"
    d.mkdir()
    (d / "rom.json").write_text("garbage", encoding="utf-8")
    rom = SessionRom(data_dir=d)
    assert rom.count() == 0
    assert rom.latest() is None
