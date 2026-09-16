"""Hermetic tests for levi.brain.train.v2.config (stdlib + yaml only)."""

import textwrap

import pytest
import yaml

from levi.brain.train.v2.config import (
    ConfigError,
    fingerprint,
    load_config,
    resolve_builder,
)

VALID_YAML = textwrap.dedent(
    """\
    name: tiny-gpt-v2
    seed: 1337
    model:
      builder: "json:loads"
      tokenizer: "json:loads"
      vocab_size: 256
      n_layer: 2
      n_head: 2
      n_embd: 64
      block_size: 64
      dropout: 0.1
    data:
      train_manifest: corpora/train.manifest.json
      val_manifest: corpora/val.manifest.json
      test_manifest: corpora/test.manifest.json
      batch_size: 16
      max_seq_len: 64
      shuffle_seed: 7
      mix:
        - {manifest: corpora/a.manifest.json, weight: 0.7}
        - {manifest: corpora/b.manifest.json, weight: 0.3}
    schedule:
      steps: 500
      learning_rate: 0.0003
      warmup_steps: 50
      lr_min: 0.00003
      weight_decay: 0.01
      grad_clip: 1.0
      log_every: 10
    eval:
      every_steps: 100
      probes_path: eval/probes.jsonl
      baseline_checkpoint: weights/v1/ckpt.npz
      max_val_batches: 10
    checkpointing:
      dir: weights/v2
      save_every: 100
      keep_last: 3
    """
)


def _write(tmp_path, text=VALID_YAML):
    p = tmp_path / "train.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_valid_config(tmp_path):
    cfg = load_config(_write(tmp_path))
    assert cfg.name == "tiny-gpt-v2"
    assert cfg.seed == 1337
    assert cfg.model.vocab_size == 256
    assert cfg.model.n_layer == 2
    assert cfg.data.batch_size == 16
    assert cfg.data.mix == (
        {"manifest": "corpora/a.manifest.json", "weight": 0.7},
        {"manifest": "corpora/b.manifest.json", "weight": 0.3},
    )
    assert cfg.schedule.steps == 500
    assert cfg.eval.every_steps == 100
    assert cfg.checkpointing.keep_last == 3


def test_defaults_fill_in(tmp_path):
    raw = yaml.safe_load(VALID_YAML)
    del raw["schedule"]
    del raw["eval"]
    del raw["checkpointing"]
    del raw["data"]["mix"]
    del raw["data"]["test_manifest"]
    p = tmp_path / "t.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    cfg = load_config(p)
    assert cfg.schedule.steps == 1000
    assert cfg.eval.every_steps == 250
    assert cfg.checkpointing.dir == "weights/v2"
    assert cfg.data.mix == ()
    assert cfg.data.test_manifest == ""


@pytest.mark.parametrize(
    "mutate, field",
    [
        (lambda r: r.pop("name"), "name"),
        (lambda r: r.pop("model"), "model"),
        (lambda r: r.pop("data"), "data"),
        (lambda r: r.pop("seed"), "seed"),
        (lambda r: r["model"].pop("builder"), "builder"),
        (lambda r: r["data"].pop("train_manifest"), "train_manifest"),
    ],
)
def test_missing_required_key(tmp_path, mutate, field):
    raw = yaml.safe_load(VALID_YAML)
    mutate(raw)
    p = tmp_path / "t.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ConfigError, match=field):
        load_config(p)


@pytest.mark.parametrize(
    "section, key, bad",
    [
        ("schedule", "steps", 0),
        ("schedule", "steps", -5),
        ("schedule", "learning_rate", 0.0),
        ("schedule", "learning_rate", -0.1),
        ("schedule", "learning_rate", "fast"),
        ("model", "vocab_size", 0),
        ("model", "n_head", True),
        ("data", "batch_size", 0),
        ("checkpointing", "keep_last", 0),
        ("eval", "max_val_batches", -1),
    ],
)
def test_out_of_range_rejected(tmp_path, section, key, bad):
    raw = yaml.safe_load(VALID_YAML)
    raw[section][key] = bad
    p = tmp_path / "t.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ConfigError, match=key):
        load_config(p)


def test_bad_mix_weights_rejected(tmp_path):
    raw = yaml.safe_load(VALID_YAML)
    raw["data"]["mix"] = [
        {"manifest": "a.json", "weight": 0.0},
        {"manifest": "b.json", "weight": 0.0},
    ]
    p = tmp_path / "t.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ConfigError, match="sum to 0"):
        load_config(p)


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_invalid_yaml(tmp_path):
    p = tmp_path / "t.yaml"
    p.write_text("name: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(p)


def test_top_level_not_mapping(tmp_path):
    p = tmp_path / "t.yaml"
    p.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        load_config(p)


@pytest.mark.parametrize("bad", ["", "   ", "not a path!!", "mod:", ":attr"])
def test_bad_builder_path_rejected(tmp_path, bad):
    raw = yaml.safe_load(VALID_YAML)
    raw["model"]["builder"] = bad or "x"  # "" handled separately below
    if not bad.strip():
        pytest.skip("empty builder covered by non-empty-str check")
    p = tmp_path / "t.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(p)


def test_empty_builder_rejected(tmp_path):
    raw = yaml.safe_load(VALID_YAML)
    raw["model"]["builder"] = ""
    p = tmp_path / "t.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ConfigError, match="builder"):
        load_config(p)


def test_fingerprint_stable(tmp_path):
    cfg = load_config(_write(tmp_path))
    assert fingerprint(cfg) == fingerprint(load_config(_write(tmp_path)))
    assert len(fingerprint(cfg)) == 64


def test_resolve_builder_colon_form():
    import json

    assert resolve_builder("json:loads") is json.loads


def test_resolve_builder_dotted_form():
    import json

    assert resolve_builder("json.loads") is json.loads


def test_resolve_builder_missing_module():
    with pytest.raises(ConfigError, match="cannot import"):
        resolve_builder("no_such_module_xyz:thing")


def test_resolve_builder_missing_attr():
    with pytest.raises(ConfigError, match="no attribute"):
        resolve_builder("json:no_such_attr_xyz")


def test_resolve_builder_not_callable():
    with pytest.raises(ConfigError, match="not callable"):
        resolve_builder("json:__name__")
