"""Tests for the census daemon — the stock-taker.

Proofs for the laws in ``levi/daemon/census.py``: honest counts from
injected providers, no half-counts on provider failure, deny-closed
diffs, corrupt snapshot lines skipped, and the ``snapshot``/``diff``
CLI entry points.
"""

import json

import pytest

from levi.daemon import census
from levi.daemon.census import CensusError


def _providers(**counts):
    return {name: (lambda v: lambda: v)(value) for name, value in counts.items()}


def test_take_census_counts_honestly():
    snap = census.take_census(
        providers=_providers(connectors=5, skills=823, daemons=17)
    )
    assert snap["counts"] == {
        "connectors": 5,
        "daemons": 17,
        "skills": 823,
    }
    assert snap["total"] == 845
    assert snap["taken_at"]


def test_provider_failure_fails_loudly_not_half(tmp_path):
    def boom():
        raise RuntimeError("registry exploded")

    with pytest.raises(CensusError):
        census.take_census(providers={"ok": lambda: 3, "bad": boom})
    # nothing was recorded: a failed census leaves no record
    assert census.latest(home=tmp_path) is None


def test_non_int_count_refused():
    with pytest.raises(CensusError):
        census.take_census(providers={"x": lambda: "many"})
    with pytest.raises(CensusError):
        census.take_census(providers={"x": lambda: True})
    with pytest.raises(CensusError):
        census.take_census(providers={"x": lambda: -1})


def test_empty_providers_refused():
    with pytest.raises(CensusError):
        census.take_census(providers={})
    with pytest.raises(CensusError):
        census.take_census(providers={"x": "not-callable"})


def test_record_appends_and_latest_reads(tmp_path):
    snap = census.record(home=tmp_path, providers=_providers(connectors=5))
    assert census.latest(home=tmp_path)["counts"] == snap["counts"]
    census.record(home=tmp_path, providers=_providers(connectors=6))
    assert len(census.history(home=tmp_path)) == 2
    assert census.latest(home=tmp_path)["counts"]["connectors"] == 6


def test_corrupt_lines_skipped(tmp_path):
    path = tmp_path / ".levi" / "daemon" / "census.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        "not json\n"
        + json.dumps({"taken_at": "t", "counts": {"a": 1}, "total": 1})
        + "\n"
        + json.dumps({"nope": True})
        + "\n",
        encoding="utf-8",
    )
    assert len(census.history(home=tmp_path)) == 1


def test_diff_grew_shrank_appeared_vanished():
    prev = {"taken_at": "t1", "counts": {"a": 5, "b": 3, "gone": 1}, "total": 9}
    cur = {"taken_at": "t2", "counts": {"a": 7, "b": 2, "new": 4}, "total": 13}
    d = census.diff_counts(prev, cur)
    assert d["grew"] == {"a": 2}
    assert d["shrank"] == {"b": 1}
    assert d["appeared"] == ["new"]
    assert d["vanished"] == ["gone"]
    assert d["total_delta"] == 4


def test_diff_refuses_dishonest_counts():
    with pytest.raises(CensusError):
        census.diff_counts({"taken_at": "t"}, {"counts": {"a": 1}, "total": 1})
    with pytest.raises(CensusError):
        census.diff_counts(
            {"taken_at": "t", "counts": {"a": "x"}, "total": 1},
            {"taken_at": "t", "counts": {"a": 1}, "total": 1},
        )


def test_cli_snapshot_writes_to_home(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(census, "_home", lambda: tmp_path)
    monkeypatch.setattr(census, "default_providers", lambda: _providers(connectors=2))
    assert census._cli(["snapshot"]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["counts"] == {"connectors": 2}
    assert census.latest(home=tmp_path)["counts"] == {"connectors": 2}


def test_cli_diff_needs_two_snapshots(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(census, "_home", lambda: tmp_path)
    monkeypatch.setattr(census, "default_providers", lambda: _providers(connectors=2))
    assert census._cli(["diff"]) == 1
    census._cli(["snapshot"])
    capsys.readouterr()
    assert census._cli(["diff"]) == 1  # still only one
    census._cli(["snapshot"])
    capsys.readouterr()
    assert census._cli(["diff"]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["total_delta"] == 0


def test_live_default_providers_count_real_things():
    prov = census.default_providers()
    assert set(prov) == {
        "connectors",
        "skills",
        "manifest_modules",
        "bot_modules",
        "daemon_modules",
    }
    counts = {name: fn() for name, fn in prov.items()}
    assert all(isinstance(v, int) and v > 0 for v in counts.values())
    # the two modules built alongside this census are counted
    assert counts["connectors"] >= 5  # directory, clock, logtail, diskwatch, portwatch
