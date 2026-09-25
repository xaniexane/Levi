"""Tests for the Day-dream imagination loop (levi.dream.imagine / glyphs /
imagery_corpus).

Invariant proofs (Chauncey's law-guard-prove rule): each test below is
named for the invariant it proves. Randomized property tests use fixed
seeds so they are reproducible.
"""

import csv
import json
import random
import string

import pytest

from levi.dream import glyphs
from levi.dream.imagine import imagine_vivid, rate_imagination, render_text_of
from levi.dream.imagery_corpus import (
    ascii_compress,
    ascii_decompress,
    index_coverage_ok,
    retrieve,
    store_upvoted,
)

ITEMS = [
    "a brass key that opens yesterday",
    "the sound of rain on a tin roof",
    "a lighthouse keeper's lunchbox",
    "seven small birds arguing politely",
]


@pytest.fixture()
def hermetic(tmp_path, monkeypatch):
    """Growth writes go to tmp (LEVI_GROWTH_DIR); corpus goes to tmp."""
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(tmp_path / "growth"))
    return tmp_path / "corpus"


# ---------------------------------------------------------------------------
# imagine purity
# ---------------------------------------------------------------------------


def test_imagine_deterministic_same_seed_same_record():
    a = imagine_vivid("a brass key that opens yesterday", seed="s1")
    b = imagine_vivid("a brass key that opens yesterday", seed="s1")
    assert a == b
    assert a["render_text"] == b["render_text"]


def test_imagine_different_seeds_differ():
    a = imagine_vivid("a brass key that opens yesterday", seed="s1")
    b = imagine_vivid("a brass key that opens yesterday", seed="s2")
    assert a["turn_ref"] != b["turn_ref"]
    assert a["ascii_render"] != b["ascii_render"]


def test_imagine_rejects_empty_item():
    with pytest.raises(ValueError):
        imagine_vivid("   ")


def test_imagine_record_shape():
    rec = imagine_vivid(ITEMS[0], seed="shape")
    assert rec["turn_ref"].startswith("imagine-")
    assert isinstance(rec["vivid"]["lines"], list) and rec["vivid"]["lines"]
    rows = rec["ascii_render"].splitlines()
    assert len(rows) == 12 and all(len(r) == 28 for r in rows)
    assert rec["keywords"]  # non-empty index material
    assert "ITEM: %s" % ITEMS[0] in rec["render_text"]


# ---------------------------------------------------------------------------
# glyph tokenizer invariants
# ---------------------------------------------------------------------------


def test_codebook_deterministic():
    a = glyphs.make_codebook()
    b = glyphs.make_codebook()
    assert a == b
    assert a["version"] == glyphs.CODEBOOK_VERSION


def test_glyph_round_trip_property():
    rng = random.Random(20260922)
    alphabet = string.ascii_letters + string.digits + " ~!@#{}[]()_.,\n\t"
    for _ in range(300):
        s = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 120)))
        assert glyphs.decode(glyphs.encode(s)) == s


def test_glyph_adversarial_patterns():
    # tildes, code-like markers, unicode, empty
    cases = [
        "",
        "~",
        "~~",
        "~~~",
        "~aa~",  # looks exactly like an encoded token
        "the ~ab~ quick ~~ brown",
        "vivid ~zz~ dreams",
        "UPPER lower MiXeD",
        "héllo wörld ☾ glyphs",
        "a" * 500,
        "~".join(["the"] * 20),
    ]
    for s in cases:
        assert glyphs.decode(glyphs.encode(s)) == s, repr(s)


def test_glyph_unknown_words_pass_through():
    s = "xylophone zephyr quixotic"
    assert glyphs.decode(glyphs.encode(s)) == s


def test_codebook_written_beside_corpus(hermetic):
    rec = imagine_vivid(ITEMS[0], seed="cb")
    store_upvoted(rec, "fb-test", str(hermetic))
    cb_path = hermetic / "codebook.json"
    assert cb_path.exists()
    payload = json.loads(cb_path.read_text(encoding="utf-8"))
    assert payload["current"] == glyphs.CODEBOOK_VERSION
    assert glyphs.CODEBOOK_VERSION in payload["versions"]


# ---------------------------------------------------------------------------
# ascii compression + storage invariants
# ---------------------------------------------------------------------------


def test_ascii_round_trip_property():
    for item in ITEMS:
        rec = imagine_vivid(item, seed="rt")
        blob = ascii_compress(rec["render_text"])
        # spreadsheet-safe: pure ASCII, no whitespace surprises
        blob.encode("ascii")
        assert "\n" not in blob and "," not in blob
        assert ascii_decompress(blob) == rec["render_text"]


def test_store_upvoted_self_verifies_and_links_feedback(hermetic):
    rec = imagine_vivid(ITEMS[0], seed="store")
    rid = store_upvoted(rec, "fb-abc123", str(hermetic))
    assert rid.startswith("img-")
    rows = (hermetic / "records.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    stored = json.loads(rows[0])
    assert stored["feedback_ref"] == "fb-abc123"
    assert stored["organ"] == "nanobit"
    assert stored["turn_ref"] == rec["turn_ref"]
    # decode the stored blob with the stored codebook version -> identical
    cb = glyphs.load_codebook(str(hermetic), stored["codebook_version"])
    assert ascii_decompress(stored["ascii_blob"], cb) == rec["render_text"]


def test_store_upvoted_idempotent(hermetic):
    rec = imagine_vivid(ITEMS[0], seed="idem")
    r1 = store_upvoted(rec, "fb-1", str(hermetic))
    r2 = store_upvoted(rec, "fb-1", str(hermetic))
    assert r1 == r2
    rows = (hermetic / "records.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1  # no duplicate


def test_store_refuses_without_feedback_link(hermetic):
    rec = imagine_vivid(ITEMS[0], seed="nolink")
    with pytest.raises(ValueError):
        store_upvoted(rec, "   ", str(hermetic))


def test_index_always_covers_every_record(hermetic):
    for i, item in enumerate(ITEMS):
        rec = imagine_vivid(item, seed="cov-%d" % i)
        store_upvoted(rec, "fb-%d" % i, str(hermetic))
    report = index_coverage_ok(str(hermetic))
    assert report["ok"], report["missing"]
    assert report["records"] == len(ITEMS)
    # every keyword of every record retrieves that record
    index = json.loads((hermetic / "index.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (hermetic / "records.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    for rec in rows:
        for kw in rec["keywords"]:
            assert rec["id"] in index["tokens"][kw]


def test_csv_spreadsheet_export_matches_jsonl(hermetic):
    rec = imagine_vivid(ITEMS[1], seed="csv")
    rid = store_upvoted(rec, "fb-csv", str(hermetic))
    csv_path = hermetic / "corpus.csv"
    assert csv_path.exists()
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["id"] == rid
    assert rows[0]["item"] == ITEMS[1]
    assert rows[0]["organ"] == "nanobit"
    rows[0]["ascii_blob"].encode("ascii")  # spreadsheet-safe


# ---------------------------------------------------------------------------
# retrieval invariant: offline, ranked, transparent decode
# ---------------------------------------------------------------------------


def test_retrieve_offline_ranked_and_decoded(hermetic):
    refs = {}
    for i, item in enumerate(ITEMS):
        rec = imagine_vivid(item, seed="ret-%d" % i)
        rid = store_upvoted(rec, "fb-%d" % i, str(hermetic))
        refs[item] = (rid, rec["render_text"])
    hits = retrieve("brass key", str(hermetic))
    assert hits
    assert hits[0]["item"] == "a brass key that opens yesterday"
    assert hits[0]["text"] == refs["a brass key that opens yesterday"][1]
    # ranked: exact matches first; unrelated query finds nothing
    assert retrieve("xylophone-not-in-corpus", str(hermetic)) == []


def test_retrieve_limit_and_empty_corpus(hermetic):
    assert retrieve("anything", str(hermetic)) == []
    for i, item in enumerate(ITEMS):
        store_upvoted(imagine_vivid(item, seed="lim-%d" % i), "fb-%d" % i, str(hermetic))
    hits = retrieve("the", str(hermetic), limit=2)
    assert len(hits) <= 2


# ---------------------------------------------------------------------------
# thumbs loop invariant: down never enters the corpus
# ---------------------------------------------------------------------------


def test_thumbs_down_never_enters_corpus(hermetic):
    rec = imagine_vivid(ITEMS[0], seed="down")
    out = rate_imagination(
        rec["turn_ref"], "down", render=rec, corpus_dir=str(hermetic)
    )
    assert out["signal"] == "down"
    assert out["corpus_record_id"] is None
    assert not (hermetic / "records.jsonl").exists()
    # ...but the growth loop DID learn (feedback record consolidated)
    assert out["feedback_id"]


def test_thumbs_up_stores_with_feedback_link(hermetic):
    rec = imagine_vivid(ITEMS[2], seed="up")
    out = rate_imagination(
        rec["turn_ref"], "up", render=rec, corpus_dir=str(hermetic)
    )
    assert out["signal"] == "up"
    assert out["corpus_record_id"]
    stored = json.loads(
        (hermetic / "records.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert stored["feedback_ref"] == out["feedback_id"]
    assert stored["turn_ref"] == rec["turn_ref"]


def test_thumbs_up_refuses_without_render(hermetic):
    rec = imagine_vivid(ITEMS[0], seed="norender")
    with pytest.raises(ValueError):
        rate_imagination(rec["turn_ref"], "up", corpus_dir=str(hermetic))


def test_thumbs_up_refuses_without_corpus_dir(hermetic):
    rec = imagine_vivid(ITEMS[0], seed="nodir")
    with pytest.raises(ValueError):
        rate_imagination(rec["turn_ref"], "up", render=rec)


def test_rate_rejects_bad_signal(hermetic):
    with pytest.raises(ValueError):
        rate_imagination("imagine-x", "sideways", corpus_dir=str(hermetic))
