"""Tests for customizations.handoff — handoff styles for session boundaries."""

import json

import pytest

from levi.customizations import handoff


def test_build_handoff_defaults():
    h = handoff.build_handoff("night-crew")
    assert h.name == "night-crew"
    assert h.verbosity == "standard"
    assert h.checkpoint_points == ("gate", "blocked")
    assert h.receipt_format == "lines"
    assert h.require_ack is False


def test_build_handoff_full():
    h = handoff.build_handoff(
        "gatekeeper",
        verbosity="terse",
        checkpoint_points=["phase-complete", "run-end"],
        receipt_format="ledger",
        require_ack=True,
    )
    assert h.verbosity == "terse"
    assert h.checkpoint_points == ("phase-complete", "run-end")
    assert h.receipt_format == "ledger"
    assert h.require_ack is True


def test_deny_closed_bad_verbosity():
    with pytest.raises(handoff.HandoffError):
        handoff.build_handoff("x", verbosity="chatty")


def test_deny_closed_bad_checkpoint_point():
    with pytest.raises(handoff.HandoffError):
        handoff.build_handoff("x", checkpoint_points=["someday"])


def test_deny_closed_duplicate_checkpoint_points():
    with pytest.raises(handoff.HandoffError):
        handoff.build_handoff("x", checkpoint_points=["gate", "gate"])


def test_deny_closed_empty_checkpoint_points():
    with pytest.raises(handoff.HandoffError):
        handoff.build_handoff("x", checkpoint_points=[])


def test_deny_closed_bad_receipt_format():
    with pytest.raises(handoff.HandoffError):
        handoff.build_handoff("x", receipt_format="carrier-pigeon")


def test_deny_closed_bad_name():
    with pytest.raises(handoff.HandoffError):
        handoff.build_handoff("")


def test_deny_closed_require_ack_must_be_bool():
    with pytest.raises(handoff.HandoffError):
        handoff.build_handoff("x", require_ack="yes")


def test_round_trip_store(tmp_path):
    h = handoff.build_handoff("night-crew", verbosity="terse", require_ack=True)
    path = handoff.set_active(h, root=tmp_path)
    assert path.name == "handoff.json"
    active = handoff.read_active(root=tmp_path)
    assert active == h


def test_read_active_none_when_unset(tmp_path):
    assert handoff.read_active(root=tmp_path) is None


def test_deactivate(tmp_path):
    handoff.set_active(handoff.build_handoff("x"), root=tmp_path)
    assert handoff.deactivate(root=tmp_path) is True
    assert handoff.read_active(root=tmp_path) is None
    assert handoff.deactivate(root=tmp_path) is False


def test_corrupt_store_is_error_not_none(tmp_path):
    (tmp_path / "handoff.json").write_text("{nope", encoding="utf-8")
    with pytest.raises(handoff.HandoffError):
        handoff.read_active(root=tmp_path)


def test_render_receipt_lines():
    h = handoff.build_handoff("x", verbosity="standard", receipt_format="lines")
    out = handoff.render_receipt(h, ["shipped braid", "no blockers"])
    assert out.startswith("handoff (standard)")
    assert "shipped braid" in out


def test_render_receipt_terse_header():
    h = handoff.build_handoff("x", verbosity="terse")
    out = handoff.render_receipt(h, ["done"])
    assert out.startswith("handoff (terse)")


def test_render_receipt_ledger_is_json():
    h = handoff.build_handoff("x", receipt_format="ledger")
    out = handoff.render_receipt(h, ["shipped braid"])
    data = json.loads(out)
    assert data == {"handoff": "x", "receipt": ["shipped braid"]}


def test_render_receipt_deny_closed():
    h = handoff.build_handoff("x")
    with pytest.raises(handoff.HandoffError):
        handoff.render_receipt(h, "not-a-list")
