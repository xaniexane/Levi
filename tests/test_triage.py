"""Tests for the triage bot (scoring + ranked queue).

Hermetic: every test runs with an isolated LEVI_HOME in tmp_path.
"""

from __future__ import annotations

import pytest

from levi.bot import triage
from levi.bot.triage import TriageQueue, bucket, score_item


@pytest.fixture()
def home(tmp_path, monkeypatch):
    h = tmp_path / "levi-home"
    h.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h))
    return h


# ---------------------------------------------------------------- scoring


def test_urgent_title_scores_now():
    scored = score_item(
        "URGENT: prod outage, database down now", "everything is broken"
    )
    assert scored.bucket == "now"
    assert scored.score >= 70
    assert any("urgency" in r for r in scored.reasons)


def test_plain_note_stays_later():
    scored = score_item("saw an interesting bird at the park", "it was blue")
    assert scored.bucket == "later"
    assert scored.score == 20


def test_time_pressure_pushes_up():
    base = score_item("please review the draft")
    pressured = score_item("please review the draft today")
    assert pressured.score > base.score
    assert pressured.bucket == "soon"


def test_known_source_bonus():
    unknown = score_item("heads up", source="stranger")
    known = score_item("heads up", source="chauncey", known_sources=("chauncey",))
    assert known.score == unknown.score + 15


def test_staleness_decays():
    fresh = score_item("reminder: water the plants", age_hours=1.0)
    stale = score_item("reminder: water the plants", age_hours=72.0)
    assert stale.score < fresh.score


def test_bucket_boundaries():
    assert bucket(70) == "now"
    assert bucket(69) == "soon"
    assert bucket(40) == "soon"
    assert bucket(39) == "later"


def test_empty_title_rejected():
    with pytest.raises(ValueError):
        triage.Item(title="  ")


# ----------------------------------------------------------------- queue


def test_add_scores_and_receipts(home):
    q = TriageQueue()
    item = q.add("URGENT: server outage now", source="ops")
    assert item.bucket == "now"
    assert triage.queue_path().exists()
    assert triage.receipts_path().exists()
    pending = q.list_pending()
    assert [i.id for i in pending] == [item.id]


def test_next_pops_highest_priority_first(home):
    q = TriageQueue()
    q.add("low priority newsletter", body="x" * 900)
    q.add("URGENT: outage now")
    q.add("question for later?")
    top = q.next()
    assert top is not None and top.bucket == "now"
    assert "outage" in top.title
    second = q.next()
    assert second is not None and second.title == "question for later?"
    rest = q.list_pending()
    assert len(rest) == 1
    assert rest[0].title == "low priority newsletter"


def test_next_empty_returns_none(home):
    assert TriageQueue().next() is None


def test_counts(home):
    q = TriageQueue()
    q.add("URGENT: outage now")
    q.add("a thought")
    assert q.counts() == {"now": 1, "soon": 0, "later": 1}


def test_corrupt_queue_line_skipped(home):
    q = TriageQueue()
    q.add("real item")
    with triage.queue_path().open("a", encoding="utf-8") as fh:
        fh.write("this is not json\n")
    pending = q.list_pending()
    assert len(pending) == 1
    assert pending[0].title == "real item"
