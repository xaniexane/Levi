"""Hermetic tests for LEVI native brain v2: model, tokenizer, data pipeline.

torch-dependent tests skip cleanly when torch is unavailable (same pattern
as test_brain_train.py). Everything is synthetic and CPU-tiny; no corpus
files, no network, no PII.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip(
    "torch", reason="torch not installed; v2 brain modules need it"
)
import torch.nn.functional as F  # noqa: E402

TRAIN_DIR = Path(__file__).resolve().parent.parent / "core" / "levi" / "brain" / "train"
sys.path.insert(0, str(TRAIN_DIR))

import data_pipe  # noqa: E402
import model_v2  # noqa: E402
import tok as tok_mod  # noqa: E402
from data_pipe import Curriculum, DataPipeline, doc_boundary_mask  # noqa: E402
from model_v2 import build_model, load_checkpoint, save_checkpoint  # noqa: E402
from tok import ByteBPETokenizer  # noqa: E402


# ---------------------------------------------------------------- fixtures


def _synthetic_texts(n: int = 300, seed: int = 7) -> list[str]:
    rng = random.Random(seed)
    words = [
        "the",
        "levi",
        "brain",
        "defense",
        "detection",
        "hardening",
        "network",
        "system",
        "policy",
        "analysis",
        "kernel",
        "signal",
    ]
    return [
        " ".join(rng.choice(words) for _ in range(rng.randint(8, 40))) for _ in range(n)
    ]


@pytest.fixture(scope="module")
def tokenizer() -> ByteBPETokenizer:
    return ByteBPETokenizer.train(_synthetic_texts(), vocab_size=320, verbose=False)


@pytest.fixture()
def jsonl_corpus(tmp_path: Path) -> Path:
    path = tmp_path / "corpus.jsonl"
    docs = [
        ("doc-0", "alpha alpha alpha operating systems manage hardware"),
        ("doc-1", "beta beta compilers translate source code to machine"),
        ("doc-2", "gamma gamma networks route packets across machines"),
        ("doc-3", "delta delta databases store and index records"),
        ("doc-4", "epsilon learning models minimize loss functions"),
        ("doc-5", "zeta zeta cryptography protects data in transit"),
        ("doc-6", "eta eta schedulers allocate cpu time fairly"),
        ("doc-7", "theta theta filesystems organize bytes on disk"),
    ]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n")  # blank line: must be skipped gracefully
        for did, text in docs:
            fh.write(json.dumps({"id": did, "text": text}) + "\n")
        fh.write(json.dumps({"id": "doc-empty", "text": ""}) + "\n")  # skipped
        fh.write("not json at all\n")  # skipped by the planner
    return path


TINY_CFG = {
    "vocab_size": 320,
    "n_layer": 2,
    "n_head": 4,
    "n_kv_head": 4,
    "n_embd": 64,
    "block_size": 32,
    "tie_weights": True,
}


# ---------------------------------------------------------------- tokenizer


def test_bpe_trains_to_requested_vocab(tokenizer: ByteBPETokenizer):
    assert 260 < tokenizer.vocab_size <= 320


def test_tokenizer_roundtrip_synthetic(tokenizer: ByteBPETokenizer):
    s = "the levi brain: detection wörld 🌍\n\ttabbed — “quoted”\r\n"
    assert tokenizer.decode(tokenizer.encode(s)) == s


def test_tokenizer_roundtrip_all_bytes(tokenizer: ByteBPETokenizer):
    s = "".join(chr(b) for b in range(1, 256))  # every byte value but NUL
    assert tokenizer.decode(tokenizer.encode(s)) == s
    assert tokenizer.encode("") == []
    assert tokenizer.decode([]) == ""


def test_encode_never_emits_specials(tokenizer: ByteBPETokenizer):
    ids = tokenizer.encode("some ordinary text with wörds")
    assert not ({256, 257, 258, 259} & set(ids))
    # but the pipeline may insert them; decode renders them as markers
    assert tokenizer.decode([tokenizer.doc_id, 65, tokenizer.eod_id]) == "<doc>A<eod>"


def test_tokenizer_save_load_roundtrip(tokenizer: ByteBPETokenizer, tmp_path: Path):
    p = tmp_path / "tok.json"
    tokenizer.save(p)
    tok2 = ByteBPETokenizer.load(p)
    assert tok2.vocab_size == tokenizer.vocab_size
    s = "roundtrip after save/load 🌍"
    assert tok2.decode(tok2.encode(s)) == s
    with pytest.raises(ValueError, match="not a levi-bpe-v1"):
        (tmp_path / "wrong.json").write_text('{"format": "nope"}')
        ByteBPETokenizer.load(tmp_path / "wrong.json")


def test_train_from_jsonl(tmp_path: Path):
    p = tmp_path / "c.jsonl"
    with open(p, "w", encoding="utf-8") as fh:
        for t in _synthetic_texts(60):
            fh.write(json.dumps({"text": t}) + "\n")
    tok = ByteBPETokenizer.train_from_jsonl(p, vocab_size=300, verbose=False)
    assert 260 < tok.vocab_size <= 300
    assert tok.decode(tok.encode("the brain")) == "the brain"


def test_learned_merges_compress(tokenizer: ByteBPETokenizer):
    # trained merges must actually fire: frequent words -> single tokens
    ids = tokenizer.encode("the")
    assert len(ids) == 1 and ids[0] >= 260


# ---------------------------------------------------------------- model


def test_forward_shapes():
    torch.manual_seed(0)
    model = build_model(TINY_CFG)
    model.eval()
    x = torch.randint(0, TINY_CFG["vocab_size"], (2, 16))
    with torch.no_grad():
        logits = model(x)
    assert logits.shape == (2, 16, TINY_CFG["vocab_size"])
    assert torch.isfinite(logits).all()


def test_default_param_count_in_expected_range():
    n = build_model(None).n_params()
    assert 8_000_000 <= n <= 15_000_000, f"default v2 model has {n:,} params"


def test_weight_tying():
    tied = build_model({**TINY_CFG, "tie_weights": True})
    assert tied.head.weight is tied.tok_emb.weight
    untied = build_model({**TINY_CFG, "tie_weights": False})
    assert untied.head.weight is not untied.tok_emb.weight
    assert untied.n_params() > tied.n_params()


def test_rope_makes_position_matter():
    torch.manual_seed(1)
    model = build_model(TINY_CFG)
    model.eval()
    idx = torch.full((1, 8), 7, dtype=torch.long)  # same token everywhere
    with torch.no_grad():
        logits = model(idx)
    # identical tokens at different positions must produce different outputs
    assert not torch.allclose(logits[0, 0], logits[0, 7])
    # shorter-than-block sequences are fine; longer ones are rejected loudly
    with torch.no_grad():
        assert model(torch.zeros((1, 5), dtype=torch.long)).shape[1] == 5
    with pytest.raises(ValueError):
        model(torch.zeros((1, TINY_CFG["block_size"] + 1), dtype=torch.long))


def test_gqa_config_runs():
    cfg = {**TINY_CFG, "n_kv_head": 2}
    model = build_model(cfg)
    x = torch.randint(0, cfg["vocab_size"], (2, 10))
    assert model(x).shape == (2, 10, cfg["vocab_size"])
    with pytest.raises(ValueError):
        build_model({**TINY_CFG, "n_head": 5})  # 64 % 5 != 0


def test_gradient_checkpointing_forward_backward():
    cfg = {**TINY_CFG, "gradient_checkpointing": True}
    model = build_model(cfg)
    model.train()
    x = torch.randint(0, cfg["vocab_size"], (2, 12))
    y = torch.randint(0, cfg["vocab_size"], (2, 12))
    loss = F.cross_entropy(model(x).view(-1, cfg["vocab_size"]), y.view(-1))
    loss.backward()
    assert all(p.grad is not None for p in model.parameters() if p.requires_grad)


def test_generate_smoke():
    torch.manual_seed(2)
    model = build_model(TINY_CFG)
    idx = torch.zeros((1, 4), dtype=torch.long)
    out = model.generate(idx, max_new=6, temperature=0.0)
    assert out.shape == (1, 10)
    assert (out < TINY_CFG["vocab_size"]).all()


# ---------------------------------------------------------------- checkpoint


def test_checkpoint_save_load_roundtrip(tmp_path: Path):
    torch.manual_seed(3)
    model = build_model(TINY_CFG)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    p = tmp_path / "ckpt.pt"
    save_checkpoint(p, model, opt, step=42, extra={"note": "test"})
    fresh = build_model(TINY_CFG)
    ckpt = load_checkpoint(p, fresh)
    assert ckpt["format"] == model_v2.CKPT_FORMAT
    assert ckpt["version"] == model_v2.CKPT_VERSION
    assert ckpt["step"] == 42
    assert ckpt["extra"] == {"note": "test"}
    assert ckpt["config"]["n_layer"] == TINY_CFG["n_layer"]
    for (k1, v1), (k2, v2) in zip(
        model.state_dict().items(), fresh.state_dict().items(), strict=True
    ):
        assert k1 == k2 and torch.equal(v1, v2)
    # optimizer state round-trips too
    assert ckpt["optimizer_state"] is not None


def test_checkpoint_rejects_wrong_format(tmp_path: Path):
    bad = tmp_path / "bad.pt"
    torch.save({"format": "something-else", "version": 1}, bad)
    with pytest.raises(ValueError, match="not a levi-brain-v2"):
        load_checkpoint(bad)
    old = tmp_path / "old.pt"
    torch.save({"format": model_v2.CKPT_FORMAT, "version": 999}, old)
    with pytest.raises(ValueError, match="unsupported"):
        load_checkpoint(old)


# ---------------------------------------------------------------- data pipe


def test_doc_boundary_mask_semantics():
    seg = torch.tensor([[0, 0, 0, 1, 1, 2]])
    m = doc_boundary_mask(seg)
    assert m.shape == (1, 1, 6, 6)
    # position 3 (doc 1) sees 3 only of the past; not doc 0, not the future
    assert m[0, 0, 3, 3] == 0.0
    assert m[0, 0, 3, 0] == float("-inf")  # cross-doc, past
    assert m[0, 0, 3, 4] == float("-inf")  # future
    assert m[0, 0, 4, 3] == 0.0  # same doc, past
    assert m[0, 0, 2, 0] == 0.0  # same doc, past
    assert m[0, 0, 2, 3] == float("-inf")  # future


def test_batch_shapes_and_shifted_labels(
    jsonl_corpus: Path, tokenizer: ByteBPETokenizer
):
    pipe = DataPipeline(
        jsonl_corpus, tokenizer, block_size=16, batch_size=2, val_fraction=0.0
    )
    batches = list(pipe.iter_train(shuffle=False))
    assert batches, "expected at least one batch"
    for b in batches:
        assert b["input_ids"].shape == (2, 16)
        assert b["labels"].shape == (2, 16)
        assert b["segment_ids"].shape == (2, 16)
        assert b["attn_mask"].shape == (2, 1, 16, 16)
        # labels are inputs shifted by one within each chunk
        assert torch.equal(b["labels"][:, :-1], b["input_ids"][:, 1:])


def test_doc_boundaries_are_eod_separated(
    jsonl_corpus: Path, tokenizer: ByteBPETokenizer
):
    pipe = DataPipeline(
        jsonl_corpus, tokenizer, block_size=16, batch_size=2, val_fraction=0.0
    )
    stream_t, stream_s = [], []
    for b in pipe.iter_train(shuffle=False):
        for i in range(b["input_ids"].shape[0]):
            stream_t.extend(b["input_ids"][i].tolist())
            stream_s.extend(b["segment_ids"][i].tolist())
    # every document start is preceded by an <eod> (except the very first)
    changes = [i for i in range(1, len(stream_s)) if stream_s[i] != stream_s[i - 1]]
    assert changes, "expected multiple documents in the stream"
    for i in changes:
        assert stream_t[i - 1] == tokenizer.eod_id


def test_isolate_docs_flag(jsonl_corpus: Path, tokenizer: ByteBPETokenizer):
    kw = dict(block_size=16, batch_size=2, val_fraction=0.0)
    iso = next(
        DataPipeline(jsonl_corpus, tokenizer, isolate_docs=True, **kw).iter_train(
            shuffle=False
        )
    )
    plain = next(
        DataPipeline(jsonl_corpus, tokenizer, isolate_docs=False, **kw).iter_train(
            shuffle=False
        )
    )
    assert iso["attn_mask"] is not None
    assert (iso["attn_mask"] == float("-inf")).any()  # real blocking happens
    assert plain["attn_mask"] is None


def test_val_split_deterministic_and_disjoint(
    jsonl_corpus: Path, tokenizer: ByteBPETokenizer
):
    kw = dict(block_size=16, batch_size=2, val_fraction=0.25)
    p1 = DataPipeline(jsonl_corpus, tokenizer, **kw)
    p2 = DataPipeline(jsonl_corpus, tokenizer, **kw)
    assert p1.stats() == p2.stats()
    st = p1.stats()
    assert st["documents"] == 8  # blank/invalid/empty lines excluded
    assert st["train_documents"] + st["val_documents"] == 8
    assert st["val_documents"] >= 1
    plan = p1._build_plan()
    val_ids = {did for _, did, _ in plan if p1._is_val(did)}
    train_ids = {did for _, did, _ in plan if not p1._is_val(did)}
    assert val_ids.isdisjoint(train_ids)
    assert len(val_ids) == st["val_documents"]


def test_curriculum_order(jsonl_corpus: Path, tokenizer: ByteBPETokenizer):
    manifest = {
        "stages": [
            {"name": "stage-b", "doc_ids": ["doc-1"]},
            {"name": "stage-c", "doc_ids": ["doc-0"]},
        ]
    }
    cur = Curriculum(manifest)
    pipe = DataPipeline(
        jsonl_corpus,
        tokenizer,
        block_size=64,
        batch_size=1,
        val_fraction=0.0,
        curriculum=cur,
    )
    assert [s for s in pipe.stats()["curriculum_stages"]] == [-1, 0, 1]
    first = next(pipe.iter_train(shuffle=False))
    ids = first["input_ids"][0].tolist()
    first_doc = tokenizer.decode(ids[: ids.index(tokenizer.eod_id)])
    # unlisted docs (stage -1) stream before any curriculum stage
    assert first_doc.startswith("gamma"), first_doc


def test_pipeline_feeds_model_end_to_end(
    jsonl_corpus: Path, tokenizer: ByteBPETokenizer
):
    torch.manual_seed(4)
    cfg = {**TINY_CFG, "vocab_size": tokenizer.vocab_size}
    model = build_model(cfg)
    pipe = DataPipeline(
        jsonl_corpus, tokenizer, block_size=16, batch_size=2, val_fraction=0.0
    )
    b = next(pipe.iter_train(shuffle=False))
    logits = model(b["input_ids"], b["attn_mask"])
    loss = F.cross_entropy(
        logits.reshape(-1, cfg["vocab_size"]), b["labels"].reshape(-1)
    )
    assert torch.isfinite(loss) and loss.item() > 0
    loss.backward()  # gradients flow through the masked attention path


def test_prepend_doc_token(jsonl_corpus: Path, tokenizer: ByteBPETokenizer):
    pipe = DataPipeline(
        jsonl_corpus,
        tokenizer,
        block_size=64,
        batch_size=1,
        val_fraction=0.0,
        prepend_doc_token=True,
    )
    first = next(pipe.iter_train(shuffle=False))
    assert first["input_ids"][0, 0].item() == tokenizer.doc_id


def test_data_pipe_module_contract():
    # the v2 harness (SCAFFOLD) can rely on these names
    for name in (
        "DataPipeline",
        "Curriculum",
        "doc_boundary_mask",
        "iter_jsonl_docs",
        "stable_hash01",
    ):
        assert hasattr(data_pipe, name), name
    assert tok_mod.FORMAT == "levi-bpe-v1"
    assert model_v2.CKPT_FORMAT == "levi-brain-v2"


# ---------------------------------------------------------------- harness plug-in


def test_build_tokenizer_missing_file_errors_loudly(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LEVI_TOKENIZER_PATH", raising=False)
    monkeypatch.setattr(model_v2, "DEFAULT_TOKENIZER_PATH", tmp_path / "nope.json")
    with pytest.raises(FileNotFoundError, match="train one first"):
        model_v2.build_tokenizer()


def test_build_tokenizer_loads_from_env(
    tokenizer: ByteBPETokenizer, tmp_path: Path, monkeypatch
):
    p = tmp_path / "tok.json"
    tokenizer.save(p)
    monkeypatch.setenv("LEVI_TOKENIZER_PATH", str(p))
    tok = model_v2.build_tokenizer()
    assert tok.vocab_size == tokenizer.vocab_size
    assert tok.decode(tok.encode("hello")) == "hello"
    # explicit path beats the env var
    assert model_v2.build_tokenizer(p).vocab_size == tokenizer.vocab_size


def test_build_model_accepts_harness_spec_dict():
    # the v2 trainer calls build_model with the YAML model: section as a dict
    spec = {
        "vocab_size": 512,
        "n_layer": 2,
        "n_head": 4,
        "n_embd": 64,
        "block_size": 32,
        "dropout": 0.0,
    }
    model = build_model(spec)
    assert model.config["n_layer"] == 2
    assert model.config["tie_weights"] is True  # harness default fills in
    x = torch.randint(0, 512, (1, 8))
    assert model(x).shape == (1, 8, 512)


def test_package_import_matches_direct_import():
    # the harness imports levi.brain.train.model_v2; relative imports of .tok
    # must resolve there too (namespace package, no __init__.py in train/)
    core_dir = Path(__file__).resolve().parent.parent / "core"
    if str(core_dir) not in sys.path:
        sys.path.insert(0, str(core_dir))
    pkg = pytest.importorskip("levi.brain.train.model_v2")
    assert pkg.build_model is not None
    assert pkg.build_tokenizer is not None
    m = pkg.build_model(TINY_CFG)
    assert m.config["n_embd"] == TINY_CFG["n_embd"]


# ---------------------------------------------------------------- v2 checkpoint bridge


def test_v2_checkpoint_bridge_roundtrip(tmp_path: Path):
    pytest.importorskip(
        "levi.brain.train.v2.checkpoint",
        reason="SCAFFOLD v2 checkpoint module not importable",
    )
    torch.manual_seed(5)
    model = build_model(TINY_CFG)
    ckpt_dir = tmp_path / "ckpts"
    path = model_v2.save_v2_checkpoint(
        ckpt_dir, model, step=7, metrics={"loss": 2.5}, config_hash="abc"
    )
    assert path.suffix == ".npz"
    assert (ckpt_dir / "checkpoints.json").is_file()
    fresh = build_model(TINY_CFG)
    ckpt = model_v2.load_v2_checkpoint(path, fresh)
    assert ckpt["step"] == 7
    assert ckpt["metrics"] == {"loss": 2.5}
    assert ckpt["model_config"]["n_layer"] == TINY_CFG["n_layer"]
    for (k1, v1), (k2, v2) in zip(
        model.state_dict().items(), fresh.state_dict().items(), strict=True
    ):
        assert k1 == k2 and torch.equal(v1, v2)


def test_v2_checkpoint_bridge_rejects_arch_mismatch(tmp_path: Path):
    pytest.importorskip(
        "levi.brain.train.v2.checkpoint",
        reason="SCAFFOLD v2 checkpoint module not importable",
    )
    model = build_model(TINY_CFG)
    ckpt_dir = tmp_path / "ckpts"
    path = model_v2.save_v2_checkpoint(ckpt_dir, model, step=1)
    other = build_model({**TINY_CFG, "n_layer": 3})
    with pytest.raises(ValueError, match="architecture mismatch"):
        model_v2.load_v2_checkpoint(path, other)
