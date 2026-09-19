"""v2 checkpointing: atomic writes, manifest with step/loss/config hash.

Checkpoints are stored as compressed numpy ``.npz`` files holding a dict of
weight arrays (plus metrics/scalars), so this module never needs torch at
import time. Convert to/from torch at the edges with
:func:`torch_state_dict_to_numpy` / :func:`numpy_to_torch_state_dict`.

Every save is atomic (temp file + fsync + os.replace) and recorded in
``checkpoints.json`` (the manifest). Crash mid-write leaves either the old
or the new file intact — never a half-written checkpoint.

Manifest entry schema::

    {"step": 500, "file": "ckpt-000500.npz", "sha256": "...",
     "bytes": 123456, "config_hash": "...",
     "metrics": {"loss": 2.31, "held_out_nll": 4.12},
     "saved_at": "2026-09-15T21:00:00Z"}

``metrics.held_out_nll`` (recorded when the trainer has run an eval)
is the checkpoint's held-out evidence; the lowest-NLL entry is the
run's best self and is protected from pruning (see ``keep_best``).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

MANIFEST_NAME = "checkpoints.json"


class CheckpointError(RuntimeError):
    """Checkpoint save/load/resume failed."""


# ---------------------------------------------------------------------------
# Writing (atomic)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write bytes atomically: temp file in the same dir, fsync, rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".tmp.")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_checkpoint(
    ckpt_dir: str | Path,
    *,
    step: int,
    arrays: Mapping[str, np.ndarray],
    metrics: Mapping[str, float] | None = None,
    config_hash: str = "",
    keep_last: int = 5,
    keep_best: bool = True,
) -> Path:
    """Save a checkpoint atomically and record it in the manifest.

    Returns the final checkpoint path. Prunes older checkpoints to
    ``keep_last`` after saving — but never prunes the best-held-out
    checkpoint (``keep_best``): the run's best self is never deleted,
    no matter how many newer, worse checkpoints follow it.
    """
    if step < 0:
        raise CheckpointError(f"step must be >= 0, got {step}")
    ckpt_dir = Path(ckpt_dir)
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    name = f"ckpt-{step:06d}.npz"
    path = ckpt_dir / name

    # npz only stores arrays: the step is packed as an internal marker array;
    # metrics / config hash live in the JSON manifest, not in the .npz.
    npz_arrays = dict(arrays)
    npz_arrays["__step__"] = np.asarray(step, dtype=np.int64)

    fd, tmp = tempfile.mkstemp(dir=str(ckpt_dir), prefix=name + ".tmp.")
    try:
        with os.fdopen(fd, "wb") as fh:
            np.savez_compressed(fh, **npz_arrays)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise CheckpointError(f"failed to write checkpoint {path}") from None

    entry = {
        "step": step,
        "file": name,
        "sha256": _sha256_file(path),
        "bytes": path.stat().st_size,
        "config_hash": config_hash,
        "metrics": dict(metrics or {}),
        "saved_at": _utcnow(),
    }
    _append_manifest_entry(ckpt_dir, entry)
    protect: set[str] = set()
    if keep_best:
        best = best_held_out_entry(ckpt_dir)
        if best is not None:
            protect.add(best["file"])
    prune_checkpoints(ckpt_dir, keep_last, protect=protect)
    return path


def _append_manifest_entry(ckpt_dir: Path, entry: dict) -> None:
    manifest_path = ckpt_dir / MANIFEST_NAME
    entries: list[dict] = []
    if manifest_path.is_file():
        try:
            entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            entries = []
        if not isinstance(entries, list):
            entries = []
    entries = [e for e in entries if e.get("file") != entry["file"]]
    entries.append(entry)
    entries.sort(key=lambda e: e.get("step", 0))
    data = json.dumps(entries, indent=2, sort_keys=True).encode("utf-8")
    _atomic_write_bytes(manifest_path, data)


# ---------------------------------------------------------------------------
# Reading / resuming


def list_checkpoints(ckpt_dir: str | Path) -> list[dict]:
    """Manifest entries sorted by step ascending. Missing/corrupt -> []."""
    manifest_path = Path(ckpt_dir) / MANIFEST_NAME
    if not manifest_path.is_file():
        return []
    try:
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(entries, list):
        return []
    return sorted(entries, key=lambda e: e.get("step", 0))


def latest_checkpoint(ckpt_dir: str | Path) -> Path | None:
    """Path of the newest checkpoint whose file actually exists on disk."""
    ckpt_dir = Path(ckpt_dir)
    for entry in reversed(list_checkpoints(ckpt_dir)):
        path = ckpt_dir / entry.get("file", "")
        if path.is_file():
            return path
    return None


def load_checkpoint(path: str | Path) -> dict:
    """Load a checkpoint file. Verifies the sha256 against the manifest.

    Returns ``{"step", "arrays", "metrics", "config_hash", "sha256"}``.
    Arrays exclude the internal ``__step__`` marker.
    """
    path = Path(path)
    if not path.is_file():
        raise CheckpointError(f"checkpoint not found: {path}")
    try:
        with np.load(path, allow_pickle=False) as zf:
            arrays = {k: zf[k] for k in zf.files if k != "__step__"}
            step = int(zf["__step__"]) if "__step__" in zf.files else -1
    except Exception as exc:
        raise CheckpointError(f"checkpoint {path} is unreadable: {exc}") from exc

    entry = next(
        (e for e in list_checkpoints(path.parent) if e.get("file") == path.name),
        None,
    )
    if entry is not None:
        actual = _sha256_file(path)
        if actual != entry.get("sha256"):
            raise CheckpointError(
                f"checkpoint {path} sha256 mismatch: manifest says "
                f"{entry.get('sha256')}, file is {actual} — file is corrupt "
                "or was tampered with; refusing to load"
            )
        return {
            "step": entry.get("step", step),
            "arrays": arrays,
            "metrics": entry.get("metrics", {}),
            "config_hash": entry.get("config_hash", ""),
            "sha256": actual,
        }
    return {
        "step": step,
        "arrays": arrays,
        "metrics": {},
        "config_hash": "",
        "sha256": _sha256_file(path),
    }


def resume_from_latest(
    ckpt_dir: str | Path, *, expected_config_hash: str = ""
) -> dict | None:
    """Return the latest checkpoint dict, or None if there is nothing.

    If ``expected_config_hash`` is given and differs from the checkpoint's,
    the checkpoint is still returned but the mismatch is reported in
    ``"config_mismatch"`` — the caller decides whether to continue, because
    silently resuming under a different config would corrupt the run.
    """
    path = latest_checkpoint(ckpt_dir)
    if path is None:
        return None
    ckpt = load_checkpoint(path)
    ckpt["path"] = str(path)
    ckpt["config_mismatch"] = bool(
        expected_config_hash and ckpt["config_hash"] != expected_config_hash
    )
    return ckpt


# ---------------------------------------------------------------------------
# Pruning


def best_held_out_entry(ckpt_dir: str | Path) -> dict | None:
    """Manifest entry with the lowest held-out NLL — the run's best self.

    Entries without a recorded ``metrics.held_out_nll`` are ignored.
    Returns None when no entry has held-out evidence yet.
    """
    ckpt_dir = Path(ckpt_dir)
    scored = [
        e
        for e in list_checkpoints(ckpt_dir)
        if isinstance(e.get("metrics"), dict)
        and e["metrics"].get("held_out_nll") is not None
        and (ckpt_dir / e.get("file", "")).is_file()
    ]
    if not scored:
        return None
    return min(scored, key=lambda e: (e["metrics"]["held_out_nll"], e.get("step", 0)))


def prune_checkpoints(
    ckpt_dir: str | Path,
    keep_last: int,
    protect: Iterable[str] = (),
) -> list[Path]:
    """Delete all but the ``keep_last`` newest checkpoints. Returns removed.

    ``protect`` holds checkpoint filenames that must survive pruning (the
    best-held-out checkpoint). Protected files are also kept in the manifest
    so the record reflects the disk.
    """
    if keep_last < 1:
        raise CheckpointError(f"keep_last must be >= 1, got {keep_last}")
    ckpt_dir = Path(ckpt_dir)
    protect = set(protect)
    existing = [
        e
        for e in reversed(list_checkpoints(ckpt_dir))
        if (ckpt_dir / e.get("file", "")).is_file()
    ]
    removed: list[Path] = []
    for entry in existing[keep_last:]:
        if entry["file"] in protect:
            continue
        path = ckpt_dir / entry["file"]
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            pass
    removed_files = {p.name for p in removed}
    # Drop pruned entries from the manifest so it reflects disk.
    kept_files = {e["file"] for e in existing[:keep_last]} | {
        e["file"]
        for e in existing
        if e["file"] in protect and e["file"] not in removed_files
    }
    manifest_path = ckpt_dir / MANIFEST_NAME
    entries = [e for e in list_checkpoints(ckpt_dir) if e.get("file") in kept_files]
    _atomic_write_bytes(
        manifest_path, json.dumps(entries, indent=2, sort_keys=True).encode()
    )
    return removed


# ---------------------------------------------------------------------------
# torch bridge (optional; only imported when used)


def torch_state_dict_to_numpy(state_dict: Mapping[str, Any]) -> dict[str, np.ndarray]:
    """Convert a torch state_dict to numpy arrays for checkpointing."""
    import torch

    out: dict[str, np.ndarray] = {}
    for key, value in state_dict.items():
        if isinstance(value, torch.Tensor):
            out[key] = value.detach().cpu().numpy()
        else:
            raise CheckpointError(
                f"state_dict['{key}'] is {type(value).__name__}, not a Tensor"
            )
    return out


def numpy_to_torch_state_dict(
    arrays: Mapping[str, np.ndarray], template: Mapping[str, Any]
) -> dict[str, Any]:
    """Rebuild a torch state_dict, casting arrays to the template dtypes."""
    import torch

    out: dict[str, Any] = {}
    for key, tmpl in template.items():
        if key not in arrays:
            raise CheckpointError(f"checkpoint is missing parameter '{key}'")
        arr = arrays[key]
        t = torch.from_numpy(np.asarray(arr))
        if isinstance(tmpl, torch.Tensor) and t.dtype != tmpl.dtype:
            t = t.to(tmpl.dtype)
        out[key] = t
    extra = set(arrays) - set(template)
    if extra:
        raise CheckpointError(f"checkpoint has unexpected parameters: {sorted(extra)}")
    return out
