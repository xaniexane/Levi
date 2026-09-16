"""Tests for levi.videotex — the Minitel-heritage navigation layer."""

from __future__ import annotations

import pytest

from levi.videotex import CHOICES_PER_SCREEN, PAGE_WIDTH
from levi.videotex.keys import guide_lines, parse
from levi.videotex.navigate import Navigator
from levi.videotex.pages import build_tree, render, wrap


# ---------------------------------------------------------------- key parsing
def test_parse_minitel_keys():
    assert parse("*").kind == "retour"
    assert parse("#").kind == "envoi"
    assert parse("sommaire").kind == "sommaire"
    assert parse("suite").kind == "suite"
    assert parse("guide").kind == "guide"
    assert parse("annulation").kind == "annulation"
    assert parse("repetition").kind == "repetition"
    assert parse("correction").kind == "correction"


def test_parse_aliases_and_digits():
    assert parse("home").kind == "sommaire"
    assert parse("?").kind == "guide"
    assert parse("q").kind == "annulation"
    assert parse("3").kind == "choice" and parse("3").number == 3
    assert parse("nope").kind == "unknown"
    assert parse("").kind == "unknown"
    assert parse("   ").kind == "unknown"


def test_guide_mentions_keys():
    text = "\n".join(guide_lines())
    assert "RETOUR" in text and "ENVOI" in text and "sommaire" in text


# ---------------------------------------------------------------- 40 columns
def test_wrap_never_exceeds_width():
    lines = wrap(" ".join(["mot"] * 200))
    assert lines and all(len(ln) <= PAGE_WIDTH for ln in lines)


def test_wrap_hard_splits_long_tokens():
    lines = wrap("x" * 100)
    assert all(len(ln) <= PAGE_WIDTH for ln in lines)
    assert "".join(lines) == "x" * 100


def test_render_lines_fit_terminal():
    nav = Navigator.build()
    for pid, page in nav.pages.items():
        for line in render(page, [page.title]).splitlines():
            assert len(line) <= PAGE_WIDTH, (pid, line)


# ---------------------------------------------------------------- navigation
def test_drill_down_and_back():
    nav = Navigator.build()
    assert nav.current == "home"
    nav.handle("1")  # warehouses
    assert nav.current == "warehouses"
    nav.handle("*")  # retour
    assert nav.current == "home"


def test_sommaire_returns_home_from_deep():
    nav = Navigator.build()
    nav.handle("1")
    first_wh = nav._visible()[0].target
    nav.handle("1")
    assert nav.current == first_wh
    nav.handle("sommaire")
    assert nav.current == "home" and nav.history == []


def test_unknown_choice_is_harmless():
    nav = Navigator.build()
    text, quit_flag = nav.handle("99")
    assert not quit_flag and nav.current == "home"
    assert "inconnu" in text


def test_unknown_key_points_to_guide():
    text, quit_flag = Navigator.build().handle("xyzzy")
    assert not quit_flag and "guide" in text


def test_annulation_quits_at_root():
    text, quit_flag = Navigator.build().handle("annulation")
    assert quit_flag


def test_retour_at_root_hangs_up_minitel_style():
    text, quit_flag = Navigator.build().handle("*")
    assert quit_flag


def test_suite_chunks_long_choice_lists():
    nav = Navigator.build()
    nav.handle("2")  # docs page: dozens of documents
    page = nav.pages["docs"]
    total = len(page.choices)
    assert total > CHOICES_PER_SCREEN
    first_chunk = [c.label for c in nav._visible()]
    nav.handle("suite")
    second_chunk = [c.label for c in nav._visible()]
    assert first_chunk != second_chunk
    assert len(first_chunk) == CHOICES_PER_SCREEN


def test_suite_at_end_is_harmless():
    nav = Navigator.build()
    nav.handle("2")
    for _ in range(20):
        nav.handle("suite")
    text, quit_flag = nav.handle("suite")
    assert not quit_flag and "pas d'autre page" in text


def test_run_script_replays_session():
    nav = Navigator.build()
    outputs = nav.run_script(["1", "*", "annulation"])
    assert len(outputs) == 4  # initial render + 3 inputs
    assert nav.current == "home"  # annulation at root hangs up


# ---------------------------------------------------------------- passive law
def test_every_choice_target_resolves_to_a_page():
    """The passive-terminal law: choices navigate, never execute."""
    nav = Navigator.build()
    seen = set()
    stack = ["home"]
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        for choice in nav.pages[pid].choices:
            assert isinstance(choice.target, str), pid
            assert choice.target in nav.pages, (pid, choice.target)
            stack.append(choice.target)
    assert len(seen) > 3  # home + sections + content


# ---------------------------------------------------------------- adapters
def test_tree_degrades_honestly_without_sources(tmp_path):
    pages = build_tree(root=tmp_path)
    assert "home" in pages and "guide" in pages
    text = render(pages["warehouses"], ["x"])
    assert "indisponible" in text or "introuvable" in text
    assert render(pages["docs"], ["x"])


def test_real_tree_has_content():
    pages = build_tree()
    assert len(pages["warehouses"].choices) >= 10  # fourteen warehouses documented
    assert len(pages["docs"].choices) >= 10
