"""Hermetic tests for revival/agenda.py (Lotus Agenda rule engine)."""

from __future__ import annotations

import json

import pytest

from levi.revival.agenda import (
    Explanation,
    Rule,
    RuleEngine,
    default_rules,
)


def entry(content="", tags=None, source="journal", importance=0.5):
    return {
        "content": content,
        "tags": tags or [],
        "source": source,
        "importance": importance,
    }


def test_default_incident_rule_fires():
    engine = RuleEngine()
    category, expl = engine.file_entry(entry("The deploy failed with a traceback."))
    assert category == "incidents"
    assert expl.rule_name == "incidents"


def test_explanation_names_rule_and_matched_conditions():
    engine = RuleEngine()
    _, expl = engine.file_entry(entry("We decided to ship the new parser."))
    assert isinstance(expl, Explanation)
    assert expl.rule_name == "decisions"
    assert expl.matched  # names which conditions matched
    assert any("decided" in m for m in expl.matched)
    assert "decisions" in expl.summary()
    assert "filed as 'decisions'" in expl.summary()


def test_priority_resolves_conflicts_incidents_beat_gratitude():
    engine = RuleEngine()
    category, expl = engine.file_entry(
        entry("Thanks for the patch — but it caused an error on prod.")
    )
    assert category == "incidents"
    assert expl.rule_name == "incidents"
    # runner-up is visible: the glass cockpit shows what else matched
    assert "gratitude" in expl.candidates


def test_fail_open_uncategorized_never_silent():
    engine = RuleEngine()
    category, expl = engine.file_entry(entry("A quiet walk at dusk."))
    assert category == "uncategorized"
    assert expl.rule_name is None
    assert "fail-open" in expl.summary()


def test_non_dict_entry_fail_open_never_raises():
    engine = RuleEngine()
    category, expl = engine.file_entry(None)
    assert category == "uncategorized"
    assert expl.rule_name is None
    category, _ = engine.file_entry(42)
    assert category == "uncategorized"


def test_rule_crud():
    engine = RuleEngine(rules=[])
    rule = Rule("work", {"tags": ["work"]}, "work-stuff", priority=5)
    engine.add_rule(rule)
    assert engine.get_rule("work") is rule
    assert engine.list_rules() == [rule]
    with pytest.raises(ValueError, match="already exists"):
        engine.add_rule(Rule("work", {"tags": ["w"]}, "x"))
    removed = engine.remove_rule("work")
    assert removed is rule
    with pytest.raises(ValueError, match="no rule named"):
        engine.remove_rule("work")


def test_update_rule():
    engine = RuleEngine(rules=[])
    engine.add_rule(Rule("a", {"tags": ["x"]}, "cat-a", priority=1))
    engine.update_rule("a", category="cat-b", priority=9)
    assert engine.get_rule("a").category == "cat-b"
    assert engine.get_rule("a").priority == 9


def test_bad_rule_rejected_at_construction():
    with pytest.raises(ValueError, match="unknown condition"):
        Rule("bad", {"frobnicator": True}, "x")
    with pytest.raises(ValueError, match="invalid regex"):
        Rule("bad", {"regex": ["[unclosed"]}, "x")
    with pytest.raises(ValueError, match="at least one condition"):
        Rule("bad", {}, "x")


def test_audit_log_records_every_decision(tmp_path):
    audit = tmp_path / "audit.jsonl"
    engine = RuleEngine(audit_path=audit)
    engine.file_entry(entry("An error occurred."))
    engine.file_entry(entry("A quiet walk."))
    log = engine.audit_log()
    assert len(log) == 2
    assert log[0]["category"] == "incidents"
    assert log[0]["rule_name"] == "incidents"
    assert log[1]["category"] == "uncategorized"
    assert log[1]["rule_name"] is None
    # durable: JSONL lines on disk
    lines = audit.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["category"] == "incidents"


def test_json_persistence_round_trip(tmp_path):
    engine = RuleEngine()
    engine.add_rule(Rule("custom", {"source": "automation"}, "auto", priority=200))
    path = engine.save(tmp_path / "rules.json")
    loaded = RuleEngine.load(path)
    category, expl = loaded.file_entry(entry("x", source="automation"))
    assert category == "auto"
    assert expl.rule_name == "custom"
    # defaults survive too
    assert loaded.get_rule("incidents") is not None


def test_regex_and_importance_conditions():
    engine = RuleEngine(rules=[])
    engine.add_rule(Rule("big", {"min_importance": 0.9}, "big", priority=1))
    engine.add_rule(Rule("todo", {"regex": [r"\btodo\b"]}, "todos", priority=2))
    cat, _ = engine.file_entry(entry("remember todo: buy milk", importance=0.1))
    assert cat == "todos"
    cat, _ = engine.file_entry(entry("life-changing insight", importance=0.95))
    assert cat == "big"


def test_default_rules_exist_and_prioritized():
    rules = default_rules()
    assert {r.name for r in rules} >= {"incidents", "decisions", "learnings", "ideas"}
    by_name = {r.name: r for r in rules}
    assert by_name["incidents"].priority > by_name["ideas"].priority


def test_explain_does_not_audit():
    engine = RuleEngine(rules=[])
    engine.add_rule(Rule("a", {"tags": ["x"]}, "ax", priority=1))
    expl = engine.explain(entry("hi", tags=["x"]))
    assert expl.rule_name == "a"
    assert engine.audit_log() == []
