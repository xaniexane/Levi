"""Tests for levi.bot.summarize — deterministic extractive summaries.

Proofs for the module's contract: sentences are *selected* from the
source (never generated), scoring is deterministic (ties break by
position), the sentence budget is hard, held-back sentences are counted
in ``dropped``, and every malformed input is refused with a named
error.
"""

from __future__ import annotations

import pytest

from levi.bot.summarize import SHELF, SummaryError, summarize

_TEXT = (
    "Leviathan is the codename for the local-first synthetic organism. "
    "The organism runs entirely offline on the user's own machines. "
    "Training happens on the user's own records, never outsourced. "
    "The organism is local-first and offline by design. "
    "Bread is baked every morning. "
    "The baker wakes at dawn."
)


def test_picks_top_sentences_in_source_order():
    result = summarize(_TEXT, max_lines=2)
    assert result.sentences == 2
    assert result.dropped == 4
    assert result.text == (
        "Leviathan is the codename for the local-first synthetic organism. "
        "The organism runs entirely offline on the user's own machines."
    )


def test_output_sentences_come_from_source_verbatim():
    result = summarize(_TEXT, max_lines=3)
    for sentence in result.text.split(". "):
        piece = sentence if sentence.endswith(".") else sentence + "."
        assert piece in _TEXT


def test_deterministic_across_runs():
    assert summarize(_TEXT, max_lines=3).text == summarize(_TEXT, max_lines=3).text


def test_tie_break_favors_earlier_sentence():
    text = (
        "Alpha builds engine prime. Beta builds engine dual. Gamma builds engine trine."
    )
    # All three score identically — the earlier ones must win.
    result = summarize(text, max_lines=2)
    assert result.text == "Alpha builds engine prime. Beta builds engine dual."


def test_budget_honored_and_dropped_counted():
    result = summarize(_TEXT, max_lines=1)
    assert result.sentences == 1
    assert result.dropped == 5
    assert result.compression == pytest.approx(round(1 / 6, 4))


def test_max_chars_trims_at_sentence_boundaries():
    result = summarize(_TEXT, max_lines=6, max_chars=120)
    assert len(result.text) <= 120
    # No cut sentences: every kept sentence ends with a period.
    for sentence in [s.strip() for s in result.text.split(".") if s.strip()]:
        assert (sentence + ".") in _TEXT or sentence in _TEXT


def test_sentence_never_cut_in_half():
    with pytest.raises(SummaryError):
        summarize("A very long sentence " * 40 + ". Short.", max_lines=2, max_chars=50)


def test_char_budget_fitting_nothing_is_honest():
    with pytest.raises(SummaryError):
        summarize(_TEXT, max_lines=6, max_chars=5)


def test_deny_closed_inputs():
    with pytest.raises(SummaryError):
        summarize("")
    with pytest.raises(SummaryError):
        summarize("   ")
    with pytest.raises(SummaryError):
        summarize(42)  # type: ignore[arg-type]
    with pytest.raises(SummaryError):
        summarize(_TEXT, max_lines=0)
    with pytest.raises(SummaryError):
        summarize(_TEXT, max_lines=-3)
    with pytest.raises(SummaryError):
        summarize(_TEXT, max_lines=True)
    with pytest.raises(SummaryError):
        summarize(_TEXT, max_lines=3, max_chars=0)


def test_single_sentence_text():
    result = summarize("Only one sentence here.", max_lines=4)
    assert result.sentences == 1
    assert result.dropped == 0
    assert result.compression == 1.0
    assert result.text == "Only one sentence here."


def test_shelf_descriptor_present():
    assert SHELF["name"] == "bot-summarize"
    assert "never generated" in SHELF["summary"]
