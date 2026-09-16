"""Tests for PDI (ASCII opcode vector-graphics stream).

Hermetic: pure functions everywhere; tmp_path only for the CLI
file-input tests.
"""

from __future__ import annotations

import io

import pytest

from levi.pdi.pdi import (
    PDIError,
    PALETTE,
    parse,
    validate,
    render_svg,
    render_ascii,
)


# ------------------------------------------------------------------ parsing


def test_parse_each_opcode():
    pic = parse("C\nK 3\nP 10 20\nL 0 0 100 100\nR 10 10 20 30\nE 50 50 10 20\nT 5 5 hi\n")
    names = [op.name for op in pic.ops]
    assert names == ["K", "P", "L", "R", "E", "T"]
    assert pic.ops[0].args == (3,)
    assert pic.ops[1].args == (10.0, 20.0)
    assert pic.ops[4].args == (50.0, 50.0, 10.0, 20.0)
    assert pic.ops[5].args == (5.0, 5.0, "hi")
    assert pic.cleared


def test_parse_ignores_comments_blank_lines_and_semicolons():
    src = "# a comment\n\nK 1; K 2\n   L 0 0 1 1  # trailing\n"
    pic = parse(src)
    names = [op.name for op in pic.ops]
    assert names == ["K", "K", "L"]
    assert pic.ops[0].line == 3
    assert pic.ops[2].line == 4


def test_text_is_literal_rest_of_line():
    pic = parse("T 20 40 Hello, world! 1 <2> & 3")
    assert pic.ops[0].args[2] == "Hello, world! 1 <2> & 3"


def test_unknown_opcode_raises_with_line_number():
    with pytest.raises(PDIError) as ei:
        parse("K 1\nZ 9\n")
    assert "line 2" in str(ei.value)


def test_wrong_arg_count_raises():
    with pytest.raises(PDIError) as ei:
        parse("L 0 0 1\n")
    assert "line 1" in str(ei.value)


def test_non_numeric_arg_raises():
    with pytest.raises(PDIError) as ei:
        parse("R 10 x 20 30\n")
    assert "line 1" in str(ei.value)


def test_bad_palette_index_raises():
    with pytest.raises(PDIError):
        parse("K 9\n")
    with pytest.raises(PDIError):
        parse("K 1.5\n")


def test_validate_returns_error_strings_without_raising():
    assert validate("K 1\nL 0 0 100 100\n") == []
    errors = validate("K 1\nBOOM\n")
    assert len(errors) == 1
    assert errors[0].startswith("line 2")


# ------------------------------------------------------------------- render


def test_render_svg_contains_expected_elements():
    pic = parse("K 2\nP 10 10\nL 0 0 100 100\nR 10 10 20 20\nE 50 50 10 10\nT 5 5 hi\n")
    svg = render_svg(pic)
    assert "<svg" in svg and "</svg>" in svg
    assert "<line" in svg and "<rect" in svg and "<ellipse" in svg and "<text" in svg


def test_render_svg_escapes_text():
    pic = parse("T 10 10 A & B <C>\n")
    svg = render_svg(pic)
    assert "&amp;" in svg
    assert "&lt;C&gt;" in svg


def test_render_svg_k_changes_color():
    pic = parse("L 0 0 10 10\nK 2\nL 0 0 10 10\n")
    svg = render_svg(pic)
    assert PALETTE[7] in svg  # default color before K
    assert PALETTE[2] in svg  # color after K 2
    assert svg.index(PALETTE[7]) < svg.index(PALETTE[2])


def test_render_svg_clear_adds_background():
    with_bg = render_svg(parse("C\nL 0 0 10 10\n"))
    without_bg = render_svg(parse("L 0 0 10 10\n"))
    assert without_bg.count("<rect") == 0
    assert with_bg.count("<rect") == 1
    assert PALETTE[0] in with_bg


def test_render_ascii_horizontal_line():
    pic = parse("L 0 50 100 50\n")
    art = render_ascii(pic, cols=16, rows=8)
    lines = art.split("\n")
    assert len(lines) == 8
    mid = lines[4]
    assert set(mid.strip()) == {"#"}
    assert all(line.strip() == "" for i, line in enumerate(lines) if i != 4)


def test_render_ascii_later_ops_overwrite():
    pic = parse("L 0 50 100 50\nP 50 50\n")
    art = render_ascii(pic, cols=16, rows=8)
    assert art.split("\n")[4][8] == "*"


def test_render_ascii_text_clipping_does_not_crash():
    pic = parse("T 95 50 way too far to the right edge of the grid\n")
    art = render_ascii(pic, cols=16, rows=8)
    assert len(art.split("\n")) == 8


def test_clear_resets_ops():
    pic = parse("L 0 0 10 10\nL 0 0 20 20\nC\nP 1 1\n")
    assert [op.name for op in pic.ops] == ["P"]
    assert pic.cleared


# ---------------------------------------------------------------------- CLI


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def _run_cli(monkeypatch, tmp_path, argv, stdin_text=""):
    from levi.pdi import __main__ as cli

    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_cli_validate_file(tmp_path, monkeypatch):
    f = _write(tmp_path, "ok.pdi", "K 1\nL 0 0 100 100\n")
    code, out, _ = _run_cli(monkeypatch, tmp_path, ["validate", f])
    assert code == 0
    assert out.strip() == "valid"


def test_cli_validate_rejects_bad_file(tmp_path, monkeypatch):
    f = _write(tmp_path, "bad.pdi", "NOPE\n")
    code, _, err = _run_cli(monkeypatch, tmp_path, ["validate", f])
    assert code == 1
    assert "line 1" in err


def test_cli_render_ascii_from_stdin(monkeypatch, tmp_path):
    code, out, _ = _run_cli(
        monkeypatch, tmp_path, ["render", "--ascii"], stdin_text="L 0 50 100 50\n"
    )
    assert code == 0
    assert "#" in out


def test_cli_render_svg_from_file(tmp_path, monkeypatch):
    f = _write(tmp_path, "a.pdi", "K 3\nR 10 10 80 60\n")
    code, out, _ = _run_cli(monkeypatch, tmp_path, ["render", "--svg", f])
    assert code == 0
    assert "<svg" in out and "<rect" in out
