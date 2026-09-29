# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Proof for the ten DDD SI operators (law → guard → prove).

Laws under test:
  L1 draft-only, L2 no payment, L3 no outbound (refused loudly),
  L4 read-only watch (honest zero-state, rows never invented),
  L5 ReviewReply hard rule (drafts only, never posts).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import levi.ddd.agents as pkg
import levi.ddd.agents.base as base
from levi.dynasty.dna import AgentError, DynastyAgent

AGENT_CLASSES = [
    pkg.NoShowWarden,
    pkg.ListingHerald,
    pkg.AuditWarden,
    pkg.ChaseClerk,
    pkg.SwitchKeeper,
    pkg.LeadScout,
    pkg.ReplyDrafter,
    pkg.LotAppraiser,
    pkg.MenuCrafter,
    pkg.RentRollKeeper,
]

DRAFT_METHODS = {
    "NoShowWarden": "draft_reminders",
    "ListingHerald": "draft_pack",
    "AuditWarden": "draft_brief",
    "ChaseClerk": "draft_chase_list",
    "SwitchKeeper": "draft_checklist",
    "LeadScout": "draft_pack",
    "ReplyDrafter": "draft_replies",
    "LotAppraiser": "draft_worksheet",
    "MenuCrafter": "draft_preview",
    "RentRollKeeper": "draft_roll",
}

AGENTS_DIR = Path(pkg.__file__).parent
_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,31}$")

#: Tokens that must never appear in an advisory-only operator's source.
FORBIDDEN_TOKENS = [
    "smtplib",
    "stripe",
    "paypal",
    "twilio",
    "requests.post",
    "requests.put",
    "requests.delete",
    ".publish(",
    "auto_post",
    "send_email",
    "send_sms",
    "create_charge",
    "charge_customer",
    "subprocess",
]

#: Method definitions that must never exist on an advisory-only operator.
FORBIDDEN_DEFS = re.compile(
    r"^\s*def\s+(send|publish|charge|post|contact)\s*\(", re.MULTILINE
)


def test_all_ten_registered_in_package():
    assert len(AGENT_CLASSES) == 10
    assert set(pkg.__all__) == {c.__name__ for c in AGENT_CLASSES}
    for cls in AGENT_CLASSES:
        assert issubclass(cls, DynastyAgent)
        assert issubclass(cls, base.DDDOperatorAgent)


def test_ids_unique_valid_and_names_provisional():
    ids = [c.agent_id for c in AGENT_CLASSES]
    assert len(set(ids)) == 10, f"duplicate agent ids: {ids}"
    for cls in AGENT_CLASSES:
        assert _ID_RE.match(cls.agent_id), f"bad id {cls.agent_id!r}"
        assert "provisional" in cls.display_name.lower()
        assert cls.generation == 2


def test_advisory_only_flags_on_every_agent(tmp_path):
    for cls in AGENT_CLASSES:
        assert cls.advisory_only is True, cls.__name__
        assert cls.draft_only is True, cls.__name__
        assert cls.outbound_actions == (), cls.__name__
        assert cls.allowed_wares == (), cls.__name__
        agent = cls(drafts_dir=tmp_path)
        assert agent.advisory_only is True
        assert agent.draft_only is True


def test_outbound_kinds_refused_loudly(tmp_path):
    for cls in AGENT_CLASSES:
        agent = cls(drafts_dir=tmp_path)
        for kind in sorted(base.OUTBOUND_KINDS):
            with pytest.raises(AgentError):
                agent.handle({"kind": kind})
        with pytest.raises(AgentError):
            agent.refuse_outbound("send")


def test_unknown_kind_refused(tmp_path):
    agent = pkg.AuditWarden(drafts_dir=tmp_path)
    with pytest.raises(AgentError):
        agent.handle({"kind": "definitely-not-a-kind"})


def test_watch_and_first_task_return_honest_state(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "_DDD_ROOT", tmp_path / "empty-ddd")
    for cls in AGENT_CLASSES:
        agent = cls(drafts_dir=tmp_path)
        state = agent.watch()
        assert isinstance(state, dict)
        assert state["agent_id"] == cls.agent_id
        assert "checked_at" in state
        assert state.get("n_rows", 0) == 0 or cls is pkg.SwitchKeeper
        first = agent.first_task()
        assert first["agent_id"] == cls.agent_id


def test_draft_methods_return_labeled_drafts(tmp_path):
    for cls in AGENT_CLASSES:
        agent = cls(drafts_dir=tmp_path)
        method = getattr(agent, DRAFT_METHODS[cls.__name__])
        text = method()
        assert isinstance(text, str) and len(text) > 20
        assert "DRAFT" in text
        out = agent.handle({"kind": "draft"})
        assert "DRAFT" in out["draft"]


def test_save_draft_writes_labeled_file_and_cannot_escape(tmp_path):
    agent = pkg.NoShowWarden(drafts_dir=tmp_path / "drafts")
    path = agent.save_draft("warden-test", "# hello")
    written = Path(path)
    assert written.parent == (tmp_path / "drafts").resolve()
    body = written.read_text(encoding="utf-8")
    assert "DRAFT" in body and "# hello" in body
    with pytest.raises(AgentError):
        agent.save_draft("../escape", "nope")
    with pytest.raises(AgentError):
        agent.save_draft("UPPERCASE", "nope")


def test_no_forbidden_tokens_or_defs_in_operator_sources():
    for mod in sorted(AGENTS_DIR.glob("*.py")):
        if mod.name in ("__init__.py", "base.py"):
            continue
        src = mod.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            assert token not in src, f"{mod.name} contains {token!r}"
        assert not FORBIDDEN_DEFS.search(src), f"{mod.name} defines an outbound method"
        tree = ast.parse(src)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        for bad in ("requests", "stripe", "smtplib", "twilio", "boto3"):
            assert bad not in imports, f"{mod.name} imports {bad}"


def test_reply_drafter_carries_the_hard_rule(tmp_path):
    agent = pkg.ReplyDrafter(drafts_dir=tmp_path)
    assert "never posts" in agent.owns.lower()
    text = agent.draft_replies()
    assert "NEVER POSTED" in text or "never posted" in text.lower()
    with pytest.raises(AgentError):
        agent.handle({"kind": "post"})
