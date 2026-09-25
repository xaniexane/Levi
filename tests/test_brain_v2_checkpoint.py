"""Hermetic tests for levi.brain.train.v2.checkpoint (numpy only, no torch)."""

import json

import numpy as np
import pytest

from levi.brain.train.v2 import checkpoint as ckpt
from levi.brain.train.v2.checkpoint import CheckpointError


def _arrays(n=3):
    rng = np.random.default_rng(0)
    return {f"layer{i}.w": rng.normal(size=(4, 4)).astype(np.float32) for i in range(n)}


def test_save_and_load_roundtrip(tmp_path):
    arrays = _arrays()
    path = ckpt.save_checkpoint(
        tmp_path,
        step=100,
        arrays=arrays,
        metrics={"loss": 2.5},
        config_hash="abc123",
    )
    assert path.name == "ckpt-000100.npz"
    loaded = ckpt.load_checkpoint(path)
    assert loaded["step"] == 100
    assert loaded["metrics"] == {"loss": 2.5}
    assert loaded["config_hash"] == "abc123"
    for k, v in arrays.items():
        np.testing.assert_array_equal(loaded["arrays"][k], v)


def test_manifest_records_steps_and_hashes(tmp_path):
    ckpt.save_checkpoint(tmp_path, step=10, arrays=_arrays(), metrics={"loss": 3.0})
    ckpt.save_checkpoint(tmp_path, step=20, arrays=_arrays(), metrics={"loss": 2.0})
    entries = ckpt.list_checkpoints(tmp_path)
    assert [e["step"] for e in entries] == [10, 20]
    assert all(len(e["sha256"]) == 64 for e in entries)
    assert all(e["bytes"] > 0 for e in entries)
    manifest = json.loads((tmp_path / "checkpoints.json").read_text())
    assert len(manifest) == 2


def test_latest_checkpoint_skips_missing_files(tmp_path):
    p1 = ckpt.save_checkpoint(tmp_path, step=10, arrays=_arrays())
    ckpt.save_checkpoint(tmp_path, step=20, arrays=_arrays())
    p1.unlink()  # simulate a lost file
    assert ckpt.latest_checkpoint(tmp_path).name == "ckpt-000020.npz"


def test_latest_none_when_empty(tmp_path):
    assert ckpt.latest_checkpoint(tmp_path) is None
    assert ckpt.resume_from_latest(tmp_path) is None


def test_resume_from_latest_reports_config_mismatch(tmp_path):
    ckpt.save_checkpoint(tmp_path, step=5, arrays=_arrays(), config_hash="hash-a")
    resumed = ckpt.resume_from_latest(tmp_path, expected_config_hash="hash-b")
    assert resumed["step"] == 5
    assert resumed["config_mismatch"] is True
    ok = ckpt.resume_from_latest(tmp_path, expected_config_hash="hash-a")
    assert ok["config_mismatch"] is False


def test_prune_keeps_last_n(tmp_path):
    for step in (10, 20, 30, 40):
        ckpt.save_checkpoint(tmp_path, step=step, arrays=_arrays(), keep_last=10)
    removed = ckpt.prune_checkpoints(tmp_path, keep_last=2)
    assert {p.name for p in removed} == {"ckpt-000010.npz", "ckpt-000020.npz"}
    entries = ckpt.list_checkpoints(tmp_path)
    assert [e["step"] for e in entries] == [30, 40]
    assert ckpt.latest_checkpoint(tmp_path).name == "ckpt-000040.npz"


def test_save_auto_prunes(tmp_path):
    for step in (10, 20, 30):
        ckpt.save_checkpoint(tmp_path, step=step, arrays=_arrays(), keep_last=2)
    assert [e["step"] for e in ckpt.list_checkpoints(tmp_path)] == [20, 30]


def test_prune_rejects_zero(tmp_path):
    with pytest.raises(CheckpointError, match="keep_last"):
        ckpt.prune_checkpoints(tmp_path, keep_last=0)


def test_tampered_file_refused(tmp_path):
    path = ckpt.save_checkpoint(tmp_path, step=10, arrays=_arrays())
    with open(path, "r+b") as fh:
        fh.seek(100)
        fh.write(b"\x00\x01\x02\x03")
    # Either the sha256 check or the npz parse must refuse the tampered file.
    with pytest.raises(CheckpointError):
        ckpt.load_checkpoint(path)


def test_manifest_hash_mismatch_refused(tmp_path):
    import json as _json

    path = ckpt.save_checkpoint(tmp_path, step=10, arrays=_arrays())
    manifest_path = tmp_path / "checkpoints.json"
    entries = _json.loads(manifest_path.read_text(encoding="utf-8"))
    entries[0]["sha256"] = "0" * 64  # lie about the recorded hash
    manifest_path.write_text(_json.dumps(entries), encoding="utf-8")
    with pytest.raises(CheckpointError, match="sha256 mismatch"):
        ckpt.load_checkpoint(path)


def test_corrupt_npz_refused(tmp_path):
    path = ckpt.save_checkpoint(tmp_path, step=10, arrays=_arrays())
    path.write_bytes(b"not a numpy file at all")
    # Manifest hash no longer matches either; either error is a refusal.
    with pytest.raises(CheckpointError):
        ckpt.load_checkpoint(path)


def test_missing_checkpoint_load(tmp_path):
    with pytest.raises(CheckpointError, match="not found"):
        ckpt.load_checkpoint(tmp_path / "ckpt-000999.npz")


def test_negative_step_rejected(tmp_path):
    with pytest.raises(CheckpointError, match="step"):
        ckpt.save_checkpoint(tmp_path, step=-1, arrays=_arrays())


def test_load_without_manifest_still_works(tmp_path):
    path = ckpt.save_checkpoint(tmp_path, step=42, arrays=_arrays())
    (tmp_path / "checkpoints.json").unlink()
    loaded = ckpt.load_checkpoint(path)
    assert loaded["step"] == 42  # falls back to the __step__ marker
    assert loaded["metrics"] == {}


def test_torch_bridge_roundtrip():
    torch = pytest.importorskip("torch", reason="torch not installed")
    sd = {"w": torch.randn(3, 3), "b": torch.zeros(3, dtype=torch.float64)}
    arrays = ckpt.torch_state_dict_to_numpy(sd)
    assert arrays["w"].dtype == np.float32
    back = ckpt.numpy_to_torch_state_dict(arrays, sd)
    assert back["w"].dtype == torch.float32
    assert back["b"].dtype == torch.float64
    torch.testing.assert_close(back["w"], sd["w"])


def test_torch_bridge_rejects_non_tensor():
    torch = pytest.importorskip("torch", reason="torch not installed")
    with pytest.raises(CheckpointError, match="not a Tensor"):
        ckpt.torch_state_dict_to_numpy({"w": torch.randn(2), "lr": 0.1})


def test_torch_bridge_rejects_missing_key():
    torch = pytest.importorskip("torch", reason="torch not installed")
    sd = {"w": torch.randn(2)}
    with pytest.raises(CheckpointError, match="missing parameter"):
        ckpt.numpy_to_torch_state_dict({}, sd)


# --- keep_best: the run never deletes its own best self ---


def test_keep_best_protects_lowest_nll_outside_window(tmp_path):
    nlls = {100: 5.0, 200: 4.0, 300: 4.5, 400: 4.2, 500: 4.8, 600: 5.2}
    for step, nll in nlls.items():
        ckpt.save_checkpoint(
            tmp_path,
            step=step,
            arrays=_arrays(),
            metrics={"loss": 2.0, "held_out_nll": nll},
            keep_last=3,
            keep_best=True,
        )
    remaining = {e["step"] for e in ckpt.list_checkpoints(tmp_path)}
    assert 200 in remaining  # best survives outside the keep_last window
    assert remaining == {200, 400, 500, 600}


def test_keep_best_false_restores_legacy_prune(tmp_path):
    # Best (step 100) is the oldest: legacy pruning deletes it like anything else.
    for step in (100, 200, 300, 400):
        ckpt.save_checkpoint(
            tmp_path,
            step=step,
            arrays=_arrays(),
            metrics={"held_out_nll": 4.0 + step / 1000.0},
            keep_last=2,
            keep_best=False,
        )
    assert [e["step"] for e in ckpt.list_checkpoints(tmp_path)] == [300, 400]


def test_best_held_out_entry_selects_minimum(tmp_path):
    ckpt.save_checkpoint(
        tmp_path, step=100, arrays=_arrays(), metrics={"held_out_nll": 5.0}
    )
    ckpt.save_checkpoint(
        tmp_path, step=200, arrays=_arrays(), metrics={"held_out_nll": 4.0}
    )
    ckpt.save_checkpoint(
        tmp_path, step=300, arrays=_arrays(), metrics={"held_out_nll": 4.5}
    )
    best = ckpt.best_held_out_entry(tmp_path)
    assert best is not None and best["step"] == 200
    assert best["metrics"]["held_out_nll"] == 4.0


def test_best_held_out_entry_none_without_evidence(tmp_path):
    ckpt.save_checkpoint(
        tmp_path, step=100, arrays=_arrays(), metrics={"loss": 1.0}
    )
    assert ckpt.best_held_out_entry(tmp_path) is None


def test_best_held_out_entry_ignores_missing_files(tmp_path):
    p = ckpt.save_checkpoint(
        tmp_path, step=100, arrays=_arrays(), metrics={"held_out_nll": 4.0}
    )
    ckpt.save_checkpoint(
        tmp_path, step=200, arrays=_arrays(), metrics={"held_out_nll": 5.0}
    )
    p.unlink()  # the recorded best is gone from disk: fall back honestly
    best = ckpt.best_held_out_entry(tmp_path)
    assert best is not None and best["step"] == 200
