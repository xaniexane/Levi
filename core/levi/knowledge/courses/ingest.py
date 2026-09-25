"""Ingest awesome-courses course pages into a local text corpus.

Reads core/levi/knowledge/courses/catalog.json, fetches each course's primary
link, extracts readable text, and stores it under
core/levi/knowledge/courses/raw/<subject-slug>/<course-slug>.txt.
Writes core/levi/knowledge/courses/coverage.json with per-course status.

Fetching: stdlib urllib.request with a 10s timeout, 0.3s delay between
requests, and a LEVI user-agent. All parsing/extraction is stdlib.

Usage: python3 ingest.py [--limit N] [--subject slug]
Idempotent: skips courses already recorded in coverage.json unless --refetch.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent
RAW = BASE / "raw"
COVERAGE = BASE / "coverage.json"
UA = "LEVI-course-ingest/1.0 (curriculum knowledge base; polite 0.3s delay)"
TIMEOUT = 10
DELAY = 0.3
MAX_CHARS = 20_000

VIDEO_HOSTS = (
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    "itunes.apple.com",
    "podcasts.apple.com",
    "dailymotion.com",
)
BINARY_EXTS = (".pdf", ".ppt", ".pptx", ".zip", ".mp4", ".mp3", ".dmg", ".exe")


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "course"


def classify(url: str) -> str | None:
    """Return a skip status or None if the URL is worth fetching."""
    if not url:
        return "dead"
    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    if any(v in host for v in VIDEO_HOSTS):
        return "skipped-video"
    if path.endswith(BINARY_EXTS):
        return "skipped-binary"
    return None


def fetch(url: str) -> tuple[str | None, str]:
    """Return (html_text, detail). Stdlib urllib with the politeness contract."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            ctype = resp.headers.get("Content-Type", "")
            body = resp.read(5_000_000 + 1)
    except Exception as exc:  # noqa: BLE001 - never crash the pass
        return None, f"fetch error: {type(exc).__name__}"
    if status is not None and not (200 <= status < 300):
        return None, f"HTTP {status}"
    if "html" not in ctype.lower() and "text" not in ctype.lower():
        return None, f"non-text content-type {ctype}"
    if len(body) > 5_000_000:
        return None, "body over 5MB cap"
    try:
        return body.decode("utf-8", "replace"), "ok"
    except Exception as exc:  # noqa: BLE001
        return None, f"decode error: {exc}"


def extract_text(html_text: str) -> str:
    text = re.sub(
        r"(?is)<(script|style|noscript|header|footer|nav)[^>]*>.*?</\1>", " ", html_text
    )
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def _load_catalog() -> dict:
    """Load and schema-validate catalog.json. Raises ValueError on corrupt
    data (never a raw KeyError/JSONDecodeError traceback)."""
    path = BASE / "catalog.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError("ingest: catalog not found at %s" % path) from None
    except (OSError, ValueError) as exc:
        raise ValueError("ingest: catalog.json is not valid JSON: %s" % exc) from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("subjects"), list):
        raise ValueError(
            "ingest: catalog.json must be {subjects: [...]}; "
            "fix catalog.json before ingesting"
        )
    for i, subj in enumerate(raw["subjects"]):
        if (
            not isinstance(subj, dict)
            or not isinstance(subj.get("slug"), str)
            or not subj["slug"]
        ):
            raise ValueError(
                "ingest: catalog subject #%d is missing a non-empty 'slug'" % i
            )
        if not isinstance(subj.get("courses"), list):
            raise ValueError(
                "ingest: catalog subject %r is missing a 'courses' list"
                % subj.get("slug")
            )
        for j, course in enumerate(subj["courses"]):
            if not isinstance(course, dict):
                raise ValueError(
                    "ingest: subject %r course #%d is not an object" % (subj["slug"], j)
                )
            for field in ("code", "title", "school", "primary"):
                if not isinstance(course.get(field), str) or not course[field].strip():
                    raise ValueError(
                        "ingest: subject %r course #%d is missing non-empty %r"
                        % (subj["slug"], j, field)
                    )
    return raw


def _load_coverage(refetch: bool) -> dict[str, dict]:
    """Load coverage.json, tolerating nothing but silence on first run."""
    coverage: dict[str, dict] = {}
    if not COVERAGE.exists() or refetch:
        return coverage
    try:
        raw = json.loads(COVERAGE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(
            "ingest: coverage.json is not valid JSON (%s); delete it to start "
            "fresh, or fix it" % exc
        ) from exc
    if not isinstance(raw, list):
        raise ValueError(
            "ingest: coverage.json must be a list of records; "
            "delete it to start fresh, or fix it"
        )
    for rec in raw:
        if isinstance(rec, dict) and isinstance(rec.get("id"), str):
            coverage[rec["id"]] = rec
    return coverage


def _checkpoint(coverage: dict[str, dict]) -> None:
    """Atomically persist coverage so an interrupted run keeps progress."""
    tmp = COVERAGE.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(sorted(coverage.values(), key=lambda r: r["id"]), indent=1),
        encoding="utf-8",
    )
    tmp.replace(COVERAGE)


def main(argv: list[str]) -> int:
    limit = None
    only_subject = None
    refetch = False
    for a in argv:
        if a.startswith("--limit="):
            try:
                limit = int(a.split("=", 1)[1])
            except ValueError:
                print("ingest: --limit must be a positive integer")
                return 2
            if limit < 1:
                print("ingest: --limit must be a positive integer")
                return 2
        elif a.startswith("--subject="):
            only_subject = a.split("=", 1)[1]
        elif a == "--refetch":
            refetch = True

    try:
        catalog = _load_catalog()
        coverage = _load_coverage(refetch)
    except ValueError as exc:
        print(exc)
        return 2

    records: list[dict] = []
    done = 0
    for subj in catalog["subjects"]:
        if only_subject and subj["slug"] != only_subject:
            continue
        dest_dir = RAW / subj["slug"]
        dest_dir.mkdir(parents=True, exist_ok=True)
        for course in subj["courses"]:
            cid = f"{subj['slug']}/{slug(course['code'] + '-' + course['title'])}"
            if cid in coverage and not refetch:
                records.append(coverage[cid])
                continue
            if limit is not None and done >= limit:
                break
            rec = {
                "id": cid,
                "subject": subj["slug"],
                "title": course["title"],
                "school": course["school"],
                "primary": course["primary"],
                "status": "dead",
                "detail": "",
            }
            skip = classify(course["primary"])
            if skip:
                rec["status"] = skip
                rec["detail"] = "primary link host/type"
            else:
                page, detail = fetch(course["primary"])
                if page is None:
                    rec["status"] = "dead"
                    rec["detail"] = detail
                else:
                    text = extract_text(page)[:MAX_CHARS]
                    if len(text.strip()) < 200:
                        rec["status"] = "dead"
                        rec["detail"] = "page had <200 chars of readable text"
                    else:
                        dest = dest_dir / (cid.split("/", 1)[1] + ".txt")
                        dest.write_text(
                            f"# {course['title']}\n# {course['school']}\n"
                            f"# source: {course['primary']}\n\n{text}",
                            encoding="utf-8",
                        )
                        rec["status"] = "ok"
                        rec["detail"] = f"{len(text)} chars"
                        rec["file"] = str(dest.relative_to(BASE))
            records.append(rec)
            coverage[cid] = rec
            done += 1
            time.sleep(DELAY)
            if done % 25 == 0:
                _checkpoint(coverage)
                print(f"  ...{done} attempted (checkpointed)", flush=True)

    # keep previously-recorded subjects when filtering
    if only_subject or limit:
        seen = {r["id"] for r in records}
        for cid, rec in coverage.items():
            if cid not in seen:
                records.append(rec)
    records.sort(key=lambda r: r["id"])
    _checkpoint({r["id"]: r for r in records})

    from collections import Counter

    counts = Counter(r["status"] for r in records)
    chars = sum(
        int((r.get("detail") or "0").split()[0]) for r in records if r["status"] == "ok"
    )
    print(f"attempted this run: {done}")
    print("status counts:", dict(counts))
    print(f"total corpus chars (ok): {chars}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
