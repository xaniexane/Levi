"""Hermetic tests for levi.feedreader.

No live network: every test monkeypatches ``reader._http_fetch`` (the
single HTTP choke point) with canned responses. No real HOME writes:
``FeedStore()`` resolves paths at call time via os.path.expanduser("~"),
so patching HOME genuinely isolates.
"""

from __future__ import annotations

import pytest

from levi.feedreader import reader
from levi.feedreader.__main__ import main as cli_main
from levi.feedreader.reader import FeedError, FeedStore

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Test Feed</title>
<item><title>Post One</title><link>https://ex.com/p1</link>
<description>First</description></item>
<item><title>Post Two</title><link>https://ex.com/p2</link>
<description>Second</description></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Atom Feed</title>
<entry><title>Entry A</title><link href="https://ex.com/a"/>
<summary>Summary A</summary></entry>
</feed>"""

URL = "https://ex.com/feed.xml"
AURL = "https://ex.com/atom.xml"


def _herm(monkeypatch, tmp_path, router=None):
    monkeypatch.setenv("HOME", str(tmp_path))
    if router is not None:
        monkeypatch.setattr(reader, "_http_fetch", router)
    return FeedStore()


def _router_ok(url, etag, last_modified):
    if url == URL:
        return 200, RSS, {"etag": '"abc"'}, 0.05
    if url == AURL:
        return 200, ATOM, {}, 0.05
    raise AssertionError("unexpected url " + url)


def test_add_and_list(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.add(URL, "Test")
    feeds = st.list_feeds()
    assert len(feeds) == 1 and feeds[0]["url"] == URL
    with pytest.raises(FeedError):
        st.add(URL)  # duplicate


def test_remove(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.add(URL)
    st.remove(URL)
    assert st.list_feeds() == []


def test_poll_rss_and_items(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path, _router_ok)
    st.add(URL, "Test")
    reports = st.poll(force=True)
    assert reports[0]["ok"] and reports[0]["new_items"] == 2
    rows = st.items()
    assert len(rows) == 2
    assert rows[0]["title"] == "Post One"
    assert st.unread_count() == 2


def test_poll_atom(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path, _router_ok)
    st.add(AURL, "Atom")
    reports = st.poll(force=True)
    assert reports[0]["new_items"] == 1
    assert st.items()[0]["link"] == "https://ex.com/a"


def test_conditional_get_304(monkeypatch, tmp_path):
    calls = []

    def router(url, etag, last_modified):
        calls.append((etag, last_modified))
        return 304, b"", {}, 0.01

    st = _herm(monkeypatch, tmp_path, router)
    st.add(URL)
    reports = st.poll(force=True)
    assert reports[0]["ok"] and reports[0]["not_modified"]
    assert st.items() == []  # nothing new on 304


def test_no_duplicate_items_on_repoll(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path, _router_ok)
    st.add(URL)
    st.poll(force=True)
    st.poll(force=True)
    assert len(st.items()) == 2


def test_error_counts_fail_streak(monkeypatch, tmp_path):
    def router(url, etag, last_modified):
        raise ConnectionError("boom")

    st = _herm(monkeypatch, tmp_path, router)
    st.add(URL)
    r = st.poll(force=True)[0]
    assert not r["ok"] and r["fail_streak"] == 1
    h = st.health()[0]
    assert h["status"] == "degraded"
    st.poll(force=True); st.poll(force=True); st.poll(force=True); st.poll(force=True)
    assert st.health()[0]["status"] == "down"


def test_backoff_skips_without_force(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path, _router_ok)
    st.add(URL)
    st.poll(force=True)
    reports = st.poll()  # not forced: within _MIN_INTERVAL
    assert reports[0]["skipped"]


def test_mark_read_and_unread_views(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path, _router_ok)
    st.add(URL)
    st.poll(force=True)
    assert st.mark_read("https://ex.com/p1") == 1
    assert st.unread_count() == 1
    assert len(st.items(unread_only=True)) == 1
    assert st.items(unread_only=True)[0]["title"] == "Post Two"


def test_health_never_polled(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.add(URL)
    assert st.health()[0]["status"] == "never-polled"


def test_opml_roundtrip(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.add(URL, "Test")
    st.add(AURL, "Atom")
    xml_text = st.opml_export()
    assert "xmlUrl" in xml_text and URL in xml_text

    # fresh store in a second home: import must work there too
    monkeypatch.setenv("HOME", str(tmp_path / "home2"))
    st2 = FeedStore()
    assert st2.opml_import(xml_text) == 2
    assert st2.opml_import(xml_text) == 0  # idempotent
    assert {f["url"] for f in st2.list_feeds()} == {URL, AURL}


def test_opml_bad_xml(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    with pytest.raises(FeedError):
        st.opml_import("not xml at all <")


def test_cli_add_poll_items(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path, _router_ok)
    assert cli_main(["add", URL, "--title", "Test"]) == 0
    assert cli_main(["poll", "--force"]) == 0
    assert cli_main(["items"]) == 0
    out = capsys.readouterr().out
    assert "Post One" in out and "Post Two" in out
    assert cli_main(["health"]) == 0
    assert "ok" in capsys.readouterr().out


def test_cli_duplicate_add_fails(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    assert cli_main(["add", URL]) == 0
    assert cli_main(["add", URL]) == 1
