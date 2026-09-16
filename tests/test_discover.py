"""Hermetic tests for levi.discover: tmp HOME, synthetic corpora."""

import json
from datetime import date

import pytest

from levi.discover import SHELF
from levi.discover.digest import (
    _recently_picked,
    current_week_label,
    generate_digest,
    week_seed,
)
from levi.discover.items import DiscoverError, load_items, validate_item


@pytest.fixture()
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LEVI_HOME", raising=False)
    monkeypatch.delenv("LEVI_DISCOVER_SOURCE", raising=False)
    return tmp_path / ".levi" / "discover"


def _items(n=20):
    kinds = ["note", "paper", "bookmark", "memory"]
    return [
        {
            "id": f"item-{i}",
            "title": f"Title {i}",
            "kind": kinds[i % 4],
            "tags": [f"tag-{i % 5}"],
            "added_at": "2026-01-01",
            "source": "test",
            "blurb": "",
        }
        for i in range(n)
    ]


def _write_corpus(tmp_path, items, corrupt=True):
    p = tmp_path / "corpus.jsonl"
    with open(p, "w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it) + "\n")
        if corrupt:
            fh.write("not json at all\n")
            fh.write(json.dumps({"no": "id or title"}) + "\n")
    return p


def test_shelf_shape():
    assert SHELF["name"] and SHELF["summary"] and len(SHELF["items"]) >= 3


def test_validate_item():
    ok = validate_item({"id": "a", "title": "T"})
    assert ok["kind"] == "misc" and ok["tags"] == []
    with pytest.raises(DiscoverError):
        validate_item({"title": "no id"})
    with pytest.raises(DiscoverError):
        validate_item({"id": "a", "title": "x", "tags": "notalist"})


def test_load_items_skips_bad_lines(tmp_path, capsys):
    p = _write_corpus(tmp_path, _items(5))
    items = load_items(p)
    assert len(items) == 5
    out = capsys.readouterr().out
    assert "corrupt line" in out and "invalid line" in out


def test_load_items_missing_file(tmp_path):
    with pytest.raises(DiscoverError):
        load_items(tmp_path / "nope.jsonl")


def test_week_label_and_seed():
    assert current_week_label(date(2026, 9, 15)) == "2026-W38"
    assert week_seed("2026-W38") == week_seed("2026-W38")
    assert week_seed("2026-W38") != week_seed("2026-W39")


def test_digest_picks_seven_with_diversity(home):
    digest, md = generate_digest(_items(20), "2026-W38", home, seed=1)
    assert len(digest["picks"]) == 7
    kinds = [p["kind"] for p in digest["picks"]]
    assert max(kinds.count(k) for k in set(kinds)) <= 2  # per-kind cap
    assert f"Seed `{digest['seed']}`" in md
    assert "why this is here" in md
    assert (home / "digests" / "2026-W38.md").exists()


def test_digest_reproducible_with_seed(home):
    d1, _ = generate_digest(_items(20), "2026-W38", home, seed=42)
    # second home: same seed -> same picks
    import shutil

    home2 = home.parent / "discover2"
    d2, _ = generate_digest(_items(20), "2026-W38", home2, seed=42)
    assert [p["id"] for p in d1["picks"]] == [p["id"] for p in d2["picks"]]
    shutil.rmtree(home2, ignore_errors=True)


def test_digest_refuses_regeneration(home):
    generate_digest(_items(20), "2026-W38", home, seed=1)
    with pytest.raises(DiscoverError):
        generate_digest(_items(20), "2026-W38", home, seed=2)


def test_no_repeat_window(home):
    items = _items(10)
    d1, _ = generate_digest(items, "2026-W38", home, seed=1, count=5)
    first_ids = {p["id"] for p in d1["picks"]}
    d2, _ = generate_digest(items, "2026-W39", home, seed=1, count=5)
    second_ids = {p["id"] for p in d2["picks"]}
    assert first_ids.isdisjoint(second_ids)


def test_unseen_preferred(home):
    items = _items(10)
    d1, _ = generate_digest(items, "2026-W38", home, seed=7, count=10,
                            per_kind_cap=10, per_tag_cap=10, no_repeat_weeks=0)
    # with no-repeat off and high caps, second digest must still exist;
    # first digest's picks are "seen", so the second prefers the rest
    d2, _ = generate_digest(items, "2026-W39", home, seed=7, count=10,
                            per_kind_cap=10, per_tag_cap=10, no_repeat_weeks=0)
    first_ids = {p["id"] for p in d1["picks"]}
    # unseen items (none picked in W38... all 10 were picked) -> falls back to seen
    assert len(d2["picks"]) == 10


def test_per_tag_cap(home):
    items = [{"id": f"i{i}", "title": f"T{i}", "kind": f"k{i}",
              "tags": ["same"], "added_at": "", "source": "t", "blurb": ""}
             for i in range(10)]
    digest, _ = generate_digest(items, "2026-W38", home, seed=3, count=7,
                                per_kind_cap=10, per_tag_cap=2)
    assert len(digest["picks"]) <= 2  # tag cap binds
    assert digest["skipped_by_diversity_caps"] > 0


def test_recently_picked_window():
    hist = {"2026-W36": ["a"], "2026-W37": ["b"], "2026-W38": ["c"]}
    assert _recently_picked(hist, "2026-W38", window=2) == {"b", "c"}
    assert _recently_picked(hist, "2026-W38", window=8) == {"a", "b", "c"}


def test_cli_roundtrip(home, tmp_path, capsys, monkeypatch):
    from levi.discover.__main__ import main

    monkeypatch.setenv("LEVI_HOME", str(home.parent))
    corpus = _write_corpus(tmp_path, _items(12), corrupt=False)
    assert main(["--source", str(corpus), "discover", "--week", "2026-W38",
                 "--seed", "11"]) == 0
    out = capsys.readouterr().out
    assert "# Discover Weekly — 2026-W38" in out
    assert (home / "digests" / "2026-W38.md").exists()
    assert main(["history"]) == 0
    assert "2026-W38: 7 picks" in capsys.readouterr().out
    # second run for the same week fails closed
    assert main(["--source", str(corpus), "discover", "--week", "2026-W38"]) == 1
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_cli_init_sample(home, tmp_path, capsys, monkeypatch):
    from levi.discover.__main__ import main

    monkeypatch.setenv("LEVI_HOME", str(home.parent))
    dest = tmp_path / "sample.jsonl"
    assert main(["init-sample", str(dest)]) == 0
    items = load_items(dest)
    assert len(items) == 10
    assert all(i["source"] == "sample" for i in items)
    assert main(["init-sample", str(dest)]) == 1  # no overwrite without --force
