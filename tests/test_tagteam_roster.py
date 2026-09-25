"""Tests for the tag-team roster: seats, intake bridging, drop validation."""

import json

import pytest

from levi.brain.tagteam import roster
from levi.brain.tagteam.roster import (
    DropRejected,
    UnknownSeat,
    intake_name,
    iter_drop_files,
    split_staged,
)


def test_team_is_nine_protocol_seats():
    assert roster.TEAM == (
        "kai9000",
        "qwen",
        "deepseek",
        "mistral",
        "kimi",
        "grok",
        "claude",
        "gemini",
        "rex",
    )


def test_intake_name_maps_one_to_one_seats():
    for seat in ("qwen", "deepseek", "mistral", "kimi", "grok", "claude", "gemini"):
        assert intake_name(seat) == seat


def test_intake_name_aliases_rex_to_muse():
    assert intake_name("rex") == "muse"


def test_intake_name_kai9000_stages_when_roster_lacks_it():
    # The sibling's intake roster has no kai9000 seat yet: the loop must
    # stage those drops, never send them to intake, never drop them.
    assert intake_name("kai9000") is None


def test_intake_name_rejects_non_protocol_seat():
    with pytest.raises(UnknownSeat):
        intake_name("chatgpt")


def test_iter_drop_files_rejects_weight_files(tmp_path):
    (tmp_path / "past1.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "evil.pt").write_text("fake", encoding="utf-8")
    with pytest.raises(DropRejected, match="weight files"):
        iter_drop_files(tmp_path)


def test_iter_drop_files_rejects_all_weight_suffixes(tmp_path):
    for suffix in (".pt", ".bin", ".safetensors", ".ckpt"):
        d = tmp_path / suffix.strip(".")
        d.mkdir()
        (d / f"w{suffix}").write_text("x", encoding="utf-8")
        with pytest.raises(DropRejected):
            iter_drop_files(d)


def test_iter_drop_files_lists_jsonl_deterministic(tmp_path):
    (tmp_path / "b.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "a.jsonl").write_text("", encoding="utf-8")
    assert [p.name for p in iter_drop_files(tmp_path)] == ["a.jsonl", "b.jsonl"]


def test_iter_drop_files_missing_dir(tmp_path):
    with pytest.raises(DropRejected, match="drops dir missing"):
        iter_drop_files(tmp_path / "nope")


def test_split_staged_rewrites_rex_and_stages_kai9000():
    raw = [
        {"teacher": "rex", "prompt": "q", "response": "a"},
        {"teacher": "kai9000", "prompt": "q", "response": "a"},
        {"teacher": "qwen", "prompt": "q", "response": "a"},
    ]
    ready, staged = split_staged(raw)
    assert [r["teacher"] for r in ready] == ["muse", "qwen"]
    assert list(staged) == ["kai9000"]
    assert len(staged["kai9000"]) == 1
    # originals untouched
    assert raw[0]["teacher"] == "rex"


def test_split_staged_rejects_non_protocol_seat():
    with pytest.raises(UnknownSeat):
        split_staged([{"teacher": "sneaky", "prompt": "q", "response": "a"}])
