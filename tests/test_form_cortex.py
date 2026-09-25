"""cortex form tests: the how-to library.

Proving bar: intake is fail-closed (untitled/unreadable docs are
quarantined, never indexed), documents are data (never executed),
search is honest text matching.
"""

import pytest

from levi.cortex import FORM_NAME, CortexLibrary


@pytest.fixture()
def docs_dir(tmp_path):
    (tmp_path / "deploy.md").write_text(
        "# Deploying a service\n\n<!-- tags: ops, deploy -->\n\nSteps to deploy.\n"
    )
    (tmp_path / "backup.md").write_text(
        "# Backups\n\nTags: ops, safety\n\nHow to back up.\n"
    )
    (tmp_path / "untitled.md").write_text("no heading here, just text\n")
    (tmp_path / "notmd.txt").write_text("# ignored\n")
    return tmp_path


def test_index_quarantines_untitled_and_ignores_non_md(docs_dir):
    lib = CortexLibrary(docs_dir)
    r = lib.index()
    assert r["form"] == FORM_NAME
    assert r["indexed"] == 2
    assert r["quarantined"] == 1
    q = lib.quarantine()
    assert q[0].id == "untitled"
    assert "title" in q[0].reason


def test_search_is_honest_text_match(docs_dir):
    lib = CortexLibrary(docs_dir)
    lib.index()
    hits = lib.search("deploy")
    assert [h.id for h in hits] == ["deploy.md".replace(".md", "")]
    assert lib.search("ops") and len(lib.search("ops")) == 2
    assert lib.search("zzz-no-such-thing") == []
    assert lib.search("") == []
    assert lib.search(42) == []


def test_get_fail_closed(docs_dir):
    lib = CortexLibrary(docs_dir)
    lib.index()
    h = lib.get("deploy")
    assert h.title == "Deploying a service"
    assert "ops" in h.tags
    with pytest.raises(KeyError):
        lib.get("nope")
    with pytest.raises(KeyError):
        lib.get(None)


def test_constructor_fail_closed():
    with pytest.raises(ValueError):
        CortexLibrary(None)
    with pytest.raises(ValueError):
        CortexLibrary("/does/not/exist")


def test_status_honest_limit(docs_dir):
    lib = CortexLibrary(docs_dir)
    lib.index()
    s = lib.status()
    assert s["indexed"] == 2
    assert "never executes" in s["honest_limit"]
