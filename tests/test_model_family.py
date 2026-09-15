"""LEVI-first model family: registry, resolution, and CLI.

Hermetic: fake HOME / LEVI_MODEL_DIR / LEVI_BRAIN_WEIGHTS everywhere;
no network, no real weights, no user-HOME writes. CLI tests run the
real ``python -m levi.cli.main`` subprocess with a scrubbed env.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from levi.agent import model_family
from levi.agent import local_model
from levi.agent.local_model import LocalModelProvider
from levi.agent.providers import (
    LocalProvider,
    provider_names,
    select_provider,
)
from levi.agent.brain_provider import NativeBrainProvider

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Registry: only real weights, honestly attributed
# ---------------------------------------------------------------------------


def test_family_seeds_only_real_entries():
    assert model_family.family_names() == ["levi-tiny", "levi-0.6b", "levi-4b"]
    tiny = model_family.get_entry("levi-tiny")
    assert tiny["kind"] == "native"
    assert tiny["base"] is None  # genuinely LEVI's — no upstream base
    for remix in ("levi-0.6b", "levi-4b"):
        entry = model_family.get_entry(remix)
        assert entry["kind"] == "remix"
        assert entry["packaged_by"] == "levi"
        assert entry["base"] in ("qwen3-0.6b", "qwen3-4b")  # honest base
        assert entry["local_key"] in local_model.MODELS  # real download spec


def test_unknown_entry_is_none():
    assert model_family.get_entry("levi-99b") is None
    with pytest.raises(KeyError):
        model_family.status("levi-99b")


def test_set_choice_unknown_raises():
    with pytest.raises(ValueError, match="unknown LEVI family member"):
        model_family.set_choice("levi-99b")


def test_register_remix_validates(monkeypatch):
    with pytest.raises(ValueError, match="unknown local_model key"):
        model_family.register_remix(
            "levi-bogus", base="x", version="1", local_key="no-such-key"
        )
    with pytest.raises(ValueError, match="new 'levi-\\*' name"):
        model_family.register_remix(
            "levi-0.6b", base="x", version="1", local_key="qwen3-0.6b"
        )
    with pytest.raises(ValueError, match="base must be a non-empty string"):
        model_family.register_remix(
            "levi-bogus", base="", version="1", local_key="qwen3-0.6b"
        )
    with pytest.raises(ValueError, match="version must be a non-empty string"):
        model_family.register_remix(
            "levi-bogus", base="qwen3-0.6b", version="  ", local_key="qwen3-0.6b"
        )
    entry = model_family.register_remix(
        "levi-test-remix",
        base="qwen3-0.6b",
        version="test/1",
        local_key="qwen3-0.6b",
        notes="test only",
    )
    try:
        assert entry["kind"] == "remix"
        assert entry["base"] == "qwen3-0.6b"
        assert "levi-test-remix" in model_family.family_names()
    finally:
        model_family._FAMILY.remove(entry)
    assert "levi-test-remix" not in model_family.family_names()


# ---------------------------------------------------------------------------
# Helpers: fake HOME + fake model dir
# ---------------------------------------------------------------------------


def _scrub_env(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LEVI_MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("LEVI_BRAIN_WEIGHTS", str(tmp_path / "no-weights.pt"))
    for key in (
        "LEVI_PROVIDER",
        "LEVI_LOCAL_MODEL",
        "LEVI_LLAMA_SERVER",
        "LEVI_OPENAI_API_KEY",
        "LEVI_OPENAI_BASE_URL",
        "LEVI_ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


def _fake_gguf(model_dir: Path, file_name: str) -> Path:
    model_dir.mkdir(parents=True, exist_ok=True)
    gguf = model_dir / file_name
    gguf.write_bytes(b"GGUF-fake")
    return gguf


def _fake_runner(monkeypatch, tmp_path) -> Path:
    runner = tmp_path / "llama-server"
    runner.write_text("#!/bin/sh\n")
    runner.chmod(0o755)
    monkeypatch.setenv("LEVI_LLAMA_SERVER", str(runner))
    return runner


# ---------------------------------------------------------------------------
# Choice persistence
# ---------------------------------------------------------------------------


def test_use_persists_and_resolves(monkeypatch, tmp_path):
    _scrub_env(monkeypatch, tmp_path)
    assert model_family.get_choice() is None
    model_family.set_choice("levi-4b")
    assert model_family.get_choice() == "levi-4b"
    stored = json.loads(model_family.choice_path().read_text(encoding="utf-8"))
    assert stored == {"model": "levi-4b"}
    assert model_family.choice_path().parent == Path.home() / ".levi" / "agent"


def test_choice_survives_reimport_semantics(monkeypatch, tmp_path):
    # get_choice reads the file fresh every time — no stale caching.
    _scrub_env(monkeypatch, tmp_path)
    model_family.set_choice("levi-0.6b")
    model_family.clear_choice()
    assert model_family.get_choice() is None


# ---------------------------------------------------------------------------
# Default resolution: LEVI-first
# ---------------------------------------------------------------------------


def test_default_prefers_downloaded_levi_weight_over_rules(monkeypatch, tmp_path):
    _scrub_env(monkeypatch, tmp_path)
    model_dir = Path(os.environ["LEVI_MODEL_DIR"])
    _fake_gguf(model_dir, "Qwen3-0.6B-Q8_0.gguf")
    _fake_runner(monkeypatch, tmp_path)
    resolved = model_family.resolve_family()
    assert resolved is not None
    assert resolved["entry"] == "levi-0.6b"
    assert resolved["provider"] == "levi-local"
    p = select_provider()
    assert isinstance(p, LocalModelProvider)
    assert not isinstance(p, LocalProvider)


def test_default_prefers_largest_downloaded_remix(monkeypatch, tmp_path):
    _scrub_env(monkeypatch, tmp_path)
    model_dir = Path(os.environ["LEVI_MODEL_DIR"])
    _fake_gguf(model_dir, "Qwen3-0.6B-Q8_0.gguf")
    _fake_gguf(model_dir, "Qwen3-4B-Q4_K_M.gguf")
    _fake_runner(monkeypatch, tmp_path)
    resolved = model_family.resolve_family()
    assert resolved["entry"] == "levi-4b"
    p = select_provider()
    assert isinstance(p, LocalModelProvider)
    assert os.environ.get("LEVI_LOCAL_MODEL") == "Qwen3-4B-Q4_K_M.gguf"


def test_tiny_preferred_when_native_brain_present(monkeypatch, tmp_path):
    _scrub_env(monkeypatch, tmp_path)
    weights = tmp_path / "tiny-gpt.pt"
    weights.write_bytes(b"fake-ckpt")
    monkeypatch.setenv("LEVI_BRAIN_WEIGHTS", str(weights))
    monkeypatch.setattr("levi.agent.brain_provider.torch_available", lambda: True)
    resolved = model_family.resolve_family()
    assert resolved is not None
    assert resolved["entry"] == "levi-tiny"
    assert resolved["provider"] == "levi-brain"
    p = select_provider()
    assert isinstance(p, NativeBrainProvider)


def test_persisted_choice_wins_when_downloaded(monkeypatch, tmp_path):
    _scrub_env(monkeypatch, tmp_path)
    model_dir = Path(os.environ["LEVI_MODEL_DIR"])
    _fake_gguf(model_dir, "Qwen3-0.6B-Q8_0.gguf")
    _fake_gguf(model_dir, "Qwen3-4B-Q4_K_M.gguf")
    _fake_runner(monkeypatch, tmp_path)
    model_family.set_choice("levi-0.6b")  # smaller, but explicitly chosen
    resolved = model_family.resolve_family()
    assert resolved["entry"] == "levi-0.6b"


def test_nothing_downloaded_falls_back_to_rules(monkeypatch, tmp_path):
    _scrub_env(monkeypatch, tmp_path)
    assert model_family.resolve_family() is None
    p = select_provider()
    assert isinstance(p, LocalProvider)


def test_explicit_family_name_selects_provider(monkeypatch, tmp_path):
    _scrub_env(monkeypatch, tmp_path)
    model_dir = Path(os.environ["LEVI_MODEL_DIR"])
    _fake_gguf(model_dir, "Qwen3-4B-Q4_K_M.gguf")
    _fake_runner(monkeypatch, tmp_path)
    p = select_provider("levi-4b")
    assert isinstance(p, LocalModelProvider)
    assert os.environ.get("LEVI_LOCAL_MODEL") == "Qwen3-4B-Q4_K_M.gguf"


def test_explicit_user_env_model_not_overwritten(monkeypatch, tmp_path):
    _scrub_env(monkeypatch, tmp_path)
    model_dir = Path(os.environ["LEVI_MODEL_DIR"])
    _fake_gguf(model_dir, "Qwen3-4B-Q4_K_M.gguf")
    _fake_gguf(model_dir, "Qwen3-0.6B-Q8_0.gguf")
    _fake_runner(monkeypatch, tmp_path)
    monkeypatch.setenv("LEVI_LOCAL_MODEL", "Qwen3-0.6B-Q8_0.gguf")
    select_provider("levi-4b")  # must respect the explicit env, not re-pin
    assert os.environ["LEVI_LOCAL_MODEL"] == "Qwen3-0.6B-Q8_0.gguf"


def test_provider_names_family_first():
    names = provider_names()
    assert names[:3] == ["levi-tiny", "levi-0.6b", "levi-4b"]
    assert "local" in names and "openai" in names and "anthropic" in names


# ---------------------------------------------------------------------------
# CLI (subprocess, scrubbed env, fake HOME)
# ---------------------------------------------------------------------------


def _cli_env(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "core"), *sys.path])
    env["HOME"] = str(tmp_path / "home")
    for key in (
        "LEVI_PROVIDER",
        "LEVI_MODEL_DIR",
        "LEVI_BRAIN_WEIGHTS",
        "LEVI_LOCAL_MODEL",
        "LEVI_LLAMA_SERVER",
        "LEVI_OPENAI_API_KEY",
        "LEVI_OPENAI_BASE_URL",
        "LEVI_ANTHROPIC_API_KEY",
    ):
        env.pop(key, None)
    return env


def _levi(tmp_path, *argv):
    return subprocess.run(
        [sys.executable, "-m", "levi.cli.main", *argv],
        cwd=ROOT,
        env=_cli_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_cli_model_list_family_first(tmp_path):
    proc = _levi(tmp_path, "agent", "model", "list")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "LEVI model family" in out
    assert out.index("levi-tiny") < out.index("Other selectable sources")
    assert out.index("Other selectable sources") < out.index("openai")


def test_cli_model_use_unknown_errors(tmp_path):
    proc = _levi(tmp_path, "agent", "model", "use", "levi-99b")
    assert proc.returncode == 2
    assert "unknown LEVI family member" in proc.stdout


def test_cli_model_use_persists(tmp_path):
    proc = _levi(tmp_path, "agent", "model", "use", "levi-4b")
    assert proc.returncode == 0, proc.stderr
    stored = json.loads(
        (tmp_path / "home" / ".levi" / "agent" / "model_choice.json").read_text(
            encoding="utf-8"
        )
    )
    assert stored == {"model": "levi-4b"}


def test_cli_model_pull_unknown_errors(tmp_path):
    proc = _levi(tmp_path, "agent", "model", "pull", "levi-99b")
    assert proc.returncode == 2
    assert "Unknown model" in proc.stdout


def test_cli_model_pull_tiny_is_trained_not_downloaded(tmp_path):
    proc = _levi(tmp_path, "agent", "model", "pull", "levi-tiny")
    assert proc.returncode == 0, proc.stderr
    assert "trained, not downloaded" in proc.stdout


def test_cli_model_status_reports_no_weight(tmp_path):
    proc = _levi(tmp_path, "agent", "model", "status")
    assert proc.returncode == 0, proc.stderr
    assert "Active model" in proc.stdout
    assert "no LEVI weight available" in proc.stdout
    assert "fluent-ish gibberish" in proc.stdout  # honest limits shown
