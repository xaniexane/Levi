"""Factory Genesis batch-2 proof — ten new agents (genesis-011..020).

Law->guard->prove per agent: mint_agent(class) proves agent_id,
generation 2, commissioned_by factory-genesis, and a non-empty
first_task() dict; the queue must mark each registered.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "core"))

QUEUE = REPO / "core" / "levi" / "factory" / "genesis" / "intake" / "queue.jsonl"


def _queue_status(item_id: str) -> str:
    for raw in QUEUE.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        item = json.loads(raw)
        if item.get("id") == item_id:
            return str(item.get("status"))
    return "missing"


@pytest.fixture(scope="module")
def wave():
    import levi.dynasty.wave as wave
    return wave


@pytest.fixture(scope="module")
def hooks():
    from levi.factory.genesis import registry_hooks
    return registry_hooks


def test_agent_watchtender(wave, hooks):
    cls = wave.WatchTender
    result = hooks.mint_agent(cls)
    assert result["verified"] is True
    assert result["agent_id"] == "watchtender"
    assert result["generation"] == 2
    assert result["commissioned_by"] == "factory-genesis"
    assert _queue_status("genesis-011") == "registered"

def test_agent_ledgerwarden(wave, hooks):
    cls = wave.LedgerWarden
    result = hooks.mint_agent(cls)
    assert result["verified"] is True
    assert result["agent_id"] == "ledgerwarden"
    assert result["generation"] == 2
    assert result["commissioned_by"] == "factory-genesis"
    assert _queue_status("genesis-012") == "registered"

def test_agent_briefscribe(wave, hooks):
    cls = wave.BriefScribe
    result = hooks.mint_agent(cls)
    assert result["verified"] is True
    assert result["agent_id"] == "briefscribe"
    assert result["generation"] == 2
    assert result["commissioned_by"] == "factory-genesis"
    assert _queue_status("genesis-013") == "registered"

def test_agent_corpusminer(wave, hooks):
    cls = wave.CorpusMiner
    result = hooks.mint_agent(cls)
    assert result["verified"] is True
    assert result["agent_id"] == "corpusminer"
    assert result["generation"] == 2
    assert result["commissioned_by"] == "factory-genesis"
    assert _queue_status("genesis-014") == "registered"

def test_agent_specsmith(wave, hooks):
    cls = wave.SpecSmith
    result = hooks.mint_agent(cls)
    assert result["verified"] is True
    assert result["agent_id"] == "specsmith"
    assert result["generation"] == 2
    assert result["commissioned_by"] == "factory-genesis"
    assert _queue_status("genesis-015") == "registered"

def test_agent_proofclerk(wave, hooks):
    cls = wave.ProofClerk
    result = hooks.mint_agent(cls)
    assert result["verified"] is True
    assert result["agent_id"] == "proofclerk"
    assert result["generation"] == 2
    assert result["commissioned_by"] == "factory-genesis"
    assert _queue_status("genesis-016") == "registered"

def test_agent_nametender(wave, hooks):
    cls = wave.NameTender
    result = hooks.mint_agent(cls)
    assert result["verified"] is True
    assert result["agent_id"] == "nametender"
    assert result["generation"] == 2
    assert result["commissioned_by"] == "factory-genesis"
    assert _queue_status("genesis-017") == "registered"

def test_agent_dealspotter(wave, hooks):
    cls = wave.DealSpotter
    result = hooks.mint_agent(cls)
    assert result["verified"] is True
    assert result["agent_id"] == "dealspotter"
    assert result["generation"] == 2
    assert result["commissioned_by"] == "factory-genesis"
    assert _queue_status("genesis-018") == "registered"

def test_agent_receiptclerk(wave, hooks):
    cls = wave.ReceiptClerk
    result = hooks.mint_agent(cls)
    assert result["verified"] is True
    assert result["agent_id"] == "receiptclerk"
    assert result["generation"] == 2
    assert result["commissioned_by"] == "factory-genesis"
    assert _queue_status("genesis-019") == "registered"

def test_agent_inboxtender(wave, hooks):
    cls = wave.InboxTender
    result = hooks.mint_agent(cls)
    assert result["verified"] is True
    assert result["agent_id"] == "inboxtender"
    assert result["generation"] == 2
    assert result["commissioned_by"] == "factory-genesis"
    assert _queue_status("genesis-020") == "registered"
