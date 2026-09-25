"""Hub social LEVI tab — bottom-nav slot, permission gate, bloodstream.

Hermetic: no network, no HOME writes (LEVI_HUB_SOCIAL_DIR redirected to tmp).
"""

import pytest

from levi.hub.social_levi_tab import (
    ASK_VISIBILITY,
    SURFACES,
    TAB_DESCRIPTOR,
    TAB_MAP_STATUS,
    LeviPresence,
    PermissionDenied,
    PermissionGate,
    SurfaceBus,
    UnknownSurface,
    ask,
    nav_slots,
    render_nav_html,
    render_tab_html,
)


@pytest.fixture()
def gate(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HUB_SOCIAL_DIR", str(tmp_path / "social"))
    return PermissionGate()


@pytest.fixture()
def presence(gate):
    return LeviPresence(gate=gate)


# -- the bottom-nav slot ---------------------------------------------------


def test_tab_descriptor_shape():
    for key in ("id", "label", "icon", "route", "position", "kind"):
        assert key in TAB_DESCRIPTOR
    assert TAB_DESCRIPTOR["id"] == "levi"
    assert TAB_DESCRIPTOR["kind"] == "intelligence"


def test_nav_slots_claim_levi():
    slots = nav_slots()
    assert [s["id"] for s in slots] == ["levi"]


def test_tab_map_is_explicitly_unresolved():
    assert TAB_MAP_STATUS["status"] == "unresolved"
    assert TAB_MAP_STATUS["decided_by"] == "Chauncey"
    assert "open_question" in TAB_MAP_STATUS


def test_render_nav_includes_levi_intelligence_marker():
    html = render_nav_html()
    assert 'data-tab="levi"' in html
    assert 'data-kind="intelligence"' in html
    assert "LEVI" in html


def test_render_nav_sorted_by_position():
    extra = [
        {
            "id": "feed",
            "label": "Feed",
            "icon": "F",
            "route": "/tab/feed",
            "position": 1,
            "kind": "surface",
        }
    ]
    html = render_nav_html(extra_slots=extra)
    assert html.index("Feed") < html.index("LEVI")


# -- permission gate: fail closed -------------------------------------------


def test_gate_denies_by_default(gate):
    assert not gate.check("feed", "summarize")


def test_gate_grant_then_check(gate):
    gate.grant("feed", "summarize")
    assert gate.check("feed", "summarize")
    assert not gate.check("feed", "draft-reply")  # grant is per-action


def test_gate_revoke(gate):
    gate.grant("feed", "summarize")
    gate.revoke("feed", "summarize")
    assert not gate.check("feed", "summarize")


def test_gate_revoke_all_surface(gate):
    gate.grant("feed", "summarize")
    gate.grant("feed", "draft-reply")
    gate.revoke_all("feed")
    assert gate.grants() == []


def test_gate_rejects_unknown_surface(gate):
    with pytest.raises(UnknownSurface):
        gate.grant("void-surface", "act")


def test_gate_persists_locally(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HUB_SOCIAL_DIR", str(tmp_path / "social"))
    g1 = PermissionGate()
    g1.grant("creation", "caption-draft")
    g2 = PermissionGate()  # fresh instance, same data dir
    assert g2.check("creation", "caption-draft")


def test_gate_corrupt_file_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HUB_SOCIAL_DIR", str(tmp_path / "social"))
    g = PermissionGate()
    g.path.write_text("{broken", encoding="utf-8")
    g2 = PermissionGate()
    assert not g2.check("feed", "summarize")


def test_grant_ledger_is_auditable(gate):
    gate.grant("discovery", "tune-recipe", note="member said yes")
    ledger = gate.grants()
    assert len(ledger) == 1
    assert ledger[0]["note"] == "member said yes"


# -- bloodstream: assist requires grant, returns paired advisory ------------


def test_assist_without_grant_raises(presence):
    with pytest.raises(PermissionDenied):
        presence.assist("feed", "summarize", "what did I miss")


def test_assist_with_grant_returns_advisory(presence, gate):
    gate.grant("feed", "summarize")
    adv = presence.assist("feed", "summarize", "what did I miss today")
    assert adv.advisory is True
    assert adv.needs_member_decision is True
    assert adv.surface == "feed"
    assert adv.draft  # proposer produced a draft
    assert adv.verifier_note  # verifier produced the honest check
    assert adv.draft != adv.verifier_note  # two minds, not one


def test_assist_after_revoke_denied(presence, gate):
    gate.grant("communities", "summarize-thread")
    gate.revoke("communities", "summarize-thread")
    with pytest.raises(PermissionDenied):
        presence.assist("communities", "summarize-thread", "tl;dr")


def test_assist_unknown_surface_raises(presence):
    with pytest.raises(UnknownSurface):
        presence.assist("void", "act", "x")


def test_bloodstream_covers_four_surfaces():
    assert set(SURFACES) == {"feed", "communities", "discovery", "creation"}


def test_audit_lists_grants(presence, gate):
    gate.grant("discovery", "tune-recipe")
    audit = presence.audit()
    assert audit["surfaces"] == list(SURFACES)
    assert any(g["action"] == "tune-recipe" for g in audit["grants"])


def test_surface_bus_subscribe_and_emit(gate):
    bus = SurfaceBus(gate)
    seen = []
    bus.subscribe("feed", lambda event, payload: seen.append((event, payload)))
    bus.emit("feed", "new-post", {"id": "p1"})
    assert seen == [("new-post", {"id": "p1"})]


def test_surface_bus_rejects_unknown_surface(gate):
    bus = SurfaceBus(gate)
    with pytest.raises(UnknownSurface):
        bus.subscribe("void", lambda e, p: None)


# -- the front door: ask with ternary visibility ---------------------------


def test_ask_visibility_is_ternary():
    assert set(ASK_VISIBILITY) == {"public", "community", "just-me"}


def test_ask_defaults_to_just_me():
    result = ask("help me write a bio")
    assert result["visibility"] == "just-me"
    assert result["advisory"] is True
    assert result["tab"] == "levi"


def test_ask_accepts_all_three_states():
    for visibility in ASK_VISIBILITY:
        assert ask("q q q", visibility=visibility)["visibility"] == visibility


def test_ask_rejects_binary_only_visibility():
    with pytest.raises(ValueError):
        ask("help me write a bio", visibility="private")  # not silently coerced


def test_ask_rejects_empty_question():
    with pytest.raises(ValueError):
        ask("   ")


# -- tab HTML: safe by construction ------------------------------------------


def test_render_tab_escapes_user_content():
    # The renderer takes no user content, but the fragment must carry no
    # script and must use theme variables (theming THROUGHOUT).
    html = render_tab_html()
    assert "<script" not in html.lower()
    assert "var(--hub-bg)" in html
    assert 'id="tab-levi"' in html


def test_render_tab_uses_active_theme_css():
    from levi.hub import themes

    css = themes.css_variables(themes.paper_pack())
    html = render_tab_html(pack_css=css)
    assert "--hub-bg:#ffffff" in html  # paper pack visible in the LEVI tab
