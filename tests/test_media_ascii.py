"""Tests for levi.media.ascii_art — proving L1..L6."""

import hashlib
import json
import struct
import zlib
from pathlib import Path

import pytest

from levi.media import ascii_art as aa
from levi.media import local as _local


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _render_rgb(seed=7, style="dark", w=64, h=48):
    from levi.media.local import _V2_STYLES, _render, _render2, _seed_from, encode_png

    s = _seed_from("test", seed)
    rgb = _render2(w, h, s, style) if style in _V2_STYLES else _render(w, h, s, style)
    return w, h, rgb, encode_png(w, h, rgb)


def _png_bytes(width, height, color_type, rows):
    """Hand-build a PNG with explicit per-row filter bytes (tests unfilter)."""
    raw = b"".join(bytes([f]) + r for f, r in rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)

    def chunk(ctype, data):
        crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


# ---------------------------------------------------------------------------
# L3: lossless decode
# ---------------------------------------------------------------------------


def test_decode_roundtrip_rgb():
    for seed, style in [(7, "dark"), (42, "abstract"), (99, "poster")]:
        w, h, rgb, png = _render_rgb(seed, style)
        dw, dh, drgb = aa.decode_png(png)
        assert (dw, dh) == (w, h)
        assert drgb == rgb  # byte-for-byte


def test_decode_unfilter_all_types_and_alpha():
    # 2x2 RGBA: row0 filter=1 (Sub), row1 filter=4 (Paeth); alpha stripped.
    px = [(10, 20, 30, 255), (40, 50, 60, 128), (70, 80, 90, 0), (100, 110, 120, 255)]
    raw_rows = []
    for r in range(2):
        row = b"".join(bytes(p) for p in px[r * 2 : r * 2 + 2])
        raw_rows.append(row)
    # encode with Sub on row0, Paeth on row1 (pre-filtered manually)
    bpp = 4
    f1 = bytearray(raw_rows[0])
    for i in range(bpp, 8):
        f1[i] = (f1[i] - f1[i - bpp]) & 0xFF
    prev = raw_rows[0]
    cur = bytearray(raw_rows[1])
    f4 = bytearray(cur)
    for i in range(8):
        a = cur[i - bpp] if i >= bpp else 0
        b_, c_ = prev[i], prev[i - bpp] if i >= bpp else 0
        p = a + b_ - c_
        pa, pb, pc = abs(p - a), abs(p - b_), abs(p - c_)
        pr = a if (pa <= pb and pa <= pc) else (b_ if pb <= pc else c_)
        f4[i] = (cur[i] - pr) & 0xFF
    png = _png_bytes(2, 2, 6, [(1, bytes(f1)), (4, bytes(f4))])
    w, h, rgb = aa.decode_png(png)
    assert (w, h) == (2, 2)
    expected = b"".join(bytes(p[:3]) for p in px)
    assert rgb == expected


def test_decode_fail_closed():
    _, _, _, png = _render_rgb()
    with pytest.raises(aa.PngDecodeError):
        aa.decode_png(b"not a png")
    with pytest.raises(aa.PngDecodeError):
        aa.decode_png(png[:40])  # truncated
    bad = bytearray(png)
    bad[50] ^= 0xFF  # corrupt -> CRC mismatch
    with pytest.raises(aa.PngDecodeError):
        aa.decode_png(bytes(bad))
    # unsupported color type (grayscale=0)
    ihdr_bad = struct.pack(">IIBBBBB", 8, 8, 8, 0, 0, 0, 0)

    def chunk(ctype, data):
        crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)

    gray_png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr_bad)
        + chunk(b"IDAT", zlib.compress(b"\x00" + b"\x80" * 8))
        + chunk(b"IEND", b"")
    )
    with pytest.raises(aa.PngDecodeError):
        aa.decode_png(gray_png)


# ---------------------------------------------------------------------------
# ASCII encode / decode
# ---------------------------------------------------------------------------


def test_ascii_deterministic_and_shaped():
    w, h, rgb, _ = _render_rgb()
    a1 = aa.image_to_ascii(rgb, w, h, cols=40)
    a2 = aa.image_to_ascii(rgb, w, h, cols=40)
    assert a1.lines == a2.lines
    assert a1.cols == 40 and all(len(l) == 40 for l in a1.lines)
    assert a1.rows == max(1, round(40 * h / w * aa.CELL_ASPECT))
    assert set("".join(a1.lines)) <= set(aa.CHARSET_DENSE)


def test_ascii_rejects_bad_params():
    w, h, rgb, _ = _render_rgb()
    with pytest.raises(ValueError):
        aa.image_to_ascii(rgb, w, h, cols=4)
    with pytest.raises(ValueError):
        aa.image_to_ascii(rgb, w, h, cols=40, charset="aaa")
    with pytest.raises(ValueError):
        aa.image_to_ascii(b"short", w, h)


def test_ascii_to_rgb_dims_and_deterministic():
    w, h, rgb, _ = _render_rgb()
    art = aa.image_to_ascii(rgb, w, h, cols=32)
    rw, rh, out1 = aa.ascii_to_rgb(art, scale=8)
    _, _, out2 = aa.ascii_to_rgb(art, scale=8)
    assert (rw, rh) == (32 * 8, art.rows * 8)
    assert out1 == out2 and len(out1) == rw * rh * 3
    # grayscale: r == g == b everywhere
    assert all(out1[i] == out1[i + 1] == out1[i + 2] for i in range(0, len(out1), 3))
    with pytest.raises(ValueError):
        aa.ascii_to_rgb(art, scale=0)


# ---------------------------------------------------------------------------
# Bundle pack / unpack / fingerprint
# ---------------------------------------------------------------------------


def _bundle():
    w, h, rgb, png = _render_rgb()
    return aa.compress_png(png, prompt="test", seed=7, style="dark", cols=40), png


def test_bundle_roundtrip_and_fingerprint_stable():
    b, _ = _bundle()
    packed = aa.pack(b)
    b2 = aa.unpack(packed)
    assert aa.pack(b2) == packed
    assert aa.fingerprint(b) == aa.fingerprint(b2)


def test_bundle_rejects_garbage():
    b, _ = _bundle()
    packed = aa.pack(b)
    with pytest.raises(aa.BundleError):
        aa.unpack("not json")
    with pytest.raises(aa.BundleError):
        aa.unpack(json.dumps({"v": 999}))
    doc = json.loads(packed)
    doc["rows"] = doc["rows"] + 5  # lie about dimensions
    with pytest.raises(aa.BundleError):
        aa.unpack(json.dumps(doc))
    doc2 = json.loads(packed)
    del doc2["art"]
    with pytest.raises(aa.BundleError):
        aa.unpack(json.dumps(doc2))


# ---------------------------------------------------------------------------
# L1 / L2: regenerate + compress
# ---------------------------------------------------------------------------


def test_regenerate_byte_identical_l1():
    b, _ = _bundle()
    assert aa.regenerate(b, scale=4) == aa.regenerate(b, scale=4)
    assert aa.regenerate(b, scale=4)[:8] == b"\x89PNG\r\n\x1a\n"


def test_regenerate_dims():
    b, _ = _bundle()
    png = aa.regenerate(b, scale=8)
    w, h, _ = aa.decode_png(png)
    assert (w, h) == (b.cols * 8, b.rows * 8)


def test_bundle_smaller_than_png_l2():
    for seed, style, cols in [(7, "dark", 80), (42, "abstract", 60), (99, "photo", 80)]:
        w, h, rgb, png = _render_rgb(seed, style, 256, 256)
        b = aa.compress_png(png, cols=cols)
        packed_len = len(aa.pack(b).encode("utf-8"))
        assert packed_len < len(png), f"L2 failed for {style}: {packed_len} >= {len(png)}"


def test_compress_pixels_hook_matches_png_path():
    w, h, rgb, png = _render_rgb()
    via_pixels = aa.compress_pixels(rgb, w, h, cols=40)
    via_png = aa.compress_png(png, cols=40)
    assert via_pixels.art == via_png.art  # same composition


def test_compress_file(tmp_path):
    _, _, _, png = _render_rgb()
    p = tmp_path / "src.png"
    p.write_bytes(png)
    b = aa.compress_file(p, cols=40)
    assert b.src_sha256 == hashlib.sha256(png).hexdigest()
    out = tmp_path / "re.png"
    assert aa.regenerate_to(b, out, scale=4) == str(out)
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# Remix
# ---------------------------------------------------------------------------


def test_remix_invert_and_charset():
    b, _ = _bundle()
    r1 = aa.remix(b, invert=True)
    r2 = aa.remix(b, invert=True)
    assert r1.art == r2.art  # deterministic
    assert r1.art != b.art  # actually changed
    assert r1.params["remixed_from"] == aa.fingerprint(b)
    r3 = aa.remix(b, charset=aa.CHARSET_BLOCKS)
    assert set("".join(r3.art)) <= set(aa.CHARSET_BLOCKS)
    # remix regenerates fine
    assert aa.regenerate(r1, scale=4)[:8] == b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# L6: fidelity is measured
# ---------------------------------------------------------------------------


def test_fidelity_measured_not_claimed():
    w, h, rgb, _ = _render_rgb()
    art = aa.image_to_ascii(rgb, w, h, cols=40)
    fid = aa.fidelity(rgb, w, h, art)
    assert 0.0 < fid["similarity"] <= 1.0
    assert 0.0 <= fid["mae"] <= 255.0
    assert fid["psnr_db"] > 0


# ---------------------------------------------------------------------------
# L4: thumbs-down loop
# ---------------------------------------------------------------------------


def test_browse_session_deals_per_round(tmp_path):
    s = aa.BrowseSession("a red barn", per_round=3, seed=1234, work_dir=tmp_path / "s1")
    cands = s.candidates
    assert len(cands) == 3
    assert len({c.id for c in cands}) == 3
    assert all(Path(c.path).exists() for c in cands)
    assert all(c.bundle.art for c in cands)


def test_thumbs_down_fresh_alternatives_l4(tmp_path):
    s = aa.BrowseSession("a red barn", per_round=3, seed=1234, work_dir=tmp_path / "s1")
    first_ids = {c.id for c in s.candidates}
    victim = s.candidates[0].id
    new_cands = s.thumbs_down(victim)
    new_ids = {c.id for c in new_cands}
    assert len(new_cands) == 3
    assert new_ids.isdisjoint(first_ids)  # all fresh
    assert victim not in new_ids  # rejected never reappears
    # second thumbs-down: still fresh, still no repeats
    victim2 = new_cands[0].id
    third = s.thumbs_down(victim2)
    third_ids = {c.id for c in third}
    assert third_ids.isdisjoint(first_ids | new_ids)
    hist = s.history()
    assert hist["rejected"] == sorted([victim, victim2])
    assert hist["rounds_dealt"] == 3


def test_browse_session_deterministic(tmp_path):
    kw = dict(prompt="a red barn", per_round=3, seed=99)
    s1 = aa.BrowseSession(work_dir=tmp_path / "a", **kw)
    s2 = aa.BrowseSession(work_dir=tmp_path / "b", **kw)
    assert [c.seed for c in s1.candidates] == [c.seed for c in s2.candidates]
    assert s1.export_bundle(s1.candidates[0].id) == s2.export_bundle(s2.candidates[0].id)


def test_browse_session_misuse_raises(tmp_path):
    s = aa.BrowseSession("x", per_round=2, seed=5, work_dir=tmp_path / "s")
    with pytest.raises(aa.CurateError):
        s.thumbs_down("nope")
    vid = s.candidates[0].id
    s.thumbs_down(vid)
    with pytest.raises(aa.CurateError):
        s.thumbs_down(vid)  # double reject
    # thumbs-up locks the session
    winner = s.candidates[0].id
    assert s.thumbs_up(winner).id == winner
    assert s.final.id == winner
    with pytest.raises(aa.CurateError):
        s.thumbs_down(s.candidates[0].id)  # session over
    with pytest.raises(aa.CurateError):
        aa.BrowseSession("", per_round=2)
    with pytest.raises(aa.CurateError):
        aa.BrowseSession("x", per_round=0)


def test_export_bundle_regenerates(tmp_path):
    s = aa.BrowseSession("a lighthouse", per_round=2, seed=11, work_dir=tmp_path / "s")
    cid = s.candidates[0].id
    packed = s.export_bundle(cid)
    b = aa.unpack(packed)
    regen = aa.regenerate(b, scale=4)
    w, h, _ = aa.decode_png(regen)
    assert (w, h) == (b.cols * 4, b.rows * 4)


# ---------------------------------------------------------------------------
# Academy drill runner
# ---------------------------------------------------------------------------


def test_ex_media_ascii_drill(tmp_path):
    entry = {"title": "ascii compression drill"}
    result = aa.ex_media_ascii(entry, {}, {}, work_dir=tmp_path / "drill")
    assert result["score"] == 1.0
    assert all(c["passed"] for c in result["checks"])
    art = result["artifact"]
    assert art["status"] == "ok"
    assert art["ratio"] > 1.0
    assert 0.0 < art["fidelity"]["similarity"] <= 1.0
    assert Path(art["source_png"]).exists()
    assert Path(art["bundle_txt"]).exists()
    assert Path(art["regenerated_png"]).exists()
    # the stored bundle genuinely regenerates
    b = aa.unpack(Path(art["bundle_txt"]).read_text(encoding="utf-8"))
    assert aa.regenerate(b, scale=4) == Path(art["regenerated_png"]).read_bytes()
