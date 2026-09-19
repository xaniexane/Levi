"""Plumbing tests for the Plaiground adult surface.

Hermetic: tmp home, never the real ``~/.levi``. Covers the creator,
simulator (Echoverse underneath, never merged), chat, and photo hooks —
plus invariants: no explicit presets ship with tone parameters, the
zones stay separate, and nothing in this package generates real images.
"""

from pathlib import Path

import pytest

from levi.plaiground import (
    ZONE,
    CLEAN_ZONE,
    chat,
    companions,
    gate,
    photos,
    simulator,
)
from levi.plaiground.gate import GateLockedError


@pytest.fixture()
def home(tmp_path):
    return tmp_path


@pytest.fixture()
def enabled(home):
    gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, home=home)
    return home


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in gate.MINOR_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# Zones stay separate
# ---------------------------------------------------------------------------


def test_zone_spelling_is_plaiground():
    assert ZONE == "plaiground"
    assert CLEAN_ZONE == "echoverse"


def test_no_third_zone_leaks_into_echo():
    # The Echoverse organ stays clean: importing it must not pull in
    # anything adult-side, and plaiground imports it only as an engine.
    import levi.organs.echo as echo

    assert not hasattr(echo, "plaiground")
    assert "plaiground" not in echo.run_echo.__module__


# ---------------------------------------------------------------------------
# Creator
# ---------------------------------------------------------------------------


def test_create_and_roundtrip(enabled):
    record = companions.create_companion(
        "Nova",
        traits=["curious", "dry-witted"],
        boundaries=["no spoilers past chapter one"],
        home=enabled,
    )
    assert record["name"] == "Nova"
    assert record["zone"] == "plaiground"
    loaded = companions.get_companion("Nova", home=enabled)
    assert loaded["traits"] == ["curious", "dry-witted"]
    assert loaded["boundaries"] == ["no spoilers past chapter one"]


def test_defaults_are_neutral(enabled):
    record = companions.create_companion("Ash", home=enabled)
    assert record["traits"] == ["steady"]
    assert record["boundaries"] == ["keep it respectful"]


def test_companion_file_is_owner_only(enabled):
    companions.create_companion("Ash", home=enabled)
    path = gate.gate_dir(enabled) / "companions" / "ash.json"
    assert path.stat().st_mode & 0o777 == 0o600


def test_create_validates_input(enabled):
    with pytest.raises(ValueError):
        companions.create_companion("", home=enabled)
    with pytest.raises(ValueError):
        companions.create_companion("x" * 100, home=enabled)
    with pytest.raises(ValueError):
        companions.create_companion("Nova\nInjected", home=enabled)
    with pytest.raises(ValueError):
        companions.create_companion("Nova", traits=["t"] * 25, home=enabled)


def test_get_missing_raises(enabled):
    with pytest.raises(KeyError):
        companions.get_companion("Nobody", home=enabled)


def test_delete(enabled):
    companions.create_companion("Ash", home=enabled)
    assert companions.delete_companion("Ash", home=enabled) is True
    assert companions.delete_companion("Ash", home=enabled) is False


# ---------------------------------------------------------------------------
# Simulator — Echoverse underneath, never merged
# ---------------------------------------------------------------------------


def test_simulator_uses_echo_engine(enabled):
    companions.create_companion("Nova", home=enabled)
    result = simulator.run_scenario(
        "Nova", "a quiet evening walk", cycles=2, home=enabled
    )
    assert result["zone"] == "plaiground"
    assert result["engine"] == "echoverse"
    assert result["companion"] == "Nova"
    kinds = [b["kind"] for b in result["beats"]]
    assert kinds == ["taken", "not_taken", "wild"]
    assert set(result) >= {
        "companion",
        "scenario",
        "beats",
        "insight",
        "boundaries",
    }


def test_simulator_is_deterministic(enabled):
    companions.create_companion("Nova", home=enabled)
    first = simulator.run_scenario("Nova", "the same walk", home=enabled)
    second = simulator.run_scenario("Nova", "the same walk", home=enabled)
    assert first["beats"] == second["beats"]


def test_simulator_honors_boundaries(enabled):
    companions.create_companion("Nova", boundaries=["no storms tonight"], home=enabled)
    result = simulator.run_scenario("Nova", "an evening walk", home=enabled)
    assert "no storms tonight" in result["boundaries"]


def test_simulator_validates_scenario(enabled):
    companions.create_companion("Nova", home=enabled)
    with pytest.raises(ValueError):
        simulator.run_scenario("Nova", "", home=enabled)
    with pytest.raises(ValueError):
        simulator.run_scenario("Nova", "x" * 2001, home=enabled)


def test_format_scenario(enabled):
    companions.create_companion("Nova", home=enabled)
    text = simulator.format_scenario(
        simulator.run_scenario("Nova", "a walk", home=enabled)
    )
    assert "Nova" in text and "[taken]" in text and "[wild]" in text


# ---------------------------------------------------------------------------
# Chat — tones stay non-explicit, allowlist enforced
# ---------------------------------------------------------------------------


def test_tones_have_no_explicit_presets():
    assert set(chat.TONES) == {
        "warm",
        "playful",
        "witty",
        "calm",
        "curious",
        "poetic",
        "grounded",
    }


def test_chat_rejects_unlisted_tone(enabled):
    companions.create_companion("Nova", home=enabled)
    with pytest.raises(ValueError):
        chat.ChatSession("Nova", tone="seductive", home=enabled)
    with pytest.raises(ValueError):
        chat.ChatSession("Nova", tone="", home=enabled)


def test_chat_session_roundtrip(enabled):
    companions.create_companion(
        "Nova", traits=["curious"], boundaries=["keep it light"], home=enabled
    )
    session = chat.ChatSession("Nova", tone="witty", home=enabled)
    reply = session.say("Tell me about the stars.")
    assert "Nova" in reply
    assert "witty" in reply and "curious" in reply
    assert "keep it light" in reply
    assert len(session.history()) == 2
    summary = session.close()
    assert summary["turns"] == 1 and summary["companion"] == "Nova"


def test_chat_is_deterministic_per_turn(enabled):
    companions.create_companion("Nova", home=enabled)
    first = chat.ChatSession("Nova", home=enabled).say("hello")
    second = chat.ChatSession("Nova", home=enabled).say("hello")
    assert first == second


def test_chat_validates_message(enabled):
    companions.create_companion("Nova", home=enabled)
    session = chat.ChatSession("Nova", home=enabled)
    with pytest.raises(ValueError):
        session.say("   ")
    with pytest.raises(ValueError):
        session.say("x" * 4001)


# ---------------------------------------------------------------------------
# Photos — contract only; procedural backend is honest art
# ---------------------------------------------------------------------------


def test_default_backend_is_procedural_only(enabled):
    assert photos.available_backends(enabled) == ["procedural"]


def test_request_photo_returns_metadata_not_bytes(enabled, tmp_path):
    result = photos.request_photo(
        "a moonlit lake",
        style="abstract",
        seed=7,
        width=32,
        height=32,
        save_dir=tmp_path,
        home=enabled,
    )
    assert isinstance(result, photos.PhotoResult)
    assert result.backend == "procedural"
    assert result.seed == 7
    assert result.width == 32 and result.height == 32
    assert "not photorealistic" in result.note
    assert result.path is not None and Path(result.path).is_file()


def test_request_photo_validates_prompt(enabled):
    with pytest.raises(ValueError):
        photos.request_photo("", home=enabled)
    with pytest.raises(KeyError):
        photos.request_photo("a lake", backend="photoreal-xl", home=enabled)


def test_register_backend_requires_contract_and_gate(enabled):
    class Bad:
        pass

    with pytest.raises(ValueError):
        photos.register_backend(Bad(), home=enabled)


def test_register_backend_gate_checked(home):
    class Stub:
        name = "stub"

        def generate(self, **kwargs):
            raise AssertionError("must not run while locked")

    with pytest.raises(GateLockedError):
        photos.register_backend(Stub())


def test_no_explicit_content_shipped_in_module_sources():
    # The package ships plumbing only: spot-check that the shipped sources
    # contain no explicit-content vocabulary.
    package = Path(__file__).resolve().parents[1] / "core" / "levi" / "plaiground"
    banned = ["porn", "xxx", "nsfw", "erotic", "fetish"]
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in text, "%s contains %r" % (path.name, word)
