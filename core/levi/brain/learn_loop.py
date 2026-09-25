"""Learning-loop orchestrator: observe -> corpus -> retrain -> eval-gate.

One cycle of the self-sufficiency engine:

1. OBSERVE  read the local observation log (never crashes on a missing
   or corrupt store)
2. CORPUS   observations -> deterministic training corpus (dedupe,
   quality filters, teacher weighting, vocab alignment, train/val split)
3. ESTIMATE  honest pre-training cost estimate (calibrated when possible)
4. RETRAIN   candidate weights into a staging dir (skipped on dry-run;
   needs torch, else the cycle stops honestly after the corpus stage)
5. EVAL     candidate vs incumbent: held-out loss + behavioral checks +
   regret check
6. GATE     promote only on real improvement; otherwise reject with
   reasons. Promotion keeps the previous weights as rollback.
7. RECEIPT   every cycle writes a receipt, whatever happened.

Disabled by default: there is no schedule until ``learn schedule`` runs,
and ``learn once`` is a dry-run unless ``--live`` is passed. Chauncey
turns it on.

Public surfaces:
- ``levi brain learn once|tick|schedule|unschedule|status|rollback|history``
- ``run_cycle(cfg, ...)`` for programmatic use (train/eval/export/model
  loading are injectable for hermetic tests).
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from levi.brain.learn_corpus import BrainLoopError, build_corpus
from levi.brain.learn_eval import (
    export_portable,
    gate_decision,
    list_rollbacks,
    load_anchors,
    measure_scores,
    promote,
    read_lineage,
    rollback,
)
from levi.brain.learn_obs import observations_file, read_observations
from levi.brain.learn_train import (
    estimate_cost,
    load_calibration,
    run_retrain,
    torch_available,
)

SCHEMA = "levi-learn-loop/1"
RECEIPT_KIND = "learn-cycle"


def default_loop_dir() -> Path:
    return Path.home() / ".levi" / "brain-loop"


def default_weights_dir() -> Path:
    # core/levi/brain/learn_loop.py -> parents[3] is the repo root.
    return Path(__file__).resolve().parents[3] / "core" / "levi" / "brain" / "weights"


@dataclass
class LoopConfig:
    loop_dir: Path = field(default_factory=default_loop_dir)
    weights_dir: Path = field(default_factory=default_weights_dir)
    observations_path: Optional[Path] = None  # None -> env/default lookup
    seed: int = 1337
    val_ratio: float = 0.10
    min_quality: float = 0.3
    min_text_chars: int = 16
    max_text_chars: int = 8000
    max_steps: int = 600
    max_seconds: int = 3600
    batch_size: int = 32
    lr: float = 3e-4
    promote_margin: float = 0.02
    regret_margin: float = 0.05
    teacher_weights: Dict[str, float] = field(default_factory=dict)
    max_copies: int = 8
    anchors_k: int = 8
    eval_windows: int = 6
    eval_window_chars: int = 40
    dry_run: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["loop_dir"] = str(self.loop_dir)
        d["weights_dir"] = str(self.weights_dir)
        d["observations_path"] = (
            str(self.observations_path) if self.observations_path else None
        )
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoopConfig":
        d = dict(data)
        for key in ("loop_dir", "weights_dir", "observations_path"):
            if d.get(key):
                d[key] = Path(d[key])
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})


def config_path(loop_dir: Path) -> Path:
    return Path(loop_dir) / "config.json"


def load_config(loop_dir: Optional[Path] = None) -> LoopConfig:
    base = LoopConfig()
    if loop_dir is not None:
        base.loop_dir = Path(loop_dir)
    p = config_path(base.loop_dir)
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            data = {}
        if isinstance(data, dict):
            data = dict(data)
            data["loop_dir"] = str(base.loop_dir)
            return LoopConfig.from_dict(data)
    return base


def save_config(cfg: LoopConfig) -> Path:
    p = config_path(cfg.loop_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg.to_dict(), indent=1), encoding="utf-8")
    return p


# ---------------------------------------------------------------- receipts


def receipts_dir(loop_dir: Path) -> Path:
    return Path(loop_dir) / "receipts"


def write_receipt(loop_dir: Path, record: Dict[str, Any]) -> Path:
    d = receipts_dir(loop_dir)
    d.mkdir(parents=True, exist_ok=True)
    rec = dict(record)
    rec.setdefault("kind", RECEIPT_KIND)
    rec.setdefault("schema", SCHEMA)
    rec.setdefault("logged_at", datetime.now(timezone.utc).isoformat())
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = d / f"learn-{ts}-{rec.get('cycle_id', 'x')[:8]}.json"
    path.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def read_receipts(loop_dir: Path, limit: int = 20) -> List[Dict[str, Any]]:
    d = receipts_dir(loop_dir)
    if not d.is_dir():
        return []
    files = sorted(d.glob("learn-*.json"))
    out: List[Dict[str, Any]] = []
    for p in files[-limit:]:
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


# ---------------------------------------------------------------- scheduler


def schedule_path(loop_dir: Path) -> Path:
    return Path(loop_dir) / "schedule.json"


def schedule_loop(
    loop_dir: Path, *, every_seconds: int, mode: str = "dry-run"
) -> Dict[str, Any]:
    if every_seconds <= 0:
        raise BrainLoopError("schedule: every_seconds must be positive")
    if mode not in ("dry-run", "live"):
        raise BrainLoopError("schedule: mode must be 'dry-run' or 'live'")
    entry = {
        "schema": SCHEMA,
        "every_seconds": every_seconds,
        "mode": mode,
        "next_run": time.time(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    p = schedule_path(loop_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entry, indent=1), encoding="utf-8")
    return entry


def unschedule_loop(loop_dir: Path) -> bool:
    p = schedule_path(loop_dir)
    if p.is_file():
        p.unlink()
        return True
    return False


def load_schedule(loop_dir: Path) -> Optional[Dict[str, Any]]:
    p = schedule_path(loop_dir)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------- the cycle


@dataclass
class CycleReport:
    cycle_id: str
    mode: str
    started_at: str
    finished_at: str = ""
    status: str = "unknown"
    stages: Dict[str, Any] = field(default_factory=dict)
    decision: str = ""
    reasons: List[str] = field(default_factory=list)
    receipt_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _new_cycle_id() -> str:
    return (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        + f"-{int(time.time() * 1000) % 100000:05d}"
    )


def _incumbent_vocab_chars(weights_dir: Path) -> Optional[List[str]]:
    """Read the incumbent's charset from the portable manifest, if the
    torch-free export is present and valid. Never raises."""
    try:
        from levi.brain import runtime as _rt

        manifest, _blobs = _rt.load_portable_tensors(
            str(Path(weights_dir) / "tiny-gpt-portable")
        )
        chars = manifest.get("chars")
        if isinstance(chars, list) and chars:
            return [str(c) for c in chars]
    except Exception:
        pass
    return None


def _read_val_text(val_path: str) -> str:
    texts = []
    with open(val_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = rec.get("text", "") if isinstance(rec, dict) else ""
            if t:
                texts.append(t)
    return "\n\n".join(texts)


def run_cycle(
    cfg: LoopConfig,
    *,
    train_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    model_fn: Optional[Callable[[Path], Any]] = None,
    measure_fn: Optional[Callable[..., Any]] = None,
    export_fn: Optional[Callable[[Path, Path], Dict[str, Any]]] = None,
    validate_fn: Optional[Callable[[Path], None]] = None,
) -> CycleReport:
    """Run one full learning-loop cycle. Every exit path — promoted,
    rejected, blocked, dry-run — writes a receipt.

    ``train_fn`` / ``model_fn`` / ``measure_fn`` / ``export_fn`` /
    ``validate_fn`` are injectable so tests run the whole cycle
    hermetically (no torch, no subprocess, no network, no HOME writes).
    """
    mode = "dry-run" if cfg.dry_run else "live"
    rep = CycleReport(
        cycle_id=_new_cycle_id(),
        mode=mode,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    obs_path = cfg.observations_path or observations_file()

    def finish(status: str) -> CycleReport:
        rep.status = status
        rep.finished_at = datetime.now(timezone.utc).isoformat()
        rep.receipt_path = str(write_receipt(cfg.loop_dir, rep.to_dict()))
        return rep

    # 1. OBSERVE
    try:
        obs = read_observations(obs_path)
    except Exception as exc:  # noqa: BLE001 — the loop never crashes on I/O
        rep.stages["observe"] = {"error": f"{exc.__class__.__name__}: {exc}"}
        return finish("blocked")
    rep.stages["observe"] = {
        "path": obs["path"],
        "records": len(obs["records"]),
        "skipped": obs["skipped"],
    }
    if not obs["records"]:
        rep.decision = "none"
        rep.reasons = ["no observations recorded yet — nothing to learn from"]
        return finish("empty")

    # 2. CORPUS
    vocab_chars = _incumbent_vocab_chars(cfg.weights_dir)
    corpus_dir = cfg.loop_dir / "corpora"
    try:
        source_mtime = ""
        try:
            source_mtime = str(obs_path.stat().st_mtime)
        except OSError:
            pass
        built = build_corpus(
            obs["records"],
            corpus_dir,
            seed=cfg.seed,
            val_ratio=cfg.val_ratio,
            vocab_chars=vocab_chars,
            teacher_weights=cfg.teacher_weights,
            min_quality=cfg.min_quality,
            min_text_chars=cfg.min_text_chars,
            max_text_chars=cfg.max_text_chars,
            max_copies=cfg.max_copies,
            source_path=obs["path"],
            source_mtime=source_mtime,
        )
    except BrainLoopError as exc:
        rep.decision = "none"
        rep.reasons = [str(exc)]
        return finish("blocked")
    manifest = built["manifest"]
    rep.stages["corpus"] = {
        "corpus_id": built["corpus_id"],
        "counts": manifest["counts"],
        "train_chars": manifest["train_chars"],
        "val_chars": manifest["val_chars"],
        "per_model_lines": manifest["per_model_lines"],
        "vocab_filter": manifest["vocab_filter"],
    }
    if manifest["train_chars"] < 10_000:
        rep.decision = "none"
        rep.reasons = [
            f"corpus too small ({manifest['train_chars']} chars < 10000 "
            "required by the trainer) — keep recording observations"
        ]
        return finish("blocked")

    # 3. ESTIMATE
    cost = estimate_cost(
        corpus_chars=manifest["train_chars"],
        steps=cfg.max_steps,
        max_seconds=cfg.max_seconds,
        calibration=load_calibration(cfg.loop_dir),
    )
    rep.stages["estimate"] = cost

    if cfg.dry_run:
        rep.decision = "dry-run"
        rep.reasons = [
            "dry-run: corpus built and cost estimated; no training, no "
            "promotion. Pass --live to run for real."
        ]
        return finish("dry-run")

    # 4. RETRAIN
    if not torch_available() and train_fn is None:
        rep.decision = "none"
        rep.reasons = [
            "torch is not installed — retraining needs the training "
            "environment. The corpus is staged and ready."
        ]
        return finish("blocked")
    try:
        staged = run_retrain(
            train_jsonl=Path(built["train_path"]),
            corpus_id=built["corpus_id"],
            corpus_chars=manifest["train_chars"],
            staging_root=cfg.loop_dir / "staging",
            loop_dir=cfg.loop_dir,
            steps=cfg.max_steps,
            seed=cfg.seed,
            batch_size=cfg.batch_size,
            lr=cfg.lr,
            max_seconds=cfg.max_seconds,
            weights_dir=cfg.weights_dir,
            train_fn=train_fn,
        )
    except BrainLoopError as exc:
        rep.decision = "none"
        rep.reasons = [f"retrain failed: {exc}"]
        return finish("blocked")
    rep.stages["retrain"] = {
        "staging_dir": staged["staging_dir"],
        "reused": staged["reused"],
        "train_log": staged.get("train_log", {}),
    }

    # 5. EVAL — export candidate to portable, measure both models
    export = export_fn or export_portable
    candidate_portable = Path(staged["staging_dir"]) / "portable"
    try:
        export(Path(staged["weights_pt"]), candidate_portable)
    except BrainLoopError as exc:
        rep.decision = "none"
        rep.reasons = [f"candidate export failed: {exc}"]
        return finish("blocked")

    val_text = _read_val_text(built["val_path"])
    anchors = load_anchors(cfg.weights_dir)
    try:
        if measure_fn is not None:
            scores = measure_fn(
                candidate_portable_dir=candidate_portable,
                incumbent_portable_dir=cfg.weights_dir / "tiny-gpt-portable",
                val_text=val_text,
                anchors=anchors,
                cfg=cfg,
            )
        else:
            from levi.brain.learn_eval import RuntimeScoredModel

            load_model = model_fn or (lambda d: RuntimeScoredModel(Path(d)))
            candidate_model = load_model(candidate_portable)
            incumbent_model = load_model(cfg.weights_dir / "tiny-gpt-portable")
            scores = measure_scores(
                candidate=candidate_model,
                incumbent=incumbent_model,
                val_text=val_text,
                anchors=anchors,
                eval_windows=cfg.eval_windows,
                eval_window_chars=cfg.eval_window_chars,
                seed=cfg.seed,
                backend="numpy",
            )
    except BrainLoopError as exc:
        rep.decision = "none"
        rep.reasons = [f"eval failed: {exc}"]
        return finish("blocked")
    rep.stages["eval"] = {
        "heldout_candidate": scores.heldout_candidate,
        "heldout_incumbent": scores.heldout_incumbent,
        "positions_scored": scores.positions_scored,
        "val_chars_excluded": scores.val_chars_excluded,
        "behavioral": scores.behavioral,
        "regret_candidate": scores.regret_candidate,
        "regret_incumbent": scores.regret_incumbent,
        "regret_skipped": scores.regret_skipped,
    }

    # 6. GATE
    decision, reasons = gate_decision(
        scores, promote_margin=cfg.promote_margin, regret_margin=cfg.regret_margin
    )
    rep.decision = decision
    rep.reasons = reasons
    if decision == "promote":
        incumbent_model = None
        if model_fn is not None or measure_fn is None:
            try:
                from levi.brain.learn_eval import RuntimeScoredModel

                load_model = model_fn or (lambda d: RuntimeScoredModel(Path(d)))
                incumbent_model = load_model(cfg.weights_dir / "tiny-gpt-portable")
            except Exception:
                incumbent_model = None
        try:
            result = promote(
                candidate_pt=Path(staged["weights_pt"]),
                candidate_portable_dir=candidate_portable,
                weights_dir=cfg.weights_dir,
                lineage_entry={
                    "corpus_id": built["corpus_id"],
                    "corpus_sha256": manifest["files"]["train.jsonl"],
                    "eval": rep.stages["eval"],
                    "config": {
                        "steps": cfg.max_steps,
                        "seed": cfg.seed,
                        "promote_margin": cfg.promote_margin,
                        "regret_margin": cfg.regret_margin,
                    },
                    "observations": rep.stages["observe"],
                },
                incumbent=incumbent_model,
                anchors_k=cfg.anchors_k,
                seed=cfg.seed,
                validate_fn=validate_fn,
            )
            rep.stages["promote"] = result
        except BrainLoopError as exc:
            rep.decision = "reject"
            rep.reasons = [f"promotion aborted: {exc}"]
            return finish("blocked")
        return finish("promoted")
    return finish("rejected")


def tick(cfg: LoopConfig, **cycle_kw: Any) -> Dict[str, Any]:
    """Run the scheduled job if it is due. No schedule -> honest no-op."""
    sched = load_schedule(cfg.loop_dir)
    if sched is None:
        return {"ran": False, "reason": "no schedule registered (learn schedule)"}
    now = time.time()
    if now < float(sched.get("next_run", 0)):
        return {"ran": False, "reason": "not due yet"}
    mode = sched.get("mode", "dry-run")
    cfg.dry_run = mode != "live"
    report = run_cycle(cfg, **cycle_kw)
    sched["next_run"] = now + float(sched.get("every_seconds", 86400))
    sched["last_run"] = report.to_dict()
    schedule_path(cfg.loop_dir).write_text(json.dumps(sched, indent=1))
    return {"ran": True, "mode": mode, "report": report.to_dict()}


# ---------------------------------------------------------------- status


def status(cfg: LoopConfig) -> Dict[str, Any]:
    obs_path = cfg.observations_path or observations_file()
    try:
        obs = read_observations(obs_path)
        obs_info = {
            "path": obs["path"],
            "records": len(obs["records"]),
            "skipped": obs["skipped"],
        }
    except Exception as exc:  # noqa: BLE001
        obs_info = {"path": str(obs_path), "error": str(exc)}
    sched = load_schedule(cfg.loop_dir)
    receipts = read_receipts(cfg.loop_dir, limit=1)
    lineage = read_lineage(cfg.weights_dir, limit=1)
    weights_pt = cfg.weights_dir / "tiny-gpt.pt"
    portable = cfg.weights_dir / "tiny-gpt-portable" / "manifest.json"
    rollbacks = [p.name for p in list_rollbacks(cfg.weights_dir)]
    return {
        "schema": SCHEMA,
        "loop_dir": str(cfg.loop_dir),
        "weights_dir": str(cfg.weights_dir),
        "observations": obs_info,
        "schedule": sched,
        "weights_present": weights_pt.is_file(),
        "portable_present": portable.is_file(),
        "rollback_backups": rollbacks,
        "last_cycle": receipts[-1] if receipts else None,
        "last_lineage": lineage[-1] if lineage else None,
        "dry_run_default": cfg.dry_run,
    }


# ---------------------------------------------------------------- CLI


def _add_common(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--loop-dir", default=None, help="Loop state dir")
    ap.add_argument("--weights-dir", default=None, help="Live weights dir")
    ap.add_argument(
        "--observations", default=None, help="Observation log path (overrides default)"
    )
    ap.add_argument("--json", action="store_true", help="Machine-readable output")


def _cfg_from_args(args: argparse.Namespace) -> LoopConfig:
    cfg = load_config(Path(args.loop_dir) if args.loop_dir else None)
    if args.weights_dir:
        cfg.weights_dir = Path(args.weights_dir)
    if getattr(args, "observations", None):
        cfg.observations_path = Path(args.observations)
    return cfg


def main_cli(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi brain learn",
        description="LEVI's learning loop: observations -> corpus -> "
        "retrain -> eval-gate -> promote/rollback. Dry-run by default.",
    )
    sub = ap.add_subparsers(dest="cmd")

    p_once = sub.add_parser("once", help="Run one cycle now")
    p_once.add_argument("--live", action="store_true", help="Really train+promote")
    p_once.add_argument("--dry-run", action="store_true", help="Force dry-run")
    p_once.add_argument("--steps", type=int, default=None)
    p_once.add_argument("--margin", type=float, default=None)
    p_once.add_argument("--force", action="store_true", help="Retrain, ignore staged")
    _add_common(p_once)

    p_tick = sub.add_parser("tick", help="Run the scheduled job if due")
    _add_common(p_tick)

    p_sched = sub.add_parser("schedule", help="Register the loop on an interval")
    p_sched.add_argument("--every", type=int, required=True, help="Seconds")
    p_sched.add_argument("--live", action="store_true")
    _add_common(p_sched)

    p_uns = sub.add_parser("unschedule", help="Remove the schedule")
    _add_common(p_uns)

    p_stat = sub.add_parser("status", help="Loop status")
    _add_common(p_stat)

    p_rb = sub.add_parser("rollback", help="Restore previous weights")
    p_rb.add_argument("--to", default=None)
    p_rb.add_argument("--reason", default="")
    _add_common(p_rb)

    p_hist = sub.add_parser("history", help="Recent cycle receipts")
    p_hist.add_argument("n", nargs="?", type=int, default=5)
    _add_common(p_hist)

    args = ap.parse_args(argv)
    cfg = _cfg_from_args(args)
    as_json = bool(getattr(args, "json", False))

    def emit(obj: Any, text: str) -> int:
        if as_json:
            print(json.dumps(obj, indent=1, ensure_ascii=False, default=str))
        else:
            print(text)
        return 0

    cmd = args.cmd or "status"
    if cmd == "once":
        if args.steps:
            cfg.max_steps = args.steps
        if args.margin is not None:
            cfg.promote_margin = args.margin
        if args.live:
            cfg.dry_run = False
        if args.dry_run:
            cfg.dry_run = True
        rep = run_cycle(cfg)
        d = rep.to_dict()
        return emit(
            d,
            f"cycle {rep.cycle_id} [{rep.mode}] -> {rep.status} "
            f"(decision: {rep.decision})\n"
            + "\n".join(f"  - {r}" for r in rep.reasons),
        )
    if cmd == "tick":
        res = tick(cfg)
        return emit(
            res, f"tick: ran={res['ran']} ({res.get('reason', res.get('mode'))})"
        )
    if cmd == "schedule":
        entry = schedule_loop(
            cfg.loop_dir,
            every_seconds=args.every,
            mode="live" if args.live else "dry-run",
        )
        save_config(cfg)
        return emit(entry, f"scheduled every {args.every}s in {entry['mode']} mode")
    if cmd == "unschedule":
        removed = unschedule_loop(cfg.loop_dir)
        return emit(
            {"removed": removed}, "schedule removed" if removed else "no schedule"
        )
    if cmd == "rollback":
        try:
            res = rollback(cfg.weights_dir, to=args.to, reason=args.reason)
        except BrainLoopError as exc:
            print(f"rollback failed: {exc}")
            return 1
        return emit(res, f"rolled back to {res['restored_from']}")
    if cmd == "history":
        recs = read_receipts(cfg.loop_dir, limit=args.n)
        if as_json:
            print(json.dumps(recs, indent=1, ensure_ascii=False, default=str))
        else:
            for r in recs:
                print(
                    f"{r.get('logged_at')} [{r.get('mode')}] "
                    f"{r.get('status')} decision={r.get('decision')}"
                )
            if not recs:
                print("no cycles recorded yet")
        return 0
    # status
    st = status(cfg)
    return emit(st, _format_status(st))


def _format_status(st: Dict[str, Any]) -> str:
    obs = st.get("observations", {})
    sched = st.get("schedule")
    lines = [
        f"loop dir   : {st['loop_dir']}",
        f"weights dir: {st['weights_dir']}",
        f"observations: {obs.get('records', '?')} records "
        f"(skipped {obs.get('skipped', '?')}) at {obs.get('path')}",
        f"weights    : {'present' if st['weights_present'] else 'MISSING'}; "
        f"portable: {'present' if st['portable_present'] else 'MISSING'}",
        f"rollbacks  : {len(st['rollback_backups'])} backup(s)",
        "schedule   : "
        + (
            f"every {sched['every_seconds']}s, mode={sched['mode']}"
            if sched
            else "none (disabled by default — run 'learn schedule')"
        ),
    ]
    last = st.get("last_cycle")
    lines.append(
        "last cycle : "
        + (
            f"{last.get('logged_at')} [{last.get('mode')}] {last.get('status')} "
            f"decision={last.get('decision')}"
            if last
            else "none yet"
        )
    )
    lin = st.get("last_lineage")
    lines.append(
        "lineage    : "
        + (f"{lin.get('kind')} at {lin.get('ts')}" if lin else "none yet")
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main_cli())
