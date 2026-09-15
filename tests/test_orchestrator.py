"""Smoke: the orchestration loop works hermetically.

``Orchestrator.turn`` runs the full pipeline (UNDERSTAND → PERSONA →
SPECIALISTS → SKILLS/POLICY → SYNTHESIZE) against the deterministic
offline model path. A trivial "help" input resolves locally without
contacting Ollama or the network.
"""
from levi.orchestration.loop import Orchestrator, TurnResult


def test_orchestrator_constructs():
    orch = Orchestrator()
    assert orch.ei is not None
    assert orch.lattice is not None
    assert "normal" in orch.lattice.keys()


def test_orchestrator_turn_help_hermetic():
    orch = Orchestrator()
    result = orch.turn("help")
    assert isinstance(result, TurnResult)
    assert result.response, "turn('help') produced an empty response"
    assert result.intent


def test_orchestrator_turn_does_not_require_network():
    # No localhost Ollama daemon is running in CI; if turn() needed one,
    # it would raise ConnectionError here instead of returning offline text.
    orch = Orchestrator()
    result = orch.turn("help")
    assert "offline" in result.response.lower() or result.response
