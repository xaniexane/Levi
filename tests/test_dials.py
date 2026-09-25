"""Hermetic tests for levi.dials — no network, tmp HOME."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from levi.dials import SHELF
from levi.dials.dials import AttentionDials, DialError, FEATURES
from levi.dials.__main__ import main


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LEVI_HOME", raising=False)


def _ts(minutes_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def test_shelf_shape():
    assert SHELF["name"] == "dials"
    assert SHELF["summary"]
    assert isinstance(SHELF["items"], list) and SHELF["items"]


def test_chronological_is_sticky_default(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    d = AttentionDials()
    assert d.mode == "chronological"
    d.add_item("a", "old", timestamp=_ts(120))
    d.add_item("b", "new", timestamp=_ts(5))
    feed = d.feed()
    assert [i.author for i in feed] == ["b", "a"]


def test_weighted_ranking_uses_weights(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    d = AttentionDials()
    d.set_mode("weighted")
    d.set_weight("recency", 0.0)
    d.set_weight("affinity", 1.0)
    d.set_weight("diversity", 0.0)
    d.set_weight("substance", 0.0)
    d.set_weight("tag_match", 0.0)
    d.add_affinity("friend")
    d.add_item("stranger", "x" * 500, timestamp=_ts(1))
    d.add_item("friend", "hi", timestamp=_ts(1000))
    ranked = d.rank()
    assert ranked[0][0].author == "friend"  # affinity outweighs everything


def test_explain_breaks_down_contributions(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    d = AttentionDials()
    item = d.add_item("a", "hello world", tags=["news"])
    info = d.explain(item.id)
    assert set(info["features"]) == set(FEATURES)
    assert abs(sum(info["contributions"].values()) - info["score"]) < 1e-9
    assert info["score"] <= 1.0 + 1e-9


def test_affinity_is_explicit_only(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    d = AttentionDials()
    d.add_item("prolific", "one")
    d.add_item("prolific", "two")
    d.add_item("prolific", "three")
    d.set_mode("weighted")
    d.set_weight("recency", 0.0)
    d.set_weight("affinity", 1.0)
    d.set_weight("diversity", 0.0)
    d.set_weight("substance", 0.0)
    d.set_weight("tag_match", 0.0)
    # posting a lot does NOT earn affinity — only the explicit list does
    assert all(s <= 1e-9 for _, s, _ in d.rank())


def test_bad_weight_rejected(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    d = AttentionDials()
    with pytest.raises(DialError):
        d.set_weight("mind-control", 1.0)
    with pytest.raises(DialError):
        d.set_weight("recency", -1.0)
    with pytest.raises(DialError):
        d.add_item("", "text")


def test_cli_roundtrip(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert (
        main(["add", "--author", "ada", "--text", "first post", "--tags", "news"]) == 0
    )
    assert main(["weights"]) == 0
    out = capsys.readouterr().out
    assert "mode: chronological" in out
    assert main(["set-weight", "recency", "2.5"]) == 0
    assert main(["affinity-add", "ada"]) == 0
    assert main(["mode", "weighted"]) == 0
    assert main(["feed"]) == 0
    assert "ada" in capsys.readouterr().out
    # explain needs a real id; grab it from a fresh engine view
    d = AttentionDials()
    assert main(["explain", d.items[0].id]) == 0
    assert "contrib=" in capsys.readouterr().out


def test_cli_rank_does_not_move_sticky_mode(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["add", "--author", "a", "--text", "hello"]) == 0
    assert main(["rank"]) == 0
    assert AttentionDials().mode == "chronological"
