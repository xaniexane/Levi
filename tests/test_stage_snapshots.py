"""Tests for stage snapshots: engine, academy stages, ops-snapshot service."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from levi.snapshots import _seal
from levi.snapshots.stages import (
    StageError,
    StageStore,
    diff_stages,
)


@pytest.fixture()
def home(tmp_path):
    return tmp_path / "levihome"


@pytest.fixture()
def store(home):
    return StageStore(home=home)


def test_capture_round_trip(store):
    snap = store.capture_stage("v1", {"a": 1, "b": [1, 2]}, stage_label="v1")
    assert snap.id.startswith("stage_")
    assert snap.stage_label == "v1"
    assert store.materialize(snap.id) == {"a": 1, "b": [1, 2]}
    assert any(s.id == snap.id for s in store.list_stages())


def test_content_addressed_identical_payload(store):
    a = store.capture_stage("v1", {"x": 1})
    b = store.capture_stage("v1-again", {"x": 1})
    assert a.id == b.id  # identical payload = identical snapshot


def test_diff_detects_changes(store):
    a = store.capture_stage("a", {"keep": 1, "chg": 1, "gone": 2})
    b = store.capture_stage("b", {"keep": 1, "chg": 2, "new": 3})
    diffs = {d["path"]: d["kind"] for d in diff_stages(store, a.id, b.id)}
    assert diffs["chg"] == "changed"
    assert diffs["gone"] == "removed"
    assert diffs["new"] == "added"
    assert "keep" not in diffs


def test_diff_identical(store):
    a = store.capture_stage("a", {"x": 1})
    assert diff_stages(store, a.id, a.id) == []


def test_restore_writes_target(store, tmp_path):
    snap = store.capture_stage("v1", {"a": 1}, stage_label="v1")
    target = store.restore_stage(snap.id, tmp_path / "restored")
    payload = json.loads((target / "payload.json").read_text())
    assert payload == {"a": 1}
    manifest = json.loads((target / "manifest.json").read_text())
    assert manifest["snapshot_id"] == snap.id
    assert manifest["payload_hash"] == snap.payload_hash
    # Snapshot itself untouched.
    assert store.materialize(snap.id) == {"a": 1}


def test_fork_keeps_original_pristine(store):
    orig = store.capture_stage("orig", {"n": 1}, stage_label="v1")
    child = store.fork_stage(orig.id, "refined", stage_label="v2", note="improved")
    assert child.parent_id == orig.id
    assert child.id != orig.id
    assert store.materialize(orig.id) == {"n": 1}
    assert store.materialize(child.id) == {"n": 1}


def test_recreate_into_fresh_dir(store, tmp_path):
    snap = store.capture_stage("v1", {"a": 1})
    dest = store.recreate_stage(snap.id, tmp_path / "rebuilt")
    assert json.loads((dest / "payload.json").read_text()) == {"a": 1}
    with pytest.raises(StageError):
        store.recreate_stage(snap.id, tmp_path / "rebuilt")  # not empty


def test_implement_hands_payload_to_handler(store):
    snap = store.capture_stage("v1", {"kind": "demo", "v": 2})
    result = store.implement_stage(snap.id, lambda p: {"saw": p["v"]})
    assert result == {"saw": 2}
    with pytest.raises(StageError):
        store.implement_stage(snap.id, "not-callable")


def test_tampered_blob_detected(store):
    snap = store.capture_stage("v1", {"secret": "data"})
    blob = store.blobs / (snap.payload_hash + ".json")
    raw = blob.read_text()
    # Flip a character inside the ciphertext.
    tampered = raw.replace(raw[120], "A" if raw[120] != "A" else "B")
    blob.write_text(tampered)
    with pytest.raises(StageError):
        store.materialize(snap.id)
    with pytest.raises(StageError):
        store.verify_stage(snap.id)


def test_chain_verification(store):
    for i in range(3):
        store.capture_stage(f"s{i}", {"i": i})
    assert store.verify_chain() == 3


def test_chain_break_detected(store):
    a = store.capture_stage("a", {"i": 0})
    b = store.capture_stage("b", {"i": 1})
    # Tamper the index entry's chain MAC.
    lines = store.index_path.read_text().splitlines()
    rec = json.loads(lines[1])
    rec["chain_mac"] = "0" * 64
    lines[1] = json.dumps(rec)
    store.index_path.write_text("\n".join(lines) + "\n")
    with pytest.raises(StageError):
        store.verify_stage(b.id)
    with pytest.raises(StageError):
        store.verify_chain()
    # The untouched first snapshot still verifies.
    assert store.verify_stage(a.id).id == a.id


def test_unknown_snapshot_refused(store):
    with pytest.raises(StageError):
        store.materialize("stage_deadbeefdeadbeef")


def test_store_permissions(home):
    StageStore(home=home)
    root = home / "stage-snapshots"
    assert (root.stat().st_mode & 0o777) == 0o700
    assert ((root / "keeper.key").stat().st_mode & 0o777) == 0o600


def test_seal_round_trip_and_tamper(home):
    root = home / "stage-snapshots"
    root.mkdir(parents=True, exist_ok=True)
    key = _seal.keeper_key(root)
    env = _seal.seal_bytes(b"hello", key, "snapshots/stage")
    assert _seal.open_bytes(env, key, "snapshots/stage") == b"hello"
    env["ct"] = env["ct"][:-2] + ("AA" if not env["ct"].endswith("AA") else "BB")
    with pytest.raises(_seal.SealError):
        _seal.open_bytes(env, key, "snapshots/stage")


# -- academy stages -------------------------------------------------------


def test_academy_payload_collects(home):
    from levi.snapshots.stage_academy import collect_bootcamp_payload

    payload = collect_bootcamp_payload()
    assert payload["kind"] == "academy-bootcamp"
    assert payload["syllabus"] is not None  # real academy syllabus.json
    assert isinstance(payload["lessons"], list)
    assert len(payload["lessons"]) > 0


def test_bootcamp_stage_lifecycle(home, tmp_path):
    from levi.snapshots.stage_academy import (
        diff_bootcamp_stages,
        fork_bootcamp_stage,
        list_bootcamp_stages,
        restore_bootcamp_stage,
        snapshot_bootcamp,
    )

    a = snapshot_bootcamp("test-stage-a", note="t", home=home)
    b = snapshot_bootcamp("test-stage-b", note="t", home=home)
    assert a.id == b.id  # same academy content -> same snapshot
    listed = list_bootcamp_stages(home=home)
    assert any(s.id == a.id for s in listed)
    target = restore_bootcamp_stage(a.id, tmp_path / "bc", home=home)
    payload = json.loads((target / "payload.json").read_text())
    assert payload["kind"] == "academy-bootcamp"
    child = fork_bootcamp_stage(a.id, "test-stage-fork", home=home)
    assert child.parent_id == a.id
    assert diff_bootcamp_stages(a.id, child.id, home=home) == []


# -- ops-snapshot service --------------------------------------------------


def test_service_type_registered():
    from levi.services.offering import SERVICE_TYPES
    from levi.snapshots.stage_service import (
        SNAPSHOT_SERVICE_TYPE,
        register_snapshot_service_type,
    )

    register_snapshot_service_type()
    assert SNAPSHOT_SERVICE_TYPE in SERVICE_TYPES


def test_snapshot_quote_advice_band():
    from levi.snapshots.stage_service import advise_snapshot_quote

    advice = advise_snapshot_quote(giant_price=300.0, strategy="volume")
    # Doctrine: ~30-60% below the giant.
    assert 0.30 * 300.0 <= advice["recommended"] <= 0.60 * 300.0
    assert advice["low"] <= advice["recommended"] <= advice["high"]
    assert advice["receipt"]  # advisor receipt attached


def test_snapshot_service_pipeline(home, tmp_path):
    from levi.services.offering import ServiceStore
    from levi.snapshots.stage_service import (
        deliver_snapshot_service,
        offer_snapshot_service,
        quote_snapshot_service,
    )

    subject = tmp_path / "subject"
    subject.mkdir()
    (subject / "config.json").write_text('{"k": "v"}')
    (subject / "notes.md").write_text("# hello")

    offering = offer_snapshot_service(
        provider="levi",
        title="Snapshot test subject",
        subject=str(subject),
        client="test",
        home=home,
    )
    assert offering.stage == "offered"
    offering = quote_snapshot_service(offering, giant_price=300.0, home=home)
    assert offering.stage == "quoted"
    receipt = deliver_snapshot_service(
        offering, subject_dir=subject, stage_label="v1-test", home=home
    )
    assert receipt["snapshot_id"].startswith("stage_")
    assert receipt["chain_verified"] >= 1
    assert "restore" in receipt and "fork" in receipt
    final = ServiceStore(home=home).get(offering.offering_id)
    assert final.stage == "delivered"
    assert any("snapshot-receipt" in h["event"] for h in final.history)


def test_snapshot_cli_list_smoke(home, tmp_path, capsys, monkeypatch):
    import argparse

    from levi.snapshots.stage_cli import cmd_snapshot
    from levi.snapshots.stages import StageStore as _SS

    monkeypatch.setenv("LEVI_HOME", str(home))
    _SS(home=home).capture_stage("cli-test", {"a": 1})
    args = argparse.Namespace(snapshot_cmd="list", home=str(home))
    assert cmd_snapshot(args) == 0
    out = capsys.readouterr().out
    assert "cli-test" in out

    args = argparse.Namespace(snapshot_cmd="verify", snapshot_id=None, home=str(home))
    assert cmd_snapshot(args) == 0
    assert "chain OK" in capsys.readouterr().out
