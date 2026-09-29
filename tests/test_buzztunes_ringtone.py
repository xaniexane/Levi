"""Proof for the YouTube-to-ringtone laws (core/levi/buzztunes/ringtone.py).

Unit tests pin the examples; property tests throw randomized inputs at
the guards and assert the laws hold on every draw:
  L2: trim output always satisfies 0 <= start < end <= duration and
      end - start <= MAX_RINGTONE_MS
  L4: the URL gate only ever returns an 11-char id from a YouTube host
  L1: allowed_write_path never admits a path outside cache/Ringtones
"""

from __future__ import annotations

import random
import string

import pytest

from levi.buzztunes import ringtone
from levi.buzztunes.ringtone import (
    AUTO_TRIM_MS,
    AUTO_WINDOW_MS,
    EQ_BAND_HZ,
    EQ_MAX_DB,
    EQ_MIN_DB,
    EQ_PRESETS,
    MAX_RINGTONE_MS,
    MIN_RINGTONE_MS,
    RingtoneError,
    allowed_write_path,
    auto_trim,
    default_trim,
    export_receipt,
    parse_video_id,
    plan,
    ringtone_filename,
    validate_eq,
    validate_fade,
    validate_trim,
)

VID = "dQw4w9WgXcQ"  # 11 chars, valid shape


# ---- L4: URL gate ----

def test_parse_watch_url():
    assert parse_video_id(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ") == VID


def test_parse_short_url():
    assert parse_video_id("https://youtu.be/dQw4w9WgXcQ") == VID


def test_parse_shorts_and_embed():
    assert parse_video_id(
        "https://www.youtube.com/shorts/dQw4w9WgXcQ") == VID
    assert parse_video_id(
        "https://www.youtube.com/embed/dQw4w9WgXcQ") == VID
    assert parse_video_id(
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ") == VID


def test_parse_bare_domain_gets_scheme():
    assert parse_video_id("youtube.com/watch?v=dQw4w9WgXcQ") == VID


@pytest.mark.parametrize("bad", [
    "https://vimeo.com/12345",
    "https://www.youtube.com/",
    "https://www.youtube.com/watch?v=short",
    "https://youtu.be/",
    "https://evil-youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ",
    "",
    "not a url at all",
])
def test_parse_rejects_non_youtube(bad):
    with pytest.raises(RingtoneError):
        parse_video_id(bad)


def _rand_host(rng):
    return rng.choice([
        "youtube.com", "www.youtube.com", "m.youtube.com",
        "music.youtube.com", "youtu.be",
    ])


def _rand_vid(rng):
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(rng.choice(alphabet) for _ in range(11))


def test_property_url_gate_never_leaks(rng_seed=20260929):
    """L4 property: accepted ids are always 11-char and from YouTube hosts;
    hostile hosts are always refused."""
    rng = random.Random(rng_seed)
    for _ in range(500):
        host = _rand_host(rng)
        vid = _rand_vid(rng)
        if host == "youtu.be":
            url = f"https://{host}/{vid}"
        else:
            url = f"https://{host}/watch?v={vid}"
        got = parse_video_id(url)
        assert got == vid and len(got) == 11
    for _ in range(200):
        host = rng.choice([
            "youtube.com.evil.com", "evilyoutube.com", "youtu.be.evil.com",
            "notyoutube.org", "youtubecom",
        ])
        with pytest.raises(RingtoneError):
            parse_video_id(f"https://{host}/watch?v={_rand_vid(rng)}")


# ---- L2: trim bounds ----

def test_validate_basic():
    assert validate_trim(5_000, 30_000, 200_000) == (5_000, 30_000)


def test_validate_clamps_to_duration():
    assert validate_trim(0, 999_000, 200_000) == (0, 45_000)  # capped too


def test_validate_negative_start_clamped():
    assert validate_trim(-5_000, 20_000, 200_000) == (0, 20_000)


def test_validate_collapsed_range_refused():
    with pytest.raises(RingtoneError):
        validate_trim(50_000, 40_000, 200_000)  # start past end
    with pytest.raises(RingtoneError):
        validate_trim(300_000, 400_000, 200_000)  # wholly past duration


def test_validate_unknown_duration_refused():
    with pytest.raises(RingtoneError):
        validate_trim(0, 10_000, 0)
    with pytest.raises(RingtoneError):
        validate_trim(0, 10_000, -5)


def test_validate_too_short_refused():
    with pytest.raises(RingtoneError):
        validate_trim(1_000, 1_500, 200_000)


def test_validate_non_int_refused():
    with pytest.raises(RingtoneError):
        validate_trim(0.5, 10_000, 200_000)


def test_default_trim_caps():
    assert default_trim(200_000) == (0, 45_000)
    assert default_trim(20_000) == (0, 20_000)


def test_property_trim_laws_hold(rng_seed=777):
    """L2 property: on every random draw, the guard's output satisfies
    0 <= start < end <= duration and end - start <= MAX_RINGTONE_MS,
    or it raises RingtoneError (also legal)."""
    rng = random.Random(rng_seed)
    for _ in range(2000):
        duration = rng.randint(1, 600_000)
        start = rng.randint(-60_000, 600_000)
        end = rng.randint(-60_000, 660_000)
        try:
            s, e = validate_trim(start, end, duration)
        except RingtoneError:
            continue
        assert 0 <= s < e <= duration, (start, end, duration, s, e)
        assert e - s <= MAX_RINGTONE_MS
        assert e - s >= MIN_RINGTONE_MS


# ---- L1: write boundary ----

def test_allowed_write_path():
    cache = "/data/data/dev.buzztunes.app/cache"
    assert allowed_write_path(cache + "/yt-audio.m4a", cache)
    assert allowed_write_path(cache, cache)
    assert allowed_write_path("Ringtones/mine.m4a", cache)
    assert not allowed_write_path("/sdcard/Music/mine.m4a", cache)
    assert not allowed_write_path("/data/data/dev.buzztunes.app/cache-evil/x", cache)
    assert not allowed_write_path("", cache)
    assert not allowed_write_path(cache + "/x", "")


def test_property_write_boundary_never_escapes(rng_seed=4242):
    """L1 property: random hostile paths are refused; only cache-rooted
    and Ringtones paths pass."""
    rng = random.Random(rng_seed)
    cache = "/data/data/dev.buzztunes.app/cache"
    evil = ["/sdcard/", "/data/data/other.app/", "..", "/",
            cache + "-suffix", cache.replace("cache", "cache2")]
    for _ in range(500):
        base = rng.choice(evil)
        p = base + "".join(
            rng.choice(string.ascii_lowercase) for _ in range(8))
        assert not allowed_write_path(p, cache), p
    for _ in range(200):
        p = cache + "/" + "".join(
            rng.choice(string.ascii_lowercase) for _ in range(8))
        assert allowed_write_path(p, cache)


# ---- L5/L6: plan + receipt ----

def test_plan_end_to_end():
    p = plan("https://youtu.be/dQw4w9WgXcQ", "My Song",
             0, 60_000, 200_000)
    assert p.video_id == VID
    assert (p.start_ms, p.end_ms) == (0, 45_000)
    assert p.length_ms == 45_000
    assert p.filename.endswith(".m4a") and VID in p.filename


def test_plan_rejects_bad_url_and_bad_trim():
    with pytest.raises(RingtoneError):
        plan("https://vimeo.com/1", "x", 0, 10_000, 200_000)
    with pytest.raises(RingtoneError):
        plan("https://youtu.be/dQw4w9WgXcQ", "x", 0, 10_000, 0)


def test_ringtone_filename_sanitized():
    name = ringtone_filename(VID, 'a/b\\c:d*e?f"g<h>i|j')
    assert "/" not in name and "\\" not in name
    assert name.endswith(".m4a")


def test_export_receipt_shape():
    r = export_receipt(VID, "My Song", 0, 45_000,
                       "content://media/external/audio/media/42", 200_000)
    assert r["kind"] == "ringtone_export"
    assert r["length_ms"] == 45_000
    assert r["video_id"] == VID
    assert "exported_at" in r


def test_describe_lists_laws():
    d = ringtone.describe()
    assert d["max_length_ms"] == MAX_RINGTONE_MS
    assert len(d["laws"]) == 8
    assert d["eq_bands_hz"] == [60, 230, 910, 3600, 14000]
    assert "bass_boost" in d["eq_presets"]


# ---- L7: auto-trim ----

def _spike_energies(n=240, spike_at=120, spike_len=60,
                    low=0.1, high=1.0):
    e = [low] * n
    for i in range(spike_at, min(n, spike_at + spike_len)):
        e[i] = high
    return e


def test_auto_trim_picks_the_drop():
    # 120s track, 30s spike at 60s -> pick covers the spike.
    e = _spike_energies()
    s, ms = auto_trim(120_000, e)
    assert s <= 60_000 <= ms
    assert ms - s == AUTO_TRIM_MS


def test_auto_trim_short_track_gives_whole_track():
    e = [0.5] * 20  # 10s of audio
    assert auto_trim(10_000, e) == (0, 10_000)


def test_auto_trim_deterministic():
    rng = random.Random(42)
    e = [rng.random() for _ in range(300)]
    assert auto_trim(150_000, e) == auto_trim(150_000, e)


def test_auto_trim_ties_break_earliest():
    e = [1.0] * 200  # flat: every run ties -> earliest wins
    s, ms = auto_trim(100_000, e)
    assert (s, ms) == (0, AUTO_TRIM_MS)


def test_auto_trim_rejects_garbage():
    with pytest.raises(RingtoneError):
        auto_trim(100_000, [])
    with pytest.raises(RingtoneError):
        auto_trim(0, [0.5] * 10)
    with pytest.raises(RingtoneError):
        auto_trim(100_000, [0.5, -1.0, 0.5])


def test_property_auto_trim_obeys_l2(rng_seed=31337):
    """L7 property: the DJ's pick always satisfies the trim laws."""
    rng = random.Random(rng_seed)
    for _ in range(500):
        duration = rng.randint(5_000, 400_000)
        n = max(1, duration // AUTO_WINDOW_MS)
        e = [rng.random() * rng.choice([1, 1, 1, 5]) for _ in range(n)]
        try:
            s, ms = auto_trim(duration, e)
        except RingtoneError:
            continue
        assert 0 <= s < ms <= duration
        assert ms - s <= MAX_RINGTONE_MS
        assert ms - s >= MIN_RINGTONE_MS


def test_dj_hook_delegates():
    from levi.buzztunes import dj
    e = _spike_energies()
    assert dj.suggest_ringtone_segment("HUMBLE.", 120_000, e) == \
        auto_trim(120_000, e)


# ---- L8: equalizer ----

def test_eq_presets_valid():
    for name, gains in EQ_PRESETS.items():
        out = validate_eq(name)
        assert len(out) == len(EQ_BAND_HZ) == 5
        assert all(EQ_MIN_DB <= g <= EQ_MAX_DB for g in out)


def test_eq_explicit_gains():
    assert validate_eq([0, 0, 0, 0, 0]) == (0.0, 0.0, 0.0, 0.0, 0.0)
    assert validate_eq([-15, 15, 0, 0, 0]) == (-15.0, 15.0, 0.0, 0.0, 0.0)


@pytest.mark.parametrize("bad", [
    [16, 0, 0, 0, 0], [-16, 0, 0, 0, 0], [0, 0, 0, 0], [0] * 6,
    "not-a-preset", None, ["loud"] * 5,
])
def test_eq_rejects_bad(bad):
    with pytest.raises(RingtoneError):
        validate_eq(bad)


def test_property_eq_bounds(rng_seed=606):
    """L8 property: gains inside ±15dB always pass; outside never do."""
    rng = random.Random(rng_seed)
    for _ in range(300):
        gains = [rng.uniform(-15, 15) for _ in range(5)]
        assert validate_eq(gains) == tuple(gains)
    for _ in range(100):
        gains = [rng.uniform(-15, 15) for _ in range(5)]
        i = rng.randrange(5)
        gains[i] = rng.choice([-15.1, 15.1, -30, 30])
        with pytest.raises(RingtoneError):
            validate_eq(gains)


# ---- L8: fades ----

def test_fade_basic():
    assert validate_fade(2000, 3000, 30_000) == (2000, 3000)
    assert validate_fade(0, 0, 30_000) == (0, 0)


def test_fade_scales_when_too_long():
    # 20s + 20s fades on a 30s segment -> 15s/15s, exact fit.
    fi, fo = validate_fade(20_000, 20_000, 30_000)
    assert (fi, fo) == (15_000, 15_000)
    assert fi + fo == 30_000


def test_fade_clamped_to_segment():
    fi, fo = validate_fade(60_000, 0, 30_000)
    assert (fi, fo) == (30_000, 0)


def test_fade_rejects_negative():
    with pytest.raises(RingtoneError):
        validate_fade(-100, 1000, 30_000)


def test_property_fade_always_fits(rng_seed=909):
    """L8 property: validated fades always fit inside the segment."""
    rng = random.Random(rng_seed)
    for _ in range(500):
        length = rng.randint(1_000, 45_000)
        fi = rng.randint(0, 60_000)
        fo = rng.randint(0, 60_000)
        a, b = validate_fade(fi, fo, length)
        assert 0 <= a and 0 <= b and a + b <= length


# ---- plan with eq/fade ----

def test_plan_with_eq_and_fade():
    p = plan("https://youtu.be/dQw4w9WgXcQ", "My Song",
             0, 60_000, 200_000,
             eq="bass_boost", fade_in_ms=2000, fade_out_ms=3000)
    assert p.eq_bands == EQ_PRESETS["bass_boost"]
    assert p.eq_preset_name == "bass_boost"
    assert (p.fade_in_ms, p.fade_out_ms) == (2000, 3000)


def test_plan_defaults_flat_no_fade():
    p = plan("https://youtu.be/dQw4w9WgXcQ", "x", 0, 10_000, 200_000)
    assert p.eq_bands == EQ_PRESETS["flat"]
    assert (p.fade_in_ms, p.fade_out_ms) == (0, 0)


def test_plan_rejects_bad_eq():
    with pytest.raises(RingtoneError):
        plan("https://youtu.be/dQw4w9WgXcQ", "x", 0, 10_000, 200_000,
             eq=[99, 0, 0, 0, 0])


def test_receipt_carries_eq_fade_autotrim():
    r = export_receipt(VID, "t", 0, 30_000, "uri", 200_000,
                       eq_bands=(6.0, 4.0, 0.0, 0.0, 0.0),
                       fade_in_ms=2000, fade_out_ms=3000,
                       auto_trimmed=True)
    assert r["eq_db"] == [6.0, 4.0, 0.0, 0.0, 0.0]
    assert r["fade_ms"] == {"in": 2000, "out": 3000}
    assert r["auto_trimmed"] is True
