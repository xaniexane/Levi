"""Build per-subject field guides from the ingested textbook corpus.

Deterministic and extractive (no LLM): for each subject in books.json,
writes briefs/<subject-slug>.md containing the book list with chapter
counts, top topic keywords aggregated from chapter texts (stopwords
removed), and "start here" picks (first book per subject, alphabetically).

Usage: python3 build_briefs.py
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
BRIEFS = BASE / "briefs"
RAW = BASE / "raw"

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
chapter chapters figure figures table tables example examples section sections
defined definition term terms following shows show shown using used
http https www com org edu html
""".split()
)


def keywords(texts: list[str], n: int = 30) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for text in texts:
        for w in re.findall(r"[a-z]{4,}", text.lower()):
            if w not in STOPWORDS:
                counts[w] += 1
    return counts.most_common(n)


def main() -> int:
    try:
        books = json.loads((BASE / "books.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("build-briefs: books.json not found; nothing to summarize")
        return 2
    coverage: dict[str, dict] = {}
    if (BASE / "coverage.json").exists():
        coverage = json.loads((BASE / "coverage.json").read_text(encoding="utf-8"))

    by_subject: dict[str, list[dict]] = {}
    for b in books:
        by_subject.setdefault(b.get("subject", "misc"), []).append(b)

    BRIEFS.mkdir(parents=True, exist_ok=True)
    for subject, blist in sorted(by_subject.items()):
        texts: list[str] = []
        rows: list[str] = []
        total_ch = 0
        for b in sorted(blist, key=lambda x: x["slug"]):
            cov = coverage.get(b["slug"], {})
            ch = cov.get("modules", 0)
            total_ch += ch
            status = cov.get("status", "unaccounted")
            rows.append(f"- **{b['title']}** — {ch} chapters [{status}]")
            rows.append(f"  - {b['source']} · {b['license']}")
            if cov.get("status") == "ok":
                for fp in sorted(
                    (RAW / b["slug"]).glob("*.txt")
                    if (RAW / b["slug"]).exists()
                    else []
                ):
                    try:
                        texts.append(fp.read_text(encoding="utf-8", errors="replace"))
                    except OSError:
                        pass
        top = keywords(texts)
        slug = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")
        lines = [
            f"# {subject.title()} — field guide",
            "",
            f"_Source: OpenStax openly-licensed college textbooks (CC BY); "
            f"{len(blist)} books, {total_ch} chapters ingested. Extractive "
            f"summary — keyword frequencies from chapter text, not expert judgment._",
            "",
            "## Books",
            "",
            *rows,
            "",
            "## Top terms across chapters",
            "",
            ", ".join(f"{w} ({c})" for w, c in top)
            if top
            else "_no text ingested yet_",
            "",
        ]
        (BRIEFS / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")
        print(f"briefs: {slug}.md ({len(blist)} books, {total_ch} chapters)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
