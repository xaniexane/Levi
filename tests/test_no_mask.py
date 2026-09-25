"""No-mask tests — LEVI wears no mask: 100% pure LEVI.

Everything LEVI renders about itself must pass check_no_mask():
no borrowed identities, no provider branding worn as its own.
"""

from levi.bot.persona import (
    _IDENTITY_PATTERNS,
    answer_identity_question,
    check_no_mask,
    render_system_prompt,
)


def test_rendered_system_prompt_is_pure():
    assert check_no_mask(render_system_prompt()) == []


def test_identity_answers_are_pure():
    for _pattern, reply in _IDENTITY_PATTERNS:
        assert check_no_mask(reply) == [], reply


def test_identity_answers_name_levi():
    assert "LEVI" in (answer_identity_question("who are you") or "")
    assert "LEVI" in (answer_identity_question("are you grok") or "")


def test_catches_borrowed_identity():
    violations = check_no_mask("I am Grok, here to help!")
    assert violations, "expected a mask violation to be caught"
    assert any("forbidden claim" in v for v in violations)


def test_catches_provider_brands():
    assert check_no_mask("I was built by xai") != []
    assert check_no_mask("powered by openai under the hood") != []
    assert check_no_mask("I am sentient") != []


def test_clean_levi_text_passes():
    clean = (
        "I'm LEVI — a local-first synthetic-intelligence companion. "
        "Not artificial. Synthetic."
    )
    assert check_no_mask(clean) == []


def test_empty_and_non_string_are_safe():
    assert check_no_mask("") == []
    assert check_no_mask(None) == []  # type: ignore[arg-type]
