"""Hermetic tests for levi.recap.

No network, no real HOME. Event files live in tmp_path; the sample
generator is deterministic (seeded).
"""

from __future__ import annotations

import json

import pytest

from levi.recap.__main__ import main as cli_main
from levi.recap.recap import (
    RecapError,
    compute_stats,
    load_events,
    render_html,
    render_text,
    sample_events,
)


def _write_events(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return str(path)


def _row(ts, cat, kind="session", label=None, value=1, unit=None):
    r = {"ts": ts, "category": cat, "kind": kind, "value": value}
    if label:
        r["label"] = label
    if unit:
        r["unit"] = unit
    return r


def test_load_validates_rows(tmp_path):
    p = _write_events(
        tmp_path / "e.jsonl",
        [
            _row(
                "2026-01-01T10:00:00", "reading", label="Dune", value=30, unit="minutes"
            ),
            {"category": "x", "kind": "y"},  # missing ts
        ],
    )
    with pytest.raises(RecapError) as e:
        load_events(p)
    assert "missing 'ts'" in str(e.value)


def test_load_rejects_bad_json(tmp_path):
    p = tmp_path / "e.jsonl"
    p.write_text("{not json}\n")
    with pytest.raises(RecapError):
        load_events(p)


def test_load_missing_file(tmp_path):
    with pytest.raises(RecapError):
        load_events(tmp_path / "nope.jsonl")


def test_stats_totals_and_streak(tmp_path):
    p = _write_events(
        tmp_path / "e.jsonl",
        [
            _row("2026-03-01T09:00:00", "reading", value=20),
            _row("2026-03-02T09:00:00", "reading", value=30),
            _row("2026-03-03T09:00:00", "coding", value=60),
            _row("2026-03-10T09:00:00", "reading", value=10),  # gap breaks streak
        ],
    )
    s = compute_stats(load_events(p))
    assert s["events"] == 4
    assert s["active_days"] == 4
    assert s["longest_streak_days"] == 3
    assert s["top_categories_by_events"][0] == ("reading", 3)
    assert {c for c, _ in s["top_categories_by_value"][:2]} == {"reading", "coding"}
    assert s["busiest_month"] == ("2026-03", 4)


def test_stats_top_value_ordering(tmp_path):
    p = _write_events(
        tmp_path / "e.jsonl",
        [
            _row("2026-03-01T09:00:00", "reading", value=20),
            _row("2026-03-02T09:00:00", "coding", value=200),
        ],
    )
    s = compute_stats(load_events(p))
    assert s["top_categories_by_value"][0] == ("coding", 200.0)


def test_stats_year_filter(tmp_path):
    p = _write_events(
        tmp_path / "e.jsonl",
        [
            _row("2025-12-31T23:00:00", "reading"),
            _row("2026-01-01T09:00:00", "reading"),
        ],
    )
    s = compute_stats(load_events(p), year=2026)
    assert s["events"] == 1


def test_stats_milestones_and_biggest_day(tmp_path):
    rows = [
        _row("2026-05-%02dT10:00:00" % d, "music", label="jazz", value=5)
        for d in range(1, 11)
    ]
    rows.append(_row("2026-05-11T10:00:00", "music", label="jazz", value=500))
    p = _write_events(tmp_path / "e.jsonl", rows)
    s = compute_stats(load_events(p))
    assert s["biggest_day"] == {"day": "2026-05-11", "value": 500.0}
    assert s["top_labels"]["music"]["label"] == "jazz"
    assert any("first event" in m["text"] for m in s["milestones"])


def test_stats_empty(tmp_path):
    p = _write_events(tmp_path / "e.jsonl", [])
    s = compute_stats(load_events(p))
    assert s["empty"]
    assert "nothing to recap" in render_text(s).lower()


def test_render_text_honest_footer(tmp_path):
    p = _write_events(tmp_path / "e.jsonl", [_row("2026-01-01T10:00:00", "reading")])
    t = render_text(compute_stats(load_events(p)))
    assert "nothing left the machine" in t


def test_render_html_is_standalone(tmp_path):
    p = _write_events(
        tmp_path / "e.jsonl",
        [
            _row("2026-01-01T10:00:00", "reading", label="Dune <script>", value=30),
        ],
    )
    page = render_html(compute_stats(load_events(p)))
    assert "<script>" not in page  # label is escaped
    assert "Dune &lt;script&gt;" in page
    assert "http://" not in page and "https://" not in page  # no external refs


def test_sample_is_deterministic_and_labeled(tmp_path):
    p1 = sample_events(tmp_path / "a.jsonl", n=50)
    p2 = sample_events(tmp_path / "b.jsonl", n=50)
    assert p1.read_text() == p2.read_text()
    assert "synthetic" in p1.read_text().splitlines()[0]
    events = load_events(p1)  # marker line skipped cleanly
    assert len(events) == 50
    s = compute_stats(events)
    assert s["events"] == 50 and not s["empty"]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def test_cli_stats_and_html(tmp_path, capsys):
    p = sample_events(tmp_path / "s.jsonl", n=120)
    assert cli_main(["stats", str(p)]) == 0
    assert "LEVI RECAP" in capsys.readouterr().out
    out = tmp_path / "card.html"
    assert cli_main(["html", str(p), "--out", str(out)]) == 0
    assert "<!DOCTYPE html>" in out.read_text()
    assert "standalone" in capsys.readouterr().out


def test_cli_sample(tmp_path, capsys):
    out = tmp_path / "gen.jsonl"
    assert cli_main(["sample", "--out", str(out), "--n", "10"]) == 0
    assert len(load_events(out)) == 10


def test_cli_bad_file_fails(tmp_path):
    assert cli_main(["stats", str(tmp_path / "missing.jsonl")]) == 1
