"""Tests for revival wave 37: efficient codecs & vector graphics.

RLE image, GIF/LZW codec, bitmap pages, ITA2 mode-shift, turbo proxy,
alphageometric PDI, NAPLPS PDI with macros and DRCS. Deterministic, no
network, stdlib only.
"""

import pytest

from core.levi.revival import (
    rle_image,
    gif_codec,
    bitmap_pages,
    mode_shift_code,
    turbo_proxy,
    alphageometric,
    pdi_graphics,
)


# ===========================================================================
# rle_image (CompuServe RLE shape)
# ===========================================================================


def test_rle_blank_roundtrip():
    img = rle_image.RLEImage.blank()
    assert rle_image.RLEImage.decode(img.encode()) == img


def test_rle_checkerboard_roundtrip():
    img = rle_image.RLEImage.blank()
    for y in range(0, rle_image.HEIGHT, 4):
        for x in range(rle_image.WIDTH):
            img.set(x, y, (x // 4) % 2)
    decoded = rle_image.RLEImage.decode(img.encode())
    assert decoded.pixels == img.pixels


def test_rle_stream_shape():
    img = rle_image.RLEImage.blank()
    img.set(0, 0, rle_image.BLACK)
    stream = img.encode()
    assert stream.startswith("\x1bGH")
    assert stream.endswith("Z")
    # one black pixel, then 49151 white pixels split into 522 runs of 94 + 1 of 83
    expected = "\x1bGH" + "B!" + "W~" * 522 + "Ws" + "Z"
    assert stream == expected


def test_rle_rejects_bad_header():
    with pytest.raises(rle_image.RLEImageError):
        rle_image.RLEImage.decode("XXB!Z")


def test_rle_rejects_truncated_stream():
    img = rle_image.RLEImage.blank()
    stream = img.encode()
    with pytest.raises(rle_image.RLEImageError):
        rle_image.RLEImage.decode(stream[:-2])


# ===========================================================================
# gif_codec (GIF-shaped LZW)
# ===========================================================================


def test_lzw_roundtrip():
    cases = [
        (bytes([i % 3 for i in range(500)]), 2),
        (bytes([i % 9 for i in range(500)] + [12] * 100), 4),
        (bytes([i % 251 for i in range(2000)]), 8),
    ]
    for data, mcs in cases:
        assert gif_codec.lzw_decompress(gif_codec.lzw_compress(data, mcs)) == data


def test_lzw_rejects_out_of_range_values():
    with pytest.raises(gif_codec.GIFError):
        gif_codec.lzw_compress(bytes([4]), 2)


def test_gif_encode_decode_roundtrip():
    palette = [(0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255)]
    pixels = [(x + y) % 4 for y in range(8) for x in range(8)]
    img = gif_codec.PalettedImage(8, 8, pixels, palette)
    blob = img.encode()
    assert blob[:6] == b"GIF89a"
    assert blob.endswith(b"\x3b")
    back = gif_codec.PalettedImage.decode(blob)
    assert (back.width, back.height) == (8, 8)
    assert back.pixels == pixels
    assert back.palette[:4] == palette


def test_gif_rejects_bad_signature():
    with pytest.raises(gif_codec.GIFError):
        gif_codec.PalettedImage.decode(b"XXXXXX" + b"\x00" * 20)


def test_gif_single_pixel_image():
    img = gif_codec.PalettedImage(1, 1, [0], [(10, 20, 30)])
    back = gif_codec.PalettedImage.decode(img.encode())
    assert back.pixels == [0]


# ===========================================================================
# bitmap_pages (CAPTAIN shape)
# ===========================================================================


def test_page_roundtrip():
    page = bitmap_pages.BitmapPage.blank(16, 4)
    page.set(0, 0)
    page.set(15, 3)
    back = bitmap_pages.BitmapPage.decode(page.encode())
    assert back.rows == page.rows
    assert (back.width, back.height) == (16, 4)


def test_page_copy_token_for_repeated_lines():
    page = bitmap_pages.BitmapPage.blank(8, 3)
    encoded = page.encode()
    assert encoded.count(bitmap_pages._COPY_TOKEN + "\n") == 2


def test_page_all_black_row():
    page = bitmap_pages.BitmapPage(10, 2, [bytes([1] * 10), bytes([0] * 10)])
    back = bitmap_pages.BitmapPage.decode(page.encode())
    assert back.rows[0] == bytes([1] * 10)
    assert back.rows[1] == bytes([0] * 10)


def test_page_rejects_bad_magic():
    with pytest.raises(bitmap_pages.PageError):
        bitmap_pages.BitmapPage.decode("XX 8 8\n")


def test_page_ascii_render():
    page = bitmap_pages.BitmapPage(4, 2, [bytes([1, 0, 1, 0]), bytes([0] * 4)])
    art = page.to_ascii()
    assert art.split("\n")[0] == "# # "


# ===========================================================================
# mode_shift_code (ITA2)
# ===========================================================================


def test_ita2_letters_roundtrip():
    codes = mode_shift_code.encode("HELLO WORLD")
    assert mode_shift_code.decode(codes) == "HELLO WORLD"


def test_ita2_mixed_roundtrip():
    text = "MEET AT 5 PM, BRING $20!"
    codes = mode_shift_code.encode(text)
    assert mode_shift_code.decode(codes) == text
    # shift codes actually inserted around the figures
    assert mode_shift_code.FIGS in codes
    assert mode_shift_code.LTRS in codes


def test_ita2_starts_in_letters_no_leading_shift():
    codes = mode_shift_code.encode("ABC")
    assert codes[0] != mode_shift_code.LTRS


def test_ita2_pack_unpack_roundtrip():
    codes = mode_shift_code.encode("SOS 123")
    packed = mode_shift_code.pack(codes)
    assert mode_shift_code.unpack(packed, len(codes)) == codes


def test_ita2_rejects_unknown_character():
    with pytest.raises(mode_shift_code.ModeShiftError):
        mode_shift_code.encode("héllo")


def test_ita2_rejects_unknown_code():
    with pytest.raises(mode_shift_code.ModeShiftError):
        mode_shift_code.decode([63])


# ===========================================================================
# turbo_proxy (Opera Turbo shape)
# ===========================================================================


def test_turbo_off_is_passthrough():
    proxy = turbo_proxy.TurboProxy(enabled=False)
    page = turbo_proxy.PageModel(
        "<html>   <body>hi</body> </html>",
        [turbo_proxy.PageAsset("image", "a.png", 10000, alt="a")],
    )
    out, report = proxy.fetch(page)
    assert report.savings_ratio == 0.0
    assert not report.degraded()
    assert proxy.status()["indicator"] == "grey"


def test_turbo_on_compresses_and_reports_honestly():
    proxy = turbo_proxy.TurboProxy(enabled=True)
    page = turbo_proxy.PageModel(
        "<html><!-- x --><body>   hi   </body></html>",
        [turbo_proxy.PageAsset("image", "a.png", 10000, alt="photo")],
    )
    out, report = proxy.fetch(page)
    assert report.savings_ratio > 0.5  # image dominates
    assert report.degraded()  # images replaced
    assert out.assets[0].alt == "photo"  # alt text kept
    assert out.assets[0].size == 256  # placeholder budget
    assert proxy.status() == {"turbo": "ON", "indicator": "green", "runs": 1}


def test_turbo_toggle_flips_indicator():
    proxy = turbo_proxy.TurboProxy()
    proxy.toggle(True)
    assert proxy.status()["turbo"] == "ON"
    proxy.toggle(False)
    assert proxy.status()["turbo"] == "OFF"


def test_turbo_stage_reports_add_up():
    proxy = turbo_proxy.TurboProxy(enabled=True)
    page = turbo_proxy.PageModel("<p>a</p>", [])
    _, report = proxy.fetch(page)
    assert report.original_bytes - report.final_bytes == sum(
        s.bytes_saved for s in report.stages
    )


# ===========================================================================
# alphageometric (Telidon shape)
# ===========================================================================


def test_coord_pack_roundtrip():
    for value in (0, 1, 63, 4095, 16777215):
        assert alphageometric.decode_coord(alphageometric.encode_coord(value)) == value


def test_xy_pack_roundtrip():
    assert alphageometric.decode_xy(alphageometric.encode_xy(12345, 678)) == (
        12345,
        678,
    )


def test_page_encode_decode_roundtrip():
    page = (
        alphageometric.Page()
        .line(0, 0, 100, 200)
        .rect(10, 10, 50, 60)
        .point(5, 5)
        .text(1, 2, "HI")
    )
    stream = page.encode()
    assert all(32 <= ord(c) < 127 or c in "\x1b" for c in stream)
    back = alphageometric.Page.decode(stream)
    assert len(back.instructions) == 4
    assert back.instructions[0].points == [(0, 0), (100, 200)]
    assert back.instructions[3].text == "HI"


def test_segments_flatten_rect():
    page = alphageometric.Page().rect(0, 0, 10, 10)
    assert len(page.segments()) == 4


def test_rejects_bad_opcode():
    with pytest.raises(alphageometric.AlphaGeoError):
        alphageometric.Page.decode("!")


def test_rejects_out_of_range_coord():
    with pytest.raises(alphageometric.AlphaGeoError):
        alphageometric.encode_coord(1 << 24)


# ===========================================================================
# pdi_graphics (NAPLPS shape)
# ===========================================================================


def test_pdi_draw_roundtrip():
    canvas = (
        pdi_graphics.Canvas()
        .line(0, 0, 300, 400)
        .rect(10, 20, 30, 40)
        .circle(5, 5, 9)
        .text(1, 1, "NAPLPS")
    )
    back = pdi_graphics.Canvas.decode(canvas.encode())
    assert len(back.stream) == 4
    assert back.stream[0].startswith(pdi_graphics.OP_LINE)


def test_pdi_macro_define_and_expand():
    canvas = pdi_graphics.Canvas()
    body = (
        pdi_graphics.OP_LINE
        + pdi_graphics.encode_xy(1, 2)
        + pdi_graphics.encode_xy(3, 4)
    )
    canvas.define_macro("box", body).run_macro("box").run_macro("box")
    back = pdi_graphics.Canvas.decode(canvas.encode())
    assert "box" in back.macros
    assert back.stream.count(body) == 2  # expanded at decode time


def test_pdi_macro_rejects_undefined_run():
    canvas = pdi_graphics.Canvas()
    with pytest.raises(pdi_graphics.PDIError):
        canvas.run_macro("nope")


def test_pdi_drcs_load_and_use():
    canvas = pdi_graphics.Canvas()
    glyphs = {65: ["0110", "1001", "1111", "1001"]}
    canvas.load_font("f1", glyphs).drcs_text("f1", 10, 10, [65])
    back = pdi_graphics.Canvas.decode(canvas.encode())
    assert back.glyph("f1", 65) == ["0110", "1001", "1111", "1001"]


def test_pdi_polygon_needs_three_points():
    with pytest.raises(pdi_graphics.PDIError):
        pdi_graphics.Canvas().polygon([(0, 0), (1, 1)])


def test_pdi_value_pack_roundtrip():
    for groups in (2, 3, 4):
        for value in (0, 63, (1 << (6 * groups)) - 1):
            assert (
                pdi_graphics.decode_value(pdi_graphics.encode_value(value, groups))
                == value
            )


def test_pdi_rejects_bad_opcode():
    with pytest.raises(pdi_graphics.PDIError):
        pdi_graphics.Canvas.decode("!")


def test_pdi_variable_resolution():
    canvas = pdi_graphics.Canvas(groups=2)
    canvas.point(100, 200)
    back = pdi_graphics.Canvas.decode(canvas.encode())
    assert back.stream[0].startswith(pdi_graphics.OP_POINT + "2")
