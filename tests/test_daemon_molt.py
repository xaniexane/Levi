"""Proof for the molt daemon: generations shed, records never deleted."""

import json
from pathlib import Path

import pytest

from levi.daemon import molt


@pytest.fixture()
def yard(tmp_path):
    root = tmp_path / "yard"
    root.mkdir()
    state = tmp_path / "state"
    stored = tmp_path / "stored"
    return root, state, stored


def _gen(root: Path, name: str, num: int, ext: str = ".md", body: str | None = None):
    path = root / f"{name}.gen-{num}{ext}"
    path.write_text(body if body is not None else f"{name} generation {num}")
    return path


def _tick(root, keep=3, dry_run=False, state=None, stored=None):
    return molt.tick(
        root, keep=keep, dry_run=dry_run, state_dir=state, stored_dir=stored
    )


def test_keeps_newest_and_relocates_older(yard):
    root, state, stored = yard
    for num in range(1, 6):
        _gen(root, "slate", num)
    report = _tick(root, state=state, stored=stored)
    assert report.kept == 3
    assert report.relocated == 2
    assert report.skipped == 0
    remaining = sorted(p.name for p in root.iterdir())
    assert remaining == ["slate.gen-3.md", "slate.gen-4.md", "slate.gen-5.md"]


def test_relocation_preserves_bytes_and_provenance(yard):
    root, state, stored = yard
    old = _gen(root, "slate", 1, body="the original words")
    _gen(root, "slate", 2)
    report = _tick(root, keep=1, state=state, stored=stored)
    assert report.relocated == 1
    assert report.kept == 1
    moved = list(stored.rglob("slate.gen-1.md"))
    assert len(moved) == 1
    assert moved[0].read_text() == "the original words"
    assert not old.exists()  # relocated, and the copy is byte-identical
    assert "molt" in str(moved[0])  # under stored/molt/<date>/


def test_numeric_ordering_not_lexicographic(yard):
    root, state, stored = yard
    for num in (1, 2, 9, 10, 11):
        _gen(root, "digest", num)
    report = _tick(root, keep=2, state=state, stored=stored)
    assert report.kept == 2
    remaining = sorted(p.name for p in root.iterdir())
    assert remaining == ["digest.gen-10.md", "digest.gen-11.md"]


def test_non_generation_files_are_untouched(yard):
    root, state, stored = yard
    plain = root / "notes.md"
    plain.write_text("not a generation")
    _gen(root, "slate", 1)
    report = _tick(root, keep=1, state=state, stored=stored)
    assert report.relocated == 0
    assert plain.exists()


def test_dry_run_moves_nothing(yard):
    root, state, stored = yard
    for num in range(1, 5):
        _gen(root, "slate", num)
    report = _tick(root, keep=1, dry_run=True, state=state, stored=stored)
    assert report.relocated == 3
    assert len(list(root.iterdir())) == 4
    assert not stored.exists() or not any(stored.rglob("*"))


def test_every_action_is_receipted(yard):
    root, state, stored = yard
    for num in range(1, 4):
        _gen(root, "slate", num)
    _tick(root, keep=2, state=state, stored=stored)
    receipts = (state / molt.RECEIPTS_NAME).read_text().strip().splitlines()
    actions = [json.loads(line)["action"] for line in receipts]
    assert sorted(actions) == ["kept", "kept", "relocated"]
    for line in receipts:
        entry = json.loads(line)
        assert entry["at"] and entry["family"] == "slate.md"
        assert entry["generation"] >= 1


def test_destination_collision_skips_never_overwrites(yard):
    root, state, stored = yard
    _gen(root, "slate", 1, body="root copy")
    _gen(root, "slate", 2)  # newest stays; gen-1 is the one being shed
    dest_dir = stored / "molt" / molt._utcnow().strftime("%Y-%m-%d")
    dest_dir.mkdir(parents=True)
    (dest_dir / "slate.gen-1.md").write_text("stored copy")
    report = _tick(root, keep=1, state=state, stored=stored)
    assert report.skipped == 1
    assert report.relocated == 0
    assert (root / "slate.gen-1.md").read_text() == "root copy"
    assert (dest_dir / "slate.gen-1.md").read_text() == "stored copy"


def test_deny_closed_bad_root_and_keep(yard):
    root, state, stored = yard
    with pytest.raises(molt.MoltError):
        molt.tick(root / "missing", keep=2, state_dir=state, stored_dir=stored)
    with pytest.raises(molt.MoltError):
        molt.tick(root, keep=0, state_dir=state, stored_dir=stored)


def test_never_deletes_even_module_level():
    source = Path(molt.__file__).read_text()
    for forbidden in ("os.unlink(", "os.remove(", "shutil.rmtree("):
        assert forbidden not in source.replace("os.unlink(tmp)", ""), (
            f"molt must never call {forbidden}"
        )
