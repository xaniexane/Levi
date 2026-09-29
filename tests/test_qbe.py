"""Tests for levi.qbe — the Query By Example engine.

Law->guard->prove: each test names the law it guards.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from levi.qbe import QueryError, example, load_jsonl, query

SAILORS = [
    {"sid": 22, "sname": "Dustin", "rating": 7, "age": 45},
    {"sid": 29, "sname": "Brutus", "rating": 9, "age": 33},
    {"sid": 31, "sname": "Lubber", "rating": 8, "age": 55},
]
RESERVES = [
    {"sid": 22, "bid": 101, "day": "2026-09-01"},
    {"sid": 29, "bid": 102, "day": "2026-09-02"},
    {"sid": 29, "bid": 103, "day": "2026-09-03"},
]
BOATS = [
    {"bid": 101, "bname": "Interlake", "color": "blue"},
    {"bid": 102, "bname": "Clipper", "color": "red"},
    {"bid": 103, "bname": "Marine", "color": "red"},
]
TABLES = {"sailors": SAILORS, "reserves": RESERVES, "boats": BOATS}


def test_simple_example_and_print():
    # show a name-shaped row, get names back
    rows = query(
        TABLES,
        [{"table": "sailors", "rows": [{"sname": "P."}]}],
    )
    assert rows == [{"sname": "Dustin"}, {"sname": "Brutus"}, {"sname": "Lubber"}]


def test_literal_conjunction_L2():
    rows = query(
        TABLES,
        [{"table": "sailors", "rows": [{"rating": 9, "sname": "P."}]}],
    )
    assert rows == [{"sname": "Brutus"}]


def test_variable_unification_L1():
    # _s must be equal in both cells of the row; only sid 29 rows have
    # rating 9 AND appear in reserves with bid 102.
    rows = query(
        TABLES,
        [
            {"table": "sailors", "rows": [{"sid": "_s", "sname": "P._n"}]},
            {"table": "reserves", "rows": [{"sid": "_s", "bid": 102}]},
        ],
    )
    assert rows == [{"sname": "Brutus"}]


def test_join_across_three_tables_L1():
    ex = example()
    rows = query(ex["tables"], ex["skeletons"])
    assert rows == [
        {"sname": "Brutus", "bname": "Clipper"},
        {"sname": "Brutus", "bname": "Marine"},
    ]


def test_condition_operators():
    rows = query(
        TABLES,
        [{"table": "sailors", "rows": [{"rating": ">7", "sname": "P."}]}],
    )
    assert [r["sname"] for r in rows] == ["Brutus", "Lubber"]
    rows = query(
        TABLES,
        [{"table": "sailors", "rows": [{"age": "<=45", "sname": "P."}]}],
    )
    assert [r["sname"] for r in rows] == ["Dustin", "Brutus"]
    rows = query(
        TABLES,
        [{"table": "sailors", "rows": [{"sname": "!='Dustin'", "sid": "P."}]}],
    )
    assert [r["sid"] for r in rows] == [29, 31]


def test_glob_wildcard():
    rows = query(
        {"records": [{"id": "arch-qbe-1"}, {"id": "arch-kwic-2"}, {"id": "other"}]},
        [{"table": "records", "rows": [{"id": "P.arch-*"}]}],
    )
    assert rows == [{"id": "arch-qbe-1"}, {"id": "arch-kwic-2"}]


def test_rows_are_union():
    rows = query(
        TABLES,
        [{"table": "sailors",
          "rows": [{"sname": "Dustin", "sid": "P."},
                   {"sname": "Lubber", "sid": "P."}]}],
    )
    assert rows == [{"sid": 22}, {"sid": 31}]


def test_empty_is_honest_L3():
    rows = query(
        TABLES,
        [{"table": "sailors", "rows": [{"rating": ">100", "sname": "P."}]}],
    )
    assert rows == []


def test_missing_column_never_matches():
    rows = query(
        TABLES,
        [{"table": "sailors", "rows": [{"nickname": "P."}]}],
    )
    assert rows == []


def test_projection_exact_L4():
    rows = query(
        TABLES,
        [{"table": "sailors",
          "rows": [{"sid": 22, "sname": "P.", "rating": 7, "age": 45}]}],
    )
    assert rows == [{"sname": "Dustin"}]  # only the P. column


def test_dedup_default_and_off():
    tables = {"t": [{"a": 1}, {"a": 1}]}
    sk = [{"table": "t", "rows": [{"a": "P."}]}]
    assert query(tables, sk) == [{"a": 1}]
    assert query(tables, sk, dedup=False) == [{"a": 1}, {"a": 1}]


def test_print_with_variable_binds_and_prints():
    rows = query(
        TABLES,
        [{"table": "sailors", "rows": [{"sname": "P._n", "rating": "_r"}]}],
    )
    assert {"sname": "Dustin"} in rows and len(rows) == 3


def test_malformed_skeleton_raises_not_silent():
    with pytest.raises(QueryError):
        query(TABLES, [{"table": "sailors"}])  # missing rows
    with pytest.raises(QueryError):
        query(TABLES, [{"table": "nope", "rows": [{}]}])
    with pytest.raises(QueryError):
        query(TABLES, [{"table": "sailors", "rows": [{"a": "P.P._x"}]}])


def test_load_jsonl_roundtrip(tmp_path):
    p = tmp_path / "r.jsonl"
    p.write_text('{"id": "a"}\n{"id": "b"}\n', encoding="utf-8")
    assert load_jsonl(str(p)) == [{"id": "a"}, {"id": "b"}]


def test_cli_queries_archive_jsonl(tmp_path):
    recs = tmp_path / "records.jsonl"
    recs.write_text(
        '{"id": "arch-qbe", "rating": "load-bearing"}\n'
        '{"id": "arch-x", "rating": "inspirational"}\n',
        encoding="utf-8",
    )
    qf = tmp_path / "q.json"
    qf.write_text(
        json.dumps({"skeletons": [
            {"table": "records",
             "rows": [{"rating": "load-bearing", "id": "P._i"}]}]}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, "-m", "levi.qbe", str(recs), str(qf)],
        capture_output=True, text=True,
        cwd=Path(__file__).resolve().parents[1],
        env={"PYTHONPATH": "core", "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == [{"id": "arch-qbe"}]
