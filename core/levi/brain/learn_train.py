"""Learning-loop retraining job: corpus -> candidate weights (staged).

The candidate is ALWAYS trained into a staging directory, never into the
live weights dir — promotion is a separate, eval-gated step. Staging is
idempotent: a staging dir whose manifest matches the corpus id is reused
instead of retraining (restartable without wasted work); ``force=True``
retrains from scratch.

The default trainer is the existing ``train/train.py`` invoked as a
subprocess (``--data/--steps/--out/--seed``), which gives a real wall-clock
watchdog via ``subprocess`` timeout. Tests inject ``train_fn`` instead —
no torch, no subprocess, no waiting.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from levi.brain.learn_corpus import BrainLoopError

TRAINER_REL = Path("core") / "levi" / "brain" / "train" / "train.py"


def torch_available() -> bool:
    try:
        import torch  # noqa: F401
    except Exception:
        return False
    return True


def repo_root(start: Optional[Path] = None) -> Path:
    """Best-effort repo root: walk up from ``start`` until ``core/levi``
    exists, else fall back to the current working directory."""
    here = Path(start) if start is not None else Path.cwd()
    for cand in (here, *here.parents):
        if (cand / "core" / "levi").is_dir():
            return cand
    return Path.cwd()


def calibration_path(loop_dir: Path) -> Path:
    return Path(loop_dir) / "calibration.json"


def load_calibration(loop_dir: Path) -> Dict[str, Any]:
    p = calibration_path(loop_dir)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_calibration(loop_dir: Path, entry: Dict[str, Any]) -> None:
    Path(loop_dir).mkdir(parents=True, exist_ok=True)
    calibration_path(loop_dir).write_text(json.dumps(entry, indent=1), encoding="utf-8")


def estimate_cost(
    *,
    corpus_chars: int,
    steps: int,
    params: Optional[int] = None,
    max_seconds: int = 3600,
    calibration: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Honest pre-training cost estimate, logged before every run.

    ``est_seconds`` is only populated when calibration data exists (chars
    per second measured from a previous real training run); otherwise it
    is None and the report says so plainly. The run is always bounded by
    ``max_steps`` and the ``max_seconds`` watchdog regardless.
    """
    cal = calibration or {}
    chars_per_sec = cal.get("chars_per_sec")
    est_seconds: Optional[float] = None
    if isinstance(chars_per_sec, (int, float)) and chars_per_sec > 0:
        # Rough: work scales with steps * corpus passes; calibration
        # measured seconds per (step * 1k chars).
        est_seconds = round(steps * (corpus_chars / 1000.0) / chars_per_sec, 1)
    return {
        "steps": steps,
        "corpus_chars": corpus_chars,
        "params": params,
        "max_seconds": max_seconds,
        "calibrated": est_seconds is not None,
        "est_seconds": est_seconds,
        "note": (
            "calibrated estimate from previous run"
            if est_seconds is not None
            else "no calibration data — first run is uncalibrated; "
            "bounded by max_steps and the max_seconds watchdog"
        ),
    }


def _default_train_fn(
    *,
    data: Path,
    steps: int,
    out_dir: Path,
    seed: int,
    batch_size: int,
    lr: float,
    timeout: int,
    repo: Path,
    device: str = "auto",
) -> Dict[str, Any]:
    """Run the existing trainer as a subprocess with a wall-clock watchdog."""
    if not torch_available():
        raise BrainLoopError(
            "retrain: torch is not installed — the candidate can only be "
            "trained in the training environment. Observations are still "
            "being recorded; run the loop where torch is available."
        )
    trainer = repo / TRAINER_REL
    if not trainer.is_file():
        raise BrainLoopError(f"retrain: trainer not found at {trainer}")
    cmd = [
        sys.executable,
        str(trainer),
        "--data",
        str(data),
        "--steps",
        str(steps),
        "--out",
        str(out_dir),
        "--seed",
        str(seed),
        "--device",
        device,
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise BrainLoopError(
            f"retrain: trainer exceeded the {timeout}s watchdog and was "
            "killed — no candidate produced"
        ) from exc
    seconds = round(time.time() - t0, 1)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-2000:]
        raise BrainLoopError(
            f"retrain: trainer failed (exit {proc.returncode}): {tail}"
        )
    weights_pt = out_dir / "tiny-gpt.pt"
    train_log = out_dir / "train_log.json"
    if not weights_pt.is_file():
        raise BrainLoopError("retrain: trainer exited 0 but wrote no tiny-gpt.pt")
    log: Dict[str, Any] = {}
    if train_log.is_file():
        try:
            log = json.loads(train_log.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            log = {}
    log["wall_seconds"] = seconds
    return {"weights_pt": str(weights_pt), "train_log": log, "seconds": seconds}


def staging_manifest(staging_dir: Path) -> Dict[str, Any]:
    p = Path(staging_dir) / "stage_manifest.json"
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def run_retrain(
    *,
    train_jsonl: Path,
    corpus_id: str,
    corpus_chars: int,
    staging_root: Path,
    loop_dir: Path,
    steps: int,
    seed: int,
    batch_size: int = 32,
    lr: float = 3e-4,
    max_seconds: int = 3600,
    weights_dir: Optional[Path] = None,
    force: bool = False,
    device: str = "auto",
    train_fn: Optional[Callable[..., Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Train a candidate from ``train_jsonl`` into a staging dir.

    Never trains into the live weights dir (asserted). Idempotent: when a
    previous staging run for the same ``corpus_id`` exists and is intact,
    it is reused and reported as such.
    """
    staging_root = Path(staging_root)
    staging_dir = staging_root / f"candidate-{corpus_id}"
    if weights_dir is not None and staging_dir.resolve() == Path(weights_dir).resolve():
        raise BrainLoopError("retrain: staging dir must not be the live weights dir")
    if weights_dir is not None and Path(train_jsonl).resolve().is_relative_to(
        Path(weights_dir).resolve()
    ):
        raise BrainLoopError("retrain: will not train from inside the live weights dir")

    if not force:
        prev = staging_manifest(staging_dir)
        if (
            prev.get("corpus_id") == corpus_id
            and (staging_dir / "tiny-gpt.pt").is_file()
        ):
            return {
                "staging_dir": str(staging_dir),
                "weights_pt": str(staging_dir / "tiny-gpt.pt"),
                "reused": True,
                "train_log": prev.get("train_log", {}),
            }

    cost = estimate_cost(
        corpus_chars=corpus_chars,
        steps=steps,
        max_seconds=max_seconds,
        calibration=load_calibration(loop_dir),
    )
    fn = train_fn or (
        lambda **kw: _default_train_fn(
            data=Path(kw["data"]),
            steps=int(kw["steps"]),
            out_dir=Path(kw["out_dir"]),
            seed=int(kw["seed"]),
            batch_size=int(kw.get("batch_size", 32)),
            lr=float(kw.get("lr", 3e-4)),
            timeout=int(kw.get("timeout", max_seconds)),
            repo=repo_root(),
            device=str(kw.get("device", device)),
        )
    )
    staging_dir.mkdir(parents=True, exist_ok=True)
    result = fn(
        data=str(train_jsonl),
        steps=steps,
        out_dir=str(staging_dir),
        seed=seed,
        batch_size=batch_size,
        lr=lr,
        timeout=max_seconds,
    )
    train_log = result.get("train_log", {}) if isinstance(result, dict) else {}
    manifest = {
        "corpus_id": corpus_id,
        "staged_at": datetime.now(timezone.utc).isoformat(),
        "steps": steps,
        "seed": seed,
        "batch_size": batch_size,
        "lr": lr,
        "device": device,
        "cost_estimate": cost,
        "train_log": train_log,
        "weights_pt": str(staging_dir / "tiny-gpt.pt"),
    }
    (staging_dir / "stage_manifest.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8"
    )
    # Feed calibration for the next estimate.
    wall = train_log.get("wall_seconds") or result.get("seconds")
    if isinstance(wall, (int, float)) and wall > 0 and steps > 0:
        save_calibration(
            loop_dir,
            {
                "chars_per_sec": round(steps * (corpus_chars / 1000.0) / wall, 3),
                "measured_at": datetime.now(timezone.utc).isoformat(),
                "steps": steps,
                "corpus_chars": corpus_chars,
                "wall_seconds": wall,
            },
        )
    return {
        "staging_dir": str(staging_dir),
        "weights_pt": str(staging_dir / "tiny-gpt.pt"),
        "reused": False,
        "train_log": train_log,
        "cost_estimate": cost,
    }
