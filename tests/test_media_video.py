"""Tests for levi.media.video — the fail-closed ffmpeg wrapper.

Needs a real ffmpeg on PATH; every op test is skipped with a clear
reason when it is absent. The fail-closed path is tested by
monkeypatching instead.
"""

import shutil
import subprocess

import pytest

from pathlib import Path

from levi.media import video as vmod

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


def _make_clip(path: Path, duration: float = 2.0, freq: int = 440,
               size: str = "320x240") -> Path:
    cmd = [
        shutil.which("ffmpeg"), "-y", "-v", "error",
        "-f", "lavfi", "-i", f"testsrc=duration={duration}:size={size}:rate=15",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(path),
    ]
    subprocess.run(cmd, check=True, timeout=120)
    return path


@pytest.fixture()
def clip_a(tmp_path):
    return _make_clip(tmp_path / "a.mp4", duration=3.0, freq=440)


@pytest.fixture()
def clip_b(tmp_path):
    return _make_clip(tmp_path / "b.mp4", duration=2.0, freq=880)


@pytest.fixture()
def still(tmp_path):
    from levi.media import local as _local

    img = _local.generate("video drill still", width=160, height=120, seed=5,
                          style="gradient", save_dir=tmp_path)
    return Path(img.path)


def _verify_receipt(r, op, inputs):
    assert r.op == op
    assert r.engine == "ffmpeg"
    assert r.inputs == [str(p) for p in inputs]
    assert len(r.input_hashes) == len(inputs)
    assert all(len(h) == 64 for h in r.input_hashes)
    assert Path(r.output).exists() and Path(r.output).stat().st_size > 0
    assert vmod._sha256(Path(r.output)) == r.output_hash
    assert r.duration_s >= 0


# -- fail-closed ---------------------------------------------------------------


def test_fail_closed_without_ffmpeg(monkeypatch):
    def _missing():
        raise vmod.FFmpegMissing("nope")

    monkeypatch.setattr(vmod, "check_ffmpeg", _missing)
    with pytest.raises(vmod.FFmpegMissing):
        vmod.check_ffmpeg()


def test_install_hint_names_installers():
    assert "apt install ffmpeg" in vmod.INSTALL_HINT
    assert "pkg install ffmpeg" in vmod.INSTALL_HINT


def test_op_fails_closed(monkeypatch, tmp_path):
    def _missing():
        raise vmod.FFmpegMissing(vmod.INSTALL_HINT)

    monkeypatch.setattr(vmod, "check_ffmpeg", _missing)
    with pytest.raises(vmod.FFmpegMissing) as e:
        vmod.trim("in.mp4", str(tmp_path / "o.mp4"))
    assert "ffmpeg" in str(e.value).lower()


# -- guards --------------------------------------------------------------------


@needs_ffmpeg
def test_missing_input_refused(tmp_path):
    with pytest.raises(vmod.VideoError):
        vmod.trim(str(tmp_path / "nope.mp4"), str(tmp_path / "o.mp4"))


@needs_ffmpeg
def test_refuses_to_overwrite_input(clip_a):
    with pytest.raises(vmod.VideoError):
        vmod.trim(str(clip_a), str(clip_a))


@needs_ffmpeg
def test_bad_params_rejected(clip_a, tmp_path):
    with pytest.raises(vmod.VideoError):
        vmod.trim(str(clip_a), str(tmp_path / "o.mp4"), start_s=-1)
    with pytest.raises(vmod.VideoError):
        vmod.trim(str(clip_a), str(tmp_path / "o.mp4"), duration_s=0)
    with pytest.raises(vmod.VideoError):
        vmod.trim(str(clip_a), str(tmp_path / "o.mp4"), start_s=2, end_s=1)
    with pytest.raises(vmod.VideoError):
        vmod.cut(str(clip_a), [], str(tmp_path / "o.mp4"))
    with pytest.raises(vmod.VideoError):
        vmod.concat([str(clip_a)], str(tmp_path / "o.mp4"))
    with pytest.raises(vmod.VideoError):
        vmod.crossfade(str(clip_a), str(clip_a), str(tmp_path / "o.mp4"),
                       duration_s=99)


# -- ops -------------------------------------------------------------------------


@needs_ffmpeg
def test_trim_receipt(clip_a, tmp_path):
    out = tmp_path / "t.mp4"
    r = vmod.trim(str(clip_a), str(out), start_s=0.5, duration_s=1.0)
    _verify_receipt(r, "trim", [clip_a])
    assert r.params["start_s"] == 0.5
    dur = vmod._probe_duration(out)
    assert abs(dur - 1.0) < 0.3


@needs_ffmpeg
def test_trim_fast(clip_a, tmp_path):
    out = tmp_path / "t.mp4"
    r = vmod.trim(str(clip_a), str(out), start_s=0, end_s=1.0, fast=True)
    assert r.params["fast"] is True
    assert vmod._probe_duration(out) > 0


@needs_ffmpeg
def test_cut(clip_a, tmp_path):
    out = tmp_path / "c.mp4"
    r = vmod.cut(str(clip_a), [(0, 1), (2, 3)], str(out))
    _verify_receipt(r, "cut", [clip_a])
    assert abs(vmod._probe_duration(out) - 2.0) < 0.4


@needs_ffmpeg
def test_concat(clip_a, clip_b, tmp_path):
    out = tmp_path / "j.mp4"
    r = vmod.concat([str(clip_a), str(clip_b)], str(out))
    _verify_receipt(r, "concat", [clip_a, clip_b])
    assert abs(vmod._probe_duration(out) - 5.0) < 0.5


@needs_ffmpeg
def test_concat_refuses_mixed_audio(clip_a, tmp_path):
    silent = tmp_path / "silent.mp4"
    subprocess.run(
        [shutil.which("ffmpeg"), "-y", "-v", "error", "-i", str(clip_a),
         "-an", "-c:v", "copy", str(silent)],
        check=True, timeout=120,
    )
    with pytest.raises(vmod.VideoError):
        vmod.concat([str(clip_a), str(silent)], str(tmp_path / "o.mp4"))


@needs_ffmpeg
def test_burn_captions(clip_a, tmp_path):
    srt = tmp_path / "c.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nhello world\n")
    out = tmp_path / "cap.mp4"
    r = vmod.burn_captions(str(clip_a), str(srt), str(out))
    _verify_receipt(r, "burn_captions", [clip_a, srt])


@needs_ffmpeg
def test_burn_captions_rejects_empty_srt(clip_a, tmp_path):
    srt = tmp_path / "e.srt"
    srt.write_text("")
    with pytest.raises(vmod.VideoError):
        vmod.burn_captions(str(clip_a), str(srt), str(tmp_path / "o.mp4"))


@needs_ffmpeg
def test_kenburns(still, tmp_path):
    out = tmp_path / "kb.mp4"
    r = vmod.kenburns(str(still), str(out), duration_s=2.0, width=320,
                      height=240, fps=15, direction="in")
    _verify_receipt(r, "kenburns", [still])
    assert abs(vmod._probe_duration(out) - 2.0) < 0.3


@needs_ffmpeg
def test_kenburns_bad_direction(still, tmp_path):
    with pytest.raises(vmod.VideoError):
        vmod.kenburns(str(still), str(tmp_path / "o.mp4"), direction="sideways")


@needs_ffmpeg
def test_crossfade(clip_a, clip_b, tmp_path):
    out = tmp_path / "x.mp4"
    r = vmod.crossfade(str(clip_a), str(clip_b), str(out), duration_s=0.5)
    _verify_receipt(r, "crossfade", [clip_a, clip_b])
    # 3 + 2 - 0.5 = 4.5
    assert abs(vmod._probe_duration(out) - 4.5) < 0.5


@needs_ffmpeg
def test_normalize_audio(clip_a, tmp_path):
    out = tmp_path / "n.mp4"
    r = vmod.normalize_audio(str(clip_a), str(out), target_i=-16.0)
    _verify_receipt(r, "normalize_audio", [clip_a])
    assert r.params["target_i"] == -16.0


@needs_ffmpeg
def test_duck(clip_a, clip_b, tmp_path):
    out = tmp_path / "d.mp4"
    r = vmod.duck(str(clip_a), str(clip_b), str(out))
    _verify_receipt(r, "duck", [clip_a, clip_b])


@needs_ffmpeg
def test_vertical(clip_a, tmp_path):
    out = tmp_path / "v.mp4"
    r = vmod.vertical(str(clip_a), str(out), width=360, height=640)
    _verify_receipt(r, "vertical", [clip_a])
    p = subprocess.run(
        [shutil.which("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(out)],
        capture_output=True, timeout=30,
    )
    assert p.stdout.decode().strip() == "360,640"


@needs_ffmpeg
def test_thumbnail(clip_a, tmp_path):
    out = tmp_path / "t.jpg"
    r = vmod.thumbnail(str(clip_a), str(out), at_s=1.0, width=160)
    _verify_receipt(r, "thumbnail", [clip_a])
    assert r.params["at_s"] == 1.0


@needs_ffmpeg
def test_thumbnail_past_end_refused(clip_a, tmp_path):
    with pytest.raises(vmod.VideoError):
        vmod.thumbnail(str(clip_a), str(tmp_path / "o.jpg"), at_s=999)


def test_receipt_format_fields(tmp_path):
    r = vmod.VideoReceipt(
        op="trim", inputs=["a.mp4"], input_hashes=["0" * 64],
        params={"start_s": 0}, output="b.mp4",
        output_hash="f" * 64, duration_s=1.5,
    )
    text = r.format()
    assert "op: trim" in text and "b.mp4" in text and "1.50s" in text
