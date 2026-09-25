"""Tests for the fairtrade counter-play layer (aware of their trades,
exploiting the opposite — profitably and popularly, in LEVI's own ways).
"""

import subprocess
import sys

import pytest

from levi.fairtrade import (
    all_counterplays,
    brief,
    counterplay,
    pattern_ids,
    playbook,
)

REQUIRED_KEYS = {"technique", "profit_engine", "popularity_engine", "levi_proof"}


def test_every_pattern_has_a_counterplay():
    assert set(
        all_counterplays()[i]["pattern_id"] for i in range(len(pattern_ids()))
    ) == set(pattern_ids())


def test_counterplay_has_all_required_keys():
    for pid in pattern_ids():
        cp = counterplay(pid)
        assert REQUIRED_KEYS <= set(cp.keys()), pid


def test_counterplay_fields_are_substantive():
    for pid in pattern_ids():
        cp = counterplay(pid)
        for key in REQUIRED_KEYS:
            assert isinstance(cp[key], str) and len(cp[key]) > 40, (pid, key)


def test_counterplay_names_the_opposite_technique():
    cp = counterplay("walled-garden-generosity")
    assert "export" in cp["technique"].lower()
    cp = counterplay("roach-motel-funnel")
    assert "exit" in cp["technique"].lower() or "cancel" in cp["technique"].lower()


def test_profit_engine_names_the_paid_layers():
    for pid in pattern_ids():
        cp = counterplay(pid)
        text = cp["profit_engine"].lower()
        assert any(
            word in text
            for word in (
                "paid",
                "money",
                "sells",
                "premium",
                "managed",
                "layers",
                "lifetime value",
                "ltv",
                "converts",
            )
        ), pid


def test_popularity_engine_is_a_spread_story():
    for pid in pattern_ids():
        cp = counterplay(pid)
        assert len(cp["popularity_engine"]) > 40, pid


def test_levi_proof_grounds_the_claim():
    markers = (
        "forge",
        "life-pack",
        "fair play charter",
        "interpenetrationengine",
        "check_no_mask",
        "local-first",
        "megazord",
    )
    for pid in pattern_ids():
        cp = counterplay(pid)
        text = cp["levi_proof"].lower()
        assert any(m in text for m in markers), pid


def test_unknown_pattern_id_raises():
    with pytest.raises(ValueError):
        counterplay("no-such-trade")


def test_brief_covers_every_pattern():
    from levi.fairtrade import get_pattern

    b = brief()
    for pid in pattern_ids():
        assert get_pattern(pid)["name"] in b, pid
    assert "opposite" in b.lower()
    assert "trust" in b.lower()


def test_playbook_contains_every_technique():
    pb = playbook()
    for cp in all_counterplays():
        assert cp["technique"].split(":")[0] in pb
        assert cp["pattern_name"] in pb


def _run_cli(*argv):
    return subprocess.run(
        [sys.executable, "-m", "levi.fairtrade", *argv],
        capture_output=True,
        text=True,
        cwd=".",
        env={"PYTHONPATH": "core", "PATH": "/usr/bin:/bin"},
    )


def test_cli_counter_ok():
    r = _run_cli("counter", "roach-motel-funnel")
    assert r.returncode == 0, r.stderr
    assert "counter-play" in r.stdout.lower()
    assert "profit" in r.stdout.lower()


def test_cli_counter_unknown_id_fails():
    r = _run_cli("counter", "no-such-trade")
    assert r.returncode == 2


def test_cli_playbook_ok():
    r = _run_cli("playbook")
    assert r.returncode == 0, r.stderr
    assert "COUNTER-PLAYBOOK" in r.stdout


def test_cli_brief_ok():
    r = _run_cli("brief")
    assert r.returncode == 0, r.stderr
    assert "aware" in r.stdout.lower()
