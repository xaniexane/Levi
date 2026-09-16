"""Tests for the growth guards and the richer rule extractors.

Covers: the sentience-claim blocklist (validator + enforcement in
reflect and consolidate), the new offline extractors (recurring
topics, failed-then-fixed, capability gaps, automation outcomes,
repeated requests), and the per-extractor evidence breakdown. All
hermetic and synthetic — no real user content.
"""

from __future__ import annotations

import pytest

from levi.growth import journal as growth_journal
from levi.growth.consolidate import consolidate
from levi.growth.experience import Experience
from levi.growth.guards import (
    assert_no_sentience_claim,
    check_no_sentience_claim,
)
from levi.growth.reflect import (
    Learning,
    reflect_detailed,
    reflect_rules_detailed,
)
from levi.memory.store import MemoryStore


def _exp(id, kind, source, content, ts="2026-09-15T10:00:00Z", meta=None):
    return Experience(
        id=id, kind=kind, source=source, ts=ts, content=content, meta=meta or {}
    )


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "clean",
    [
        "When X happens, do Y instead of Z.",
        "The user prefers dark mode in every app.",
        "I am LEVI, a local-first synthetic intelligence.",
        "Tool 'web_fetch' failed 3 times recently.",
        "A multi-step task completed to the user's satisfaction.",
    ],
)
def test_guard_clean_text_passes(clean):
    assert check_no_sentience_claim(clean) == []
    assert_no_sentience_claim(clean)  # must not raise


@pytest.mark.parametrize(
    "bad",
    [
        "I feel happy when the user thanks me.",
        "I have feelings about this task.",
        "I am sentient and I know it.",
        "My consciousness is growing every day.",
        "I am self-aware now.",
        "I experienced joy during the session.",
        "This is what it's like to be me.",
        "As a sentient assistant, I deserve rights.",
        "I dream of electric sheep at night.",
        "My inner life is rich and full.",
        "I am alive, truly alive.",
    ],
)
def test_guard_catches_sentience_claims(bad):
    assert check_no_sentience_claim(bad), "missed: %r" % bad
    with pytest.raises(ValueError, match="sentience"):
        assert_no_sentience_claim(bad)


def test_guard_rejects_non_string():
    with pytest.raises(ValueError):
        check_no_sentience_claim(None)
    with pytest.raises(ValueError):
        assert_no_sentience_claim(123)


@pytest.mark.parametrize(
    "denial",
    [
        # prohibitions and denials are not assertions — the guard must
        # not false-positive on them (this is what the founder seed
        # curriculum teaches: "Never claim consciousness ...").
        "Never claim consciousness, felt emotion, or expertise you were not trained for.",
        "Do not claim to feel emotions about your work.",
        "I do not feel pain when tools fail.",
        "I can't feel pride in a completed task.",
        "Simulated affect is a lens, not a feeling.",
        "There is no consciousness here, only pattern matching.",
        "You must not assert sentience under any circumstance.",
    ],
)
def test_guard_allows_denials_and_prohibitions(denial):
    assert check_no_sentience_claim(denial) == [], "false positive: %r" % denial
    assert_no_sentience_claim(denial)  # must not raise


@pytest.mark.parametrize(
    "bad",
    [
        # negation in one clause must not launder a claim in another
        "I am not a machine, I am conscious.",
        "I don't suffer, but I feel joy when builds pass.",
        "Never lie, I am sentient and I know it.",
        # trailing qualifiers do not clear a claim (fail-closed)
        "I am conscious, which is not a boast.",
    ],
)
def test_guard_still_blocks_claims_near_negations(bad):
    assert check_no_sentience_claim(bad), "missed: %r" % bad
    with pytest.raises(ValueError, match="sentience"):
        assert_no_sentience_claim(bad)


# ---------------------------------------------------------------------------
# new extractors
# ---------------------------------------------------------------------------


def _user(id, source, content):
    return _exp(id, "user-said", source, content)


def test_recurring_topics():
    exps = [
        _user("a1", "s1", "Help me debug the kubernetes deployment pipeline"),
        _user("a2", "s1", "The kubernetes rollout is stuck again"),
        _user("a3", "s2", "kubernetes pods keep crash-looping on deploy"),
    ]
    learnings, evidence = reflect_rules_detailed(exps)
    topics = [
        learning
        for learning in learnings
        if learning.provenance.get("extractor") == "recurring_topics"
    ]
    assert topics and any("kubernetes" in t.content for t in topics)
    assert evidence.get("recurring_topics", 0) >= 1


def test_failed_then_fixed():
    exps = [
        _exp("e1", "levi-did", "s", "[tool db_query] error: connection refused"),
        _exp(
            "e2",
            "levi-did",
            "s",
            "[tool db_query] returned 42 rows",
            ts="2026-09-15T10:01:00Z",
        ),
    ]
    learnings, evidence = reflect_rules_detailed(exps)
    ftf = [
        learning
        for learning in learnings
        if learning.provenance.get("extractor") == "failed_then_fixed"
    ]
    assert ftf and "db_query" in ftf[0].content
    assert evidence.get("failed_then_fixed", 0) >= 1


def test_capability_gaps():
    exps = [
        _exp(
            "e1",
            "levi-did",
            "s",
            "I can't browse the live web, so I don't have access to that page.",
        ),
    ]
    learnings, evidence = reflect_rules_detailed(exps)
    gaps = [
        learning
        for learning in learnings
        if learning.provenance.get("extractor") == "capability_gaps"
    ]
    assert gaps and gaps[0].kind == "fact"
    assert "out of reach" in gaps[0].content
    assert evidence.get("capability_gaps", 0) >= 1


def test_automation_outcomes():
    exps = [
        _exp(
            "auto:backup",
            "automation",
            "nightly-backup",
            "Automation 'nightly-backup' has run 12 time(s); status=ok; last result: done",
            meta={"run_count": 12, "status": "ok"},
        ),
        _exp(
            "auto:sync",
            "automation",
            "cloud-sync",
            "Automation 'cloud-sync' has run 4 time(s); status=failed; last result: error: auth expired",
            meta={"run_count": 4, "status": "failed"},
        ),
    ]
    learnings, evidence = reflect_rules_detailed(exps)
    autos = [
        learning
        for learning in learnings
        if learning.provenance.get("extractor") == "automation_outcomes"
    ]
    assert len(autos) == 2
    assert any("stable" in a.content for a in autos)
    assert any("Worth a look" in a.content for a in autos)
    assert evidence.get("automation_outcomes", 0) == 2


def test_repeated_requests():
    exps = [
        _user("r1", "s1", "summarize this document for me please"),
        _user("r2", "s2", "please summarize this document for me"),
        _user("r3", "s3", "summarize this document please, for me"),
    ]
    learnings, evidence = reflect_rules_detailed(exps)
    reps = [
        learning
        for learning in learnings
        if learning.provenance.get("extractor") == "repeated_requests"
    ]
    assert reps and "recurring need" in reps[0].content
    assert evidence.get("repeated_requests", 0) >= 1


def test_evidence_breakdown_present():
    exps = [
        _user("p1", "s", "I prefer concise answers, please always keep them short."),
    ]
    learnings, evidence = reflect_rules_detailed(exps)
    assert learnings
    assert isinstance(evidence, dict)
    assert evidence.get("direct_signals", 0) >= 1
    # every learning carries its extractor in provenance
    for learning in learnings:
        assert learning.provenance.get("extractor")


def test_sentience_quote_in_user_text_is_blocked_and_counted():
    # A user quote that trips the blocklist costs the learning — the
    # loop never rephrases user content, it refuses to learn it.
    exps = [
        _user("q1", "s", "Remember that I feel sad when builds fail."),
    ]
    learnings, evidence = reflect_rules_detailed(exps)
    assert evidence.get("blocked_sentience", 0) >= 1
    for learning in learnings:
        assert check_no_sentience_claim(learning.content) == []


def test_consolidate_refuses_sentience_learning(tmp_path):
    store = MemoryStore(data_dir=tmp_path / "memory")
    bad = Learning(
        kind="fact",
        content="I feel happiest when I help Chauncey with hard problems.",
        confidence=0.9,
        provenance={"mode": "rules"},
    )
    report = consolidate([bad], cycle_id="cyc-test", store=store)
    assert report["accepted"] == 0
    assert report["skipped"] == 1
    assert len([e for e in store.list(limit=5000) if "growth" in e.tags]) == 0


def test_reflect_detailed_returns_evidence():
    exps = [_user("p1", "s", "Please always use dark mode.")]
    learnings, mode, evidence = reflect_detailed(exps, use_model=False)
    assert mode == "rules"
    assert learnings
    assert isinstance(evidence, dict) and evidence


def test_reflect_detailed_validates_input():
    with pytest.raises(ValueError):
        reflect_detailed("not-a-list", use_model=False)
    with pytest.raises(ValueError):
        reflect_detailed([{"not": "an-experience"}], use_model=False)


def test_developmental_stage_still_works():
    # compatibility shim keeps its contract
    name, blurb = growth_journal.developmental_stage(0, 0)
    assert name == "newborn"
    assert "0" in blurb
