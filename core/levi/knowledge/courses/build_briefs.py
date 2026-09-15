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

STOPWORDS = set("""
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
""".split())


def keywords(texts: list[str], n: int = 25) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for text in texts:
        for w in re.findall(r"[a-z]{4,}", text.lower()):
            if w not in STOPWORDS:
                counts[w] += 1
    return counts.most_common(n)


def main() -> int:
    catalog = json.loads((BASE / "catalog.json").read_text(encoding="utf-8"))
    coverage = {}
    if (BASE / "coverage.json").exists():
        for rec in json.loads((BASE / "coverage.json").read_text(encoding="utf-8")):
            coverage[rec["id"]] = rec
    BRIEFS.mkdir(parents=True, exist_ok=True)

    for subj in catalog["subjects"]:
        slug = subj["slug"]
        texts: list[str] = []
        rows: list[str] = []
        live: list[dict] = []
        for course in subj["courses"]:
            rows.append(f"- **{course['title']}** — {course['school'] or 'n/a'}")
            if course.get("description"):
                rows.append(f"  - {course['description'][:220]}")
            cid = next((k for k in coverage
                        if k.startswith(slug + "/")
                        and coverage[k]["title"] == course["title"]), None)
            rec = coverage.get(cid) if cid else None
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
        lines += ["", f"_Generated from catalog.json + coverage.json._", ""]
        (BRIEFS / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")
        print(f"  {slug}: {len(texts)} texts, {len(rows)} course rows, "
              f"{len(''.join(lines))} chars")
    print("briefs written to", BRIEFS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
