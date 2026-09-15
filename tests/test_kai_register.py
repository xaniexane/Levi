"""KAI-9000 register grounding: runtime --register wiring + identity corpus.

Covers the Phase-2 KAI-9000 addition:
- bad --register id exits 2 and lists the valid ids
- system_for() content actually reaches the provider as the system message
  (both run_subtask and the chat ConversationManager paths)
- prepare_corpus emits exactly 14 identity records (LEVI-original registers)
"""
import subprocess
import sys
from pathlib import Path


from levi.persona.kai9000 import all_variants, get, system_for
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
        "kai_9000", "kai_9000_care", "kai_9000_ops", "kai_9000_challenger",
        "kai_9000_literary", "kai_9000_forensic", "kai_9000_void",
        "kai_9000_builder", "kai_9000_mirror", "kai_9000_architect",
        "kai_9000_sentinel", "kai_9000_oracle",
        "kai_9000_muse", "kai_9000_grok",
    }


def test_muse_system_block():
    text = system_for("kai_9000_muse")
    assert "KAI-9000 Muse" in text
    assert "companion register" in text
    assert get("kai_9000_muse").intensity == 0.45


def test_grok_system_block():
    text = system_for("kai_9000_grok")
    assert "wit register" in text
    assert "KAI-9000 Grok" in text
    assert "Care register" in text
    assert get("kai_9000_grok").intensity == 0.7


def test_get_unknown_returns_none():
    assert get("nope") is None
    assert get("kai_9000_ops") is not None


def test_system_for_ops_content():
    text = system_for("kai_9000_ops")
    assert "STATUS / RISK / DECISION" in text


def test_run_subtask_system_prompt_reaches_provider(tmp_path):
    from levi.agent.loop import run_subtask
    from levi.agent.tools import build_default_registry

    provider = CaptureProvider()
    registry = build_default_registry(workspace_root=tmp_path)
    system = system_for("kai_9000_ops")
    run_subtask("say hello", provider=provider, registry=registry,
                max_steps=1, system_prompt=system)
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
        system_prompt=system_for("kai_9000_care"),
    )
    mgr.turn("hello")
    assert provider.seen, "provider was never called"
    first_system = _system_text(provider.seen[0])
    assert "KAI-9000 Care" in first_system


def test_cli_bad_register_lists_valid_ids():
    cmd = [sys.executable, "-m", "levi.cli.main",
           "agent", "run", "--register", "nope", "hi"]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO,
                       env={"PATH": "/usr/bin:/bin",
                            "PYTHONPATH": str(REPO / "core")})
    assert p.returncode == 2, p.stderr[:300]
    for vid in ("kai_9000", "kai_9000_ops", "kai_9000_oracle"):
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
    assert "kai_9000_muse" in ids
    assert "kai_9000_grok" in ids
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
