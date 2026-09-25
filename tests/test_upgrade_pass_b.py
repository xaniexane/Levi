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


# ---- B: video (⚡)


def test_kenburns_step_is_fps_independent():
    # B1: the old 0.0012/frame step made zoom speed fps-dependent.
    f15 = video._kenburns_filter(150, 1280, 720, 15, "in", "none")
    f30 = video._kenburns_filter(300, 1280, 720, 30, "in", "none")
    assert "pzoom+0.002000" in f15  # 0.3/150
    assert "pzoom+0.001000" in f30  # 0.3/300
    # both end at 1.3 after their frame counts: frames*step == 0.3
    assert 150 * 0.002000 == pytest.approx(0.3)
    assert 300 * 0.001000 == pytest.approx(0.3)


def test_kenburns_runs_with_new_filter(tmp_path):
    img = tmp_path / "still.png"
    local.generate("kb", seed=1, style="dark", save=False)
    from levi.media.local import encode_png, _render2
    img.write_bytes(encode_png(64, 36, _render2(64, 36, 1, "dark")))
    out = str(tmp_path / "kb.mp4")
    r = video.kenburns(str(img), out, duration_s=0.5, width=64,
                       height=36, fps=10)
    assert Path(out).exists() and r.op == "kenburns"


def test_loudnorm_json_parse():
    stderr = ('frame= 10\n{\n    "input_i" : "-23.45",\n'
              '    "measured_I" : "-23.45",\n'
              '    "measured_TP" : "-2.10",\n'
              '    "measured_LRA" : "7.50",\n'
              '    "measured_thresh" : "-34.20",\n'
              '    "measured_offset" : "7.45"\n}\n')
    m = video._parse_loudnorm_json(stderr)
    assert m == {"measured_I": -23.45, "measured_TP": -2.10,
                 "measured_LRA": 7.5, "measured_thresh": -34.2,
                 "measured_offset": 7.45}
    # new ffmpeg prints input_i/input_tp/... + target_offset instead
    stderr2 = ('{\n\t"input_i" : "-21.85",\n\t"input_tp" : "-17.72",\n'
               '\t"input_lra" : "0.00",\n\t"input_thresh" : "-31.85",\n'
               '\t"target_offset" : "0.01"\n}\n')
    m2 = video._parse_loudnorm_json(stderr2)
    assert m2 == {"measured_I": -21.85, "measured_TP": -17.72,
                  "measured_LRA": 0.0, "measured_thresh": -31.85,
                  "measured_offset": 0.01}
    with pytest.raises(video.VideoError):
        video._parse_loudnorm_json("no json here")


def _sine_clip(path, seconds=2):
    _ffmpeg("-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
            "-c:a", "aac", str(path))


def test_normalize_audio_measured_two_pass(tmp_path):
    # B2: the measured two-pass route — proves it is not the single pass.
    src = tmp_path / "src.m4a"
    _sine_clip(src)
    out = str(tmp_path / "norm.m4a")
    r = video.normalize_audio_measured(str(src), out)
    assert r.op == "normalize_audio_measured"
    assert r.params["passes"] == 2
    assert "measured_I" in r.params  # measured values recorded
    assert Path(out).exists()
    attrs = video.info(out)
    assert attrs["audio_streams"] >= 1


def test_info_probe(tmp_path):
    src = tmp_path / "src.m4a"
    _sine_clip(src)
    attrs = video.info(str(src))
    assert attrs["duration_s"] == pytest.approx(2.0, abs=0.3)
    assert attrs["audio_streams"] >= 1
    assert attrs["video_streams"] == 0


def _testsrc(path, w, h, seconds=1):
    _ffmpeg("-f", "lavfi", "-i",
            f"testsrc=size={w}x{h}:rate=10:duration={seconds}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path))


def test_crossfade_preflight_refuses_mismatch(tmp_path):
    # B4: xfade fails deep in ffmpeg on mismatched inputs — refuse early.
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    _testsrc(a, 64, 64)
    _testsrc(b, 128, 64)
    with pytest.raises(video.VideoError, match="resolution"):
        video.crossfade(str(a), str(b), str(tmp_path / "x.mp4"),
                        duration_s=0.3)


def test_crossfade_matching_still_works(tmp_path):
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    _testsrc(a, 64, 64)
    _testsrc(b, 64, 64)
    out = str(tmp_path / "x.mp4")
    r = video.crossfade(str(a), str(b), out, duration_s=0.3)
    assert Path(out).exists() and r.op == "crossfade"


