"""v2 trainer: the loop that consumes the harness.

Pipeline::

    train.yaml -> load_config -> stage_curriculum -> train loop
       -> checkpoint every N steps (atomic, pruned, resumable;
          keep_best never deletes the run's best self)
       -> eval harness every M steps (held-out ppl + probes, JSON reports,
          baseline comparison) with early stopping on held-out NLL
       -> spectrum samples every eval (creative / agentic / identity)
       -> bloodline ledger entry when the run ends

Only :meth:`Trainer.run` needs torch. Planning, curriculum staging, and
report comparison are torch-free and hermetic-testable.

Builder contract (matches ``levi.brain.train.model_v2:build_model``):
  - ``builder(model_hyperparam_dict)`` -> ``torch.nn.Module`` with
    ``forward(idx: LongTensor (B, T)) -> Tensor (B, T, V)``. The dict is
    the config's ``model:`` section WITHOUT the ``builder``/``tokenizer``
    import-path keys (they are harness routing, not model config).
  - tokenizer builder takes no arguments -> object with ``encode`` /
    ``decode`` / ``vocab_size`` (``eod_id`` used as doc separator when
    present). ``vocab_size``/``eod_id`` may be properties or methods;
    both are accepted.

Resume semantics: the run directory holds the checkpoints; resuming with a
different config hash raises instead of silently continuing. Optimizer state
is intentionally NOT checkpointed (documented limitation): the LR schedule
continues from the resumed global step, so resumed training picks up the
decayed LR rather than restarting warmup.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from levi.brain.train.v2 import eval_harness as eh
from levi.brain.train.v2.checkpoint import (
    best_held_out_entry,
    list_checkpoints,
    numpy_to_torch_state_dict,
    resume_from_latest,
    save_checkpoint,
    torch_state_dict_to_numpy,
)
from levi.brain.train.v2.config import (
    TrainConfig,
    fingerprint,
    load_config,
    resolve_builder,
)
from levi.brain.train.v2.corpus_manager import (
    Doc,
    check_policy,
    dedupe,
    load_jsonl_docs,
    load_manifest,
)
from levi.brain.train.v2.curriculum import (
    CurriculumManifest,
    build_curriculum,
    describe_stages,
    save_curriculum,
)


class TrainerError(RuntimeError):
    """Trainer setup or run failed."""


def require_torch():
    """Import torch or raise a helpful error (training needs it)."""
    try:
        import torch

        return torch
    except ImportError as exc:
        raise TrainerError(
            "torch is required to train. Install the training stack:\n"
            "    pip install -r core/levi/brain/train/requirements.txt\n"
            "(the runtime kernel stays stdlib-only; torch is training-only)"
        ) from exc


# ---------------------------------------------------------------------------
# Planning (torch-free)


@dataclass
class RunPlan:
    cfg: TrainConfig
    config_hash: str
    config_dir: Path
    run_dir: Path
    ckpt_dir: Path
    reports_dir: Path
    curriculum_path: Path
    train_sources: list[tuple[Path, float]]  # (manifest path, weight)
    val_manifest: Path | None
    test_manifest: Path | None


def _resolve(path_str: str, config_dir: Path, what: str) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = config_dir / p
    if not p.is_file():
        raise TrainerError(f"{what} not found: {p}")
    return p


def plan_run(
    cfg: TrainConfig | str | Path, run_dir: str | Path | None = None
) -> RunPlan:
    """Resolve a config into a concrete run plan. No torch, no training."""
    if isinstance(cfg, (str, Path)):
        config_path = Path(cfg)
        cfg = load_config(config_path)
        config_dir = config_path.resolve().parent
    else:
        config_dir = Path.cwd()
    if run_dir is None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        run_dir = Path("runs") / f"{cfg.name}-{stamp}"
    run_dir = Path(run_dir)
    ckpt_dir = run_dir / "checkpoints"
    reports_dir = run_dir / "reports"

    train_sources: list[tuple[Path, float]] = []
    if cfg.data.mix:
        for entry in cfg.data.mix:
            mp = _resolve(entry["manifest"], config_dir, "mix manifest")
            train_sources.append((mp, entry["weight"]))
    else:
        train_sources.append(
            (_resolve(cfg.data.train_manifest, config_dir, "train manifest"), 1.0)
        )
    val_manifest = (
        _resolve(cfg.data.val_manifest, config_dir, "val manifest")
        if cfg.data.val_manifest
        else None
    )
    test_manifest = (
        _resolve(cfg.data.test_manifest, config_dir, "test manifest")
        if cfg.data.test_manifest
        else None
    )
    return RunPlan(
        cfg=cfg,
        config_hash=fingerprint(cfg),
        config_dir=config_dir,
        run_dir=run_dir,
        ckpt_dir=ckpt_dir,
        reports_dir=reports_dir,
        curriculum_path=run_dir / "curriculum.json",
        train_sources=train_sources,
        val_manifest=val_manifest,
        test_manifest=test_manifest,
    )


def load_manifest_docs(
    manifest_path: Path, *, base_dir: Path | None = None
) -> list[Doc]:
    """Load + dedupe every doc behind a corpus manifest (policy-checked)."""
    manifest = load_manifest(manifest_path)
    check_policy(manifest.tags)  # news gate, enforced again at train time
    base = base_dir or manifest_path.parent
    docs: list[Doc] = []
    for entry in manifest.files:
        docs.extend(load_jsonl_docs(base / entry.path))
    unique, removed = dedupe(docs)
    if removed:
        print(f"trainer: deduped {removed} duplicate docs from {manifest.name}")
    return unique


def stage_curriculum(plan: RunPlan) -> CurriculumManifest:
    """Build + save the simple->complex curriculum for this run.

    Torch-free. The TEACH worker consumes the saved manifest; the trainer
    itself walks docs in curriculum order each epoch (simplest first).
    """
    docs: list[Doc] = []
    for manifest_path, _weight in plan.train_sources:
        docs.extend(load_manifest_docs(manifest_path))
    if not docs:
        raise TrainerError("no training docs found behind train manifests")
    sources = [
        f"{load_manifest(mp).name}@{load_manifest(mp).version}"
        for mp, _ in plan.train_sources
    ]
    manifest = build_curriculum(
        docs,
        name=f"{plan.cfg.name}-curriculum",
        source_manifests=sources,
        n_stages=4,
        seed=plan.cfg.seed,
    )
    save_curriculum(manifest, plan.curriculum_path)
    for stage in describe_stages(manifest):
        print(
            f"trainer: curriculum stage {stage['stage']}: "
            f"{stage['n_docs']} docs "
            f"(difficulty {stage['difficulty_min']}..{stage['difficulty_max']})"
        )
    return manifest


def _tokenizer_int(tok: Any, name: str) -> int | None:
    """Read a tokenizer int that may be a property or a method.

    IMPROVE's ``ByteBPETokenizer`` exposes ``vocab_size``/``eod_id`` as
    properties; other builders may use methods. Accept both so the trainer
    does not break on either convention.
    """
    val = getattr(tok, name, None)
    if val is None:
        return None
    return int(val() if callable(val) else val)


def build_token_stream(
    docs: list[Doc], tok: Any, *, base_vocab_check: bool = True
) -> list[int]:
    """Encode docs into one id stream, separated by eod_id when available."""
    sep = _tokenizer_int(tok, "eod_id")
    vocab = _tokenizer_int(tok, "vocab_size")
    ids: list[int] = []
    for doc in docs:
        encoded = tok.encode(doc.text)
        if (
            base_vocab_check
            and vocab is not None
            and any(e < 0 or e >= vocab for e in encoded)
        ):
            raise TrainerError("tokenizer produced ids outside vocab range")
        ids.extend(encoded)
        if sep is not None:
            ids.append(sep)
    if not ids:
        raise TrainerError("token stream is empty after encoding")
    return ids


# ---------------------------------------------------------------------------
# Eval adapter (torch model -> harness ModelProto)


class _TorchLogitsAdapter:
    """Wrap a torch LM so the eval harness can score it (torch-free API)."""

    def __init__(self, model, tok, device, *, eval_block: int = 256):
        self._model = model
        self._tok = tok
        self._device = device
        self._eval_block = eval_block

    def logits_for_batch(self, prefixes: list[list[int]]) -> np.ndarray:
        torch = require_torch()
        self._model.eval()
        vocab = _tokenizer_int(self._tok, "vocab_size")
        if not vocab:
            raise eh.EvalError("tokenizer has no usable vocab_size")
        out = np.zeros((len(prefixes), vocab), dtype=np.float64)
        truncated = False
        with torch.no_grad():
            for i in range(0, len(prefixes), 32):
                chunk = prefixes[i : i + 32]
                # Pad to equal length; score only the last real position.
                max_len = max(len(p) for p in chunk)
                if max_len == 0:
                    raise eh.EvalError("empty prefix in eval batch")
                if max_len > self._eval_block:
                    # Truncate from the left; report it honestly, once.
                    chunk = [p[-self._eval_block :] for p in chunk]
                    max_len = self._eval_block
                    truncated = True
                batch = torch.zeros(len(chunk), max_len, dtype=torch.long)
                for j, p in enumerate(chunk):
                    batch[j, -len(p) :] = torch.tensor(p, dtype=torch.long)
                logits = self._model(batch.to(self._device)).cpu().numpy()
                for j in range(len(chunk)):
                    out[i + j] = logits[j, -1]
        if truncated:
            print(
                f"trainer: eval truncated >{self._eval_block}-token prefixes "
                f"from the left (eval_block={self._eval_block})"
            )
        return out


# ---------------------------------------------------------------------------
# The trainer


@dataclass
class Trainer:
    plan: RunPlan
    device: str = "cpu"
    max_val_tokens: int = 20000

    # -- torch-free setup -------------------------------------------------
    def stage(self) -> CurriculumManifest:
        """Build the curriculum manifest (no torch needed)."""
        self.plan.run_dir.mkdir(parents=True, exist_ok=True)
        return stage_curriculum(self.plan)

    # -- the run (needs torch) --------------------------------------------
    @staticmethod
    def _check_vocab(cfg: TrainConfig, actual_vocab: int | None) -> None:
        """Refuse a tokenizer/config vocab mismatch before torch sees it.

        Without this, an undersized model dies with a bare ``IndexError``
        inside the embedding lookup mid-run.
        """
        if actual_vocab is not None and actual_vocab > cfg.model.vocab_size:
            raise TrainerError(
                f"tokenizer vocab_size {actual_vocab} exceeds config "
                f"model.vocab_size {cfg.model.vocab_size} — the model cannot "
                f"embed ids the tokenizer emits; raise model.vocab_size"
            )

    @staticmethod
    def _model_cfg_dict(cfg: TrainConfig) -> dict:
        """Model hyper-parameters for the builder (no harness routing keys).

        ``n_kv_head=0`` means "no grouped-query attention": fall back to
        ``n_head``, mirroring the builder's default of ``n_kv_head=n_head``.
        """
        model_cfg = asdict(cfg.model)
        model_cfg.pop("builder", None)
        model_cfg.pop("tokenizer", None)
        if not model_cfg.get("n_kv_head"):
            model_cfg["n_kv_head"] = model_cfg["n_head"]
        return model_cfg

    def run(self) -> dict:
        torch = require_torch()
        plan, cfg = self.plan, self.plan.cfg
        plan.run_dir.mkdir(parents=True, exist_ok=True)

        seed = cfg.seed
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)

        model_builder = resolve_builder(cfg.model.builder)
        # The builder contract takes model hyper-parameters only; the
        # harness-level import paths are not model config.
        model = model_builder(self._model_cfg_dict(cfg))
        tok_builder = (
            resolve_builder(cfg.model.tokenizer) if cfg.model.tokenizer else None
        )
        tok = tok_builder() if tok_builder else None
        if tok is None:
            raise TrainerError(
                "config model.tokenizer is empty and the builder did not "
                "provide one — the trainer needs a tokenizer to encode data"
            )
        device = torch.device(self.device)
        model.to(device)

        actual_vocab = _tokenizer_int(tok, "vocab_size")
        self._check_vocab(cfg, actual_vocab)

        self.stage()
        streams = self._build_streams(tok, plan)
        # Dedicated RNG for stream sampling (the global seeds above cover
        # torch/numpy); reproducible without perturbing other users of
        # the module-level `random` instance.
        self._rng = random.Random(seed)

        val_ids = self._load_eval_stream(plan.val_manifest, tok, "val")

        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=cfg.schedule.learning_rate,
            weight_decay=cfg.schedule.weight_decay,
        )

        start_step = self._maybe_resume(model, plan)
        total_steps = cfg.schedule.steps
        if start_step >= total_steps:
            raise TrainerError(
                f"checkpoint already at step {start_step} >= "
                f"configured steps {total_steps}"
            )

        n_params = sum(p.numel() for p in model.parameters())
        print(
            f"trainer: {cfg.name} | params={n_params:,} | "
            f"steps {start_step}->{total_steps} | device={self.device}"
        )

        ema_loss: float | None = None
        reports: list[str] = []
        # Judgment state: the loop's memory of its own best self. Restored
        # from the manifest on resume, so a resumed run doesn't forget what
        # it already learned about itself.
        patience = cfg.schedule.early_stop_patience
        min_delta = cfg.schedule.early_stop_min_delta
        best_nll, best_step = self._restore_best(plan)
        stale_evals = 0
        latest_nll: float | None = None
        early_stopped = False
        last_step = start_step
        t0 = time.time()
        for step in range(start_step + 1, total_steps + 1):
            last_step = step
            loss = self._train_step(
                torch, model, optimizer, streams, cfg, step, total_steps
            )
            ema_loss = loss if ema_loss is None else 0.9 * ema_loss + 0.1 * loss

            if step % cfg.schedule.log_every == 0:
                lr = optimizer.param_groups[0]["lr"]
                print(
                    f"trainer: step {step}/{total_steps} "
                    f"loss={loss:.4f} ema={ema_loss:.4f} lr={lr:.2e} "
                    f"elapsed={time.time() - t0:.0f}s",
                    flush=True,
                )

            # Evaluate BEFORE checkpointing on shared steps, so checkpoint
            # metrics carry the freshest held-out evidence — the keep_best
            # decision depends on it.
            stop_now = False
            if (
                cfg.eval.every_steps and step % cfg.eval.every_steps == 0
            ) or step == total_steps:
                report_path, nll = self._evaluate(
                    torch, model, tok, device, plan, cfg, step, val_ids
                )
                reports.append(str(report_path))
                self._creative_samples(torch, model, tok, device, plan, cfg, step)
                latest_nll = nll
                if nll is not None:
                    if best_nll is None or nll < best_nll - min_delta:
                        best_nll, best_step, stale_evals = nll, step, 0
                    else:
                        stale_evals += 1
                        if patience > 0 and stale_evals >= patience:
                            print(
                                f"trainer: early stop at step {step}: held-out "
                                f"NLL {nll:.4f} unimproved for {stale_evals} "
                                f"evals (best {best_nll:.4f} at step {best_step})",
                                flush=True,
                            )
                            stop_now = True

            if (
                step % cfg.checkpointing.save_every == 0
                or step == total_steps
                or stop_now
            ):
                metrics: dict[str, float] = {
                    "loss": float(ema_loss if ema_loss is not None else loss)
                }
                if latest_nll is not None:
                    metrics["held_out_nll"] = float(latest_nll)
                path = save_checkpoint(
                    plan.ckpt_dir,
                    step=step,
                    arrays=torch_state_dict_to_numpy(model.state_dict()),
                    metrics=metrics,
                    config_hash=plan.config_hash,
                    keep_last=cfg.checkpointing.keep_last,
                    keep_best=cfg.checkpointing.keep_best,
                )
                print(f"trainer: checkpoint -> {path}")

            if stop_now:
                early_stopped = True
                break

        summary = {
            "name": cfg.name,
            "steps": total_steps,
            "steps_trained": last_step,
            "final_ema_loss": ema_loss,
            "early_stopped": early_stopped,
            "best_held_out_nll": best_nll,
            "best_step": best_step,
            "config_hash": plan.config_hash,
            "checkpoints": str(plan.ckpt_dir),
            "reports": reports,
            "elapsed_s": round(time.time() - t0, 1),
        }
        print(f"trainer: done. {summary}")
        self._record_bloodline(plan, cfg, summary)
        return summary

    # -- internals ----------------------------------------------------------

    def _build_streams(self, tok: Any, plan: RunPlan) -> list[tuple[list[int], float]]:
        """One token stream per train source, walked in curriculum order."""
        order = self._curriculum_order(plan)
        streams: list[tuple[list[int], float]] = []
        for manifest_path, weight in plan.train_sources:
            docs = load_manifest_docs(manifest_path)
            by_id = {d.id: d for d in docs}
            ordered = [by_id[i] for i in order if i in by_id]
            streams.append((build_token_stream(ordered or docs, tok), weight))
        total = sum(w for _, w in streams)
        return [(ids, w / total) for ids, w in streams]

    def _curriculum_order(self, plan: RunPlan) -> list[str]:
        from levi.brain.train.v2.curriculum import load_curriculum

        if plan.curriculum_path.is_file():
            return load_curriculum(plan.curriculum_path).order
        return []

    def _load_eval_stream(
        self, manifest_path: Path | None, tok: Any, what: str
    ) -> list[int]:
        if manifest_path is None:
            return []
        docs = load_manifest_docs(manifest_path)
        ids = build_token_stream(docs, tok)[: self.max_val_tokens]
        print(f"trainer: {what} stream: {len(ids)} tokens from {len(docs)} docs")
        return ids

    def _maybe_resume(self, model, plan: RunPlan) -> int:
        require_torch()  # fail fast with a helpful message
        resumed = resume_from_latest(
            plan.ckpt_dir, expected_config_hash=plan.config_hash
        )
        if resumed is None:
            return 0
        if resumed["config_mismatch"]:
            raise TrainerError(
                f"checkpoint at step {resumed['step']} was trained under a "
                f"different config (hash {resumed['config_hash'][:12]}... vs "
                f"{plan.config_hash[:12]}...). Refusing to resume: use a fresh "
                f"run dir or the matching config."
            )
        state = numpy_to_torch_state_dict(resumed["arrays"], model.state_dict())
        model.load_state_dict(state)
        print(f"trainer: resumed from step {resumed['step']} ({resumed['path']})")
        return int(resumed["step"])

    def _restore_best(self, plan: RunPlan) -> tuple[float | None, int | None]:
        """Best held-out state from the checkpoint manifest (survives resume).

        A resumed run inherits the judgment of its earlier self instead of
        starting amnesiac.
        """
        entry = best_held_out_entry(plan.ckpt_dir)
        if entry is None:
            return None, None
        return float(entry["metrics"]["held_out_nll"]), int(entry["step"])

    # Spectrum prompts: the run is measured on prediction (held-out NLL +
    # probes) AND on generation across the creative / agentic / identity
    # spectrum. Fixed prompts and per-step seeding keep steps comparable.
    SPECTRUM_PROMPTS: tuple[tuple[str, str], ...] = (
        ("creative", "Write a short verse about a machine that dreams:"),
        ("agentic", "Plan three steps to teach a new skill to a helper:"),
        ("identity", "I am LEVI, and what I remember most is"),
    )

    def _creative_samples(
        self,
        torch,
        model,
        tok,
        device,
        plan: RunPlan,
        cfg: TrainConfig,
        step: int,
    ) -> Path:
        """Generate spectrum samples with the live model; write a report page."""
        model.eval()
        torch.manual_seed(cfg.seed + step)
        rows: list[tuple[str, str, str]] = []
        with torch.no_grad():
            for kind, prompt in self.SPECTRUM_PROMPTS:
                ids = tok.encode(prompt)
                idx = torch.tensor([ids], dtype=torch.long, device=device)
                out = model.generate(idx, max_new=60, temperature=0.8, top_k=50)
                text = tok.decode(out[0].tolist())
                rows.append((kind, prompt, text))
        path = plan.reports_dir / f"samples-step-{step:06d}.md"
        lines = [
            f"# Spectrum samples — {cfg.name} @ step {step}",
            "",
            "_Greedy/temperature generations from fixed prompts "
            "(temperature 0.8, top_k 50). Same prompts every eval; "
            "compare across steps to watch the creative spectrum move._",
            "",
        ]
        for kind, prompt, text in rows:
            lines += [f"## {kind}", "", f"**prompt:** {prompt}", "", text.strip(), ""]
        path.write_text("\n".join(lines), encoding="utf-8")
        print(f"trainer: samples -> {path}")
        return path

    def _record_bloodline(self, plan: RunPlan, cfg: TrainConfig, summary: dict) -> None:
        """Append this run to the bloodline ledger: every run's best self, remembered.

        The ledger lives at ``runs/BLOODLINE.json`` — one entry per run, so
        the lineage of the brain is inspectable without digging through run dirs.
        """
        import datetime

        ledger_path = Path(plan.run_dir).parent / "BLOODLINE.json"
        entries: list = []
        if ledger_path.is_file():
            try:
                entries = json.loads(ledger_path.read_text(encoding="utf-8"))
                if not isinstance(entries, list):
                    entries = []
            except (json.JSONDecodeError, OSError):
                entries = []
        entries.append(
            {
                "run": cfg.name,
                "run_dir": str(plan.run_dir),
                "finished_at": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
                "config_hash": plan.config_hash,
                "steps_trained": summary.get("steps_trained"),
                "early_stopped": summary.get("early_stopped"),
                "best_held_out_nll": summary.get("best_held_out_nll"),
                "best_step": summary.get("best_step"),
                "final_ema_loss": summary.get("final_ema_loss"),
                "checkpoints": summary.get("checkpoints"),
            }
        )
        tmp = ledger_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        os.replace(tmp, ledger_path)
        print(f"trainer: bloodline -> {ledger_path}")

    def _train_step(
        self,
        torch,
        model,
        optimizer,
        streams,
        cfg: TrainConfig,
        step: int,
        total_steps: int,
    ) -> float:
        # Clamp the train length by the model's block size when exposed.
        block = self._model_block_size(model)
        t = min(cfg.data.max_seq_len, block - 1)
        if t < 2:
            raise TrainerError(f"block_size {block} too small to train on")

        r = self._rng.random()
        cumulative = 0.0
        ids = streams[0][0]
        for stream_ids, weight in streams:
            cumulative += weight
            if r <= cumulative:
                ids = stream_ids
                break
        if len(ids) < t + 1:
            raise TrainerError(f"train stream has {len(ids)} tokens < needed {t + 1}")
        start = random.randrange(0, len(ids) - t)
        seq = torch.tensor(
            ids[start : start + t + 1],
            dtype=torch.long,
            device=next(model.parameters()).device,
        )
        x, y = seq[:-1].unsqueeze(0), seq[1:].unsqueeze(0)

        # LR schedule: linear warmup -> cosine decay to lr_min.
        sched = cfg.schedule
        if step <= sched.warmup_steps and sched.warmup_steps > 0:
            lr = sched.learning_rate * step / sched.warmup_steps
        else:
            progress = (step - sched.warmup_steps) / max(
                1, total_steps - sched.warmup_steps
            )
            lr = sched.lr_min + 0.5 * (sched.learning_rate - sched.lr_min) * (
                1 + math.cos(math.pi * min(1.0, progress))
            )
        for group in optimizer.param_groups:
            group["lr"] = lr

        model.train()
        optimizer.zero_grad(set_to_none=True)
        logits = model(x)
        loss = torch.nn.functional.cross_entropy(
            logits.view(-1, logits.size(-1)), y.view(-1)
        )
        loss.backward()
        if sched.grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), sched.grad_clip)
        optimizer.step()
        return float(loss.detach().cpu())

    @staticmethod
    def _model_block_size(model) -> int:
        for attr in ("config", "cfg", "hparams"):
            c = getattr(model, attr, None)
            if isinstance(c, dict) and "block_size" in c:
                return int(c["block_size"])
        return 10**9

    def _evaluate(
        self,
        torch,
        model,
        tok,
        device,
        plan: RunPlan,
        cfg: TrainConfig,
        step: int,
        val_ids: list[int],
    ) -> tuple[Path, float | None]:
        """Run the eval harness; return (report path, held-out NLL or None)."""
        # Never score a prefix longer than the model can consume: clamp the
        # eval block to both the model's block size and the training length.
        block = self._model_block_size(model)
        eval_block = max(2, min(block, cfg.data.max_seq_len, 256))
        adapter = _TorchLogitsAdapter(model, tok, device, eval_block=eval_block)
        probes = cfg.eval.probes_path or None
        if probes:
            probes = (
                str(plan.config_dir / probes)
                if not Path(probes).is_absolute()
                else probes
            )
        report = eh.run_eval(
            adapter,
            tok,
            model_name=f"{cfg.name}@step{step}",
            step=step,
            val_token_ids=val_ids or None,
            probes_path=probes,
        )
        baseline_note = self._attach_baseline(
            torch, report, plan, cfg, tok, device, val_ids, probes
        )
        if baseline_note:
            report.notes.append(baseline_note)
        path = plan.reports_dir / f"eval-step-{step:06d}.json"
        eh.write_report(report, path)
        print(f"trainer: eval report -> {path}")
        for note in report.notes:
            print(f"trainer: eval note: {note}")
        nll = report.perplexity.get("nll_per_token") if isinstance(
            report.perplexity, dict
        ) else None
        return path, (float(nll) if nll is not None else None)

    def _attach_baseline(
        self,
        torch,
        report: eh.EvalReport,
        plan: RunPlan,
        cfg: TrainConfig,
        tok,
        device,
        val_ids: list[int],
        probes,
    ) -> str | None:
        """Compare against the baseline; returns a note for the report."""
        base = cfg.eval.baseline_checkpoint
        if not base:
            return None
        base_path = Path(base)
        if not base_path.is_absolute():
            base_path = plan.config_dir / base_path
        if not base_path.is_file():
            return f"baseline {base} not found — comparison skipped."
        try:
            if base_path.suffix == ".json":
                import json

                baseline_report = json.loads(base_path.read_text(encoding="utf-8"))
            elif base_path.suffix == ".npz":
                baseline_report = self._eval_baseline_npz(
                    torch, base_path, plan, cfg, tok, device, val_ids, probes
                )
            else:
                return (
                    f"baseline {base_path.name}: unsupported format "
                    f"({base_path.suffix}) — comparison skipped. "
                    "Use a v2 .npz checkpoint or an eval report .json."
                )
            comparison = eh.compare_reports(baseline_report, report.to_dict())
            verdict = comparison.get("overall", "unknown")
            return f"baseline comparison vs {base_path.name}: {verdict}"
        except Exception as exc:  # never let baseline scoring break the run
            return f"baseline comparison failed ({exc}) — skipped."

    def _eval_baseline_npz(
        self,
        torch,
        base_path: Path,
        plan: RunPlan,
        cfg: TrainConfig,
        tok,
        device,
        val_ids: list[int],
        probes,
    ) -> dict:
        from levi.brain.train.v2.checkpoint import load_checkpoint

        model_builder = resolve_builder(cfg.model.builder)
        base_model = model_builder(self._model_cfg_dict(cfg))
        ckpt = load_checkpoint(base_path)
        state = numpy_to_torch_state_dict(ckpt["arrays"], base_model.state_dict())
        base_model.load_state_dict(state)
        base_model.to(device)
        block = self._model_block_size(base_model)
        eval_block = max(2, min(block, cfg.data.max_seq_len, 256))
        adapter = _TorchLogitsAdapter(base_model, tok, device, eval_block=eval_block)
        report = eh.run_eval(
            adapter,
            tok,
            model_name=f"baseline@{ckpt['step']}",
            step=int(ckpt["step"]),
            val_token_ids=val_ids or None,
            probes_path=probes,
        )
        return report.to_dict()


# ---------------------------------------------------------------------------
# CLI


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="v2 brain trainer: config -> curriculum -> train -> "
        "checkpoint -> honest eval"
    )
    ap.add_argument("--config", required=True, help="path to train.yaml")
    ap.add_argument(
        "--run-dir",
        default=None,
        help="run directory (default: runs/<name>-<timestamp>)",
    )
    ap.add_argument("--device", default="cpu", help="torch device (default: cpu)")
    ap.add_argument(
        "--stage-only",
        action="store_true",
        help="only build the curriculum manifest, then exit",
    )
    args = ap.parse_args(argv)

    try:
        plan = plan_run(args.config, args.run_dir)
    except (TrainerError, Exception) as exc:
        print(f"trainer: {exc}", file=sys.stderr)
        return 2
    trainer = Trainer(plan, device=args.device)
    try:
        if args.stage_only:
            trainer.stage()
            print(f"trainer: curriculum staged -> {plan.curriculum_path}")
            return 0
        trainer.run()
        return 0
    except TrainerError as exc:
        print(f"trainer: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
