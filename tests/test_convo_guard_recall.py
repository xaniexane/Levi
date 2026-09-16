"""Tests for thread-sense recall, guard, and rendering."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from levi.convo.state import DialogueState
from levi.convo.recall import recall_turns
from levi.convo.guard import check_contradictions, extract_claims
from levi.convo.render import render_block, render_constellation


def _long_convo():
    """~12 turns; turn 2 is about postgres, the rest drift elsewhere."""
    turns = [
        {
            "speaker": "user",
            "text": "How do I tune the old postgres database for writes?",
        },
        {
            "speaker": "levi",
            "text": "Raise shared_buffers and checkpoint_timeout for write-heavy postgres.",
        },
        {"speaker": "user", "text": "Now the nginx config needs a reload"},
        {"speaker": "levi", "text": "Use nginx -s reload after validating the config."},
        {"speaker": "user", "text": "What about backup retention windows?"},
        {"speaker": "levi", "text": "Keep 7 daily and 4 weekly snapshots."},
        {"speaker": "user", "text": "The drive space is getting tight"},
        {"speaker": "levi", "text": "42GB free should cover the weekend migration."},
        {"speaker": "user", "text": "Should I enable TLS on the load balancer?"},
        {"speaker": "levi", "text": "Yes, terminate TLS at the balancer."},
        {"speaker": "user", "text": "Remind me about the postgres write tuning"},
        {"speaker": "levi", "text": "placeholder current turn"},
    ]
    return turns


def test_recall_surfaces_early_relevant_turn():
    turns = _long_convo()
    # query from the second-to-last user turn; last 2 turns are excluded
    recalled = recall_turns("postgres write tuning", turns[:-1], limit=3)
    assert recalled, "recall should find something"
    idxs = [i for i, _, _ in recalled]
    assert 0 in idxs or 1 in idxs, "early postgres turn should surface, got %r" % idxs


def test_recall_skips_recent_turns():
    turns = _long_convo()
    recalled = recall_turns("TLS load balancer", turns, limit=5)
    idxs = [i for i, _, _ in recalled]
    assert all(i < len(turns) - 2 for i in idxs), "recent turns must be excluded"


def test_recall_empty_query():
    assert recall_turns("", [{"speaker": "u", "text": "hi"}]) == []
    assert recall_turns("  ", [{"speaker": "u", "text": "hi"}]) == []


def test_contradiction_direct_negation():
    facts = [{"text": "nginx runs on port 8080.", "turn": 3}]
    findings = check_contradictions("No — nginx does not run on port 8080.", facts)
    assert any(f["type"] == "direct_negation" for f in findings), findings


def test_contradiction_attribute_conflict():
    facts = [{"text": "nginx runs on port 8080.", "turn": 3}]
    findings = check_contradictions("nginx runs on port 9090.", facts)
    assert any(f["type"] == "attribute_conflict" for f in findings), findings


def test_no_conflict_on_different_predicates():
    # Same subject, different predicates ("runs on X" vs "is on my radar")
    # is not a contradiction.
    facts = [{"text": "The Nginx migration is on my radar.", "turn": 1}]
    findings = check_contradictions("Nginx runs on port 9090.", facts)
    assert findings == [], findings


def test_no_contradiction_on_agreement():
    facts = [{"text": "nginx runs on port 8080.", "turn": 3}]
    findings = check_contradictions(
        "Right, nginx runs on port 8080 as you said.", facts
    )
    assert findings == [], findings


def test_guard_empty_inputs():
    assert check_contradictions("", [{"text": "x is y.", "turn": 0}]) == []
    assert check_contradictions("x is y.", []) == []


def test_extract_claims():
    claims = extract_claims("Hello there. nginx runs on port 8080! What do you think?")
    assert any("8080" in c for c in claims)
    assert not any("Hello" in c for c in claims)


def test_render_block_compact():
    s = DialogueState()
    s.update("user", "migrating the server, nginx needs reconfiguring")
    s.update("levi", "I'll check the drive space first.")
    s.update("user", "back to the server thing — restart it")
    block = render_block(s)
    assert block.count("\n") + 1 <= 9, "block must stay compact:\n%s" % block
    assert "THREADS:" in block
    assert "REIGNITED" in block


def test_render_block_empty_state():
    assert render_block(DialogueState()) == ""


def test_constellation_renders():
    s = DialogueState()
    s.update("user", "migrating the server, nginx needs reconfiguring")
    s.update("levi", "I'll check the drive space first.")
    out = render_constellation(s)
    assert "thread-sense" in out
    assert "⏳" in out  # the open promise shows as a pending orbit
    assert isinstance(out, str) and len(out) > 50
