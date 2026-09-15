"""Tests for the capability atlas (honest 'what can you do?')."""

from __future__ import annotations

import json
from pathlib import Path

ATLAS = (
    Path(__file__).resolve().parent.parent
    / "core"
    / "levi"
    / "knowledge"
    / "capabilities"
    / "atlas.json"
)


def _atlas() -> dict:
    return json.loads(ATLAS.read_text(encoding="utf-8"))


def test_atlas_domains_reference_only_real_tools():
    from levi.agent.tools import build_default_registry

    real = set(build_default_registry()._tools)
    atlas = _atlas()
    assert len(atlas["domains"]) >= 10, "atlas should cover the platform's domains"
    ids = [d["id"] for d in atlas["domains"]]
    assert len(ids) == len(set(ids)), "duplicate domain ids"
    for d in atlas["domains"]:
        assert d["id"] and d["name"] and d["description"]
        assert d["example_prompts"], f"{d['id']} has no example prompts"
        assert d["known_limits"], f"{d['id']} lists no limits"
        for t in d["tools"]:
            assert t in real, f"domain {d['id']} references non-existent tool {t!r}"


def test_capabilities_tool_returns_full_list_and_single_domain():
    from levi.agent.tools import build_default_registry, ExecContext

    reg = build_default_registry()
    ctx = ExecContext()
    full = reg.execute("capabilities", {}, ctx)
    assert full.ok, full.error
    assert "Honesty rule" in full.output
    one = reg.execute("capabilities", {"domain": "current-events"}, ctx)
    assert one.ok, one.error
    assert "current-events" in one.output
    assert "curriculum-qa" not in one.output  # narrowed correctly
    bad = reg.execute("capabilities", {"domain": "time-travel"}, ctx)
    assert not bad.ok and "unknown domain" in bad.error
