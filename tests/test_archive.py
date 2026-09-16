"""Hermetic tests for the LEVI Archive (Smithsonian module).

No network, no user HOME writes (ArchiveStore takes an explicit home),
no real research reports — parsers are tested on small synthetic fixtures
in the three heading styles.
"""

import json
from pathlib import Path

import pytest

from levi.archive import ingest as ing
from levi.archive.record import (ArchiveRecord, Provenance, make_id, slugify)
from levi.archive.search import build_collections, search
from levi.archive.store import ArchiveStore

SW30_FIXTURE = """# Fake Report

## Methodology

### 1. Fakecard (Fakeco, 1987–2004)
- **What/when:** A fake card system from 1987, bundled with everything.
- **Ahead-of-its-time mechanism:** Zero-mode-switch editing; the card you read is the card you edit.
  It also had a second line of mechanism text.
- **Why it faded:** The web won by being good enough and networked.
- **Revival recipe:** Pair cards with local sandboxed generation.
- **Application:** Track houseplants on cards.

### 2. GhostOS (Ghost Inc, 1990–1995)
- **What/when:** A ghost OS. Still alive today via hobbyists — flagged honestly.
- **Ahead-of-its-time mechanism:** Everything is a file.
- **Why it \"retired\":** No apps.
- **Revival recipe:** Namespaces on top of the host OS.
- **Application:** Per-agent namespaces.

## Ranked Top 10

1. Fakecard is great.
"""

SW50_FIXTURE = """# Fake 50

## 1. Fakernel 🟡 — **LOAD-BEARING**
1. Fake kernel, 2001; still sold.
2. Mechanism: message-passing microkernel with restartable servers.
3. Died: never died; confined to embedded.
4. Revival: adopt the resource-manager discipline locally.
5. App: crashed drivers restart without losing state.
Sources:
- https://example.com/fakernel
- https://example.org/fakernel-docs

## 2. Oldstep 🔴 (absorbed — do not call the ideas dead) — **USEFUL PATTERN**
1. Oldstep, 1989–1995; became an ancestor.
2. Mechanism: live object wiring.
3. Died: hardware too expensive; absorbed into a bigger OS.
4. Revival: keep the live wiring idea.
5. App: offline agent builder.
Sources:
- https://example.com/oldstep

# Ranked Top 10

1. Fakernel wins.
"""

M40_FIXTURE = """# Fake Methods

## 1. The Fake Loci (classical art) — LOAD-BEARING

**What it was:** A fake memory technique from antiquity.

**Mechanism:** Spatial hooks preserve sequence.

**Why it died:** Writing removed the pressure.

**Revival recipe:** The assistant builds memory palaces locally.

**Application:** Learn a talk via palace walks.

**Skepticism:** The founding myth is legendary, not fact.

- https://example.com/loci

## 2. Fake Wheels — INSPIRATIONAL

**What it was:** Rotating wheels of fake categories.

**Mechanism:** Exhaust the combinations mechanically.

**Why it died:** The combinations were vacuous.

**Revival recipe:** Use the form with grounded primitives.

**Application:** Ideation by exhaustion.

- https://example.com/wheels

## Ranked Top 10

1. Loci first.
"""


def _prov(slug="fake-research-1"):
    return Provenance(found_date="2026-09-16", research_slug=slug,
                      notes="synthetic fixture")


def _rec(**kw):
    base = dict(id="arch-t-fake-one", title="Fake One", era="1990",
                kind="software", summary="s", mechanism="m", decline="d",
                revival_recipe="r", levi_application="a",
                provenance=_prov())
    base.update(kw)
    return ArchiveRecord(**base)


# -- record validation ----------------------------------------------------

def test_record_roundtrip():
    rec = _rec(sources=["https://example.com/x"], rating="load-bearing",
               status="preserved", skepticism="maybe myth")
    d = rec.to_dict()
    back = ArchiveRecord.from_dict(d)
    assert back == rec


def test_record_rejects_bad_kind():
    with pytest.raises(ValueError):
        _rec(kind="spell")


def test_record_rejects_bad_rating_and_status():
    with pytest.raises(ValueError):
        _rec(rating="game-changing")
    with pytest.raises(ValueError):
        _rec(status="mostly-dead")


def test_record_rejects_bad_url_and_empty_fields():
    with pytest.raises(ValueError):
        _rec(sources=["ftp://example.com/x"])
    with pytest.raises(ValueError):
        _rec(title="  ")
    with pytest.raises(ValueError):
        _rec(mechanism="")


def test_record_rejects_bad_id():
    with pytest.raises(ValueError):
        _rec(id="not a slug!!")


def test_provenance_requires_fields():
    with pytest.raises(ValueError):
        Provenance.from_dict({"found_date": "2026-09-16"})
    with pytest.raises(ValueError):
        ArchiveRecord.from_dict({**_rec().to_dict(),
                                 "provenance": {"found_date": "x"}})


def test_slugify_and_make_id():
    assert slugify("HyperCard (Apple, 1987–2004)") == "hypercard-apple-1987-2004"
    rid = make_id("software", "sw30", "HyperCard", "Apple, 1987-2004")
    assert rid.startswith("arch-sw30-software-hypercard-apple-1987-2004")
    assert make_id("software", "sw30", "X", "", 2).endswith("-2")


# -- sw30 parser ----------------------------------------------------------

def test_parse_sw30_two_entries():
    recs = ing.parse_sw30(SW30_FIXTURE, _prov())
    assert len(recs) == 2
    r1, r2 = recs
    assert r1.title == "Fakecard"
    assert r1.era == "Fakeco, 1987–2004"
    assert r1.kind == "software"
    assert "second line of mechanism" in r1.mechanism  # continuation lines
    assert "good enough and networked" in r1.decline
    assert r1.rating == "unrated"
    assert r1.status == "dead"
    assert r2.status == "alive-underused"  # "Still alive today" heuristic
    assert r1.sources == []
    assert r1.provenance.research_slug == "fake-research-1"
    assert r1.id.startswith("arch-sw30-software-fakecard-")


def test_parse_sw30_stops_before_ranked_list():
    recs = ing.parse_sw30(SW30_FIXTURE, _prov())
    assert all("great" not in r.title for r in recs)


# -- sw50 parser ----------------------------------------------------------

def test_parse_sw50_badges_and_ratings():
    recs = ing.parse_sw50(SW50_FIXTURE, _prov())
    assert len(recs) == 2
    r1, r2 = recs
    assert r1.title == "Fakernel"
    assert r1.rating == "load-bearing"
    assert r1.status == "alive-underused"  # 🟡
    assert r1.sources == ["https://example.com/fakernel",
                          "https://example.org/fakernel-docs"]
    assert "message-passing microkernel" in r1.mechanism
    assert r2.title == "Oldstep"
    assert r2.rating == "useful-pattern"
    assert r2.status == "absorbed"  # absorbed note wins over 🔴
    assert r2.id.startswith("arch-sw50-software-oldstep")


# -- m40 parser -----------------------------------------------------------

def test_parse_m40_skepticism_and_sources():
    recs = ing.parse_m40(M40_FIXTURE, _prov())
    assert len(recs) == 2
    r1, r2 = recs
    assert r1.title == "The Fake Loci (classical art)"
    assert r1.kind == "method"
    assert r1.rating == "load-bearing"
    assert "legendary, not fact" in r1.skepticism
    assert r1.sources == ["https://example.com/loci"]
    assert r2.rating == "inspirational"
    assert r2.skepticism == ""


# -- dedup ----------------------------------------------------------------

def test_dedup_within_report_skips_true_repeats():
    dup = SW30_FIXTURE.replace(
        "### 2. GhostOS (Ghost Inc, 1990–1995)",
        "### 2. Fakecard (Fakeco, 1987–2004)")
    recs = ing.parse_sw30(dup, _prov())
    assert len(recs) == 1  # second identical identity skipped


def test_same_title_different_reports_coexist():
    a = ing.parse_sw30(SW30_FIXTURE, _prov("slug-a"))
    b = ing.parse_sw30(SW30_FIXTURE, _prov("slug-b"))
    # ids differ only by report tag if we re-tag: simulate via make_id
    assert a[0].title == b[0].title
    assert a[0].provenance.research_slug != b[0].provenance.research_slug


# -- store ----------------------------------------------------------------

def test_store_add_get_and_duplicate_refusal(tmp_path):
    store = ArchiveStore(home=tmp_path)
    rec = _rec()
    store.add(rec)
    assert store.get(rec.id) == rec
    with pytest.raises(ValueError):
        store.add(rec)  # never silently overwrite


def test_store_add_many_skips_dupes(tmp_path):
    store = ArchiveStore(home=tmp_path)
    result = store.add_many([_rec(), _rec()])
    assert result == {"added": 1, "skipped": 1}


def test_store_roundtrip_and_permissions(tmp_path):
    store = ArchiveStore(home=tmp_path)
    store.add(_rec(id="arch-t-fake-two", title="Fake Two"))
    assert (tmp_path / ".levi" / "archive").stat().st_mode & 0o777 == 0o700
    assert store.records_path.stat().st_mode & 0o777 == 0o600
    fresh = ArchiveStore(home=tmp_path)
    assert fresh.count() == 1
    assert fresh.get("arch-t-fake-two").title == "Fake Two"


def test_store_rejects_non_records(tmp_path):
    store = ArchiveStore(home=tmp_path)
    with pytest.raises(ValueError):
        store.add({"id": "arch-x"})


# -- search ---------------------------------------------------------------

def _search_store(tmp_path):
    store = ArchiveStore(home=tmp_path)
    store.add_many([
        _rec(id="arch-t-alpha", title="Alpha Replication",
             summary="offline replica sync", mechanism="bidirectional sync",
             rating="load-bearing", status="alive-underused"),
        _rec(id="arch-t-beta", title="Beta Cards",
             summary="card stacks", mechanism="hypertext cards",
             rating="useful-pattern", status="dead"),
    ])
    return store


def test_search_title_outranks_body(tmp_path):
    store = _search_store(tmp_path)
    hits = search(store, "replication")
    assert hits[0].record.id == "arch-t-alpha"
    assert "title:replication" in hits[0].why


def test_search_filters(tmp_path):
    store = _search_store(tmp_path)
    assert [h.record.id for h in search(store, "", kind="software")] != []
    assert search(store, "", kind="method") == []
    assert [h.record.id for h in search(store, "", rating="load-bearing")] == ["arch-t-alpha"]
    assert [h.record.id for h in search(store, "", status="dead")] == ["arch-t-beta"]
    with pytest.raises(ValueError):
        search(store, "", kind="spell")


def test_search_prefix_fallback(tmp_path):
    store = _search_store(tmp_path)
    hits = search(store, "replic")
    assert hits and hits[0].record.id == "arch-t-alpha"


# -- collections ----------------------------------------------------------

def test_collections_are_explainable(tmp_path):
    store = _search_store(tmp_path)
    wings = build_collections(store.all())
    offline = wings["offline-first"]
    assert "arch-t-alpha" in offline.record_ids  # "replication"/"offline"/"sync"
    assert offline.matched_keywords["arch-t-alpha"]  # keywords listed


# -- ingest_reports with synthetic research root --------------------------

def test_ingest_reports_from_fake_root(tmp_path):
    root = tmp_path / "research_notes"
    (root / "s1").mkdir(parents=True)
    (root / "s1" / "report.md").write_text(SW30_FIXTURE, encoding="utf-8")
    # point the sw30 spec at our fake slug via a patched spec list
    spec = [s for s in ing.REPORTS if s["tag"] == "sw30"][0]
    fake_spec = dict(spec, slug="s1")
    orig = ing.REPORTS
    ing.REPORTS = [fake_spec]
    try:
        recs, errors = ing.ingest_reports(root)
    finally:
        ing.REPORTS = orig
    assert errors == []
    assert len(recs) == 2


def test_ingest_reports_missing_file_is_error(tmp_path):
    root = tmp_path / "research_notes"
    root.mkdir()
    recs, errors = ing.ingest_reports(
        root, slugs=["retired-software-revival-research-20260916-0004"])
    assert recs == []
    assert errors and "missing report file" in errors[0]
