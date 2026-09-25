"""LEVI register grounding: runtime --register wiring + identity corpus.

Covers the Phase-2 LEVI addition:
- bad --register id exits 2 and lists the valid ids
- system_for() content actually reaches the provider as the system message
  (both run_subtask and the chat ConversationManager paths)
- prepare_corpus emits exactly 14 identity records (LEVI-original registers)
"""

import subprocess
import sys
from pathlib import Path


from levi.persona.levi import all_variants, get, system_for
from levi.agent.providers import ChatProvider, ChatMessage, ChatResponse


REPO = Path(__file__).resolve().parent.parent
VALID_IDS = [v.id for v in all_variants()]


class CaptureProvider(ChatProvider):
    """Fake provider that records messages and answers without tools."""

    name = "capture"

    def __init__(self):
        self.seen: list[list[ChatMessage]] = []

    def is_available(self) -> bool:
        return True

    def chat(self, messages: list[ChatMessage], tools: list[dict]) -> ChatResponse:
        self.seen.append(list(messages))
        return ChatResponse(text="done", model="capture", provider="capture")


def _system_text(messages: list[ChatMessage]) -> str:
    for m in messages:
        if m.role == "system":
            return m.content
    return ""


def test_fourteen_registers():
    assert len(all_variants()) == 14
    assert set(VALID_IDS) == {
        "levi",
        "levi_care",
        "levi_ops",
        "levi_challenger",
        "levi_literary",
        "levi_forensic",
        "levi_void",
        "levi_builder",
        "levi_mirror",
        "levi_architect",
        "levi_sentinel",
        "levi_oracle",
        "levi_companion",
        "levi_wit",
    }


def test_muse_system_block():
    text = system_for("levi_companion")
    assert "LEVI Companion" in text
    assert "companion register" in text
    assert get("levi_companion").intensity == 0.45


def test_grok_system_block():
    text = system_for("levi_wit")
    assert "wit register" in text
    assert "LEVI Wit" in text
    assert "Care register" in text
    assert get("levi_wit").intensity == 0.7


def test_get_unknown_returns_none():
    assert get("nope") is None
    assert get("levi_ops") is not None


def test_system_for_ops_content():
    text = system_for("levi_ops")
    assert "STATUS / RISK / DECISION" in text


def test_run_subtask_system_prompt_reaches_provider(tmp_path):
    from levi.agent.loop import run_subtask
    from levi.agent.tools import build_default_registry

    provider = CaptureProvider()
    registry = build_default_registry(workspace_root=tmp_path)
    system = system_for("levi_ops")
    run_subtask(
        "say hello",
        provider=provider,
        registry=registry,
        max_steps=1,
        system_prompt=system,
    )
    assert provider.seen, "provider was never called"
    assert system in _system_text(provider.seen[0])


def test_chat_manager_system_prompt_reaches_provider(tmp_path, monkeypatch):
    from levi.agent.chat import ConversationManager

    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(tmp_path / "sessions"))
    provider = CaptureProvider()
    mgr = ConversationManager(
        "kai-test",
        provider=provider,
        max_steps=1,
        system_prompt=system_for("levi_care"),
    )
    mgr.turn("hello")
    assert provider.seen, "provider was never called"
    first_system = _system_text(provider.seen[0])
    assert "LEVI Care" in first_system


def test_cli_bad_register_lists_valid_ids():
    cmd = [
        sys.executable,
        "-m",
        "levi.cli.main",
        "agent",
        "run",
        "--register",
        "nope",
        "hi",
    ]
    p = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(REPO / "core")},
    )
    assert p.returncode == 2, p.stderr[:300]
    for vid in ("levi", "levi_ops", "levi_oracle"):
        assert vid in p.stdout


def test_prepare_corpus_has_fourteen_identity_records(tmp_path):
    sys.path.insert(0, str(REPO / "core" / "levi" / "brain" / "train"))
    try:
        import prepare_corpus
    finally:
        sys.path.pop(0)
    recs = prepare_corpus.identity_records()
    assert len(recs) == 14
    ids = {r.get("register") for r in recs}
    assert "levi_companion" in ids
    assert "levi_wit" in ids
    for rec in recs:
        assert rec["kind"] == "identity"
        for marker in ("Register:", "Voice:", "Strengths:", "Never:", "System:"):
            assert marker in rec["text"], marker
    # full run on an empty fixture dir still yields exactly the 14
    out = tmp_path / "out"
    old_raw, old_briefs = prepare_corpus.RAW, prepare_corpus.BRIEFS
    prepare_corpus.RAW = tmp_path / "noraw"
    prepare_corpus.BRIEFS = tmp_path / "nobriefs"
    try:
        prepare_corpus.main(["--out", str(out)])
    finally:
        prepare_corpus.RAW, prepare_corpus.BRIEFS = old_raw, old_briefs
    stats = __import__("json").loads((out / "corpus_stats.json").read_text())
    assert stats["identity_records"] == 14
    assert stats["chunks"] == 14
