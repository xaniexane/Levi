"""Tests for gap reports and rotating teacher requests."""

import json

import pytest

from levi.brain.tagteam import requests as req
from levi.brain.tagteam.prompts import PROMPT_IDS


def _scores(**kw):
    return dict(kw)


def test_gap_report_flags_regression():
    prev = _scores(**{"arith-1": 0.80})
    cur = _scores(**{"arith-1": 0.60})
    gaps = req.gap_report(prev, cur)
    assert len(gaps) == 1
    g = gaps[0]
    assert (g.topic, g.prompt_id, g.severity) == ("arithmetic", "arith-1", "regressed")
    assert g.delta == pytest.approx(-0.20)


def test_gap_report_flags_weak_baseline_round_one():
    gaps = req.gap_report(None, _scores(**{"chem-1": 0.40}))
    assert [g.prompt_id for g in gaps] == ["chem-1"]
    assert gaps[0].severity == "weak"
    assert gaps[0].prev_score is None


def test_gap_report_ignores_strong_and_improving():
    prev = _scores(**{"arith-1": 0.50, "arith-2": 0.90})
    cur = _scores(**{"arith-1": 0.58, "arith-2": 0.91})
    assert req.gap_report(prev, cur) == []


def test_gap_report_tiny_dip_is_not_regression():
    prev = _scores(**{"arith-1": 0.80})
    cur = _scores(**{"arith-1": 0.77})
    assert req.gap_report(prev, cur) == []


def test_assign_requests_two_teachers_per_gap_and_deterministic():
    gaps = req.gap_report(None, _scores(**{"chem-1": 0.30}))
    r1 = req.assign_requests(gaps, 1, {})
    r2 = req.assign_requests(gaps, 1, {})
    assert len(r1) == 2  # disagreements preserved: never one voice
    assert r1 == r2
    assert r1[0].teacher != r1[1].teacher
    assert all(r.topic == "chemistry" and r.round == 1 for r in r1)
    assert r1[0].request_id.startswith("r001-chemistry-")


def test_assign_requests_rotates_avoids_last_round_seats():
    gaps = req.gap_report(None, _scores(**{"chem-1": 0.30}))
    first = req.assign_requests(gaps, 1, {})
    used = {"chemistry": [r.teacher for r in first]}
    second = req.assign_requests(gaps, 2, used)
    assert not set(r.teacher for r in second) & set(used["chemistry"])


def test_assign_requests_rotation_walks_roster_across_rounds():
    gaps = req.gap_report(None, _scores(**{"chem-1": 0.30}))
    seen = set()
    hist = {}
    for n in range(1, 6):
        rs = req.assign_requests(gaps, n, hist)
        hist = {"chemistry": [r.teacher for r in rs]}
        seen.update(hist["chemistry"])
    # 5 rounds x 2 seats with no immediate repeats must touch many seats
    assert len(seen) >= 6


def test_brief_names_weakness_and_jsonl_shape():
    gaps = req.gap_report({"arith-1": 0.8}, {"arith-1": 0.5})
    (r,) = req.assign_requests(gaps, 3, {})[:1]
    assert r.topic == "arithmetic" and r.round == 3
    assert "arithmetic" in r.brief
    assert "round 3" in r.brief
    assert '"teacher": "qwen"' in r.brief or f'"teacher": "{r.teacher}"' in r.brief
    assert "disagreements" in r.brief


def test_write_and_render_requests(tmp_path):
    gaps = req.gap_report(None, _scores(**{"chem-1": 0.30, "ei-1": 0.20}))
    rs = req.assign_requests(gaps, 1, {})
    assert len(rs) == 4  # 2 topics x 2 teachers
    p = tmp_path / "requests.jsonl"
    req.write_requests(p, rs)
    lines = p.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 4

    first = json.loads(lines[0])
    assert first["request_id"].startswith("r001-")
    assert first["n_items"] == req.ITEMS_PER_REQUEST
    md = req.render_requests_md(rs, 1)
    assert "# Tag-team round 1" in md
    assert "chemistry" in md and "emotional-intelligence" in md
