"""Torch-free native-brain runtime — LEVI's own Ollama-style local model runner.

This module is two things at once:

1. **A torch-free inference engine** for LEVI's trained char-GPT weights.
   It loads the portable weight export
   (``core/levi/brain/weights/tiny-gpt-portable/`` — JSON manifest + raw
   float32 blobs, exported once from ``tiny-gpt.pt`` which is never
   modified) and runs the exact forward pass mirrored from
   ``train/train.py``: embedding -> 4 transformer blocks with causal
   mask -> layernorm -> logits. ``numpy`` is used opportunistically when
   importable (fast); otherwise a pure-stdlib path with a per-token KV
   cache runs the identical math (slower).

2. **A tiny local model runner** in the shape of Ollama: models are
   described by :class:`ModelSpec` (architecture id, weights locator,
   tokenizer, sampling defaults, origin), architectures are pluggable
   via :func:`register_architecture`, and :func:`run` serves any
   registered model as ``run(model_id, prompt)``. LEVI's char-GPT ships
   as the first built-in model, id ``levi-native``. An optional
   loopback-only HTTP stub (:func:`serve_loopback`) exposes the same
   runner on 127.0.0.1 — never on any other interface.

HONESTY LAW — same as ``inference.py``: this is a proof-of-learning
brain and its samples are garbled (see ``weights/eval.json`` and
``weights/samples.md``). This module runs the brain for real — never
simulates one, never returns canned text — but its output is labeled
as raw brain continuation everywhere it is used, never as reasoning.
The rules engine stays the decider; the brain is explicit-only.

IDENTITY LAW — the built-in ``levi-native`` model is LEVI's own. Any
non-LEVI model (Qwen-class or anything else) registers with
``origin="reference"`` and is labeled as a reference everywhere it
appears — via ``core/levi/plugins/references.py``, never as LEVI
identity, never a persona. :func:`register_model` enforces this.

ADDING A NEW ARCHITECTURE (e.g. a Qwen-class reference later):

1. Pick an ``arch_id`` (``"qwen-class"`` is reserved and documented
   but intentionally NOT implemented — see below).
2. Write a loader ``load(spec: ModelSpec) -> ModelHandle``. Your
   loader owns the weights format; the recommended layout is the same
   ``manifest.json`` + raw little-endian float32 blob layout as
   ``levi-brain-portable/1`` so the sha256 validation here can be
   reused, but any offline format is acceptable if you validate it.
3. Implement the :class:`ModelHandle` interface on what you return:
   ``describe()``, ``encode(text)``, ``logits_for(ids)`` (optional but
   recommended for cross-checks), and ``generate(prompt,
   max_new_chars, temperature, seed)`` returning the same receipt keys
   as :meth:`CharGPTHandle.generate` (``prompt``, ``continuation``,
   ``text``, ``unmapped_chars``, ``max_new_chars``, ``temperature``,
   ``seed``, ``params``, ``label``).
4. Describe the tokenizer in ``ModelSpec.tokenizer`` (``encode`` maps
   text to ids; out-of-vocab input must be handled honestly, e.g.
   mapped to a space and counted like the char-GPT path does).
5. Call :func:`register_architecture` with the loader, a plain-words
   description, and the weights/tokenizer format notes.
6. Register each model with :func:`register_model`. Non-LEVI models
   MUST use ``origin="reference"`` plus the ``reference`` id you
   recorded in ``plugins/references.py`` (``kind="model"``) — the
   registry refuses reference ids that collide with LEVI identity.

Stdlib only at import time. ``numpy`` is opportunistic (never
required). ``torch`` is never imported by this module, not even
lazily: the torch reference path lives in ``inference.py`` and
:func:`load_brain_auto` selects it only when torch is importable.

``BrainError`` is raised (never a crash through) whenever the runtime
cannot run — missing export, corrupt blobs, unknown model/arch,
unusable prompts — so callers can report honestly.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import sys
import time
from array import array
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from levi.brain.inference import BrainError

ORIGIN = "levi-brain/runtime"

# Portable export format this runtime reads.
PORTABLE_FORMAT = "levi-brain-portable/1"
PORTABLE_DIR_NAME = "tiny-gpt-portable"

# Sane generation cap for the torch-free path: the stdlib fallback is
# far slower than torch, so one call never produces more than this many
# chars (the torch reference path in inference.py allows 2048).
MAX_NEW_CHARS_CAP = 512

# Must match the source checkpoint the portable export was taken from.
EXPECTED_SOURCE_SHA256 = (
    "7474e24f97c8df50904a26367a27e2e57dbaa050b0238cba1b1e79a46997e3b2"
)

_LN_EPS = 1e-5  # nn.LayerNorm default, matches train/train.py
_MODEL_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")

#: Architecture id for LEVI's char-level GPT (fully implemented here).
ARCH_CHAR_GPT = "char-gpt"
#: Reserved id for a future Qwen-class reference architecture.
#: Documented, intentionally NOT implemented (see module docstring).
ARCH_QWEN_CLASS = "qwen-class"

_LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")


# ---------------------------------------------------------------- backend


_numpy: Any = None  # cached: numpy module, or False when unavailable


def _numpy_module() -> Optional[Any]:
    """Import numpy opportunistically — never required, never at import."""
    global _numpy
    if _numpy is None:
        try:
            import numpy as np_mod  # noqa: F401

            _numpy = np_mod
        except ImportError:
            _numpy = False
    return _numpy or None


def backend_available() -> str:
    """Which compute backend this runtime would use: 'numpy' or 'stdlib'."""
    return "numpy" if _numpy_module() is not None else "stdlib"


# ---------------------------------------------------------------- model spec


@dataclass
class ModelSpec:
    """What a model is: architecture, weights, tokenizer, sampling, origin.

    ``origin`` is ``"levi"`` for LEVI's own models and ``"reference"``
    for anything else; reference models must name the
    ``plugins/references.py`` entry (``kind="model"``) in ``reference``
    and are labeled as references on every display path.
    """

    model_id: str
    arch: str
    display_name: str = ""
    description: str = ""
    weights_dir: Optional[str] = None
    tokenizer: str = "char-list"
    sampling: Dict[str, Any] = field(
        default_factory=lambda: {
            "temperature": 0,
            "seed": 1337,
            "max_new_chars": 160,
        }
    )
    origin: str = "levi"
    reference: Optional[str] = None
    honesty_note: str = (
        "Raw brain continuation — not reasoning. The rules engine stays the decider."
    )

    def model_label(self) -> str:
        """Identity label. Reference models are NEVER labeled as LEVI."""
        if self.origin == "reference":
            return f"reference model (not LEVI) — ref: {self.reference}"
        return "LEVI native model"


@dataclass
class Architecture:
    """A pluggable model architecture: id + loader + format notes."""

    arch_id: str
    description: str
    load: Callable[[ModelSpec], "ModelHandle"]
    weights_format: str
    tokenizer: str


class ModelHandle:
    """Interface every architecture loader returns. Offline, honest."""

    def __init__(self, spec: ModelSpec) -> None:
        self.spec = spec

    @property
    def model_id(self) -> str:
        return self.spec.model_id

    def model_label(self) -> str:
        return self.spec.model_label()

    def describe(self) -> Dict[str, Any]:
        raise NotImplementedError

    def encode(self, text: str) -> Tuple[List[int], int]:
        raise NotImplementedError

    def generate(
        self,
        prompt: str,
        max_new_chars: int = 160,
        temperature: float = 0.8,
        seed: int = 1337,
    ) -> Dict[str, Any]:
        raise NotImplementedError


# ---------------------------------------------------------------- registries


_ARCHITECTURES: Dict[str, Architecture] = {}
_MODELS: Dict[str, ModelSpec] = {}
_BUILTIN_MODEL_IDS = ("levi-native",)


def register_architecture(arch: Architecture) -> Architecture:
    """Register a model architecture. Honest errors on bad input."""
    arch_id = (arch.arch_id or "").strip()
    if not _MODEL_ID_RE.match(arch_id):
        raise BrainError(
            f"architecture id {arch.arch_id!r} invalid — want {_MODEL_ID_RE.pattern}"
        )
    if arch_id in _ARCHITECTURES:
        raise BrainError(f"architecture {arch_id!r} is already registered")
    if not callable(arch.load):
        raise BrainError(f"architecture {arch_id!r} has no callable load()")
    _ARCHITECTURES[arch_id] = arch
    return arch


def get_architecture(arch_id: str) -> Architecture:
    try:
        return _ARCHITECTURES[arch_id]
    except KeyError:
        known = sorted(_ARCHITECTURES) or ["<none>"]
        raise BrainError(
            f"unknown architecture {arch_id!r} — registered: {', '.join(known)}"
        ) from None


def list_architectures() -> List[Dict[str, Any]]:
    return [
        {
            "arch_id": a.arch_id,
            "description": a.description,
            "weights_format": a.weights_format,
            "tokenizer": a.tokenizer,
        }
        for a in (_ARCHITECTURES[k] for k in sorted(_ARCHITECTURES))
    ]


def _references_module() -> Any:
    """Load plugins/references.py WITHOUT executing levi.plugins.__init__.

    The package __init__ wires heavy connector classes; the reference
    registry itself is stdlib-only, so the module is loaded directly
    from its file location. Cached after the first call.
    """
    global _references_mod
    if _references_mod is None:
        import importlib.util

        path = Path(__file__).resolve().parent.parent / "plugins" / "references.py"
        if not path.is_file():
            raise BrainError(f"provider-reference module not found at {path}")
        spec = importlib.util.spec_from_file_location(
            "levi_brain_standalone_references", str(path)
        )
        if spec is None or spec.loader is None:
            raise BrainError(f"cannot load provider-reference module at {path}")
        mod = importlib.util.module_from_spec(spec)
        # Dataclass processing can look the module up in sys.modules, so
        # it must be registered BEFORE exec_module runs.
        sys.modules["levi_brain_standalone_references"] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            sys.modules.pop("levi_brain_standalone_references", None)
            raise
        _references_mod = mod
    return _references_mod


_references_mod: Any = None


def register_model(spec: ModelSpec) -> ModelSpec:
    """Register a model. Enforces the identity law for references."""
    model_id = (spec.model_id or "").strip()
    if not _MODEL_ID_RE.match(model_id):
        raise BrainError(
            f"model id {spec.model_id!r} invalid — want {_MODEL_ID_RE.pattern}"
        )
    if model_id in _MODELS:
        raise BrainError(
            f"model {model_id!r} is already registered — "
            "unregister it first to replace it"
        )
    get_architecture(spec.arch)  # honest unknown-arch error here, not at load
    if spec.origin not in ("levi", "reference"):
        raise BrainError(
            f"model {model_id!r} origin must be 'levi' or 'reference', "
            f"got {spec.origin!r}"
        )
    if spec.origin == "reference":
        if not (spec.reference or "").strip():
            raise BrainError(
                f"reference model {model_id!r} must name its "
                "plugins/references.py entry in 'reference'"
            )
        refs = _references_module()
        try:
            refs.assert_not_levi_identity(model_id, what="reference model")
        except refs.ReferenceError as exc:
            raise BrainError(str(exc)) from exc
    _MODELS[model_id] = spec
    return spec


def unregister_model(model_id: str) -> None:
    if model_id in _BUILTIN_MODEL_IDS:
        raise BrainError(f"cannot unregister built-in model {model_id!r}")
    if model_id not in _MODELS:
        raise BrainError(f"unknown model {model_id!r} — nothing to unregister")
    _MODELS.pop(model_id)
    _LOADED.pop(model_id, None)


def get_model(model_id: str) -> ModelSpec:
    try:
        return _MODELS[model_id]
    except KeyError:
        known = sorted(_MODELS) or ["<none>"]
        raise BrainError(
            f"unknown model {model_id!r} — registered: {', '.join(known)}"
        ) from None


def list_models() -> List[Dict[str, Any]]:
    out = []
    for model_id in sorted(_MODELS):
        spec = _MODELS[model_id]
        out.append(
            {
                "model_id": spec.model_id,
                "arch": spec.arch,
                "display_name": spec.display_name,
                "description": spec.description,
                "origin": spec.origin,
                "reference": spec.reference,
                "label": (
                    "LEVI native model"
                    if spec.origin == "levi"
                    else f"reference model (not LEVI) — ref: {spec.reference}"
                ),
                "loaded": any(key[0] == model_id for key in _LOADED),
            }
        )
    return out


# ---------------------------------------------------------------- portable weights


def _default_portable_dir() -> Path:
    return Path(__file__).resolve().parent / "weights" / PORTABLE_DIR_NAME


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _required_tensors(
    config: Dict[str, Any], vocab_size: int
) -> Dict[str, Tuple[int, ...]]:
    """The 45 real parameter tensors of TinyGPT (mask buffers excluded)."""
    n_layer = int(config["n_layer"])
    n_embd = int(config["n_embd"])
    block_size = int(config["block_size"])
    req: Dict[str, Tuple[int, ...]] = {
        "tok_emb.weight": (vocab_size, n_embd),
        "pos_emb.weight": (block_size, n_embd),
        "ln_f.weight": (n_embd,),
        "ln_f.bias": (n_embd,),
        "head.weight": (vocab_size, n_embd),
    }
    for layer in range(n_layer):
        p = f"blocks.{layer}"
        req[f"{p}.ln1.weight"] = (n_embd,)
        req[f"{p}.ln1.bias"] = (n_embd,)
        req[f"{p}.attn.qkv.weight"] = (3 * n_embd, n_embd)
        req[f"{p}.attn.proj.weight"] = (n_embd, n_embd)
        req[f"{p}.ln2.weight"] = (n_embd,)
        req[f"{p}.ln2.bias"] = (n_embd,)
        req[f"{p}.mlp.0.weight"] = (4 * n_embd, n_embd)
        req[f"{p}.mlp.0.bias"] = (4 * n_embd,)
        req[f"{p}.mlp.2.weight"] = (n_embd, 4 * n_embd)
        req[f"{p}.mlp.2.bias"] = (n_embd,)
    return req


def load_portable_tensors(
    portable_dir: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, bytes]]:
    """Read + validate the portable weight export.

    Returns ``(manifest, blobs)`` where blobs maps tensor name to raw
    little-endian float32 bytes. Every required tensor is checked for
    presence, shape, byte size, and sha256. Raises ``BrainError`` with
    the specific reason on anything missing or corrupt.
    """
    root = Path(portable_dir) if portable_dir else _default_portable_dir()
    if not root.is_dir():
        raise BrainError(
            f"no torch-free brain export found at {root} — "
            "the portable weights have not been exported"
        )
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise BrainError(f"portable export at {root} has no manifest.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        raise BrainError(
            f"portable manifest unreadable ({exc.__class__.__name__}: {exc})"
        ) from exc
    if not isinstance(manifest, dict):
        raise BrainError("portable manifest is not a JSON object")
    if manifest.get("format") != PORTABLE_FORMAT:
        raise BrainError(
            f"portable export format {manifest.get('format')!r} != "
            f"supported {PORTABLE_FORMAT!r}"
        )
    config = manifest.get("config")
    chars = manifest.get("chars")
    if not isinstance(config, dict) or not isinstance(chars, list) or not chars:
        raise BrainError("portable manifest missing usable 'config'/'chars'")
    for key in ("n_layer", "n_head", "n_embd", "block_size"):
        if key not in config:
            raise BrainError(f"portable config missing required key {key!r}")

    entries = {e["name"]: e for e in manifest.get("tensors", []) if isinstance(e, dict)}
    required = _required_tensors(config, len(chars))
    blobs: Dict[str, bytes] = {}
    for name, shape in required.items():
        entry = entries.get(name)
        if entry is None:
            raise BrainError(f"portable export missing required tensor {name!r}")
        if tuple(entry.get("shape", ())) != shape:
            raise BrainError(
                f"portable tensor {name!r} shape {entry.get('shape')} != "
                f"expected {shape}"
            )
        if entry.get("dtype") != "float32" or entry.get("byteorder") != "little":
            raise BrainError(f"portable tensor {name!r} is not little-endian float32")
        blob_path = root / entry.get("file", "")
        if not blob_path.is_file():
            raise BrainError(f"portable blob missing: {entry.get('file')}")
        raw = blob_path.read_bytes()
        expect_len = 4
        for dim in shape:
            expect_len *= dim
        if len(raw) != expect_len:
            raise BrainError(
                f"portable blob {entry.get('file')} size {len(raw)} != "
                f"expected {expect_len}"
            )
        if hashlib.sha256(raw).hexdigest() != entry.get("sha256"):
            raise BrainError(
                f"portable blob {entry.get('file')} sha256 mismatch — "
                "weights are corrupt"
            )
        blobs[name] = raw
    return manifest, blobs


def portable_available(portable_dir: Optional[str] = None) -> bool:
    """True when a valid torch-free export exists (never raises)."""
    try:
        load_portable_tensors(portable_dir)
        return True
    except BrainError:
        return False


# ---------------------------------------------------------------- char-GPT engine
#
# Exact mirror of train/train.py TinyGPT:
#   x = tok_emb[idx] + pos_emb[arange(T)]
#   x = x + attn(ln1(x));  x = x + mlp(ln2(x))   (x4 blocks)
#   logits = head(ln_f(x))
# with:
#   attn: qkv Linear(C->3C, no bias) -> 4 heads x 64 dim, causal mask,
#         scale 1/sqrt(64), proj Linear(C->C, no bias)
#   mlp: Linear(C->4C, bias) -> GELU (exact erf) -> Linear(4C->C, bias)
#   layernorm: eps 1e-5, biased variance (divide by N)
#
# Two backends compute the identical math:
#   numpy  — vectorized full forward per token (fast; preferred)
#   stdlib — per-token KV cache over nested lists (slow; fallback)
# The stdlib cache is mathematically identical to the full forward for
# the last position: cached k/v never change (causal), and positions
# are re-indexed 0..T-1 on the truncated window exactly like torch.


def _params_numpy(
    blobs: Dict[str, bytes], required: Dict[str, Tuple[int, ...]]
) -> Dict[str, Any]:
    np_ = _numpy_module()
    assert np_ is not None
    params = {}
    for name, shape in required.items():
        arr = np_.frombuffer(blobs[name], dtype="<f4").reshape(shape)
        params[name] = arr
    return params


def _reshape_nested(flat: array, shape: Tuple[int, ...]) -> List:
    if len(shape) == 1:
        return list(flat)
    n = shape[0]
    sub = len(flat) // n
    return [_reshape_nested(flat[i * sub : (i + 1) * sub], shape[1:]) for i in range(n)]


def _params_stdlib(
    blobs: Dict[str, bytes], required: Dict[str, Tuple[int, ...]]
) -> Dict[str, Any]:
    params = {}
    for name, shape in required.items():
        flat = array("f", blobs[name])
        if sys.byteorder != "little":
            flat.byteswap()
        params[name] = _reshape_nested(flat, shape)
    return params


# -- numpy math --------------------------------------------------------


def _layernorm_np(x: Any, w: Any, b: Any) -> Any:
    mean = x.mean(axis=-1, keepdims=True)
    var = ((x - mean) ** 2).mean(axis=-1, keepdims=True)
    return (x - mean) / (var + _LN_EPS) ** 0.5 * w + b


def _erf_as(x: Any) -> Any:
    """Abramowitz & Stegun 7.1.26 erf, vectorized (|err| <= 1.5e-7)."""
    np_ = _numpy_module()
    a1, a2, a3, a4, a5, p = (
        0.254829592,
        -0.284496736,
        1.421413741,
        -1.453152027,
        1.061405429,
        0.3275911,
    )
    sign = np_.sign(x)
    ax = np_.abs(x)
    t = 1.0 / (1.0 + p * ax)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * np_.exp(-ax * ax)
    return sign * y


_SQRT1_2_F32: Any = None


def _gelu_np(x: Any) -> Any:
    """Exact-form GELU: 0.5 * x * (1 + erf(x / sqrt(2))) — torch default."""
    global _SQRT1_2_F32
    np_ = _numpy_module()
    if _SQRT1_2_F32 is None:
        _SQRT1_2_F32 = np_.float32(0.7071067811865476)
    return 0.5 * x * (1.0 + _erf_as(x * _SQRT1_2_F32))


def _softmax_np(x: Any, axis: int = -1) -> Any:
    m = x.max(axis=axis, keepdims=True)
    e = _numpy_module().exp(x - m)
    return e / e.sum(axis=axis, keepdims=True)


def _forward_numpy(params: Dict[str, Any], ids: List[int], cfg: Dict[str, Any]) -> Any:
    """Full forward pass, vectorized. Returns (T, vocab) float32 logits."""
    np_ = _numpy_module()
    n_layer = int(cfg["n_layer"])
    n_head = int(cfg["n_head"])
    n_embd = int(cfg["n_embd"])
    head_dim = n_embd // n_head
    scale = 1.0 / math.sqrt(head_dim)
    T = len(ids)
    idx = np_.array(ids, dtype=np_.int64)
    x = params["tok_emb.weight"][idx] + params["pos_emb.weight"][:T]
    for layer in range(n_layer):
        p = f"blocks.{layer}"
        h = _layernorm_np(x, params[f"{p}.ln1.weight"], params[f"{p}.ln1.bias"])
        qkv = h @ params[f"{p}.attn.qkv.weight"].T
        q, k, v = np_.split(qkv, 3, axis=-1)
        q = q.reshape(T, n_head, head_dim).transpose(1, 0, 2)
        k = k.reshape(T, n_head, head_dim).transpose(1, 0, 2)
        v = v.reshape(T, n_head, head_dim).transpose(1, 0, 2)
        att = (q @ k.transpose(0, 2, 1)) * scale
        mask = np_.tril(np_.ones((T, T), dtype=np_.bool_))
        att = np_.where(mask, att, np_.float32("-inf"))
        att = _softmax_np(att, axis=-1)
        y = (att @ v).transpose(1, 0, 2).reshape(T, n_embd)
        y = y @ params[f"{p}.attn.proj.weight"].T
        x = x + y
        h = _layernorm_np(x, params[f"{p}.ln2.weight"], params[f"{p}.ln2.bias"])
        h = h @ params[f"{p}.mlp.0.weight"].T + params[f"{p}.mlp.0.bias"]
        h = _gelu_np(h)
        h = h @ params[f"{p}.mlp.2.weight"].T + params[f"{p}.mlp.2.bias"]
        x = x + h
    x = _layernorm_np(x, params["ln_f.weight"], params["ln_f.bias"])
    return x @ params["head.weight"].T


def _sample_numpy(logits: Any, temperature: float, rng: Any) -> int:
    np_ = _numpy_module()
    if temperature == 0:
        return int(np_.argmax(logits))
    m = logits.max()
    e = np_.exp((logits - m) / temperature)
    probs = e / e.sum()
    return int(rng.choice(len(logits), p=probs))


# -- stdlib math -------------------------------------------------------


def _matvec(w: List[List[float]], x: List[float]) -> List[float]:
    return [sum(rj * xv for rj, xv in zip(row, x, strict=True)) for row in w]


def _matvec_bias(w: List[List[float]], b: List[float], x: List[float]) -> List[float]:
    return [
        bv + sum(rj * xv for rj, xv in zip(row, x, strict=True))
        for row, bv in zip(w, b, strict=True)
    ]


def _layernorm_list(x: List[float], w: List[float], b: List[float]) -> List[float]:
    n = len(x)
    mean = sum(x) / n
    var = sum((v - mean) ** 2 for v in x) / n
    inv = 1.0 / math.sqrt(var + _LN_EPS)
    return [(v - mean) * inv * wv + bv for v, wv, bv in zip(x, w, b, strict=True)]


def _gelu_scalar(x: float) -> float:
    return 0.5 * x * (1.0 + math.erf(x * 0.7071067811865476))


def _softmax_list(vals: List[float]) -> List[float]:
    m = max(vals)
    exps = [math.exp(v - m) for v in vals]
    s = sum(exps)
    return [e / s for e in exps]


def _sample_list(logits: List[float], temperature: float, rng: random.Random) -> int:
    if temperature == 0:
        best, best_v = 0, logits[0]
        for i in range(1, len(logits)):
            if logits[i] > best_v:
                best, best_v = i, logits[i]
        return best
    m = max(logits)
    exps = [math.exp((v - m) / temperature) for v in logits]
    s = sum(exps)
    r = rng.random() * s
    acc = 0.0
    for i, e in enumerate(exps):
        acc += e
        if r < acc:
            return i
    return len(logits) - 1


# ---------------------------------------------------------------- char-GPT handle


class CharGPTHandle(ModelHandle):
    """A loaded char-GPT model: the torch-free path for LEVI's native brain."""

    def __init__(
        self,
        spec: ModelSpec,
        manifest: Dict[str, Any],
        blobs: Dict[str, bytes],
        backend: Optional[str] = None,
        manifest_path: Optional[Path] = None,
    ) -> None:
        super().__init__(spec)
        self._manifest = manifest
        self._manifest_path = manifest_path
        self._config = manifest["config"]
        self._chars: List[str] = manifest["chars"]
        self._stoi = {c: i for i, c in enumerate(self._chars)}
        self._backend = backend or backend_available()
        if self._backend not in ("numpy", "stdlib"):
            raise BrainError(f"unknown backend {self._backend!r}")
        if self._backend == "numpy" and _numpy_module() is None:
            raise BrainError("numpy backend requested but numpy is not importable")
        required = _required_tensors(self._config, len(self._chars))
        if self._backend == "numpy":
            self._params = _params_numpy(blobs, required)
        else:
            self._params = _params_stdlib(blobs, required)
        self._n_params = sum(math.prod(shape) for shape in required.values())
        self._block_size = int(self._config["block_size"])
        self._n_head = int(self._config["n_head"])
        self._n_embd = int(self._config["n_embd"])
        self._head_dim = self._n_embd // self._n_head

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def chars(self) -> List[str]:
        return list(self._chars)

    # -- provenance ------------------------------------------------------

    def describe(self) -> Dict[str, Any]:
        cfg = self._config
        src = self._manifest.get("source", {})
        src_sha = src.get("sha256", "")
        return {
            "origin": ORIGIN,
            "model_id": self.model_id,
            "model_label": self.model_label(),
            "arch": ARCH_CHAR_GPT,
            "backend": self._backend,
            "portable_dir": str(self._manifest_path.parent)
            if self._manifest_path
            else "?",
            "manifest_sha256": (
                _sha256_file(self._manifest_path) if self._manifest_path else "?"
            ),
            "source_checkpoint_sha256": src_sha,
            "source_sha256_expected": EXPECTED_SOURCE_SHA256,
            "source_sha256_match": src_sha == EXPECTED_SOURCE_SHA256,
            "params": self._n_params,
            "training_steps": int(cfg.get("steps", -1)),
            "vocab_chars": len(self._chars),
            "corpus_chars": int(cfg.get("corpus_chars", -1)),
            "corpus_file": str(cfg.get("corpus_file", "?")),
            "architecture": {
                "layers": int(cfg["n_layer"]),
                "heads": int(cfg["n_head"]),
                "embed": int(cfg["n_embd"]),
                "block_size": int(cfg["block_size"]),
                "level": "char",
            },
            "honest_note": self.spec.honesty_note,
        }

    # -- encoding --------------------------------------------------------

    def encode(self, text: str) -> Tuple[List[int], int]:
        """Encode ``text`` to vocab ids; chars outside the vocab map to a
        space and are counted (returned as the second value)."""
        ids: List[int] = []
        unmapped = 0
        for ch in text:
            idx = self._stoi.get(ch)
            if idx is None:
                ids.append(self._stoi[" "])
                unmapped += 1
            else:
                ids.append(idx)
        return ids, unmapped

    # -- forward ---------------------------------------------------------

    def logits_for(self, ids: List[int]) -> List[float]:
        """Last-position logits for ``ids`` — the cross-check hook."""
        ids = [int(i) for i in ids][-self._block_size :]
        if not ids:
            raise BrainError("no ids: nothing to score")
        if self._backend == "numpy":
            logits = _forward_numpy(self._params, ids, self._config)[-1]
            return [float(v) for v in logits]
        caches = self._fresh_caches()
        last_x = self._prime(ids, caches)
        return self._head_logits_list(last_x)

    # -- stdlib KV-cache machinery ---------------------------------------

    def _fresh_caches(self) -> List[Tuple[List, List]]:
        return [([], []) for _ in range(int(self._config["n_layer"]))]

    def _embed_tok(self, pos: int, tok: int) -> List[float]:
        te = self._params["tok_emb.weight"][tok]
        pe = self._params["pos_emb.weight"][pos]
        return [a + b for a, b in zip(te, pe, strict=True)]

    def _step_cached(
        self, x_t: List[float], caches: List[Tuple[List, List]]
    ) -> List[float]:
        """One transformer pass over a single position; appends k/v."""
        P = self._params
        n_head, head_dim, n_embd = self._n_head, self._head_dim, self._n_embd
        scale = 1.0 / math.sqrt(head_dim)
        for layer in range(int(self._config["n_layer"])):
            p = f"blocks.{layer}"
            h = _layernorm_list(x_t, P[f"{p}.ln1.weight"], P[f"{p}.ln1.bias"])
            qkv = _matvec(P[f"{p}.attn.qkv.weight"], h)
            q, k, v = qkv[:n_embd], qkv[n_embd : 2 * n_embd], qkv[2 * n_embd :]
            k_list, v_list = caches[layer]
            k_list.append(k)
            v_list.append(v)
            n_past = len(k_list)
            y = [0.0] * n_embd
            for hd in range(n_head):
                off = hd * head_dim
                qs = q[off : off + head_dim]
                scores = [
                    sum(qs[d] * k_list[t][off + d] for d in range(head_dim)) * scale
                    for t in range(n_past)
                ]
                probs = _softmax_list(scores)
                for d in range(head_dim):
                    y[off + d] = sum(
                        probs[t] * v_list[t][off + d] for t in range(n_past)
                    )
            y = _matvec(P[f"{p}.attn.proj.weight"], y)
            x_t = [a + b for a, b in zip(x_t, y, strict=True)]
            h = _layernorm_list(x_t, P[f"{p}.ln2.weight"], P[f"{p}.ln2.bias"])
            h = _matvec_bias(P[f"{p}.mlp.0.weight"], P[f"{p}.mlp.0.bias"], h)
            h = [_gelu_scalar(v) for v in h]
            h = _matvec_bias(P[f"{p}.mlp.2.weight"], P[f"{p}.mlp.2.bias"], h)
            x_t = [a + b for a, b in zip(x_t, h, strict=True)]
        return x_t

    def _prime(self, ids: List[int], caches: List[Tuple[List, List]]) -> List[float]:
        """Replay ``ids`` through the cache; returns the last position state."""
        last_x: List[float] = []
        for pos, tok in enumerate(ids):
            last_x = self._step_cached(self._embed_tok(pos, tok), caches)
        return last_x

    def _head_logits_list(self, x_t: List[float]) -> List[float]:
        P = self._params
        h = _layernorm_list(x_t, P["ln_f.weight"], P["ln_f.bias"])
        return _matvec(P["head.weight"], h)

    # -- generation ------------------------------------------------------

    def _generate_numpy(
        self, ids: List[int], max_new: int, temperature: float, seed: int
    ) -> List[int]:
        np_ = _numpy_module()
        rng = np_.random.default_rng(int(seed))
        ids = list(ids)
        out: List[int] = []
        for _ in range(max_new):
            window = ids[-self._block_size :]
            logits = _forward_numpy(self._params, window, self._config)[-1]
            nxt = _sample_numpy(logits, temperature, rng)
            out.append(nxt)
            ids.append(nxt)
        return out

    def _generate_stdlib(
        self, ids: List[int], max_new: int, temperature: float, seed: int
    ) -> List[int]:
        rng = random.Random(int(seed))
        ids = list(ids[-self._block_size :])
        out: List[int] = []
        caches = self._fresh_caches()
        last_x = self._prime(ids, caches)
        logits = self._head_logits_list(last_x)
        for _ in range(max_new):
            nxt = _sample_list(logits, temperature, rng)
            out.append(nxt)
            ids.append(nxt)
            if len(ids) > self._block_size:
                # Window truncated: positions re-index from 0 exactly like
                # the torch reference, so the cache is rebuilt from the
                # current window (slow, but exact — and rare).
                del ids[0]
                caches = self._fresh_caches()
                last_x = self._prime(ids, caches)
            else:
                last_x = self._step_cached(self._embed_tok(len(ids) - 1, nxt), caches)
            logits = self._head_logits_list(last_x)
        return out

    def generate(
        self,
        prompt: str,
        max_new_chars: int = 160,
        temperature: float = 0,
        seed: int = 1337,
    ) -> Dict[str, Any]:
        """Continue ``prompt`` with raw brain text.

        Deterministic for a fixed (prompt, seed, temperature, backend).
        ``temperature <= 0`` selects greedily (the default). ``max_new_chars``
        is clamped to [1, MAX_NEW_CHARS_CAP].
        """
        if not isinstance(prompt, str) or not prompt.strip():
            raise BrainError("empty prompt: nothing to continue")
        if temperature is None or temperature < 0:
            raise BrainError(f"temperature must be >= 0, got {temperature!r}")
        max_new_chars = max(1, min(int(max_new_chars), MAX_NEW_CHARS_CAP))

        ids, unmapped = self.encode(prompt.strip())
        if not ids:
            raise BrainError("prompt has no usable characters")
        ids = ids[-self._block_size :]
        if self._backend == "numpy":
            out_ids = self._generate_numpy(ids, max_new_chars, float(temperature), seed)
        else:
            out_ids = self._generate_stdlib(
                ids, max_new_chars, float(temperature), seed
            )

        continuation = "".join(self._chars[i] for i in out_ids)
        return {
            "prompt": prompt.strip(),
            "continuation": continuation,
            "text": prompt.strip() + continuation,
            "unmapped_chars": unmapped,
            "max_new_chars": max_new_chars,
            "temperature": float(temperature),
            "seed": int(seed),
            "params": self._n_params,
            "backend": self._backend,
            "label": "raw brain continuation — not reasoning",
        }


def _load_char_gpt(spec: ModelSpec, backend: Optional[str] = None) -> CharGPTHandle:
    manifest, blobs = load_portable_tensors(spec.weights_dir)
    root = Path(spec.weights_dir) if spec.weights_dir else _default_portable_dir()
    return CharGPTHandle(
        spec, manifest, blobs, backend=backend, manifest_path=root / "manifest.json"
    )


def load_runtime_brain(
    portable_dir: Optional[str] = None, backend: Optional[str] = None
) -> CharGPTHandle:
    """Load LEVI's native brain on the torch-free path (original API)."""
    spec = get_model("levi-native")
    if portable_dir is not None:
        spec = ModelSpec(
            model_id=spec.model_id,
            arch=spec.arch,
            display_name=spec.display_name,
            description=spec.description,
            weights_dir=portable_dir,
            tokenizer=spec.tokenizer,
            sampling=dict(spec.sampling),
            origin=spec.origin,
            reference=spec.reference,
            honesty_note=spec.honesty_note,
        )
    return _load_char_gpt(spec, backend=backend)


# ------------------------------------------------- observation store
#
# The training substrate. Every run through the runner can append one
# observation record: what model ran (id + arch + origin label), the
# prompt (plaintext plus its SHA-256), what the model produced
# (sampled output / actions / decisions), the sampling params, timing,
# and the run receipt (ok or honest failure). A future training track
# will train LEVI's brain off these records (distillation). This module
# is NOT the training loop — it is the clean, honest record format the
# loop will consume.
#
# Storage: append-only JSONL, local only, never networked, owner-only
# permissions (mode 0o600 file, 0o700 directory — the same pattern as
# ~/.levi/references.json in core/levi/plugins/references.py).
# Recording is ON by default for local runs: this is the owner's own
# machine and his own models. Pass record=False (or --no-record on the
# CLI) to disable per run. Prompts are stored in plaintext locally so
# the future trainer can consume them; the SHA-256 is there for
# dedup/integrity. Disable recording for prompts you would not want
# written to disk.

OBS_SCHEMA = "levi-observation/1"
"""Version of the observation record schema. Bump on any schema change."""

OBS_MAX_PROMPT_CHARS = 8000
"""Prompts longer than this are truncated in the stored record (flagged)."""


def observations_path() -> Path:
    """Path of the local observation log. Tests can point elsewhere with
    the LEVI_OBSERVATIONS_FILE environment variable."""
    override = os.environ.get("LEVI_OBSERVATIONS_FILE")
    if override:
        return Path(override)
    return Path.home() / ".levi" / "model-observations.jsonl"


def _ensure_observations_file(path: Path) -> None:
    """Create the log and its directory with owner-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    if not path.exists():
        path.touch(exist_ok=True)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


_OBS_REQUIRED = (
    "schema",
    "ts",
    "model_id",
    "arch",
    "prompt_sha256",
    "sampling",
    "timing",
    "receipt",
)


def append_observation(record: Dict[str, Any]) -> Path:
    """Append one observation record as a single JSONL line.

    Raises BrainError for a non-dict record. Sets owner-only permissions
    on the file and directory. Never touches the network.
    """
    if not isinstance(record, dict):
        raise BrainError("observation record must be a dict")
    path = observations_path()
    _ensure_observations_file(path)
    rec = dict(record)
    rec["schema"] = OBS_SCHEMA
    if "ts" not in rec:
        rec["ts"] = datetime.now(timezone.utc).isoformat()
    line = json.dumps(rec, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return path


def read_observations(
    limit: Optional[int] = None, model_id: Optional[str] = None
) -> Dict[str, Any]:
    """Read the observation log.

    Corrupt lines (not JSON, not a dict, wrong schema version, missing
    required fields) are SKIPPED and counted honestly in ``skipped`` —
    one bad line never poisons the whole log. Returns
    {"records": [...], "skipped": N, "path": str}.
    """
    path = observations_path()
    records: List[Dict[str, Any]] = []
    skipped = 0
    if path.is_file():
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    skipped += 1
                    continue
                if (
                    not isinstance(rec, dict)
                    or rec.get("schema") != OBS_SCHEMA
                    or any(key not in rec for key in _OBS_REQUIRED)
                ):
                    skipped += 1
                    continue
                if model_id is not None and rec.get("model_id") != model_id:
                    continue
                records.append(rec)
    if limit is not None:
        records = records[-max(0, int(limit)) :]
    return {"records": records, "skipped": skipped, "path": str(path)}


def _build_run_observation(
    handle: ModelHandle,
    prompt: str,
    sampling: Dict[str, Any],
    started_at: datetime,
    finished_at: datetime,
    seconds: float,
    receipt: Dict[str, Any],
    output: str,
) -> Dict[str, Any]:
    full_prompt = prompt if isinstance(prompt, str) else str(prompt)
    truncated = len(full_prompt) > OBS_MAX_PROMPT_CHARS
    stored_prompt = full_prompt[:OBS_MAX_PROMPT_CHARS] if truncated else full_prompt
    try:
        backend = handle.describe().get("backend", "unknown")
    except BrainError:
        backend = "unknown"
    return {
        "model_id": handle.model_id,
        "arch": handle.spec.arch,
        "origin": handle.spec.origin,
        "model_label": handle.model_label(),
        "prompt": stored_prompt,
        "prompt_truncated": truncated,
        "prompt_sha256": hashlib.sha256(full_prompt.encode("utf-8")).hexdigest(),
        "output": output,
        "output_chars": len(output),
        "sampling": dict(sampling),
        "timing": {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "seconds": round(seconds, 3),
            "backend": backend,
        },
        "receipt": dict(receipt),
        "label": "recorded model output — not LEVI reasoning",
    }


# ---------------------------------------------------------------- runner API

_LOADED: Dict[Tuple[str, Optional[str]], ModelHandle] = {}


def load_model(
    model_id: str = "levi-native", backend: Optional[str] = None
) -> ModelHandle:
    """Load (and cache) the model registered under ``model_id``.

    Raises BrainError for an unknown model id or an unknown
    architecture — never silently substitutes another model.

    ``backend`` is an explicit escape hatch for the char-gpt engine
    ("numpy" or "stdlib"); any other architecture raises BrainError
    for a backend override it does not support.
    """
    cache_key = (model_id, backend)
    if cache_key not in _LOADED:
        spec = get_model(model_id)
        if backend is None:
            _LOADED[cache_key] = get_architecture(spec.arch).load(spec)
        elif spec.arch == ARCH_CHAR_GPT:
            _LOADED[cache_key] = _load_char_gpt(spec, backend=backend)
        else:
            raise BrainError(
                f"backend override is not supported for arch {spec.arch!r}"
            )
    return _LOADED[cache_key]


def unload_model(model_id: str) -> None:
    """Drop cached model handle(s) so the next load re-reads the weights."""
    for key in [k for k in _LOADED if k[0] == model_id]:
        _LOADED.pop(key, None)


def run(
    model_id: str = "levi-native",
    prompt: str = "",
    max_new_chars: Optional[int] = None,
    temperature: Optional[float] = None,
    seed: Optional[int] = None,
    record: bool = True,
    backend: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a prompt through the registered model.

    Returns the handle's result dict plus ``model_id``, ``model_label``,
    ``arch``, and ``recorded``. The output is always labeled
    "raw brain continuation — not reasoning".

    Recording: an observation record is appended to the local JSONL log
    (see observations_path()) unless ``record=False``. The log is the
    future training substrate; nothing is ever sent over the network.

    ``backend`` pins the char-gpt engine ("numpy"/"stdlib"); other
    architectures reject it with BrainError.
    """
    handle = load_model(model_id, backend=backend)
    spec = handle.spec
    defaults = spec.sampling
    sampling = {
        "max_new_chars": defaults["max_new_chars"]
        if max_new_chars is None
        else max_new_chars,
        "temperature": defaults["temperature"] if temperature is None else temperature,
        "seed": defaults["seed"] if seed is None else seed,
    }
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    try:
        result = handle.generate(prompt, **sampling)
    except BrainError as exc:
        finished_at = datetime.now(timezone.utc)
        if record:
            append_observation(
                _build_run_observation(
                    handle,
                    prompt,
                    sampling,
                    started_at,
                    finished_at,
                    time.perf_counter() - t0,
                    {"ok": False, "error": str(exc), "error_type": "BrainError"},
                    "",
                )
            )
        raise
    finished_at = datetime.now(timezone.utc)
    seconds = time.perf_counter() - t0
    if record:
        append_observation(
            _build_run_observation(
                handle,
                prompt,
                sampling,
                started_at,
                finished_at,
                seconds,
                {
                    "ok": True,
                    "unmapped_chars": result.get("unmapped_chars", 0),
                    "params": result.get("params"),
                },
                result.get("continuation", ""),
            )
        )
    result = dict(result)
    result["model_id"] = handle.model_id
    result["model_label"] = handle.model_label()
    result["arch"] = spec.arch
    result["recorded"] = bool(record)
    return result


# ---------------------------------------------------------------- torch bridge


def load_brain_auto(
    weights_path: Optional[str] = None, portable_dir: Optional[str] = None
) -> Any:
    """Select the brain backend: torch when it is importable, otherwise
    the torch-free portable path. Same contract as before the runner."""
    try:
        import torch  # noqa: F401

        torch_ok = True
    except ImportError:
        torch_ok = False
    if torch_ok:
        from levi.brain.inference import load_brain as _torch_load

        return _torch_load(weights_path)
    return load_runtime_brain(portable_dir)


# ---------------------------------------------------------------- loopback server

_LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")


def serve_loopback(
    model_id: str = "levi-native", host: str = "127.0.0.1", port: int = 0
):
    """Serve the runner over HTTP on the loopback interface ONLY.

    Endpoints:
      GET  /models -> {"models": [...]}
      POST /run    -> {"model_id", "prompt", "max_new_chars",
                       "temperature", "seed", "record"} -> run() result
    ``record`` defaults to true, matching run(). The server object is
    returned WITHOUT being served — the caller decides (e.g.
    ``serve_forever()``). Nothing is ever exposed off-loopback: a
    non-loopback host raises BrainError instead of binding.
    """
    if host not in _LOOPBACK_HOSTS:
        raise BrainError(
            f"refusing non-loopback host {host!r}: the local model server "
            f"listens on loopback only {_LOOPBACK_HOSTS}"
        )
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class _Handler(BaseHTTPRequestHandler):
        server_version = "levi-brain-runtime/1"

        def log_message(self, *args: Any) -> None:
            pass

        def _json(self, obj: Any, status: int = 200) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/models":
                self._json({"models": list_models()})
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self) -> None:
            if self.path != "/run":
                self._json({"error": "not found"}, 404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except (TypeError, ValueError):
                length = 0
            if length > 1 << 20:
                self._json({"error": "request too large"}, 413)
                return
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._json({"error": "invalid JSON"}, 400)
                return
            if not isinstance(payload, dict):
                self._json({"error": "JSON body must be an object"}, 400)
                return
            try:
                self._json(
                    run(
                        payload.get("model_id", model_id),
                        payload.get("prompt", ""),
                        max_new_chars=payload.get("max_new_chars"),
                        temperature=payload.get("temperature"),
                        seed=payload.get("seed"),
                        record=bool(payload.get("record", True)),
                    )
                )
            except BrainError as exc:
                self._json({"error": str(exc)}, 400)

    server = ThreadingHTTPServer((host, port), _Handler)
    server.daemon_threads = True
    return server


# ---------------------------------------------------------------- built-ins

register_architecture(
    Architecture(
        arch_id=ARCH_CHAR_GPT,
        description=(
            "LEVI's char-level causal GPT (4 layers / 256 dim / 4 heads / "
            "block 128). Torch-free numpy/stdlib engine."
        ),
        load=lambda spec: _load_char_gpt(spec),
        weights_format=(
            "levi-brain-portable/1: manifest.json plus raw little-endian "
            "float32 blobs (see weights/tiny-gpt-portable/)"
        ),
        tokenizer=(
            "char-list: the ordered character vocabulary comes from the "
            "manifest; input characters outside the vocab map to a space "
            "and are counted honestly"
        ),
    )
)

register_model(
    ModelSpec(
        model_id="levi-native",
        arch=ARCH_CHAR_GPT,
        display_name="LEVI native brain",
        description=(
            "Proof-of-learning char-GPT trained on LEVI's own course "
            "corpus (600 steps). Raw continuation — not reasoning."
        ),
    )
)

__all__ = [
    "BrainError",
    "ModelSpec",
    "Architecture",
    "ModelHandle",
    "CharGPTHandle",
    "ORIGIN",
    "ARCH_CHAR_GPT",
    "ARCH_QWEN_CLASS",
    "PORTABLE_FORMAT",
    "MAX_NEW_CHARS_CAP",
    "OBS_SCHEMA",
    "OBS_MAX_PROMPT_CHARS",
    "backend_available",
    "register_architecture",
    "get_architecture",
    "list_architectures",
    "register_model",
    "get_model",
    "list_models",
    "unregister_model",
    "load_portable_tensors",
    "portable_available",
    "load_runtime_brain",
    "load_brain_auto",
    "load_model",
    "unload_model",
    "run",
    "serve_loopback",
    "observations_path",
    "append_observation",
    "read_observations",
]
