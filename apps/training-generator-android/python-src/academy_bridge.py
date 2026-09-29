"""Training Generator Android bridge.

JSON in/out wrappers over the on-device LEVI Boot Camp engine
(core/levi/academy): 120 sessions / 30 days, battle rhythm
BRIEF->TEACH->REVIEW->DRILL->TEST->DEBRIEF, mastery gates
(80% lesson / 70% drill), spaced repetition, remediation on failed gates,
session 120 = the graduation crucible.

Every function returns a JSON string. The Java side never touches Python
objects directly.

Call set_data_dir() FIRST (before any other call) so the academy uses
the app's files dir instead of ~/.levi.
"""

from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

_DATA_DIR: str | None = None


def _ensure():
    if _DATA_DIR is None:
        raise RuntimeError("data dir not set — call set_data_dir first")
    os.environ["LEVI_ACADEMY_DIR"] = _DATA_DIR
    import levi.academy.run_session as rs  # noqa: E402

    return rs


def set_data_dir(path: str) -> str:
    global _DATA_DIR
    _DATA_DIR = path
    Path(path).mkdir(parents=True, exist_ok=True)
    return json.dumps({"ok": True})


def _err(exc: BaseException) -> str:
    return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def _track_of(rs, n: int) -> str:
    day, block = rs.n_to_day_block(n)
    track, _ = rs.entry_for(rs.load_syllabus(), day, block)
    return track


def status() -> str:
    """Overall progress: completed/120, next session, streaks, gates."""
    try:
        rs = _ensure()
        progress = rs.load_progress()
        syllabus = rs.load_syllabus()
        completed = progress.get("completed", [])
        nxt = rs.next_uncompleted(progress)
        day, block = rs.n_to_day_block(nxt)
        track, entry = rs.entry_for(syllabus, day, block)
        return json.dumps({
            "ok": True,
            "program": syllabus.get("program", ""),
            "completed": len(completed),
            "total": syllabus.get("sessions_total", 120),
            "graduated": bool(progress.get("graduated")),
            "pending_remedial": progress.get("pending_remedial"),
            "streaks": rs.get_streaks(progress),
            "next": {
                "n": nxt,
                "day": day,
                "block": block,
                "session_id": rs.session_id(day, block),
                "track": track,
                "title": entry.get("title", ""),
                "objectives": entry.get("objectives", [])[:5],
                "phase": rs.week_phase_for(syllabus, day),
            },
        })
    except Exception as e:  # noqa: BLE001
        return _err(e)


def track_mastery() -> str:
    """Per-track mastery from completed sessions."""
    try:
        rs = _ensure()
        syllabus = rs.load_syllabus()
        progress = rs.load_progress()
        sessions = progress.get("sessions", {})
        track_names = syllabus.get("track_names", {})
        out = {}
        for t, name in track_names.items():
            ms = [s.get("mastery_score") for s in sessions.values()
                  if s.get("track") == t and s.get("mastery_score") is not None]
            es = [s.get("exercise_score") for s in sessions.values()
                  if s.get("track") == t and s.get("exercise_score") is not None]
            out[t] = {
                "name": name,
                "completed": len([s for s in sessions.values() if s.get("track") == t]),
                "avg_mastery": round(sum(ms) / len(ms), 3) if ms else None,
                "avg_exercise": round(sum(es) / len(es), 3) if es else None,
            }
        return json.dumps({"ok": True, "tracks": out,
                           "mastery_bar": 0.80, "exercise_bar": 0.70})
    except Exception as e:  # noqa: BLE001
        return _err(e)


def lessons() -> str:
    """List synthesized lessons (original LEVI-authored synthesis)."""
    try:
        rs = _ensure()
        d = Path(rs.data_dir()) / "lessons"
        items = []
        if d.exists():
            for f in sorted(d.glob("*.md")):
                title = f.stem
                try:
                    first = f.read_text(encoding="utf-8").splitlines()[0]
                    if first.startswith("# "):
                        title = first[2:].strip()
                except OSError:
                    pass
                items.append({"id": f.stem, "title": title})
        return json.dumps({"ok": True, "count": len(items), "lessons": items,
                           "note": "lessons are synthesized original — LEVI-authored, never copied"})
    except Exception as e:  # noqa: BLE001
        return _err(e)


def lesson_detail(sid: str) -> str:
    """Full markdown of one synthesized lesson."""
    try:
        rs = _ensure()
        f = Path(rs.data_dir()) / "lessons" / f"{sid}.md"
        if not f.exists():
            return json.dumps({"ok": False, "error": f"no lesson {sid}"})
        text = f.read_text(encoding="utf-8")
        # Cap for the phone; the file stays whole on disk.
        return json.dumps({"ok": True, "id": sid,
                           "truncated": len(text) > 60000,
                           "markdown": text[:60000]})
    except Exception as e:  # noqa: BLE001
        return _err(e)


def crucible() -> str:
    """The path to session 120 — the graduation crucible."""
    try:
        rs = _ensure()
        syllabus = rs.load_syllabus()
        progress = rs.load_progress()
        sessions = progress.get("sessions", {})
        total = syllabus.get("sessions_total", 120)
        done = set(progress.get("completed", []))
        remaining = total - len(done)
        # Weakest track by average mastery.
        by_track: dict[str, list[float]] = {}
        for s in sessions.values():
            t = s.get("track")
            m = s.get("mastery_score")
            if t and m is not None:
                by_track.setdefault(t, []).append(m)
        weakest = None
        if by_track:
            weakest = min(by_track, key=lambda t: sum(by_track[t]) / len(by_track[t]))
        track_names = syllabus.get("track_names", {})
        return json.dumps({
            "ok": True,
            "remaining": remaining,
            "graduated": bool(progress.get("graduated")),
            "weakest_track": {"id": weakest, "name": track_names.get(weakest)} if weakest else None,
            "crucible": ("session 120 samples ALL prior concepts, weakest first; "
                         "grades A/B/C separately; names the weakest area as the "
                         "post-graduation drill focus"),
            "guarantee": "all lessons synthesized original — LEVI-authored, never copied",
        })
    except Exception as e:  # noqa: BLE001
        return _err(e)


def run_session(budget_minutes: float = 20.0) -> str:
    """Run one boot-camp session through the battle rhythm.

    Remediation first (a failed gate never advances); otherwise the next
    uncompleted syllabus session. Time-bounded; aborts cleanly on budget.
    Honest about research: on-device has no network, so TEACH synthesizes
    from local knowledge and says so in the journal.
    """
    try:
        rs = _ensure()
        progress = rs.load_progress()
        pending = progress.get("pending_remedial")
        if pending:
            result = rs.run_remedial(pending, budget_minutes=budget_minutes)
            result["kind"] = "remedial"
        else:
            nxt = rs.next_uncompleted(progress)
            day, block = rs.n_to_day_block(nxt)
            result = rs.run_one_session(day, block, budget_minutes=budget_minutes)
            result["kind"] = "session"
        # Slim the payload for the phone; the journal keeps everything.
        slim = {k: result.get(k) for k in (
            "kind", "session_id", "day", "block", "track", "title",
            "mastery_score", "exercise_score", "gate", "passed",
            "remediation", "journal_note", "budget_exhausted", "error")}
        slim["ok"] = True
        return json.dumps(slim, default=str)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}",
                           "trace": traceback.format_exc()[-2000:]})


# ---------------------------------------------------------------------------
# Multimodal training generator (Chauncey ruling 2026-09-27)
#
# Pattern grounded on generator-hq3-mm (generate_levi_hq3_mm.py):
# every record carries "modality": "text" | "photo" | "video".
#   - PHOTO prompts produce generation SPECS — subject, composition,
#     lighting, style, mood: a model-ready description. NOT rendered media.
#   - VIDEO prompts produce shot-list SPECS — timed shots, caption, audio:
#     a script. NOT a rendered video.
# The honest boundary is kept visible everywhere: the UI labels these
# "spec" / "shot-list", never claims pixels or footage.
#
# Video learning -> training pipeline (settled 2026-09-24): refined video
# analyses feed the training corpus as TEXT entries, labeled heuristics,
# never trained as ground truth.
#
# NOT included (separate open item): the MiMo-V2.6 "luxury" pass
# (response diversity, teacher labels).
# ---------------------------------------------------------------------------

PHOTO_SUBJECTS = [
    "a boot-camp training session in progress",
    "the graduation crucible board",
    "a defender's desk with notes and a journal",
    "the mastery-gate scorecard",
    "spaced-repetition flashcards fanned out",
    "a remediation plan pinned to a wall",
    "the four training tracks as a wall chart",
    "a debrief journal open on a desk",
    "the drill floor before a session",
    "hands on a keyboard mid-exercise",
]

PHOTO_COMPOSITIONS = [
    "rule-of-thirds framing with the subject left of center",
    "centered hero framing with clean negative space",
    "close-up crop filling the frame",
    "wide shot with layered depth",
    "overhead flat-lay arrangement",
    "low angle looking up at the subject",
]

PHOTO_LIGHTING = [
    "soft window light from the left",
    "warm practical fluorescents overhead",
    "golden-hour side light",
    "single hard key light with deep shadows",
    "even diffused daylight",
    "practical lamp glow in a dark room",
]

PHOTO_STYLES = [
    "candid documentary photo",
    "clean instructional photography",
    "gritty phone-camera realism",
    "warm editorial style",
    "minimal catalog shot",
    "raw behind-the-scenes still",
]

PHOTO_MOODS = [
    "focused and industrious",
    "quiet pride of ownership",
    "early-morning determination",
    "scrappy resourcefulness",
    "calm local-first confidence",
    "the grind made visible",
]

VIDEO_SUBJECTS = [
    "the battle rhythm explained",
    "a mastery gate in sixty seconds",
    "spaced repetition, visualized",
    "the road to session 120",
    "what a remediation looks like",
    "the four tracks at a glance",
    "debrief: the honest journal",
    "a drill floor walkthrough",
]

VIDEO_SHOTS = [
    "hands opening the training journal",
    "close-up of the scorecard",
    "wide view of the drill floor",
    "over-the-shoulder view of the lesson",
    "slow pan across the track chart",
    "detail of the remediation plan",
    "the crucible board lighting up",
    "tapping the mastery bar on a phone",
]

VIDEO_CAPTIONS = [
    "The standard does not move.",
    "Brief, teach, review, drill, test, debrief.",
    "Eighty percent or no advance.",
    "Rung by rung to one-twenty.",
    "Synthesized original. Never copied.",
]

VIDEO_AUDIO = [
    "ambient room tone, no music",
    "quiet paper rustle under narration",
    "low synth pulse, minimal",
    "natural sound only",
    "soft metronome bed",
]


def modalities() -> str:
    """The three selectable training modalities."""
    try:
        _ensure()
        return json.dumps({"ok": True, "modalities": [
            {"id": "text", "name": "Text training",
             "desc": "Boot-camp sessions: BRIEF→TEACH→REVIEW→DRILL→TEST→DEBRIEF. Lessons synthesized original."},
            {"id": "photo", "name": "Photo training",
             "desc": "Photo generation SPECS — subject, composition, lighting, style, mood. Model-ready descriptions, NOT rendered images."},
            {"id": "video", "name": "Video training",
             "desc": "Video shot-list SPECS — timed shots, caption, audio. Scripts, NOT rendered footage."},
        ]})
    except Exception as e:  # noqa: BLE001
        return _err(e)


def photo_subjects() -> str:
    try:
        _ensure()
        return json.dumps({"ok": True, "subjects": PHOTO_SUBJECTS})
    except Exception as e:  # noqa: BLE001
        return _err(e)


def video_subjects() -> str:
    try:
        _ensure()
        return json.dumps({"ok": True, "subjects": VIDEO_SUBJECTS})
    except Exception as e:  # noqa: BLE001
        return _err(e)


def _spec_idx() -> int:
    """Deterministic rotation counter persisted in the data dir."""
    rs = _ensure()
    f = Path(rs.data_dir()) / "mm_counter.json"
    try:
        n = int(json.loads(f.read_text(encoding="utf-8")).get("n", 0))
    except (OSError, ValueError, KeyError):
        n = 0
    f.write_text(json.dumps({"n": n + 1}), encoding="utf-8")
    return n


def photo_spec(subject: str) -> str:
    """Build a photo generation SPEC — not a rendered image.

    Five labeled fields an image model can execute directly, rotated by
    mixed-radix on a persistent counter so specs vary by construction.
    """
    try:
        idx = _spec_idx()
        n_c, n_l = len(PHOTO_COMPOSITIONS), len(PHOTO_LIGHTING)
        n_s, n_m = len(PHOTO_STYLES), len(PHOTO_MOODS)
        spec = {
            "ok": True,
            "modality": "photo",
            "kind": "spec",
            "subject": subject,
            "composition": PHOTO_COMPOSITIONS[idx % n_c],
            "lighting": PHOTO_LIGHTING[(idx // n_c) % n_l],
            "style": PHOTO_STYLES[(idx // (n_c * n_l)) % n_s],
            "mood": PHOTO_MOODS[(idx // (n_c * n_l * n_s)) % n_m],
            "honest": "SPEC ONLY — a model-ready description. No image is rendered.",
        }
        return json.dumps(spec)
    except Exception as e:  # noqa: BLE001
        return _err(e)


def video_shots(subject: str) -> str:
    """Build a video shot-list SPEC for a 10-second clip — not rendered video.

    Three timed shots, one caption line, one audio bed. Consecutive shots
    are offset so they differ.
    """
    try:
        idx = _spec_idx()
        n = len(VIDEO_SHOTS)
        spec = {
            "ok": True,
            "modality": "video",
            "kind": "shot-list",
            "subject": subject,
            "shots": [
                {"t": "0-3s", "shot": VIDEO_SHOTS[idx % n]},
                {"t": "3-7s", "shot": VIDEO_SHOTS[(idx + 3) % n]},
                {"t": "7-10s", "shot": VIDEO_SHOTS[(idx + 7) % n]},
            ],
            "caption": VIDEO_CAPTIONS[idx % len(VIDEO_CAPTIONS)],
            "audio": VIDEO_AUDIO[(idx // len(VIDEO_CAPTIONS)) % len(VIDEO_AUDIO)],
            "honest": "SHOT-LIST ONLY — a script. No video is rendered.",
        }
        return json.dumps(spec)
    except Exception as e:  # noqa: BLE001
        return _err(e)


def video_ingest(analysis_text: str, source: str = "manual") -> str:
    """Video learning -> training pipeline entry point (settled 2026-09-24).

    Stores a refined video ANALYSIS as a text corpus entry, labeled
    heuristics — never trained as ground truth. The entry lands in the
    app's data dir under video_ingest/ for later corpus folding.
    """
    try:
        rs = _ensure()
        d = Path(rs.data_dir()) / "video_ingest"
        d.mkdir(parents=True, exist_ok=True)
        import time as _time
        stamp = _time.strftime("%Y%m%dT%H%M%S", _time.gmtime())
        entry = {
            "modality": "video",
            "kind": "video_analysis",
            "source": source,
            "heuristics": True,
            "ground_truth": False,
            "ingested_at": stamp,
            "analysis": analysis_text[:20000],
        }
        f = d / f"video-analysis-{stamp}.json"
        f.write_text(json.dumps(entry, indent=1), encoding="utf-8")
        return json.dumps({"ok": True, "stored": f.name,
                           "label": "heuristics — never ground truth"})
    except Exception as e:  # noqa: BLE001
        return _err(e)


# ---------------------------------------------------------------------------
# Training-FOR corpora (Chauncey clarification 2026-09-27)
#
# BOTH directions are in scope:
#   1. Train FOR photo/video generation: this app produces TRAINING CORPORA
#      for generative models — prompt<->photo-spec pairs and
#      prompt<->shot-list pairs, with quality gates and provenance,
#      structured as real training data (paired examples, clean schema).
#   2. Video learning: LEVI learns FROM videos via video_ingest (above) —
#      refined analyses become text corpus entries, heuristics labeled,
#      never trained as ground truth.
#
# Honest boundary: this produces the TRAINING DATA and the learning-ingest
# path. Training actual photo/video diffusion models is GPU-heavy and is
# NOT in this build — nothing here implies otherwise.
# ---------------------------------------------------------------------------

_PAIR_SCHEMA = ("prompt", "response", "modality", "kind", "provenance", "quality")


def _provenance(modality: str, kind: str) -> dict:
    import time as _time
    return {
        "generator": "training-generator-android 0.1.0",
        "modality": modality,
        "kind": kind,
        "synthetic_original": True,
        "ground_truth": False,
        "ingested_at": _time.strftime("%Y%m%dT%H%M%SZ", _time.gmtime()),
    }


def _corpus_dir(modality: str) -> "Path":
    rs = _ensure()
    d = Path(rs.data_dir()) / "corpus" / modality
    d.mkdir(parents=True, exist_ok=True)
    return d


def _quality_gate_prompt(prompt: str) -> "tuple[bool, str]":
    if not prompt or not prompt.strip():
        return False, "empty prompt"
    if len(prompt.strip()) < 8:
        return False, "prompt too short"
    return True, "ok"


def _save_pair(modality: str, prompt: str, response: dict) -> dict:
    """Quality-gate, dedupe, provenance, save. Returns the stored pair."""
    ok, reason = _quality_gate_prompt(prompt)
    if not ok:
        return {"ok": False, "error": reason}
    for v in response.values():
        if isinstance(v, str) and not v.strip():
            return {"ok": False, "error": "empty response field"}
    d = _corpus_dir(modality)
    norm = " ".join(prompt.strip().lower().split())
    for f in d.glob("*.json"):
        try:
            if json.loads(f.read_text(encoding="utf-8")).get("prompt_norm") == norm:
                return {"ok": True, "duplicate": True, "note": "pair already in corpus"}
        except (OSError, ValueError):
            continue
    import time as _time
    stamp = _time.strftime("%Y%m%dT%H%M%S", _time.gmtime())
    pair = {
        "prompt": prompt.strip(),
        "prompt_norm": norm,
        "response": response,
        "modality": modality,
        "kind": response.get("kind", "spec"),
        "provenance": _provenance(modality, response.get("kind", "spec")),
        "quality": {"gate": "pass", "checks": ["prompt non-empty",
                                               "response fields non-empty",
                                               "exact-prompt dedupe"]},
    }
    f = d / f"pair-{stamp}.json"
    f.write_text(json.dumps(pair, indent=1), encoding="utf-8")
    pair.pop("prompt_norm", None)
    pair["saved"] = f.name
    return {"ok": True, "pair": pair}


def photo_pair(subject: str) -> str:
    """Paired training example FOR photo generation: prompt <-> photo spec."""
    try:
        idx = _spec_idx()
        n_c, n_l = len(PHOTO_COMPOSITIONS), len(PHOTO_LIGHTING)
        n_s, n_m = len(PHOTO_STYLES), len(PHOTO_MOODS)
        prompt = f"Generate a photo of {subject}."
        spec = {
            "kind": "spec",
            "subject": subject,
            "composition": PHOTO_COMPOSITIONS[idx % n_c],
            "lighting": PHOTO_LIGHTING[(idx // n_c) % n_l],
            "style": PHOTO_STYLES[(idx // (n_c * n_l)) % n_s],
            "mood": PHOTO_MOODS[(idx // (n_c * n_l * n_s)) % n_m],
            "honest": "SPEC ONLY — a model-ready description. No image is rendered.",
        }
        return json.dumps(_save_pair("photo", prompt, spec))
    except Exception as e:  # noqa: BLE001
        return _err(e)


def video_pair(subject: str) -> str:
    """Paired training example FOR video generation: prompt <-> shot-list."""
    try:
        idx = _spec_idx()
        n = len(VIDEO_SHOTS)
        prompt = f"Make a short video about {subject}."
        spec = {
            "kind": "shot-list",
            "subject": subject,
            "shots": [
                {"t": "0-3s", "shot": VIDEO_SHOTS[idx % n]},
                {"t": "3-7s", "shot": VIDEO_SHOTS[(idx + 3) % n]},
                {"t": "7-10s", "shot": VIDEO_SHOTS[(idx + 7) % n]},
            ],
            "caption": VIDEO_CAPTIONS[idx % len(VIDEO_CAPTIONS)],
            "audio": VIDEO_AUDIO[(idx // len(VIDEO_CAPTIONS)) % len(VIDEO_AUDIO)],
            "honest": "SHOT-LIST ONLY — a script. No video is rendered.",
        }
        return json.dumps(_save_pair("video", prompt, spec))
    except Exception as e:  # noqa: BLE001
        return _err(e)


def corpus_stats() -> str:
    """Training-corpus pair counts per modality."""
    try:
        return json.dumps({"ok": True, "corpus": {
            "photo": len(list(_corpus_dir("photo").glob("*.json"))),
            "video": len(list(_corpus_dir("video").glob("*.json"))),
        }})
    except Exception as e:  # noqa: BLE001
        return _err(e)


def corpus_export() -> str:
    """Export the full paired training corpus as one JSONL file."""
    try:
        rs = _ensure()
        out = Path(rs.data_dir()) / "corpus" / "training-corpus.jsonl"
        count = 0
        with out.open("w", encoding="utf-8") as fh:
            for modality in ("photo", "video"):
                for f in sorted(_corpus_dir(modality).glob("*.json")):
                    pair = json.loads(f.read_text(encoding="utf-8"))
                    pair.pop("prompt_norm", None)
                    fh.write(json.dumps(pair) + "\n")
                    count += 1
        return json.dumps({"ok": True, "file": str(out), "pairs": count})
    except Exception as e:  # noqa: BLE001
        return _err(e)
