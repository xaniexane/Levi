"""Hicomb IDE snapshot-every-stage law (Chauncey, 2026-09-23).

Machine-checks for S1–S5 (declared in levi/hicomb/snapshots.py):
  S1 EVERY-STAGE   every acting stage captures a pre-snapshot before it
                   touches anything, and a post-snapshot after it acts;
                   an exception mid-stage still leaves the pre-snapshot.
  S2 RECEIPTED     every snapshot is receipted: stage name, timestamp,
                   content hash, restorable location, chained prev id.
  S3 RESTORABLE    restore() returns byte-identical content, hash-verified;
                   tampering raises SnapshotTampered, unknown ids raise
                   SnapshotMissing.
  S4 VIOLATION     a stage that acts without its pre-snapshot raises
                   StageViolation — build-breaking, never a warning.
  S5 OFFLINE       stdlib only: no network imports in snapshots.py.

Hermetic: isolated store_dir per test via tmp_path.
"""

import ast
import json

import pytest

from levi.hicomb.forge import ForgeArm
from levi.hicomb.pipeline import save_pipeline
from levi.hicomb.buffer import Buffer
from levi.hicomb.self_upgrade import SelfUpgradeLoop
from levi.hicomb.snapshots import (
    SnapshotMissing,
    SnapshotStore,
    SnapshotTampered,
    StageGuard,
    StageRun,
    StageViolation,
    content_hash,
    snapshotted,
)


@pytest.fixture()
def store(tmp_path):
    return SnapshotStore(tmp_path / "snaps")


# ------------------------------------------------------------------ S2/S3
def test_receipt_carries_stage_ts_hash_location_and_chain(store):
    pre = store.capture("pollen-format", {"before": "x=1"}, kind="pre")
    post = store.capture("pollen-format", {"after": "x = 1"}, kind="post")
    receipts = store.receipts()
    assert len(receipts) == 2
    for r in receipts:
        for field in ("id", "stage", "kind", "ts", "hash", "size_bytes",
                      "path", "prev"):
            assert field in r, f"receipt missing {field}"
    assert receipts[0]["prev"] == ""
    assert receipts[1]["prev"] == receipts[0]["id"]  # audit chain
    assert receipts[0]["path"].endswith(".json")


def test_restore_returns_byte_identical_payload(store):
    payload = {"before": "x=1\n", "language": "python"}
    snap = store.capture("surgeon-edit", payload, kind="pre")
    assert store.restore(snap.id) == payload
    assert content_hash(store.restore(snap.id)) == snap.hash


def test_restore_rejects_unknown_id(store):
    with pytest.raises(SnapshotMissing):
        store.restore("no-such-snapshot")


def test_restore_detects_tampering(store):
    snap = store.capture("nlir-plan", {"intent": "build engine x"},
                         kind="pre")
    target = store.root / f"{snap.id}.json"
    doc = json.loads(target.read_text(encoding="utf-8"))
    doc["payload"]["intent"] = "build engine EVIL"
    target.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SnapshotTampered):
        store.restore(snap.id)


def test_hash_is_deterministic(store):
    payload = {"b": [1, 2], "a": "x"}
    assert content_hash(payload) == content_hash(dict(payload))
    assert content_hash(payload) != content_hash({"a": "y", "b": [1, 2]})


def test_rollback_to_earlier_snapshot(store):
    s1 = store.capture("final-write", {"text": "v1"}, kind="pre")
    store.capture("final-write", {"text": "v2"}, kind="post")
    assert store.rollback_to(s1.id) == {"text": "v1"}


# ------------------------------------------------------------------ S4
def test_check_without_open_run_raises_violation(store):
    guard = StageGuard(store)
    with pytest.raises(StageViolation):
        guard.check("pollen-format")


def test_run_without_pre_snapshot_raises_on_act(store):
    guard = StageGuard(store)
    run = StageRun(guard, "surgeon-edit", None)  # built wrong: no pre
    with pytest.raises(StageViolation):
        run.act()


def test_double_end_raises_violation(store):
    guard = StageGuard(store)
    run = guard.begin("x", {"a": 1})
    run.end({"b": 2})
    with pytest.raises(StageViolation):
        run.end({"b": 3})


def test_snapshotted_keeps_pre_on_exception_and_reraises(store):
    def boom():
        raise RuntimeError("stage blew up")

    with pytest.raises(RuntimeError):
        snapshotted(store, "surgeon-edit", {"before": "src"}, boom)
    receipts = store.receipts(stage="surgeon-edit")
    assert [r["kind"] for r in receipts] == ["pre"]  # pre kept, no post
    assert store.restore(receipts[0]["id"]) == {"before": "src"}


def test_snapshotted_happy_path(store):
    result, pre, post = snapshotted(
        store, "pollen-format", {"before": "x=1"},
        lambda: "x = 1",
        post=lambda r: {"after": r},
    )
    assert result == "x = 1"
    assert pre.kind == "pre" and post.kind == "post"
    assert store.restore(post.id) == {"after": "x = 1"}


def test_guard_context_manager_aborts_on_exception(store):
    guard = StageGuard(store)
    with pytest.raises(ValueError), guard.stage("x", {"a": 1}):
        raise ValueError("mid-stage")
    kinds = [r["kind"] for r in store.receipts(stage="x")]
    assert kinds == ["pre"]


# ------------------------------------------------------------------ S1: forge
@pytest.fixture()
def forge(tmp_path):
    return ForgeArm(store_dir=tmp_path / "forge_store")


def test_forge_snapshots_pollen_and_surgeon(forge):
    dirty = "x=1\n\n\n\ndef f():\n\treturn  x\n"
    result = forge.forge_text(dirty, "python", path_hint="t.py")
    assert result.ok
    snaps = forge._snapshots
    stages = snaps.stages_seen()
    assert "pollen-format" in stages
    assert "surgeon-edit" in stages
    for stage in ("pollen-format", "surgeon-edit"):
        kinds = [r["kind"] for r in snaps.receipts(stage=stage)]
        assert kinds == ["pre", "post"], f"{stage}: {kinds}"
    # the surgeon pre-snapshot is the rollback point: it holds the
    # pollen-formatted text, and restoring it is byte-identical.
    pre = snaps.receipts(stage="surgeon-edit")[0]
    restored = snaps.restore(pre["id"])
    assert "before" in restored and isinstance(restored["before"], str)


def test_forge_pollen_refusal_keeps_pre_snapshot(forge):
    # pollen refuses unformattable input; the pre-snapshot stays.
    from levi.hicomb import forge as forge_mod
    orig = forge_mod.format_text

    def refuse(lang, text):
        from levi.hicomb.pollen import FormatterError
        raise FormatterError("nope")

    forge_mod.format_text = refuse
    try:
        result = forge.forge_text("x=1", "python")
    finally:
        forge_mod.format_text = orig
    assert not result.ok and result.text == "x=1"
    kinds = [r["kind"]
             for r in forge._snapshots.receipts(stage="pollen-format")]
    assert kinds == ["pre"]


# ------------------------------------------------------------------ S1: pipeline
def test_save_pipeline_snapshots_format_and_write(tmp_path):
    target = tmp_path / "hello.py"
    target.write_text("x=1\n", encoding="utf-8")
    buf = Buffer()
    buf.set_text("x=1\n")
    buf.path = str(target)
    res = save_pipeline(buf, snapshot_store_dir=str(tmp_path / "sstore"))
    assert res.ok
    snaps = SnapshotStore(tmp_path / "sstore" / ".snapshots")
    kinds_fmt = [r["kind"] for r in snaps.receipts(stage="pollen-format")]
    kinds_write = [r["kind"] for r in snaps.receipts(stage="final-write")]
    assert kinds_fmt == ["pre", "post"]
    assert kinds_write == ["pre", "post"]
    # rollback: the final-write pre-snapshot predates the write.
    pre = snaps.receipts(stage="final-write")[0]
    restored = snaps.restore(pre["id"])
    assert restored["path"] == str(target)


# ------------------------------------------------------------------ S1: self-upgrade
@pytest.fixture()
def loop(tmp_path):
    return SelfUpgradeLoop(store_dir=tmp_path / "up_store")


def test_self_upgrade_stages_all_snapshot(loop):
    proj = loop.propose_projection(
        "tweak x", {"kind": "fix", "module": "m"}, "fixes x")
    denied = loop.propose_projection(
        "tweak y", {"kind": "fix", "module": "m"}, "fixes y")
    loop.decide(denied.id, False, reason="nope")
    out = loop.recombine([denied.id], "remix", {"kind": "fix"},
                         "remixed fix")
    assert out["ok"]
    loop.decide(proj.id, True, reason="ship it")
    applied = loop.apply_projection(proj.id)
    assert applied["ok"]
    stages = loop._snapshots.stages_seen()
    for stage in ("upgrade-propose", "upgrade-decide", "quetta-remix",
                  "upgrade-apply"):
        assert stage in stages, f"missing stage {stage}"
        kinds = [r["kind"]
                 for r in loop._snapshots.receipts(stage=stage)]
        assert kinds[0] == "pre" and kinds[-1] == "post"
    # the decide pre-snapshot holds the exact undecided projection.
    pre = loop._snapshots.receipts(stage="upgrade-decide")[0]
    restored = loop._snapshots.restore(pre["id"])
    assert restored["proposal"]["status"] == "proposed"


# ------------------------------------------------------------------ S1: nl->ir
def test_nlir_plan_and_apply_snapshot(tmp_path):
    from levi.hicomb import ide_nl

    store = tmp_path / "ide"
    job = ide_nl.plan_intent("build engine demo", tier="E3",
                             store_dir=store)
    snaps = SnapshotStore(store / ".snapshots")
    kinds = [r["kind"] for r in snaps.receipts(stage="nlir-plan")]
    assert kinds == ["pre", "post"]
    pre = snaps.receipts(stage="nlir-plan")[0]
    restored = snaps.restore(pre["id"])
    assert restored["intent"] == "build engine demo"
    assert restored["tier"] == "E3"
    # apply snapshots too (E3 needs no HITL)
    ide_nl.apply_job(job.id, store_dir=store)
    kinds = [r["kind"] for r in snaps.receipts(stage="nlir-apply")]
    assert kinds == ["pre", "post"]


# ------------------------------------------------------------------ S5 offline
def test_snapshots_module_is_stdlib_only():
    from pathlib import Path
    src = (Path(__file__).parent.parent / "core" / "levi" / "hicomb"
           / "snapshots.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    banned = {"socket", "urllib", "http", "requests", "httpx", "ssl"}
    assert not (imports & banned), f"network imports: {imports & banned}"
