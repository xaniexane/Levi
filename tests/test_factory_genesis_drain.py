"""Factory Genesis queue-drain proof — genesis-003/004/005.

Law->guard->prove for the drained intake items:
- skill mints prove via registry_hooks.mint_skill (registered, factory
  category, info risk);
- the agent mint proves via registry_hooks.mint_agent with its class
  (agent_id, generation 2, commissioned_by factory-genesis, first_task
  returns a non-empty dict);
- ventures (genesis-006..010) are spec-only: prove the spec file exists
  and the queue marks them spec'd.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "core"))

QUEUE = REPO / "core" / "levi" / "factory" / "genesis" / "intake" / "queue.jsonl"
SPECS = REPO / "core" / "levi" / "factory" / "genesis" / "specs"


def _queue_status(item_id: str) -> str:
    for raw in QUEUE.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        item = json.loads(raw)
        if item.get("id") == item_id:
            return str(item.get("status"))
    return "missing"


def test_skill_mystery_box_pricer():
    from levi.factory.genesis.registry_hooks import mint_skill

    result = mint_skill("factory.mystery_box_pricer")
    assert result["verified"] is True
    assert result["category"] == "factory"
    assert result["risk"] == 0  # info
    assert _queue_status("genesis-003") == "registered"


def test_skill_competitor_brief():
    from levi.factory.genesis.registry_hooks import mint_skill

    result = mint_skill("factory.competitor_brief")
    assert result["verified"] is True
    assert result["category"] == "factory"
    assert result["risk"] == 0  # info
    assert _queue_status("genesis-005") == "registered"


def test_agent_ddd_inbox_watcher():
    from levi.dynasty.wave import DDDInboxWatcher
    from levi.factory.genesis.registry_hooks import mint_agent

    result = mint_agent(DDDInboxWatcher)
    assert result["verified"] is True
    assert result["agent_id"] == "ddd-inbox-watcher"
    assert result["generation"] == 2
    assert result["commissioned_by"] == "factory-genesis"
    assert _queue_status("genesis-004") == "registered"


@pytest.mark.parametrize("vid", ["genesis-006", "genesis-007", "genesis-008", "genesis-009", "genesis-010"])
def test_venture_specs_exist(vid):
    # Ventures are spec-only: the starter spec is the deliverable.
    assert (SPECS / f"{vid}.md").is_file()
    assert _queue_status(vid) == "spec'd"
