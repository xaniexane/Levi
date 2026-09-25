"""Proof tests for jobs sheet_sync — two-way tracker <-> CSV pipeline sync.

Laws: idempotent (export/import/export is a fixed point), transitions
stay lawful (illegal CSV moves are skipped, never forced), no silent
invention (bad rows skipped with reasons).
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from levi.jobs.sheet_sync import export_csv, import_csv  # noqa: E402
from levi.jobs.tracker import JobTracker  # noqa: E402


def _tracker(tmp_path):
    return JobTracker(path=tmp_path / "jobs.json")


def test_export_writes_all_jobs(tmp_path):
    t = _tracker(tmp_path)
    t.add("Backend dev", company="Acme", source="manual")
    t.add("Support rep", company="Globex", source="manual", status="active")
    n = export_csv(t, tmp_path / "sheet.csv")
    assert n == 2
    with open(tmp_path / "sheet.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert {r["title"] for r in rows} == {"Backend dev", "Support rep"}
    assert {r["status"] for r in rows} == {"new", "active"}


def test_import_round_trip_is_fixed_point(tmp_path):
    t = _tracker(tmp_path)
    t.add("Backend dev", company="Acme")
    export_csv(t, tmp_path / "sheet.csv")
    r1 = import_csv(t, tmp_path / "sheet.csv")
    assert r1 == {"created": 0, "updated": 0, "skipped": []}
    export_csv(t, tmp_path / "sheet2.csv")
    assert (tmp_path / "sheet.csv").read_bytes() == (tmp_path / "sheet2.csv").read_bytes()


def test_import_creates_new_rows(tmp_path):
    t = _tracker(tmp_path)
    with open(tmp_path / "in.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["title", "company", "source", "status"])
        w.writeheader()
        w.writerow({"title": "Cook", "company": "Diner", "source": "walk-in",
                    "status": "new"})
    r = import_csv(t, tmp_path / "in.csv")
    assert r["created"] == 1 and r["updated"] == 0 and r["skipped"] == []
    assert t.find("Cook", "Diner", "walk-in") is not None


def test_import_legal_move_applies(tmp_path):
    t = _tracker(tmp_path)
    t.add("Backend dev", company="Acme")
    with open(tmp_path / "in.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["title", "company", "source", "status"])
        w.writeheader()
        w.writerow({"title": "Backend dev", "company": "Acme", "source": "manual",
                    "status": "active"})
    r = import_csv(t, tmp_path / "in.csv")
    assert r["updated"] == 1
    assert t.find("Backend dev", "Acme", "manual").status == "active"


def test_import_illegal_move_skipped_not_forced(tmp_path):
    t = _tracker(tmp_path)
    t.add("Backend dev", company="Acme")  # status new
    with open(tmp_path / "in.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["title", "company", "source", "status"])
        w.writeheader()
        w.writerow({"title": "Backend dev", "company": "Acme", "source": "manual",
                    "status": "won"})  # new -> won is illegal
    r = import_csv(t, tmp_path / "in.csv")
    assert r["updated"] == 0
    assert len(r["skipped"]) == 1
    assert "invalid transition" in r["skipped"][0]["reason"]
    assert t.find("Backend dev", "Acme", "manual").status == "new"


def test_import_bad_rows_skipped_with_reasons(tmp_path):
    t = _tracker(tmp_path)
    with open(tmp_path / "in.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["title", "company", "source", "status"])
        w.writeheader()
        w.writerow({"title": "", "status": "new"})
        w.writerow({"title": "X", "status": "hired"})  # unknown status
    r = import_csv(t, tmp_path / "in.csv")
    assert r["created"] == 0
    assert len(r["skipped"]) == 2
    assert r["skipped"][0]["reason"] == "empty title"
    assert "unknown status" in r["skipped"][1]["reason"]


def test_import_company_mismatch_not_merged(tmp_path):
    t = _tracker(tmp_path)
    t.add("Backend dev", company="Acme")
    with open(tmp_path / "in.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["title", "company", "source", "status"])
        w.writeheader()
        w.writerow({"title": "Backend dev", "company": "EvilCorp", "source": "manual",
                    "status": "active"})
    r = import_csv(t, tmp_path / "in.csv")
    assert r["created"] == 0 and r["updated"] == 0
    assert "identity key" in r["skipped"][0]["reason"]
    assert len(t.list()) == 1  # no duplicate
