"""Tests for levi.weblayer — the honest Web layer."""

import json
import re

import pytest

from levi.weblayer import Canvas, Hotspot, to_html, to_svg
from levi.weblayer.__main__ import main as cli_main


def _canvas() -> Canvas:
    return Canvas(
        width=800, height=600, title="test", image="t.png",
        hotspots=[
            Hotspot(id="r1", shape="rect", coords=[10, 10, 100, 50],
                    href="a.html", label="A"),
            Hotspot(id="e1", shape="ellipse", coords=[400, 300, 60, 40],
                    href="b.html", label="B", alt="bee"),
            Hotspot(id="p1", shape="polygon", coords=[10, 500, 90, 500, 50, 560],
                    href="c.html", label="C"),
        ])


def test_valid_canvas_passes():
    c = _canvas()
    c.validate()
    assert len(c.hotspots) == 3


def test_zero_canvas_size_refused():
    with pytest.raises(ValueError):
        Canvas(width=0, height=100).validate()


def test_negative_rect_size_refused():
    with pytest.raises(ValueError):
        Canvas(width=100, height=100,
               hotspots=[Hotspot(id="x", shape="rect", coords=[0, 0, -5, 5],
                                 href="a")]).validate()


def test_out_of_bounds_refused():
    with pytest.raises(ValueError):
        Canvas(width=100, height=100,
               hotspots=[Hotspot(id="x", shape="rect", coords=[90, 90, 50, 50],
                                 href="a")]).validate()


def test_polygon_needs_three_points():
    with pytest.raises(ValueError):
        Canvas(width=100, height=100,
               hotspots=[Hotspot(id="x", shape="polygon", coords=[1, 2, 3, 4],
                                 href="a")]).validate()


def test_duplicate_ids_refused():
    h = Hotspot(id="dup", shape="rect", coords=[0, 0, 10, 10], href="a")
    with pytest.raises(ValueError):
        Canvas(width=100, height=100, hotspots=[h, h]).validate()


def test_bad_id_refused():
    with pytest.raises(ValueError):
        Canvas(width=100, height=100,
               hotspots=[Hotspot(id="No Spaces!", shape="rect",
                                 coords=[0, 0, 10, 10], href="a")]).validate()


def test_missing_href_refused():
    with pytest.raises(ValueError):
        Canvas(width=100, height=100,
               hotspots=[Hotspot(id="x", shape="rect", coords=[0, 0, 10, 10],
                                 href="  ")]).validate()


def test_malformed_dict_refused():
    with pytest.raises(ValueError):
        Hotspot.from_dict({"id": "x"})
    with pytest.raises(ValueError):
        Canvas.from_dict({"width": 1})


def test_dict_roundtrip():
    c = _canvas()
    assert Canvas.from_dict(json.loads(json.dumps(c.to_dict()))).to_dict() == c.to_dict()


def test_html_export_has_map_and_areas():
    out = to_html(_canvas())
    assert '<map name="weblayer">' in out
    assert out.count("<area ") == 3
    assert 'shape="rect" coords="10,10,110,60"' in out
    # ellipse degrades to circle at the smaller radius (min(60, 40) = 40);
    # polygon uses the poly keyword
    assert 'shape="circle" coords="400,300,40"' in out
    assert 'shape="poly" coords="10,500,90,500,50,560"' in out
    assert "no tracking" in out


def test_html_export_uses_only_valid_keywords():
    # W3C HTML5 §4.8.12: area shape keywords are rect, circle, poly,
    # default. Anything else silently degrades to rectangle in browsers.
    out = to_html(_canvas())
    shapes = re.findall(r'shape="([^"]+)"', out)
    assert shapes, "expected shape attributes in HTML output"
    assert set(shapes) <= {"rect", "circle", "poly", "default"}
    assert 'shape="ellipse"' not in out
    assert 'shape="polygon"' not in out


def test_html_circle_radius_uses_smaller_axis():
    c = Canvas(
        width=200,
        height=200,
        hotspots=[
            Hotspot(
                id="e",
                shape="ellipse",
                coords=[100, 100, 70, 30],
                href="a",
            )
        ],
    )
    out = to_html(c)
    assert 'shape="circle" coords="100,100,30"' in out


def test_svg_export_has_anchors_and_shapes():
    out = to_svg(_canvas())
    assert out.count("<a href=") == 3
    assert "<rect " in out and "<ellipse " in out and "<polygon " in out
    assert 'viewBox="0 0 800 600"' in out


def test_html_escapes_href_and_label():
    c = Canvas(width=100, height=100,
               hotspots=[Hotspot(id="x", shape="rect", coords=[0, 0, 10, 10],
                                 href='a"b<c', label="<b>bold</b>")])
    out = to_html(c)
    assert 'a&quot;b&lt;c' in out
    assert "&lt;b&gt;bold&lt;/b&gt;" in out


def test_cli_demo_prints_valid_json(capsys):
    assert cli_main(["demo"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert Canvas.from_dict(data).width == 800


def test_cli_validate(tmp_path, capsys):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(_canvas().to_dict()))
    assert cli_main(["validate", str(p)]) == 0
    assert "valid" in capsys.readouterr().out
    p.write_text('{"width": -1}')
    assert cli_main(["validate", str(p)]) == 1


def test_cli_export(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(_canvas().to_dict()))
    out = tmp_path / "c.svg"
    assert cli_main(["export", str(p), "--format", "svg", "-o", str(out)]) == 0
    assert "<svg" in out.read_text()
