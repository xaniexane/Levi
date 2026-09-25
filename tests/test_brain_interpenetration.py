"""Tests for the brain interpenetration prototype.

Hermetic: no network, no daemons, no user HOME writes. Reads the
committed portable weight export (repo-relative) and operates on
in-memory copies only — the original weights are never modified.

Proves: ternary round-trip fidelity + measured size cut +
determinism; growable add/prune keeps the forward working with
correct shapes; the streaming skeleton runs a few steps cleanly.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

from levi.brain import growable, runtime, stream1, ternary

WEIGHTS_PORTABLE = (
    Path(__file__).resolve().parent.parent
    / "core" / "levi" / "brain" / "weights" / "tiny-gpt-portable"
)


@pytest.fixture(scope="module")
def bundle():
    manifest, blobs = runtime.load_portable_tensors(str(WEIGHTS_PORTABLE))
    cfg = manifest["config"]
    chars = manifest["chars"]
    req = runtime._required_tensors(cfg, len(chars))
    params = runtime._params_numpy(blobs, req)
    return manifest, cfg, chars, params


# ---------------------------------------------------------------- ternary


def test_ternary_roundtrip_bounded(bundle):
    _, _, _, params = bundle
    w = params["blocks.0.mlp.0.weight"]
    t = ternary.quantize_ternary(w, "probe")
    back = ternary.dequantize_ternary(t)
    assert back.shape == w.shape
    assert set(np.unique(t.codes)).issubset({-1, 0, 1})
    rel = np.linalg.norm((back - w).ravel()) / np.linalg.norm(w.ravel())
    assert rel < 0.9  # loose honest bound for naive PTQ on a tiny model
    assert 0.0 < t.sparsity < 1.0


def test_ternary_size_reduction_measured(bundle):
    _, _, _, params = bundle
    tern, untouched = ternary.ternarize_state_dict(params)
    rep = ternary.size_report(params, tern)
    assert rep.n_ternarized > 0 and rep.n_untouched > 0
    # Measured on tiny-gpt: ~3.71x at int8, ~11.55x projected at 2-bit.
    assert rep.int8_ratio > 3.0
    assert rep.packed_ratio > 8.0


def test_ternary_determinism(bundle):
    _, _, _, params = bundle
    w = params["blocks.2.attn.qkv.weight"]
    a = ternary.quantize_ternary(w, "d")
    b = ternary.quantize_ternary(w, "d")
    assert np.array_equal(a.codes, b.codes)
    assert a.scale == b.scale


def test_ternary_forward_divergence_reported(bundle):
    _, cfg, chars, params = bundle
    tern, _ = ternary.ternarize_state_dict(params)
    # apply_ternary must not mutate the originals
    before = params["blocks.0.mlp.0.weight"].copy()
    tern_params = ternary.apply_ternary(params, tern)
    assert np.array_equal(params["blocks.0.mlp.0.weight"], before)
    ids = [chars.index(c) for c in "levi is "]
    lo_fp32 = runtime._forward_numpy(params, ids, cfg)
    lo_tern = runtime._forward_numpy(tern_params, ids, cfg)
    div = ternary.divergence(lo_fp32, lo_tern)
    assert np.isfinite(div.mean_abs) and np.isfinite(div.max_abs)
    assert div.mean_abs < 2.0  # measured ~0.82 on this probe
    assert 0.0 <= div.top1_agreement <= 1.0


# ---------------------------------------------------------------- growable


def _manual_mlp(h, w1, b1, w2, b2):
    c = np.sqrt(2.0 / np.pi)
    g = h @ w1.T + b1
    g = 0.5 * g * (1.0 + np.tanh(c * (g + 0.044715 * g**3)))
    return g @ w2.T + b2


@pytest.fixture(scope="module")
def mlp_tensors(bundle):
    _, _, _, params = bundle
    return (
        params["blocks.0.mlp.0.weight"],
        params["blocks.0.mlp.0.bias"],
        params["blocks.0.mlp.2.weight"],
        params["blocks.0.mlp.2.bias"],
    )


def test_growable_single_expert_identity(mlp_tensors):
    w1, b1, w2, b2 = mlp_tensors
    g = growable.GrowableMLP.from_block_tensors(w1, b1, w2, b2, seed=7)
    rng = np.random.RandomState(11)
    h = rng.randn(4, 256).astype(np.float32)
    out = g.forward(h)
    expect = _manual_mlp(h, w1, b1, w2, b2)
    assert out.shape == (4, 256)
    assert np.array_equal(out, expect)  # gating bypassed: bit-identical


def test_growable_add_prune_shapes(mlp_tensors):
    w1, b1, w2, b2 = mlp_tensors
    g = growable.GrowableMLP.from_block_tensors(w1, b1, w2, b2, seed=3)
    assert g.add_expert(seed=101) == 2
    assert g.add_expert(seed=102) == 3
    rng = np.random.RandomState(5)
    h = rng.randn(8, 256).astype(np.float32)
    out = g.forward(h)
    assert out.shape == (8, 256)
    assert np.all(np.isfinite(out))
    assert g.prune_expert() in (0, 1, 2)
    assert g.n_experts == 2
    assert g.prune_expert() is not None
    assert g.n_experts == 1
    assert g.prune_expert() is None  # never drops the last expert
    assert g.n_experts == 1


def test_growable_topk_active_subset(mlp_tensors):
    w1, b1, w2, b2 = mlp_tensors
    g = growable.GrowableMLP.from_block_tensors(w1, b1, w2, b2, seed=9)
    for s in (201, 202, 203):
        g.add_expert(seed=s)
    g.top_k = 2
    g.reset_utilization()
    rng = np.random.RandomState(21)
    h = rng.randn(6, 256).astype(np.float32)
    out = g.forward(h)
    assert out.shape == (6, 256)
    assert np.all(np.isfinite(out))
    # exactly k experts credited per token
    assert sum(g.utilization) == 6 * 2


def test_growable_determinism(mlp_tensors):
    w1, b1, w2, b2 = mlp_tensors
    a = growable.GrowableMLP.from_block_tensors(w1, b1, w2, b2, seed=4)
    b = growable.GrowableMLP.from_block_tensors(w1, b1, w2, b2, seed=4)
    assert np.array_equal(a.router_w, b.router_w)
    a.add_expert(seed=55)
    b.add_expert(seed=55)
    assert np.array_equal(a.experts[1].w1, b.experts[1].w1)


def test_growable_all_blocks_build(bundle):
    _, cfg, _, params = bundle
    mlps = growable.growable_mlps_from_params(
        params, int(cfg["n_layer"]), seed=1
    )
    assert len(mlps) == 4
    assert all(m.n_experts == 1 for m in mlps.values())


# ---------------------------------------------------------------- streaming


def test_streaming_skeleton_few_steps(bundle):
    _, cfg, chars, params = bundle
    char_to_id = {c: i for i, c in enumerate(chars)}
    text = "levi is the smallest thing here. " * 4

    def forward_fn(ids):
        return runtime._forward_numpy(params, ids, cfg)

    skel = stream1.StreamingSkeleton(forward_fn, vocab_size=len(chars))
    batches = stream1.stream_char_batches(text, char_to_id, block_size=16)
    hist = skel.run(batches, max_steps=3)
    assert len(hist) == 3
    for entry in hist:
        assert np.isfinite(entry.loss) and entry.loss > 0
        assert entry.tokens == 16
    # determinism: same stream, fresh skeleton, same losses
    skel2 = stream1.StreamingSkeleton(forward_fn, vocab_size=len(chars))
    hist2 = skel2.run(
        stream1.stream_char_batches(text, char_to_id, block_size=16),
        max_steps=3,
    )
    assert [e.loss for e in hist] == [e.loss for e in hist2]


def test_streaming_batches_document_clean():
    batches = list(stream1.stream_char_batches("abcdef", {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4, "f": 5}, block_size=4))
    assert batches[0] == ([0, 1, 2, 3], [1, 2, 3, 4])
    assert batches[1] == ([4], [5])
