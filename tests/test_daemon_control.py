"""Control daemon hardening tests (hermetic, stdlib-only)."""

from __future__ import annotations

import json

import pytest

from levi.daemon.control import ControlDaemon, ControlError


@pytest.fixture()
def daemon(tmp_path):
    return ControlDaemon(path=tmp_path / "control.json")


def test_issue_validates_inputs(daemon):
    with pytest.raises(ControlError, match="directive kind"):
        daemon.issue("nonsense_kind")
    with pytest.raises(ControlError, match="directive kind"):
        daemon.issue("")
    with pytest.raises(ControlError, match="strength"):
        daemon.issue("clear", strength=float("nan"))
    with pytest.raises(ControlError, match="strength"):
        daemon.issue("clear", strength=float("inf"))
    with pytest.raises(ControlError, match="strength"):
        daemon.issue("clear", strength=2.0)
    with pytest.raises(ControlError, match="strength"):
        daemon.issue("clear", strength="lots")  # type: ignore[arg-type]
    with pytest.raises(ControlError, match="turns"):
        daemon.issue("clear", turns=0)
    with pytest.raises(ControlError, match="turns"):
        daemon.issue("clear", turns=2.5)  # type: ignore[arg-type]
    with pytest.raises(ControlError, match="turns"):
        daemon.issue("clear", turns=True)  # type: ignore[arg-type]
    with pytest.raises(ControlError, match="target"):
        daemon.issue("lock_persona", target=123)  # type: ignore[arg-type]
    with pytest.raises(ControlError, match="reason"):
        daemon.issue("clear", reason=None)  # type: ignore[arg-type]


def test_issue_and_expiry(daemon):
    d = daemon.issue("boost_persona", target="sage", strength=0.6, turns=2)
    assert d.kind == "boost_persona"
    assert daemon.persona_bias("sage") == pytest.approx(0.6)
    daemon.tick_turn()
    daemon.tick_turn()
    assert daemon.directives == []  # directive itself expired
    # Side effects decay gently (×0.92/turn), not dropped: still positive…
    assert daemon.persona_bias("sage") > 0.0
    # …and gone once decayed below the 0.05 floor.
    for _ in range(40):
        daemon.tick_turn()
    assert daemon.persona_bias("sage") == 0.0


def test_set_stance_validates(daemon):
    with pytest.raises(ControlError, match="intensity"):
        daemon.set_alchemy(intensity=float("nan"))
    with pytest.raises(ControlError, match="intensity"):
        daemon.set_chisel(intensity=1.5)
    with pytest.raises(ControlError, match="enabled"):
        daemon.set_alchemy(enabled="yes")  # type: ignore[arg-type]
    daemon.set_alchemy(intensity=0.7)
    assert daemon.alchemy.intensity == pytest.approx(0.7)


def test_corrupt_directive_record_skipped_valid_kept(tmp_path, capsys):
    path = tmp_path / "control.json"
    payload = {
        "directives": [
            {
                "id": "d1",
                "kind": "lock_persona",
                "target": "sage",
                "strength": 0.5,
                "turns_remaining": 5,
                "reason": "ok",
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            {"id": "d2", "kind": "bogus_kind", "strength": 0.5, "turns_remaining": 5},
            {"id": "d3", "kind": "clear", "strength": "lots", "turns_remaining": 5},
        ],
        "alchemy": {"enabled": True, "intensity": float("nan")},
        "locked_persona": 123,
        "boosts": {"sage": "high", "root": 0.4},
    }
    path.write_text(json.dumps(payload))
    d = ControlDaemon(path=path)
    assert [x.id for x in d.directives] == ["d1"]
    assert d.locked_persona is None  # non-string degraded
    assert d.boosts == {"root": 0.4}  # bad weight dropped
    assert "skipping bad directive" in capsys.readouterr().err


def test_persona_bias_neutral_on_garbage(daemon):
    assert daemon.persona_bias(None) == 0.0  # type: ignore[arg-type]
    assert daemon.persona_bias(["x"]) == 0.0  # type: ignore[arg-type]


def test_persist_failure_is_domain_error(daemon):
    daemon.issue("clear", reason="setup")
    path = daemon.path
    path.unlink()
    path.mkdir()
    with pytest.raises(ControlError, match="cannot persist"):
        daemon.issue("clear", reason="boom")
