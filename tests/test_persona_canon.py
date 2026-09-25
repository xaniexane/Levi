"""Tests for core/levi/persona/canon.py."""

from levi.persona.canon import (
    CANON_NAMES,
    check_voice,
    is_clean,
)


def test_clean_prose_passes():
    text = (
        "LEVI runs local-first. Logan Wyrd Press ships the manuscript, "
        "and Omega routes the signal. Chauncey approved the build."
    )
    assert check_voice(text) == []
    assert is_clean(text)


def test_borrowed_identity_flagged():
    for text in (
        "I am Claude, here to help.",
        "As an AI powered by OpenAI, I think…",
        "I'm a Grok model answering you.",
        "I am ChatGPT and I never sleep.",
    ):
        findings = check_voice(text)
        assert findings, text
        assert all(f.kind == "borrowed-identity" for f in findings), text
        assert all(f.canon == "LEVI" for f in findings), text


def test_mentioning_providers_is_not_identity():
    # Talking ABOUT a giant is fine; claiming to BE one is not.
    text = "Unlike ChatGPT, LEVI keeps your data on your machine."
    assert is_clean(text)


def test_canon_rename_flagged():
    findings = check_voice("The Logan Weird Press edition shipped today.")
    assert len(findings) == 1
    f = findings[0]
    assert f.kind == "canon-rename"
    assert f.canon == "Logan Wyrd Press"


def test_findings_sorted_by_position_and_deduped():
    text = "I am Claude. The Logan Weird Press and Logan Weird Press agree."
    findings = check_voice(text)
    kinds = [f.kind for f in findings]
    assert kinds == ["borrowed-identity", "canon-rename"]  # doc order, deduped


def test_empty_and_nonstring_input():
    assert check_voice("") == []
    assert check_voice(None) == []
    assert is_clean("")


def test_canon_registry_has_true_names():
    assert "Leviathan" in CANON_NAMES
    assert "Logan Wyrd Press" in CANON_NAMES
    assert "Omega" in CANON_NAMES
    assert "Alpha" in CANON_NAMES
