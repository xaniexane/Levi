"""v2 training config: ONE YAML file drives model size, data mix, schedule.

Example ``train.yaml``::

    name: tiny-gpt-v2
    seed: 1337
    model:
      builder: "levi.brain.train.model_v2:build_model"  # callable import path
      tokenizer: "levi.brain.train.model_v2:build_tokenizer"
      vocab_size: 256
      n_layer: 4
      n_head: 4
      n_embd: 128
      block_size: 128
      dropout: 0.0
    data:
      train_manifest: corpora/courses_train.manifest.json
      val_manifest: corpora/courses_val.manifest.json
      test_manifest: corpora/courses_test.manifest.json
      batch_size: 32
      max_seq_len: 128
      shuffle_seed: 1337
      # optional weighted mix over corpus manifests:
      # mix:
      #   - {manifest: corpora/courses.manifest.json, weight: 0.7}
      #   - {manifest: corpora/growth_learn.manifest.json, weight: 0.3}
    schedule:
      steps: 2000
      learning_rate: 3.0e-4
      warmup_steps: 100
      lr_min: 3.0e-5
      weight_decay: 0.01
      grad_clip: 1.0
      log_every: 25
    eval:
      every_steps: 250
      probes_path: eval/probes.jsonl
      baseline_checkpoint: weights/v1/tiny-gpt.pt.npz
      max_val_batches: 50
    checkpointing:
      dir: weights/v2
      save_every: 250
      keep_last: 5

Validation is strict and loud: a bad config raises :class:`ConfigError`
naming the offending field instead of silently training on garbage.
"""

from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml


class ConfigError(ValueError):
    """A training config is missing, malformed, or out of range."""


# ---------------------------------------------------------------------------
# Spec dataclasses


@dataclass(frozen=True)
class ModelSpec:
    builder: str  # "package.module:attr" or "package.module.attr"
    tokenizer: str = ""  # same format; "" = builder provides its own
    vocab_size: int = 256
    n_layer: int = 4
    n_head: int = 4
    n_kv_head: int = 0  # 0 = fall back to n_head (no grouped-query attention)
    n_embd: int = 128
    block_size: int = 128
    dropout: float = 0.0


@dataclass(frozen=True)
class DataSpec:
    train_manifest: str
    val_manifest: str
    test_manifest: str = ""
    batch_size: int = 32
    max_seq_len: int = 128
    shuffle_seed: int = 1337
    mix: tuple = field(default_factory=tuple)  # ({manifest, weight}, ...)


@dataclass(frozen=True)
class ScheduleSpec:
    steps: int = 1000
    learning_rate: float = 3.0e-4
    warmup_steps: int = 100
    lr_min: float = 3.0e-5
    weight_decay: float = 0.0
    grad_clip: float = 1.0
    log_every: int = 25
    # Judgment: stop after this many evals with no held-out improvement
    # (0 = disabled; the run always trains the full schedule).
    early_stop_patience: int = 0
    # Minimum held-out NLL drop that counts as an improvement.
    early_stop_min_delta: float = 0.0


@dataclass(frozen=True)
class EvalSpec:
    every_steps: int = 250
    probes_path: str = ""
    baseline_checkpoint: str = ""
    max_val_batches: int = 50


@dataclass(frozen=True)
class CheckpointSpec:
    dir: str = "weights/v2"
    save_every: int = 250
    keep_last: int = 5
    # The keeper's law, encoded: never delete the best self. The
    # lowest-held-out-NLL checkpoint is protected from pruning even when
    # newer, worse checkpoints push it out of the keep_last window.
    keep_best: bool = True


@dataclass(frozen=True)
class TrainConfig:
    name: str
    seed: int
    model: ModelSpec
    data: DataSpec
    schedule: ScheduleSpec = field(default_factory=ScheduleSpec)
    eval: EvalSpec = field(default_factory=EvalSpec)
    checkpointing: CheckpointSpec = field(default_factory=CheckpointSpec)


# ---------------------------------------------------------------------------
# Validation helpers


def _req(mapping: dict, key: str, where: str) -> Any:
    if key not in mapping:
        raise ConfigError(f"config[{where}]: missing required key '{key}'")
    return mapping[key]


def _check_int(value: Any, key: str, where: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"config[{where}].{key}: expected int, got {value!r}")
    if value < minimum:
        raise ConfigError(f"config[{where}].{key}: expected >= {minimum}, got {value}")
    return value


def _check_float(value: Any, key: str, where: str, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"config[{where}].{key}: expected number, got {value!r}")
    value = float(value)
    if value < minimum:
        raise ConfigError(f"config[{where}].{key}: expected >= {minimum}, got {value}")
    return value


def _check_str(value: Any, key: str, where: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ConfigError(f"config[{where}].{key}: expected non-empty str")
    return value


def _check_bool(value: Any, key: str, where: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"config[{where}].{key}: expected bool, got {value!r}")
    return value


def _reject_unknown(raw: dict, known: set[str], where: str) -> None:
    """Fail loudly on misspelled/unsupported keys instead of ignoring them.

    A silently-ignored key (e.g. ``probes`` instead of ``probes_path``)
    means the operator's intent never takes effect — that must be an
    error, not a default.
    """
    extra = sorted(set(raw) - known)
    if extra:
        raise ConfigError(
            f"config[{where}]: unknown key(s) {extra}; known keys: {sorted(known)}"
        )


def _model_spec(raw: Any) -> ModelSpec:
    if not isinstance(raw, dict):
        raise ConfigError("config[model]: expected a mapping")
    _reject_unknown(
        raw,
        {
            "builder",
            "tokenizer",
            "vocab_size",
            "n_layer",
            "n_head",
            "n_kv_head",
            "n_embd",
            "block_size",
            "dropout",
        },
        "model",
    )
    builder = _check_str(_req(raw, "builder", "model"), "builder", "model")
    _validate_import_path(builder, "model.builder")
    return ModelSpec(
        builder=builder,
        tokenizer=_check_str(
            raw.get("tokenizer", ""), "tokenizer", "model", allow_empty=True
        ),
        vocab_size=_check_int(raw.get("vocab_size", 256), "vocab_size", "model"),
        n_layer=_check_int(raw.get("n_layer", 4), "n_layer", "model"),
        n_head=_check_int(raw.get("n_head", 4), "n_head", "model"),
        n_kv_head=_check_int(raw.get("n_kv_head", 0), "n_kv_head", "model", minimum=0),
        n_embd=_check_int(raw.get("n_embd", 128), "n_embd", "model"),
        block_size=_check_int(raw.get("block_size", 128), "block_size", "model"),
        dropout=_check_float(raw.get("dropout", 0.0), "dropout", "model"),
    )


def _data_spec(raw: Any) -> DataSpec:
    if not isinstance(raw, dict):
        raise ConfigError("config[data]: expected a mapping")
    _reject_unknown(
        raw,
        {
            "train_manifest",
            "val_manifest",
            "test_manifest",
            "batch_size",
            "max_seq_len",
            "shuffle_seed",
            "mix",
        },
        "data",
    )
    mix_raw = raw.get("mix", [])
    if not isinstance(mix_raw, list):
        raise ConfigError("config[data].mix: expected a list of {manifest, weight}")
    mix = []
    total = 0.0
    for i, entry in enumerate(mix_raw):
        where = f"data.mix[{i}]"
        if not isinstance(entry, dict):
            raise ConfigError(f"config[{where}]: expected a mapping")
        _reject_unknown(entry, {"manifest", "weight"}, where)
        manifest = _check_str(_req(entry, "manifest", where), "manifest", where)
        weight = _check_float(
            _req(entry, "weight", where), "weight", where, minimum=0.0
        )
        mix.append({"manifest": manifest, "weight": weight})
        total += weight
    if mix and total <= 0.0:
        raise ConfigError("config[data].mix: weights sum to 0")
    return DataSpec(
        train_manifest=_check_str(
            _req(raw, "train_manifest", "data"), "train_manifest", "data"
        ),
        val_manifest=_check_str(
            _req(raw, "val_manifest", "data"), "val_manifest", "data"
        ),
        test_manifest=_check_str(
            raw.get("test_manifest", ""), "test_manifest", "data", allow_empty=True
        ),
        batch_size=_check_int(raw.get("batch_size", 32), "batch_size", "data"),
        max_seq_len=_check_int(raw.get("max_seq_len", 128), "max_seq_len", "data"),
        shuffle_seed=_check_int(
            raw.get("shuffle_seed", 1337), "shuffle_seed", "data", minimum=0
        ),
        mix=tuple(mix),
    )


def _schedule_spec(raw: Any) -> ScheduleSpec:
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ConfigError("config[schedule]: expected a mapping")
    _reject_unknown(
        raw,
        {
            "steps",
            "learning_rate",
            "warmup_steps",
            "lr_min",
            "weight_decay",
            "grad_clip",
            "log_every",
            "early_stop_patience",
            "early_stop_min_delta",
        },
        "schedule",
    )
    lr = _check_float(
        raw.get("learning_rate", 3.0e-4), "learning_rate", "schedule", minimum=0.0
    )
    if lr == 0.0:
        raise ConfigError("config[schedule].learning_rate: must be > 0")
    return ScheduleSpec(
        steps=_check_int(raw.get("steps", 1000), "steps", "schedule"),
        learning_rate=lr,
        warmup_steps=_check_int(
            raw.get("warmup_steps", 100), "warmup_steps", "schedule", minimum=0
        ),
        lr_min=_check_float(raw.get("lr_min", 3.0e-5), "lr_min", "schedule"),
        weight_decay=_check_float(
            raw.get("weight_decay", 0.0), "weight_decay", "schedule"
        ),
        grad_clip=_check_float(raw.get("grad_clip", 1.0), "grad_clip", "schedule"),
        log_every=_check_int(raw.get("log_every", 25), "log_every", "schedule"),
        early_stop_patience=_check_int(
            raw.get("early_stop_patience", 0),
            "early_stop_patience",
            "schedule",
            minimum=0,
        ),
        early_stop_min_delta=_check_float(
            raw.get("early_stop_min_delta", 0.0), "early_stop_min_delta", "schedule"
        ),
    )


def _eval_spec(raw: Any) -> EvalSpec:
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ConfigError("config[eval]: expected a mapping")
    _reject_unknown(
        raw,
        {"every_steps", "probes_path", "baseline_checkpoint", "max_val_batches"},
        "eval",
    )
    return EvalSpec(
        every_steps=_check_int(raw.get("every_steps", 250), "every_steps", "eval"),
        probes_path=_check_str(
            raw.get("probes_path", ""), "probes_path", "eval", allow_empty=True
        ),
        baseline_checkpoint=_check_str(
            raw.get("baseline_checkpoint", ""),
            "baseline_checkpoint",
            "eval",
            allow_empty=True,
        ),
        max_val_batches=_check_int(
            raw.get("max_val_batches", 50), "max_val_batches", "eval"
        ),
    )


def _checkpoint_spec(raw: Any) -> CheckpointSpec:
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ConfigError("config[checkpointing]: expected a mapping")
    _reject_unknown(
        raw, {"dir", "save_every", "keep_last", "keep_best"}, "checkpointing"
    )
    return CheckpointSpec(
        dir=_check_str(raw.get("dir", "weights/v2"), "dir", "checkpointing"),
        save_every=_check_int(
            raw.get("save_every", 250), "save_every", "checkpointing"
        ),
        keep_last=_check_int(raw.get("keep_last", 5), "keep_last", "checkpointing"),
        keep_best=_check_bool(raw.get("keep_best", True), "keep_best", "checkpointing"),
    )


# ---------------------------------------------------------------------------
# Loading


def load_config(path: str | Path) -> TrainConfig:
    """Load and validate a v2 training YAML config.

    Raises :class:`ConfigError` with a field-naming message on any problem.
    """
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"config {path}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"config {path}: top level must be a mapping")
    _reject_unknown(
        raw,
        {"name", "seed", "model", "data", "schedule", "eval", "checkpointing"},
        "top",
    )
    name = _check_str(_req(raw, "name", "top"), "name", "top")
    seed = _check_int(_req(raw, "seed", "top"), "seed", "top", minimum=0)
    return TrainConfig(
        name=name,
        seed=seed,
        model=_model_spec(_req(raw, "model", "top")),
        data=_data_spec(_req(raw, "data", "top")),
        schedule=_schedule_spec(raw.get("schedule")),
        eval=_eval_spec(raw.get("eval")),
        checkpointing=_checkpoint_spec(raw.get("checkpointing")),
    )


def fingerprint(cfg: TrainConfig) -> str:
    """Stable SHA256 of the canonical config — stored in every checkpoint."""
    canon = json.dumps(asdict(cfg), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Pluggable builders


def _validate_import_path(path: str, where: str) -> None:
    """Check the path parses as ``pkg.mod:attr`` or ``pkg.mod.attr``."""
    if ":" in path:
        mod, _, attr = path.partition(":")
    else:
        mod, _, attr = path.rpartition(".")
    if (
        not mod
        or not attr
        or not all(part.isidentifier() for part in mod.split(".") + [attr])
    ):
        raise ConfigError(
            f"config[{where}]: '{path}' is not a valid import path "
            "(expected 'package.module:attr' or 'package.module.attr')"
        )


def resolve_builder(path: str) -> Callable[..., Any]:
    """Import and return the callable at ``path``.

    The model builder is called as ``builder(model_spec_dict)`` and must
    return an object with ``logits_for_batch(prefixes) -> np.ndarray (B, V)``.
    The tokenizer builder takes no arguments and returns an object with
    ``encode`` / ``decode`` / ``vocab_size``.
    """
    _validate_import_path(path, "builder")
    if ":" in path:
        mod_name, _, attr = path.partition(":")
    else:
        mod_name, _, attr = path.rpartition(".")
    try:
        module = importlib.import_module(mod_name)
    except ImportError as exc:
        raise ConfigError(
            f"builder '{path}': cannot import module '{mod_name}': {exc}"
        ) from exc
    try:
        target = getattr(module, attr)
    except AttributeError as exc:
        raise ConfigError(
            f"builder '{path}': module '{mod_name}' has no attribute '{attr}'"
        ) from exc
    if not callable(target):
        raise ConfigError(f"builder '{path}': '{attr}' is not callable")
    return target
