"""Hermetic tests for levi.brain.train.v2.trainer.

Only Trainer.run() needs torch; planning, curriculum staging, token streams,
and baseline-report comparison are torch-free and fully tested here. The
end-to-end smoke test skips cleanly when torch is unavailable (same pattern
as test_brain_train.py).
"""

import json
import textwrap

import pytest

from levi.brain.train.v2 import trainer as tr
from levi.brain.train.v2.corpus_manager import (
    PolicyError,
    build_manifest,
    save_manifest,
)
from levi.brain.train.v2.trainer import Trainer, TrainerError, plan_run


class FakeTokenizer:
    def __init__(self, words):
        self._w2i = {w: i for i, w in enumerate(words)}

    @property
    def vocab_size(self):
        return len(self._w2i)

    def eod_id(self):
        return self.vocab_size - 1

    def encode(self, text):
        return [self._w2i[w] for w in text.split()]

    def decode(self, ids):
        inv = {i: w for w, i in self._w2i.items()}
        return " ".join(inv[i] for i in ids)


WORDS = ["the", "cat", "sat", "dog", "ran", "<eod>"]

CONFIG_YAML = textwrap.dedent(
    """\
    name: smoke-v2
    seed: 7
    model:
      builder: "json:loads"
      tokenizer: "json:loads"
    data:
      train_manifest: train.manifest.json
      val_manifest: val.manifest.json
      batch_size: 4
      max_seq_len: 16
    schedule:
      steps: 10
      learning_rate: 0.001
      warmup_steps: 2
      log_every: 5
    eval:
      every_steps: 5
    checkpointing:
      dir: weights/v2
      save_every: 5
      keep_last: 2
    """
)


@pytest.fixture()
def corpus_dir(tmp_path):
    d = tmp_path / "corpora"
    d.mkdir()
    train_texts = [
        "the cat sat",
        "the dog ran",
        "the cat ran",
        "the dog sat",
        "cat dog the sat ran",
    ]
    val_texts = ["the cat sat", "the dog ran"]
    for name, texts in (("train.jsonl", train_texts), ("val.jsonl", val_texts)):
        with open(d / name, "w", encoding="utf-8") as fh:
            for t in texts:
                fh.write(json.dumps({"text": t}) + "\n")
    save_manifest(
        build_manifest("train", "v1", [d / "train.jsonl"], tags=["test"], base_dir=d),
        d / "train.manifest.json",
    )
    save_manifest(
        build_manifest("val", "v1", [d / "val.jsonl"], tags=["test"], base_dir=d),
        d / "val.manifest.json",
    )
    cfg_path = d / "train.yaml"
    cfg_path.write_text(CONFIG_YAML, encoding="utf-8")
    return d


# ---------------------------------------------------------------- planning


def test_plan_run_resolves(corpus_dir, tmp_path):
    plan = plan_run(corpus_dir / "train.yaml", tmp_path / "run")
    assert plan.cfg.name == "smoke-v2"
    assert len(plan.config_hash) == 64
    assert plan.train_sources[0][0].name == "train.manifest.json"
    assert plan.val_manifest.name == "val.manifest.json"
    assert plan.test_manifest is None
    assert plan.ckpt_dir == tmp_path / "run" / "checkpoints"
    assert plan.reports_dir == tmp_path / "run" / "reports"


def test_plan_run_missing_manifest(corpus_dir):
    (corpus_dir / "train.manifest.json").unlink()
    with pytest.raises(TrainerError, match="train manifest"):
        plan_run(corpus_dir / "train.yaml")


def test_plan_run_default_run_dir(corpus_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plan = plan_run(corpus_dir / "train.yaml")
    assert plan.run_dir.parent.name == "runs"
    assert plan.run_dir.name.startswith("smoke-v2-")


# ---------------------------------------------------------------- staging


def test_stage_curriculum(corpus_dir, tmp_path):
    plan = plan_run(corpus_dir / "train.yaml", tmp_path / "run")
    manifest = tr.stage_curriculum(plan)
    assert plan.curriculum_path.is_file()
    assert manifest.name == "smoke-v2-curriculum"
    assert len(manifest.order) == 5
    assert set(manifest.stage_of.values()) <= {0, 1, 2, 3}
    stages = [manifest.stage_of[i] for i in manifest.order]
    assert stages == sorted(stages)


def test_stage_curriculum_rejects_news(corpus_dir, tmp_path):
    d = corpus_dir
    news = d / "news.jsonl"
    news.write_text(
        json.dumps({"text": "breaking news today"}) + "\n", encoding="utf-8"
    )
    with pytest.raises(PolicyError):
        build_manifest("news", "v1", [news], tags=["news"], base_dir=d)


def test_stage_curriculum_no_docs(tmp_path):
    d = tmp_path / "corpora"
    d.mkdir()
    empty = d / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    save_manifest(
        build_manifest("empty", "v1", [empty], tags=["test"], base_dir=d),
        d / "empty.manifest.json",
    )
    cfg = CONFIG_YAML.replace("train.manifest.json", "empty.manifest.json")
    cfg = cfg.replace("val.manifest.json", "empty.manifest.json")
    cfg_path = d / "train.yaml"
    cfg_path.write_text(cfg, encoding="utf-8")
    plan = plan_run(cfg_path, tmp_path / "run")
    with pytest.raises(TrainerError, match="no training docs"):
        tr.stage_curriculum(plan)


# ---------------------------------------------------------------- token streams


def test_build_token_stream_with_eod():
    from levi.brain.train.v2.corpus_manager import Doc, doc_sha256

    tok = FakeTokenizer(WORDS)
    docs = [
        Doc(id=doc_sha256("the cat"), text="the cat"),
        Doc(id=doc_sha256("sat"), text="sat"),
    ]
    ids = tr.build_token_stream(docs, tok)
    assert ids == [0, 1, 5, 2, 5]  # eod between docs


def test_build_token_stream_empty():
    with pytest.raises(TrainerError, match="empty"):
        tr.build_token_stream([], FakeTokenizer(WORDS))


def test_build_token_stream_out_of_vocab():
    from levi.brain.train.v2.corpus_manager import Doc, doc_sha256

    class BadTok(FakeTokenizer):
        def encode(self, text):
            return [999]

    with pytest.raises(TrainerError, match="outside vocab"):
        tr.build_token_stream([Doc(id=doc_sha256("x"), text="x")], BadTok(WORDS))


def test_load_manifest_docs_dedupes(corpus_dir):
    import json as _json

    d = corpus_dir
    dup = d / "dup.jsonl"
    with open(dup, "w", encoding="utf-8") as fh:
        for _ in range(3):
            fh.write(_json.dumps({"text": "the cat sat"}) + "\n")
    mp = d / "dup.manifest.json"
    save_manifest(build_manifest("dup", "v1", [dup], tags=["test"], base_dir=d), mp)
    docs = tr.load_manifest_docs(mp)
    assert len(docs) == 1


# ---------------------------------------------------------------- torch gate


def test_require_torch_error_is_helpful():
    try:
        import torch  # noqa: F401

        pytest.skip("torch is installed; gate not exercised")
    except ImportError:
        pass
    with pytest.raises(TrainerError, match="pip install"):
        tr.require_torch()


def test_run_without_torch_raises_helpfully(corpus_dir, tmp_path):
    try:
        import torch  # noqa: F401

        pytest.skip("torch is installed; gate not exercised")
    except ImportError:
        pass
    plan = plan_run(corpus_dir / "train.yaml", tmp_path / "run")
    with pytest.raises(TrainerError, match="torch is required"):
        Trainer(plan).run()


# ---------------------------------------------------------------- baselines


def _report_dict(name="cand", ppl=80.0, acc=0.6):
    return {
        "model_name": name,
        "perplexity": {"perplexity": ppl},
        "next_token": {"accuracy": acc},
        "topic": {},
    }


def test_attach_baseline_json_report(corpus_dir, tmp_path):
    import dataclasses

    plan = plan_run(corpus_dir / "train.yaml", tmp_path / "run")
    base = tmp_path / "base-report.json"
    base.write_text(
        json.dumps(_report_dict("base", ppl=100.0, acc=0.5)), encoding="utf-8"
    )
    plan.cfg = dataclasses.replace(
        plan.cfg,
        eval=dataclasses.replace(plan.cfg.eval, baseline_checkpoint=str(base)),
    )
    note = Trainer(plan)._attach_baseline(
        None,
        _report_as_evalreport("cand"),
        plan,
        plan.cfg,
        None,
        "cpu",
        [],
        None,
    )
    assert "baseline comparison vs base-report.json" in note
    assert "improved" in note


def _report_as_evalreport(name="cand"):
    from levi.brain.train.v2.eval_harness import EvalReport

    return EvalReport(
        model_name=name,
        step=10,
        perplexity={"perplexity": 80.0},
        next_token={"accuracy": 0.6},
    )


def test_attach_baseline_missing_file(corpus_dir, tmp_path):
    import dataclasses

    plan = plan_run(corpus_dir / "train.yaml", tmp_path / "run")
    cfg = dataclasses.replace(
        plan.cfg,
        eval=dataclasses.replace(plan.cfg.eval, baseline_checkpoint="nope.npz"),
    )
    note = Trainer(plan)._attach_baseline(
        None, _report_as_evalreport(), plan, cfg, None, "cpu", [], None
    )
    assert "not found" in note


def test_attach_baseline_unsupported_format(corpus_dir, tmp_path):
    import dataclasses

    weird = tmp_path / "base.txt"
    weird.write_text("hello", encoding="utf-8")
    plan = plan_run(corpus_dir / "train.yaml", tmp_path / "run")
    cfg = dataclasses.replace(
        plan.cfg,
        eval=dataclasses.replace(plan.cfg.eval, baseline_checkpoint=str(weird)),
    )
    note = Trainer(plan)._attach_baseline(
        None, _report_as_evalreport(), plan, cfg, None, "cpu", [], None
    )
    assert "unsupported format" in note


def test_attach_baseline_absent(corpus_dir, tmp_path):
    plan = plan_run(corpus_dir / "train.yaml", tmp_path / "run")
    note = Trainer(plan)._attach_baseline(
        None, _report_as_evalreport(), plan, plan.cfg, None, "cpu", [], None
    )
    assert note is None


# ---------------------------------------------------------------- CLI


def test_main_stage_only(corpus_dir, tmp_path, capsys):
    rc = tr.main(
        [
            "--config",
            str(corpus_dir / "train.yaml"),
            "--run-dir",
            str(tmp_path / "run"),
            "--stage-only",
        ]
    )
    assert rc == 0
    assert (tmp_path / "run" / "curriculum.json").is_file()
    assert "curriculum stage" in capsys.readouterr().out


def test_main_missing_config(tmp_path):
    rc = tr.main(["--config", str(tmp_path / "nope.yaml")])
    assert rc == 2


# ---------------------------------------------------------------- smoke (torch)


TINY_BUILDERS = textwrap.dedent(
    '''\
    """Tiny torch model + word tokenizer for the trainer smoke test."""
    import torch
    import torch.nn as nn

    WORDS = ["the", "cat", "sat", "dog", "ran", "<eod>"]
    W2I = {w: i for i, w in enumerate(WORDS)}


    class TinyLM(nn.Module):
        def __init__(self, cfg):
            super().__init__()
            self.config = {"block_size": cfg["block_size"],
                           "vocab_size": len(WORDS)}
            self.emb = nn.Embedding(len(WORDS), 16)
            self.head = nn.Linear(16, len(WORDS))

        def forward(self, idx):
            return self.head(self.emb(idx))


    def build_model(cfg):
        return TinyLM(cfg)


    class Tok:
        @property
        def vocab_size(self):
            return len(WORDS)

        def eod_id(self):
            return len(WORDS) - 1

        def encode(self, text):
            return [W2I[w] for w in text.split()]

        def decode(self, ids):
            return " ".join(WORDS[i] for i in ids)


    def build_tokenizer():
        return Tok()
    '''
)

SMOKE_YAML = textwrap.dedent(
    """\
    name: smoke-tiny
    seed: 7
    model:
      builder: "tiny_builders:build_model"
      tokenizer: "tiny_builders:build_tokenizer"
      vocab_size: 6
      block_size: 32
    data:
      train_manifest: train.manifest.json
      val_manifest: val.manifest.json
      batch_size: 4
      max_seq_len: 8
    schedule:
      steps: 6
      learning_rate: 0.01
      warmup_steps: 2
      log_every: 3
    eval:
      every_steps: 3
      probes_path: probes.jsonl
    checkpointing:
      dir: weights/v2
      save_every: 3
      keep_last: 2
    """
)


def test_run_smoke_tiny(corpus_dir, tmp_path, monkeypatch):
    torch = pytest.importorskip("torch", reason="torch not installed")
    assert torch is not None
    (tmp_path / "tiny_builders.py").write_text(TINY_BUILDERS, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    (corpus_dir / "probes.jsonl").write_text(
        json.dumps({"kind": "next_token", "prefix": "the cat", "expected": "sat"})
        + "\n",
        encoding="utf-8",
    )
    (corpus_dir / "smoke.yaml").write_text(SMOKE_YAML, encoding="utf-8")
    plan = plan_run(corpus_dir / "smoke.yaml", tmp_path / "run")
    summary = Trainer(plan).run()
    assert summary["steps"] == 6
    assert summary["final_ema_loss"] > 0
    assert len(summary["reports"]) == 2  # steps 3 and 6
    ckpts = sorted((tmp_path / "run" / "checkpoints").glob("ckpt-*.npz"))
    assert [p.name for p in ckpts] == ["ckpt-000003.npz", "ckpt-000006.npz"]
    report = json.loads(open(summary["reports"][0], encoding="utf-8").read())
    assert report["model_name"] == "smoke-tiny@step3"
    assert report["perplexity"]["n_tokens"] > 0
    # Resume: a second Trainer on the same run dir refuses to re-train —
    # the checkpoint already reached the configured step count.
    plan2 = plan_run(corpus_dir / "smoke.yaml", tmp_path / "run")
    with pytest.raises(TrainerError, match="already at step 6"):
        Trainer(plan2).run()
