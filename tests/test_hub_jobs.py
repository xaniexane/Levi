"""Hub job engine tests — network mocked at _fetch_json."""

import pytest

from levi.hub import jobs


@pytest.fixture()
def hubdir(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_HUB_DIR", str(tmp_path / "hub"))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def _fake_fetch(monkeypatch, payload=None, ok=True, error="boom"):
    def fake(url, timeout=20.0):
        if ok:
            return {"ok": True, "data": payload, "url": url}
        return {"ok": False, "error": error, "url": url}

    monkeypatch.setattr(jobs, "_fetch_json", fake)


def test_remotive_parses(monkeypatch):
    _fake_fetch(
        monkeypatch,
        {
            "jobs": [
                {
                    "title": "Python Dev",
                    "company_name": "Acme",
                    "url": "https://x",
                    "salary": "$100k",
                    "description": "d",
                }
            ]
        },
    )
    res = jobs.search_remotive("python")
    assert res["ok"] and res["count"] == 1
    row = res["listings"][0]
    assert row["job_title"] == "Python Dev" and row["company"] == "Acme"
    assert row["label"] == "OBSERVED"


def test_remoteok_skips_metadata_row(monkeypatch):
    _fake_fetch(
        monkeypatch,
        [{"legal": "x"}, {"position": "Dev", "company": "Acme", "url": "https://y"}],
    )
    res = jobs.search_remoteok()
    assert res["ok"] and res["count"] == 1
    assert res["listings"][0]["job_title"] == "Dev"


def test_source_failure_degrades(monkeypatch):
    _fake_fetch(monkeypatch, ok=False)
    for fn in (
        jobs.search_remotive,
        jobs.search_remoteok,
        jobs.search_arbeitnow,
        jobs.search_himalayas,
        jobs.search_jobicy,
    ):
        res = fn("") if fn in (jobs.search_remotive, jobs.search_himalayas) else fn()
        assert res["ok"] is False and res["listings"] == []


def test_search_all_polite_and_total(monkeypatch):
    _fake_fetch(monkeypatch, {"jobs": []})
    monkeypatch.setattr(jobs.time, "sleep", lambda s: None)
    res = jobs.search_all("python", pause=0)
    assert res["ok"] and res["total_listings"] == 0
    assert len(res["sources"]) == 5
    assert res["label"] == "OBSERVED"


def test_stage_dry_run(hubdir, monkeypatch):
    _fake_fetch(monkeypatch, {"jobs": []})
    report = jobs.stage(
        [
            {
                "job_title": "Dev",
                "company": "Acme",
                "url": "https://x",
                "source_board": "remotive",
            }
        ],
        dry_run=True,
    )
    assert report["dry_run"] is True
    assert report["staged"] + report["refreshed"] >= 0
