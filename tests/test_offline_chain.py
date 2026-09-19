"""Tests for levi.offline — the offline-first answer chain.

Hermetic: no network, no HOME writes; scripted backends only.
"""

import pytest

from levi.offline import (
    Answer,
    GatePolicy,
    Journal,
    Offliner,
    RuleBackend,
    default_policy,
)
from levi.offline.chain import Backend


class Scripted(Backend):
    name = "local:scripted"

    def __init__(self, confidence: float, text: str = "scripted answer"):
        self._confidence = confidence
        self._text = text

    def generate(self, prompt: str, context: str = "") -> Answer:
        return Answer(text=self._text, confidence=self._confidence, backend=self.name)


class CloudStub(Backend):
    name = "cloud:stub"

    def generate(self, prompt: str, context: str = "") -> Answer:
        return Answer(text="cloud answer", confidence=0.8, backend=self.name)


def test_default_policy_is_local_only():
    p = default_policy()
    assert p.keeper_allows_cloud is False
    ok, reason = p.escalation_permitted(True)
    assert ok is False and "keeper" in reason


def test_gate_needs_both_switches():
    p = GatePolicy(keeper_allows_cloud=True)
    ok, _ = p.escalation_permitted(False)
    assert ok is False
    ok, _ = p.escalation_permitted(True)
    assert ok is True


def test_confident_local_answer_never_escalates():
    chain = Offliner(
        Scripted(0.9), cloud=CloudStub(), policy=GatePolicy(keeper_allows_cloud=True)
    )
    res = chain.answer("hello", allow_cloud=True)
    assert res.receipt.escalated is False
    assert res.receipt.escalation_considered is False
    assert res.answer.backend == "local:scripted"


def test_low_confidence_escalates_only_with_dual_gate():
    # keeper gate closed -> denied even with per-call consent
    chain = Offliner(Scripted(0.1), cloud=CloudStub())
    res = chain.answer("help", allow_cloud=True)
    assert res.receipt.escalation_considered is True
    assert res.receipt.escalated is False
    assert "keeper" in res.receipt.escalation_reason
    assert res.answer.backend == "local:scripted"

    # keeper gate open but no per-call consent -> denied
    chain = Offliner(
        Scripted(0.1), cloud=CloudStub(), policy=GatePolicy(keeper_allows_cloud=True)
    )
    res = chain.answer("help", allow_cloud=False)
    assert res.receipt.escalated is False
    assert "per-call" in res.receipt.escalation_reason

    # both open -> escalated
    res = chain.answer("help", allow_cloud=True)
    assert res.receipt.escalated is True
    assert res.answer.backend == "cloud:stub"


def test_no_cloud_backend_means_no_escalation():
    chain = Offliner(
        Scripted(0.1), cloud=None, policy=GatePolicy(keeper_allows_cloud=True)
    )
    res = chain.answer("help", allow_cloud=True)
    assert res.receipt.escalated is False
    assert "no cloud backend" in res.receipt.escalation_reason


def test_prompt_is_scrubbed_before_backend_sees_it():
    seen = {}

    class Spy(Backend):
        name = "local:spy"

        def generate(self, prompt: str, context: str = "") -> Answer:
            seen["prompt"] = prompt
            return Answer(text="ok", confidence=0.9, backend=self.name)

    chain = Offliner(Spy())
    chain.answer("contact alice@example.com please")
    assert "alice@example.com" not in seen["prompt"]
    assert "[email redacted]" in seen["prompt"]


def test_rule_backend_is_honest_about_missing_context():
    backend = RuleBackend()
    with_ctx = backend.generate("summarize", context="LEVI is local-first.")
    assert with_ctx.confidence > 0.5
    no_ctx = backend.generate("summarize")
    assert no_ctx.confidence < 0.5
    assert "will not guess" in no_ctx.text


def test_receipt_carries_audit_trail():
    chain = Offliner(Scripted(0.9))
    res = chain.answer("hi")
    r = res.receipt
    assert r.backend == "local:scripted"
    assert r.confidence == 0.9
    assert r.redaction_applied is False
    assert r.prompt_chars == 2


# --- journal ---------------------------------------------------------------


def test_journal_logs_scrubbed_turn(tmp_path):
    journal = Journal(tmp_path / "turns.db")
    try:
        chain = Offliner(Scripted(0.9, "answer here"))
        res = chain.answer("login with password=hunter2 please")
        turn_id = journal.log(res, "login with password=hunter2 please", session="s1")
        assert turn_id == 1
        rows = journal.recent(session="s1")
        assert len(rows) == 1
        assert "hunter2" not in rows[0]["prompt"]
        assert rows[0]["backend"] == "local:scripted"
    finally:
        journal.close()


def test_journal_purge_enforces_retention(tmp_path):
    journal = Journal(tmp_path / "turns.db")
    try:
        import time

        chain = Offliner(Scripted(0.9))
        res = chain.answer("hi")
        journal.log(res, "hi")
        # backdate the row 60 days
        journal._conn.execute(
            "UPDATE offline_turns SET ts = ?", (time.time() - 60 * 86400,)
        )
        journal._conn.commit()
        removed = journal.purge(30)
        assert removed == 1
        assert journal.recent() == []
    finally:
        journal.close()


def test_journal_export_is_scrubbed_jsonl(tmp_path):
    import json

    journal = Journal(tmp_path / "turns.db")
    try:
        chain = Offliner(Scripted(0.9, "the answer"))
        res = chain.answer("email me at bob@example.com")
        journal.log(res, "email me at bob@example.com")
        out = tmp_path / "corpus.jsonl"
        n = journal.export_jsonl(out)
        assert n == 1
        rec = json.loads(out.read_text().splitlines()[0])
        roles = [m["role"] for m in rec["messages"]]
        assert roles == ["system", "user", "assistant"]
        assert "bob@example.com" not in out.read_text()
    finally:
        journal.close()
