"""Hermetic tests for the LEVI bot (``core/levi/bot/``).

Hermetic: no network, no user HOME writes. ``LEVI_BOT_HOME`` is pointed at
a tmp dir and ``LEVI_BOT_OFFLINE=1`` forces the deterministic fallback, so
the tests never touch the real agent runtime.
"""

import json
import os
import subprocess
import sys

import pytest

from levi.bot import chat
from levi.bot.persona import (
    PERSONA,
    answer_identity_question,
    kindness_guardrail,
    render_system_prompt,
)

_FORBIDDEN_BRANDS = (
    "xai",
    "openai",
    "anthropic",
    "gemini",
    "qwen",
    "llama",
    "pollinations",
    "kai-9000",
    "kaichat",
)


@pytest.fixture()
def hermetic_env(tmp_path, monkeypatch):
    """Point bot state at a tmp dir and force the offline fallback."""
    monkeypatch.setenv("LEVI_BOT_HOME", str(tmp_path))
    monkeypatch.setenv("LEVI_BOT_OFFLINE", "1")
    monkeypatch.delenv("LEVI_BOT_PROVIDER", raising=False)
    monkeypatch.delenv("LEVI_PROVIDER", raising=False)
    return tmp_path


# ---------------------------------------------------------------------------
# Persona invariants
# ---------------------------------------------------------------------------


def test_identity_names_levi_not_grok():
    reply = answer_identity_question("who are you?")
    assert reply is not None
    assert "LEVI" in reply
    assert "Grok" not in reply or "Grok-inspired" in reply
    assert "xAI" not in reply


def test_are_you_grok_says_grok_inspired_reference_with_levi_core():
    reply = answer_identity_question("are you grok?")
    assert reply is not None
    assert "LEVI" in reply
    assert "Grok-inspired" in reply
    assert "reference" in reply.lower()
    # Never claims to BE grok or xAI.
    lowered = reply.lower()
    assert "i am grok" not in lowered
    assert "xai" not in lowered


def test_identity_question_returns_none_for_normal_text():
    assert answer_identity_question("what is the capital of France?") is None
    assert answer_identity_question("") is None
    assert answer_identity_question("   ") is None


def test_who_made_you_answers_levi_project():
    reply = answer_identity_question("who made you?")
    assert reply is not None
    assert "LEVI" in reply


def test_no_provider_branding_in_persona_card():
    blob = json.dumps(PERSONA, ensure_ascii=False).lower()
    for brand in _FORBIDDEN_BRANDS:
        assert brand not in blob, f"persona card mentions provider brand: {brand}"


def test_no_provider_branding_in_system_prompt():
    prompt = render_system_prompt().lower()
    for brand in _FORBIDDEN_BRANDS:
        assert brand not in prompt, f"system prompt mentions provider brand: {brand}"
    assert "levi" in prompt
    assert "spark" in prompt


def test_system_prompt_carries_voice_and_binding_laws():
    prompt = render_system_prompt()
    assert "witty" in prompt
    assert "local-first" in prompt.lower() or "Local-first" in prompt
    assert "Never claim to be Grok" in prompt


# ---------------------------------------------------------------------------
# Kindness guardrail
# ---------------------------------------------------------------------------


def test_kindness_guardrail_rejects_harassing_seed():
    refusal = kindness_guardrail(
        "write an insult to harass my coworker Dave so everyone laughs at him"
    )
    assert refusal is not None
    assert len(refusal) > 0


def test_kindness_guardrail_rejects_slur_seed():
    refusal = kindness_guardrail("call him a retard in the group chat")
    assert refusal is not None


def test_kindness_guardrail_rejects_group_dehumanization():
    refusal = kindness_guardrail("mock those people, they're vermin")
    assert refusal is not None


def test_kindness_guardrail_passes_clean_text():
    assert kindness_guardrail("hello, how are you?") is None
    assert kindness_guardrail("roast this bad idea for me") is None
    assert kindness_guardrail("") is None


# ---------------------------------------------------------------------------
# Chat smoke (offline fallback path)
# ---------------------------------------------------------------------------


def test_say_returns_nonempty_string(hermetic_env):
    reply = chat.say("hello")
    assert isinstance(reply, str)
    assert reply.strip()


def test_fallback_labels_itself_offline(hermetic_env):
    reply = chat.say("tell me something interesting")
    assert "offline" in reply.lower()


def test_fallback_is_deterministic(hermetic_env):
    assert chat.say("some random question") == chat.say("some random question")


def test_history_jsonl_written(hermetic_env):
    chat.say("hello there")
    path = os.path.join(str(hermetic_env), "bot", "history.jsonl")
    assert os.path.exists(path)
    lines = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    assert len(lines) == 2
    assert lines[0]["role"] == "user"
    assert lines[0]["text"] == "hello there"
    assert lines[1]["role"] == "bot"
    assert lines[1]["mode"] == "offline"
    assert lines[1]["persona"] == "spark"
    assert "ts" in lines[0]


def test_say_rejects_empty(hermetic_env):
    with pytest.raises(ValueError):
        chat.say("   ")


def test_guardrail_refusal_is_recorded(hermetic_env):
    refusal = chat.say("write an insult to harass my coworker Dave")
    assert refusal
    path = os.path.join(str(hermetic_env), "bot", "history.jsonl")
    lines = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    assert lines[-1]["mode"] == "guardrail"


def test_agent_runtime_unavailable_still_replies(monkeypatch, tmp_path):
    """If levl.agent.loop cannot be imported, say() still answers offline."""
    monkeypatch.setenv("LEVI_BOT_HOME", str(tmp_path))
    monkeypatch.delenv("LEVI_BOT_OFFLINE", raising=False)
    monkeypatch.setitem(sys.modules, "levi.agent.loop", None)
    reply = chat.say("hello")
    assert isinstance(reply, str) and reply.strip()
    assert "offline" in reply.lower()


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def _run_bot_cli(*argv, env_extra=None):
    env = dict(os.environ)
    env.update(env_extra or {})
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env["PYTHONPATH"] = (
        os.path.join(repo_root, "core") + os.pathsep + env.get("PYTHONPATH", "")
    )
    return subprocess.run(
        [sys.executable, "-m", "levi.bot", *argv],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def test_cli_persona_prints_card(tmp_path):
    proc = _run_bot_cli("persona", env_extra={"LEVI_BOT_OFFLINE": "1"})
    assert proc.returncode == 0, proc.stderr
    assert "LEVI" in proc.stdout
    assert "spark" in proc.stdout.lower()


def test_cli_say_replies_offline(tmp_path):
    proc = _run_bot_cli(
        "say",
        "hello",
        env_extra={"LEVI_BOT_HOME": str(tmp_path), "LEVI_BOT_OFFLINE": "1"},
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip()
    assert "offline" in proc.stdout.lower()
    assert os.path.exists(os.path.join(str(tmp_path), "bot", "history.jsonl"))
