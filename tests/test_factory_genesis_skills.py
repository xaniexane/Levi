"""Factory Genesis batch-3 proof — ten new skills (genesis-021..030).

Law->guard->prove per skill: mint_skill(id) proves registration,
factory category, info risk, no permissions, no confirmation.
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
def hooks():
    from levi.factory.genesis import registry_hooks
    return registry_hooks


def test_skill_watch_summary(hooks):
    result = hooks.mint_skill("factory.watch_summary")
    assert result["verified"] is True
    assert result["category"] == "factory"
    assert result["risk"] == 0  # info
    assert result["permissions"] == []
    assert _queue_status("genesis-021") == "registered"

def test_skill_deposit_tracker(hooks):
    result = hooks.mint_skill("factory.deposit_tracker")
    assert result["verified"] is True
    assert result["category"] == "factory"
    assert result["risk"] == 0  # info
    assert result["permissions"] == []
    assert _queue_status("genesis-022") == "registered"

def test_skill_receipt_audit(hooks):
    result = hooks.mint_skill("factory.receipt_audit")
    assert result["verified"] is True
    assert result["category"] == "factory"
    assert result["risk"] == 0  # info
    assert result["permissions"] == []
    assert _queue_status("genesis-023") == "registered"

def test_skill_listing_drafter(hooks):
    result = hooks.mint_skill("factory.listing_drafter")
    assert result["verified"] is True
    assert result["category"] == "factory"
    assert result["risk"] == 0  # info
    assert result["permissions"] == []
    assert _queue_status("genesis-024") == "registered"

def test_skill_audit_runner(hooks):
    result = hooks.mint_skill("factory.audit_runner")
    assert result["verified"] is True
    assert result["category"] == "factory"
    assert result["risk"] == 0  # info
    assert result["permissions"] == []
    assert _queue_status("genesis-025") == "registered"

def test_skill_signal_triage(hooks):
    result = hooks.mint_skill("factory.signal_triage")
    assert result["verified"] is True
    assert result["category"] == "factory"
    assert result["risk"] == 0  # info
    assert result["permissions"] == []
    assert _queue_status("genesis-026") == "registered"

def test_skill_budget_ledger_post(hooks):
    result = hooks.mint_skill("factory.budget_ledger_post")
    assert result["verified"] is True
    assert result["category"] == "factory"
    assert result["risk"] == 0  # info
    assert result["permissions"] == []
    assert _queue_status("genesis-027") == "registered"

def test_skill_namecheck(hooks):
    result = hooks.mint_skill("factory.namecheck")
    assert result["verified"] is True
    assert result["category"] == "factory"
    assert result["risk"] == 0  # info
    assert result["permissions"] == []
    assert _queue_status("genesis-028") == "registered"

def test_skill_launch_gatekeeper(hooks):
    result = hooks.mint_skill("factory.launch_gatekeeper")
    assert result["verified"] is True
    assert result["category"] == "factory"
    assert result["risk"] == 0  # info
    assert result["permissions"] == []
    assert _queue_status("genesis-029") == "registered"

def test_skill_stall_report(hooks):
    result = hooks.mint_skill("factory.stall_report")
    assert result["verified"] is True
    assert result["category"] == "factory"
    assert result["risk"] == 0  # info
    assert result["permissions"] == []
    assert _queue_status("genesis-030") == "registered"
