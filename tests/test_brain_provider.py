"""Hermetic tests for levi.agent.brain_provider (the ``levi-brain`` provider).

LEVI's native brain: trained from scratch on LEVI's own corpus — no
LLaMA weights, no llama.cpp. Tests cover availability gating, honest
fallback, prompt building, and (when torch is importable) end-to-end
generation from a synthetic toy checkpoint.
"""

import pytest

from levi.agent.brain_provider import NativeBrainProvider, weights_path
from levi.agent.providers import ChatMessage, LocalProvider, select_provider


def _msg(role, content):
    return ChatMessage(role=role, content=content)


# ---------------------------------------------------------------------------
# Availability gating
# ---------------------------------------------------------------------------


def test_weights_path_default_points_at_brain_weights():
    p = weights_path()
    assert p.name == "tiny-gpt.pt"
    assert "brain" in p.parts and "weights" in p.parts


def test_weights_path_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_BRAIN_WEIGHTS", str(tmp_path / "custom.pt"))
    assert weights_path() == tmp_path / "custom.pt"


def test_unavailable_without_weights(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_BRAIN_WEIGHTS", str(tmp_path / "missing.pt"))
    p = NativeBrainProvider()
    assert not p.is_available()
    st = p.status()
    assert st["available"] is False
    assert st["weights_present"] is False


def test_chat_without_weights_returns_honest_error(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_BRAIN_WEIGHTS", str(tmp_path / "missing.pt"))
    p = NativeBrainProvider()
    resp = p.chat([_msg("user", "hello")], [])
    assert resp.provider == "levi-brain"
    assert resp.error is not None
    assert resp.text == ""


# ---------------------------------------------------------------------------
# Selection chain: levi-brain is explicit-only, never automatic
# ---------------------------------------------------------------------------


def test_select_explicit_brain_unavailable_falls_back(monkeypatch, tmp_path):
    monkeypatch.delenv("LEVI_PROVIDER", raising=False)
    monkeypatch.setenv("LEVI_BRAIN_WEIGHTS", str(tmp_path / "missing.pt"))
    p = select_provider("levi-brain")
    assert isinstance(p, LocalProvider)


def test_select_env_brain_unavailable_falls_back(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_PROVIDER", "levi-brain")
    monkeypatch.setenv("LEVI_BRAIN_WEIGHTS", str(tmp_path / "missing.pt"))
    p = select_provider()
    assert isinstance(p, LocalProvider)


def test_brain_never_wins_default_chain(monkeypatch, tmp_path):
    # Even if weights existed, the default chain stays rules-only.
    monkeypatch.delenv("LEVI_PROVIDER", raising=False)
    p = select_provider()
    assert isinstance(p, LocalProvider)


# ---------------------------------------------------------------------------
# Prompt building (pure, no torch)
# ---------------------------------------------------------------------------


def test_prompt_renders_conversation():
    p = NativeBrainProvider()
    prompt = p._prompt(
        [
            _msg("system", "You are Levi."),
            _msg("user", "what is 2+2"),
            _msg("assistant", "four"),
            _msg("user", "and 3+3"),
        ]
    )
    assert "You are Levi." in prompt
    assert "user: what is 2+2" in prompt
    assert "assistant: four" in prompt
    assert prompt.rstrip().endswith("assistant:")


def test_prompt_empty_messages_seeds_brain():
    p = NativeBrainProvider()
    assert p._prompt([]).strip().startswith("Levi")


# ---------------------------------------------------------------------------
# End-to-end generation from a synthetic toy checkpoint (needs torch)
# ---------------------------------------------------------------------------


def _toy_checkpoint(path):
    torch = pytest.importorskip("torch")
    from levi.brain.train.train import TinyGPT

    chars = list("abcdefghij \n")
    model = TinyGPT(len(chars), n_layer=1, n_head=2, n_embd=16, block_size=32)
    torch.save(
        {
            "chars": chars,
            "config": {
                "n_layer": 1,
                "n_head": 2,
                "n_embd": 16,
                "block_size": 32,
                "params": model.n_params(),
                "steps": 1,
                "corpus_chars": 100,
            },
            "model_state": model.state_dict(),
        },
        str(path),
    )


def test_chat_generates_from_toy_brain(monkeypatch, tmp_path):
    pytest.importorskip("torch")
    ckpt = tmp_path / "tiny-gpt.pt"
    _toy_checkpoint(ckpt)
    monkeypatch.setenv("LEVI_BRAIN_WEIGHTS", str(ckpt))
    p = NativeBrainProvider()
    assert p.is_available()
    resp = p.chat([_msg("user", "abc")], [])
    assert resp.error is None
    assert resp.provider == "levi-brain"
    assert resp.model == "tiny-gpt"
    assert isinstance(resp.text, str)


def test_select_explicit_brain_available(monkeypatch, tmp_path):
    pytest.importorskip("torch")
    ckpt = tmp_path / "tiny-gpt.pt"
    _toy_checkpoint(ckpt)
    monkeypatch.setenv("LEVI_BRAIN_WEIGHTS", str(ckpt))
    monkeypatch.delenv("LEVI_PROVIDER", raising=False)
    p = select_provider("levi-brain")
    assert isinstance(p, NativeBrainProvider)


def test_generate_validates_inputs_without_torch():
    """_generate validates n_chars/temperature before importing torch."""
    from levi.agent.brain_provider import NativeBrainProvider

    prov = NativeBrainProvider()
    with pytest.raises(ValueError, match="n_chars"):
        prov._generate("hello", n_chars=0)
    with pytest.raises(ValueError, match="n_chars"):
        prov._generate("hello", n_chars="many")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="temperature"):
        prov._generate("hello", temperature=0.0)
    with pytest.raises(ValueError, match="temperature"):
        prov._generate("hello", temperature=float("nan"))
    with pytest.raises(ValueError, match="temperature"):
        prov._generate("hello", temperature="hot")  # type: ignore[arg-type]


def test_chat_rejects_empty_messages():
    from levi.agent.brain_provider import NativeBrainProvider

    prov = NativeBrainProvider()
    with pytest.raises(ValueError, match="non-empty list"):
        prov.chat([], [])
