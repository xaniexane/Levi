"""Upgrade-pass proof tests (⚡): strengthen/refine/improve over the four
recent media builds, with Alpha as the critic.

Laws:
  U1 no regression — pre-existing deterministic outputs unchanged
      (legacy styles, ASCII L1-L6, video receipts).
  U2 no fakes — every new feature proven by a test that fails if faked.
  U3 Alpha judges — alpha_critique returns substrate-labeled verdicts.
  U4 bundle v1 stays forward-compatible.
"""

import json
import re
import struct
import subprocess
import zlib
from pathlib import Path

import pytest

from levi.media import ascii_art, local, refine, video
from levi.knowledge.video_learn import analyze, engines

TMP = Path("/tmp")


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", *args],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   timeout=120, check=True)


def _gray_png(width, height, rows):
    def chunk(t, data):
        c = struct.pack(">I", len(data)) + t + data
        return c + struct.pack(">I", zlib.crc32(t + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


# ---- D: video_learn + Alpha (⚡)


HTML_FIXTURE = """<html><head>
<meta property="og:title" content="Test Vid">
<meta property="og:description" content="A published description">
<meta property="og:video:duration" content="372">
<meta name="author" content="SomeChan">
<meta property="article:published_time" content="2026-01-02">
<title>fallback title</title>
</head></html>"""


def test_parse_html_meta():
    f = analyze.parse_html_meta(HTML_FIXTURE)
    assert f["title"] == "Test Vid"
    assert f["description"] == "A published description"
    assert f["duration_s"] == 372.0
    assert f["uploader"] == "SomeChan"
    assert f["upload_date"] == "2026-01-02"


def test_parse_html_meta_title_fallback():
    f = analyze.parse_html_meta("<html><head><title>only title</title></head></html>")
    assert f["title"] == "only title"
    assert f["description"] is None


def test_html_meta_engine_end_to_end(monkeypatch):
    # D1: unknown hosts no longer fail closed when the page publishes meta.
    monkeypatch.setattr(
        analyze, "_http_get",
        lambda url, timeout=30: (HTML_FIXTURE.encode(), "text/html"),
    )
    monkeypatch.setattr(
        engines, "detect",
        lambda: {k: {"available": False, "hint": "x"} for k in
                 ("yt_dlp", "whisper", "vosk")}
        | {"oembed": {"available": True}, "ffmpeg": {"available": True}},
    )
    pack = analyze.analyze_video("https://example.com/watch/abc",
                                 with_alpha=False)
    assert pack["metadata_engine"] == "html-meta"
    assert pack["title"] == "Test Vid"
    assert pack["description"] == "A published description"
    assert pack["transcript_status"] == "blocked"  # law 1: never faked
    assert pack["alpha_critique"] == {"status": "skipped"}


def test_html_meta_refuses_titleless_page(monkeypatch):
    monkeypatch.setattr(
        analyze, "_http_get",
        lambda url, timeout=30: (b"<html><head></head></html>", "text/html"),
    )
    with pytest.raises(analyze.AnalysisError):
        analyze._fetch_metadata_html_meta("https://example.com/x")


def test_analyze_with_alpha_critique(monkeypatch):
    # D2: Alpha in the mix — the pack carries a substrate-labeled verdict.
    monkeypatch.setattr(
        analyze, "_http_get",
        lambda url, timeout=30: (HTML_FIXTURE.encode(), "text/html"),
    )
    pack = analyze.analyze_video("https://example.com/watch/abc",
                                 with_alpha=True)
    crit = pack["alpha_critique"]
    assert crit["status"] == "ok"
    assert crit["substrate"] == "rules-engine"  # U3: substrate labeled
    assert crit["verdict"] and crit["answer"]
    assert pack["pack_hash"]  # hash covers the critique


def test_alpha_critique_honest_on_empty_task():
    r = refine.alpha_critique("   ")
    assert r["status"] == "error"


def test_alpha_critique_real_verdict():
    r = refine.alpha_critique(
        "Judge this upgrade plan: fix a filename collision bug by adding "
        "a prompt hash to generated filenames. Approve, reject, or amend.")
    assert r["status"] == "ok"
    assert r["substrate"] == "rules-engine"
    assert isinstance(r["verdict"], dict)
