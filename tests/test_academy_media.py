"""Tests for the academy M track: media_subjects catalog + media drills.

The catalog follows the D-track pattern (TRACK_KEY, as_track,
merge_into copying never mutating). The drills produce REAL artifacts
into a work dir — graded by verifying the files, never faked.
"""

import json
import shutil

import pytest

from pathlib import Path

from levi.academy import media_subjects as ms
from levi.academy import session_exercises as aex
from levi.media import video as vmod

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)

BLOOM_VERBS = (
    "generate", "verify", "evaluate", "justify", "design", "render",
    "distinguish", "select", "defend", "explain", "name", "write",
    "deconstruct", "build", "execute", "read", "choose", "diagnose",
    "state", "produce", "assemble", "critique", "reformat",
)


def _entry(exercise_type):
    sid, entry = next(
        (s, e) for s, e in ms.syllabus_entries() if e["exercise_type"] == exercise_type
    )
    return entry


# -- catalog -------------------------------------------------------------------


def test_track_identity():
    assert ms.TRACK_KEY == "M"
    assert ms.TRACK_NAME == "Media Production"
    assert len(ms.SUBJECTS) == 6


def test_three_objectives_three_questions():
    for s in ms.SUBJECTS:
        assert len(s["objectives"]) == 3, s["id"]
        assert len(s["key_questions"]) == 3, s["id"]


def test_objectives_use_measurable_verbs():
    for s in ms.SUBJECTS:
        for obj in s["objectives"]:
            first = obj.split()[0].lower()
            assert first in BLOOM_VERBS, f"{s['id']}: {obj!r}"


def test_exercise_types_registered():
    for s in ms.SUBJECTS:
        assert s["exercise_type"] in aex.EXERCISE_RUNNERS, s["id"]


def test_get_subject_and_ids():
    assert ms.get_subject("ffmpeg-fundamentals")["title"].startswith("FFmpeg")
    assert set(ms.subject_ids()) == {s["id"] for s in ms.SUBJECTS}
    with pytest.raises(KeyError):
        ms.get_subject("nope")


def test_as_track_shape():
    track = ms.as_track()
    assert track["name"] == "Media Production"
    assert set(track["days"]) == {"1", "2", "3", "4", "5", "6"}
    for day in track["days"].values():
        assert set(day) == {"title", "objectives", "key_questions", "exercise_type"}


def test_merge_into_copies_never_mutates():
    syllabus = {"tracks": {"A": {"name": "x", "days": {}}}, "track_names": {"A": "x"}}
    before = json.dumps(syllabus, sort_keys=True)
    merged = ms.merge_into(syllabus)
    assert json.dumps(syllabus, sort_keys=True) == before
    assert merged["tracks"]["M"]["name"] == "Media Production"
    assert merged["track_names"]["M"] == "Media Production"


def test_merge_into_refuses_duplicate_key():
    syllabus = {"tracks": {}, "track_names": {}}
    merged = ms.merge_into(syllabus)
    with pytest.raises(ValueError):
        ms.merge_into(merged)


# -- drills: real artifacts -------------------------------------------------------


def test_media_photo_produces_real_png(tmp_path):
    res = aex.run_exercise(
        "media-photo", _entry("media-photo"), "lesson", {}, work_dir=tmp_path
    )
    assert res["score"] == 1.0
    art = res["artifact"]
    p = Path(art["image"])
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert art["safe_zone"]["position"] == "bottom"


def test_media_backend_decision_file(tmp_path):
    res = aex.run_exercise(
        "media-backend", _entry("media-backend"), "lesson", {}, work_dir=tmp_path
    )
    assert res["score"] == 1.0
    data = json.loads(Path(res["artifact"]["decisions_file"]).read_text())
    assert [d["choice"] for d in data] == ["local", "pollinations", "sd"]


def test_media_prompt_template(tmp_path):
    res = aex.run_exercise(
        "media-prompt", _entry("media-prompt"), "lesson", {}, work_dir=tmp_path
    )
    assert res["score"] == 1.0
    assert "no real person" in res["artifact"]["rendered_prompt"]


@needs_ffmpeg
def test_media_video_produces_real_clip(tmp_path):
    res = aex.run_exercise(
        "media-video", _entry("media-video"), "lesson", {}, work_dir=tmp_path
    )
    assert res["score"] == 1.0, res
    art = res["artifact"]
    clip = Path(art["final_clip"])
    assert clip.stat().st_size > 0
    assert abs(art["duration_s"] - 1.0) < 0.3


@needs_ffmpeg
def test_media_vertical_real_916(tmp_path):
    res = aex.run_exercise(
        "media-vertical", _entry("media-vertical"), "lesson", {}, work_dir=tmp_path
    )
    assert res["score"] == 1.0, res
    assert res["artifact"]["dims"] == "360,640"
    assert Path(res["artifact"]["thumbnail"]).stat().st_size > 0


def test_media_thumbnail_pair(tmp_path):
    res = aex.run_exercise(
        "media-thumbnail", _entry("media-thumbnail"), "lesson", {}, work_dir=tmp_path
    )
    assert res["score"] == 1.0
    art = res["artifact"]
    assert Path(art["poster"]).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert art["seed_shared"] is True


def test_media_drills_block_honestly_without_ffmpeg(tmp_path, monkeypatch):
    def _missing():
        raise vmod.FFmpegMissing(vmod.INSTALL_HINT)

    monkeypatch.setattr(vmod, "check_ffmpeg", _missing)
    for etype in ("media-video", "media-vertical"):
        res = aex.run_exercise(etype, _entry(etype), "lesson", {}, work_dir=tmp_path)
        assert res["score"] == 0.0
        assert res["artifact"]["status"] == "blocked"
        assert "ffmpeg" in res["artifact"]["reason"].lower()


def test_unknown_media_type_still_rejected():
    with pytest.raises(ValueError):
        aex.run_exercise("media-nope", {}, "lesson", {})
