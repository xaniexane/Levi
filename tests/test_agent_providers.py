"""Hermetic tests for core/levi/agent/providers.py — NO network.

urllib is monkeypatched for the HTTP providers; LocalProvider is pure
rule-based planning and needs no patching.
"""
import json
import urllib.error


from levi.agent.providers import (
    AnthropicProvider,
    ChatMessage,
    ChatProvider,
    ChatResponse,
    LocalProvider,
    OpenAICompatibleProvider,
    ProviderToolCall,
    provider_names,
    select_provider,
)

FILE_TOOLS = [
    {"name": "file_write", "description": "Write content to a file",
     "parameters": {"type": "object"}},
    {"name": "file_read", "description": "Read a file",
     "parameters": {"type": "object"}},
]


def scripted_conversation():
    """The canonical multi-step file task: create notes, write 3 lines, read back."""
    messages = [ChatMessage(role="user",
                            content="create notes.txt with three lines then read it back")]
    p = LocalProvider()

    r1 = p.chat(messages, FILE_TOOLS)
    messages.append(ChatMessage(role="assistant", content=r1.text,
                                tool_call_id=None))
    messages.append(ChatMessage(role="tool", name="file_write",
                                tool_call_id="local-1",
                                content="wrote 3 lines to notes.txt"))
    r2 = p.chat(messages, FILE_TOOLS)
    messages.append(ChatMessage(role="assistant", content=r2.text))
    messages.append(ChatMessage(role="tool", name="file_read",
                                tool_call_id="local-2",
                                content="Line 1\nLine 2\nLine 3"))
    r3 = p.chat(messages, FILE_TOOLS)
    return r1, r2, r3


def test_local_first_response_emits_file_write():
    r1, _, _ = scripted_conversation()
    assert len(r1.tool_calls) == 1
    call = r1.tool_calls[0]
    assert call.name == "file_write"
    assert call.arguments["path"] == "notes.txt"
    lines = call.arguments["content"].splitlines()
    assert len(lines) == 3


def test_local_second_step_emits_file_read():
    _, r2, _ = scripted_conversation()
    assert len(r2.tool_calls) == 1
    call = r2.tool_calls[0]
    assert call.name == "file_read"
    assert call.arguments["path"] == "notes.txt"


def test_local_final_text_no_tool_calls_mentions_completion():
    _, _, r3 = scripted_conversation()
    assert r3.tool_calls == []
    assert r3.error is None
    assert "read" in r3.text.lower() or "done" in r3.text.lower()


def test_local_deterministic_per_conversation():
    a = scripted_conversation()
    b = scripted_conversation()
    for ra, rb in zip(a, b, strict=True):
        assert ra.tool_calls == rb.tool_calls
        assert ra.text == rb.text
        assert ra.provider == rb.provider == "local"


def test_local_never_emits_unknown_tools():
    # Only file_read is offered; file_write is NOT — the planner must not
    # emit it even though the task wants a write first.
    messages = [ChatMessage(role="user",
                            content="create notes.txt with three lines then read it back")]
    r = LocalProvider().chat(messages, [FILE_TOOLS[1]])
    for call in r.tool_calls:
        assert call.name in {"file_read"}
    # With the needed tool missing it must say so honestly, not act.
    assert r.tool_calls == []
    assert "file_write" in r.text


def test_local_empty_tools_list_never_emits_calls():
    messages = [ChatMessage(role="user", content="create notes.txt")]
    r = LocalProvider().chat(messages, [])
    assert r.tool_calls == []
    assert r.text  # honest explanation, not silence


def test_local_unclear_task_asks_for_clarification():
    messages = [ChatMessage(role="user", content="do the thing with the stuff")]
    r = LocalProvider().chat(messages, FILE_TOOLS)
    assert r.tool_calls == []
    assert r.text  # must ask for clarification, not hallucinate work


def test_local_is_always_available():
    assert LocalProvider().is_available() is True


def test_local_memory_intent():
    messages = [ChatMessage(role="user",
                            content="remember that the deploy key is at ~/.ssh/deploy")]
    r = LocalProvider().chat(messages, [
        {"name": "memory_write", "description": "Save a note",
         "parameters": {"type": "object"}}])
    assert len(r.tool_calls) == 1
    assert r.tool_calls[0].name == "memory_write"
    assert "deploy" in r.tool_calls[0].arguments["text"]


def test_local_notes_file_without_extension():
    # "create a notes file, write three lines, read it back"
    messages = [ChatMessage(role="user",
                            content="create a notes file, write three lines, read it back")]
    r1 = LocalProvider().chat(messages, FILE_TOOLS)
    assert r1.tool_calls and r1.tool_calls[0].name == "file_write"
    assert r1.tool_calls[0].arguments["path"] == "notes.txt"


# ---------------------------------------------------------------------------
# Fake urlopen plumbing
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, payload: bytes, status: int = 200):
        self._payload = payload
        self.status = status

    def getcode(self):
        return self.status

    def read(self):
        return self._payload

    def close(self):
        pass


def patch_urlopen(monkeypatch, responder):
    monkeypatch.setattr("urllib.request.urlopen", responder)


OPENAI_TOOL_CALL_JSON = json.dumps({
    "id": "chatcmpl-x",
    "model": "gpt-4o-mini",
    "choices": [{
        "message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "file_read",
                             "arguments": '{"path": "notes.txt"}'},
            }],
        },
        "finish_reason": "tool_calls",
    }],
    "usage": {},
}).encode("utf-8")


def test_openai_parses_tool_call(monkeypatch):
    monkeypatch.setenv("LEVI_OPENAI_API_KEY", "sk-test")
    captured = {}

    def fake(req, timeout=None):
        captured["url"] = req.full_url
        captured["auth"] = req.headers.get("Authorization")
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse(OPENAI_TOOL_CALL_JSON)

    patch_urlopen(monkeypatch, fake)
    r = OpenAICompatibleProvider().chat(
        [ChatMessage(role="user", content="read notes.txt")], FILE_TOOLS)

    assert r.error is None
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-test"
    fns = {f["function"]["name"]: f["function"] for f in captured["body"]["tools"]}
    assert fns["file_read"]["name"] == "file_read"
    assert r.text == ""
    assert len(r.tool_calls) == 1
    call = r.tool_calls[0]
    assert isinstance(call, ProviderToolCall)
    assert call.id == "call_1"
    assert call.name == "file_read"
    assert call.arguments == {"path": "notes.txt"}
    assert r.provider == "openai"


def test_openai_tool_result_message_roundtrip(monkeypatch):
    monkeypatch.setenv("LEVI_OPENAI_API_KEY", "sk-test")
    captured = {}

    def fake(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse(json.dumps({
            "choices": [{"message": {"role": "assistant",
                                    "content": "All done."}}],
        }).encode("utf-8"))

    patch_urlopen(monkeypatch, fake)
    r = OpenAICompatibleProvider().chat([
        ChatMessage(role="user", content="read notes.txt"),
        ChatMessage(role="tool", name="file_read", tool_call_id="call_1",
                    content="Line 1"),
    ], FILE_TOOLS)
    assert r.error is None
    assert r.text == "All done."
    tool_msg = captured["body"]["messages"][-1]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call_1"


def test_openai_network_error_surfaced_not_raised(monkeypatch):
    monkeypatch.setenv("LEVI_OPENAI_API_KEY", "sk-test")

    def fake(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    patch_urlopen(monkeypatch, fake)
    r = OpenAICompatibleProvider().chat(
        [ChatMessage(role="user", content="hi")], [])
    assert r.tool_calls == []
    assert r.error is not None
    assert "connection refused" in r.error


def test_openai_http_error_surfaced(monkeypatch):
    monkeypatch.setenv("LEVI_OPENAI_API_KEY", "sk-bad")

    def fake(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized",
                                     {}, None)

    patch_urlopen(monkeypatch, fake)
    r = OpenAICompatibleProvider().chat(
        [ChatMessage(role="user", content="hi")], [])
    assert r.error is not None
    assert "401" in r.error


def test_openai_base_url_override_needs_no_key(monkeypatch):
    monkeypatch.delenv("LEVI_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LEVI_OPENAI_BASE_URL", raising=False)
    assert OpenAICompatibleProvider().is_available() is False
    monkeypatch.setenv("LEVI_OPENAI_BASE_URL", "http://localhost:11434/v1")
    assert OpenAICompatibleProvider().is_available() is True


def test_openai_base_url_override_used(monkeypatch):
    monkeypatch.delenv("LEVI_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LEVI_OPENAI_BASE_URL", "http://localhost:11434/v1")
    captured = {}

    def fake(req, timeout=None):
        captured["url"] = req.full_url
        return FakeResponse(json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
        }).encode("utf-8"))

    patch_urlopen(monkeypatch, fake)
    r = OpenAICompatibleProvider().chat(
        [ChatMessage(role="user", content="hi")], [])
    assert r.error is None
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"


ANTHROPIC_TOOL_USE_JSON = json.dumps({
    "id": "msg_1",
    "type": "message",
    "model": "claude-sonnet-4-20250514",
    "content": [
        {"type": "text", "text": "I'll read it."},
        {"type": "tool_use", "id": "toolu_1", "name": "file_read",
         "input": {"path": "notes.txt"}},
    ],
    "stop_reason": "tool_use",
}).encode("utf-8")


def test_anthropic_parses_tool_use(monkeypatch):
    monkeypatch.setenv("LEVI_ANTHROPIC_API_KEY", "sk-ant-test")
    captured = {}

    def fake(req, timeout=None):
        captured["headers"] = dict(req.headers)
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse(ANTHROPIC_TOOL_USE_JSON)

    patch_urlopen(monkeypatch, fake)
    r = AnthropicProvider().chat(
        [ChatMessage(role="system", content="You are LEVI."),
         ChatMessage(role="user", content="read notes.txt")], FILE_TOOLS)

    assert r.error is None
    assert r.text == "I'll read it."
    assert len(r.tool_calls) == 1
    call = r.tool_calls[0]
    assert call.id == "toolu_1"
    assert call.name == "file_read"
    assert call.arguments == {"path": "notes.txt"}
    assert r.provider == "anthropic"
    # request shape
    assert captured["body"]["model"] == "claude-sonnet-4-20250514"
    assert captured["body"]["system"] == "You are LEVI."
    tools_by_name = {t["name"]: t for t in captured["body"]["tools"]}
    assert tools_by_name["file_read"]["name"] == "file_read"
    assert "input_schema" in tools_by_name["file_read"]
    hdrs = {k.lower(): v for k, v in captured["headers"].items()}
    assert hdrs.get("anthropic-version") == "2023-06-01"
    assert hdrs.get("x-api-key") == "sk-ant-test"


def test_anthropic_network_error_surfaced_not_raised(monkeypatch):
    monkeypatch.setenv("LEVI_ANTHROPIC_API_KEY", "sk-ant-test")

    def fake(req, timeout=None):
        raise urllib.error.URLError("dns failure")

    patch_urlopen(monkeypatch, fake)
    r = AnthropicProvider().chat([ChatMessage(role="user", content="hi")], [])
    assert r.tool_calls == []
    assert r.error is not None
    assert "dns failure" in r.error


def test_anthropic_missing_key_not_available_and_honest_error(monkeypatch):
    monkeypatch.delenv("LEVI_ANTHROPIC_API_KEY", raising=False)
    assert AnthropicProvider().is_available() is False
    r = AnthropicProvider().chat([ChatMessage(role="user", content="hi")], [])
    assert r.error is not None
    assert "LEVI_ANTHROPIC_API_KEY" in r.error


def test_anthropic_available_with_key(monkeypatch):
    monkeypatch.setenv("LEVI_ANTHROPIC_API_KEY", "sk-ant-test")
    assert AnthropicProvider().is_available() is True


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def test_provider_names():
    assert provider_names() == [
        "levi-tiny", "levi-0.6b", "levi-4b",
        "local", "levi-brain", "levi-local", "openai", "anthropic",
    ]


def test_select_default_is_local(monkeypatch, tmp_path):
    # The default chain is LEVI-first: with no family weight downloaded
    # and no native-brain weights, it falls back to the rules planner.
    monkeypatch.delenv("LEVI_PROVIDER", raising=False)
    monkeypatch.delenv("LEVI_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LEVI_OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("LEVI_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("LEVI_BRAIN_WEIGHTS", str(tmp_path / "no-weights.pt"))
    monkeypatch.setenv("LEVI_MODEL_DIR", str(tmp_path / "empty-models"))
    p = select_provider()
    assert isinstance(p, LocalProvider)


def test_select_flag_wins_over_env(monkeypatch):
    monkeypatch.setenv("LEVI_PROVIDER", "anthropic")
    monkeypatch.setenv("LEVI_ANTHROPIC_API_KEY", "sk-ant-test")
    p = select_provider("local")
    assert isinstance(p, LocalProvider)


def test_select_env_wins_over_default(monkeypatch):
    monkeypatch.setenv("LEVI_PROVIDER", "anthropic")
    monkeypatch.setenv("LEVI_ANTHROPIC_API_KEY", "sk-ant-test")
    p = select_provider()
    assert isinstance(p, AnthropicProvider)


def test_select_unavailable_preferred_falls_back_to_local(monkeypatch, tmp_path):
    monkeypatch.delenv("LEVI_PROVIDER", raising=False)
    monkeypatch.delenv("LEVI_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("LEVI_MODEL_DIR", str(tmp_path / "empty-models"))
    p = select_provider("anthropic")
    assert isinstance(p, LocalProvider)
    monkeypatch.setenv("LEVI_PROVIDER", "openai")
    monkeypatch.delenv("LEVI_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LEVI_OPENAI_BASE_URL", raising=False)
    p = select_provider()
    assert isinstance(p, LocalProvider)


def test_select_unknown_name_falls_back_to_local(monkeypatch):
    monkeypatch.delenv("LEVI_PROVIDER", raising=False)
    assert isinstance(select_provider("bogus"), LocalProvider)


def test_contract_shape():
    assert issubclass(LocalProvider, ChatProvider)
    assert issubclass(OpenAICompatibleProvider, ChatProvider)
    assert issubclass(AnthropicProvider, ChatProvider)
    r = ChatResponse()
    assert r.text == "" and r.tool_calls == [] and r.error is None
