"""Tests for the Turn Packet (levi.agent.context_packet): deterministic,
budgeted, manifest-bearing Minimal Sufficient Context."""

from levi.agent import context_packet as cp


def _sources(**over):
    base = {
        "oath": cp.OATH_LINE,
        "task": "summarize the quarterly report",
        "receipts": "turn: provider=local status=ok steps=3",
        "summary": "Earlier: the user asked about revenue.",
        "recent": "user: what about Q3?\nassistant: Q3 was flat.",
        "facts": "[2026-09-16] user prefers terse answers",
        "growth": "advisory: keep answers short",
        "tools": "memory_read: read scratch\nmemory_write: write scratch",
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# build_packet
# ---------------------------------------------------------------------------


def test_all_fit_all_included():
    p = cp.build_packet(_sources())
    by_name = {s.name: s for s in p.sections}
    assert all(s.status == "included" for s in p.sections)
    assert p.used_chars <= p.budget_chars
    assert by_name["oath"].content == cp.OATH_LINE


def test_tiny_budget_excludes_late_sections_with_reason():
    p = cp.build_packet(_sources(), budget_chars=300)
    by_name = {s.name: s for s in p.sections}
    # oath + task always win the budget race
    assert by_name["oath"].status == "included"
    assert by_name["task"].status == "included"
    excluded = [s for s in p.sections if s.status == "excluded"]
    assert excluded, "something must give under a 300-char budget"
    assert all(s.reason for s in excluded)
    assert any(
        "budget exhausted" in s.reason or "chars left" in s.reason for s in excluded
    )
    # manifest says so too — nothing cut silently
    manifest_names = {s["name"]: s for s in p.manifest()["sections"]}
    assert manifest_names["tools"]["status"] == "excluded"


def test_over_cap_section_truncated_and_marked():
    p = cp.build_packet(_sources(recent="x" * 9000))
    by_name = {s.name: s for s in p.sections}
    recent = by_name["recent"]
    assert recent.status == "truncated"
    assert "cut" in recent.content  # the marker rides the content
    assert "cut" in recent.reason
    assert p.used_chars <= p.budget_chars


def test_truncation_marker_count_is_honest():
    text, cut = cp._truncate("x" * 9000, 4000)
    assert len(text) == 4000
    assert cut == 9000 - (4000 - len(cp.CUT_MARKER.format(n=cut)))
    assert f"cut {cut} chars" in text


def test_empty_source_excluded_as_empty():
    p = cp.build_packet(_sources(growth="", facts=""))
    by_name = {s.name: s for s in p.sections}
    assert by_name["growth"].status == "excluded"
    assert by_name["growth"].reason == "empty"


def test_digest_deterministic_and_sensitive():
    a = cp.build_packet(_sources())
    b = cp.build_packet(_sources())
    c = cp.build_packet(_sources(task="something else entirely"))
    assert a.digest() == b.digest()
    assert a.digest() != c.digest()
    assert len(a.digest()) == 64


def test_render_contains_manifest():
    text = cp.build_packet(_sources()).render()
    assert "TURN PACKET" in text
    assert "[§oath" in text
    assert "─── manifest ───" in text
    assert "digest sha256:" in text


# ---------------------------------------------------------------------------
# packet_for_conversation
# ---------------------------------------------------------------------------


def test_packet_for_conversation(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(tmp_path))
    monkeypatch.setenv("LEVI_PROVIDER", "local")
    from levi.agent.chat import ConversationManager

    conv = ConversationManager(session_name="packet-test", provider="local")
    conv.session.append_message("user", "hello levi")
    conv.session.append_message("assistant", "hello chauncey")
    conv.session.append_turn_meta(provider="local", ok=True, steps=2)

    packet = cp.packet_for_conversation(conv, task="greet the user")
    by_name = {s.name: s for s in packet.sections}
    assert by_name["oath"].status == "included"
    assert "greet the user" in by_name["task"].content
    assert "hello levi" in by_name["recent"].content
    assert "provider=local" in by_name["receipts"].content
    # tools inventory present and bounded
    assert by_name["tools"].status in ("included", "truncated")
    assert "memory_read" in by_name["tools"].content
    # manifest is complete and honest
    manifest = packet.manifest()
    assert manifest["used_chars"] <= manifest["budget_chars"]
    assert {s["name"] for s in manifest["sections"]} == {
        name for name, _, _ in cp.SECTION_SPECS
    }


def test_packet_for_conversation_tiny_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(tmp_path))
    monkeypatch.setenv("LEVI_PROVIDER", "local")
    from levi.agent.chat import ConversationManager

    conv = ConversationManager(session_name="packet-tiny", provider="local")
    conv.session.append_message("user", "hi")
    packet = cp.packet_for_conversation(conv, task="say hi", budget_chars=200)
    assert packet.used_chars <= 200
    assert any(s.status == "excluded" for s in packet.sections)
