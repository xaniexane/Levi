"""Tests for levi.bot.switchboard — the inbound router bot."""

from __future__ import annotations

from levi.bot.switchboard import route, route_summary, score_module, tokenize


def test_tokenize_drops_stopwords():
    assert tokenize("What is the battery level?") == ["battery", "level"]


def test_route_finds_daemon_for_heartbeat():
    routes = route("is the daemon heartbeat still running?")
    assert routes[0].module == "daemon"
    assert any("daemon.heartbeat" in m for m in routes[0].matched)


def test_route_finds_memory_for_remember():
    routes = route("remember that I like dark mode")
    assert routes[0].module == "memory-store"


def test_route_finds_finance_for_stocks():
    routes = route("what is the stock price today")
    assert routes[0].module == "finance"


def test_route_finds_automation_for_schedule():
    routes = route("schedule a daily routine for my minions")
    assert routes[0].module == "automation"


def test_unrouted_is_honest():
    routes = route("xylophone quasar banana")
    assert len(routes) == 1
    assert routes[0].module == "unrouted"
    assert routes[0].routed is False


def test_empty_text_is_unrouted():
    routes = route("   ")
    assert routes[0].module == "unrouted"


def test_top_n_limits_candidates():
    routes = route("daemon memory finance king service", top_n=2)
    assert len(routes) <= 2
    assert all(r.routed for r in routes)


def test_confidence_stays_in_range():
    for r in route("build the factory automation for memory finance king services"):
        assert 0.0 <= r.confidence <= 1.0
        assert r.score >= 1


def test_summary_mentions_unrouted():
    summary = route_summary(route("xylophone quasar banana"))
    assert "unrouted" in summary
    assert "no guess" in summary


def test_score_module_uses_signal_hints():
    scored = score_module("integrations", tokenize("check my phone battery"))
    assert scored.score >= 1
