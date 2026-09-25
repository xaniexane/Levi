"""Hardening-sweep regression tests (2026-09-15).

Covers the validation boundaries and degraded-mode behavior added during
the LEVI hardening sweep: model-engine configure(), story-fabric lookup
and persist batching, model-abstraction URL/request validation, relay
config cleaning, ledger transactions, and the small graph/lwp helper
guards. All hermetic: tmp dirs only, no network, no user-HOME writes.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from levi.graph import backwords, story_quality, symbiosis
from levi.graph.organism import register_into_graph
from levi.graph.story_fabric import StoryFabric
from levi.graph.story_prose import expand_paragraph
from levi.king import ledger as ledger_mod
from levi.king.ledger import ContinuityLedger
from levi.lwp import mirror_cascade, premium_craft
from levi.lwp.model_engine import LWPModelEngine
from levi.model.abstraction import (
    DeterministicFallbackProvider,
    GenerationRequest,
    OllamaProvider,
)
from levi.model.relay import ModelRelay, RelayConfig


# -- organism graph registration -------------------------------------------


def test_organism_registers_bloodstream_bonds(monkeypatch, tmp_path):
    """register_into_graph reads GraphEdge.source_id/target_id (not .source)."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    result = register_into_graph()
    assert result.startswith("Organism registered"), result
    added = int(result.split("new bonds")[0].rsplit(" ", 2)[-2])
    assert added > 0


# -- story fabric ------------------------------------------------------------


def _fabric(tmp_path) -> StoryFabric:
    return StoryFabric(data_dir=tmp_path / "stories")


def test_story_fabric_unknown_story_is_actionable(tmp_path):
    fab = _fabric(tmp_path)
    with pytest.raises(ValueError, match="Unknown story"):
        fab.expand("story.nope")


def test_story_fabric_expand_validates_focus(tmp_path):
    fab = _fabric(tmp_path)
    s = fab.create_story("A harbor premise.", genre="literary", title="T")
    with pytest.raises(ValueError, match="focus"):
        fab.expand(s.id, focus=42)  # type: ignore[arg-type]


def test_story_fabric_auto_forward_validates_beats(tmp_path):
    fab = _fabric(tmp_path)
    s = fab.create_story("A harbor premise.", genre="literary", title="T")
    with pytest.raises(ValueError, match="beats"):
        fab.auto_forward(s.id, beats="5")  # type: ignore[arg-type]


def test_story_fabric_auto_forward_single_write(monkeypatch, tmp_path):
    """The _batch() context collapses N+1 persists into 1 file write."""
    writes = []
    real_write_text = pathlib.Path.write_text

    def counting(self, data, *args, **kwargs):
        if self.name == "stories.tmp":
            writes.append(1)
        return real_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "write_text", counting)
    fab = _fabric(tmp_path)
    s = fab.create_story("A harbor premise.", genre="literary", title="T")
    writes.clear()
    fab.auto_forward(s.id, beats=5)
    assert len(writes) == 1
    # and the beats really landed
    assert len(fab.get(s.id).beats) >= 5


# -- model engine configure ---------------------------------------------------


def test_model_engine_configure_accepts_known_settings(tmp_path):
    eng = LWPModelEngine(path=tmp_path / "model.json")
    status = eng.configure(phase="peak", genres="noir, systems_horror")
    assert "phase=" in status


def test_model_engine_configure_rejects_unknown_key(tmp_path):
    eng = LWPModelEngine(path=tmp_path / "model.json")
    with pytest.raises(ValueError, match="unknown manuscript setting"):
        eng.configure(bogus_key=1)


def test_model_engine_configure_validates_enums_and_types(tmp_path):
    eng = LWPModelEngine(path=tmp_path / "model.json")
    with pytest.raises(ValueError, match="phase"):
        eng.configure(phase="not-a-phase")
    with pytest.raises(ValueError, match="words"):
        eng.configure(words="many")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="words"):
        eng.configure(words=True)
    with pytest.raises(ValueError, match="genres"):
        eng.configure(genres=[1, 2])  # type: ignore[arg-type]


# -- model abstraction -------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    ["file:///etc/passwd", "javascript:alert(1)", "http://", "", "ftp://h/x", 123],
)
def test_ollama_base_url_rejects_unsafe(bad):
    with pytest.raises(ValueError, match="base_url"):
        OllamaProvider(bad)


def test_ollama_base_url_accepts_localhost():
    p = OllamaProvider("http://127.0.0.1:11434/")
    assert p.base_url == "http://127.0.0.1:11434"


def test_generate_validates_request_shape():
    fb = DeterministicFallbackProvider()
    with pytest.raises(ValueError, match="prompt"):
        fb.generate("fallback-deterministic", GenerationRequest(prompt="   "))
    with pytest.raises(ValueError, match="max_tokens"):
        fb.generate(
            "fallback-deterministic", GenerationRequest(prompt="hi", max_tokens=0)
        )
    with pytest.raises(ValueError, match="temperature"):
        fb.generate(
            "fallback-deterministic",
            GenerationRequest(prompt="hi", temperature=5.0),
        )
    with pytest.raises(ValueError, match="model_id"):
        fb.generate("", GenerationRequest(prompt="hi"))


# -- model relay --------------------------------------------------------------


def test_relay_config_drops_malformed_endpoints(tmp_path):
    p = tmp_path / "relay.json"
    p.write_text(
        json.dumps(
            {
                "prefer_local": False,
                "cloud_endpoints": [{"url": "https://x"}, "junk", {"url": 5}, 42],
            }
        )
    )
    cfg = RelayConfig.load(p)
    assert cfg.prefer_local is False
    assert cfg.cloud_endpoints == [{"url": "https://x"}]


def test_relay_config_degrades_on_bad_file(tmp_path):
    p = tmp_path / "relay.json"
    p.write_text("not json{{")
    cfg = RelayConfig.load(p)
    assert cfg == RelayConfig()
    p.write_text("[1,2]")
    assert RelayConfig.load(p).cloud_endpoints == []


def test_relay_generate_rejects_empty_prompt():
    relay = ModelRelay(config=RelayConfig())
    with pytest.raises(ValueError, match="prompt"):
        relay.generate("   ")


# -- king ledger transactions --------------------------------------------------


def _count_ledger_writes(monkeypatch):
    writes = []
    real = ledger_mod._write_json_600

    def counting(path, payload):
        if pathlib.Path(path).name == "ledger.json":
            writes.append(1)
        return real(path, payload)

    monkeypatch.setattr(ledger_mod, "_write_json_600", counting)
    return writes


def test_ledger_transaction_batches_writes(monkeypatch, tmp_path):
    led = ContinuityLedger(data_dir=tmp_path)
    writes = _count_ledger_writes(monkeypatch)
    with led.transaction():
        led.harvest(source="king", words=1, banks=1)
        with led.transaction():
            led.harvest(source="king", words=1, banks=1)
    assert len(writes) == 1


def test_ledger_transaction_failure_persists_then_raises(monkeypatch, tmp_path):
    led = ContinuityLedger(data_dir=tmp_path)
    writes = _count_ledger_writes(monkeypatch)
    with pytest.raises(RuntimeError, match="boom"):
        with led.transaction():
            led.harvest(source="king", words=7, banks=1, event="will-fail")
            raise RuntimeError("boom")
    assert len(writes) == 1  # best-effort persist of prior mutations
    # data survived on disk
    led2 = ContinuityLedger(data_dir=tmp_path)
    assert led2.total_words >= 7


# -- small helper guards -------------------------------------------------------


def test_backwords_guards():
    assert backwords.split_units(None) == []
    with pytest.raises(ValueError):
        backwords.reverse_units("no")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        story_quality.rate_text(5)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        expand_paragraph("b", "l", "g", "p", wound="w", index="1")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        symbiosis.value_check(None)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        premium_craft.pick_cascade_beat(1.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        premium_craft.scene_goal(None)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        mirror_cascade.MirrorCascade().run(42)  # type: ignore[arg-type]
