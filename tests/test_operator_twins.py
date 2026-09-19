"""Tests for the orchestrated twin-pair on-demand mode (levi.operator.twins).

Chauncey ratified the hybrid choice on 2026-09-18: twin mode
``"on_demand"``. Covers:

(a) fork on high stakes; no fork on trivial stakes;
(b) the arrival banner is present and legible (plain speech);
(c) auto-merge on VERIFIED (primary text + verifier concurrence,
    note records both contributors);
(d) user-judge path on CHALLENGED: BOTH results returned framed as
    "your call", nothing auto-merged, stable disagreement_id;
(e) record_pick writes a growth-loop learning with provenance
    "twin-judge" (additive — growth internals untouched);
(f) NO inverse-merge semantics anywhere in the twins module
    (the full inverse-twin merge/judge stays GATED);
(g) force_twin in context triggers the fork on non-high stakes;
(h) the ratified default mode is on_demand.

Hermetic: no network, no torch, journal/memory writes go to tmp dirs.

Run:  python3 -m pytest tests/test_operator_twins.py -q
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

import pytest  # noqa: E402

from levi.operator import (  # noqa: E402
    NATIVE,
    Operator,
    OperatorCapabilities,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
    OperatorRegistry,
    resolve_twin,
)
from levi.operator.twins import (  # noqa: E402
    TwinArrival,
    TwinTurnResult,
    record_pick,
    run_twin_turn,
)


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _StubOperator(Operator):
    """Minimal native stub operator: fixed reply, honest health."""

    def __init__(self, name: str, reply: str) -> None:
        self._name = name
        self._reply = reply
        self.steps = 0

    @property
    def name(self) -> str:  # type: ignore[override]
        return self._name

    kind = NATIVE
    version = "0.0.1"
    lineage = "test:stub"

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=(),
            streaming=False,
            memory_access=False,
            context_window=1024,
            tool_use_loop=False,
            notes="test stub",
        )

    def health(self) -> OperatorHealth:
        return OperatorHealth(ok=True, note="stub healthy")

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        self.steps += 1
        return OperatorResult(
            text=self._reply,
            operator=self._name,
            kind=self.kind,
            finish_reason="stop",
        )


def _user(text: str) -> List[OperatorMessage]:
    return [OperatorMessage(role="user", content=text)]


def _registry(verdict: str = "VERIFIED") -> OperatorRegistry:
    """Registry with a primary and a verifier whose verdict text is
    fixed: "VERIFIED" or "CHALLENGED"."""
    reg = OperatorRegistry()
    reg.register("primary-op", _StubOperator("primary-op", "Primary answer."))
    if verdict == "VERIFIED":
        reply = "VERIFIED: I checked the primary's answer independently."
    else:
        reply = (
            "CHALLENGED: the primary missed the second constraint. "
            "Its answer assumes a condition the user did not state."
        )
    reg.register("verifier-op", _StubOperator("verifier-op", reply))
    # Stand-ins for the seats/tiers the single-operator path can resolve.
    reg.register("levi-brain", _StubOperator("levi-brain", "Brain answer."))
    reg.register("nano-bit", _StubOperator("nano-bit", "nano-bit reply."))
    return reg


def _config(mode: str = "on_demand") -> Dict[str, Any]:
    return {
        "twins": {
            "mode": mode,
            "seats": {"chat": {"primary": "primary-op", "verifier": "verifier-op"}},
        }
    }


# ---------------------------------------------------------------------------
# (a) fork on high stakes; no fork on trivial
# ---------------------------------------------------------------------------


def test_fork_on_high_stakes():
    reg = _registry("VERIFIED")
    turn = run_twin_turn(
        reg, "chat", _user("transfer money now"), [], {"stakes": "high"}, _config()
    )
    assert turn.arrival is not None
    assert turn.arrival.verifier_name == "verifier-op"
    assert turn.arrival.stakes == "high"
    assert turn.verifier_result is not None
    assert turn.disagreement is False
    assert turn.needs_user_judge is False
    assert turn.disagreement_id is None
    assert turn.merged_result is not None


def test_no_fork_on_trivial_stakes():
    reg = _registry("VERIFIED")
    turn = run_twin_turn(reg, "chat", _user("hi"), [], {}, _config())
    assert turn.arrival is None
    assert turn.verifier_result is None
    assert turn.disagreement is False
    assert turn.needs_user_judge is False
    assert turn.disagreement_id is None
    assert turn.merged_result is not None
    assert turn.merged_result.text == "Primary answer."
    # The verifier stub never ran.
    assert reg.resolve("verifier-op").steps == 0


def test_no_fork_when_mode_off():
    reg = _registry("VERIFIED")
    turn = run_twin_turn(
        reg, "chat", _user("transfer money now"), [], {"stakes": "high"}, _config("off")
    )
    assert turn.arrival is None
    assert turn.verifier_result is None


# ---------------------------------------------------------------------------
# (b) legible arrival banner
# ---------------------------------------------------------------------------


def test_arrival_banner_legible():
    reg = _registry("VERIFIED")
    turn = run_twin_turn(
        reg, "chat", _user("transfer money now"), [], {"stakes": "high"}, _config()
    )
    assert turn.arrival is not None
    banner = turn.arrival.banner()
    assert banner == (
        "Second mind 'verifier-op' joined — high-stakes turn "
        "(stakes assessed high)."
    )
    # Rendered into the merged result's note too.
    assert turn.merged_result is not None
    assert banner in turn.merged_result.note


def test_arrival_banner_on_forced_fork():
    reg = _registry("VERIFIED")
    turn = run_twin_turn(
        reg, "chat", _user("hi"), [], {"force_twin": True}, _config()
    )
    assert turn.arrival is not None
    assert turn.arrival.banner() == (
        "Second mind 'verifier-op' joined — requested by the seat "
        "(force_twin set in context)."
    )


# ---------------------------------------------------------------------------
# (c) auto-merge on VERIFIED
# ---------------------------------------------------------------------------


def test_auto_merge_on_verified():
    reg = _registry("VERIFIED")
    turn = run_twin_turn(
        reg, "chat", _user("transfer money now"), [], {"stakes": "high"}, _config()
    )
    merged = turn.merged_result
    assert merged is not None
    assert merged.text.startswith("Primary answer.")
    assert "verifier-op" in merged.text  # concurrence recorded
    note = merged.note
    assert "primary-op" in note and "verifier-op" in note  # both contributors
    assert "VERIFIED" in note
    assert "combined confidence" in note


# ---------------------------------------------------------------------------
# (d) user-judge path on CHALLENGED
# ---------------------------------------------------------------------------


def test_user_judge_on_challenged():
    reg = _registry("CHALLENGED")
    turn = run_twin_turn(
        reg, "chat", _user("transfer money now"), [], {"stakes": "high"}, _config()
    )
    assert turn.disagreement is True
    assert turn.needs_user_judge is True
    assert turn.merged_result is None  # NOT auto-merged
    assert turn.disagreement_id is not None
    assert turn.disagreement_id.startswith("twindis-")
    # Both results returned, framed as "your call".
    assert "Primary answer." in turn.primary_result.text
    assert "CHALLENGED" in turn.verifier_result.text
    assert "your call" in turn.primary_result.note
    assert "your call" in turn.verifier_result.note


def test_disagreement_id_is_stable():
    reg = _registry("CHALLENGED")
    first = run_twin_turn(
        reg, "chat", _user("transfer money now"), [], {"stakes": "high"}, _config()
    )
    second = run_twin_turn(
        reg, "chat", _user("transfer money now"), [], {"stakes": "high"}, _config()
    )
    assert first.disagreement_id == second.disagreement_id
    assert first.disagreement_id != "twindis-"


# ---------------------------------------------------------------------------
# (g) force_twin triggers the fork
# ---------------------------------------------------------------------------


def test_fork_on_force_twin():
    reg = _registry("VERIFIED")
    turn = run_twin_turn(
        reg, "chat", _user("hi"), [], {"force_twin": True}, _config()
    )
    assert turn.arrival is not None
    assert turn.verifier_result is not None
    assert turn.merged_result is not None


# ---------------------------------------------------------------------------
# (e) record_pick writes a growth learning (additive)
# ---------------------------------------------------------------------------


def test_record_pick_writes_growth_learning(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(tmp_path / "growth"))
    from levi.memory.store import MemoryStore

    store = MemoryStore(data_dir=tmp_path / "memory")
    report = record_pick("twindis-abc123", "rules-engine", store)
    assert report["accepted"] >= 1

    entries = [
        e
        for e in store.list(limit=100)
        if "twin-judge" in (e.tags or [])
    ]
    assert len(entries) >= 1
    entry = entries[0]
    prov = (entry.metadata or {}).get("provenance") or {}
    assert prov.get("twin-judge") is True
    assert prov.get("disagreement_id") == "twindis-abc123"
    assert prov.get("winner") == "rules-engine"
    assert "twindis-abc123" in (entry.content or "")
    assert "rules-engine" in (entry.content or "")

    # Journal record landed in the hermetic growth dir.
    journal = tmp_path / "growth" / "journal.jsonl"
    assert journal.exists()
    assert "twindis-abc123" in journal.read_text(encoding="utf-8")


def test_record_pick_validates_inputs():
    with pytest.raises(ValueError):
        record_pick("", "rules-engine", None)
    with pytest.raises(ValueError):
        record_pick("twindis-x", "", None)
    with pytest.raises(ValueError):
        record_pick("twindis-x", "rules-engine", object())


def test_record_pick_rejects_unknown_winner_via_registry():
    reg = OperatorRegistry()  # no operators registered
    with pytest.raises(ValueError):
        record_pick("twindis-x", "no-such-operator", reg)


# ---------------------------------------------------------------------------
# (f) NO inverse-merge semantics — GATED, must not exist here
# ---------------------------------------------------------------------------


def test_no_inverse_semantics_in_twins_module():
    import ast

    source = (
        Path(__file__).resolve().parents[1] / "core" / "levi" / "operator" / "twins.py"
    )
    tree = ast.parse(source.read_text(encoding="utf-8"))
    identifiers = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            identifiers.add(node.name)
    # No inverse merge/judge is IMPLEMENTED here. (The module's
    # docstrings legitimately name the gate — "not the gated inverse
    # merge" — which is why this checks identifiers, not prose.)
    assert not any("inverse" in name.lower() for name in identifiers)

    import levi.operator.twins as twins_mod

    for name in dir(twins_mod):
        assert "inverse" not in name.lower()
    # No merge/judge pair machinery: the twin objects are structural.
    assert not hasattr(twins_mod, "TwinPair")


# ---------------------------------------------------------------------------
# (h) ratified default mode
# ---------------------------------------------------------------------------


def test_ratified_default_mode_is_on_demand():
    pair = resolve_twin(
        "chat",
        {"twins": {"seats": {"chat": {"primary": "a", "verifier": "b"}}}},
    )
    assert pair is not None
    assert pair.mode == "on_demand"
    # Explicit mode still respected.
    pair_off = resolve_twin(
        "chat",
        {"twins": {"mode": "off", "seats": {"chat": {"primary": "a", "verifier": "b"}}}},
    )
    assert pair_off is None
