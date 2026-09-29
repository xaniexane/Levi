"""YouTube-to-ringtone spec — the canonical rules for the flagship feature.

Chauncey's spec (2026-09-29): "create ringtone from videos being watched
on YouTube as an option". The phone-side work (stream extraction, trim,
MediaStore export) lives in the Android app (RingtoneMaker.java /
RingtoneActivity.java). This module is the single source of truth for the
rules both sides obey — the Java side calls these functions through
Chaquopy so the law is declared once, in plain Python.

LAWS
----
L1  WRITE BOUNDARY. Exported audio may land in exactly two places: the
    app's private cache dir (intermediate files) and the MediaStore
    ``Ringtones`` collection (final ringtone). ``allowed_write_path()``
    is the guard — anything else is refused.
L2  TRIM BOUNDS. For an audio track of ``duration_ms``:
    0 <= start_ms < end_ms <= duration_ms and
    end_ms - start_ms <= MAX_RINGTONE_MS (45s). Out-of-range input is
    *clamped* to the legal range; a clamp that collapses the range
    (start >= end after clamping) is an error, never a silent zero file.
L3  NETWORK CONSENT. Nothing here touches the network. Extraction and
    download happen on the phone only after the user taps "Get audio".
    This module never fetches, never streams, never phones home.
L4  URL GATE. Only youtube.com, www.youtube.com, m.youtube.com,
    music.youtube.com and youtu.be are accepted. The video id must match
    ^[A-Za-z0-9_-]{11}$. Anything else is rejected, never guessed at.
L5  NO FAKES. Unknown or zero duration is refused — we never trim or
    export audio we cannot measure. Failures return structured errors,
    never silent no-ops, never invented audio.
L6  RECEIPT. Every export emits a JSON receipt: video id, title, trim
    bounds, output uri, timestamp. Receipts are the audit trail.
L7  AUTO TRIM. The DJ's auto-pick obeys L2 (it goes through
    ``validate_trim``), is deterministic for the same input (ties break
    to the earliest segment), and never exports on its own — the user
    always previews and confirms or adjusts first.
L8  EQUALIZER + FADES. EQ is 5 fixed bands (60/230/910/3600/14000 Hz),
    each gain clamped to [-15, +15] dB; presets are fixed honest curves,
    documented below — no magic "enhance" button. Fade-in/out durations
    are non-negative and always fit inside the trimmed segment (scaled
    down proportionally if they don't). Processing order is fixed:
    decode → EQ → fade-in → fade-out → encode. The phone bakes both
    into the exported file; what you preview is the trim, what you save
    is trim + EQ + fades.

The GUARD is ``validate_trim`` / ``parse_video_id`` / ``allowed_write_path``
/ ``auto_trim`` / ``validate_eq`` / ``validate_fade``.
The PROOF is tests/test_buzztunes_ringtone.py (unit + randomized property
checks over the laws).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

# Law L2: ringtones stay short. 45 seconds max.
MAX_RINGTONE_MS = 45_000
# Law L2: a ringtone shorter than this is a mistake, not a ringtone.
MIN_RINGTONE_MS = 1_000
# Law L7: auto-trim defaults — the DJ's pick aims for a 30s hook/drop.
AUTO_TRIM_MS = 30_000
AUTO_WINDOW_MS = 500
# Law L8: the equalizer's 5 fixed bands (Hz) and gain limits (dB).
EQ_BAND_HZ = (60, 230, 910, 3600, 14000)
EQ_MIN_DB = -15.0
EQ_MAX_DB = 15.0
# Law L8: presets are fixed honest curves — documented, no magic.
EQ_PRESETS = {
    "flat": (0.0, 0.0, 0.0, 0.0, 0.0),
    "bass_boost": (6.0, 4.0, 0.0, 0.0, 0.0),
    "treble_boost": (0.0, 0.0, 0.0, 4.0, 6.0),
    "vocal": (-2.0, 0.0, 3.0, 4.0, 2.0),
    "dance": (5.0, 3.0, 0.0, 2.0, 4.0),
}

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Law L4: the only hosts we ever accept.
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


class RingtoneError(ValueError):
    """Structured refusal — the guard saying no, in plain speech."""


def parse_video_id(url: str) -> str:
    """Extract the 11-char video id from a YouTube URL. Law L4.

    Accepts watch?v=, youtu.be/<id>, /shorts/<id>, /embed/<id>, /v/<id>.
    Raises RingtoneError for anything that is not a YouTube video URL.
    """
    if not url or not isinstance(url, str):
        raise RingtoneError("give me a YouTube link first")
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        parts = urlparse(url)
    except Exception:
        raise RingtoneError(f"that link doesn't parse: {url!r}")
    host = (parts.hostname or "").lower()
    if host not in YOUTUBE_HOSTS:
        raise RingtoneError(
            f"not a YouTube link (host {host or 'missing'}); "
            "paste a youtube.com or youtu.be link"
        )
    vid: Optional[str] = None
    path = parts.path or ""
    if host in ("youtu.be", "www.youtu.be"):
        seg = path.strip("/").split("/")
        vid = seg[0] if seg and seg[0] else None
    else:
        qs = parse_qs(parts.query)
        v = qs.get("v")
        if v:
            vid = v[0]
        else:
            m = re.match(r"^/(shorts|embed|v|live)/([^/?#]+)", path)
            if m:
                vid = m.group(2)
    if not vid or not _VIDEO_ID_RE.match(vid):
        raise RingtoneError(
            "couldn't find a video id in that link — "
            "use a normal youtube.com/watch?v=... or youtu.be/... link"
        )
    return vid


def validate_trim(
    start_ms: int, end_ms: int, duration_ms: int
) -> Tuple[int, int]:
    """Clamp a trim request into the legal range. Law L2.

    Returns (start_ms, end_ms) with
        0 <= start < end <= duration and end - start <= MAX_RINGTONE_MS.
    Raises RingtoneError when the request cannot be made legal
    (unknown/zero duration, or the clamp collapses the range).
    """
    for name, val in (("start_ms", start_ms), ("end_ms", end_ms),
                      ("duration_ms", duration_ms)):
        if not isinstance(val, int) or isinstance(val, bool):
            raise RingtoneError(f"{name} must be a whole number of ms")
    # Law L5: never trim audio we cannot measure.
    if duration_ms <= 0:
        raise RingtoneError(
            "audio length unknown — can't trim what we can't measure"
        )
    start = max(0, min(start_ms, duration_ms))
    end = max(0, min(end_ms, duration_ms))
    # Law L2: cap the ringtone length, keeping the start anchored.
    if end - start > MAX_RINGTONE_MS:
        end = start + MAX_RINGTONE_MS
    if start >= end:
        raise RingtoneError(
            f"trim {start_ms}-{end_ms}ms collapses inside a "
            f"{duration_ms}ms track — pick a start before the end"
        )
    if end - start < MIN_RINGTONE_MS:
        raise RingtoneError(
            f"trim is only {end - start}ms — ringtones need at least "
            f"{MIN_RINGTONE_MS}ms to be worth keeping"
        )
    return start, end


def default_trim(duration_ms: int) -> Tuple[int, int]:
    """Whole-track trim, capped at MAX_RINGTONE_MS. Law L2."""
    return validate_trim(0, MAX_RINGTONE_MS, duration_ms)


def auto_trim(
    duration_ms: int,
    energies: List[float],
    window_ms: int = AUTO_WINDOW_MS,
    target_ms: int = AUTO_TRIM_MS,
) -> Tuple[int, int]:
    """The DJ's pick: the most energetic ``target_ms`` run. Law L7.

    ``energies`` is one non-negative RMS value per ``window_ms`` of audio
    (measured on the phone by decoding the track — see
    RingtoneMaker.analyzeEnergy). The winning run is the contiguous
    ``target_ms`` stretch with the highest total energy — the hook, the
    drop, the loudest chorus. Ties break to the earliest run, so the
    pick is deterministic for the same input.

    The result always goes through ``validate_trim`` (Law L2): short
    tracks yield a shorter pick, never an error, never a fake.
    Raises RingtoneError for empty/garbage energy data (Law L5).
    """
    if not isinstance(duration_ms, int) or isinstance(duration_ms, bool):
        raise RingtoneError("duration_ms must be a whole number of ms")
    if duration_ms <= 0:
        raise RingtoneError(
            "audio length unknown — the DJ can't pick from silence (L5)")
    if not energies:
        raise RingtoneError("no energy data — can't auto-trim blind (L5)")
    for i, e in enumerate(energies):
        if not isinstance(e, (int, float)) or isinstance(e, bool) or e < 0:
            raise RingtoneError(
                f"energy window {i} is garbage ({e!r}) — refusing (L5)")
    if not isinstance(window_ms, int) or window_ms <= 0:
        raise RingtoneError("window_ms must be a positive whole number")
    if not isinstance(target_ms, int) or target_ms <= 0:
        raise RingtoneError("target_ms must be a positive whole number")

    n = len(energies)
    # Whole track is shorter than the target: the pick is the whole track.
    if n * window_ms <= target_ms:
        return validate_trim(0, n * window_ms, duration_ms)

    run_windows = max(1, target_ms // window_ms)
    best_start = 0
    best_energy = -1.0
    # Sliding-window sum over the energy envelope; earliest wins ties.
    window_sum = sum(energies[:run_windows])
    best_energy = window_sum
    for start in range(1, n - run_windows + 1):
        window_sum += energies[start + run_windows - 1] - energies[start - 1]
        if window_sum > best_energy:
            best_energy = window_sum
            best_start = start
    start_ms = best_start * window_ms
    return validate_trim(start_ms, start_ms + target_ms, duration_ms)


def validate_eq(bands) -> Tuple[float, ...]:
    """Validate 5 EQ band gains in dB. Law L8.

    Returns a tuple of 5 floats, each within [EQ_MIN_DB, EQ_MAX_DB].
    Accepts a preset name ("bass_boost") or an explicit 5-tuple/list.
    Raises RingtoneError for anything else.
    """
    if isinstance(bands, str):
        preset = EQ_PRESETS.get(bands.strip().lower().replace(" ", "_"))
        if preset is None:
            raise RingtoneError(
                f"unknown EQ preset {bands!r} — pick from: "
                + ", ".join(sorted(EQ_PRESETS)))
        return preset
    try:
        gains = tuple(float(g) for g in bands)
    except (TypeError, ValueError):
        raise RingtoneError(
            "EQ needs 5 band gains in dB (or a preset name)")
    if len(gains) != len(EQ_BAND_HZ):
        raise RingtoneError(
            f"EQ needs exactly {len(EQ_BAND_HZ)} bands, got {len(gains)}")
    for i, g in enumerate(gains):
        if not (EQ_MIN_DB <= g <= EQ_MAX_DB):
            raise RingtoneError(
                f"EQ band {i} ({EQ_BAND_HZ[i]}Hz) gain {g}dB is outside "
                f"[{EQ_MIN_DB}, {EQ_MAX_DB}]dB")
    return gains


def validate_fade(
    fade_in_ms: int, fade_out_ms: int, length_ms: int
) -> Tuple[int, int]:
    """Validate fade durations against the trimmed length. Law L8.

    Fades must be non-negative and fit inside the segment. If their sum
    exceeds the segment length they are scaled down proportionally (the
    documented behavior — a 30s fade on a 10s ringtone becomes 5s/5s,
    not an error, not a silent drop).
    """
    for name, val in (("fade_in_ms", fade_in_ms),
                      ("fade_out_ms", fade_out_ms),
                      ("length_ms", length_ms)):
        if not isinstance(val, int) or isinstance(val, bool):
            raise RingtoneError(f"{name} must be a whole number of ms")
    if fade_in_ms < 0 or fade_out_ms < 0:
        raise RingtoneError("fades can't be negative")
    if length_ms <= 0:
        raise RingtoneError("can't fade a zero-length segment")
    fi = min(fade_in_ms, length_ms)
    fo = min(fade_out_ms, length_ms)
    if fi + fo > length_ms and fi + fo > 0:
        scale = length_ms / (fi + fo)
        fi = int(fi * scale)
        fo = length_ms - fi  # keep the exact fit, no rounding drift
    return fi, fo


def ringtone_filename(video_id: str, title: str) -> str:
    """Safe filename for the exported ringtone. Law L1 (name, not path)."""
    safe = re.sub(r"[^A-Za-z0-9 _.-]", "", (title or "buzz-tunes").strip())
    safe = re.sub(r"\s+", " ", safe).strip()[:60] or "buzz-tunes"
    return f"{safe} [{video_id}].m4a"


def allowed_write_path(path: str, cache_dir: str) -> bool:
    """Law L1 guard: True only for app cache dir or the Ringtones
    MediaStore relative path. The Java side enforces this before any
    FileOutputStream / MediaStore insert."""
    if not path or not cache_dir:
        return False
    norm = path.replace("\\", "/")
    cache = cache_dir.rstrip("/").replace("\\", "/")
    if norm == cache or norm.startswith(cache + "/"):
        return True
    # MediaStore relative path used by the exporter:
    if norm in ("Ringtones", "Ringtones/") or norm.startswith("Ringtones/"):
        return True
    return False


def export_receipt(
    video_id: str,
    title: str,
    start_ms: int,
    end_ms: int,
    output_uri: str,
    duration_ms: int,
    eq_bands: Optional[Tuple[float, ...]] = None,
    fade_in_ms: int = 0,
    fade_out_ms: int = 0,
    auto_trimmed: bool = False,
) -> Dict:
    """Law L6: the audit trail for one ringtone export."""
    return {
        "kind": "ringtone_export",
        "video_id": video_id,
        "title": title,
        "trim_ms": {"start": start_ms, "end": end_ms},
        "length_ms": end_ms - start_ms,
        "duration_ms": duration_ms,
        "eq_db": list(eq_bands) if eq_bands is not None else [0.0] * 5,
        "fade_ms": {"in": fade_in_ms, "out": fade_out_ms},
        "auto_trimmed": auto_trimmed,
        "output_uri": output_uri,
        "exported_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def receipt_json(receipt: Dict) -> str:
    return json.dumps(receipt, indent=2, sort_keys=True)


@dataclass
class RingtonePlan:
    """Everything the phone needs, pre-validated. Built only through
    ``plan()`` so the laws run before any work starts."""

    video_id: str
    title: str
    start_ms: int
    end_ms: int
    duration_ms: int
    filename: str
    eq_bands: Tuple[float, ...] = EQ_PRESETS["flat"]
    fade_in_ms: int = 0
    fade_out_ms: int = 0

    @property
    def length_ms(self) -> int:
        return self.end_ms - self.start_ms

    @property
    def eq_preset_name(self) -> Optional[str]:
        for name, gains in EQ_PRESETS.items():
            if tuple(gains) == tuple(self.eq_bands):
                return name
        return None  # a custom curve, not a preset


def plan(
    url: str,
    title: str,
    start_ms: int,
    end_ms: int,
    duration_ms: int,
    eq: object = "flat",
    fade_in_ms: int = 0,
    fade_out_ms: int = 0,
) -> RingtonePlan:
    """Validate a full ringtone request up front. Laws L2, L4, L5, L8."""
    vid = parse_video_id(url)          # L4
    start, end = validate_trim(start_ms, end_ms, duration_ms)  # L2, L5
    bands = validate_eq(eq)            # L8
    fi, fo = validate_fade(fade_in_ms, fade_out_ms, end - start)  # L8
    return RingtonePlan(
        video_id=vid,
        title=title or "buzz-tunes",
        start_ms=start,
        end_ms=end,
        duration_ms=duration_ms,
        filename=ringtone_filename(vid, title),
        eq_bands=bands,
        fade_in_ms=fi,
        fade_out_ms=fo,
    )


def describe() -> Dict:
    """Plain-speech summary of the feature contract."""
    return {
        "feature": "YouTube-to-ringtone",
        "max_length_ms": MAX_RINGTONE_MS,
        "min_length_ms": MIN_RINGTONE_MS,
        "laws": [
            "L1 writes only to app cache + MediaStore Ringtones",
            "L2 trim always inside [0, duration], max 45s",
            "L3 no network until the user taps Get audio",
            "L4 only youtube.com / youtu.be links accepted",
            "L5 unknown duration refused, never faked",
            "L6 every export writes a receipt",
            "L7 auto-trim obeys L2, deterministic, user confirms",
            "L8 EQ 5 bands ±15dB + fades fit inside the segment",
        ],
        "eq_bands_hz": list(EQ_BAND_HZ),
        "eq_presets": sorted(EQ_PRESETS),
    }
