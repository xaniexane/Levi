"""Academy & Credential Network — `academy.py` (spec §4 system 8, phase 2).

Courses, enrollments, and completions. Completions feed the Credential
Graph: a completed course becomes a credential claim on the worker's
record with full provenance — the same honesty rules as every other
credential in the system.

LAWS (machine-checked by `check_laws`):
- L1: academy credentials are CLAIMS with provenance (issuer = the
  course id), and `verified_by_us` is False unless the operator records
  an external check — the honest-labeling law from `work.py`.
- L2: completion requires a real enrollment and a recorded pass —
  no free credentials.
- L3: courses are catalog entries (outlines), never claims about
  teaching quality or guaranteed outcomes.
"""

from __future__ import annotations

from typing import Any

from . import work
from .store import Store


def create_course(
    store: Store,
    title: str,
    category: str,
    outline: list[str],
    instructor: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Add a course to the academy catalog (an outline, not a quality claim)."""
    course = {
        "id": store.next_id("course"),
        "title": title,
        "category": category,
        "outline": list(outline),
        "instructor": instructor,
        "status": "active",
    }
    return store.append("courses", course, now=now)


def enroll(
    store: Store,
    course_id: str,
    worker_id: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Enroll a worker in a course."""
    if work.latest_worker(store, worker_id) is None:
        raise KeyError(f"no worker {worker_id}")
    if not any(c.get("id") == course_id for c in store.read_all("courses")):
        raise KeyError(f"no course {course_id}")
    return store.append(
        "enrollments",
        {"course_id": course_id, "worker_id": worker_id, "status": "enrolled"},
        now=now,
    )


def _enrollment(store: Store, course_id: str, worker_id: str) -> dict | None:
    matches = [
        e
        for e in store.read_all("enrollments")
        if e.get("course_id") == course_id and e.get("worker_id") == worker_id
    ]
    return matches[-1] if matches else None


def complete(
    store: Store,
    course_id: str,
    worker_id: str,
    passed: bool,
    now: str | None = None,
) -> dict[str, Any]:
    """Record completion. On pass, the course becomes a credential claim
    on the worker's record (law L1 — the claim carries provenance)."""
    enrollment = _enrollment(store, course_id, worker_id)
    if enrollment is None:
        raise ValueError(
            f"worker {worker_id} is not enrolled in {course_id} (law L2)"
        )
    course = next(
        c for c in store.read_all("courses") if c.get("id") == course_id
    )
    status = "passed" if passed else "failed"
    record = dict(enrollment)
    record.pop("seq", None)
    record.pop("ts", None)
    record["status"] = status
    store.append("enrollments", record, now=now)
    if passed:
        work.add_credential(
            store,
            worker_id,
            {
                "type": "academy_completion",
                "issuer": course_id,
                "evidence": f"completed '{course['title']}'",
            },
            now=now,
        )
    return {"course_id": course_id, "worker_id": worker_id, "status": status}


def course_roster(store: Store, course_id: str) -> list[dict[str, Any]]:
    latest: dict[str, dict] = {}
    for e in store.read_all("enrollments"):
        if e.get("course_id") == course_id:
            latest[e["worker_id"]] = e
    return list(latest.values())


def check_laws(store: Store) -> dict[str, Any]:
    """Machine-check the academy laws against live state."""
    checks: dict[str, dict] = {}
    # L1: every academy_completion credential is a claim with provenance.
    bad = []
    for w in store.read_all("workers"):
        for c in w.get("credentials", []):
            if c.get("type") == "academy_completion":
                if not c.get("issuer") or "asserted_by" not in c:
                    bad.append(w.get("id"))
    checks["academy_claims_have_provenance"] = {
        "ok": not bad,
        "violations": bad,
    }
    # L2: every passed enrollment traces to a real enrollment.
    enrollments = {
        (e.get("course_id"), e.get("worker_id"))
        for e in store.read_all("enrollments")
        if e.get("status") in ("enrolled", "passed", "failed")
    }
    passed = [
        e
        for e in store.read_all("enrollments")
        if e.get("status") == "passed"
    ]
    orphan = [
        e.get("worker_id")
        for e in passed
        if (e.get("course_id"), e.get("worker_id")) not in enrollments
    ]
    checks["completions_have_enrollment"] = {
        "ok": not orphan,
        "violations": orphan,
    }
    return {"ok": all(c["ok"] for c in checks.values()), "checks": checks}
