"""hub.jobs: keyless job-search runtime for the hub.

The original's strongest keyless code was its multi-source job search
(Remotive, RemoteOK, Arbeitnow, Himalayas, Jobicy). This is the same
idea rebuilt ours-only: ``urllib`` fetches, polite headers, per-source
parsers, graceful degradation (a dead source yields an empty result with
a note — never a crash). Keyed sources (Adzuna) are excluded by design:
no keys, no fiction.

Results normalize onto ``levi.jobs``' listing shape and can stage into
its review buffer via ``levi.jobs.sourcing.ingest_listings`` (dry-run
default — the human decides what moves).

Every source result carries ``label: "OBSERVED"`` (fetched market data)
and per-source status. Anything we synthesize from them is INFERENCE.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

UA = "LEVI-hub/0.1 (+local keyless job search; contact: founder)"

_SOURCES = ("remotive", "remoteok", "arbeitnow", "himalayas", "jobicy")


def _fetch_json(url: str, timeout: float = 20.0) -> Dict[str, Any]:
    """Polite single GET. Returns {"ok", "data"|"error", "url"} — never raises."""
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return {"ok": False, "error": f"http {resp.status}", "url": url}
            raw = resp.read(2_000_000).decode("utf-8", "replace")
        return {"ok": True, "data": json.loads(raw), "url": url}
    except Exception as exc:  # network, JSON, timeout — degrade, don't crash
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "url": url}


def _base(row: Dict[str, Any], board: str) -> Dict[str, Any]:
    return {
        "job_title": str(row.get("job_title") or ""),
        "company": str(row.get("company") or ""),
        "source_board": board,
        "url": str(row.get("url") or ""),
        "pay_range": str(row.get("pay_range") or ""),
        "location_remote": str(row.get("location_remote") or ""),
        "notes": str(row.get("notes") or ""),
        "label": "OBSERVED",
    }


def search_remotive(query: str = "") -> Dict[str, Any]:
    """Remotive keyless API: https://remotive.com/api/remote-jobs"""
    params = {}
    if query:
        params["search"] = query
    url = "https://remotive.com/api/remote-jobs"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    res = _fetch_json(url)
    if not res["ok"]:
        return {
            "source": "remotive",
            "ok": False,
            "error": res["error"],
            "listings": [],
        }
    jobs = (res["data"] or {}).get("jobs", []) if isinstance(res["data"], dict) else []
    out = []
    for j in jobs:
        if not isinstance(j, dict):
            continue
        out.append(
            _base(
                {
                    "job_title": j.get("title"),
                    "company": j.get("company_name"),
                    "url": j.get("url"),
                    "pay_range": j.get("salary") or "",
                    "location_remote": "remote",
                    "notes": (j.get("description") or "")[:300],
                },
                "remotive",
            )
        )
    return {"source": "remotive", "ok": True, "listings": out, "count": len(out)}


def search_remoteok() -> Dict[str, Any]:
    """RemoteOK keyless API: https://remoteok.com/api"""
    res = _fetch_json("https://remoteok.com/api")
    if not res["ok"]:
        return {
            "source": "remoteok",
            "ok": False,
            "error": res["error"],
            "listings": [],
        }
    jobs = res["data"] if isinstance(res["data"], list) else []
    out = []
    for j in jobs[1:]:  # first element is metadata/legal
        if not isinstance(j, dict):
            continue
        tags = j.get("tags") or []
        out.append(
            _base(
                {
                    "job_title": j.get("position"),
                    "company": j.get("company"),
                    "url": j.get("url") or j.get("apply_url"),
                    "pay_range": f"{j.get('salary_min', '')}-{j.get('salary_max', '')}".strip(
                        "-"
                    ),
                    "location_remote": j.get("location") or "remote",
                    "notes": " ".join(tags[:6]),
                },
                "remoteok",
            )
        )
    return {"source": "remoteok", "ok": True, "listings": out, "count": len(out)}


def search_arbeitnow() -> Dict[str, Any]:
    """Arbeitnow keyless API: https://www.arbeitnow.com/api/job-board-api"""
    res = _fetch_json("https://www.arbeitnow.com/api/job-board-api")
    if not res["ok"]:
        return {
            "source": "arbeitnow",
            "ok": False,
            "error": res["error"],
            "listings": [],
        }
    jobs = (res["data"] or {}).get("data", []) if isinstance(res["data"], dict) else []
    out = []
    for j in jobs:
        if not isinstance(j, dict):
            continue
        out.append(
            _base(
                {
                    "job_title": j.get("title"),
                    "company": j.get("company_name"),
                    "url": j.get("url"),
                    "location_remote": j.get("location") or "",
                    "notes": (j.get("description") or "")[:300],
                },
                "arbeitnow",
            )
        )
    return {"source": "arbeitnow", "ok": True, "listings": out, "count": len(out)}


def search_himalayas(query: str = "") -> Dict[str, Any]:
    """Himalayas keyless API: https://himalayas.app/jobs/api/search"""
    params = {"limit": "50"}
    if query:
        params["search"] = query
    url = "https://himalayas.app/jobs/api/search?" + urllib.parse.urlencode(params)
    res = _fetch_json(url)
    if not res["ok"]:
        return {
            "source": "himalayas",
            "ok": False,
            "error": res["error"],
            "listings": [],
        }
    jobs = (res["data"] or {}).get("jobs", []) if isinstance(res["data"], dict) else []
    out = []
    for j in jobs:
        if not isinstance(j, dict):
            continue
        company = j.get("company") or {}
        out.append(
            _base(
                {
                    "job_title": j.get("title"),
                    "company": company.get("name")
                    if isinstance(company, dict)
                    else company,
                    "url": j.get("applicationLink") or j.get("url"),
                    "pay_range": j.get("salary") or "",
                    "location_remote": "remote" if j.get("isRemote") else "",
                    "notes": (j.get("excerpt") or "")[:300],
                },
                "himalayas",
            )
        )
    return {"source": "himalayas", "ok": True, "listings": out, "count": len(out)}


def search_jobicy() -> Dict[str, Any]:
    """Jobicy keyless API: https://jobicy.com/api/v2/remote-jobs"""
    res = _fetch_json("https://jobicy.com/api/v2/remote-jobs?count=50")
    if not res["ok"]:
        return {"source": "jobicy", "ok": False, "error": res["error"], "listings": []}
    data = res["data"]
    jobs = (
        data.get("jobs", [])
        if isinstance(data, dict)
        else (data if isinstance(data, list) else [])
    )
    out = []
    for j in jobs:
        if not isinstance(j, dict):
            continue
        out.append(
            _base(
                {
                    "job_title": j.get("jobTitle") or j.get("title"),
                    "company": j.get("companyName") or j.get("company"),
                    "url": j.get("url") or j.get("jobUrl"),
                    "pay_range": j.get("salary") or "",
                    "location_remote": "remote",
                    "notes": (j.get("jobExcerpt") or "")[:300],
                },
                "jobicy",
            )
        )
    return {"source": "jobicy", "ok": True, "listings": out, "count": len(out)}


_FETCHERS = {
    "remotive": search_remotive,
    "remoteok": lambda q: search_remoteok(),
    "arbeitnow": lambda q: search_arbeitnow(),
    "himalayas": search_himalayas,
    "jobicy": lambda q: search_jobicy(),
}


def search_all(
    query: str = "", sources: Optional[List[str]] = None, pause: float = 1.0
) -> Dict[str, Any]:
    """Run the keyless sources (polite 1s spacing). Returns per-source results."""
    wanted = [s for s in (sources or list(_SOURCES)) if s in _FETCHERS]
    results: List[Dict[str, Any]] = []
    total = 0
    for i, name in enumerate(wanted):
        if i:
            time.sleep(pause)
        try:
            res = _FETCHERS[name](query)
        except Exception as exc:  # a parser bug must not kill the sweep
            res = {
                "source": name,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "listings": [],
            }
        results.append(res)
        total += len(res.get("listings", []))
    return {
        "ok": True,
        "query": query,
        "sources": results,
        "total_listings": total,
        "label": "OBSERVED",
        "note": "keyless sources only; Adzuna and other keyed boards excluded by design",
    }


def stage(
    listings: List[Dict[str, Any]], source_board: str = "hub", dry_run: bool = True
) -> Dict[str, Any]:
    """Stage listings into levi.jobs' review buffer. Dry-run default.

    Returns the sourcing report (staged/refreshed/rejected counts).
    """
    from levi.jobs import store as job_store
    from levi.jobs import sourcing as job_sourcing

    warehouse = job_store.Warehouse()
    return job_sourcing.ingest_listings(
        warehouse, listings, source_board=source_board, dry_run=dry_run
    )
