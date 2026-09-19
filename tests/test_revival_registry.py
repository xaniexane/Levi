"""Tests for the revival registry + CLI (lazy by design).

The registry must import NONE of the twenty revival modules on import;
modules resolve only through explicit ``load(entry)``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from levi.revival.registry import RevivalEntry, get, list_entries, load, search

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = str(REPO_ROOT / "core")


def _run_cli(*args):
    env = dict(os.environ, PYTHONPATH=CORE_DIR)
    return subprocess.run(
        [sys.executable, "-m", "levi.revival", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=60,
    )


def test_exactly_twenty_entries():
    entries = list_entries()
    assert len(entries) == 20


def test_entries_well_formed_and_unique():
    entries = list_entries()
    names = [e.levi_name for e in entries]
    modules = [e.module for e in entries]
    assert len(set(names)) == 20
    assert len(set(modules)) == 20
    for e in entries:
        assert isinstance(e, RevivalEntry)
        assert e.module.startswith("levi.revival.")
        assert e.levi_name and e.title and e.flair
        assert e.origin.startswith("levi-revival/")
        assert e.status == "active"
        tail = e.module.rsplit(".", 1)[-1]
        assert e.origin == f"levi-revival/{tail}"


def test_registry_import_is_lazy():
    """A fresh interpreter importing the registry must load no modules."""
    code = (
        "import sys, json;"
        "from levi.revival import registry;"
        "loaded = [m for m in sys.modules"
        " if m.startswith('levi.revival.') and m not in ('levi.revival', 'levi.revival.registry')];"
        "print(json.dumps(loaded))"
    )
    env = dict(os.environ, PYTHONPATH=CORE_DIR)
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == []


def test_load_imports_every_module_path():
    for e in list_entries():
        mod = load(e)
        assert mod.__name__ == e.module


def test_get_by_levi_name():
    e = get("Wayfinder")
    assert e.module == "levi.revival.goap"
    assert get("wayfinder").module == "levi.revival.goap"
    assert get("MIRRORWISE").module == "levi.revival.interlisp"


def test_get_by_module_path():
    e = get("levi.revival.telescript")
    assert e.levi_name == "Sealtender"
    assert get("telescript").module == "levi.revival.telescript"


def test_get_by_title_keyword():
    e = get("supervision")
    assert e.module == "levi.revival.otp"


def test_get_unknown_and_ambiguous():
    with pytest.raises(KeyError):
        get("no-such-revival")
    with pytest.raises(ValueError):
        get("sync")  # matches both Twindesk and Fieldnotes titles


def test_search_finds_expected_entries():
    hits = {e.module for e in search("permit")}
    assert "levi.revival.telescript" in hits
    hits = {e.module for e in search("offline")}
    assert hits >= {"levi.revival.notes", "levi.revival.groove"}
    assert search("zzz-no-match") == []
    assert search("") == []


def test_cli_list():
    proc = _run_cli("list")
    assert proc.returncode == 0, proc.stderr
    for e in list_entries():
        assert e.levi_name in proc.stdout
    assert "20" in proc.stdout


def test_cli_show():
    proc = _run_cli("show", "Wayfinder")
    assert proc.returncode == 0, proc.stderr
    assert "Wayfinder" in proc.stdout
    assert "levi.revival.goap" in proc.stdout
    assert "Goal-oriented planning" in proc.stdout

    # show also accepts a module path
    proc = _run_cli("show", "levi.revival.xanadu")
    assert proc.returncode == 0, proc.stderr
    assert "Trailwright" in proc.stdout


def test_cli_show_unknown():
    proc = _run_cli("show", "no-such-revival")
    assert proc.returncode != 0


def test_cli_search():
    proc = _run_cli("search", "permit")
    assert proc.returncode == 0, proc.stderr
    assert "Sealtender" in proc.stdout


def test_cli_lazy():
    """The CLI itself must not import any revival module."""
    env = dict(os.environ, PYTHONPATH=CORE_DIR)
    code = (
        "import sys, json;"
        "from levi.revival import __main__;"
        "__main__.main(['list']);"
        "loaded = [m for m in sys.modules"
        " if m.startswith('levi.revival.') and m not in ('levi.revival', 'levi.revival.registry', 'levi.revival.__main__')];"
        "print(json.dumps(loaded), file=sys.stderr)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stderr.strip().splitlines()[-1]) == []
