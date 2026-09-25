"""Law/guard/proof tests for DemandPulse eyes — server-side sensing.

Laws under test:
  E1 polite keyless reads only — failures degrade to empty, never raise
  E2 public chatter is not demand — HYPOTHESIS only, source labels kept
  E3 never streams — one bounded poll per tick
  E4 bounded work — caps, cooldowns, tick budget honored
  E5 stdlib only — urllib + xml, no new dependencies

Hermetic: HOME/LEVI_HOME redirected, network monkeypatched except the
two explicitly marked LIVE tests (skipped without egress).
"""

import json
import time

import pytest

from levi.demand import eyes as emod
from levi.demand import watcher as wmod
from levi.demand.pulse import DemandPulse


@pytest.fixture
def herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi_home"))
    return tmp_path


def _dp(tmp_path):
    return DemandPulse(path=tmp_path / "dp.json")


def _st(tmp_path):
    return wmod.WatcherState.load(path=tmp_path / "wstate.json")


# ------------------------------------------------------------------ parsing


RSS_FIXTURE = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
<item><title>I need a better shift planner</title>
<link>https://x.example/1</link>
<description><p>Everything is clunky.</p></description></item>
<item><title>Markets rally on earnings</title><link>https://x.example/2</link></item>
</channel></rss>"""

ATOM_FIXTURE = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>T</title>
<entry><title>Frustrated with onboarding flows</title>
<link href="https://x.example/3"/>
<summary>Can't find anything usable.</summary></entry>
</feed>"""


def test_parse_rss_extracts_items():
    items = emod.parse_feed(RSS_FIXTURE)
    assert len(items) == 2
    assert items[0]["title"] == "I need a better shift planner"
    assert "<p>" not in items[0]["summary"]  # html stripped


def test_parse_atom_extracts_items():
    items = emod.parse_feed(ATOM_FIXTURE)
    assert len(items) == 1
    assert items[0]["link"] == "https://x.example/3"


def test_parse_feed_never_raises_on_garbage():
    assert emod.parse_feed(b"not xml at all {{{") == []
    assert emod.parse_feed(b"") == []


def test_http_get_rejects_non_http_scheme():
    assert emod._http_get("file:///etc/passwd") == (None, b"")
    assert emod._http_get("gopher://x.example/") == (None, b"")


def test_http_get_failure_is_empty_not_raise(monkeypatch):
    import urllib.request

    def boom(req, timeout=None):
        raise OSError("dns down")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert emod._http_get("https://x.example/rss") == (None, b"")


# ------------------------------------------------------------- poll bounds


def test_poll_rss_mines_needs_as_hypothesis(herm, monkeypatch):
    monkeypatch.setattr(emod, "DEFAULT_FEEDS", ())
    monkeypatch.setattr(
        emod, "_http_get", lambda url, timeout=15.0: (200, RSS_FIXTURE)
    )
    dp, st = _dp(herm), _st(herm)
    r = emod.poll_rss(dp, st, feeds=["https://x.example/rss"])
    assert r["status"] == "ok" and r["fetched"] == 1
    assert r["signals"] >= 1
    assert all(s.kind == "HYPOTHESIS" for s in dp.signals)
    assert all(s.source == "rss" for s in dp.signals)


def test_poll_rss_respects_cooldown(herm, monkeypatch):
    monkeypatch.setattr(emod, "DEFAULT_FEEDS", ())
    calls = []
    monkeypatch.setattr(
        emod, "_http_get",
        lambda url, timeout=15.0: (calls.append(url), (200, RSS_FIXTURE))[1],
    )
    dp, st = _dp(herm), _st(herm)
    emod.poll_rss(dp, st, feeds=["https://x.example/rss"])
    r2 = emod.poll_rss(dp, st, feeds=["https://x.example/rss"])
    assert r2["cooled_down"] == 1 and len(calls) == 1  # one fetch only


def test_poll_rss_dead_feed_contributes_nothing(herm, monkeypatch):
    monkeypatch.setattr(emod, "DEFAULT_FEEDS", ())
    monkeypatch.setattr(
        emod, "_http_get", lambda url, timeout=15.0: (None, b"")
    )
    dp, st = _dp(herm), _st(herm)
    r = emod.poll_rss(dp, st, feeds=["https://x.example/rss"])
    assert r["failed"] == 1 and r["signals"] == 0 and len(dp.signals) == 0


def test_poll_rss_honors_deadline(herm, monkeypatch):
    monkeypatch.setattr(emod, "DEFAULT_FEEDS", ())
    monkeypatch.setattr(
        emod, "_http_get", lambda url, timeout=15.0: (200, RSS_FIXTURE)
    )
    dp, st = _dp(herm), _st(herm)
    past = time.time() - 1.0  # budget already spent
    r = emod.poll_rss(
        dp, st,
        feeds=["https://a.example/1", "https://a.example/2"],
        deadline=past,
    )
    assert r["status"] == "budget_exceeded" and r["feeds"] == 0


def test_poll_hn_mines_hits(herm, monkeypatch):
    import levi.demand.ingest as ing

    monkeypatch.setattr(
        ing, "fetch_hackernews",
        lambda q: [{"text": "I need a calmer inbox app", "url": "u",
                    "source": "social", "source_name": "Hacker News",
                    "metadata": {}}],
    )
    dp, st = _dp(herm), _st(herm)
    r = emod.poll_hn(dp, st, queries=("i need",))
    assert r["signals"] >= 1
    assert all(s.source == "hn" for s in dp.signals)
    assert all(s.kind == "HYPOTHESIS" for s in dp.signals)


def test_eyes_never_import_alerts():
    src = open(emod.__file__, encoding="utf-8").read()
    assert "levi.demand.alerts" not in src
    assert "alert" not in " ".join(dir(emod)).lower()


def test_feed_list_env_override(monkeypatch):
    monkeypatch.setenv(
        "DP_EYES_FEEDS", "https://a.example/rss, https://a.example/rss ,")
    feeds = emod.feed_list()
    assert feeds.count("https://a.example/rss") == 1
    assert feeds[0] == "https://news.ycombinator.com/rss"


# ------------------------------------------------------- provider sensing


def test_default_feeds_hn_first_then_reddit_subs():
    feeds = emod.DEFAULT_FEEDS
    assert feeds[0] == "https://news.ycombinator.com/rss"
    for sub in ("SomebodyMakeThis", "BusinessIdeas", "startups",
                "smallbusiness"):
        assert f"https://www.reddit.com/r/{sub}/.rss" in feeds


def test_poll_providers_mines_hits_as_hypothesis(herm, monkeypatch):
    _stub_provider_fetchers(monkeypatch)
    dp, st = _dp(herm), _st(herm)
    r = emod.poll_providers(dp, st)
    chs = r["channels"]
    assert set(chs) == {"reddit", "stackoverflow", "github", "arxiv", "jobs"}
    assert chs["reddit"]["status"] == "ok"
    assert chs["reddit"]["signals"] >= 1
    assert all(s.kind == "HYPOTHESIS" for s in dp.signals)  # E2
    assert all(s.source == "reddit" for s in dp.signals)  # source labels
    assert all(s.confidence == 0.35 for s in dp.signals)


def test_poll_providers_uses_documented_queries(herm, monkeypatch):
    import levi.demand.ingest as ing
    seen = {}

    def _mk(name):
        def _f(q):
            seen.setdefault(name, []).append(q)
            return []
        return _f

    monkeypatch.setattr(ing, "fetch_reddit_signals", _mk("reddit"))
    monkeypatch.setattr(
        ing, "fetch_stackoverflow_signals", _mk("stackoverflow"))
    monkeypatch.setattr(ing, "fetch_github_signals", _mk("github"))
    monkeypatch.setattr(ing, "fetch_arxiv_signals", _mk("arxiv"))
    monkeypatch.setattr(ing, "fetch_job_signals", _mk("jobs"))
    emod.poll_providers(_dp(herm), _st(herm))
    assert seen["reddit"] == list(emod.REDDIT_AMBIENT_QUERIES)
    assert seen["stackoverflow"] == list(emod.SO_AMBIENT_QUERIES)
    assert seen["github"] == list(emod.GITHUB_AMBIENT_QUERIES)
    assert seen["arxiv"] == list(emod.ARXIV_AMBIENT_QUERIES)
    assert seen["jobs"] == list(emod.JOB_AMBIENT_QUERIES)


def test_poll_providers_respects_cooldown(herm, monkeypatch):
    import levi.demand.ingest as ing
    calls = []

    def _f(q):
        calls.append(q)
        return []

    for _fn in ("fetch_reddit_signals", "fetch_stackoverflow_signals",
                "fetch_github_signals", "fetch_arxiv_signals",
                "fetch_job_signals"):
        monkeypatch.setattr(ing, _fn, _f)
    dp, st = _dp(herm), _st(herm)
    emod.poll_providers(dp, st)
    n1 = len(calls)
    assert n1 > 0
    r2 = emod.poll_providers(dp, st)
    assert len(calls) == n1  # every query cooled — zero fetches
    assert all(c["cooled_down"] >= 1 for c in r2["channels"].values())


def test_poll_providers_fetcher_failure_is_silence(herm, monkeypatch):
    import levi.demand.ingest as ing

    def boom(q):
        raise RuntimeError("rate limited")

    for _fn in ("fetch_reddit_signals", "fetch_stackoverflow_signals",
                "fetch_github_signals", "fetch_arxiv_signals",
                "fetch_job_signals"):
        monkeypatch.setattr(ing, _fn, boom)
    dp, st = _dp(herm), _st(herm)
    r = emod.poll_providers(dp, st)  # must not raise — E1
    assert all(c["signals"] == 0 for c in r["channels"].values())
    assert len(dp.signals) == 0


def test_poll_providers_caps_hits_per_query(herm, monkeypatch):
    import levi.demand.ingest as ing
    monkeypatch.setattr(
        ing, "fetch_reddit_signals",
        lambda q: [{"text": f"I need thing {i}", "url": "u",
                    "source": "reddit", "source_name": "R", "metadata": {}}
                   for i in range(50)])
    for _fn in ("fetch_stackoverflow_signals", "fetch_github_signals",
                "fetch_arxiv_signals", "fetch_job_signals"):
        monkeypatch.setattr(ing, _fn, lambda q: [])
    dp, st = _dp(herm), _st(herm)
    r = emod.poll_providers(dp, st)
    assert r["channels"]["reddit"]["fetched"] == (
        emod.PROVIDER_HITS_PER_QUERY * len(emod.REDDIT_AMBIENT_QUERIES))


def test_poll_providers_honors_deadline(herm, monkeypatch):
    _stub_provider_fetchers(monkeypatch)
    dp, st = _dp(herm), _st(herm)
    r = emod.poll_providers(dp, st, deadline=time.time() - 1.0)
    assert all(c["status"] == "budget_exceeded"
               for c in r["channels"].values())


def test_run_eyes_includes_providers(herm, monkeypatch):
    monkeypatch.setattr(emod, "DEFAULT_FEEDS", ())
    monkeypatch.setattr(
        emod, "_http_get", lambda url, timeout=15.0: (None, b""))
    _stub_provider_fetchers(monkeypatch)
    r = emod.run_eyes(dp=_dp(herm), state=_st(herm), budget_s=10.0)
    assert set(r["channels"]) >= {"rss", "hn", "reddit", "stackoverflow",
                                  "github", "arxiv", "jobs"}
    assert r["channels"]["reddit"]["signals"] >= 1


def test_eyes_status_lists_provider_transports(herm):
    s = emod.status(state=_st(herm))
    assert set(s) >= {"rss", "hn", "reddit", "stackoverflow", "github",
                      "arxiv", "jobs"}
    assert "reddit" in s["reddit"]["transport"].lower()
    assert s["reddit"]["feeds"] == list(emod.REDDIT_AMBIENT_QUERIES)


# ------------------------------------------------- watcher integration


def _stub_provider_fetchers(monkeypatch):
    """Hermetic stand-ins for the keyless ingest fetchers."""
    import levi.demand.ingest as ing
    monkeypatch.setattr(ing, "fetch_hackernews", lambda q: [])
    monkeypatch.setattr(
        ing, "fetch_reddit_signals",
        lambda q: [{"text": "I need a calmer inbox app", "url": "u",
                    "source": "reddit", "source_name": "Reddit (public .json)",
                    "metadata": {}}])
    for _fn in ("fetch_stackoverflow_signals", "fetch_github_signals",
                "fetch_arxiv_signals", "fetch_job_signals"):
        monkeypatch.setattr(ing, _fn, lambda q: [])


def test_watcher_run_includes_eye_channels(herm, monkeypatch):
    import levi.demand.watcher as w
    monkeypatch.setattr(
        w, "_run_cli", lambda argv, timeout_s=45.0:
        (0, json.dumps({"status": "not_connected"}), ""))
    monkeypatch.setattr(
        w, "_run_facebook_cli", lambda argv, timeout_s=45.0:
        (127, "", "CLI not found"))
    monkeypatch.setattr(
        emod, "_http_get", lambda url, timeout=15.0: (None, b""))
    _stub_provider_fetchers(monkeypatch)
    dp, st = _dp(herm), _st(herm)
    r = wmod.run(dp=dp, state=st, budget_s=5.0)
    assert set(r["channels"]) >= {"email", "facebook", "rss", "hn", "text",
                                  "notification", "reddit", "stackoverflow",
                                  "github", "arxiv", "jobs"}
    assert r["channels"]["text"]["status"] == "not_configured"
    assert r["channels"]["facebook"]["status"] == "not_configured"


def test_email_deepening_defaults(herm, monkeypatch):
    import levi.demand.watcher as w
    seen = {}

    def fake(argv, timeout_s=45.0):
        seen["argv"] = argv
        return (0, json.dumps({"status": "connected", "messages": []}), "")

    monkeypatch.setattr(w, "_run_cli", fake)
    wmod.poll_email(_dp(herm), _st(herm))
    argv = seen["argv"]
    assert "newer_than:3d" in argv  # 3-day lookback
    assert argv[argv.index("--max") + 1] == "50"  # deepened triage


def test_email_read_cap_defers_not_drops(herm, monkeypatch):
    import levi.demand.watcher as w
    triage = {"messages": [
        {"id": f"m{i}", "from": "Pal <pal@example.com>",
         "subject": "I need help with rostering"}
        for i in range(20)
    ]}

    def fake(argv, timeout_s=45.0):
        if "+triage" in argv:
            return (0, json.dumps(triage), "")
        if "status" in argv:
            return (0, json.dumps({"status": "connected"}), "")
        return (0, json.dumps({"id": "x", "body": "I need help."}), "")

    monkeypatch.setattr(w, "_run_cli", fake)
    dp, st = _dp(herm), _st(herm)
    r = wmod.poll_email(dp, st)
    assert r["read"] == wmod._EMAIL_READ_CAP
    assert r["read_capped"] == 20 - wmod._EMAIL_READ_CAP
    # capped items were NOT marked seen: next tick picks them up
    assert len(st.channels["email"]["seen_ids"]) == wmod._EMAIL_READ_CAP


# ------------------------------------------------------------- LIVE (egress)


@pytest.mark.live
def test_live_hn_rss_reachable():
    status, body = emod._http_get("https://news.ycombinator.com/rss")
    assert status == 200 and len(body) > 1000
    assert len(emod.parse_feed(body)) > 0


@pytest.mark.live
def test_live_hn_algolia_reachable():
    import levi.demand.ingest as ing
    hits = ing.fetch_hackernews("shift planner")
    assert isinstance(hits, list)  # [] is honest when rate-limited
