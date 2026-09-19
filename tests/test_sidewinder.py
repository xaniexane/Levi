"""LEVI Sidewinder CURRICULUM tests: schema, corpus, progressions, editions, growth.

The course (training curriculum) lives in core/levi/sidewinder/curriculum/:

- schema (entry schema incl. the crisis-domain law);
- corpus loading: every entry valid, unique ids, deduped titles;
- prerequisite graph integrity: no dangling refs, no cycles;
- progressions: track ordering foundation -> applied -> mastery;
- editions: manifest-driven packs (schema + pack entries + dangling refs);
- growth pipeline: validate/dedup/append/consume/dry-run + stub emission;
- planned_titles.txt: parseable, unique, covers the corpus, >= 1000.

Run:  python3 tests/test_sidewinder.py     (has a real __main__ runner)
      python3 -m pytest tests/test_sidewinder.py -q
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.sidewinder import (  # noqa: E402
    DOMAINS,
    LEVELS,
    LEVEL_ORDER,
    SIDEWINDER_DOCTRINE,
    TRACKS,
)
from levi.sidewinder.curriculum import editions as editions_mod  # noqa: E402
from levi.sidewinder.curriculum import growth as growth_mod  # noqa: E402
from levi.sidewinder.curriculum.corpus import (  # noqa: E402
    format_entry,
    load_corpus,
    normalize_title,
)
from levi.sidewinder.curriculum.editions import (  # noqa: E402
    edition_corpus,
    format_edition,
    load_manifests,
    validate_manifest,
)
from levi.sidewinder.curriculum.progressions import (  # noqa: E402
    check_graph,
    learning_path,
    progression,
    track_counts,
)
from levi.sidewinder.curriculum.growth import (  # noqa: E402
    grow,
    load_planned_titles,
    write_stubs,
)
from levi.sidewinder.curriculum.schema import check_batch, validate_entry  # noqa: E402

MODULE_DIR = ROOT / "core" / "levi" / "sidewinder"
CURRICULUM_DIR = MODULE_DIR / "curriculum"


def _good_entry(**over):
    entry = {
        "id": "sw-plumbing-900",
        "title": "Test entry for schema checks",
        "domain": "plumbing",
        "tracks": ["restore", "improvise"],
        "level": "applied",
        "prerequisites": ["sw-foundations-007"],
        "difficulty": 2,
        "mechanism_check": ["how it is held"],
        "improvised_tools": ["on-hand substitute"],
        "steps": ["do the thing"],
        "stop_conditions": ["when to stop"],
    }
    entry.update(over)
    return entry


# ── schema ──────────────────────────────────────────────────────────

def test_schema_accepts_valid_entry():
    assert validate_entry(_good_entry()) == []


def test_schema_rejects_missing_keys():
    entry = _good_entry()
    del entry["tracks"]
    errors = validate_entry(entry)
    assert any("tracks" in e for e in errors)


def test_schema_rejects_bad_track_level_domain_id():
    assert validate_entry(_good_entry(tracks=["teleport"])) != []
    assert validate_entry(_good_entry(tracks=[])) != []
    assert validate_entry(_good_entry(level="expert")) != []
    assert validate_entry(_good_entry(domain="space")) != []
    assert validate_entry(_good_entry(id="nope")) != []
    assert validate_entry(_good_entry(id="sw-plumbing-900", domain="fasteners")) != []
    assert validate_entry(_good_entry(difficulty=9)) != []
    assert validate_entry(_good_entry(prerequisites=["not-an-id"])) != []
    assert validate_entry(_good_entry(steps=[])) != []


def test_schema_rejects_stubs():
    entry = _good_entry(stub=True)
    assert validate_entry(entry) != []


def test_schema_crisis_law():
    base = dict(
        id="sw-crisis-900",
        title="Crisis test",
        domain="crisis",
        tracks=["improvise"],
        level="applied",
        prerequisites=[],
        difficulty=3,
        mechanism_check=["scene safety"],
        improvised_tools=["cloth"],
        steps=["act"],
    )
    ok = dict(base, stop_conditions=[
        "Call for professional help FIRST — last resort otherwise.",
        "Do not attempt if the scene is unsafe.",
    ])
    assert validate_entry(ok) == []
    no_help_first = dict(base, stop_conditions=[
        "Be careful out there.",
        "Do not attempt if the scene is unsafe.",
    ])
    assert any("professional help" in e for e in validate_entry(no_help_first))
    no_boundary = dict(base, stop_conditions=[
        "Call for professional help FIRST — last resort otherwise.",
    ])
    assert any("do not attempt" in e for e in validate_entry(no_boundary))


def test_check_batch_splits_valid_invalid():
    valid, invalid = check_batch([_good_entry(), {"nope": True}])
    assert len(valid) == 1 and len(invalid) == 1


# ── corpus ──────────────────────────────────────────────────────────

def test_corpus_loads_clean():
    corpus = load_corpus()
    assert len(corpus) >= 80, f"starter corpus too small: {len(corpus)}"
    assert not corpus.bad_lines, f"bad lines: {corpus.bad_lines[:3]}"


def test_corpus_ids_unique_and_titles_deduped():
    corpus = load_corpus()
    ids = [e["id"] for e in corpus.entries]
    titles = [normalize_title(e["title"]) for e in corpus.entries]
    assert len(set(ids)) == len(ids)
    assert len(set(titles)) == len(titles)


def test_corpus_id_echoes_domain():
    corpus = load_corpus()
    for e in corpus.entries:
        assert e["id"].startswith(f"sw-{e['domain']}-"), e["id"]


def test_originating_case_present():
    corpus = load_corpus()
    spout = corpus.get("sw-plumbing-001")
    assert spout is not None
    assert spout.get("origin") is True
    assert "set screw" in format_entry(spout).lower()


def test_search_finds_spout_and_respects_filters():
    corpus = load_corpus()
    hits = corpus.search("tub spout removal")
    assert hits and hits[0]["id"] == "sw-plumbing-001"
    assert corpus.search("tub spout", domain="electrical") == []
    assert all("improvise" in e["tracks"] for e in corpus.search("bleeding", track="improvise"))


# ── curriculum graph ────────────────────────────────────────────────

def test_graph_has_no_dangling_refs_or_cycles():
    corpus = load_corpus()
    dangling, cycles = check_graph(corpus)
    assert dangling == [], dangling[:5]
    assert cycles == [], cycles[:2]


def test_all_tracks_have_entries_and_ordering():
    corpus = load_corpus()
    counts = track_counts(corpus)
    for track in TRACKS:
        assert counts[track] >= 1, f"track {track} empty"
        prog = progression(corpus, track)
        assert len(prog) == counts[track]
        orders = [LEVEL_ORDER[e["level"]] for e in prog]
        assert orders == sorted(orders), f"track {track} not level-ordered"


def test_learning_path_puts_prereqs_first():
    corpus = load_corpus()
    path = learning_path(corpus, "sw-plumbing-001")
    ids = [e["id"] for e in path]
    assert ids[-1] == "sw-plumbing-001"
    assert "sw-foundations-007" in ids[:-1]
    # foundations come before applied entries that need them
    assert ids.index("sw-foundations-007") < ids.index("sw-plumbing-001")


def test_foundations_spine_present():
    corpus = load_corpus()
    spine = corpus.by_domain("foundations")
    assert len(spine) >= 8
    assert all(e["level"] == "foundation" and not e["prerequisites"] for e in spine)


# ── crisis ethos ────────────────────────────────────────────────────

def test_doctrine_names_the_ethos():
    assert "lives depend on it" in SIDEWINDER_DOCTRINE.lower()
    assert "professional help first" in SIDEWINDER_DOCTRINE.lower()


def test_crisis_entries_carry_help_first():
    corpus = load_corpus()
    crisis = corpus.by_domain("crisis")
    assert len(crisis) >= 6
    for e in crisis:
        assert "improvise" in e["tracks"], e["id"]
        assert "professional help" in e["stop_conditions"][0].lower(), e["id"]
        assert any("do not attempt" in s.lower() for s in e["stop_conditions"]), e["id"]


# ── edition packs (manifest-driven) ─────────────────────────────────

def _manifest(**over):
    m = {
        "id": "test-pack",
        "name": "Test Pack",
        "blurb": "A pack for tests.",
        "selector": {"domains": ["general"], "tracks": [], "levels": [], "ids": []},
        "track_emphasis": ["create"],
        "entries": [],
    }
    m.update(over)
    return m


def test_first_responder_pack_loads():
    corpus = load_corpus()
    manifests = load_manifests(corpus=corpus)
    assert "first-responder" in manifests
    manifest = manifests["first-responder"]
    assert manifest["name"] == "First Responder"
    assert manifest["track_emphasis"] == ["improvise"]
    view = edition_corpus(corpus, manifest)
    assert len(view) == 13, len(view)
    crisis_ids = {e["id"] for e in corpus.by_domain("crisis")}
    assert crisis_ids <= {e["id"] for e in view.entries}
    dangling, cycles = check_graph(view)
    assert dangling == [] and cycles == []
    out = format_edition(corpus, manifest)
    assert "FIRST RESPONDER" in out
    assert "professional help FIRST" in out


def test_template_manifest_validates():
    template = json.loads((CURRICULUM_DIR / "edition_packs" / "_template.json").read_text(encoding="utf-8"))
    assert validate_manifest(template) == []
    assert validate_manifest(_manifest()) == []


def test_manifest_schema_rejects_bad_shapes():
    assert validate_manifest(_manifest(id="Bad_ID")) != []
    assert validate_manifest(_manifest(name="")) != []
    assert validate_manifest(_manifest(selector={"domains": ["space"], "tracks": [], "levels": [], "ids": []})) != []
    assert validate_manifest(_manifest(selector={"domains": [], "tracks": ["teleport"], "levels": [], "ids": []})) != []
    assert validate_manifest(_manifest(selector={"domains": [], "tracks": [], "levels": ["expert"], "ids": []})) != []
    assert validate_manifest(_manifest(selector={"domains": [], "tracks": [], "levels": [], "ids": ["nope"]})) != []
    assert validate_manifest(_manifest(selector={"domains": [], "tracks": [], "levels": [], "ids": []})) != []
    assert validate_manifest(_manifest(track_emphasis=["teleport"])) != []
    assert validate_manifest(_manifest(extra_key=1)) != []
    assert validate_manifest(_manifest(selector={"domains": ["general"], "bogus": []})) != []
    assert validate_manifest("not a dict") != []


def _write_pack(tmp: Path, manifest: dict) -> Path:
    (tmp).mkdir(parents=True, exist_ok=True)
    (tmp / f"{manifest['id']}.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp


def test_manifest_pack_entries_validated_against_corpus():
    corpus = load_corpus()
    pack_entry = _good_entry(id="sw-general-950", title="A fine pack-only entry",
                               domain="general", prerequisites=[])
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _write_pack(tmp, _manifest(entries=[pack_entry]))
        manifests = load_manifests(path=tmp, corpus=corpus)
        assert "test-pack" in manifests
        view = edition_corpus(corpus, manifests["test-pack"])
        assert view.get("sw-general-950") is not None


def test_manifest_rejects_pack_entry_with_dangling_prereq():
    corpus = load_corpus()
    pack_entry = _good_entry(
        id="sw-general-951", title="Pack entry with a dangling prereq",
        prerequisites=["sw-nope-999"],
    )
    with tempfile.TemporaryDirectory() as td:
        tmp = _write_pack(Path(td), _manifest(entries=[pack_entry]))
        try:
            load_manifests(path=tmp, corpus=corpus)
        except ValueError as exc:
            assert "dangling" in str(exc)
        else:
            raise AssertionError("expected ValueError for dangling pack prereq")


def test_manifest_rejects_pack_entry_collisions():
    corpus = load_corpus()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # id collision with the corpus
        _write_pack(tmp, _manifest(id="pack-a", entries=[
            _good_entry(id="sw-plumbing-001", title="A totally different title here")]))
        try:
            load_manifests(path=tmp, corpus=corpus)
        except ValueError as exc:
            assert "collides" in str(exc)
        else:
            raise AssertionError("expected ValueError for pack id collision")
        # title collision with the corpus
        real_title = corpus.entries[0]["title"]
        _write_pack(tmp, _manifest(id="pack-b", entries=[
            _good_entry(id="sw-general-952", title=real_title)]))
        try:
            load_manifests(path=tmp, corpus=corpus)
        except ValueError as exc:
            assert "collides" in str(exc)
        else:
            raise AssertionError("expected ValueError for pack title collision")


def test_manifest_file_name_must_match_id():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "wrong-name.json").write_text(json.dumps(_manifest()), encoding="utf-8")
        try:
            load_manifests(path=tmp)
        except ValueError as exc:
            assert "should match the file name" in str(exc)
        else:
            raise AssertionError("expected ValueError for id/file-name mismatch")


# ── planned roadmap ─────────────────────────────────────────────────

def test_planned_titles_parse_unique_and_cover_corpus():
    planned = load_planned_titles()
    assert len(planned) >= 1000, f"roadmap too small: {len(planned)}"
    titles = [normalize_title(t) for _, _, t in planned]
    assert len(set(titles)) == len(titles), "duplicate planned titles"
    for track, _, _ in planned:
        assert track in TRACKS
    corpus = load_corpus()
    planned_set = set(titles)
    missing = [e["title"] for e in corpus.entries if normalize_title(e["title"]) not in planned_set]
    assert missing == [], missing[:5]


def test_roadmap_has_no_unsafe_titles():
    planned = load_planned_titles()
    for _, _, title in planned:
        low = title.lower()
        assert "starting fluid" not in low, title


# ── grow pipeline ───────────────────────────────────────────────────

def _write_seeds(tmp: Path, entries) -> Path:
    p = tmp / "topics.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return p


def test_grow_appends_valid_dedups_and_keeps_invalid():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        corpus_dir = tmp / "corpus"
        good = _good_entry(id="sw-plumbing-901", title="A brand new valid entry")
        dup = _good_entry(id="sw-plumbing-902", title="A brand new valid entry")  # dup title
        bad = {"id": "sw-plumbing-903", "title": "Missing most keys"}
        seeds = _write_seeds(tmp, [good, dup, bad])
        report = grow(seeds_path=seeds, corpus_dir=corpus_dir)
        assert report["valid"] == 2
        assert report["invalid"] == 1
        assert report["duplicates"] == 1
        assert report["appended"] == 1
        assert report["per_domain"] == {"plumbing": 1}
        shard = corpus_dir / "plumbing.jsonl"
        assert shard.is_file()
        assert len(shard.read_text(encoding="utf-8").strip().splitlines()) == 1
        # invalid seed kept for fixing; processed ones consumed
        remaining = seeds.read_text(encoding="utf-8")
        assert "Missing most keys" in remaining
        assert "brand new valid entry" not in remaining


def test_grow_batch_preserves_unprocessed_lines():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        corpus_dir = tmp / "corpus"
        entries = [
            _good_entry(id="sw-plumbing-910", title="Batch entry one"),
            _good_entry(id="sw-plumbing-911", title="Batch entry two"),
            _good_entry(id="sw-plumbing-912", title="Batch entry three"),
        ]
        seeds = _write_seeds(tmp, entries)
        report = grow(seeds_path=seeds, corpus_dir=corpus_dir, batch=1)
        assert report["appended"] == 1
        remaining = [l for l in seeds.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(remaining) == 2, remaining
        assert "Batch entry one" not in seeds.read_text(encoding="utf-8")
        assert "Batch entry two" in seeds.read_text(encoding="utf-8")


def test_grow_dry_run_writes_nothing():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        corpus_dir = tmp / "corpus"
        seeds = _write_seeds(tmp, [_good_entry(id="sw-auto-901", title="Dry run entry")])
        report = grow(seeds_path=seeds, corpus_dir=corpus_dir, dry_run=True)
        assert report["dry_run"] is True
        assert not corpus_dir.exists()
        assert "Dry run entry" in seeds.read_text(encoding="utf-8")


def test_grow_rejects_crisis_without_help_first():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        entry = _good_entry(
            id="sw-crisis-901", title="Crisis missing the law", domain="crisis",
            tracks=["improvise"], prerequisites=[], difficulty=3,
            stop_conditions=["Just be careful."],
        )
        seeds = _write_seeds(tmp, [entry])
        report = grow(seeds_path=seeds, corpus_dir=tmp / "corpus")
        assert report["invalid"] == 1
        assert report["appended"] == 0


def test_write_stubs_skips_built_titles():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        corpus_dir = tmp / "corpus"
        planned = tmp / "planned.txt"
        planned.write_text(
            "improvise | plumbing | A brand new valid entry\n"
            "restore | plumbing | Remove a bathtub spout without a strap wrench\n",
            encoding="utf-8",
        )
        # seed the corpus with the spout title so it counts as built
        (corpus_dir).mkdir()
        (corpus_dir / "plumbing.jsonl").write_text(
            json.dumps(_good_entry(id="sw-plumbing-001",
                                   title="Remove a bathtub spout without a strap wrench"))
            + "\n", encoding="utf-8")
        report = write_stubs(5, planned_path=planned,
                             stubs_path=tmp / "stubs.jsonl", corpus_dir=corpus_dir)
        assert report["stubs_written"] == 1
        stub = json.loads((tmp / "stubs.jsonl").read_text(encoding="utf-8").strip())
        assert stub["stub"] is True
        assert stub["tracks"] == ["improvise"]
        assert validate_entry(stub) != []  # stubs never validate for promotion


# ── runner ──────────────────────────────────────────────────────────

def _run_all():
    fns = sorted(
        (n, f) for n, f in globals().items()
        if n.startswith("test_") and callable(f)
    )
    failed = 0
    for name, fn in fns:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}: {exc}")
        else:
            print(f"ok   {name}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
