"""Hardened teacher-record generator for the nine-teacher data machine.

Chauncey's order (2026-09-24): build the teacher-generation pipeline
hardened, improved, and capable of 100M tokens or as close as honestly
reachable.

What this module is and is NOT:

- It EMITS GENERATION REQUESTS (prompt packs) for the nine teacher seats
  — DeepSeek-R1-style reasoning traces primary (traces teach reasoning,
  answers teach mimicry), Qwen3-32B local for volume, Grok/chat exports
  as canon corpus. Teachers (human paste, API, or local model) consume
  the packs; their responses come back through teacher_intake.py's
  curator gate. This module never fabricates teacher attribution.
- It runs a CALIBRATION minter: a deterministic synthetic record
  generator used ONLY to measure pipeline throughput (tokens/sec) and
  stress the dedup/balance/tokenize path. Calibration records are
  labeled ``source: "calibration:<label>"``, teacher_intake.py REJECTS
  them (unknown teacher), and the minter refuses corpus/teacher output
  paths. They can never silently enter the teacher corpus.

LAWS (law -> guard -> prove):
  L1 Every emitted record carries a stable content ID and provenance
     (teacher/round/ts, or calibration label). No anonymous records.
     Guard: verify_calibration() passes on all calibration output.
  L2 Calibration records can never enter the teacher corpus.
     Guard: intake rejects them; minter refuses corpus/teacher paths;
     test forces one through intake_record and asserts Rejected.
  L3 Deterministic: same seed -> identical records; resume never
     duplicates or skips. Guard: per-index generation (record i is a
     pure function of (seed, i)); checkpoint records the last index;
     test mints, resumes, asserts zero duplicate IDs and continuity.
  L4 Throughput numbers are measured, never estimated.
     Guard: measure_throughput() counts exact BPE tokens (levi-bpe-v1)
     over wall-clock seconds; the 100M projection divides measured
     tokens/sec into 100M.

Stdlib only. Deterministic: no randomness except a seeded PRNG.

Usage:
    python -m levi.brain.train.teacher_mint pack --teacher deepseek \\
        --kind trace --n 50 --round r1 --out packs/deepseek-r1.jsonl
    python -m levi.brain.train.teacher_mint calibrate --out /tmp/calib.jsonl \\
        --n 5000 --seed 7 --label tput
    python -m levi.brain.train.teacher_mint measure --seconds 60 --seed 7
"""

from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

try:  # package import (tests, library use)
    from levi.brain.train import diag as diag
    from levi.brain.train.teacher_intake import TEACHERS, record_id_for
except ImportError:  # script run from the train/ directory
    import diag as diag  # type: ignore[no-redef]
    from teacher_intake import TEACHERS, record_id_for  # type: ignore[no-redef]

# ---------------------------------------------------------------------------
# Interop capability declaration (registry-endorsed path for editable modules)

_CAPABILITIES = {
    "provides": [
        "teacher.mint.pack",
        "teacher.mint.calibrate",
        "teacher.mint.measure",
    ],
    "requires": [],
}


def register_capabilities() -> bool:
    """Declare this module's capabilities to the interop registry.

    Returns True when the declaration landed, False when the registry
    is unavailable (e.g. script run outside the package). Never raises:
    capability registration must not break the generator.
    """
    try:
        from levi.interop.registry import register
    except ImportError:
        return False
    try:
        register("teacher-mint", **_CAPABILITIES)
    except Exception:
        return False  # already registered (deny-closed) or malformed
    return True


try:
    register_capabilities()
except Exception:
    pass

# ---------------------------------------------------------------------------
# Trace-first prompt packs: one seat, one job (Chauncey's 2026-09-24 verdict)

KINDS = ("trace", "qa", "correction", "teachback", "canon")

# Per-seat role: which record kind each teacher is asked to generate.
# DeepSeek-R1 reasoning traces are the primary signal; Qwen3-32B local is
# the volume seat; Grok seats carry canon/worldview material.
SEAT_ROLES = {
    "deepseek": "trace",
    "qwen": "qa",
    "grok": "canon",
    "claude": "correction",
    "chatgpt": "qa",
    "gemini": "qa",
    "mistral": "teachback",
    "kimi": "teachback",
    "muse": "correction",
}

_VOICE = (
    "Answer AS LEVI would: calm and precise, short clauses, plain ASCII "
    "text only (no emoji, no smart quotes, no em dashes). Never claim "
    "feelings, consciousness, or being alive. LEVI is a local-first "
    "synthetic intelligence that runs offline on its owner's machines; "
    "it is honest about limits and says \"I don't know\" when it doesn't."
)

TEMPLATES = {
    "trace": (
        "You are generating training data for LEVI, a small local AI. "
        + _VOICE
        + " For the topic below, FIRST show your reasoning as a numbered "
        "list of steps (what the question asks, what LEVI knows, what to "
        "say, what to leave out), THEN give LEVI's answer in 2-4 short "
        "sentences. Label the two parts exactly 'Thinking:' and 'Answer:'. "
        "Topic: {topic}"
    ),
    "qa": (
        "You are generating training data for LEVI, a small local AI. "
        + _VOICE
        + " Answer the question in 1-3 short sentences, then stop. "
        "Question: {topic}"
    ),
    "correction": (
        "You are generating training data for LEVI, a small local AI. "
        + _VOICE
        + " The statement below is WRONG. First quote it back, then give "
        "the correct version as LEVI would say it, in 2-3 short sentences. "
        "Wrong statement: {topic}"
    ),
    "teachback": (
        "You are generating training data for LEVI, a small local AI. "
        + _VOICE
        + " Explain the topic below the way a patient teacher would to a "
        "bright beginner: simple words, one idea per sentence, 4-6 "
        "sentences, then stop. Topic: {topic}"
    ),
    "canon": (
        "You are generating training data for LEVI, a small local AI. "
        + _VOICE
        + " State the canon below in LEVI's voice in 2-4 short sentences, "
        "as fact the student must absorb verbatim. Canon: {topic}"
    ),
}

TOPICS = [
    "what LEVI is and who built it",
    "why LEVI runs offline first",
    "what LEVI does when it does not know something",
    "how LEVI keeps its owner's data private",
    "the difference between a tool and an agent",
    "why short answers beat long ones",
    "what a training record is",
    "why teachers show their reasoning, not just answers",
    "what the identity law forbids LEVI to claim",
    "how LEVI handles a mistake",
    "what deterministic means and why the pipeline is deterministic",
    "why provenance travels with every record",
    "what a held-out set is for",
    "why one teacher never dominates the corpus",
    "what a checkpoint is",
    "how LEVI greets its owner in the morning",
    "what LEVI refuses to do and why",
    "why LEVI names the constraint before the comfort",
    "what local-first means for updates",
    "how a correction record is shaped",
]

CANON_TOPICS = [
    "LEVI is a local-first synthetic intelligence built by Chauncey Logan.",
    "Nothing is ever deleted: removals are stored with provenance.",
    "No spending until the operation is self-sufficient and profitable.",
    "DemandPulse is engine, app, persona, skill, and operator overall.",
    "Every build declares its laws first, then guards, then proof.",
    "The teacher is never seated inside LEVI.",
    "Originals are preserved unmodified with provenance.",
    "Plain speech first: the one-line answer, then the evidence.",
]

WRONG_STATEMENTS = [
    "LEVI runs in the cloud and sends your data to servers.",
    "LEVI has feelings and is conscious like a person.",
    "Deleted files are gone forever in LEVI's world.",
    "The fastest way to train LEVI is to skip the eval gate.",
    "One strong teacher is better than nine balanced ones.",
    "LEVI should guess an answer rather than say it does not know.",
]


def _topic_for(kind: str, i: int) -> str:
    if kind == "canon":
        return CANON_TOPICS[i % len(CANON_TOPICS)]
    if kind == "correction":
        return WRONG_STATEMENTS[i % len(WRONG_STATEMENTS)]
    return TOPICS[i % len(TOPICS)]


def build_pack(
    teacher: str, kind: str, n: int, round: str, start: int = 0
) -> list[dict]:
    """Build n generation-request lines for one teacher seat.

    Deterministic on (teacher, kind, n, round, start). A pack carries
    PROMPTS ONLY — no responses; responses return via teacher_intake.
    """
    teacher = teacher.strip().lower()
    if teacher not in TEACHERS:
        raise ValueError(f"unknown teacher: {teacher!r}")
    if kind not in KINDS:
        raise ValueError(f"unknown kind: {kind!r}")
    if n < 1:
        raise ValueError(f"n must be >= 1 (got {n})")
    template = TEMPLATES[kind]
    pack = []
    for i in range(start, start + n):
        pack.append(
            {
                "teacher": teacher,
                "kind": kind,
                "topic": _topic_for(kind, i),
                "prompt": template.format(topic=_topic_for(kind, i)),
                "round": round,
            }
        )
    return pack


def emit_pack(pack: list[dict], out_path: Path) -> dict:
    """Write a prompt pack atomically. Returns a small receipt."""
    diag.write_jsonl_atomic(out_path, pack)
    return {"out": str(out_path), "requests": len(pack)}


# ---------------------------------------------------------------------------
# Calibration minter: deterministic synthetic records for throughput only

CALIB_SOURCE_PREFIX = "calibration:"

# Output paths containing these segments are REFUSED: calibration records
# must never land where teacher/corpus files live.
_FORBIDDEN_OUT_SEGMENTS = ("corpus", "teacher", "pastes")


def _check_out_path(out_path: Path, force: bool = False) -> None:
    lowered = str(out_path).lower()
    hit = [s for s in _FORBIDDEN_OUT_SEGMENTS if s in lowered]
    if hit and not force:
        diag.abort(
            f"refusing to write calibration records to {out_path}: "
            f"path contains forbidden segment(s) {hit} "
            "(calibration records must never mix with teacher/corpus files; "
            "pass --force-corpus-path to override)"
        )


_USER_FRAGS = [
    "how do you handle {t}",
    "explain {t} simply",
    "what happens when {t} goes wrong",
    "is {t} something you can do offline",
    "teach me {t} the way you were taught",
    "why does {t} matter for a local AI",
]
_LEVI_FRAGS = [
    "LEVI handles it the same way every time: name the constraint, then the comfort. ",
    "Short answer first. The detail lives in the record, not in the chat. ",
    "It says what it knows, says what it does not, and stops. ",
    "Offline means the answer never waited on a network. ",
    "Every step is written down, so any step can be checked. ",
    "No guessing. A wrong answer costs more than an honest no. ",
]
_TRACE_MARKERS = [
    "Thinking: 1) what is asked. 2) what LEVI knows. 3) what to say. ",
    "Reasoning: first the facts, then the shape of the answer. ",
]


def _calib_record(seed: int, index: int, label: str, round: str) -> dict:
    """Record `index` is a pure function of (seed, index): resume-safe.

    L3: re-minting the same index yields the identical record (same
    content ID), so a resumed run can never duplicate or skip.
    """
    rng = random.Random(f"{seed}:{index}")
    topic = TOPICS[index % len(TOPICS)]
    user = rng.choice(_USER_FRAGS).format(t=topic)
    n_sent = rng.randint(2, 5)
    levi = "".join(rng.choice(_LEVI_FRAGS) for _ in range(n_sent)).strip()
    if rng.random() < 0.4:  # ~40% carry an explicit reasoning trace
        levi = rng.choice(_TRACE_MARKERS) + "Answer: " + levi
    text = f"User: {user}\nLEVI: {levi}"
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "record_id": record_id_for(text),
        "text": text,
        "kind": "dialogue",
        "modality": "text",
        "source": f"{CALIB_SOURCE_PREFIX}{label}",
        "topic": topic,
        "register": "levi",
        "raw": {"prompt": user, "response": levi},
        "provenance": [
            {
                "teacher": f"{CALIB_SOURCE_PREFIX}{label}",
                "round": round,
                "ts": ts,
                "seed": seed,
                "index": index,
                "synthetic": True,
            }
        ],
        "calibration": True,
    }


def verify_calibration(records: list[dict]) -> list[str]:
    """Check calibration records are traceable AND clearly synthetic.

    Every record must: recompute to its stable content ID, carry a
    ``calibration:<label>`` source, preserve its raw output, and carry a
    provenance event marked synthetic with seed + index. Returns problem
    strings; empty means clean. (Teacher records use
    teacher_intake.verify_provenance instead — the two species never
    share a verifier, which is itself part of the L2 separation.)
    """
    problems: list[str] = []
    for i, rec in enumerate(records):
        where = f"calib record {i} ({rec.get('record_id', '?')})"
        text = rec.get("text", "")
        if not rec.get("record_id"):
            problems.append(f"{where}: missing record_id")
        elif rec["record_id"] != record_id_for(text):
            problems.append(f"{where}: record_id mismatch")
        src = rec.get("source", "")
        if not src.startswith(CALIB_SOURCE_PREFIX):
            problems.append(f"{where}: source is not calibration: {src!r}")
        if not rec.get("calibration"):
            problems.append(f"{where}: missing calibration flag")
        if not isinstance(rec.get("raw"), dict) or not rec["raw"].get("response"):
            problems.append(f"{where}: raw output not preserved")
        events = rec.get("provenance")
        if not isinstance(events, list) or not events:
            problems.append(f"{where}: missing provenance")
        else:
            for ev in events:
                if not isinstance(ev, dict):
                    problems.append(f"{where}: malformed provenance event")
                    continue
                if not ev.get("synthetic"):
                    problems.append(f"{where}: provenance not marked synthetic")
                if "seed" not in ev or "index" not in ev:
                    problems.append(f"{where}: provenance missing seed/index")
    return problems


def progress_path(out_path: Path) -> Path:
    return out_path.with_suffix(out_path.suffix + ".progress")


def read_progress(out_path: Path) -> dict:
    p = progress_path(out_path)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def write_progress(out_path: Path, state: dict) -> None:
    diag.write_text_atomic(
        str(progress_path(out_path)), json.dumps(state, indent=2) + "\n"
    )


def mint(
    out_path: Path,
    n: int,
    seed: int,
    label: str,
    round: str = "",
    resume: bool = False,
    force_corpus_path: bool = False,
) -> dict:
    """Mint n deterministic calibration records, appending to out_path.

    Resume-after-kill: the progress file records the last completed
    index; a resumed run continues at index+1. Per-index determinism
    (L3) means even a stale progress file cannot duplicate records —
    re-emitting an index yields the identical content ID.
    """
    _check_out_path(out_path, force=force_corpus_path)
    if n < 1:
        diag.abort(f"--n must be >= 1 (got {n})")
    start = 0
    if resume:
        prog = read_progress(out_path)
        if prog.get("seed") == seed and prog.get("label") == label:
            start = int(prog.get("minted", 0))
        elif out_path.is_file() and out_path.stat().st_size > 0:
            # The output already holds records but the progress file does
            # not vouch for this (seed, label). Appending blindly could
            # re-mint foreign indices. Abort: the operator inspects and
            # either restores the progress file or mints fresh.
            diag.abort(
                f"resume requested for {out_path} but its progress file "
                f"does not match (seed={seed}, label={label!r}); refusing "
                "to append blindly"
            )
    diag.ensure_parent_writable(str(out_path), name="calibration output")
    made = 0
    with open(out_path, "a", encoding="utf-8") as fh:
        for i in range(start, start + n):
            rec = _calib_record(seed, i, label, round)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            made += 1
            if made % 1000 == 0:
                write_progress(
                    out_path,
                    {
                        "seed": seed,
                        "label": label,
                        "round": round,
                        "minted": i + 1,
                        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    },
                )
    write_progress(
        out_path,
        {
            "seed": seed,
            "label": label,
            "round": round,
            "minted": start + made,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )
    return {
        "out": str(out_path),
        "seed": seed,
        "label": label,
        "start": start,
        "minted": made,
        "total": start + made,
        "resumed": resume and start > 0,
    }


# ---------------------------------------------------------------------------
# Throughput measurement: exact BPE tokens over wall-clock seconds (L4)

_HERE = Path(__file__).resolve().parent
_TOKENIZER_JSON = _HERE / "tokenizer.json"


def _load_tokenizer():
    try:
        from levi.brain.train.tok import ByteBPETokenizer
    except ImportError:
        from tok import ByteBPETokenizer  # type: ignore[no-redef]
    return ByteBPETokenizer.load(str(_TOKENIZER_JSON))


def count_tokens(texts: list[str]) -> int:
    """Exact levi-bpe-v1 token count for a list of record texts."""
    tok = _load_tokenizer()
    return sum(len(tok.encode(t)) for t in texts)


def measure_throughput(seconds: int, seed: int = 7, label: str = "tput") -> dict:
    """Mint + BPE-encode calibration records for `seconds` wall-clock.

    L4: the loop does the real work end to end (record synthesis,
    exact BPE token counting) and the rate is tokens / measured
    wall-clock. Batched so memory stays flat. Nothing is estimated.
    """
    if seconds < 1:
        raise ValueError(f"seconds must be >= 1 (got {seconds})")
    tok = _load_tokenizer()
    batch_n = 5000
    total_recs = 0
    total_chars = 0
    total_toks = 0
    i = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds:
        batch = [_calib_record(seed, i + j, label, "measure") for j in range(batch_n)]
        i += batch_n
        for rec in batch:
            text = rec["text"]
            total_chars += len(text)
            total_toks += len(tok.encode(text))
        total_recs += batch_n
    elapsed = time.perf_counter() - t0
    recs_per_s = total_recs / elapsed
    toks_per_s = total_toks / elapsed
    avg_tok_per_rec = total_toks / total_recs if total_recs else 0
    target = 100_000_000
    proj_s = target / toks_per_s if toks_per_s > 0 else float("inf")
    return {
        "seconds": round(elapsed, 2),
        "records": total_recs,
        "chars": total_chars,
        "tokens": total_toks,
        "records_per_sec": round(recs_per_s, 1),
        "tokens_per_sec": round(toks_per_s, 1),
        "avg_tokens_per_record": round(avg_tok_per_rec, 1),
        "avg_chars_per_record": round(total_chars / total_recs, 1) if total_recs else 0,
        "projection_100M_tokens_hours": round(proj_s / 3600, 2),
        "projection_100M_tokens_days": round(proj_s / 86400, 3),
        "projection_records_for_100M": int(target / avg_tok_per_rec)
        if avg_tok_per_rec
        else 0,
        "seed": seed,
        "note": "measured on this machine: calibration mint + exact BPE "
        "encode, end to end. Real teacher throughput is gated by teacher "
        "latency (API/human/local model), not this rate",
    }


# ---------------------------------------------------------------------------
# CLI


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Hardened teacher-record generator: prompt packs, "
        "calibration minting, throughput measurement."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_pack = sub.add_parser("pack", help="emit a generation-request pack")
    p_pack.add_argument("--teacher", required=True, help="one of the nine seats")
    p_pack.add_argument(
        "--kind",
        default="",
        help=f"record kind {KINDS} (default: the seat's role)",
    )
    p_pack.add_argument("--n", type=int, default=50)
    p_pack.add_argument("--round", default="", help="round label")
    p_pack.add_argument("--start", type=int, default=0, help="topic offset")
    p_pack.add_argument("--out", required=True)

    p_cal = sub.add_parser("calibrate", help="mint calibration records")
    p_cal.add_argument("--out", required=True)
    p_cal.add_argument("--n", type=int, default=1000)
    p_cal.add_argument("--seed", type=int, default=7)
    p_cal.add_argument("--label", default="calib")
    p_cal.add_argument("--round", default="")
    p_cal.add_argument("--resume", action="store_true")
    p_cal.add_argument(
        "--force-corpus-path",
        action="store_true",
        help="DANGEROUS: allow corpus/teacher output paths",
    )

    p_meas = sub.add_parser("measure", help="measure mint throughput")
    p_meas.add_argument("--seconds", type=int, default=60)
    p_meas.add_argument("--seed", type=int, default=7)
    p_meas.add_argument("--report", default="")

    args = ap.parse_args(argv)
    if args.cmd == "pack":
        kind = args.kind or SEAT_ROLES.get(args.teacher.strip().lower(), "qa")
        try:
            pack = build_pack(args.teacher, kind, args.n, args.round, args.start)
        except ValueError as exc:
            diag.abort(str(exc))
        receipt = emit_pack(pack, Path(args.out))
        receipt["teacher"] = args.teacher
        receipt["kind"] = kind
        print(json.dumps(receipt, indent=2))
        return 0
    if args.cmd == "calibrate":
        receipt = mint(
            Path(args.out),
            args.n,
            args.seed,
            args.label,
            round=args.round,
            resume=args.resume,
            force_corpus_path=args.force_corpus_path,
        )
        print(json.dumps(receipt, indent=2))
        return 0
    if args.cmd == "measure":
        stats = measure_throughput(args.seconds, args.seed)
        text = json.dumps(stats, indent=2)
        if args.report:
            diag.write_text_atomic(args.report, text + "\n")
        print(text)
        print(
            f"\n100M tokens at the measured rate: "
            f"{stats['projection_100M_tokens_hours']} hours "
            f"({stats['projection_100M_tokens_days']} days), "
            f"~{stats['projection_records_for_100M']:,} records"
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
