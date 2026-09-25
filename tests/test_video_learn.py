"""Hermetic tests for the video learning pipeline.

Law -> guard -> prove:
  law 1: no transcript without a real engine (never a fake transcript)
  law 2: every pack carries url/fetched_at/fetch_hash/metadata_engine,
         and fetch_hash == sha256 of the exact raw bytes fetched
  law 3: ingest accepts only refined packs Chauncey (a named refiner)
         actually produced, from a pack we really exported
  law 4: signal_notes are extractive heuristics and say so

No live network, no Drive traffic, no HOME writes — engines are forced
via monkeypatch, the Drive CLI via an injected fake runner, and all
writes go to tmp_path.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from levi.knowledge.video_learn import analyze, drive_sync, engines, ingest, search

URL = "https://www.youtube.com/watch?v=example123"

RAW_OEMBED = json.dumps(
    {"title": "How Gardens Grow", "author_name": "Green Thumb"}
).encode()
FIELDS_OEMBED = {
    "title": "How Gardens Grow",
    "description": None,
    "duration_s": None,
    "uploader": "Green Thumb",
    "upload_date": None,
    "tags": [],
    "chapters": [],
    "webpage_url": URL,
}

RAW_YTDLP = json.dumps({"title": "Deep Dive: Soil", "duration": 900}).encode()
FIELDS_YTDLP = {
    "title": "Deep Dive: Soil",
    "description": "Soil health matters for tomatoes and peppers in the garden.",
    "duration_s": 900,
    "uploader": "Green Thumb",
    "upload_date": "20240101",
    "tags": ["garden", "soil"],
    "chapters": [{"start": 0, "title": "intro"}],
    "webpage_url": URL,
}

NO_ENGINES = {
    "yt_dlp": {"available": False, "hint": "pip install yt-dlp"},
    "whisper": {"available": False, "hint": "pip install openai-whisper"},
    "vosk": {"available": False, "hint": "pip install vosk"},
    "oembed": {"available": True, "hint": None},
    "ffmpeg": {"available": True, "hint": None},
}


def _no_engines(monkeypatch):
    monkeypatch.setattr(analyze.engines, "detect", lambda: dict(NO_ENGINES))


# ------------------------------------------------------------- engines


def test_engines_detect_shape():
    d = engines.detect()
    for key in ("yt_dlp", "whisper", "vosk", "oembed", "ffmpeg"):
        assert key in d
        assert "available" in d[key] and "hint" in d[key]
    assert d["oembed"]["available"] is True
    # law 1 consistency: transcription_available is exactly the OR of the three
    assert engines.transcription_available() == bool(
        d["yt_dlp"]["available"] or d["whisper"]["available"] or d["vosk"]["available"]
    )


# ------------------------------------------------------------- analyze


def test_pack_provenance_laws(monkeypatch):
    _no_engines(monkeypatch)
    monkeypatch.setattr(analyze, "_fetch_metadata_oembed", lambda url: (FIELDS_OEMBED, RAW_OEMBED))
    pack = analyze.analyze_video(URL)
    # law 2: provenance on every pack
    assert pack["url"] == URL
    assert pack["fetched_at"]
    assert pack["metadata_engine"] == "oembed"
    assert pack["fetch_hash"] == hashlib.sha256(RAW_OEMBED).hexdigest()
    # law 1: no engine -> null transcript, blocked status, reason named
    assert pack["transcript"] is None
    assert pack["transcript_engine"] is None
    assert pack["transcript_status"] == "blocked"
    assert pack["blocked_reason"]
    # law 4: heuristic notes are labeled
    assert pack["signal_notes"]["provenance"] == "heuristic"
    # pack hash is deterministic over content
    body = {k: v for k, v in pack.items() if k != "pack_hash"}
    assert pack["pack_hash"] == analyze._pack_hash(body)


def test_no_transcript_when_captions_absent(monkeypatch):
    det = dict(NO_ENGINES)
    det["yt_dlp"] = {"available": True, "hint": None}
    monkeypatch.setattr(analyze.engines, "detect", lambda: dict(det))
    monkeypatch.setattr(analyze, "_fetch_metadata_yt_dlp", lambda url: (FIELDS_YTDLP, RAW_YTDLP))
    monkeypatch.setattr(analyze, "_fetch_captions_yt_dlp", lambda url, lang="en": (None, None))
    monkeypatch.setattr(analyze, "_fetch_transcript_whisper_vosk", lambda url: (None, None))
    pack = analyze.analyze_video(URL)
    assert pack["metadata_engine"] == "yt-dlp"
    assert pack["fetch_hash"] == hashlib.sha256(RAW_YTDLP).hexdigest()
    assert pack["transcript"] is None
    assert pack["transcript_status"] == "blocked"


def test_platform_captions_become_transcript(monkeypatch):
    det = dict(NO_ENGINES)
    det["yt_dlp"] = {"available": True, "hint": None}
    monkeypatch.setattr(analyze.engines, "detect", lambda: dict(det))
    monkeypatch.setattr(analyze, "_fetch_metadata_yt_dlp", lambda url: (FIELDS_YTDLP, RAW_YTDLP))
    monkeypatch.setattr(
        analyze, "_fetch_captions_yt_dlp", lambda url, lang="en": ("hello garden world", "en")
    )
    pack = analyze.analyze_video(URL)
    assert pack["transcript"] == "hello garden world"
    assert pack["transcript_engine"] == "platform-captions"
    assert pack["transcript_status"] == "ok"


def test_analyze_rejects_empty_url():
    with pytest.raises(analyze.AnalysisError):
        analyze.analyze_video("   ")


def test_vtt_parser_strips_cues_and_tags():
    vtt = (
        "WEBVTT\n\n00:00.000 --> 00:01.000\n<c>hello</c> garden\n\n"
        "1\n00:01.000 --> 00:02.000\nhello garden\n\n"
        "00:02.000 --> 00:03.000\nworld"
    )
    assert analyze._parse_vtt(vtt) == "hello garden world"


def test_signal_notes_duration_bands():
    assert analyze._signal_notes({"duration_s": 120, "description": ""})["duration_band"] == "short (<4m)"
    assert analyze._signal_notes({"duration_s": 900, "description": ""})["duration_band"] == "mid (4-20m)"
    assert analyze._signal_notes({"duration_s": 5000, "description": ""})["duration_band"] == "long (>20m)"
    assert analyze._signal_notes({"duration_s": None, "description": ""})["duration_band"] == "unknown"


# ---------------------------------------------------------- drive_sync


def _pack():
    return {
        "schema": analyze.SCHEMA,
        "url": URL,
        "pack_hash": "ab" * 32,
        "title": "How Gardens Grow",
    }


def _fake_drive():
    calls = []

    def runner(cmd):
        calls.append(cmd)
        if cmd[2] == "files" and cmd[3] == "list":
            return {"files": []}
        if cmd[2] == "files" and cmd[3] == "create":
            return {"id": "folder-1", "name": "Levi Video Learning"}
        if cmd[2] == "+upload":
            return {"id": "file-9"}
        raise AssertionError(f"unexpected drive call: {cmd}")

    return runner, calls


def test_export_pack_fake_drive(tmp_path, monkeypatch):
    runner, _calls = _fake_drive()
    monkeypatch.setattr(drive_sync, "EXPORTS_DIR", tmp_path / "exports")
    registry = tmp_path / "exports.jsonl"
    receipt = drive_sync.export_pack(_pack(), runner=runner, registry_file=registry)
    assert receipt["drive_file_id"] == "file-9"
    assert receipt["folder_id"] == "folder-1"
    assert receipt["pack_hash"] == "ab" * 32
    # registry line written (law 3's lookup table)
    line = json.loads(registry.read_text().strip())
    assert line["pack_hash"] == "ab" * 32
    assert line["drive_file_id"] == "file-9"
    assert line["url"] == URL
    # local copy of the pack written
    assert (tmp_path / "exports" / ("ab" * 32 + ".json")).exists()


def test_export_rejects_non_pack():
    with pytest.raises(drive_sync.DriveError):
        drive_sync.export_pack({"schema": "bogus"}, runner=_fake_drive()[0])


def test_ensure_folder_reuses_existing():
    def runner(cmd):
        if cmd[3] == "list":
            return {"files": [{"id": "existing-folder"}]}
        raise AssertionError("should not create")
    assert drive_sync.ensure_folder(runner=runner) == "existing-folder"


# -------------------------------------------------------------- ingest


def _registry_with(pack_hash: str, tmp_path: Path) -> Path:
    reg = tmp_path / "exports.jsonl"
    reg.write_text(json.dumps({"pack_hash": pack_hash, "url": URL}) + "\n")
    return reg


def _valid_refined(pack_hash: str) -> dict:
    return {
        "schema": ingest.REFINED_SCHEMA,
        "title": "How Gardens Grow",
        "refined_by": "Chauncey",
        "origin_pack_hash": pack_hash,
        "source_url": URL,
        "refined_summary": "Start seeds indoors; transplant after frost.",
        "key_points": ["indoor starts", "frost dates"],
        "tags": ["garden"],
    }


def test_ingest_rejects_unknown_origin(tmp_path):
    reg = _registry_with("zz" * 32, tmp_path)
    refined = _valid_refined("ab" * 32)
    with pytest.raises(ingest.IngestRejected, match="not in the export registry"):
        ingest.ingest_refined(refined, registry_file=reg, days_dir=tmp_path / "days")


def test_ingest_rejects_empty_refiner(tmp_path):
    reg = _registry_with("ab" * 32, tmp_path)
    refined = _valid_refined("ab" * 32)
    refined["refined_by"] = "   "
    with pytest.raises(ingest.IngestRejected, match="refined_by"):
        ingest.ingest_refined(refined, registry_file=reg, days_dir=tmp_path / "days")


def test_ingest_rejects_empty_content(tmp_path):
    reg = _registry_with("ab" * 32, tmp_path)
    refined = _valid_refined("ab" * 32)
    refined["refined_summary"] = ""
    refined["key_points"] = []
    with pytest.raises(ingest.IngestRejected, match="empty refined content"):
        ingest.ingest_refined(refined, registry_file=reg, days_dir=tmp_path / "days")


def test_ingest_rejects_wrong_schema(tmp_path):
    with pytest.raises(ingest.IngestRejected, match="wrong schema"):
        ingest.ingest_refined({"schema": "nope"}, registry_file=tmp_path / "r", days_dir=tmp_path / "d")


def test_ingest_roundtrip_and_dedupe(tmp_path):
    reg = _registry_with("ab" * 32, tmp_path)
    days = tmp_path / "days"
    first = ingest.ingest_refined(
        _valid_refined("ab" * 32), registry_file=reg, days_dir=days,
        today=date(2026, 9, 24),
    )
    assert first["status"] == "ingested"
    assert first["date"] == "2026-09-24"
    entry = json.loads((days / "2026-09-24.jsonl").read_text().strip())
    assert entry["title"] == "How Gardens Grow"
    assert entry["refined_by"] == "Chauncey"
    assert entry["origin_pack_hash"] == "ab" * 32
    assert entry["key_points"] == ["indoor starts", "frost dates"]
    # law 3: dedupe — same URL never ingested twice
    again = ingest.ingest_refined(
        _valid_refined("ab" * 32), registry_file=reg, days_dir=days,
        today=date(2026, 9, 24),
    )
    assert again["status"] == "duplicate"
    assert len((days / "2026-09-24.jsonl").read_text().strip().splitlines()) == 1


def test_parse_refined_markdown(tmp_path):
    md = tmp_path / "refined.md"
    md.write_text(
        "# How Gardens Grow\n"
        "refined_by: Chauncey\n"
        "origin_pack_hash: ab12\n"
        "source_url: https://example.com/v\n"
        "tags: garden, soil\n\n"
        "## Summary\n"
        "Start seeds indoors.\n\n"
        "## Key points\n"
        "- indoor starts\n"
        "- frost dates\n"
    )
    r = ingest.parse_refined(md)
    assert r["schema"] == ingest.REFINED_SCHEMA
    assert r["title"] == "How Gardens Grow"
    assert r["refined_by"] == "Chauncey"
    assert r["origin_pack_hash"] == "ab12"
    assert r["refined_summary"] == "Start seeds indoors."
    assert r["key_points"] == ["indoor starts", "frost dates"]
    assert r["tags"] == ["garden", "soil"]


def test_parse_refined_json(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps(_valid_refined("ab" * 32)))
    assert ingest.parse_refined(p)["refined_by"] == "Chauncey"


def test_parse_refined_rejects_titleless_markdown(tmp_path):
    p = tmp_path / "r.md"
    p.write_text("just some text\n")
    with pytest.raises(ingest.RefineParseError):
        ingest.parse_refined(p)


# -------------------------------------------------------------- search


def _seed_days(days: Path):
    days.mkdir(parents=True, exist_ok=True)
    recs = [
        {
            "date": "2026-09-24", "title": "How Gardens Grow",
            "refined_summary": "tomato seedlings and soil health",
            "key_points": ["indoor starts"], "tags": ["garden"],
            "source_url": "https://example.com/g", "url_hash": "h1",
            "refined_by": "Chauncey",
        },
        {
            "date": "2026-09-24", "title": "Engine Repair Basics",
            "refined_summary": "torque specs and gaskets",
            "key_points": [], "tags": ["mechanics"],
            "source_url": "https://example.com/e", "url_hash": "h2",
            "refined_by": "Chauncey",
        },
    ]
    with (days / "2026-09-24.jsonl").open("w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")


def test_search_ranks_title_match_first(tmp_path):
    days = tmp_path / "days"
    _seed_days(days)
    hits = search.search_video_learn("gardens", days_dir=days, today=date(2026, 9, 24))
    assert hits and hits[0]["title"] == "How Gardens Grow"
    assert hits[0]["source_url"] == "https://example.com/g"


def test_search_empty_query_and_empty_corpus(tmp_path):
    days = tmp_path / "days"
    _seed_days(days)
    assert search.search_video_learn("", days_dir=days) == []
    assert search.search_video_learn("zzz-no-match", days_dir=days) == []
    assert search.search_video_learn("gardens", days_dir=tmp_path / "nodays") == []


def test_search_tokenize_drops_stopwords():
    assert search.tokenize("the and AI") == ["ai"]
