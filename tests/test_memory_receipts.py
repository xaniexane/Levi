"""Tests for `levi.memory receipts` (hermetic via LEVI_MEMORY_DIR)."""

import json
import os

import pytest

from levi.memory.__main__ import main as memory_main
from levi.memory.store import MemoryStore
from levi.memory.types import MemoryType


@pytest.fixture()
def memdir(tmp_path, monkeypatch):
    # memory __main__ appends "memory" to LEVI_MEMORY_DIR
    monkeypatch.setenv("LEVI_MEMORY_DIR", str(tmp_path))
    d = tmp_path / "memory"
    store = MemoryStore(data_dir=d)
    store.add(
        MemoryType.SEMANTIC,
        "Chauncey prefers dark mode",
        source="chat",
        importance=0.8,
        tags=["preference"],
    )
    store.add(
        MemoryType.EPISODIC, "ran the daily hunt", source="scheduler", importance=0.3
    )
    return d


def test_receipts_lists_everything_with_provenance(memdir, capsys):
    assert memory_main(["receipts"]) == 0
    out = capsys.readouterr().out
    assert "memory receipts: 2 entr(ies)" in out
    assert "src=chat" in out and "src=scheduler" in out
    assert "semantic" in out and "episodic" in out
    assert "levi.memory delete <id>" in out


def test_receipts_empty_store_is_honest(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LEVI_MEMORY_DIR", str(tmp_path / "empty"))
    assert memory_main(["receipts"]) == 0
    assert "no memories stored" in capsys.readouterr().out


def test_receipts_export_json(memdir, tmp_path):
    out_file = tmp_path / "receipts.json"
    assert memory_main(["receipts", "--export", str(out_file)]) == 0
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["count"] == 2
    assert len(data["receipts"]) == 2
    for r in data["receipts"]:
        for key in (
            "id",
            "type",
            "source",
            "created_at",
            "importance",
            "content_preview",
        ):
            assert key in r
    sources = {r["source"] for r in data["receipts"]}
    assert sources == {"chat", "scheduler"}


def test_receipts_reflects_deletion(memdir, capsys):
    store = MemoryStore(data_dir=os.path.join(os.environ["LEVI_MEMORY_DIR"], "memory"))
    first = store.list(limit=1)[0]
    assert memory_main(["delete", first.id]) == 0
    capsys.readouterr()
    assert memory_main(["receipts"]) == 0
    assert "memory receipts: 1 entr(ies)" in capsys.readouterr().out
