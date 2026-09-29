"""Tests for levi.bot.checkpoint — the memory of open loops."""

from __future__ import annotations

import json

import pytest

from levi.bot import checkpoint


def test_save_writes_checkpoint_and_ledger(tmp_path):
    record = checkpoint.save(
        [
            {"title": "Pack run 30", "state": "coding", "next_step": "run tests"},
            {
                "title": "Wait on Chauncey",
                "status": "waiting",
                "next_step": "ask the question",
            },
        ],
        name="test",
        base_dir=str(tmp_path),
    )
    assert record.path.endswith(".json")
    payload = json.loads(open(record.path, encoding="utf-8").read())
    assert len(payload["loops"]) == 2
    assert payload["loops"][0]["title"] == "Pack run 30"
    assert payload["loops"][1]["status"] == "waiting"
    ledger = tmp_path / "ledger.jsonl"
    assert ledger.exists()
    entry = json.loads(ledger.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert entry["loops"] == 2


def test_list_open_returns_newest_checkpoint(tmp_path):
    checkpoint.save(
        [{"title": "first", "next_step": "do it"}],
        name="a",
        base_dir=str(tmp_path),
    )
    checkpoint.save(
        [{"title": "second", "next_step": "do more", "status": "paused"}],
        name="b",
        base_dir=str(tmp_path),
    )
    loops = checkpoint.list_open(base_dir=str(tmp_path))
    assert [loop.title for loop in loops] == ["second"]
    assert loops[0].status == "paused"


def test_list_open_empty_dir_is_empty_list(tmp_path):
    assert checkpoint.list_open(base_dir=str(tmp_path)) == []


def test_save_refuses_bad_loops(tmp_path):
    with pytest.raises(checkpoint.CheckpointError):
        checkpoint.save([], base_dir=str(tmp_path))  # nothing to save
    with pytest.raises(checkpoint.CheckpointError):
        checkpoint.save([{"title": "", "next_step": "x"}], base_dir=str(tmp_path))
    with pytest.raises(checkpoint.CheckpointError):
        checkpoint.save(
            [{"title": "t", "next_step": "x", "status": "done"}], base_dir=str(tmp_path)
        )  # finished loops don't checkpoint
    with pytest.raises(checkpoint.CheckpointError):
        checkpoint.save(
            [{"title": "t", "next_step": "x", "mystery": 1}], base_dir=str(tmp_path)
        )  # unknown fields refused


def test_render_receipt_and_resume_list(tmp_path):
    record = checkpoint.save(
        [{"title": "Pack run 30", "next_step": "run tests"}],
        base_dir=str(tmp_path),
    )
    text = checkpoint.render(record)
    assert "Pack run 30" in text and "run tests" in text
    assert "No open loops" in checkpoint.render_list([])
    assert "Pack run 30" in checkpoint.render_list(record.loops)


def test_corrupt_checkpoint_is_skipped(tmp_path):
    (tmp_path / "junk-20200101T000000.json").write_text("{nope", encoding="utf-8")
    checkpoint.save([{"title": "real", "next_step": "go"}], base_dir=str(tmp_path))
    loops = checkpoint.list_open(base_dir=str(tmp_path))
    assert [loop.title for loop in loops] == ["real"]


def test_cli_list_renders(tmp_path, capsys):
    checkpoint.save([{"title": "real", "next_step": "go"}], base_dir=str(tmp_path))
    rc = checkpoint.cli(["list", "--render", "--base-dir", str(tmp_path)])
    assert rc == 0
    assert "real" in capsys.readouterr().out
