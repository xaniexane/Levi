"""Hermetic tests for levi.i18n (multilingual support, stdlib-only)."""

from __future__ import annotations

import pytest

from levi import i18n
from levi.i18n import (
    catalog_coverage,
    detect,
    language_name,
    normalize,
    reply_directive,
    t,
)


def test_supported_covers_major_languages():
    for code in ("en", "es", "fr", "de", "pt", "zh", "ja", "ar", "hi", "ru"):
        assert code in i18n.SUPPORTED


def test_normalize():
    assert normalize("es-MX") == "es"
    assert normalize("pt_BR") == "pt"
    assert normalize("ES") == "es"
    assert normalize("xx") == "en"
    assert normalize("") == "en"
    assert normalize(None) == "en"


def test_language_name():
    assert language_name("es") == "Spanish"
    assert language_name("ja") == "Japanese"
    assert language_name("xx") == "English"


def test_t_translated_and_fallback():
    assert t("greeting", "es").startswith("Hola")
    assert t("greeting", "fr").startswith("Salut")
    assert t("done", "de") == "Fertig."
    # Japanese has no deterministic catalog: honest English fallback
    assert t("greeting", "ja") == t("greeting", "en")
    assert t("done", "ru") == "Done."
    # formatting still works through fallback
    assert "X" in t("confirm_prompt", "ja", preview="X")
    # unknown key returns the key itself, never raises
    assert t("no_such_key", "es") == "no_such_key"
    # missing kwarg never raises
    assert isinstance(t("confirm_prompt", "es"), str)


def test_catalog_coverage_is_honest():
    cov = catalog_coverage()
    total = len(i18n._CATALOG)
    assert total > 0
    for lang in i18n.CATALOG_LANGS:
        assert cov[lang] == total
    for lang in ("zh", "ja", "ar", "hi", "ru", "it", "nl"):
        assert cov[lang] == 0


def test_detect_scripts():
    assert detect("こんにちは、元気ですか") == "ja"
    assert detect("你好，世界") == "zh"
    assert detect("مرحبا بالعالم") == "ar"
    assert detect("Привет, мир") == "ru"
    assert detect("नमस्ते दुनिया") == "hi"


def test_detect_stopwords():
    assert detect("el gato está en la casa y no quiere salir") == "es"
    assert detect("le chat est dans la maison et ne veut pas sortir") == "fr"
    assert detect("der Hund ist nicht in dem Haus") == "de"
    assert detect("o gato está em casa e não quer sair") == "pt"
    assert detect("the cat is in the house and does not want to leave") == "en"


def test_detect_fallbacks():
    assert detect("") == "en"
    assert detect(None) == "en"
    assert detect("12345 !!!") == "en"


def test_reply_directive():
    assert reply_directive("en") == ""
    assert reply_directive(None) == ""
    d = reply_directive("es")
    assert "Spanish" in d and "es" in d
    assert reply_directive("xx") == ""  # unknown → English → empty


def test_run_subtask_language_validation(tmp_path):
    from levi.agent.loop import run_subtask

    with pytest.raises(ValueError, match="language"):
        run_subtask("hi", language=123)  # type: ignore[arg-type]


def test_run_subtask_language_directive_reaches_provider(tmp_path):
    from levi.agent.loop import run_subtask
    from levi.agent.providers import ChatProvider, ChatResponse
    from levi.agent.tools import build_default_registry

    seen = {}

    class FakeProvider(ChatProvider):
        name = "fake"

        def is_available(self):
            return True

        def chat(self, messages, tools):
            seen["system"] = messages[0].content
            return ChatResponse(text="listo", model="fake", provider="fake")

    reg = build_default_registry(
        workspace_root=tmp_path / "ws",
        memory_dir=tmp_path / "mem",
        skills_dir=tmp_path / "skills",
    )
    out = run_subtask("hola", provider=FakeProvider(), registry=reg, language="es")
    assert out.ok is True
    assert "Spanish" in seen["system"]

    out_en = run_subtask("hi", provider=FakeProvider(), registry=reg, language="en")
    assert "Spanish" not in seen["system"]
    assert out_en.ok is True


def test_conversation_manager_carries_language(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from levi.agent.chat import ConversationManager

    mgr = ConversationManager("test-lang", language="pt")
    assert mgr.language == "pt"
    mgr2 = ConversationManager("test-lang-2")
    assert mgr2.language is None


def test_effective_language_explicit_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from levi.agent.chat import ConversationManager

    mgr = ConversationManager("test-eff-1", language="fr")
    # even a clearly Spanish message stays French when explicitly set
    assert mgr._effective_language("el gato está en la casa") == "fr"


def test_effective_language_detects_per_message(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from levi.agent.chat import ConversationManager

    mgr = ConversationManager("test-eff-2")
    assert mgr._effective_language("el gato está en la casa y no quiere salir") == "es"
    assert mgr._effective_language("the cat is in the house") == "en"
    assert mgr._effective_language("こんにちは、元気ですか") == "ja"
