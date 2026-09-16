"""v2 eval harness: honest held-out numbers, never inflated.

Measures:
  - held-out perplexity on tokenized validation text
  - next-token accuracy on curated synthetic probes
  - topic-classification accuracy on curated synthetic probes

Compares a candidate checkpoint against a baseline checkpoint and writes a
JSON report. The report states plainly when the model is "not capable":
scores near chance are labeled as such, not dressed up.

Model contract (kept tiny so any backend plugs in)::

    model.logits_for_batch(prefixes) -> np.ndarray  # (B, V) float logits

Tokenizer contract: ``encode(str) -> list[int]``, ``decode(list[int]) -> str``,
``vocab_size: int``.

Probe file format (JSONL, synthetic fixtures only — never real user data):

    {"kind": "next_token", "prefix": "Operating systems manage",
     "expected": " resources"}
    {"kind": "topic", "text": "Photosynthesis converts light into",
     "choices": [{"label": "biology", "text": " chemical energy"},
                 {"label": "history", "text": " ancient empires"}]}

The first listed choice is the correct label by fixture convention. Choices
are shuffled (seeded) before scoring so positional bias cannot inflate
scores; ties therefore land at chance instead of on the answer.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import numpy as np


class EvalError(RuntimeError):
    """Eval failed (bad probes, model contract violation, NaNs)."""


class ModelProto(Protocol):
    def logits_for_batch(self, prefixes: list[list[int]]) -> np.ndarray: ...


class TokenizerProto(Protocol):
    @property
    def vocab_size(self) -> int: ...

    def encode(self, text: str) -> list[int]: ...

    def decode(self, ids: list[int]) -> str: ...


# ---------------------------------------------------------------------------
# Core scoring


def _log_softmax(logits: np.ndarray) -> np.ndarray:
    m = logits.max(axis=-1, keepdims=True)
    shifted = logits - m
    return shifted - np.log(np.exp(shifted).sum(axis=-1, keepdims=True))


def _check_logits(logits: np.ndarray, n_prefixes: int, vocab_size: int) -> None:
    if logits.shape != (n_prefixes, vocab_size):
        raise EvalError(
            f"model contract violated: logits_for_batch returned shape "
            f"{logits.shape}, expected ({n_prefixes}, {vocab_size})"
        )
    if not np.all(np.isfinite(logits)):
        raise EvalError("model returned non-finite logits; cannot score")


def sequence_nll(
    model: ModelProto, tok: TokenizerProto, ids: list[int], *, max_len: int = 512
) -> tuple[float, int]:
    """Total negative log-likelihood and token count for one id sequence."""
    total = 0.0
    count = 0
    for start in range(0, len(ids), max_len):
        chunk = ids[start : start + max_len]
        if len(chunk) < 2:
            continue
        prefixes = [chunk[:i] for i in range(1, len(chunk))]
        logits = np.asarray(model.logits_for_batch(prefixes), dtype=np.float64)
        _check_logits(logits, len(prefixes), tok.vocab_size)
        logp = _log_softmax(logits)
        targets = np.asarray(chunk[1:], dtype=np.int64)
        if targets.min() < 0 or targets.max() >= tok.vocab_size:
            raise EvalError("tokenizer produced ids outside vocab range")
        total += float(-logp[np.arange(len(targets)), targets].sum())
        count += len(targets)
    return total, count


def perplexity(
    model: ModelProto,
    tok: TokenizerProto,
    token_ids: list[int],
    *,
    max_len: int = 512,
) -> dict:
    """Held-out perplexity. Returns {"perplexity", "n_tokens", "nll_per_token"}."""
    nll, count = sequence_nll(model, tok, token_ids, max_len=max_len)
    if count == 0:
        raise EvalError("no scorable tokens in validation input")
    nll_per_token = nll / count
    return {
        "perplexity": float(math.exp(min(nll_per_token, 50.0))),
        "nll_per_token": float(nll_per_token),
        "n_tokens": count,
    }


def next_token_accuracy(
    model: ModelProto, tok: TokenizerProto, probes: list[dict]
) -> dict:
    """Argmax next-token accuracy on ``{"prefix", "expected"}`` probes."""
    if not probes:
        return {"accuracy": None, "n": 0, "correct": 0, "note": "no probes"}
    prefixes = [tok.encode(p["prefix"]) for p in probes]
    expected = [tok.encode(p["expected"]) for p in probes]
    for p, e in zip(probes, expected, strict=True):
        if not p["prefix"] or not e:
            raise EvalError(f"probe has empty prefix/expected: {p!r}")
    logits = np.asarray(model.logits_for_batch(prefixes), dtype=np.float64)
    _check_logits(logits, len(prefixes), tok.vocab_size)
    pred = logits.argmax(axis=-1)
    correct = sum(int(pr == exp[0]) for pr, exp in zip(pred, expected, strict=True))
    return {"accuracy": correct / len(probes), "n": len(probes), "correct": correct}


def _choice_logprob(
    model: ModelProto, tok: TokenizerProto, prefix_ids: list[int], choice_ids: list[int]
) -> float:
    ids = prefix_ids + choice_ids
    prefixes = [ids[: len(prefix_ids) + i] for i in range(len(choice_ids))]
    logits = np.asarray(model.logits_for_batch(prefixes), dtype=np.float64)
    _check_logits(logits, len(prefixes), tok.vocab_size)
    logp = _log_softmax(logits)
    targets = np.asarray(choice_ids, dtype=np.int64)
    return float(logp[np.arange(len(targets)), targets].sum())


def topic_classification_accuracy(
    model: ModelProto, tok: TokenizerProto, probes: list[dict], *, seed: int = 0
) -> dict:
    """Pick the highest-logprob choice; accuracy over ``{"text", "choices"}``.

    ``choices`` is [{"label", "text"}]; the first choice is the correct one
    by fixture convention. Choices are shuffled with ``seed`` before scoring
    so a model cannot score above chance by positional bias (e.g. always
    picking the first-listed choice on ties).
    """
    if not probes:
        return {"accuracy": None, "n": 0, "correct": 0, "note": "no probes"}
    rng = random.Random(seed)
    correct = 0
    for p in probes:
        if not p.get("choices"):
            raise EvalError(f"topic probe has no choices: {p!r}")
        correct_label = p["choices"][0]["label"]
        order = list(p["choices"])
        rng.shuffle(order)
        prefix_ids = tok.encode(p["text"])
        scored = [
            (c["label"], _choice_logprob(model, tok, prefix_ids, tok.encode(c["text"])))
            for c in order
        ]
        best = max(scored, key=lambda s: s[1])[0]
        if best == correct_label:
            correct += 1
    n = len(probes)
    return {"accuracy": correct / n, "n": n, "correct": correct}


# ---------------------------------------------------------------------------
# Probes


def load_probes(path: str | Path) -> tuple[list[dict], list[dict]]:
    """Load probe JSONL -> (next_token_probes, topic_probes)."""
    path = Path(path)
    if not path.is_file():
        raise EvalError(f"probe file not found: {path}")
    nt, topic = [], []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                probe = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EvalError(f"{path}:{lineno}: bad JSON: {exc}") from exc
            kind = probe.get("kind")
            if kind == "next_token":
                nt.append(probe)
            elif kind == "topic":
                topic.append(probe)
            else:
                raise EvalError(f"{path}:{lineno}: unknown probe kind {kind!r}")
    return nt, topic


# ---------------------------------------------------------------------------
# Reports: honest, comparative, plain-spoken


@dataclass
class EvalReport:
    model_name: str
    step: int
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    perplexity: dict = field(default_factory=dict)
    next_token: dict = field(default_factory=dict)
    topic: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _capability_note(name: str, accuracy: float | None, chance: float) -> str:
    if accuracy is None:
        return f"{name}: no probes ran — capability untested, not assumed."
    if accuracy <= chance + 0.05:
        return (
            f"{name}: accuracy {accuracy:.2f} is at/near chance ({chance:.2f}) — "
            "the model is NOT capable at this task."
        )
    if accuracy < 0.5:
        return (
            f"{name}: accuracy {accuracy:.2f} is below 0.50 — weak, "
            "not reliable for decisions."
        )
    return f"{name}: accuracy {accuracy:.2f} — modest signal, verify before use."


def run_eval(
    model: ModelProto,
    tok: TokenizerProto,
    *,
    model_name: str,
    step: int,
    val_token_ids: list[int] | None = None,
    probes_path: str | Path | None = None,
) -> EvalReport:
    """Run the full eval suite and return an honest report."""
    report = EvalReport(model_name=model_name, step=step)
    if val_token_ids:
        report.perplexity = perplexity(model, tok, val_token_ids)
        ppl = report.perplexity["perplexity"]
        if ppl > 1000:
            report.notes.append(
                f"held-out perplexity {ppl:.1f} is very high — the model "
                "has not learned the validation distribution."
            )
    if probes_path:
        nt_probes, topic_probes = load_probes(probes_path)
        report.next_token = next_token_accuracy(model, tok, nt_probes)
        report.topic = topic_classification_accuracy(model, tok, topic_probes)
        report.notes.append(
            _capability_note(
                "next-token probes", report.next_token.get("accuracy"), chance=0.0
            )
        )
        if topic_probes:
            n_choices = max(len(p["choices"]) for p in topic_probes)
            report.notes.append(
                _capability_note(
                    "topic probes", report.topic.get("accuracy"), chance=1.0 / n_choices
                )
            )
    if not val_token_ids and not probes_path:
        report.notes.append("no eval inputs given — nothing was measured.")
    return report


def compare_reports(baseline: dict, candidate: dict) -> dict:
    """Before/after comparison. Deltas are signed (candidate - baseline).

    Verdicts: "improved" / "regressed" / "within noise" / "not comparable".
    Perplexity uses a 2% relative band; accuracies use a 2-point absolute band.
    """
    out: dict[str, Any] = {
        "baseline": baseline.get("model_name"),
        "candidate": candidate.get("model_name"),
        "metrics": {},
    }

    def verdict_ppl(b: float, c: float) -> str:
        if b <= 0:
            return "not comparable"
        rel = (b - c) / b  # positive = better (lower ppl)
        if rel > 0.02:
            return "improved"
        if rel < -0.02:
            return "regressed"
        return "within noise"

    def verdict_acc(b: float | None, c: float | None) -> str:
        if b is None or c is None:
            return "not comparable"
        d = c - b
        if d > 0.02:
            return "improved"
        if d < -0.02:
            return "regressed"
        return "within noise"

    bp, cp = baseline.get("perplexity", {}), candidate.get("perplexity", {})
    if bp.get("perplexity") and cp.get("perplexity"):
        out["metrics"]["perplexity"] = {
            "baseline": bp["perplexity"],
            "candidate": cp["perplexity"],
            "delta": cp["perplexity"] - bp["perplexity"],
            "verdict": verdict_ppl(bp["perplexity"], cp["perplexity"]),
        }
    for key in ("next_token", "topic"):
        b, c = baseline.get(key, {}), candidate.get(key, {})
        if b.get("accuracy") is not None and c.get("accuracy") is not None:
            out["metrics"][key] = {
                "baseline": b["accuracy"],
                "candidate": c["accuracy"],
                "delta": c["accuracy"] - b["accuracy"],
                "verdict": verdict_acc(b["accuracy"], c["accuracy"]),
            }
    verdicts = [m["verdict"] for m in out["metrics"].values()]
    if not verdicts:
        out["overall"] = "not comparable — no shared metrics"
    elif all(v == "improved" for v in verdicts):
        out["overall"] = "improved across all measured metrics"
    elif any(v == "regressed" for v in verdicts):
        out["overall"] = "regressed on at least one metric — do not promote"
    else:
        out["overall"] = "no clear change — within noise"
    out["honesty"] = (
        "Deltas are measured, not claimed. A 'within noise' result means the "
        "candidate is not demonstrably better, regardless of how it feels."
    )
    return out


def write_report(report: EvalReport, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path
