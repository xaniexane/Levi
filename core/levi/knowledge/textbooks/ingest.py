"""Ingest OpenStax college textbooks into a local text corpus.

Reads ``books.json`` (slug/title/subjects/repo/sha/uuid/license per book;
English college editions only), fetches each book's baked-source tree from
GitHub, parses the collection XML for chapter order, extracts module text
from CNXML, and stores it under ``raw/<book-slug>/<nn>-<module>.txt``.
Writes ``catalog.json`` and ``coverage.json`` with per-book status.

All OpenStax titles are openly licensed (CC BY); every stored file keeps
its title, source repo, and license line for attribution.

Fetching: stdlib urllib.request with a 20s timeout, 0.25s delay between
requests, and a LEVI user-agent. GitHub API use stays at ~1 request per
book (recursive tree); module bodies come from raw.githubusercontent.com,
which is not API-rate-limited. All parsing/extraction is stdlib.

Usage: python3 ingest.py [--limit N] [--book slug]
Idempotent: skips books already recorded in coverage.json unless --refetch.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parent
RAW = BASE / "raw"
BOOKS = BASE / "books.json"
COVERAGE = BASE / "coverage.json"
CATALOG = BASE / "catalog.json"
UA = "LEVI-textbook-ingest/1.0 (open-education knowledge base; polite 0.25s delay)"
TIMEOUT = 20
DELAY = 0.25
MAX_CHARS = 30_000  # per module; corpus seeder takes its own slice


def fetch(url: str, max_bytes: int = 4_000_000) -> tuple[bytes | None, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            if not (200 <= resp.status < 300):
                return None, f"HTTP {resp.status}"
            body = resp.read(max_bytes + 1)
    except Exception as exc:  # noqa: BLE001 - never crash the pass
        return None, f"fetch error: {type(exc).__name__}"
    if len(body) > max_bytes:
        return None, "body over cap"
    return body, "ok"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def cnxml_to_text(data: bytes) -> str:
    """Extract readable text from a CNXML module (stdlib XML)."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return ""
    chunks: list[str] = []
    for el in root.iter():
        name = _local(el.tag)
        if name in (
            "title",
            "para",
            "list",
            "item",
            "table",
            "entry",
            "definition",
            "meaning",
            "example",
            "note",
            "equation",
        ):
            if el.text and el.text.strip():
                chunks.append(el.text.strip())
            # capture tails of inline elements via itertext on block level
            if name in ("title", "para", "item", "entry", "meaning"):
                tail_text = "".join(el.itertext()).strip()
                if tail_text and (not chunks or chunks[-1] != tail_text):
                    if chunks:
                        chunks[-1] = tail_text
                    else:
                        chunks.append(tail_text)
        if name in ("title", "para", "item"):
            chunks.append("\n")
    text = html.unescape("\n".join(chunks))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def collection_order(data: bytes) -> list[tuple[str, str]]:
    """Return (module_id, title) in collection order from a .collection.xml."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    out: list[tuple[str, str]] = []
    for el in root.iter():
        if _local(el.tag) == "module":
            mid = el.get("document") or ""
            title = ""
            for child in el:
                if _local(child.tag) == "title" and child.text:
                    title = child.text.strip()
            if mid:
                out.append((mid, title))
    return out


def slug(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text[:60] or "module"


def ingest_book(book: dict) -> dict:
    repo = book["repo"]
    sha = book["sha"]
    tree_url = f"https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1"
    body, detail = fetch(tree_url)
    if body is None:  # one retry: GitHub API can hiccup or rate-limit briefly
        time.sleep(5)
        body, detail = fetch(tree_url)
    time.sleep(DELAY)
    if body is None:
        return {"status": "dead", "detail": f"tree: {detail}"}
    try:
        tree = json.loads(body)["tree"]
    except (json.JSONDecodeError, KeyError):
        return {"status": "dead", "detail": "bad tree JSON"}
    paths = [t["path"] for t in tree if t.get("type") == "blob"]
    cnxml: dict[str, str] = {}
    for p in paths:
        if not (p.startswith("modules/") and p.endswith(".cnxml")):
            continue
        # Layout is modules/<mid>/index.cnxml (also tolerate modules/<mid>.cnxml).
        rest = p[len("modules/") :]
        mid = rest.split("/", 1)[0].rsplit(".cnxml", 1)[0]
        cnxml[mid] = p
    collections = [
        p
        for p in paths
        if p.startswith("collections/") and p.endswith(".collection.xml")
    ]
    if not cnxml or not collections:
        return {"status": "dead", "detail": "no modules/collections"}

    # Prefer the collection matching this book's slug exactly (bundle repos
    # hold several books), then a contains-match, then the first.
    want = f"collections/{book['slug']}.collection.xml"
    coll_path = next((c for c in collections if c == want), None)
    if coll_path is None:
        stem = book["slug"].split("-2e")[0].split("-3e")[0]
        coll_path = next((c for c in collections if stem in c), collections[0])
    cbody, cdetail = fetch(
        f"https://raw.githubusercontent.com/{repo}/{sha}/{coll_path}"
    )
    time.sleep(DELAY)
    if cbody is None:
        return {"status": "dead", "detail": f"collection: {cdetail}"}
    order = collection_order(cbody)
    if not order:
        # Fall back: every module, alphabetical.
        order = [(mid, mid) for mid in sorted(cnxml)]

    book_dir = RAW / book["slug"]
    book_dir.mkdir(parents=True, exist_ok=True)
    got, failed = 0, 0
    for i, (mid, title) in enumerate(order):
        mid = mid.split("@")[0]  # defensive: strip any @version suffix
        mpath = cnxml.get(mid)
        if not mpath:
            failed += 1
            continue
        mbody, mdetail = fetch(
            f"https://raw.githubusercontent.com/{repo}/{sha}/{mpath}"
        )
        time.sleep(DELAY)
        if mbody is None:
            failed += 1
            continue
        text = cnxml_to_text(mbody)
        if len(text) < 200:
            failed += 1
            continue
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + "\n[truncated]"
        header = (
            f"# {title or mid}\n"
            f"# Book: {book['title']}\n"
            f"# Subject: {book.get('subject', '')}\n"
            f"# Source: https://github.com/{repo}\n"
            f"# License: {book.get('license', 'CC BY (OpenStax)')}\n\n"
        )
        (book_dir / f"{i:03d}-{slug(title or mid)}.txt").write_text(
            header + text, encoding="utf-8"
        )
        got += 1
    return {
        "status": "ok" if got else "dead",
        "detail": f"{got} modules, {failed} failed",
        "modules": got,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest OpenStax textbooks.")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--book", default="")
    ap.add_argument("--refetch", action="store_true")
    args = ap.parse_args(argv)

    try:
        books = json.loads(BOOKS.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("ingest: books.json not found", file=sys.stderr)
        return 1
    coverage: dict[str, dict] = {}
    if COVERAGE.exists():
        coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))

    if args.book:
        books = [b for b in books if b["slug"] == args.book]
    if args.limit:
        books = books[: args.limit]

    catalog = []
    for book in books:
        slug_ = book["slug"]
        if slug_ in coverage and not args.refetch:
            catalog.append({"slug": slug_, **book, **coverage[slug_]})
            continue
        print(f"ingest: {slug_} ...", flush=True)
        result = ingest_book(book)
        time.sleep(DELAY)
        coverage[slug_] = result
        catalog.append({"slug": slug_, **book, **result})
        print(f"ingest: {slug_}: {result['status']} ({result['detail']})", flush=True)
        COVERAGE.write_text(json.dumps(coverage, indent=1), encoding="utf-8")

    CATALOG.write_text(json.dumps(catalog, indent=1), encoding="utf-8")
    ok = sum(1 for b in catalog if b.get("status") == "ok")
    mods = sum(b.get("modules", 0) for b in catalog)
    print(f"ingest: {ok}/{len(catalog)} books ok, {mods} modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
