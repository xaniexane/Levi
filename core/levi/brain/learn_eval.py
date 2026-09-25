"""Learning-loop eval-gate: candidate vs incumbent, promote or reject.

The gate is the only path by which a candidate's weights can become the
live weights. It is deliberately conservative:

1. held-out loss — candidate vs incumbent on the SAME val text, scored on
   the shared charset. Characters the candidate never saw are penalized
   (eps smoothing), never silently excluded: a candidate must not "win"
   by forgetting characters.
2. behavioral checks — deterministic, cheap, model-agnostic:
   deterministic_argmax, charset_adherence, no_collapse, unmapped_honest.
3. regret check — the candidate must not catastrophically forget: its
   loss on anchor texts (prompt+continuation pairs captured from the
   incumbent at the last promotion) must stay within ``regret_margin``
   of the incumbent's.

Promote ONLY if the candidate beats the incumbent by ``promote_margin``
AND every behavioral check passes AND the regret check passes. Anything
else -> reject with explicit reasons. Every decision writes a receipt and
a lineage entry; the previous weights are kept as rollback.

The decision logic (``gate_decision``) is pure and fully unit-testable.
Measurement (``measure_scores``) runs against a tiny ``ScoredModel``
protocol — production wraps the torch-free runtime handles; tests inject
fakes. Production measurement needs torch only to convert the candidate
``.pt`` to the portable format; the forward passes themselves run through
the torch-free runtime (numpy backend when available).
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from levi.brain.learn_corpus import BrainLoopError

PORTABLE_FORMAT = "levi-brain-portable/1"
ANCHOR_PROMPTS = ["the ", "levi ", "a ", "in ", "to ", "of ", "and ", "is "]


# ---------------------------------------------------------------- protocols


class ScoredModel:
    """Minimal protocol the gate measures. Production wraps the torch-free
    runtime's CharGPTHandle; tests use fakes."""

    vocab_chars: List[str]

    def ce_loss(self, text: str) -> Tuple[float, int, int]:
        """Return (total_nats, positions_scored, chars_excluded)."""
        raise NotImplementedError

    def generate(
        self, prompt: str, max_new_chars: int, temperature: float, seed: int
    ) -> Dict[str, Any]:
        """Return {"continuation": str, "unmapped_chars": int}."""
        raise NotImplementedError


# ---------------------------------------------------------------- portable export


def export_portable(pt_path: Path, out_dir: Path) -> Dict[str, Any]:
    """Export a trained ``tiny-gpt.pt`` checkpoint to the portable
    ``levi-brain-portable/1`` layout (manifest.json + raw little-endian
    float32 blobs) so the torch-free runtime can load it.

    Requires torch (training environment). The tensor names in the
    checkpoint's ``model_state`` match the portable tensor names exactly.
    Raises BrainLoopError with the specific reason on any problem.
    """
    try:
        import torch
    except Exception as exc:
        raise BrainLoopError(
            "export_portable: torch is not installed — portable export "
            "needs the training environment"
        ) from exc

    pt_path = Path(pt_path)
    out_dir = Path(out_dir)
    try:
        ckpt = torch.load(str(pt_path), map_location="cpu", weights_only=True)
    except Exception as exc:
        raise BrainLoopError(
            f"export_portable: cannot read checkpoint {pt_path} "
            f"({exc.__class__.__name__}: {exc})"
        ) from exc
    if not isinstance(ckpt, dict) or "model_state" not in ckpt:
        raise BrainLoopError("export_portable: checkpoint has no 'model_state'")
    state = ckpt["model_state"]
    chars = ckpt.get("chars")
    config = ckpt.get("config") or {}
    if not isinstance(chars, list) or not chars:
        raise BrainLoopError("export_portable: checkpoint has no usable 'chars'")
    for key in ("n_layer", "n_head", "n_embd", "block_size"):
        if key not in config:
            raise BrainLoopError(f"export_portable: checkpoint config missing {key!r}")

    n_layer = int(config["n_layer"])
    required: Dict[str, Tuple[int, ...]] = {
        "tok_emb.weight": (len(chars), int(config["n_embd"])),
        "pos_emb.weight": (int(config["block_size"]), int(config["n_embd"])),
        "ln_f.weight": (int(config["n_embd"]),),
        "ln_f.bias": (int(config["n_embd"]),),
        "head.weight": (len(chars), int(config["n_embd"])),
    }
    for layer in range(n_layer):
        p = f"blocks.{layer}"
        n_embd = int(config["n_embd"])
        required[f"{p}.ln1.weight"] = (n_embd,)
        required[f"{p}.ln1.bias"] = (n_embd,)
        required[f"{p}.attn.qkv.weight"] = (3 * n_embd, n_embd)
        required[f"{p}.attn.proj.weight"] = (n_embd, n_embd)
        required[f"{p}.ln2.weight"] = (n_embd,)
        required[f"{p}.ln2.bias"] = (n_embd,)
        required[f"{p}.mlp.0.weight"] = (4 * n_embd, n_embd)
        required[f"{p}.mlp.0.bias"] = (4 * n_embd,)
        required[f"{p}.mlp.2.weight"] = (n_embd, 4 * n_embd)
        required[f"{p}.mlp.2.bias"] = (n_embd,)

    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    total_params = 0
    for name in sorted(required):
        if name not in state:
            raise BrainLoopError(f"export_portable: checkpoint missing tensor {name!r}")
        t = state[name]
        try:
            arr = t.detach().to("cpu").float().numpy().astype("<f4")
        except Exception as exc:
            raise BrainLoopError(
                f"export_portable: tensor {name!r} not convertible "
                f"({exc.__class__.__name__})"
            ) from exc
        if tuple(arr.shape) != required[name]:
            raise BrainLoopError(
                f"export_portable: tensor {name!r} shape {tuple(arr.shape)} != "
                f"expected {required[name]}"
            )
        raw = arr.tobytes()
        blob_name = f"{name}.f32"
        (out_dir / blob_name).write_bytes(raw)
        entries.append(
            {
                "name": name,
                "shape": list(arr.shape),
                "dtype": "float32",
                "byteorder": "little",
                "file": blob_name,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        total_params += arr.size

    manifest = {
        "format": PORTABLE_FORMAT,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exporter": "levi.brain.learn_eval.export_portable",
        "source": str(pt_path),
        "architecture": "char-gpt",
        "config": {
            "n_layer": int(config["n_layer"]),
            "n_head": int(config["n_head"]),
            "n_embd": int(config["n_embd"]),
            "block_size": int(config["block_size"]),
        },
        "chars": list(chars),
        "vocab_size": len(chars),
        "total_params": total_params,
        "tensors": entries,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8"
    )
    return {
        "out_dir": str(out_dir),
        "total_params": total_params,
        "tensors": len(entries),
    }


# ---------------------------------------------------------------- production model wrapper


class RuntimeScoredModel(ScoredModel):
    """ScoredModel backed by the torch-free runtime (lazy import so this
    module stays importable even while runtime.py is being edited)."""

    def __init__(self, portable_dir: Path, *, backend: Optional[str] = None):
        from levi.brain import runtime as _rt

        manifest, _blobs = _rt.load_portable_tensors(str(portable_dir))
        self._rt = _rt
        self._manifest = manifest
        self.vocab_chars = list(manifest["chars"])
        self._stoi = {c: i for i, c in enumerate(self.vocab_chars)}
        self._handle = _rt.load_runtime_brain(portable_dir=str(portable_dir))
        # Force the requested backend through a fresh handle if needed.
        self._backend = backend or "numpy"
        self.label = str(portable_dir)

    def _window_loss(self, ids: List[int], eps: float) -> Tuple[float, int, int]:
        total = 0.0
        scored = 0
        excluded = 0
        for t in range(len(ids)):
            target = ids[t]
            if target < 0:
                excluded += 1
                total += -math.log(eps)
                continue
            logits = self._handle.logits_for(ids[: t + 1])
            m = max(logits)
            exps = [math.exp(v - m) for v in logits]
            z = sum(exps)
            p = exps[target] / z
            total += -math.log(max(p, eps))
            scored += 1
        return total, scored, excluded

    def ce_loss(self, text: str) -> Tuple[float, int, int]:
        ids = [self._stoi.get(ch, -1) for ch in text]
        return self._window_loss(ids, 1e-9)

    def generate(
        self, prompt: str, max_new_chars: int, temperature: float, seed: int
    ) -> Dict[str, Any]:
        res = self._handle.generate(
            prompt,
            max_new_chars=max_new_chars,
            temperature=temperature,
            seed=seed,
        )
        return {
            "continuation": res.get("continuation", ""),
            "unmapped_chars": int(res.get("unmapped_chars", 0)),
        }


# ---------------------------------------------------------------- measurement


@dataclass
class GateScores:
    heldout_candidate: float = math.inf
    heldout_incumbent: float = math.inf
    positions_scored: int = 0
    val_chars_excluded: int = 0
    val_chars_total: int = 0
    behavioral: List[Dict[str, Any]] = field(default_factory=list)
    regret_candidate: float = math.inf
    regret_incumbent: float = math.inf
    regret_skipped: str = ""
    candidate_label: str = ""
    incumbent_label: str = ""
    backend: str = ""


def _sample_windows(
    text: str, *, windows: int, window_chars: int, seed: int
) -> List[str]:
    if len(text) <= window_chars:
        return [text] if text else []
    rng = random.Random(seed)
    starts = [rng.randrange(0, len(text) - window_chars + 1) for _ in range(windows)]
    return [text[s : s + window_chars] for s in sorted(starts)]


def heldout_nats(
    model: ScoredModel, val_text: str, *, windows: int, window_chars: int, seed: int
) -> Dict[str, Any]:
    """Mean cross-entropy (nats/char) over seeded windows of val_text."""
    total = 0.0
    scored = 0
    excluded = 0
    chars_total = 0
    for w in _sample_windows(
        val_text, windows=windows, window_chars=window_chars, seed=seed
    ):
        chars_total += len(w)
        t, s, e = model.ce_loss(w)
        total += t
        scored += s
        excluded += e
    denom = scored + excluded
    mean = (total / denom) if denom else math.inf
    return {
        "mean_nats": mean,
        "positions_scored": scored,
        "chars_excluded": excluded,
        "chars_total": chars_total,
    }


def run_behavioral_checks(
    model: ScoredModel,
    prompts: Optional[List[str]] = None,
    *,
    seed: int = 1337,
) -> List[Dict[str, Any]]:
    """Deterministic behavioral checks. Each returns
    {"name", "passed", "detail"} — failures never raise, they report."""
    prompts = prompts or ["the ", "levi "]
    out: List[Dict[str, Any]] = []
    vocab = set(model.vocab_chars)

    # 1. deterministic argmax: same seed twice -> identical text
    try:
        a = model.generate(prompts[0], 64, 0.0, seed)["continuation"]
        b = model.generate(prompts[0], 64, 0.0, seed)["continuation"]
        passed = a == b and len(a) > 0
        detail = f"identical={a == b} len={len(a)}"
    except Exception as exc:  # noqa: BLE001 — checks report, never raise
        passed, detail = False, f"{exc.__class__.__name__}: {exc}"
    out.append({"name": "deterministic_argmax", "passed": passed, "detail": detail})

    # 2-3. charset adherence + no collapse, over all prompts
    bad_chars = 0
    degenerate = 0
    n_gen = 0
    try:
        for p in prompts:
            cont = model.generate(p, 64, 0.0, seed)["continuation"]
            n_gen += 1
            bad_chars += sum(1 for ch in cont if ch not in vocab)
            if cont:
                uniq = len(set(cont)) / len(cont)
                if uniq < 0.05:
                    degenerate += 1
            else:
                degenerate += 1
        passed_charset = bad_chars == 0 and n_gen > 0
        passed_collapse = degenerate == 0 and n_gen > 0
        d1 = f"bad_chars={bad_chars} over {n_gen} generations"
        d2 = f"degenerate={degenerate} over {n_gen} generations"
    except Exception as exc:  # noqa: BLE001
        passed_charset, passed_collapse = False, False
        d1 = d2 = f"{exc.__class__.__name__}: {exc}"
    out.append({"name": "charset_adherence", "passed": passed_charset, "detail": d1})
    out.append({"name": "no_collapse", "passed": passed_collapse, "detail": d2})

    # 4. corrupt input is handled honestly, not crashed on
    try:
        res = model.generate("the \U0001f600 quick", 32, 0.0, seed)
        unmapped = int(res.get("unmapped_chars", 0))
        passed = unmapped >= 1
        detail = f"unmapped_chars={unmapped}"
    except Exception as exc:  # noqa: BLE001
        passed, detail = False, f"{exc.__class__.__name__}: {exc}"
    out.append({"name": "unmapped_honest", "passed": passed, "detail": detail})
    return out


def measure_scores(
    *,
    candidate: ScoredModel,
    incumbent: ScoredModel,
    val_text: str,
    anchors: List[Dict[str, str]],
    eval_windows: int = 6,
    eval_window_chars: int = 40,
    seed: int = 1337,
    backend: str = "",
) -> GateScores:
    """Measure everything the gate decides on. Pure measurement — no file
    ops, no decisions."""
    scores = GateScores(
        candidate_label=getattr(candidate, "label", "candidate"),
        incumbent_label=getattr(incumbent, "label", "incumbent"),
        backend=backend,
    )
    hc = heldout_nats(
        candidate,
        val_text,
        windows=eval_windows,
        window_chars=eval_window_chars,
        seed=seed,
    )
    hi = heldout_nats(
        incumbent,
        val_text,
        windows=eval_windows,
        window_chars=eval_window_chars,
        seed=seed,
    )
    scores.heldout_candidate = hc["mean_nats"]
    scores.heldout_incumbent = hi["mean_nats"]
    scores.positions_scored = hc["positions_scored"]
    scores.val_chars_excluded = hc["chars_excluded"] + hi["chars_excluded"]
    scores.val_chars_total = hc["chars_total"]
    scores.behavioral = run_behavioral_checks(candidate, seed=seed)

    if anchors:
        anchor_texts = [
            (a.get("prompt", "") + "\n" + a.get("continuation", "")) for a in anchors
        ]
        rc = sum(candidate.ce_loss(t)[0] for t in anchor_texts)
        ri = sum(incumbent.ce_loss(t)[0] for t in anchor_texts)
        n = sum(len(t) for t in anchor_texts) or 1
        scores.regret_candidate = rc / n
        scores.regret_incumbent = ri / n
    else:
        scores.regret_skipped = (
            "no anchors recorded yet — this promotion will capture them"
        )
    return scores


# ---------------------------------------------------------------- the gate


def gate_decision(
    scores: GateScores, *, promote_margin: float, regret_margin: float
) -> Tuple[str, List[str]]:
    """Promote or reject. Returns (decision, reasons). Conservative by
    design: any failed check, any insufficient improvement, any sign of
    catastrophic forgetting -> reject with the explicit reason."""
    reasons: List[str] = []
    failed = [c["name"] for c in scores.behavioral if not c.get("passed")]
    if failed:
        reasons.append(f"behavioral checks failed: {', '.join(failed)}")
    delta = scores.heldout_incumbent - scores.heldout_candidate
    if not math.isfinite(delta):
        reasons.append("held-out loss not measurable for one or both models")
    elif delta < promote_margin:
        reasons.append(
            f"held-out improvement {delta:.4f} nats < required margin "
            f"{promote_margin:.4f} "
            f"(candidate {scores.heldout_candidate:.4f} vs "
            f"incumbent {scores.heldout_incumbent:.4f} over "
            f"{scores.positions_scored} positions)"
        )
    if not scores.regret_skipped and math.isfinite(scores.regret_candidate):
        if scores.regret_candidate > scores.regret_incumbent + regret_margin:
            reasons.append(
                "regret check failed: candidate forgot anchor behavior "
                f"(candidate {scores.regret_candidate:.4f} vs incumbent "
                f"{scores.regret_incumbent:.4f} + margin {regret_margin:.4f})"
            )
    if reasons:
        return "reject", reasons
    return "promote", [
        f"held-out {scores.heldout_incumbent:.4f} -> "
        f"{scores.heldout_candidate:.4f} nats "
        f"(improvement {delta:.4f} >= margin {promote_margin:.4f}); "
        f"{len(scores.behavioral)} behavioral checks passed; "
        + (
            "regret check passed"
            if not scores.regret_skipped
            else "regret check skipped (first anchors captured now)"
        )
    ]


# ---------------------------------------------------------------- lineage + anchors


def lineage_path(weights_dir: Path) -> Path:
    return Path(weights_dir) / "lineage.jsonl"


def append_lineage(weights_dir: Path, entry: Dict[str, Any]) -> Path:
    path = lineage_path(weights_dir)
    record = dict(entry)
    record.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def read_lineage(weights_dir: Path, limit: int = 20) -> List[Dict[str, Any]]:
    path = lineage_path(weights_dir)
    if not path.is_file():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out[-limit:]


def anchors_path(weights_dir: Path) -> Path:
    return Path(weights_dir) / "anchors.json"


def load_anchors(weights_dir: Path) -> List[Dict[str, str]]:
    p = anchors_path(weights_dir)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [a for a in data if isinstance(a, dict)]


def capture_anchors(
    incumbent: ScoredModel, *, k: int = 8, seed: int = 1337
) -> List[Dict[str, str]]:
    """Record what the incumbent does on fixed prompts, temperature 0.
    The NEXT cycle's regret check measures the next candidate against
    these texts."""
    anchors = []
    for prompt in ANCHOR_PROMPTS[: max(1, k)]:
        try:
            cont = incumbent.generate(prompt, 64, 0.0, seed)["continuation"]
        except Exception:  # noqa: BLE001 — anchors are best-effort
            cont = ""
        anchors.append({"prompt": prompt, "continuation": cont, "seed": seed})
    return anchors


# ---------------------------------------------------------------- promote / rollback


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def promote(
    *,
    candidate_pt: Path,
    candidate_portable_dir: Path,
    weights_dir: Path,
    lineage_entry: Dict[str, Any],
    incumbent: Optional[ScoredModel],
    anchors_k: int = 8,
    seed: int = 1337,
    validate_fn: Optional[Callable[[Path], None]] = None,
) -> Dict[str, Any]:
    """Install the candidate as the live weights. Keeps the previous
    weights + portable export as rollback artifacts. Validates the new
    portable export before considering the promotion complete — any
    failure restores the previous weights and raises honestly.

    ``incumbent`` may be None (anchors are then skipped and the lineage
    says so); ``validate_fn`` overrides the default runtime validation
    (tests inject a no-op against synthetic fixtures)."""
    weights_dir = Path(weights_dir)
    live_pt = weights_dir / "tiny-gpt.pt"
    live_portable = weights_dir / "tiny-gpt-portable"
    if not live_pt.is_file():
        raise BrainLoopError(f"promote: no live weights at {live_pt}")
    candidate_pt = Path(candidate_pt)
    candidate_portable_dir = Path(candidate_portable_dir)
    if not candidate_pt.is_file():
        raise BrainLoopError(f"promote: candidate weights missing at {candidate_pt}")
    if not (candidate_portable_dir / "manifest.json").is_file():
        raise BrainLoopError(
            f"promote: candidate portable export missing at {candidate_portable_dir}"
        )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_pt = weights_dir / f"tiny-gpt.prev-{ts}.pt"
    backup_portable = weights_dir / f"tiny-gpt-portable.prev-{ts}"
    parent_sha = _sha256_file(live_pt)
    new_sha = _sha256_file(candidate_pt)

    # Validate the candidate portable export BEFORE touching live weights.
    if validate_fn is not None:
        validate_fn(candidate_portable_dir)
    else:
        from levi.brain import runtime as _rt

        try:
            _rt.load_portable_tensors(str(candidate_portable_dir))
        except Exception as exc:
            raise BrainLoopError(
                f"promote: candidate portable export failed validation "
                f"({exc}) — live weights untouched"
            ) from exc

    def _validate_live() -> None:
        if validate_fn is not None:
            validate_fn(live_portable)
            return
        from levi.brain import runtime as _rt

        _rt.load_portable_tensors(str(live_portable))

    anchors = capture_anchors(incumbent, k=anchors_k, seed=seed) if incumbent else []
    shutil.copy2(live_pt, backup_pt)
    if live_portable.is_dir():
        shutil.copytree(live_portable, backup_portable)
    try:
        shutil.copy2(candidate_pt, live_pt)
        if live_portable.is_dir():
            shutil.rmtree(live_portable)
        shutil.copytree(candidate_portable_dir, live_portable)
        _validate_live()
    except Exception as exc:
        # Restore: live weights must never be left half-installed.
        shutil.copy2(backup_pt, live_pt)
        if backup_portable.is_dir():
            if live_portable.is_dir():
                shutil.rmtree(live_portable)
            shutil.copytree(backup_portable, live_portable)
        raise BrainLoopError(
            f"promote: install failed ({exc}) — previous weights restored"
        ) from exc

    anchors_path(weights_dir).write_text(
        json.dumps(anchors, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    entry = dict(lineage_entry)
    entry.update(
        {
            "kind": "promote",
            "parent_sha256": parent_sha,
            "new_sha256": new_sha,
            "rollback_pt": backup_pt.name,
            "rollback_portable": backup_portable.name
            if backup_portable.is_dir()
            else "",
            "anchors_captured": len(anchors),
        }
    )
    append_lineage(weights_dir, entry)
    return {
        "new_sha256": new_sha,
        "parent_sha256": parent_sha,
        "rollback_pt": str(backup_pt),
        "anchors": len(anchors),
    }


def list_rollbacks(weights_dir: Path) -> List[Path]:
    return sorted(Path(weights_dir).glob("tiny-gpt.prev-*.pt"))


def rollback(
    weights_dir: Path, *, to: Optional[str] = None, reason: str = ""
) -> Dict[str, Any]:
    """Restore a previous weights file as the live weights (one command).
    Also restores its portable export when present. Appends a lineage
    entry of kind=rollback. Raises BrainLoopError when nothing exists."""
    weights_dir = Path(weights_dir)
    candidates = list_rollbacks(weights_dir)
    if not candidates:
        raise BrainLoopError("rollback: no previous weights found — nothing to restore")
    target: Optional[Path] = None
    if to:
        for c in candidates:
            if c.name == to or str(c) == to:
                target = c
                break
        if target is None:
            raise BrainLoopError(f"rollback: no such backup {to!r}")
    else:
        target = candidates[-1]
    live_pt = weights_dir / "tiny-gpt.pt"
    live_portable = weights_dir / "tiny-gpt-portable"
    prev_pt = weights_dir / "tiny-gpt.pt.pre-rollback"
    if live_pt.is_file():
        shutil.copy2(live_pt, prev_pt)
    shutil.copy2(target, live_pt)
    portable_restored = False
    backup_portable = weights_dir / target.name.replace(
        "tiny-gpt.prev-", "tiny-gpt-portable.prev-"
    ).replace(".pt", "")
    if backup_portable.is_dir():
        if live_portable.is_dir():
            shutil.rmtree(live_portable)
        shutil.copytree(backup_portable, live_portable)
        portable_restored = True
    append_lineage(
        weights_dir,
        {
            "kind": "rollback",
            "restored_from": target.name,
            "restored_sha256": _sha256_file(live_pt),
            "portable_restored": portable_restored,
            "reason": reason,
        },
    )
    return {
        "restored_from": target.name,
        "sha256": _sha256_file(live_pt),
        "portable_restored": portable_restored,
    }
