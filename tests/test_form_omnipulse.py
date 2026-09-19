"""omnipulse form tests: the 18-phase lifecycle heartbeat.

Proving bar: tick() is fail-closed on bad beat counts, dry-run pure,
wraps Birth after Termination, and every tick returns a receipt.
"""

import pytest

from levi.omnipulse import FORM_NAME, OmniPulse


def test_tick_advances_one_beat():
    op = OmniPulse()
    assert op.phase() == "Birth"
    r = op.tick()
    assert r["form"] == FORM_NAME
    assert r["status"] == "heartbeat"
    assert op.phase() == "Calibration"
    assert op.status()["beats"] == 1


def test_tick_multiple_beats_and_full_cycle_wraps():
    op = OmniPulse()
    op.tick(18)
    assert op.phase() == "Birth"  # full cycle returns to Birth
    assert op.status()["beats"] == 18


def test_tick_rejects_bad_beat_counts_as_data():
    op = OmniPulse()
    for bad in ("3", 3.5, -1, None, True, [1]):
        r = op.tick(bad)
        assert r["status"] == "rejected", bad
        assert op.status()["beats"] == 0  # clock untouched
    assert op.phase() == "Birth"


def test_tick_zero_beats_holds():
    op = OmniPulse()
    r = op.tick(0)
    assert r["status"] == "heartbeat"
    assert op.phase() == "Birth"
    assert op.status()["beats"] == 0


def test_tick_dry_run_purity():
    op = OmniPulse(phase="Echo")
    r = op.tick(3, dry_run=True)
    assert r["status"] == "dry-run"
    assert r["dry_run"] is True
    assert op.phase() == "Echo"  # clock untouched
    assert op.status()["beats"] == 0


def test_constructor_rejects_bad_state():
    with pytest.raises(ValueError):
        OmniPulse(beats=-1)
    with pytest.raises(ValueError):
        OmniPulse(phase="Narnia")
    with pytest.raises(ValueError):
        OmniPulse(beats=True)


def test_heartbeat_rides_the_ser18_canon():
    from levi.ser18 import SER18_PHASES

    op = OmniPulse()
    seen = [op.phase()]
    for _ in range(17):
        op.tick()
        seen.append(op.phase())
    assert seen == SER18_PHASES  # the clock walks the canon in order
