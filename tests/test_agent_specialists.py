"""Specialist registry boundary tests (hermetic, stdlib-only)."""

from __future__ import annotations

import pytest

from levi.agent.specialists import SpecialistRegistry


def test_select_for_intent_rejects_non_string():
    reg = SpecialistRegistry()
    for bad in (None, 123, "", "   "):
        with pytest.raises(ValueError, match="non-empty string"):
            reg.select_for_intent(bad)  # type: ignore[arg-type]


def test_select_for_intent_still_selects():
    reg = SpecialistRegistry()
    selected = reg.select_for_intent("research the backup schedule")
    ids = {s.id for s in selected}
    assert "supervisor" in ids and "research" in ids
