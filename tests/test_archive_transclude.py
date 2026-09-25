"""Hermetic tests for the Xanadu revival: transclusion + backlinks.

No network, no user HOME writes (ArchiveStore takes an explicit home),
synthetic records only.
"""

from levi.archive.record import ArchiveRecord
from levi.archive.store import ArchiveStore
from levi.archive.transclude import (
    build_backlinks,
    cited_by,
    find_transclusions,
    render_record,
)


def _rec(rid, summary="s", mechanism="m", **kw):
    fields = dict(
        id=rid,
        title="Title " + rid,
        era="test",
        kind="software",
        summary=summary,
        mechanism=mechanism,
        decline="d",
        revival_recipe="r",
        levi_application="a",
        rating="useful-pattern",
        status="dead",
    )
    fields.update(kw)
    return ArchiveRecord(**fields)


def _store(tmp_path, records):
    store = ArchiveStore(home=tmp_path)
    for rec in records:
        store.add(rec)
    return store


# -- marker scanning ------------------------------------------------------


def test_find_transclusions_order_and_dedup():
    text = (
        "see {{transclude:arch-b}} and {{ transclude : arch-a }}, "
        "then {{transclude:arch-b}} again"
    )
    assert find_transclusions(text) == ["arch-b", "arch-a"]


def test_find_transclusions_none():
    assert find_transclusions("no markers here {{not-a-marker}}") == []


# -- rendering ------------------------------------------------------------


def test_render_resolves_marker_with_origin(tmp_path):
    store = _store(
        tmp_path,
        [
            _rec("arch-tgt", summary="the quoted truth"),
            _rec("arch-src", summary="before {{transclude:arch-tgt}} after"),
        ],
    )
    rendered, transcluded = render_record(store.get("arch-src"), store)
    assert "> [transcluded from arch-tgt \u2014 Title arch-tgt]" in rendered
    assert "> the quoted truth" in rendered
    assert transcluded == ["arch-tgt"]


def test_render_nested_transclusion_resolves(tmp_path):
    store = _store(
        tmp_path,
        [
            _rec("arch-deep", summary="deep truth"),
            _rec("arch-mid", summary="mid says {{transclude:arch-deep}}"),
            _rec("arch-top", summary="top says {{transclude:arch-mid}}"),
        ],
    )
    rendered, transcluded = render_record(store.get("arch-top"), store)
    assert "deep truth" in rendered
    assert set(transcluded) == {"arch-mid", "arch-deep"}


def test_render_unknown_id_left_honestly(tmp_path):
    store = _store(tmp_path, [_rec("arch-a", summary="x {{transclude:arch-nope}} y")])
    rendered, transcluded = render_record(store.get("arch-a"), store)
    assert "{{transclude:arch-nope}}" in rendered
    assert "unknown record" in rendered
    assert transcluded == []


def test_render_circular_transclusion_stops(tmp_path):
    store = _store(
        tmp_path,
        [
            _rec("arch-a", summary="a cites {{transclude:arch-b}}"),
            _rec("arch-b", summary="b cites {{transclude:arch-a}}"),
        ],
    )
    rendered, _ = render_record(store.get("arch-a"), store)
    assert "circular transclusion" in rendered


def test_render_self_citation_stops(tmp_path):
    store = _store(tmp_path, [_rec("arch-a", summary="me {{transclude:arch-a}}")])
    rendered, _ = render_record(store.get("arch-a"), store)
    assert "circular transclusion" in rendered


# -- backlinks ------------------------------------------------------------


def test_backlinks_reverse_index(tmp_path):
    store = _store(
        tmp_path,
        [
            _rec("arch-a", summary="{{transclude:arch-c}}"),
            _rec("arch-b", mechanism="also {{transclude:arch-c}}"),
            _rec("arch-c", summary="cited"),
            _rec("arch-d", summary="uncited"),
        ],
    )
    assert cited_by(store, "arch-c") == ["arch-a", "arch-b"]
    assert cited_by(store, "arch-d") == []
    assert cited_by(store, "arch-missing") == []


def test_backlinks_ignore_self_citation(tmp_path):
    store = _store(tmp_path, [_rec("arch-a", summary="{{transclude:arch-a}}")])
    assert build_backlinks(store) == {}
