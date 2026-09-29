"""Tests for levi.plumb — the user-owned dispatch table.

Laws under proof:
1. Deny-closed — no matching rule means no action (no default handler).
2. User-owned table — no rules ship enabled; default_rules() is opt-in.
3. Winnow before act — all patterns must agree on the same span and
   require-predicates must hold, or the rule does not fire.
4. No shell, no execution — engine returns decisions; unregistered ports
   refuse dispatch.
5. First match wins — file order is priority.
6. Local, stdlib-only — asserted by construction (imports are re/os).
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from levi.plumb import (  # noqa: E402
    PlumbError,
    PortRegistry,
    RuleError,
    default_rules,
    parse_rules,
    plumb,
)

URLS = """\
rule open-urls
  type: text
  match: https?://[^\\s<>"']+
  port: browser
  action: open-url $0
"""


def test_parse_minimal_rule():
    (rule,) = parse_rules(URLS)
    assert rule.name == "open-urls"
    assert rule.type == "text"
    assert rule.port == "browser"
    assert rule.action == "open-url $0"


def test_parse_rejects_unknown_directive():
    with pytest.raises(RuleError):
        parse_rules("rule x\n  frobnicate: yes\n  match: a\n  port: p\n  action: a\n")


def test_parse_rejects_missing_port_and_action():
    with pytest.raises(RuleError):
        parse_rules("rule x\n  match: a\n")
    with pytest.raises(RuleError):
        parse_rules("rule x\n  match: a\n  port: p\n")


def test_parse_rejects_bad_regex_at_parse_time():
    with pytest.raises(RuleError):
        parse_rules("rule x\n  match: (unclosed\n  port: p\n  action: a\n")


def test_parse_rejects_duplicate_rule_and_directive():
    with pytest.raises(RuleError):
        parse_rules(URLS + URLS)
    with pytest.raises(RuleError):
        parse_rules("rule x\n  match: a\n  port: p\n  port: q\n  action: a\n")


def test_parse_rejects_unknown_require_predicate():
    with pytest.raises(RuleError):
        parse_rules(
            "rule x\n  match: a\n  require: summon-demons yes\n"
            "  port: p\n  action: a\n"
        )


def test_no_match_returns_none_deny_closed():
    # Law 1: nothing matches -> None, never a guess.
    rules = parse_rules(URLS)
    assert plumb({"type": "text", "data": "just some words"}, rules) is None
    assert plumb({"type": "text", "data": ""}, rules) is None


def test_url_rule_matches_and_renders_capture():
    rules = parse_rules(URLS)
    result = plumb(
        {"type": "text", "data": "see https://example.com/page for details"},
        rules,
    )
    assert result is not None
    assert result.rule == "open-urls"
    assert result.port == "browser"
    assert result.action == "open-url https://example.com/page"
    assert result.data == "https://example.com/page"
    assert result.captures["0"] == "https://example.com/page"


def test_type_constraint_filters():
    rules = parse_rules(URLS)
    assert (
        plumb({"type": "image", "data": "https://example.com/x"}, rules) is None
    )
    # A rule with no type matches any message type.
    (rule,) = parse_rules("rule any\n  match: hi\n  port: p\n  action: a\n")
    assert plumb({"type": "image", "data": "hi"}, [rule]) is not None


def test_first_match_wins():
    rules = parse_rules(
        "rule first\n  match: abc\n  port: one\n  action: one\n"
        "rule second\n  match: abc\n  port: two\n  action: two\n"
    )
    result = plumb({"type": "text", "data": "abc"}, rules)
    assert result is not None and result.port == "one"


def test_winnow_picks_leftmost_longest_without_click():
    rules = parse_rules(
        "rule u\n  match: https?://\\S+\n  port: b\n  action: $0\n"
    )
    result = plumb(
        {"type": "text", "data": "a https://short.io and https://longer.example.com/x"},
        rules,
    )
    assert result is not None
    assert result.data == "https://short.io"


def test_winnow_prefers_match_touching_click():
    rules = parse_rules(
        "rule u\n  match: https?://\\S+\n  port: b\n  action: $0\n"
    )
    data = "a https://short.io and https://longer.example.com/x"
    click = data.index("longer")
    result = plumb({"type": "text", "data": data}, rules, click=click)
    assert result is not None
    assert result.data == "https://longer.example.com/x"


def test_second_pattern_must_match_same_span():
    # Law 3: a further pattern matching only part of the span fails the rule.
    rules = parse_rules(
        "rule strict\n"
        "  match: \\w+\\.gif\n"
        "  match: horse\n"
        "  port: p\n"
        "  action: a\n"
    )
    assert plumb({"type": "text", "data": "horse .gif"}, rules) is None
    # When the second pattern agrees on the whole span, the rule fires.
    rules2 = parse_rules(
        "rule strict\n"
        "  match: horse\\.gif\n"
        "  match: horse\\.gif\n"
        "  port: p\n"
        "  action: img $0\n"
    )
    result = plumb({"type": "text", "data": "see horse.gif here"}, rules2)
    assert result is not None and result.action == "img horse.gif"


def test_require_file_exists_predicate(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("hi")
    rules = parse_rules(
        "rule files\n"
        "  match: (?P<path>/[\\w\\-. /]+):(?P<line>\\d+)\n"
        "  require: file-exists {path}\n"
        "  port: editor\n"
        "  action: open-file {path} line={line}\n"
    )
    hit = plumb(
        {"type": "text", "data": f"error at {target}:42 broken"},
        rules,
    )
    assert hit is not None
    assert hit.action == f"open-file {target} line=42"
    # Law 3: predicate fails -> rule does not fire -> deny-closed.
    miss = plumb(
        {"type": "text", "data": "error at /no/such/file.txt:42 broken"},
        rules,
    )
    assert miss is None


def test_named_and_numbered_substitution():
    rules = parse_rules(
        "rule f\n"
        "  match: (\\w+)@(\\w+)\n"
        "  port: p\n"
        "  action: user=$1 host=$2 whole=$0\n"
    )
    result = plumb({"type": "text", "data": "mail bob@home now"}, rules)
    assert result is not None
    assert result.action == "user=bob host=home whole=bob@home"


def test_registry_dispatch_and_refusal():
    registry = PortRegistry()
    rules = parse_rules(URLS)
    result = plumb({"type": "text", "data": "https://example.com"}, rules)
    assert result is not None
    # Law 4: unregistered port refuses instead of guessing.
    with pytest.raises(PlumbError):
        registry.dispatch(result)
    seen = []
    registry.register("browser", seen.append)
    assert registry.dispatch(result) is None
    assert seen == [result]
    assert registry.ports() == ("browser",)


def test_registry_rejects_bad_registration():
    registry = PortRegistry()
    with pytest.raises(PlumbError):
        registry.register("", lambda r: None)
    with pytest.raises(PlumbError):
        registry.register("x", "not-callable")


def test_default_rules_are_opt_in_not_default():
    # Law 2: importing the module must not enable any dispatch.
    import levi.plumb as plumb_mod

    assert not hasattr(plumb_mod, "RULES")
    rules = default_rules()
    assert len(rules) == 2
    result = plumb({"type": "text", "data": "https://example.com"}, rules)
    assert result is not None and result.port == "browser"


def test_non_string_data_refused():
    rules = parse_rules(URLS)
    with pytest.raises(PlumbError):
        plumb({"type": "text", "data": 123}, rules)
