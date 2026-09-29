"""Tests for the sundown bot — the evening card, composed not typed."""

import pytest

from levi.bot.sundown import (
    SundownError,
    compose_sundown,
    default_providers,
    handoffs_provider,
    ledger_provider,
    shipped_provider,
)


def _one(name="s"):
    return lambda: [f"{name}-line"]


def test_compose_sections_in_order():
    card = compose_sundown("EOD", {"a": _one("a"), "b": _one("b")})
    assert card.text.startswith("EOD")
    assert "a-line" in card.text and "b-line" in card.text
    assert card.text.index("a-line") < card.text.index("b-line")


def test_silent_provider():
    def boom():
        raise RuntimeError("nope")

    card = compose_sundown("EOD", {"ok": _one(), "bad": boom})
    assert "SILENT (RuntimeError)" in card.text
    assert "nope" not in card.text  # error class, never the traceback


def test_empty_section_is_quiet():
    card = compose_sundown("EOD", {"empty": lambda: []})
    assert "(quiet)" in card.text


def test_refuses_empty_providers():
    with pytest.raises(SundownError):
        compose_sundown("EOD", {})


def test_refuses_non_callable():
    with pytest.raises(SundownError):
        compose_sundown("EOD", {"x": "not-callable"})


def test_refuses_non_mapping():
    with pytest.raises(SundownError):
        compose_sundown("EOD", ["x"])


def test_refuses_blank_title():
    with pytest.raises(SundownError):
        compose_sundown("   ", {"x": _one()})


def test_deterministic():
    providers = {"a": _one("a"), "b": _one("b")}
    first = compose_sundown("EOD", providers).text
    second = compose_sundown("EOD", providers).text
    assert first == second


def test_line_budget_honored():
    providers = {
        f"s{i}": (lambda i=i: [f"line-{i}-{j}" for j in range(20)]) for i in range(3)
    }
    card = compose_sundown("EOD", providers, max_lines=12)
    assert card.dropped > 0
    assert len(card.text.splitlines()) <= 12  # hard budget, never exceeded


def test_default_providers_table():
    providers = default_providers()
    assert set(providers) == {"shipped", "handoffs", "ledger"}
    for _name, fn in providers.items():
        lines = fn()
        assert isinstance(lines, list)
        assert all(isinstance(x, str) for x in lines)


def test_shipped_provider_never_crashes():
    lines = shipped_provider()
    assert isinstance(lines, list) and lines


def test_handoffs_provider_honest():
    lines = handoffs_provider()
    assert isinstance(lines, list) and lines
    assert any("handoff" in line.lower() for line in lines)


def test_ledger_provider_honest():
    lines = ledger_provider()
    assert isinstance(lines, list) and lines
