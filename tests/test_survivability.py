"""Tests for the LEVI survivability catalog (core/levi/survivability/)."""

import json
import os
import subprocess
import sys

from levi.survivability import catalog, check_all, check_entry, get

REQUIRED_KEYS = {
    "id",
    "capability",
    "primary_path",
    "fallback_path",
    "degraded_mode",
    "offline_ok",
    "verify",
}


def test_catalog_nonempty():
    entries = catalog()
    assert len(entries) >= 10


def test_entry_schema():
    ids = set()
    for entry in catalog():
        assert REQUIRED_KEYS <= set(entry), entry.get("id")
        assert isinstance(entry["offline_ok"], bool)
        assert entry["id"] not in ids, "duplicate id %s" % entry["id"]
        ids.add(entry["id"])
        assert entry["capability"] and entry["primary_path"]
        assert entry["fallback_path"] and entry["degraded_mode"]


def test_get_roundtrip():
    entry = get("agent-provider-chain")
    assert entry is not None
    assert entry["capability"]
    assert get("no-such-entry") is None


def test_check_all_passes():
    results = check_all()
    assert len(results) == len(catalog())
    failures = [r for r in results if not r["ok"]]
    assert not failures, failures


def test_check_result_shape():
    for result in check_all():
        assert set(result) == {"id", "ok", "detail"}
        assert isinstance(result["ok"], bool)


def test_check_entry_bad_import_fails_cleanly():
    bad = {
        "id": "test-bad",
        "verify": {"kind": "import", "target": "levi.nope.nothing"},
    }
    result = check_entry(bad)
    assert result["ok"] is False
    assert "nope" in result["detail"]


def test_check_entry_missing_path_fails_cleanly():
    bad = {"id": "test-bad", "verify": {"kind": "path", "target": "core/levi/nope.txt"}}
    result = check_entry(bad)
    assert result["ok"] is False


def test_offline_ok_is_bool_everywhere():
    for entry in catalog():
        assert entry["offline_ok"] is True or entry["offline_ok"] is False


def test_seeded_entries_cover_known_fallbacks():
    ids = {e["id"] for e in catalog()}
    for expected in (
        "agent-provider-chain",
        "finance-broker",
        "news-ingestion",
        "native-brain-weights",
        "growth-loop",
        "eula-linter",
    ):
        assert expected in ids


def test_cli_list():
    env = dict(os.environ, PYTHONPATH="core")
    proc = subprocess.run(
        [sys.executable, "-m", "levi.survivability", "list"],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.expanduser("~/workspace/levi"),
    )
    assert proc.returncode == 0, proc.stderr
    assert "agent-provider-chain" in proc.stdout


def test_cli_check():
    env = dict(os.environ, PYTHONPATH="core")
    proc = subprocess.run(
        [sys.executable, "-m", "levi.survivability", "check"],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.expanduser("~/workspace/levi"),
    )
    assert proc.returncode == 0, proc.stderr
    assert "fallbacks present" in proc.stdout


def test_cli_list_json():
    env = dict(os.environ, PYTHONPATH="core")
    proc = subprocess.run(
        [sys.executable, "-m", "levi.survivability", "list", "--format", "json"],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.expanduser("~/workspace/levi"),
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert isinstance(data, list) and len(data) >= 10
