"""Build per-subject field guides from the ingested corpus.

Deterministic and extractive (no LLM): for each subject in catalog.json,
writes briefs/<subject-slug>.md containing the course list with schools,
top topic keywords aggregated from fetched texts (stopwords removed), and
"start here" picks (first 3 courses whose primary link is live per
coverage.json).

Usage: python3 build_briefs.py
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
BRIEFS = BASE / "briefs"

STOPWORDS = set(
    """
a about above after again against all am an and any are as at be because been
before being below between both but by can cannot could did do does doing down
during each few for from further had has have having he her here hers herself
him himself his how i if in into is it its itself let's me more most my myself
no nor not of off on once only or other ought our ours ourselves out over own
same she should so some such than that the their theirs them themselves then
there these they this those through to too under until up very was we were
what when where which while who whom why with would you your yours yourself
yourselves will also one two new using used use may many much like get within
course courses university college school class classes lecture lectures
introduction intro introductory advanced students student learn learning
topics topic cover covers covered including include includes part parts
http https www com org edu html pdf
""".split()
)


def keywords(texts: list[str], n: int = 25) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for text in texts:
        for w in re.findall(r"[a-z]{4,}", text.lower()):
            if w not in STOPWORDS:
                counts[w] += 1
    return counts.most_common(n)


def _load_briefs_inputs() -> tuple[dict, dict[str, dict]]:
    """Load catalog.json + coverage.json with actionable schema errors.

    Returns ``(catalog, coverage_by_id)``. Raises ValueError (never a raw
    JSONDecodeError/KeyError traceback) when files are missing or malformed.
    """
    try:
        catalog = json.loads((BASE / "catalog.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(
            "build-briefs: catalog.json not found; run ingest first"
        ) from None
    except (OSError, ValueError) as exc:
        raise ValueError(
            "build-briefs: catalog.json is not valid JSON: %s" % exc
        ) from exc
    if not isinstance(catalog, dict) or not isinstance(catalog.get("subjects"), list):
        raise ValueError(
            "build-briefs: catalog.json must be {subjects: [...]}; fix catalog.json"
        )
    coverage: dict[str, dict] = {}
    cov_path = BASE / "coverage.json"
    if cov_path.exists():
        try:
            raw = json.loads(cov_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(
                "build-briefs: coverage.json is not valid JSON: %s" % exc
            ) from exc
        if not isinstance(raw, list):
            raise ValueError("build-briefs: coverage.json must be a list of records")
        for rec in raw:
            if isinstance(rec, dict) and isinstance(rec.get("id"), str):
                coverage[rec["id"]] = rec
    return catalog, coverage


def main() -> int:
    try:
        catalog, coverage = _load_briefs_inputs()
    except ValueError as exc:
        print(exc)
        return 2
    BRIEFS.mkdir(parents=True, exist_ok=True)

    for subj in catalog["subjects"]:
        slug = subj["slug"]
        # O(1) coverage lookup per course (was an O(coverage) scan per course)
        by_title = {
            rec.get("title"): rec
            for cid, rec in coverage.items()
            if cid.startswith(slug + "/") and isinstance(rec.get("title"), str)
        }
        texts: list[str] = []
        rows: list[str] = []
        live: list[dict] = []
        for course in subj["courses"]:
            rows.append(f"- **{course['title']}** — {course['school'] or 'n/a'}")
            if course.get("description"):
                rows.append(f"  - {course['description'][:220]}")
            rec = by_title.get(course["title"])
            status = rec["status"] if rec else "unaccounted"
            rows.append(f"  - [{status}] {course['primary']}")
            if rec and rec["status"] == "ok" and rec.get("file"):
                p = BASE / rec["file"]
                if p.exists():
                    texts.append(p.read_text(encoding="utf-8", errors="replace"))
                live.append(course)
        top = keywords(texts)
        start_here = live[:3]
        lines = [
            f"# {subj['name']} — field guide",
            "",
            f"_Source: awesome-courses catalog; {len(subj['courses'])} courses listed, "
            f"{len(texts)} full texts ingested. Extractive summary — keyword "
            f"frequencies from fetched course pages, not expert judgment._",
            "",
            "## Start here (live links verified at ingest time)",
            "",
        ]
        if start_here:
            for c in start_here:
                lines.append(f"- **{c['title']}** ({c['school']}) — {c['primary']}")
        else:
            lines.append("- _No live primary links in this subject yet._")
        lines += ["", "## Topic keywords (by frequency in ingested texts)", ""]
        if top:
            lines.append(", ".join(f"{w} ({n})" for w, n in top))
        else:
            lines.append("_No ingested texts yet._")
        lines += ["", "## All courses", ""]
        lines += rows
        lines += ["", "_Generated from catalog.json + coverage.json._", ""]
        (BRIEFS / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")
        print(
            f"  {slug}: {len(texts)} texts, {len(rows)} course rows, "
            f"{len(''.join(lines))} chars"
        )
    print("briefs written to", BRIEFS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
