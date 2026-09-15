"""Session-time research for LEVI Boot Camp.

Public sources only. The worker researches each session's topic, then
``synthesize.py`` turns the findings into ORIGINAL LEVI-authored lesson
content — source text is never copied into lessons.

Web path: Wikipedia REST summary API (stable, public, no key) via stdlib
urllib with tight timeouts. Local fallback: LEVI's own offline materials
(archived academy lessons, the security index catalog, docs inventory),
so a session always completes even with no network.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ACADEMY_DIR = Path(__file__).resolve().parent

_WIKI = "https://en.wikipedia.org/api/rest_v1/page/summary/"
_UA = {"User-Agent": "LEVI-BootCamp/1.0 (offline-first training; contact: local)"}

_STOP = frozenset(
    "the a an of in on for to with and or as is are was were be by from at "
    "that this these those it its into over under between within without "
    "about which who whom whose when where how what why can may will would "
    "should could must shall do does did done have has had having not no yes "
    "if then than so such more most other some any each every all both per "
    "via also including include includes used use using often known".split()
)


def _wiki_summary(query: str, timeout: float = 12.0) -> dict | None:
    """Fetch one Wikipedia summary. Returns None on any failure."""
    url = _WIKI + urllib.parse.quote(query.replace(" ", "_"))
    req = urllib.request.Request(url, headers={**_UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:
        return None
    if data.get("type") == "disambiguation":
        return None
    extract = (data.get("extract") or "").strip()
    if len(extract) < 80:
        return None
    return {
        "title": data.get("title", query),
        "description": (data.get("description") or "").strip(),
        "extract": extract,
        "url": (data.get("content_urls", {}).get("desktop", {}) or {}).get("page", ""),
    }


def extract_key_terms(text: str, limit: int = 12) -> list[str]:
    """Salient multi-word / capitalized terms from source text.

    Used as vocabulary grounding for original synthesis — the terms inform
    wording, but source sentences are never copied into lessons.
    """
    terms: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"\b([A-Z][a-zA-Z0-9&'\-]*(?:\s+[A-Z][a-zA-Z0-9&'\-]*){0,3})\b", text):
        t = m.group(1).strip()
        low = t.lower()
        if len(t) < 3 or low in _STOP or t in seen:
            continue
        # skip sentence starts that are just common words
        if len(t.split()) == 1 and low in ("however", "additionally", "although"):
            continue
        seen.add(t)
        terms.append(t)
        if len(terms) >= limit:
            break
    return terms


def _queries_for(topic: str, track: str) -> list[str]:
    base = topic.split(":")[0].strip()
    queries = [base]
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", base) if w.lower() not in _STOP]
    if len(words) >= 2:
        queries.append(" ".join(words[:3]))
    hints = {
        "A": ["MITRE ATT&CK", "computer security"],
        "B": ["platform", "software"],
        "C": ["software", "computing"],
        "S": ["computer security", "software"],
    }
    for h in hints.get(track, []):
        queries.append(f"{base} {h}")
    # de-dup, cap at 3
    out: list[str] = []
    for q in queries:
        if q not in out:
            out.append(q)
        if len(out) == 3:
            break
    return out


def _local_fallback(topic: str, track: str) -> dict:
    """Offline research from LEVI's own materials. Never empty."""
    facts: list[str] = []
    sources: list[str] = []
    repo_core = ACADEMY_DIR.parent
    if track == "A":
        archive = ACADEMY_DIR / "lessons" / "archive" / "trackA_5day"
        if archive.exists():
            for md in sorted(archive.glob("*.md")):
                sources.append(f"local:academy/lessons/archive/trackA_5day/{md.name}")
            facts.append(
                "LEVI's archived defensive-analyst lessons cover the ATT&CK "
                "coverage map, detection engineering, threat hunting, DFIR, "
                "and hardening programs."
            )
        try:
            import sys
            sys.path.insert(0, str(repo_core.parent))
            from levi.knowledge.security.catalog import load_catalog
            cat = load_catalog()
            facts.append(
                f"LEVI's offline security index catalogs {len(cat)} defensive "
                "domains across 81 categories with descriptive attack profiles "
                "for detection engineering."
            )
            sources.append("local:knowledge/security catalog")
        except Exception:
            pass
    elif track == "C":
        docs_dir = repo_core.parent.parent / "docs"
        docs = sorted(docs_dir.glob("*.md")) if docs_dir.exists() else []
        for d in docs[:8]:
            sources.append(f"local:docs/{d.name}")
        facts.append(
            "LEVI's own docs inventory describes its agent runtime, skills, "
            "scheduling, memory, growth loop, finance, news, bounty, and King "
            "subsystems — the authoritative reference for domain mastery."
        )
    else:  # B and S
        facts.append(
            "Platform intelligence synthesizes public knowledge of how "
            "assistant, SecOps, fintech, and creator platforms operate: their "
            "interaction models, capability patterns, performance "
            "characteristics, and failure modes."
        )
        sources.append("local:platform-intelligence synthesis notes")
    if not facts:
        facts.append(
            f"Topic '{topic}' studied from the syllabus outline and prior "
            "session journals (compounding context)."
        )
    return {"facts": facts, "sources": sources, "mode": "local",
            "key_terms": extract_key_terms(topic), "queries": []}


def research_topic(topic: str, track: str = "A",
                   budget_seconds: float = 150.0) -> dict:
    """Research a session topic. Returns facts/sources/key_terms, web or local.

    Never raises on network failure: falls back to local materials so the
    session always completes inside its time budget.
    """
    deadline = time.time() + budget_seconds
    facts: list[str] = []
    sources: list[str] = []
    key_terms: list[str] = []
    queries = _queries_for(topic, track)
    tried = 0
    for q in queries:
        if time.time() >= deadline:
            break
        tried += 1
        page = _wiki_summary(q, timeout=min(12.0, max(4.0, deadline - time.time())))
        if not page:
            continue
        desc = page["description"]
        if desc:
            facts.append(f"{page['title']}: {desc}.")
        key_terms.extend(extract_key_terms(page["extract"]))
        if page["url"]:
            sources.append(page["url"])
        if len(facts) >= 3:
            break
    if facts:
        # de-dup key terms, keep order
        seen: set[str] = set()
        key_terms = [t for t in key_terms if not (t in seen or seen.add(t))][:12]
        return {"facts": facts, "sources": sources, "mode": "web",
                "key_terms": key_terms, "queries": queries[:tried]}
    return _local_fallback(topic, track)
