"""Hermetic tests for the continued-training hardening (continue.py).

- _latest_ckpt: newest-first discovery, None when empty.
- _save_ckpt: writes a loadable checkpoint, prunes to the 2 newest.
- carve_heldout: deterministic (byte-identical across runs), stratified,
  disjoint train/heldout splits.

All fixtures are synthetic tmp dirs — never the real weights dir.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

# torch is not installed in every environment (e.g. this sandbox). These
# tests genuinely need it (checkpoint save/load round-trips), so skip the
# whole module when it's absent instead of breaking collection for the
# entire suite.
torch = pytest.importorskip("torch")

REPO = Path(__file__).resolve().parents[1]
TRAIN = REPO / "core" / "levi" / "brain" / "train"

sys.path.insert(0, str(TRAIN))


def _load_continue():
    spec = importlib.util.spec_from_file_location("continue_mod", TRAIN / "continue.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_carver():
    spec = importlib.util.spec_from_file_location("carve_heldout", TRAIN / "carve_heldout.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cont():
    return _load_continue()


def _tiny_model(cont):
    from train import TinyGPT

    model = TinyGPT(8, n_layer=1, n_head=1, n_embd=8, block_size=8)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-4)
    chars = [chr(ord("a") + i) for i in range(8)]
    config = {"n_layer": 1, "n_head": 1, "n_embd": 8, "block_size": 8}
    return model, opt, chars, config


class _Args:
    steps = 600
    lr = 1e-4
    dialog_ratio = 0.5
    seed = 20260921


def test_latest_ckpt_none_when_empty(cont, tmp_path):
    assert cont._latest_ckpt(tmp_path) is None


def test_save_and_latest_ckpt(cont, tmp_path):
    model, opt, chars, config = _tiny_model(cont)
    cont._save_ckpt(tmp_path, 50, model, opt, chars, config, _Args(), 2.5)
    cont._save_ckpt(tmp_path, 100, model, opt, chars, config, _Args(), 2.5)
    latest = cont._latest_ckpt(tmp_path)
    assert latest is not None
    assert latest.name == "tiny-gpt-continued-ckpt-000100.pt"
    # loadable, carries step + loss_first for the explosion guard
    ckpt = torch.load(latest, map_location="cpu", weights_only=False)
    assert ckpt["step"] == 100
    assert ckpt["loss_first"] == 2.5
    assert "model_state" in ckpt and "optim_state" in ckpt


def test_save_ckpt_prunes_to_two(cont, tmp_path):
    model, opt, chars, config = _tiny_model(cont)
    for step in (50, 100, 150):
        cont._save_ckpt(tmp_path, step, model, opt, chars, config, _Args(), 2.5)
    kept = sorted(p.name for p in tmp_path.glob("tiny-gpt-continued-ckpt-*.pt"))
    assert kept == [
        "tiny-gpt-continued-ckpt-000100.pt",
        "tiny-gpt-continued-ckpt-000150.pt",
    ]


def test_carve_deterministic_and_disjoint(tmp_path):
    carver = _load_carver()
    train_p = TRAIN / "corpus_dialogue_train.jsonl"
    held_p = TRAIN / "corpus_dialogue_heldout.jsonl"
    h1 = hashlib.sha256(train_p.read_bytes()).hexdigest()
    carver.main([])  # re-run; must be byte-identical
    assert hashlib.sha256(train_p.read_bytes()).hexdigest() == h1

    train_recs = [
        json.loads(l) for l in open(train_p, encoding="utf-8") if l.strip()
    ]
    held_recs = [
        json.loads(l) for l in open(held_p, encoding="utf-8") if l.strip()
    ]
    assert len(held_recs) == 20
    assert len(train_recs) == 515
    train_texts = {r["text"] for r in train_recs}
    assert not any(r["text"] in train_texts for r in held_recs), "held-out leaks into train"
    kinds = {r["kind"] for r in held_recs}
    assert kinds == {"dialogue", "lwp_prose"}, f"held-out not stratified: {kinds}"
