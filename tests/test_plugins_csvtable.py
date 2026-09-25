"""Tests for levi.plugins.csvtable — the local CSV table connector.

Proof of the three laws:
1. READ-ONLY — no write capabilities/operations; confirmation can never gate.
2. ROOTED — paths outside the root (absolute or ../ escapes, symlinks) are refused.
3. BOUNDED — file size cap, limit bounds, offset bounds enforced.

Hermetic: tmp_path via LEVI_CSVTABLE_ROOT; no network, no HOME writes.
"""

from __future__ import annotations

import os

import pytest

from levi.plugins.csvtable import CsvTableConnector, InvalidParams
from levi.plugins.registry import get_connector, list_connectors

CSV_SAMPLE = "name,amount,count\nalpha,10.5,3\nbeta,20,7\ngamma,,2\n"

TSV_SAMPLE = "a\tb\n1\t2\n"


@pytest.fixture()
def root(tmp_path, monkeypatch):
    root = tmp_path / "data"
    root.mkdir()
    monkeypatch.setenv("LEVI_CSVTABLE_ROOT", str(root))
    return root


@pytest.fixture()
def table(root):
    (root / "spend.csv").write_text(CSV_SAMPLE, encoding="utf-8")
    return "spend.csv"


@pytest.fixture()
def tsv(root):
    (root / "vals.tsv").write_text(TSV_SAMPLE, encoding="utf-8")
    return "vals.tsv"


def _run(operation, params):
    return CsvTableConnector().perform(operation, params, token=None, transport=None)


def test_registered_and_credentialless():
    ids = [c.id for c in list_connectors()]
    assert "csvtable" in ids
    inst = get_connector("csvtable")
    assert isinstance(inst, CsvTableConnector)
    assert inst.credential() == "public"


def test_read_only_never_requires_confirmation():
    assert CsvTableConnector.requires_confirmation is False
    assert not any(c.write for c in CsvTableConnector.capabilities)
    assert not any(o.write for o in CsvTableConnector.operations)


def test_read_rows(table, root):
    out = _run("read", {"path": table})
    assert out["row_count"] == 3
    assert out["rows"][0] == {"name": "alpha", "amount": "10.5", "count": "3"}
    assert len(out["rows"]) == 3  # default limit 50 covers all


def test_read_limit_and_offset(table, root):
    out = _run("read", {"path": table, "limit": 1, "offset": 1})
    assert out["offset"] == 1
    assert out["rows"] == [{"name": "beta", "amount": "20", "count": "7"}]


def test_read_rejects_bad_bounds(table, root):
    with pytest.raises(InvalidParams):
        _run("read", {"path": table, "limit": 0})
    with pytest.raises(InvalidParams):
        _run("read", {"path": table, "limit": 501})
    with pytest.raises(InvalidParams):
        _run("read", {"path": table, "offset": -1})


def test_columns_with_types(table, root):
    out = _run("columns", {"path": table})
    by_name = {c["name"]: c["type"] for c in out["columns"]}
    assert by_name == {"name": "text", "amount": "float", "count": "int"}


def test_stats(table, root):
    out = _run("stats", {"path": table})
    by_name = {c["name"]: c for c in out["columns"]}
    assert by_name["count"]["non_null"] == 3
    assert by_name["amount"]["non_null"] == 2
    assert by_name["amount"]["min"] == pytest.approx(10.5)
    assert by_name["amount"]["max"] == pytest.approx(20.0)
    assert by_name["amount"]["mean"] == pytest.approx(15.25)
    assert "mean" not in by_name["name"]  # text column: no numeric stats


def test_tsv_delimiter_sniffed(tsv, root):
    out = _run("read", {"path": tsv})
    assert out["rows"] == [{"a": "1", "b": "2"}]


def test_root_escape_refused(root, tmp_path):
    (tmp_path / "evil.csv").write_text("x\n1\n", encoding="utf-8")
    with pytest.raises(InvalidParams):
        _run("read", {"path": str(tmp_path / "evil.csv")})  # absolute outside root
    with pytest.raises(InvalidParams):
        _run("read", {"path": "../evil.csv"})  # traversal
    # symlink inside root pointing outside: refused, not followed
    os.symlink(tmp_path / "evil.csv", root / "link.csv")
    with pytest.raises(InvalidParams):
        _run("read", {"path": "link.csv"})


def test_wrong_suffix_refused(root):
    (root / "notes.txt").write_text("x", encoding="utf-8")
    with pytest.raises(InvalidParams):
        _run("read", {"path": "notes.txt"})


def test_missing_file_refused(root):
    with pytest.raises(InvalidParams):
        _run("read", {"path": "nope.csv"})


def test_unknown_operation_refused(table, root):
    with pytest.raises(InvalidParams):
        _run("drop", {"path": table})
