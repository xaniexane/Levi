"""Tests for the RSS/Atom sense connector.

Proofs for the laws in ``levi/connectors/rss.py``: observe-only polling,
honest baseline, edge-only events, stable identity dedupe, and the
deny-closed input gates. The network is faked — no real HTTP leaves the
test.
"""

import io
import urllib.error

import pytest

from levi.connectors import registry, rss
from levi.connectors.base import ConnectorError

RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <guid>item-1</guid>
      <title>First Item</title>
      <link>https://example.test/1</link>
      <pubDate>Thu, 24 Sep 2026 10:00:00 GMT</pubDate>
      <description><![CDATA[<p>Hello <b>world</b> one</p>]]></description>
    </item>
    <item>
      <guid>item-2</guid>
      <title>Second Item</title>
      <link>https://example.test/2</link>
      <pubDate>Thu, 24 Sep 2026 11:00:00 GMT</pubDate>
      <description>Plain text two</description>
    </item>
  </channel>
</rss>
"""

ATOM_FIXTURE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Test</title>
  <entry>
    <id>urn:test:a1</id>
    <title>Atom One</title>
    <link href="https://example.test/a1"/>
    <updated>2026-09-24T12:00:00Z</updated>
    <summary><p>Atom <i>summary</i></p></summary>
  </entry>
</feed>
"""

RSS_WITH_NEW_ITEM = RSS_FIXTURE.replace(
    "</channel>",
    """  <item>
      <guid>item-3</guid>
      <title>Third Item</title>
      <link>https://example.test/3</link>
      <description>Brand new</description>
    </item>
  </channel>""",
)


class _FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _serve(monkeypatch, body, status=200, error=None):
    def fake_urlopen(request, timeout=None):
        if error is not None:
            raise error
        return _FakeResponse(body, status)

    monkeypatch.setattr(rss.urllib.request, "urlopen", fake_urlopen)


def _poll(monkeypatch, body, **inputs):
    _serve(monkeypatch, body)
    inputs.setdefault("url", "https://example.test/feed.xml")
    inputs.setdefault("state", {})
    return registry.poll("rss", **inputs)


def test_registers_with_observe_only_risk():
    ids = {c.id for c in registry.list()}
    assert "rss" in ids
    desc = registry.get("rss")
    assert desc.risk == "info"
    assert set(desc.inputs) == {"url", "state", "max_items", "timeout"}


def test_first_poll_emits_honest_baseline_and_banks_items(monkeypatch):
    events, state = _poll(monkeypatch, RSS_FIXTURE.encode())
    assert len(events) == 1
    baseline = events[0]
    assert baseline["kind"] == "baseline"
    assert baseline["title"] == "Test Feed"
    assert baseline["item_count"] == 2
    assert set(state["seen"]) == {"item-1", "item-2"}


def test_steady_feed_emits_nothing(monkeypatch):
    _events, state = _poll(monkeypatch, RSS_FIXTURE.encode())
    events, _new_state = _poll(monkeypatch, RSS_FIXTURE.encode(), state=state)
    assert events == []


def test_new_item_emits_exactly_one_event(monkeypatch):
    _events, state = _poll(monkeypatch, RSS_FIXTURE.encode())
    events, new_state = _poll(monkeypatch, RSS_WITH_NEW_ITEM.encode(), state=state)
    assert len(events) == 1
    event = events[0]
    assert event["kind"] == "item"
    assert event["id"] == "item-3"
    assert event["title"] == "Third Item"
    assert event["link"] == "https://example.test/3"
    assert event["summary"] == "Brand new"
    assert "item-3" in new_state["seen"]


def test_summary_strips_markup(monkeypatch):
    events, _state = _poll(
        monkeypatch, ATOM_FIXTURE.encode(), state={"seen": ["unrelated"]}
    )
    assert len(events) == 1
    assert events[0]["kind"] == "item"
    assert events[0]["title"] == "Atom One"
    assert "<" not in events[0]["summary"]
    assert "Atom summary" in events[0]["summary"]


def test_identity_falls_back_to_link_then_title(monkeypatch):
    body = (
        b"<rss version='2.0'><channel><title>T</title>"
        b"<item><link>https://example.test/noguid</link>"
        b"<title>No Guid</title></item></channel></rss>"
    )
    _events, state = _poll(monkeypatch, body)
    assert state["seen"] == ["https://example.test/noguid"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"url": "ftp://example.test/feed.xml"},
        {"url": "file:///etc/passwd"},
        {"url": ""},
        {"url": 123},
        {"state": {"seen": "not-a-list"}},
        {"state": {"seen": [1, 2]}},
        {"state": "nope"},
        {"max_items": 0},
        {"max_items": 101},
        {"timeout": 0},
    ],
)
def test_deny_closed_inputs(monkeypatch, kwargs):
    _serve(monkeypatch, RSS_FIXTURE.encode())
    kwargs.setdefault("url", "https://example.test/feed.xml")
    kwargs.setdefault("state", {})
    with pytest.raises(ConnectorError):
        registry.poll("rss", **kwargs)


def test_malformed_xml_is_refused_not_half_run(monkeypatch):
    _serve(monkeypatch, b"<rss><channel><item>oops")
    with pytest.raises(ConnectorError):
        registry.poll("rss", url="https://example.test/feed.xml", state={})


def test_empty_body_is_refused(monkeypatch):
    _serve(monkeypatch, b"   \n")
    with pytest.raises(ConnectorError):
        registry.poll("rss", url="https://example.test/feed.xml", state={})


def test_http_error_is_refused(monkeypatch):
    _serve(
        monkeypatch,
        b"",
        error=urllib.error.HTTPError(
            "https://example.test/feed.xml", 404, "Not Found", {}, io.BytesIO()
        ),
    )
    with pytest.raises(ConnectorError):
        registry.poll("rss", url="https://example.test/feed.xml", state={})


def test_network_failure_is_refused(monkeypatch):
    _serve(
        monkeypatch,
        b"",
        error=urllib.error.URLError("connection refused"),
    )
    with pytest.raises(ConnectorError):
        registry.poll("rss", url="https://example.test/feed.xml", state={})
