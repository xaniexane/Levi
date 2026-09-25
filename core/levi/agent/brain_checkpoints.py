"""Native-brain checkpoint manifests and honest capability gates.

The native brain is LEVI's own transformer, trained from scratch on
LEVI's own corpus. Training is the SCAFFOLD/IMPROVE worker's job; this
module is the INTEGRATE worker's contract for *selecting* checkpoints
by measurement instead of vibes.

Checkpoint discovery (stdlib only):

* The weights directory is ``core/levi/brain/weights/``
  (``LEVI_BRAIN_WEIGHTS`` selects one file inside it explicitly, or any
  path — see below).
* Every ``*.pt`` file in that directory is a checkpoint candidate.
* A checkpoint's eval report is ``<stem>.eval.json`` next to the
  ``<stem>.pt`` file — e.g. ``tiny-gpt.eval.json`` beside
  ``tiny-gpt.pt``. **This is the extension point for the v2 harness:
  drop ``model_v2.pt`` + ``model_v2.eval.json`` in this directory and
  status/gating pick them up automatically, no code change.**
* Legacy fallback: a bare ``eval.json`` in the weights dir root applies
  to ``tiny-gpt.pt`` when ``tiny-gpt.eval.json`` is absent, and
  ``train_log.json`` supplies params/steps when the manifest omits them.

Manifest schema (all fields optional; missing fields just mean the
gate has less evidence):

    {
      "checkpoint": "tiny-gpt.pt",
      "held_out_loss": 1.857,
      "perplexity": 6.4,          # derived as exp(loss) when omitted
      "eval_date": "2026-09-15",  # ISO date
      "corpus_version": "academy+main v1",
      "params": 3271168,
      "steps": 600,
      "generated_by": "core/levi/brain/train/eval.py",
      "tool_use": {"pass_rate": 0.0, "n": 0}   # when a tool-use eval exists
    }

The v2 train harness's ``EvalReport`` JSON
(``core/levi/brain/train/v2/eval_harness.py`` — ``model_name``,
``perplexity.perplexity``, ``created_at``, probe accuracies) is ALSO
understood: it is normalized to the manifest shape on read, so a
harness report dropped next to a checkpoint Just Works without the
harness adopting this schema. Probe accuracies are kept as
``probes.next_token_accuracy`` / ``probes.topic_accuracy`` (display
only — they are NOT tool-use evidence for the gate).

Capability gates — a checkpoint only becomes eligible for heavier
duties when its eval report meets DOCUMENTED thresholds (the numbers
live in ``GATES`` and in ``docs/BRAIN_TRAINING.md`` §"Capability gates"):

* ``prose-only`` — weights present. Always granted; the provider never
  emits tool calls at this tier (see ``levi.agent.brain_provider``).
* ``tool-loop-candidate`` — eval report present, held_out_loss <= 1.20,
  and a tool-use eval with pass_rate >= 0.80 on n >= 50. The checkpoint
  may be considered for the step-level tool loop.
* ``default-candidate`` — tool-loop tier plus held_out_loss <= 1.00,
  tool-use pass_rate >= 0.90, and an eval no older than 180 days. Only
  at this tier does the checkpoint earn the default slot of the
  provider chain (``model_family.resolve_family``); below it the
  native brain stays explicit-only, honestly.

Today's reality (2026-09-15): the trained checkpoint reports
held_out_loss 1.857 — prose-only, and the status line says exactly
why. No consciousness or sentience claims are made anywhere here;
these are capability measurements, not minds.

Stdlib only. Never spawns, never downloads, never raises on malformed
input — a corrupt manifest is a checkpoint with no eval evidence.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Gate thresholds — the documented numbers (docs/BRAIN_TRAINING.md)
# ---------------------------------------------------------------------------

#: held_out_loss ceiling for tool-loop candidacy.
TOOL_LOOP_MAX_LOSS = 1.20
#: tool-use eval pass-rate floor for tool-loop candidacy (n >= 50).
TOOL_LOOP_MIN_TOOL_PASS = 0.80
TOOL_LOOP_MIN_TOOL_N = 50
#: held_out_loss ceiling for default-slot candidacy.
DEFAULT_MAX_LOSS = 1.00
#: tool-use eval pass-rate floor for default-slot candidacy (n >= 50).
DEFAULT_MIN_TOOL_PASS = 0.90
#: eval freshness ceiling (days) for default-slot candidacy.
DEFAULT_MAX_EVAL_AGE_DAYS = 180

GATES = {
    "tool_loop": {
        "held_out_loss_max": TOOL_LOOP_MAX_LOSS,
        "tool_use_pass_rate_min": TOOL_LOOP_MIN_TOOL_PASS,
        "tool_use_n_min": TOOL_LOOP_MIN_TOOL_N,
    },
    "default": {
        "held_out_loss_max": DEFAULT_MAX_LOSS,
        "tool_use_pass_rate_min": DEFAULT_MIN_TOOL_PASS,
        "tool_use_n_min": TOOL_LOOP_MIN_TOOL_N,
        "eval_max_age_days": DEFAULT_MAX_EVAL_AGE_DAYS,
    },
}

#: Tiers in ascending order of trust.
TIERS = ("prose-only", "tool-loop-candidate", "default-candidate")


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def weights_dir() -> Path:
    """Directory holding native-brain checkpoints."""
    override = os.environ.get("LEVI_BRAIN_WEIGHTS", "").strip()
    if override:
        p = Path(override).expanduser()
        if p.suffix == ".pt" and p.parent.is_dir():
            return p.parent
    # Default: the shipped weights dir next to brain_provider.py.
    return Path(__file__).resolve().parent.parent / "brain" / "weights"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return _normalize_eval_report(data)


def _normalize_eval_report(data: dict[str, Any]) -> dict[str, Any]:
    """Accept the v2 harness's ``EvalReport`` JSON as a manifest.

    ``EvalReport.to_dict()`` has ``model_name``, ``step``,
    ``created_at``, ``perplexity: {perplexity: ...}``,
    ``next_token: {accuracy: ...}``, ``topic: {accuracy: ...}``,
    ``notes``. A flat manifest (``held_out_loss`` etc.) passes
    through untouched; an EvalReport-shaped dict is mapped to the
    manifest shape so status and gating read it without the harness
    changing its format. Never raises.
    """
    try:
        ppl_block = data.get("perplexity")
        is_report = isinstance(data.get("model_name"), str) and isinstance(
            ppl_block, dict
        )
        if not is_report:
            return data
        out: dict[str, Any] = {}
        try:
            ppl = (
                float(ppl_block.get("perplexity"))
                if ppl_block.get("perplexity") is not None
                else None
            )
        except (TypeError, ValueError):
            ppl = None
        if ppl is not None and ppl > 0:
            out["perplexity"] = ppl
            try:
                out["held_out_loss"] = math.log(ppl)
            except (ValueError, OverflowError):
                pass
        created = data.get("created_at")
        if isinstance(created, str) and len(created.strip()) >= 10:
            out["eval_date"] = created.strip()[:10]
        step = data.get("step")
        try:
            out["steps"] = int(step) if step is not None else None
        except (TypeError, ValueError):
            pass
        if out.get("steps") is None:
            out.pop("steps", None)
        params = data.get("params")
        try:
            if params is not None:
                out["params"] = int(params)
        except (TypeError, ValueError):
            pass
        corpus = data.get("corpus_version") or data.get("corpus")
        if isinstance(corpus, str) and corpus.strip():
            out["corpus_version"] = corpus.strip()
        probes: dict[str, Any] = {}
        for key, label in (
            ("next_token", "next_token_accuracy"),
            ("topic", "topic_accuracy"),
        ):
            block = data.get(key)
            if isinstance(block, dict):
                try:
                    acc = block.get("accuracy")
                    if acc is not None:
                        probes[label] = float(acc)
                except (TypeError, ValueError):
                    pass
        if probes:
            out["probes"] = probes
        notes = data.get("notes")
        if isinstance(notes, list) and notes:
            out["eval_notes"] = [str(n)[:200] for n in notes[:5]]
        out["generated_by"] = "core/levi/brain/train/v2/eval_harness.py"
        model_name = data.get("model_name") or ""
        if model_name:
            out["checkpoint"] = (
                model_name
                if str(model_name).endswith(".pt")
                else str(model_name) + ".pt"
            )
        return out
    except Exception:
        return data


@dataclass
class Checkpoint:
    """One ``*.pt`` file plus its eval evidence (or lack of it)."""

    name: str  # stem, e.g. "tiny-gpt"
    path: Path
    eval: dict[str, Any] = field(default_factory=dict)
    manifest_path: Path | None = None
    legacy_fallback: bool = False  # eval came from the root eval.json (v1 tiny-gpt)

    @property
    def file(self) -> str:
        return self.path.name

    @property
    def architecture(self) -> str:
        """Model architecture the checkpoint was trained as.

        Declared by the manifest's ``architecture`` field. The legacy
        root-``eval.json`` fallback is definitionally the v1 TinyGPT
        checkpoint, so it reports ``tiny-gpt``; per-stem manifests
        without the field report ``unknown`` rather than guessing.
        """
        if self.legacy_fallback:
            return "tiny-gpt"
        arch = self.eval.get("architecture")
        if isinstance(arch, str) and arch.strip():
            return arch.strip()
        return "unknown"

    @property
    def has_eval(self) -> bool:
        return bool(self.eval) and self.eval.get("held_out_loss") is not None

    @property
    def held_out_loss(self) -> float | None:
        v = self.eval.get("held_out_loss")
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def perplexity(self) -> float | None:
        v = self.eval.get("perplexity")
        try:
            if v is not None:
                return float(v)
        except (TypeError, ValueError):
            pass
        loss = self.held_out_loss
        if loss is None:
            return None
        try:
            return math.exp(loss)
        except (OverflowError, ValueError):
            return None


def _legacy_eval_for(stem: str, directory: Path) -> tuple[dict[str, Any], Path | None]:
    """The pre-manifest ``eval.json`` + ``train_log.json`` root files.

    These describe the original tiny-gpt training run; they apply to
    ``tiny-gpt.pt`` only, and only when ``tiny-gpt.eval.json`` is
    absent. Never raises.
    """
    if stem != "tiny-gpt":
        return {}, None
    merged: dict[str, Any] = {}
    src: Path | None = None
    ev = _read_json(directory / "eval.json")
    if ev:
        merged.update(ev)
        src = directory / "eval.json"
    log = _read_json(directory / "train_log.json")
    for key in ("params", "steps", "loss_first", "loss_last", "loss_min"):
        if key in log and key not in merged:
            merged[key] = log[key]
    return merged, src


def discover(directory: Path | None = None) -> list[Checkpoint]:
    """All ``*.pt`` checkpoints in the weights dir, best-evaluated first.

    Never raises: an unreadable directory yields []. Malformed
    manifests are treated as missing eval evidence. v2 (and later)
    checkpoints appear here automatically once their ``*.pt`` +
    ``*.eval.json`` land in the directory.
    """
    directory = Path(directory) if directory is not None else weights_dir()
    try:
        pts = sorted(
            (p for p in directory.iterdir() if p.suffix == ".pt" and p.is_file()),
            key=lambda p: p.name,
        )
    except Exception:
        return []
    out: list[Checkpoint] = []
    for pt in pts:
        stem = pt.stem
        manifest = directory / (stem + ".eval.json")
        eval_data = _read_json(manifest) if manifest.is_file() else {}
        manifest_path = manifest if manifest.is_file() and eval_data else None
        legacy_fallback = False
        if not eval_data:
            legacy, legacy_src = _legacy_eval_for(stem, directory)
            eval_data, manifest_path = legacy, legacy_src
            legacy_fallback = bool(eval_data)
        if eval_data:
            eval_data.setdefault("checkpoint", pt.name)
        out.append(
            Checkpoint(
                name=stem,
                path=pt,
                eval=eval_data,
                manifest_path=manifest_path,
                legacy_fallback=legacy_fallback,
            )
        )
    # Best-measured first: lowest held_out_loss, then name. Checkpoints
    # with no eval sink to the bottom (they stay prose-only).
    out.sort(
        key=lambda c: (
            c.held_out_loss if c.held_out_loss is not None else math.inf,
            c.name,
        )
    )
    return out


def get(name: str, directory: Path | None = None) -> Checkpoint | None:
    """One checkpoint by stem (``"tiny-gpt"``), or None."""
    for ckpt in discover(directory):
        if ckpt.name == name:
            return ckpt
    return None


# ---------------------------------------------------------------------------
# Capability gates
# ---------------------------------------------------------------------------


@dataclass
class GateResult:
    tier: str  # one of TIERS
    meets: dict[str, bool]  # threshold name -> met?
    reasons: list[str]  # human-readable, one line each; the "why" for status

    @property
    def tool_loop_eligible(self) -> bool:
        return self.tier in ("tool-loop-candidate", "default-candidate")

    @property
    def default_eligible(self) -> bool:
        return self.tier == "default-candidate"


def _tool_use(eval_data: dict[str, Any]) -> tuple[float | None, int]:
    tu = eval_data.get("tool_use")
    if not isinstance(tu, dict):
        return None, 0
    try:
        rate = float(tu.get("pass_rate")) if tu.get("pass_rate") is not None else None
    except (TypeError, ValueError):
        rate = None
    try:
        n = int(tu.get("n") or 0)
    except (TypeError, ValueError):
        n = 0
    return rate, n


def _eval_age_days(eval_data: dict[str, Any]) -> int | None:
    raw = eval_data.get("eval_date")
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    for fmt, width in (
        ("%Y-%m-%d", 10),
        ("%Y-%m-%dT%H:%M:%S", 19),
        ("%Y-%m-%dT%H:%M:%SZ", 20),
    ):
        try:
            d = _dt.datetime.strptime(text[:width], fmt).date()
            return (_dt.date.today() - d).days
        except ValueError:
            continue
    return None


def gate_for(checkpoint: Checkpoint) -> GateResult:
    """The capability tier a checkpoint has EARNED by measurement.

    Below-threshold checkpoints stay prose-only with reasons that name
    the exact gap. Never raises.
    """
    meets: dict[str, bool] = {}
    reasons: list[str] = []

    loss = checkpoint.held_out_loss
    if loss is None:
        meets["eval_present"] = False
        reasons.append(
            "no eval report (%s.eval.json) — prose-only until measured"
            % checkpoint.name
        )
        return GateResult(tier="prose-only", meets=meets, reasons=reasons)
    meets["eval_present"] = True

    # --- tool-loop tier ------------------------------------------------
    tl_loss_ok = loss <= TOOL_LOOP_MAX_LOSS
    meets["tool_loop_loss"] = tl_loss_ok
    rate, n = _tool_use(checkpoint.eval)
    tl_tool_ok = (
        rate is not None
        and rate >= TOOL_LOOP_MIN_TOOL_PASS
        and n >= TOOL_LOOP_MIN_TOOL_N
    )
    meets["tool_loop_tool_use"] = tl_tool_ok
    if not tl_loss_ok:
        reasons.append(
            "held_out_loss %.3f above tool-loop ceiling %.2f — prose-only"
            % (loss, TOOL_LOOP_MAX_LOSS)
        )
    if not tl_tool_ok:
        if rate is None:
            reasons.append(
                "no tool-use eval in the manifest — prose-only "
                "(tool-loop candidacy needs pass_rate >= %.2f on n >= %d)"
                % (TOOL_LOOP_MIN_TOOL_PASS, TOOL_LOOP_MIN_TOOL_N)
            )
        else:
            reasons.append(
                "tool-use eval pass_rate %.2f (n=%d) below %.2f — prose-only"
                % (rate, n, TOOL_LOOP_MIN_TOOL_PASS)
            )
    if not (tl_loss_ok and tl_tool_ok):
        return GateResult(tier="prose-only", meets=meets, reasons=reasons)

    # --- default tier ---------------------------------------------------
    d_loss_ok = loss <= DEFAULT_MAX_LOSS
    meets["default_loss"] = d_loss_ok
    d_tool_ok = (
        rate is not None and rate >= DEFAULT_MIN_TOOL_PASS and n >= TOOL_LOOP_MIN_TOOL_N
    )
    meets["default_tool_use"] = d_tool_ok
    age = _eval_age_days(checkpoint.eval)
    d_fresh_ok = age is not None and age <= DEFAULT_MAX_EVAL_AGE_DAYS
    meets["default_eval_fresh"] = d_fresh_ok
    if not d_loss_ok:
        reasons.append(
            "held_out_loss %.3f above default ceiling %.2f — tool-loop candidate only"
            % (loss, DEFAULT_MAX_LOSS)
        )
    if not d_tool_ok:
        reasons.append(
            "tool-use eval pass_rate %.2f (n=%d) below default floor %.2f"
            % (rate or 0.0, n, DEFAULT_MIN_TOOL_PASS)
        )
    if not d_fresh_ok:
        if age is None:
            reasons.append("no eval_date in the manifest — default needs a dated eval")
        else:
            reasons.append(
                "eval is %d days old (limit %d) — re-evaluate for the default slot"
                % (age, DEFAULT_MAX_EVAL_AGE_DAYS)
            )
    if d_loss_ok and d_tool_ok and d_fresh_ok:
        reasons.append(
            "meets all default thresholds (loss <= %.2f, tool-use >= %.2f, eval fresh)"
            % (DEFAULT_MAX_LOSS, DEFAULT_MIN_TOOL_PASS)
        )
        return GateResult(tier="default-candidate", meets=meets, reasons=reasons)
    reasons.append(
        "tool-loop candidate: eligible for heavier duties, not the default slot"
    )
    return GateResult(tier="tool-loop-candidate", meets=meets, reasons=reasons)


def best_default_candidate(directory: Path | None = None) -> Checkpoint | None:
    """The highest-tier checkpoint eligible for the default slot, or None.

    This is the earning mechanism: the native brain wins the default
    provider slot only when a checkpoint MEASURES as a default
    candidate. Until then it stays explicit-only (standing policy).
    """
    earned = [c for c in discover(directory) if gate_for(c).default_eligible]
    return earned[0] if earned else None


def status_report(directory: Path | None = None) -> dict[str, Any]:
    """JSON-able report: every checkpoint with eval numbers + gate tier."""
    out: list[dict[str, Any]] = []
    for ckpt in discover(directory):
        gate = gate_for(ckpt)
        ev = ckpt.eval
        out.append(
            {
                "name": ckpt.name,
                "file": ckpt.file,
                "held_out_loss": ckpt.held_out_loss,
                "perplexity": ckpt.perplexity,
                "eval_date": ev.get("eval_date"),
                "corpus_version": ev.get("corpus_version"),
                "params": ev.get("params"),
                "steps": ev.get("steps"),
                "probes": ev.get("probes"),
                "manifest": str(ckpt.manifest_path) if ckpt.manifest_path else None,
                "architecture": ckpt.architecture,
                "tier": gate.tier,
                "tool_loop_eligible": gate.tool_loop_eligible,
                "default_eligible": gate.default_eligible,
                "why": gate.reasons,
            }
        )
    return {
        "weights_dir": str(Path(directory) if directory is not None else weights_dir()),
        "checkpoints": out,
    }
