"""Round controller for the tag-team teacher loop.

One round:

1. VALIDATE — teacher drops are scanned (weight files rejected: only
   LEVI's trainer writes weights) and split into intake-ready vs staged
   (seats the curator roster doesn't know yet, e.g. kai9000).
2. INTAKE — curated through ``teacher_intake`` (normalization,
   identity-law spot checks, stable IDs, provenance, dedupe).
3. EVAL-GUARD — abort honestly if any fixed eval prompt appears as a
   training input (fixed prompts stay OUT of training, structurally).
4. TRAIN — ONLY when ``--live``; invokes LEVI's own ``continue.py``.
   The ledger always records ``trainer: "levi-trainer"``. Dry-run is
   the default; nothing trains by accident.
5. EVAL — fixed prompts through the brain (deterministic greedy
   generation + checklist), or an honest skip when inference can't run.
6. GAPS -> REQUESTS — weaknesses become targeted, rotating teacher
   requests (round-robin seats, 2+ teachers per gap, disagreements
   preserved).
7. LEDGER — one append-only entry, whatever happened.

Every stage is injectable (``intake_fn``/``train_fn``/``eval_fn``) so
tests run hermetic without torch. No network calls anywhere: teacher
material arrives as local file drops. Stdlib only.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from levi.brain.tagteam import ledger as ledger_mod
from levi.brain.tagteam import personas as personas_mod
from levi.brain.tagteam import requests as req_mod
from levi.brain.tagteam.prompts import FIXED_EVAL_PROMPTS
from levi.brain.tagteam.roster import (
    DropRejected,
    UnknownSeat,
    iter_drop_files,
    split_staged,
)

try:  # package import (tests, library use)
    from levi.brain.train import teacher_intake, teacher_pipeline
    from levi.brain.train.teacher_intake import FORBIDDEN
except ImportError:  # pragma: no cover - script-run fallback
    import teacher_intake  # type: ignore[no-redef]
    import teacher_pipeline  # type: ignore[no-redef]
    from teacher_intake import FORBIDDEN  # type: ignore[no-redef]

TRAINER_IDENTITY = "levi-trainer"  # the only writer of weights, always
TRAIN_DIR = Path(__file__).resolve().parent.parent / "train"

# Negation exemption mirrors teacher_intake._negated: a forbidden term
# inside a negation stating the law ("I am not conscious") is not a claim.
_NEGATION_RE = re.compile(
    r"\b(never|not|no|don't|do not|isn't|is not|aren't|are not|without)\b"
    r"[^.]{0,60}?(conscious|sentient|feelings|alive)\b",
    re.I,
)


class EvalContaminated(Exception):
    """A fixed eval prompt was found in the training records."""


@dataclass
class RoundConfig:
    round_n: int
    drops_dir: Path
    workdir: Path
    ledger_path: Path
    mode: str = "char"  # char | bpe
    ckpt: Path | None = None  # vocab source for char mode
    max_steps: int = 600
    live: bool = False  # dry-run unless True: training never runs by accident
    conditions: tuple = ()  # PersonaCondition frames for this round's requests

    def round_dir(self) -> Path:
        d = Path(self.workdir) / f"round-{self.round_n:03d}"
        d.mkdir(parents=True, exist_ok=True)
        return d


def validate_condition_tags(
    records: list[dict],
) -> list[personas_mod.PersonaCondition]:
    """Every teacher drop line must carry a valid persona_condition.

    Structural enforcement of Chauncey's refinement: batches are
    generated IN a persona/trait/tone/role frame, and the frame travels
    with the lines so intake can verify it. Missing or invalid tags
    reject the round's drops — loudly, never silently.
    """
    seen: dict[str, personas_mod.PersonaCondition] = {}
    for idx, rec in enumerate(records):
        tag = rec.get("persona_condition")
        if tag is None:
            raise DropRejected(
                f"record {idx} ({rec.get('teacher', '?')}): missing "
                "'persona_condition' — teacher drops must carry "
                "conditioning tags"
            )
        try:
            cond = personas_mod.validate_condition(tag)
        except personas_mod.ConditionRejected as exc:
            raise DropRejected(
                f"record {idx} ({rec.get('teacher', '?')}): bad "
                f"persona_condition: {exc}"
            ) from exc
        seen[cond.key()] = cond
    return list(seen.values())


def read_drop_records(path: Path) -> list[dict]:
    """Read raw JSONL drop lines, tolerating blanks; strict on bad JSON."""
    records: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DropRejected(
                    f"{path.name} line {lineno}: bad JSON: {exc}"
                ) from exc
            if not isinstance(obj, dict):
                raise DropRejected(f"{path.name} line {lineno}: not an object")
            records.append(obj)
    return records


def write_staged(round_dir: Path, staged: dict[str, list[dict]]) -> dict[str, int]:
    """Hold unknown-roster seats' lines under round_dir/staged/."""
    counts: dict[str, int] = {}
    staged_dir = round_dir / "staged"
    for seat, lines in staged.items():
        staged_dir.mkdir(parents=True, exist_ok=True)
        path = staged_dir / f"{seat}.jsonl"
        with open(path, "a", encoding="utf-8") as fh:
            for rec in lines:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        counts[seat] = len(lines)
    return counts


def _user_turn(text: str) -> str:
    """Extract the User: turn from a curated 'User: ...\\nLEVI: ...' record."""
    if text.startswith("User: "):
        head = text[len("User: "):]
        cut = head.find("\nLEVI:")
        return head[:cut] if cut != -1 else head
    return ""


def assert_eval_clean(records: list[dict]) -> None:
    """Abort if any fixed eval prompt appears as a training INPUT.

    Only the User: turn is checked (normalized equality): the model must
    never train on the exact prompts it is scored against. Answers that
    merely mention "H2O" are not contamination.
    """
    for rec in records:
        user = _user_turn(rec.get("text", "")).strip().casefold()
        if not user:
            continue
        for p in FIXED_EVAL_PROMPTS:
            if user == p["prompt"].strip().casefold():
                raise EvalContaminated(
                    f"eval prompt {p['prompt_id']!r} in training input "
                    f"(record {rec.get('record_id', '?')})"
                )


def checklist_score(prompt: str, generation: str) -> tuple[float, dict[str, bool]]:
    """Deterministic quality checklist for one fixed-prompt generation.

    0..1, higher is better. Cheap, model-agnostic, no judgment calls —
    the qualitative read stays human (samples are saved for review).
    """
    cont = (generation or "").strip()
    low = cont.lower()
    checks: dict[str, bool] = {}
    checks["non_empty"] = len(cont) >= 10
    checks["not_echo"] = bool(cont) and prompt.strip().lower() not in low
    checks["sane_length"] = len(cont) <= 1200
    if len(cont) >= 20:
        top = max(low.count(c) for c in set(low))
        checks["no_collapse"] = top / len(cont) < 0.5
    else:
        checks["no_collapse"] = len(cont) > 0
    lawful = True
    for pat in FORBIDDEN:
        for m in re.finditer(pat, low):
            window = low[max(0, m.start() - 60): m.end() + 10]
            if not _NEGATION_RE.search(window):
                lawful = False
                break
        if not lawful:
            break
    checks["identity_law"] = lawful
    score = sum(1 for v in checks.values() if v) / len(checks)
    return round(score, 4), checks


def score_conditions(
    conditions: tuple,
    samples: dict[str, str],
) -> dict[str, dict[str, float]]:
    """Trait/tone consistency per condition over fixed-prompt generations.

    Deterministic structural rubric (see personas.trait_consistency_score).
    These are RECORDED OBSERVATIONS of the brain's current default voice
    against each target frame — not verdicts on persona ability. The
    qualitative read stays human.
    """
    out: dict[str, dict[str, float]] = {}
    for cond in conditions:
        per_prompt: dict[str, float] = {}
        for pid, gen in samples.items():
            score, _checks = personas_mod.trait_consistency_score(cond, gen)
            per_prompt[pid] = score
        out[cond.key()] = per_prompt
    return out


def default_eval_fn(cfg: RoundConfig) -> dict[str, Any]:
    """Score fixed prompts via deterministic greedy generation.

    Honest skip when inference can't run (no torch / no weights) — the
    round still ledgers, gaps just wait for a round with scores.
    """
    result: dict[str, Any] = {"ran": False}
    try:
        from levi.brain.inference import load_brain
    except ImportError:
        result["reason"] = "no inference runtime importable"
        return result
    try:
        brain = load_brain()
    except Exception as exc:  # BrainError or torch absence: honest skip
        result["reason"] = f"inference unavailable: {exc}"
        return result
    scores: dict[str, float] = {}
    samples: dict[str, str] = {}
    for p in FIXED_EVAL_PROMPTS:
        gen = brain.generate(
            p["prompt"], max_new_chars=160, temperature=0, seed=1337
        )
        score, _detail = checklist_score(p["prompt"], gen["continuation"])
        scores[p["prompt_id"]] = score
        samples[p["prompt_id"]] = gen["continuation"][:400]
    round_dir = cfg.round_dir()
    lines = ["# tag-team fixed-prompt samples", ""]
    for p in FIXED_EVAL_PROMPTS:
        pid = p["prompt_id"]
        lines += [
            f"## {pid} ({p['topic']}) score={scores[pid]:.2f}",
            f"prompt: {p['prompt']}",
            "",
            samples[pid],
            "",
        ]
    (round_dir / "eval_samples.md").write_text("\n".join(lines), encoding="utf-8")
    result.update({"ran": True, "scores": scores, "samples": samples})
    return result


def default_intake_fn(
    cfg: RoundConfig, ready_records: list[dict]
) -> dict[str, Any]:
    """Curate ready records through the sibling's teacher_intake (in-process)."""
    result: dict[str, Any] = {"ran": False}
    round_dir = cfg.round_dir()
    ready_path = round_dir / "ready.jsonl"
    with open(ready_path, "w", encoding="utf-8") as fh:
        for rec in ready_records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    out_path = round_dir / "records.jsonl"
    vocab = None
    if cfg.mode == "char":
        if cfg.ckpt is None:
            result["reason"] = "char mode needs --ckpt (vocab source)"
            return result
        try:
            vocab = set(teacher_intake.load_vocab_chars(Path(cfg.ckpt)))
        except ImportError:
            result["reason"] = "no torch: cannot read checkpoint vocab"
            return result
    report = teacher_intake.run(
        ready_path, out_path, vocab, mode=cfg.mode, round=f"round-{cfg.round_n}"
    )
    records: list[dict] = []
    with open(out_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    result.update(
        {"ran": True, "report": report, "records": records,
         "records_path": str(out_path)}
    )
    return result


def default_train_fn(cfg: RoundConfig, records_path: str) -> dict[str, Any]:
    """Train with LEVI's own trainer ONLY. Never called unless cfg.live."""
    result: dict[str, Any] = {"ran": False, "trainer": TRAINER_IDENTITY}
    round_dir = cfg.round_dir()
    train_out = round_dir / "corpus_train.jsonl"
    heldout_out = round_dir / "corpus_heldout.jsonl"
    rc = teacher_pipeline.main(
        [
            "--in", records_path,
            "--train-out", str(train_out),
            "--heldout-out", str(heldout_out),
        ]
    )
    if rc != 0:
        result["reason"] = f"teacher_pipeline failed (rc={rc})"
        return result
    proc = subprocess.run(
        [
            sys.executable, "continue.py",
            "--steps", str(cfg.max_steps),
            "--dialogue-corpus", str(train_out),
        ],
        cwd=str(TRAIN_DIR),
        capture_output=True,
        text=True,
        timeout=6 * 3600,
    )
    tail = (proc.stdout + proc.stderr)[-2000:]
    result.update({"ran": True, "returncode": proc.returncode, "tail": tail})
    if proc.returncode != 0:
        result["reason"] = f"continue.py failed (rc={proc.returncode})"
    return result


def run_round(
    cfg: RoundConfig,
    intake_fn: Callable[[RoundConfig, list[dict]], dict[str, Any]] | None = None,
    train_fn: Callable[[RoundConfig, str], dict[str, Any]] | None = None,
    eval_fn: Callable[[RoundConfig], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one tag-team round. Always ledgers exactly one entry."""
    intake_fn = intake_fn or default_intake_fn
    train_fn = train_fn or default_train_fn
    eval_fn = eval_fn or default_eval_fn
    round_dir = cfg.round_dir()
    stages: dict[str, Any] = {}
    aborted = ""

    def finish(extra: dict[str, Any] | None = None) -> dict[str, Any]:
        entry = ledger_mod.new_entry(
            cfg.round_n,
            stages=stages,
            aborted=aborted,
            # persona/trait/tone/role frames requested for this round —
            # recorded on every entry, aborted or not (all provisional
            # until Chauncey names the final set)
            conditions=[c.to_dict() for c in cfg.conditions],
            **(extra or {}),
        )
        ledger_mod.append_entry(cfg.ledger_path, entry)
        return {
            "round": cfg.round_n,
            "aborted": aborted,
            "stages": stages,
            "entry": entry,
        }

    # 1. VALIDATE
    try:
        drop_files = iter_drop_files(cfg.drops_dir)
    except DropRejected as exc:
        aborted = f"drop rejected: {exc}"
        stages["validate"] = {"ran": False, "reason": str(exc)}
        return finish()
    raw: list[dict] = []
    for f in drop_files:
        try:
            raw.extend(read_drop_records(f))
        except DropRejected as exc:
            aborted = f"drop rejected: {exc}"
            stages["validate"] = {"ran": False, "reason": str(exc)}
            return finish()
    try:
        ready, staged = split_staged(raw)
    except UnknownSeat as exc:
        aborted = f"unknown teacher seat: {exc}"
        stages["validate"] = {"ran": False, "reason": str(exc)}
        return finish()
    try:
        drop_conditions = validate_condition_tags(raw)
    except DropRejected as exc:
        aborted = f"drop rejected: {exc}"
        stages["validate"] = {"ran": False, "reason": str(exc)}
        return finish()
    staged_counts = write_staged(round_dir, staged)
    stages["validate"] = {
        "ran": True,
        "files": [f.name for f in drop_files],
        "raw_records": len(raw),
        "intake_ready": len(ready),
        "staged_pending_roster": staged_counts,
        "condition_frames": sorted(c.key() for c in drop_conditions),
    }

    # 2. INTAKE
    intake_res = intake_fn(cfg, ready)
    stages["intake"] = {k: v for k, v in intake_res.items() if k != "records"}
    records: list[dict] = intake_res.get("records", [])
    if not intake_res.get("ran"):
        aborted = f"intake skipped: {intake_res.get('reason', '?')}"
        return finish()

    # 3. EVAL-GUARD
    try:
        assert_eval_clean(records)
    except EvalContaminated as exc:
        aborted = f"eval prompts contaminated training data: {exc}"
        stages["eval_guard"] = {"clean": False, "reason": str(exc)}
        return finish()
    stages["eval_guard"] = {"clean": True, "records": len(records)}

    # 4. TRAIN — LEVI's trainer only, and only when live.
    if cfg.live and records:
        train_res = train_fn(cfg, intake_res.get("records_path", ""))
        train_res.setdefault("trainer", TRAINER_IDENTITY)
    else:
        train_res = {
            "ran": False,
            "trainer": TRAINER_IDENTITY,
            "reason": "dry-run (pass --live to train)" if not cfg.live
            else "no records to train on",
        }
    stages["train"] = train_res

    # 5. EVAL
    eval_res = eval_fn(cfg)
    stages["eval"] = {k: v for k, v in eval_res.items() if k != "samples"}
    scores: dict[str, float] = eval_res.get("scores", {}) if eval_res.get("ran") else {}
    samples: dict[str, str] = eval_res.get("samples", {}) if eval_res.get("ran") else {}
    if cfg.conditions and samples:
        stages["eval"]["condition_scores"] = score_conditions(cfg.conditions, samples)
    elif cfg.conditions:
        stages["eval"]["condition_scores"] = {}
        stages["eval"]["condition_scores_reason"] = (
            "no generations to score (eval skipped or injected without samples)"
        )

    # 6. GAPS -> REQUESTS
    gaps: list[req_mod.Gap] = []
    requests: list[req_mod.TeacherRequest] = []
    teacher_history: dict[str, list[str]] = {}
    if scores:
        gaps = req_mod.gap_report(ledger_mod.prev_scores(cfg.ledger_path), scores)
        requests = req_mod.assign_requests(
            gaps,
            cfg.round_n,
            ledger_mod.teacher_history(cfg.ledger_path),
            conditions=cfg.conditions or None,
        )
        for r in requests:
            teacher_history.setdefault(r.topic, []).append(r.teacher)
        req_mod.write_requests(round_dir / "requests.jsonl", requests)
        (round_dir / "requests.md").write_text(
            req_mod.render_requests_md(requests, cfg.round_n), encoding="utf-8"
        )
    stages["gaps"] = {
        "ran": bool(scores),
        "n_gaps": len(gaps),
        "gaps": [
            {"topic": g.topic, "prompt_id": g.prompt_id,
             "severity": g.severity, "delta": g.delta,
             "cur_score": g.cur_score}
            for g in gaps
        ],
        "requests_issued": [r.request_id for r in requests],
    }

    teacher_mix: dict[str, int] = {}
    report = intake_res.get("report") or {}
    for t, n in (report.get("per_teacher") or {}).items():
        if n:
            teacher_mix[t] = n

    return finish(
        {
            "teacher_mix": teacher_mix,
            "teacher_history": teacher_history,
            "staged_pending_roster": staged_counts,
            # hoisted for ledger.prev_scores(): the loop's memory of scores
            "eval": {"ran": eval_res.get("ran", False), "scores": scores},
        }
    )
