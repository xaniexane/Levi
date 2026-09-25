"""Tests for the BPE (subword) training path: tokenizer, BPE intake mode,
round bookkeeping, and the TinyGPT forward pass at BPE vocab size."""

import json
from pathlib import Path

import pytest

# torch is not installed in every environment (e.g. this sandbox). These
# tests genuinely need it (TinyGPT forward pass), so skip the whole module
# when it's absent instead of breaking collection for the entire suite.
torch = pytest.importorskip("torch")

from levi.brain.train import continue_bpe as cb
from levi.brain.train import teacher_intake as ti
from levi.brain.train.tok import ByteBPETokenizer
from levi.brain.train.train import TinyGPT

TRAIN_DIR = Path(ti.__file__).resolve().parent
TOKENIZER_JSON = TRAIN_DIR / "tokenizer.json"

TRICKY = "She said “hi” — with an em dash… émojis 🔥🚀 and 한국어."


def _tok():
    return ByteBPETokenizer.load(TOKENIZER_JSON)


def test_bpe_tokenizer_vocab_and_format():
    tok = _tok()
    assert tok.vocab_size == 8192
    assert len(tok.merges) == 8192 - 260
    assert (tok.pad_id, tok.doc_id, tok.eod_id) == (256, 257, 258)


def test_bpe_roundtrip_lossless_on_tricky_text():
    tok = _tok()
    ids = tok.encode(TRICKY)
    assert tok.decode(ids) == TRICKY
    # subword compression: fewer tokens than characters on prose
    assert len(ids) < len(TRICKY)


def test_bpe_encode_never_emits_specials():
    tok = _tok()
    ids = tok.encode("User: hello\nLEVI: hi <eod> <doc>")
    assert all(i < 256 or i >= 260 for i in ids)


def test_intake_bpe_mode_keeps_full_text():
    rec, stats = ti.intake_record(
        "qwen", "Say “hi” 🔥", "LEVI says “hi” back 🔥", mode="bpe"
    )
    assert "“hi” 🔥" in rec["text"]  # zero crushing: curly quotes + emoji kept
    assert rec["tokenizer"] == "levi-bpe-v1"
    assert stats["mapped"] == 0 and stats["dropped"] == 0


def test_intake_bpe_mode_still_enforces_identity_law():
    with pytest.raises(ti.Rejected):
        ti.intake_record("kimi", "hello there", "I feel happy today", mode="bpe")


def test_intake_char_mode_still_default_and_needs_vocab():
    with pytest.raises(ti.Rejected):
        ti.intake_record("kimi", "hello there", "hi back", mode="char")
    # explicit vocab keeps the old behavior working
    rec, _ = ti.intake_record(
        "kimi", "hello there", "hi back", set("abcdefghijklmnopqrstuvwxyz \n")
    )
    assert rec["text"].startswith("User: ")


def test_intake_run_bpe_mode_report(tmp_path):
    pastes = tmp_path / "pastes.jsonl"
    pastes.write_text(
        json.dumps(
            {
                "teacher": "deepseek",
                "prompt": "hi “there” 🔥",
                "response": "hello “back” 🔥",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "records.jsonl"
    report = ti.run(pastes, out, mode="bpe")
    assert report["mode"] == "bpe"
    assert report["records_out"] == 1 and report["chars_dropped"] == 0
    rec = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert "🔥" in rec["text"] and rec["tokenizer"] == "levi-bpe-v1"


def test_tinygpt_forward_at_bpe_vocab_size():
    torch.manual_seed(0)
    model = TinyGPT(8192, n_layer=1, n_head=2, n_embd=32, block_size=16)
    x = torch.randint(0, 8192, (2, 16))
    logits = model(x)
    assert logits.shape == (2, 16, 8192)
    assert torch.isfinite(logits).all()


def test_bpe_encode_corpus_inserts_eod_markers():
    tok = _tok()
    data = cb.encode_corpus(tok, ["ab", "cd"])
    ids = data.tolist()
    assert ids[-1] == tok.eod_id and ids.count(tok.eod_id) == 2
    assert tok.decode([i for i in ids if i != tok.eod_id]) == "abcd"


def test_arch_match_rejects_mismatched_checkpoint():
    tok = _tok()
    config = {
        "vocab_size": tok.vocab_size,
        "n_layer": 2,
        "n_head": 2,
        "n_embd": 128,
        "block_size": 64,
    }
    good = {
        "tokenizer": "levi-bpe-v1",
        "vocab_size": 8192,
        "arch": dict(config, vocab_size=8192),
    }
    assert cb._check_arch_match(good, config) is None
    bad = dict(good, arch={**good["arch"], "n_embd": 256})
    assert "n_embd" in cb._check_arch_match(bad, config)
    bad_vocab = dict(good, vocab_size=162)
    assert "vocab" in cb._check_arch_match(bad_vocab, config)


def test_last_round_reads_manifest(tmp_path):
    assert cb._last_round(tmp_path) == 0
    (tmp_path / "rounds.jsonl").write_text(
        '{"round": 1}\n{"round": 3}\n', encoding="utf-8"
    )
    assert cb._last_round(tmp_path) == 3


def test_resume_with_no_checkpoint_aborts_loudly(tmp_path, capsys):
    """Fail-closed: --resume with an empty staging dir must abort, never
    silently start a fresh random model (the Drive-not-mounted case)."""
    rc = cb.main(
        [
            "--resume",
            "--steps",
            "2",
            "--staging",
            str(tmp_path / "empty-staging"),
        ]
    )
    assert rc == 2
    assert "ABORT" in capsys.readouterr().out


def test_load_resume_ckpt_falls_back_to_older(tmp_path):
    """A corrupt newest checkpoint (kill mid-write that beat os.replace is
    impossible, but a truncated copy is) must fall back to the older one."""
    staging = tmp_path / "staging"
    staging.mkdir()
    torch.save(
        {"step": 10, "tokenizer": "levi-bpe-v1"},
        staging / "tiny-gpt-bpe-ckpt-000010.pt",
    )
    (staging / "tiny-gpt-bpe-ckpt-000025.pt").write_bytes(b"not a checkpoint")
    ckpt, err = cb._load_resume_ckpt(staging, torch.device("cpu"))
    assert err is None and ckpt["step"] == 10


def test_load_resume_ckpt_all_corrupt(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "tiny-gpt-bpe-ckpt-000025.pt").write_bytes(b"garbage")
    ckpt, err = cb._load_resume_ckpt(staging, torch.device("cpu"))
    assert ckpt is None and "garbage" not in err and err != ""


def test_resume_bumps_round_after_kill(tmp_path, capsys):
    """Simulate a killed round 1: manifest empty, checkpoint says round 1 /
    step 5. --resume must become round 2 and continue at step 6 — the
    zero-manual-repair path, exercised for real (not mocked)."""
    from argparse import Namespace

    staging = tmp_path / "staging"
    staging.mkdir()
    torch.manual_seed(0)
    cfg = {
        "vocab_size": 8192,
        "n_layer": 1,
        "n_head": 2,
        "n_embd": 16,
        "block_size": 8,
        "tokenizer": "levi-bpe-v1",
    }
    model = TinyGPT(8192, n_layer=1, n_head=2, n_embd=16, block_size=8)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4)
    cb._save_ckpt(
        staging,
        5,
        model,
        opt,
        cfg,
        Namespace(steps=2, lr=3e-4, seed=0),
        9.0,
        "levi-bpe-v1",
        round_no=1,
    )
    rc = cb.main(
        [
            "--resume",
            "--steps",
            "2",
            "--staging",
            str(staging),
            "--n-layer",
            "1",
            "--n-head",
            "2",
            "--n-embd",
            "16",
            "--block-size",
            "8",
            "--batch-size",
            "4",
            "--ckpt-every",
            "2",
            "--seed",
            "0",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "round 2: resuming from step 5" in out
    assert "steps 6..7" in out
    manifest = [
        json.loads(line)
        for line in (staging / "rounds.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert manifest[-1]["round"] == 2 and manifest[-1]["steps"] == [6, 7]
    log_rounds = {
        json.loads(line)["round"]
        for line in (staging / "bpe_loss.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    }
    assert log_rounds == {2}


def test_load_resume_ckpt_ignores_tmp_leftovers(tmp_path):
    """A leftover .pt.tmp (kill during checkpoint write) must never be
    mistaken for a checkpoint; the last complete .pt still loads."""
    staging = tmp_path / "staging"
    staging.mkdir()
    torch.save({"step": 3}, staging / "tiny-gpt-bpe-ckpt-000003.pt")
    (staging / "tiny-gpt-bpe-ckpt-000010.pt.tmp").write_bytes(b"partial write")
    ckpt, err = cb._load_resume_ckpt(staging, torch.device("cpu"))
    assert err is None and ckpt["step"] == 3


def test_no_resume_no_fresh_with_checkpoints_aborts(tmp_path, capsys):
    """Fail-closed: a forgotten --resume must never silently start a fresh
    random lineage next to good checkpoints; --fresh is the override."""
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "tiny-gpt-bpe-ckpt-000025.pt").write_bytes(b"fake")
    rc = cb.main(["--steps", "2", "--staging", str(staging)])
    assert rc == 2
    assert "--fresh" in capsys.readouterr().out
