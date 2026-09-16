"""Tests for levi.reveal — the Reveal-Codes inspector."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from levi.reveal import CodeToken, exorcise, invisible_names, reveal  # noqa: E402


def kinds(text):
    return sorted(t.kind for t in reveal(text).tokens)


def test_heading():
    r = reveal("# Hello\n## Sub\n")
    heads = [t for t in r.tokens if t.kind == "heading"]
    assert [t.label for t in heads] == ["H1", "H2"]
    assert heads[0].detail == "Hello"


def test_inline_structure():
    r = reveal(
        "This is **bold** and *italic* with `code` and "
        "[a link](https://example.com/x).\n"
    )
    labels = [t.label for t in r.tokens]
    assert "B" in labels and "I" in labels and "CODE" in labels
    link = [t for t in r.tokens if t.kind == "link"][0]
    assert link.detail == "https://example.com/x"


def test_image_target():
    r = reveal("![alt](https://example.com/pic.png)\n")
    imgs = [t for t in r.tokens if t.kind == "image"]
    assert len(imgs) == 1
    assert imgs[0].detail == "https://example.com/pic.png"
    # the image must not also be reported as a link
    assert not [t for t in r.tokens if t.kind == "link"]


def test_list_quote_table_hr():
    text = "- one\n  1. two\n> quoted\n| a | b |\n|---|---|\n***\n"
    ks = kinds(text)
    assert "list" in ks and "quote" in ks and "table" in ks and "hr" in ks


def test_fenced_block_hides_structure():
    text = "```\n# not a heading\n**not bold**\n```\n"
    r = reveal(text)
    assert not [t for t in r.tokens if t.kind == "heading"]
    assert not [t for t in r.tokens if t.kind == "em"]
    assert [t.label for t in r.tokens if t.kind == "fenced"] == [
        "FENCE-ON",
        "FENCE-OFF",
    ]


def test_frontmatter():
    text = "---\ntitle: notes\n---\nBody.\n"
    r = reveal(text)
    labels = [t.label for t in r.tokens if t.kind == "frontmatter"]
    assert labels[0] == "FM-START" and labels[-1] == "FM-END"


def test_zero_width_found_and_visualized():
    r = reveal("hello\u200bworld\n")
    zw = [t for t in r.tokens if t.kind == "zero-width"]
    assert len(zw) == 1 and zw[0].label == "ZWSP"
    assert "<ZWSP>" in r.render()


def test_trailing_whitespace_hard_break():
    r = reveal("ends here  \nplain\n")
    ws = [t for t in r.tokens if t.kind == "trailing-ws"]
    assert len(ws) == 1 and ws[0].detail == "hard break"
    plain = reveal("plain\n")
    assert not [t for t in plain.tokens if t.kind == "trailing-ws"]


def test_bom():
    r = reveal("\ufeffhello\n")
    assert [t.label for t in r.tokens if t.kind == "bom"] == ["BOM"]


def test_nbsp_and_tab_indent():
    r = reveal("\tindented\nspaced\u00a0here\n")
    assert any(t.kind == "stray-tab" for t in r.tokens)
    assert any(t.label == "NBSP" for t in r.tokens)


def test_exorcise_removes_and_reports():
    cleaned, removed = exorcise("a\u200bb  \n")
    assert "\u200b" not in cleaned
    assert not cleaned.splitlines()[0].endswith(" ")
    assert len(removed) == 2
    assert all(isinstance(t, CodeToken) for t in removed)


def test_exorcise_keeps_visible_structure():
    text = "# Title\n**bold** [l](https://x.example)\n"
    cleaned, removed = exorcise(text)
    assert cleaned == text
    assert removed == []


def test_reveal_never_modifies_input():
    text = "# T\nline  \n"
    r = reveal(text)
    assert r.text == text


def test_summary_counts():
    r = reveal("# H\n**b**\nplain\u200b\n")
    s = r.summary()
    assert s["tokens"] == len(r.tokens)
    assert s["invisibles"] >= 1
    assert s["by_kind"]["heading"] == 1


def test_invisible_names_stable():
    names = invisible_names()
    assert names["\u200b"] == "ZWSP"
    assert len(names) >= 8


def test_empty_and_plain():
    r = reveal("")
    assert r.tokens == []
    r2 = reveal("just words\nmore words\n")
    assert r2.tokens == []
