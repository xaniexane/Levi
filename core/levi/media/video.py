"""ffmpeg video fx — a thin, fail-closed subprocess wrapper.

Every op shells out to the system ``ffmpeg`` (no Python bindings, no
bundled binaries). If ffmpeg is absent the module fails closed with a
clear install hint instead of pretending.

Every op returns a :class:`VideoReceipt`: input paths + sha256 hashes,
the op name, the exact params, and the output path + hash. Inputs are
never mutated — every op writes a new file.

Honest scope: these are mechanical transforms (trim, concat, caption
burn-in, Ken Burns, crossfade, loudness normalize, sidechain ducking,
9:16 reformat, thumbnail grab). Re-encoding is the default because it
is frame-accurate; ``fast=True`` on :func:`trim` uses stream copy and
cuts on keyframes — faster, less precise. Loudness normalize is a
single-pass ``loudnorm`` — good enough for social, not a mastering
chain.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

DEFAULT_DIR = Path.home() / ".levi" / "media" / "video"
_DEFAULT_TIMEOUT_S = 300

INSTALL_HINT = (
    "ffmpeg was not found on PATH. Install it first:\n"
    "  Debian/Ubuntu:  sudo apt install ffmpeg\n"
    "  Fedora:         sudo dnf install ffmpeg\n"
    "  macOS:          brew install ffmpeg\n"
    "  Termux:         pkg install ffmpeg\n"
    "Then re-run — this module fails closed until ffmpeg exists."
)


class FFmpegMissing(RuntimeError):
    """Raised when no ffmpeg binary is available. Fail-closed, with hint."""


class VideoError(RuntimeError):
    """Raised when an ffmpeg op fails. Carries the stderr tail."""


def check_ffmpeg() -> str:
    """Return the ffmpeg binary path, or raise FFmpegMissing with the hint."""
    path = shutil.which("ffmpeg")
    if not path:
        raise FFmpegMissing(INSTALL_HINT)
    return path


def _sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _require_file(path: str, label: str) -> Path:
    p = Path(path)
    if not p.is_file():
        raise VideoError(f"{label} not found: {path}")
    return p


def _check_out(src_paths: Sequence[Path], out: str) -> Path:
    dest = Path(out)
    for s in src_paths:
        if dest.resolve() == s.resolve():
            raise VideoError(f"refusing to overwrite input: {out}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    return dest


def _run(args: List[str], timeout_s: int = _DEFAULT_TIMEOUT_S) -> None:
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise VideoError(f"ffmpeg timed out after {timeout_s}s: {shlex.join(args)}") from e
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace")[-2000:]
        raise VideoError(
            f"ffmpeg failed (exit {proc.returncode}): {shlex.join(args)}\n{tail}"
        )


def _probe_video_attrs(path: Path) -> Dict[str, object]:
    """Width, height, fps, duration, stream counts for one file.

    ffprobe JSON first; `ffmpeg -i` stderr parse as fallback. fps may be
    None when the fallback cannot parse it — callers must handle that.
    """
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        proc = subprocess.run(
            [ffprobe, "-v", "error",
             "-show_entries", "stream=width,height,avg_frame_rate,codec_type",
             "-show_entries", "format=duration",
             "-of", "json", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        )
        if proc.returncode == 0:
            try:
                doc = json.loads(proc.stdout.decode())
            except (ValueError, UnicodeDecodeError):
                doc = None
            if doc:
                vstreams = [
                    s for s in doc.get("streams", [])
                    if s.get("codec_type") == "video"
                ]
                attrs: Dict[str, object] = {
                    "video_streams": len(vstreams),
                    "audio_streams": sum(
                        1 for s in doc.get("streams", [])
                        if s.get("codec_type") == "audio"
                    ),
                    "duration_s": None,
                    "width": None,
                    "height": None,
                    "fps": None,
                }
                try:
                    attrs["duration_s"] = float(
                        doc.get("format", {}).get("duration")
                    )
                except (TypeError, ValueError):
                    pass
                if vstreams:
                    v0 = vstreams[0]
                    attrs["width"] = v0.get("width")
                    attrs["height"] = v0.get("height")
                    rate = v0.get("avg_frame_rate") or ""
                    m = re.match(r"(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)", rate)
                    if m and float(m.group(2)) != 0:
                        attrs["fps"] = float(m.group(1)) / float(m.group(2))
                return attrs
    # fallback: parse `ffmpeg -i` stderr
    proc = subprocess.run(
        [check_ffmpeg(), "-hide_banner", "-i", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
    )
    err = proc.stderr.decode("utf-8", "replace")
    attrs = {
        "video_streams": len(re.findall(r"Stream #\d+:\d+.*Video:", err)),
        "audio_streams": len(re.findall(r"Stream #\d+:\d+.*Audio:", err)),
        "duration_s": None,
        "width": None,
        "height": None,
        "fps": None,
    }
    m = re.search(rb"Duration: (\d+):(\d+):([\d.]+)", proc.stderr)
    if m:
        attrs["duration_s"] = (
            int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        )
    m = re.search(r"Video:.*?, (\d+)x(\d+)", err)
    if m:
        attrs["width"], attrs["height"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+(?:\.\d+)?) fps", err)
    if m:
        attrs["fps"] = float(m.group(1))
    return attrs


def info(src: str) -> Dict[str, object]:
    """Public probe: duration, stream counts, width/height, fps for a file."""
    return _probe_video_attrs(_require_file(src, "src"))


def _probe_duration(path: Path) -> float:
    """Media duration in seconds. ffprobe first, `ffmpeg -i` parse as fallback."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        )
        if proc.returncode == 0:
            try:
                return float(proc.stdout.decode().strip())
            except ValueError:
                pass
    proc = subprocess.run(
        [check_ffmpeg(), "-hide_banner", "-i", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
    )
    m = re.search(rb"Duration: (\d+):(\d+):([\d.]+)", proc.stderr)
    if not m:
        raise VideoError(f"could not probe duration of {path}")
    h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mi * 60 + s


def _probe_streams(path: Path) -> Dict[str, int]:
    """Count of video/audio streams. ffprobe first, `ffmpeg -i` parse fallback."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "stream=codec_type",
             "-of", "csv=p=0", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        )
        if proc.returncode == 0:
            kinds = proc.stdout.decode().split()
            return {
                "video": kinds.count("video"),
                "audio": kinds.count("audio"),
            }
    proc = subprocess.run(
        [check_ffmpeg(), "-hide_banner", "-i", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
    )
    err = proc.stderr.decode("utf-8", "replace")
    return {
        "video": len(re.findall(r"Stream #\d+:\d+.*Video:", err)),
        "audio": len(re.findall(r"Stream #\d+:\d+.*Audio:", err)),
    }


@dataclass
class VideoReceipt:
    op: str
    inputs: List[str]
    input_hashes: List[str]
    params: Dict[str, object]
    output: str
    output_hash: str
    duration_s: float
    engine: str = "ffmpeg"

    def format(self) -> str:
        lines = [
            "=== LEVI video fx receipt ===",
            f"op: {self.op}  engine: {self.engine}",
            f"inputs: {', '.join(self.inputs)}",
            f"input hashes: {', '.join(h[:12] for h in self.input_hashes)}",
            f"params: {self.params}",
            f"output: {self.output}",
            f"output hash: {self.output_hash[:16]}",
            f"wall time: {self.duration_s:.2f}s",
        ]
        return "\n".join(lines)


def _receipt(
    op: str,
    srcs: Sequence[Path],
    params: Dict[str, object],
    dest: Path,
    started: float,
) -> VideoReceipt:
    return VideoReceipt(
        op=op,
        inputs=[str(s) for s in srcs],
        input_hashes=[_sha256(s) for s in srcs],
        params=params,
        output=str(dest),
        output_hash=_sha256(dest),
        duration_s=time.monotonic() - started,
    )


def _vcodec(args: List[str]) -> List[str]:
    return args + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"]


# ---------------------------------------------------------------------------
# ops
# ---------------------------------------------------------------------------


def trim(
    src: str,
    out: str,
    start_s: float = 0.0,
    duration_s: Optional[float] = None,
    end_s: Optional[float] = None,
    fast: bool = False,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> VideoReceipt:
    """Cut [start_s, start_s+duration_s|end_s] out of src.

    ``fast=True`` uses stream copy (cuts on keyframes); default re-encodes
    for frame accuracy.
    """
    ffmpeg = check_ffmpeg()
    s = _require_file(src, "src")
    dest = _check_out([s], out)
    if start_s < 0:
        raise VideoError(f"start_s must be >= 0, got {start_s}")
    if duration_s is not None and end_s is not None:
        raise VideoError("pass duration_s or end_s, not both")
    if duration_s is not None and duration_s <= 0:
        raise VideoError(f"duration_s must be > 0, got {duration_s}")
    if end_s is not None and end_s <= start_s:
        raise VideoError(f"end_s ({end_s}) must be > start_s ({start_s})")
    started = time.monotonic()
    seek = [ffmpeg, "-y", "-ss", str(start_s), "-i", str(s)]
    if duration_s is not None:
        seek += ["-t", str(duration_s)]
    elif end_s is not None:
        seek += ["-to", str(end_s - start_s)]
    if fast:
        args = seek + ["-c", "copy", str(dest)]
    else:
        args = _vcodec(seek) + [str(dest)]
    _run(args, timeout_s)
    return _receipt(
        "trim", [s], {"start_s": start_s, "duration_s": duration_s,
                      "end_s": end_s, "fast": fast}, dest, started,
    )


def cut(
    src: str,
    cuts: Sequence[Tuple[float, float]],
    out: str,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> VideoReceipt:
    """Keep only the [(start, end), ...] segments of src, concatenated."""
    ffmpeg = check_ffmpeg()
    s = _require_file(src, "src")
    dest = _check_out([s], out)
    cuts = list(cuts)
    if not cuts:
        raise VideoError("cuts must be non-empty")
    for i, (a, b) in enumerate(cuts):
        if not (0 <= a < b):
            raise VideoError(f"cut {i}: need 0 <= start < end, got ({a}, {b})")
    started = time.monotonic()
    args = [ffmpeg, "-y"]
    for a, b in cuts:
        args += ["-ss", str(a), "-t", str(b - a), "-i", str(s)]
    labels = "".join(f"[{i}:v][{i}:a]" for i in range(len(cuts)))
    args += [
        "-filter_complex",
        f"{labels}concat=n={len(cuts)}:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(dest),
    ]
    _run(args, timeout_s)
    return _receipt("cut", [s], {"cuts": [list(c) for c in cuts]}, dest, started)


def concat(
    sources: Sequence[str],
    out: str,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> VideoReceipt:
    """Join clips end to end. Re-encodes so mixed sources just work.

    All inputs must agree on audio presence (all have audio or none do);
    mixed inputs are refused rather than guessed at.
    """
    ffmpeg = check_ffmpeg()
    srcs = [_require_file(p, f"sources[{i}]") for i, p in enumerate(sources)]
    if len(srcs) < 2:
        raise VideoError("concat needs at least 2 sources")
    dest = _check_out(srcs, out)
    audio = [_probe_streams(p)["audio"] > 0 for p in srcs]
    if any(audio) and not all(audio):
        raise VideoError(
            "concat refuses mixed audio presence — normalize the inputs first"
        )
    has_audio = all(audio)
    started = time.monotonic()
    args = [ffmpeg, "-y"]
    for p in srcs:
        args += ["-i", str(p)]
    if has_audio:
        labels = "".join(f"[{i}:v][{i}:a]" for i in range(len(srcs)))
        filt = f"{labels}concat=n={len(srcs)}:v=1:a=1[v][a]"
        maps = ["-map", "[v]", "-map", "[a]"]
    else:
        labels = "".join(f"[{i}:v]" for i in range(len(srcs)))
        filt = f"{labels}concat=n={len(srcs)}:v=1:a=0[v]"
        maps = ["-map", "[v]"]
    args += ["-filter_complex", filt] + maps + [
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
    ]
    if has_audio:
        args += ["-c:a", "aac"]
    args.append(str(dest))
    _run(args, timeout_s)
    return _receipt("concat", srcs, {"n": len(srcs)}, dest, started)


def _escape_sub_path(path: str) -> str:
    return path.replace("\\", "\\\\").replace("'", r"\'").replace(":", r"\:")


def burn_captions(
    src: str,
    srt_path: str,
    out: str,
    font_size: int = 22,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> VideoReceipt:
    """Burn an .srt subtitle file into the video (libass)."""
    ffmpeg = check_ffmpeg()
    s = _require_file(src, "src")
    srt = _require_file(srt_path, "srt")
    if srt.stat().st_size == 0:
        raise VideoError("srt file is empty")
    if not 8 <= font_size <= 96:
        raise VideoError(f"font_size must be 8-96, got {font_size}")
    dest = _check_out([s, srt], out)
    started = time.monotonic()
    style = f"FontSize={font_size},PrimaryColour=&HFFFFFF&,OutlineColour=&H80000000&"
    args = _vcodec(
        [ffmpeg, "-y", "-i", str(s), "-vf",
         f"subtitles={_escape_sub_path(str(srt))}:force_style='{style}'"]
    ) + [str(dest)]
    _run(args, timeout_s)
    return _receipt(
        "burn_captions", [s, srt],
        {"srt": str(srt), "font_size": font_size}, dest, started,
    )


def _kenburns_filter(
    frames: int, width: int, height: int, fps: int,
    direction: str, pan: str,
) -> str:
    """Build the zoompan filter. The zoom step is derived from the total
    frame count so the final zoom level is fps-independent (⚡ upgrade:
    the old 0.0012/frame step made zoom speed depend on fps)."""
    step = 0.3 / max(1, frames)
    if direction == "in":
        z = f"min(pzoom+{step:.6f},1.3)"
    else:
        z = f"max(if(eq(on,1),1.3,pzoom)-{step:.6f},1.0)"
    x_expr = "iw/2-(iw/zoom/2)"
    y_expr = "ih/2-(ih/zoom/2)"
    if pan == "left":
        x_expr = f"(iw-iw/zoom)*on/{frames}"
    elif pan == "right":
        x_expr = f"(iw-iw/zoom)*(1-on/{frames})"
    elif pan == "up":
        y_expr = f"(ih-ih/zoom)*on/{frames}"
    elif pan == "down":
        y_expr = f"(ih-ih/zoom)*(1-on/{frames})"
    return (
        f"zoompan=z='{z}':x='{x_expr}':y='{y_expr}':"
        f"d={frames}:s={width}x{height}:fps={fps}"
    )


def kenburns(
    image: str,
    out: str,
    duration_s: float = 5.0,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
    direction: str = "in",
    pan: str = "none",
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> VideoReceipt:
    """Animate a still image: slow zoom (Ken Burns) with optional pan.

    ``direction``: "in" or "out". ``pan``: "none", "left", "right",
    "up", "down" — combined with the zoom.
    """
    ffmpeg = check_ffmpeg()
    img = _require_file(image, "image")
    dest = _check_out([img], out)
    if duration_s <= 0:
        raise VideoError(f"duration_s must be > 0, got {duration_s}")
    if width <= 0 or height <= 0:
        raise VideoError("width/height must be > 0")
    if not 1 <= fps <= 60:
        raise VideoError(f"fps must be 1-60, got {fps}")
    if direction not in ("in", "out"):
        raise VideoError(f"direction must be 'in' or 'out', got {direction!r}")
    if pan not in ("none", "left", "right", "up", "down"):
        raise VideoError(f"pan must be one of none/left/right/up/down, got {pan!r}")
    frames = int(duration_s * fps)
    filt = _kenburns_filter(frames, width, height, fps, direction, pan)
    started = time.monotonic()
    args = [
        ffmpeg, "-y", "-loop", "1", "-i", str(img),
        "-vf", filt, "-t", str(duration_s),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(dest),
    ]
    _run(args, timeout_s)
    return _receipt(
        "kenburns", [img],
        {"duration_s": duration_s, "width": width, "height": height,
         "fps": fps, "direction": direction, "pan": pan},
        dest, started,
    )


def crossfade(
    a: str,
    b: str,
    out: str,
    duration_s: float = 1.0,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> VideoReceipt:
    """Crossfade clip a into clip b (video fade + audio acrossfade)."""
    ffmpeg = check_ffmpeg()
    pa = _require_file(a, "a")
    pb = _require_file(b, "b")
    dest = _check_out([pa, pb], out)
    if duration_s <= 0:
        raise VideoError(f"duration_s must be > 0, got {duration_s}")
    dur_a = _probe_duration(pa)
    if duration_s >= dur_a:
        raise VideoError(
            f"crossfade duration ({duration_s}s) must be < first clip ({dur_a:.2f}s)"
        )
    # ⚡ upgrade: xfade fails deep inside ffmpeg on mismatched inputs.
    # Refuse early with a clear error instead.
    ia, ib = _probe_video_attrs(pa), _probe_video_attrs(pb)
    wa, ha, wb, hb = ia["width"], ia["height"], ib["width"], ib["height"]
    if wa and wb and (wa, ha) != (wb, hb):
        raise VideoError(
            f"crossfade needs matching resolution, got {wa}x{ha} vs {wb}x{hb} — "
            "reformat one input first (see vertical())"
        )
    fa, fb = ia["fps"], ib["fps"]
    if fa and fb and abs(fa - fb) > 0.01:
        raise VideoError(
            f"crossfade needs matching fps, got {fa:.2f} vs {fb:.2f}"
        )
    offset = dur_a - duration_s
    started = time.monotonic()
    filt = (
        f"[0:v][1:v]xfade=transition=fade:duration={duration_s}:offset={offset}[v]"
    )
    maps = ["-map", "[v]"]
    params: Dict[str, object] = {"duration_s": duration_s, "offset_s": round(offset, 3)}
    if _probe_streams(pa)["audio"] > 0 and _probe_streams(pb)["audio"] > 0:
        filt += f";[0:a][1:a]acrossfade=d={duration_s}[a]"
        maps += ["-map", "[a]"]
        params["audio"] = "acrossfade"
    else:
        params["audio"] = "video-only"
    args = [ffmpeg, "-y", "-i", str(pa), "-i", str(pb),
            "-filter_complex", filt] + maps + [
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(dest)]
    _run(args, timeout_s)
    return _receipt("crossfade", [pa, pb], params, dest, started)


def normalize_audio(
    src: str,
    out: str,
    target_i: float = -16.0,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> VideoReceipt:
    """Single-pass loudness normalize (EBU R128) toward target_i LUFS.

    Good enough for social clips; not a mastering chain — that needs the
    measured two-pass loudnorm.
    """
    ffmpeg = check_ffmpeg()
    s = _require_file(src, "src")
    dest = _check_out([s], out)
    if not -40.0 <= target_i <= 0.0:
        raise VideoError(f"target_i must be -40..0 LUFS, got {target_i}")
    started = time.monotonic()
    args = [
        ffmpeg, "-y", "-i", str(s),
        "-af", f"loudnorm=I={target_i}:TP=-1.5:LRA=11",
        "-c:v", "copy", "-c:a", "aac",
        str(dest),
    ]
    _run(args, timeout_s)
    return _receipt("normalize_audio", [s], {"target_i": target_i}, dest, started)


def _parse_loudnorm_json(stderr: str) -> Dict[str, float]:
    """Extract the measured loudnorm values from ffmpeg stderr.

    Newer ffmpeg prints the measurement as input_i/input_tp/input_lra/
    input_thresh + target_offset; older builds use measured_I/measured_TP/
    measured_LRA/measured_thresh/measured_offset. Both are accepted and
    normalized to the measured_* names.
    """
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start < 0 or end <= start:
        raise VideoError("loudnorm measurement produced no JSON block")
    try:
        doc = json.loads(stderr[start : end + 1])
    except ValueError as e:
        raise VideoError(f"could not parse loudnorm JSON: {e}") from e
    alias = {
        "measured_I": ("measured_I", "input_i"),
        "measured_TP": ("measured_TP", "input_tp"),
        "measured_LRA": ("measured_LRA", "input_lra"),
        "measured_thresh": ("measured_thresh", "input_thresh"),
        "measured_offset": ("measured_offset", "target_offset"),
    }
    measured: Dict[str, float] = {}
    missing = []
    for name, keys in alias.items():
        for k in keys:
            if k in doc:
                try:
                    measured[name] = float(doc[k])
                except (TypeError, ValueError):
                    continue
                break
        else:
            missing.append(name)
    if missing:
        raise VideoError(f"loudnorm JSON missing keys: {missing}")
    return measured


def normalize_audio_measured(
    src: str,
    out: str,
    target_i: float = -16.0,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> VideoReceipt:
    """Measured two-pass loudness normalize (EBU R128).

    ⚡ upgrade over :func:`normalize_audio`'s single pass: pass 1 measures
    the input's integrated loudness, pass 2 applies the measured values
    with ``linear=true``. This is the mastering-grade route — closer to a
    true broadcast chain than the single-pass convenience op.
    """
    ffmpeg = check_ffmpeg()
    s = _require_file(src, "src")
    dest = _check_out([s], out)
    if not -40.0 <= target_i <= 0.0:
        raise VideoError(f"target_i must be -40..0 LUFS, got {target_i}")
    if _probe_streams(s)["audio"] == 0:
        raise VideoError("normalize_audio_measured needs an audio stream")
    started = time.monotonic()
    # pass 1: measure
    try:
        proc = subprocess.run(
            [ffmpeg, "-y", "-i", str(s), "-af",
             f"loudnorm=I={target_i}:TP=-1.5:LRA=11:print_format=json",
             "-f", "null", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout_s, check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise VideoError(f"loudnorm measure pass timed out after {timeout_s}s") from e
    measured = _parse_loudnorm_json(proc.stderr.decode("utf-8", "replace"))
    # pass 2: apply
    # pass 2: apply. Note the filter's second-pass option is named
    # `offset`, not `measured_offset` (ffmpeg rejects the latter).
    filt = (
        f"loudnorm=I={target_i}:TP=-1.5:LRA=11"
        f":measured_I={measured['measured_I']}"
        f":measured_TP={measured['measured_TP']}"
        f":measured_LRA={measured['measured_LRA']}"
        f":measured_thresh={measured['measured_thresh']}"
        f":offset={measured['measured_offset']}"
        ":linear=true"
    )
    args = [
        ffmpeg, "-y", "-i", str(s),
        "-af", filt,
        "-c:v", "copy", "-c:a", "aac",
        str(dest),
    ]
    _run(args, timeout_s)
    return _receipt(
        "normalize_audio_measured", [s],
        {"target_i": target_i, "passes": 2,
         **{k: round(v, 2) for k, v in measured.items()}},
        dest, started,
    )


def duck(
    music: str,
    voice: str,
    out: str,
    threshold: float = 0.02,
    ratio: float = 8.0,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> VideoReceipt:
    """Duck the music bed under the voice track (sidechain compression).

    The voice keys a compressor on the music; the two are mixed back
    together. Video (if any) passes through from the music input.
    """
    ffmpeg = check_ffmpeg()
    pm = _require_file(music, "music")
    pv = _require_file(voice, "voice")
    dest = _check_out([pm, pv], out)
    if not 0.0 < threshold <= 1.0:
        raise VideoError(f"threshold must be 0-1, got {threshold}")
    if ratio < 1.0:
        raise VideoError(f"ratio must be >= 1, got {ratio}")
    if _probe_streams(pm)["audio"] == 0 or _probe_streams(pv)["audio"] == 0:
        raise VideoError("duck needs audio on both inputs")
    started = time.monotonic()
    filt = (
        "[0:a]asplit=2[am][ak];"
        f"[am][1:a]sidechaincompress=threshold={threshold}:ratio={ratio}:"
        "attack=20:release=400[ducked];"
        "[ducked][ak]amix=inputs=2:duration=first[a]"
    )
    args = [ffmpeg, "-y", "-i", str(pm), "-i", str(pv),
            "-filter_complex", filt, "-map", "[a]"]
    if _probe_streams(pm)["video"] > 0:
        args += ["-map", "0:v", "-c:v", "copy"]
    args += ["-c:a", "aac", "-shortest", str(dest)]
    _run(args, timeout_s)
    return _receipt(
        "duck", [pm, pv], {"threshold": threshold, "ratio": ratio}, dest, started
    )


def vertical(
    src: str,
    out: str,
    width: int = 1080,
    height: int = 1920,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> VideoReceipt:
    """Reformat to vertical (default 1080x1920 for TikTok/Reels/Shorts).

    Scales to cover the frame then center-crops — nothing is stretched,
    edges are cropped instead.
    """
    ffmpeg = check_ffmpeg()
    s = _require_file(src, "src")
    dest = _check_out([s], out)
    if width <= 0 or height <= 0:
        raise VideoError("width/height must be > 0")
    started = time.monotonic()
    filt = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
    )
    args = _vcodec([ffmpeg, "-y", "-i", str(s), "-vf", filt]) + [str(dest)]
    _run(args, timeout_s)
    return _receipt(
        "vertical", [s], {"width": width, "height": height, "filter": filt},
        dest, started,
    )


def thumbnail(
    src: str,
    out: str,
    at_s: float = 1.0,
    width: int = 640,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> VideoReceipt:
    """Grab a still frame as a thumbnail/poster image."""
    ffmpeg = check_ffmpeg()
    s = _require_file(src, "src")
    dest = _check_out([s], out)
    if at_s < 0:
        raise VideoError(f"at_s must be >= 0, got {at_s}")
    if width <= 0:
        raise VideoError("width must be > 0")
    dur = _probe_duration(s)
    if at_s > dur:
        raise VideoError(f"at_s ({at_s}s) is past the end ({dur:.2f}s)")
    started = time.monotonic()
    args = [
        ffmpeg, "-y", "-ss", str(at_s), "-i", str(s),
        "-frames:v", "1", "-vf", f"scale={width}:-1",
        str(dest),
    ]
    _run(args, timeout_s)
    return _receipt(
        "thumbnail", [s], {"at_s": at_s, "width": width}, dest, started
    )
