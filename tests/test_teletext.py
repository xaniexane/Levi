"""Tests for levi.teletext — the broadcast page carousel."""

from __future__ import annotations

import urllib.request

import pytest

from levi.teletext.pages import (
    COLS,
    MAX_PAGE,
    MIN_PAGE,
    ROWS,
    Page,
    PageStore,
    pages_from_mapping,
    render_frame,
    valid_page_number,
)
from levi.teletext.serve import build_local_pages, index_page, serve


def test_page_number_bounds():
    assert valid_page_number(100) and valid_page_number(899)
    assert not valid_page_number(99) and not valid_page_number(900)
    with pytest.raises(ValueError):
        Page(number=99, title="bad")


def test_render_grid_dimensions():
    frame = render_frame(Page(number=100, title="TEST", body=["hello"]))
    lines = frame.splitlines()
    assert len(lines) == ROWS
    assert all(len(line) == COLS for line in lines)
    assert lines[0].startswith("P100")
    assert "hello" in frame


def test_body_wraps_to_40_columns():
    frame = render_frame(Page(number=101, title="T", body=["x" * 120]))
    for line in frame.splitlines():
        assert len(line) == COLS


def test_subpages_rotate():
    store = PageStore()
    store.add(Page(number=302, title="SPORT", body=["a"], subpage=1, subpages=2))
    store.add(Page(number=302, title="SPORT", body=["b"], subpage=2, subpages=2))
    assert store.get(302, 1).body == ["a"]
    assert store.get(302, 2).body == ["b"]


def test_carousel_cycles_endlessly():
    store = PageStore()
    store.add(Page(number=100, title="A", body=[]))
    store.add(Page(number=101, title="B", body=[]))
    cycle = store.carousel()
    seq = [next(cycle).number for _ in range(5)]
    assert seq == [100, 101, 100, 101, 100]


def test_pages_from_mapping_paginates():
    mapping = {f"key{i}": f"value{i}" for i in range(50)}
    pages = pages_from_mapping("MAP", mapping, start=150)
    assert pages[0].number == 150
    assert all(valid_page_number(p.number) for p in pages)
    assert len(pages) > 1


def test_index_lists_pages():
    store = build_local_pages()
    idx = index_page(store)
    assert idx.number == 100
    rendered = render_frame(idx)
    assert "101" in rendered and "200" in rendered


def test_serve_localhost_only():
    store = build_local_pages()
    with pytest.raises(ValueError):
        serve(store, host="0.0.0.0", port=8478)


def test_serve_page_over_http():
    store = build_local_pages()
    server, _thread = serve(store, port=18477)
    try:
        with urllib.request.urlopen("http://127.0.0.1:18477/101", timeout=5) as r:
            text = r.read().decode("utf-8")
        assert "P101" in text
        with urllib.request.urlopen("http://127.0.0.1:18477/carousel", timeout=5) as r:
            assert "P1" in r.read().decode("utf-8")
        with urllib.request.urlopen("http://127.0.0.1:18477/", timeout=5) as r:
            assert "INDEX" in r.read().decode("utf-8")
    finally:
        server.shutdown()


def test_demo_cli_render():
    from levi.teletext.__main__ import main

    assert main(["render", "101"]) == 0
    assert main(["carousel", "--steps", "1"]) == 0
    assert main(["index"]) == 0
