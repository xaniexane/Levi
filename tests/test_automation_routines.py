"""Tests for LEVI-native routine learning + organism integration.

Routines ("watch me once"): recorded from the growth session harvest or by
hand, stored as user-owned data, played back only through the automation
rail with a permission gate on every step. A denied gate stops the routine
fail-closed.

Integration: the automation module is registered in the interop manifest,
the warehouses inventory, the capability atlas, and bridged to agent
intents via the interop adapter — the Megazord axes, additive only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from levi.automation import (
    RoutineStep,
    delete_routine,
    get_routine,
    list_routines,
    play_routine,
    record_from_session,
    record_routine,
)
from levi.automation.hitl import auto_approve, auto_deny
from levi.interop.adapters import automation_minions as adapter
from levi.interop.atlas import export_atlas
from levi.interop.manifest import DECLARATIONS
from levi.interop.registry import Registry
from levi.interop.warehouses import WAREHOUSES, browse_warehouse


@pytest.fixture(autouse=True)
def _hermetic_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi-home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def _complete_minion_id() -> str:
    from levi.automation import MINIONS, find_minion

    minion = next(b for b in MINIONS if not b.incomplete)
    assert find_minion(MINIONS, minion.id) is minion
    return minion.id


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


def test_record_routine_happy_path():
    routine = record_routine(
        "morning flow",
        [
            RoutineStep(
                label="stretch",
                minion_id=_complete_minion_id(),
                event_summary="morning stretch",
            ),
            RoutineStep(label="note to self", note="drink water"),
        ],
    )
    assert routine.id
    assert routine.name == "morning flow"
    assert routine.source == "manual"
    assert len(routine.steps) == 2
    assert get_routine(routine.id).id == routine.id
    assert any(r.id == routine.id for r in list_routines())


def test_record_routine_deny_closed():
    with pytest.raises(ValueError):
        record_routine("", [RoutineStep(label="x")])
    with pytest.raises(ValueError):
        record_routine("empty", [])
    with pytest.raises(ValueError):
        record_routine(
            "bad minion",
            [RoutineStep(label="x", minion_id="no-such-minion", event_summary="y")],
        )
    with pytest.raises(ValueError):
        record_routine(
            "no summary", [RoutineStep(label="x", minion_id=_complete_minion_id())]
        )
    with pytest.raises(ValueError):
        record_routine(
            "no label",
            [
                RoutineStep(
                    label="  ", minion_id=_complete_minion_id(), event_summary="y"
                )
            ],
        )


def test_record_routine_rejects_incomplete_bot():
    from levi.automation import MINIONS

    incomplete = [b for b in MINIONS if b.incomplete]
    if not incomplete:
        pytest.skip("catalog has no incomplete intake rows right now")
    with pytest.raises(ValueError):
        record_routine(
            "bad",
            [RoutineStep(label="x", minion_id=incomplete[0].id, event_summary="y")],
        )


def _write_session(sessions_dir: Path, name: str = "demo") -> None:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        {
            "kind": "message",
            "role": "user",
            "ts": "2026-09-17T10:00:00Z",
            "content": "remind me to stretch every morning",
        },
        {
            "kind": "message",
            "role": "assistant",
            "ts": "2026-09-17T10:00:05Z",
            "content": "stretch reminder armed",
        },
    ]
    (sessions_dir / f"{name}.jsonl").write_text(
        "\n".join(json.dumps(r) for r in lines), encoding="utf-8"
    )


def test_record_from_session_watch_me_once(tmp_path):
    sessions_dir = tmp_path / "sessions"
    _write_session(sessions_dir)
    routine = record_from_session("demo", sessions_dir=sessions_dir)
    assert routine.source == "session:demo"
    assert routine.steps, "expected at least one distilled step"
    assert any(s.minion_id for s in routine.steps)


def test_record_from_session_unknown_session(tmp_path):
    with pytest.raises(ValueError):
        record_from_session("ghost", sessions_dir=tmp_path / "empty")


def test_delete_routine():
    routine = record_routine("temp", [RoutineStep(label="x", note="y")])
    assert delete_routine(routine.id) is True
    assert get_routine(routine.id) is None
    assert delete_routine(routine.id) is False


# ---------------------------------------------------------------------------
# Playback — rail + permission gates
# ---------------------------------------------------------------------------


def test_play_routine_dry_run_approved():
    routine = record_routine(
        "play me",
        [
            RoutineStep(
                label="step one", minion_id=_complete_minion_id(), event_summary="go"
            ),
            RoutineStep(label="just a note", note="remember this"),
        ],
    )
    run = play_routine(routine.id, responder=auto_approve, dry_run=True)
    assert run.ok
    assert run.dry_run is True
    assert len(run.receipts) == 1
    receipt = run.receipts[0]
    assert receipt.executed is False  # dry-run never executes
    assert receipt.dry_run is True
    assert any("note" in n for n in run.step_notes)
    assert get_routine(routine.id).playback_count == 1


def test_play_routine_denied_stops_fail_closed():
    routine = record_routine(
        "denied",
        [
            RoutineStep(
                label="step one", minion_id=_complete_minion_id(), event_summary="go"
            ),
            RoutineStep(
                label="step two", minion_id=_complete_minion_id(), event_summary="go"
            ),
        ],
    )
    run = play_routine(routine.id, responder=auto_deny, dry_run=True)
    assert not run.ok
    assert len(run.receipts) == 1  # second step never ran
    assert "fail-closed" in run.note
    assert get_routine(routine.id).playback_count == 0


def test_play_routine_live_executes_through_executor():
    routine = record_routine(
        "live?",
        [RoutineStep(label="s", minion_id=_complete_minion_id(), event_summary="go")],
    )
    run = play_routine(routine.id, responder=auto_approve, dry_run=False)
    assert run.ok
    receipt = run.receipts[0]
    assert receipt.dry_run is False
    # Live playback now routes through the executor: the first complete
    # minion has no webhook URL configured in the hermetic home, so the
    # device-artifact adapter generates install-ready artifacts.
    assert receipt.executed is True
    assert any(s.startswith("verify:") for s in receipt.steps)


def test_play_routine_unknown_id():
    with pytest.raises(KeyError):
        play_routine("nope", responder=auto_approve)


# ---------------------------------------------------------------------------
# Organism integration: manifest / warehouses / atlas / adapter
# ---------------------------------------------------------------------------


def test_automation_in_manifest():
    decl = DECLARATIONS["automation"]
    assert "automation.minions" in decl["provides"]
    assert "automation.engine" in decl["provides"]
    assert "automation.hitl" in decl["provides"]
    assert "automation.routines" in decl["provides"]
    assert "growth" in decl["requires"]  # session-harvest dependency


def test_manifest_deny_closed_with_automation():
    reg = Registry()
    for name, d in DECLARATIONS.items():
        reg.register(name, provides=d["provides"], requires=d["requires"])
    reg.check_all()
    reg.check("automation")


def test_automation_warehouse_shelves_it():
    wh = WAREHOUSES["automation"]
    assert wh["shelves"] == ["automation"]
    assert wh["strategy"] == "capabilities"
    browsed = browse_warehouse("automation")
    assert browsed["inventory_count"] == 5  # five declared capabilities
    provides = browsed["shelves"][0]["provides"]
    assert "automation.routines" in provides
    assert "automation.cli" in provides


def test_atlas_exposes_automation():
    atlas = export_atlas()
    mod = atlas["modules"]["automation"]
    assert mod["cli"] == ["automation"]
    assert "automation.routines" in atlas["capabilities"]
    assert "automation" in atlas["warehouses"]
    assert atlas["warehouses"]["automation"]["inventory_count"] == 5


def test_adapter_intent_to_catalog():
    minions = adapter.minions_for_intent("remind me to stretch every morning")
    assert isinstance(minions, list)
    assert all(not b.incomplete for b in minions)


def test_adapter_blank_intent_is_honest():
    assert adapter.minions_for_intent("") == []
    assert adapter.minions_for_intent("   ") == []
    assert adapter.preview_intent_runs("") == []


def test_adapter_preview_never_executes():
    receipts = adapter.preview_intent_runs(
        "remind me to stretch every morning", payload={"time": "06:45"}
    )
    assert receipts, "expected at least one preview receipt"
    for receipt in receipts:
        assert receipt.dry_run is True
        assert receipt.executed is False


def test_adapter_record_session_routine(tmp_path):
    sessions_dir = tmp_path / "sessions"
    _write_session(sessions_dir, name="watchme")
    routine = adapter.record_session_routine("watchme", sessions_dir=sessions_dir)
    assert routine.source == "session:watchme"


def test_adapter_record_session_routine_no_records(tmp_path):
    with pytest.raises(ValueError):
        adapter.record_session_routine("ghost")


def test_store_migrates_routines_json_to_rounds_json(tmp_path):
    from levi.automation.routines import _load_store, store_path

    home = tmp_path / "levi-home"
    auto = home / "automation"
    auto.mkdir(parents=True)
    old = auto / "routines.json"
    old.write_text('{"routines": [{"name": "x"}]}', encoding="utf-8")
    path = store_path(home)
    assert path.name == "rounds.json"
    assert not old.exists()
    assert _load_store(home)["routines"] == [{"name": "x"}]
