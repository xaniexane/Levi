"""Income batch E — automation services (slots 81-92): registry presence,
run() smoke for every generator against tmp fixtures, dry-run safety,
and undo/restore manifests.

All generators are stdlib-only, write only under a tmp levi_home in tests,
and never delete without a manifest.
"""

import json
import os
import re
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from levi.income import engine
from levi.income.engine import REGISTRY, Generator, WorkReport

import levi.income.gen_automation  # noqa: F401  (self-registers slots 81-92)

EXPECTED = {
    81: ("file-sort-bot", 3.0),
    82: ("log-rotator", 2.5),
    83: ("daily-digest-assembler", 3.0),
    84: ("reminder-nudger", 2.0),
    85: ("backup-runner", 4.0),
    86: ("photo-organizer", 3.5),
    87: ("duplicate-finder", 4.0),
    88: ("bulk-renamer", 2.5),
    89: ("folder-watch-reporter", 2.0),
    90: ("task-health-checker", 3.0),
    91: ("archive-packer", 2.5),
    92: ("inbox-sweeper", 3.0),
}


def _ctx(home: Path, target: Path, dry_run: bool = True, **params):
    return {
        "levi_home": home,
        "dry_run": dry_run,
        "params": {"target": str(target), **params},
    }


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------

def test_all_twelve_registered():
    assert REGISTRY.count() >= 12
    for slot, (gid, price) in EXPECTED.items():
        gen = REGISTRY._slots[slot]
        assert gen.id == gid, f"slot {slot}: expected {gid}, got {gen.id}"
        assert gen.kind == "automation-service"
        assert gen.version == "1.0.0"
        assert gen.entry_price_usd == price
        assert 1.0 <= price <= 5.0


def test_ids_unique_and_slots_disjoint():
    ids = [g.id for g in REGISTRY._slots.values()]
    assert len(ids) == len(set(ids))
    assert list(EXPECTED.keys()) == sorted(EXPECTED.keys())


def test_slot_collision_raises():
    with pytest.raises(ValueError):
        engine.register(
            Generator(id="file-sort-bot-2", name="x", kind="automation-service",
                      description="x", run=lambda ctx: WorkReport(generator_id="x")),
            slot=81,
        )
    with pytest.raises(ValueError):
        engine.register(
            Generator(id="file-sort-bot", name="x", kind="automation-service",
                      description="x", run=lambda ctx: WorkReport(generator_id="x")),
            slot=99,
        )


def test_dry_run_writes_nothing(tmp_path):
    target = tmp_path / "mess"
    target.mkdir()
    (target / "note.txt").write_text("hello")
    home = tmp_path / "home"
    for slot, (gid, _) in EXPECTED.items():
        gen = REGISTRY.get(gid)
        rep = gen.run(_ctx(home, target, dry_run=True))
        assert isinstance(rep, WorkReport)
        assert rep.generator_id == gid
        assert rep.quoted_amount_usd is None or 1.0 <= rep.quoted_amount_usd <= 5.0
    assert not (home / ".levi").exists(), "dry run must not write anything"


# --------------------------------------------------------------------------
# 81 file-sort-bot
# --------------------------------------------------------------------------

def test_file_sort_bot(tmp_path):
    target = tmp_path / "mess"
    target.mkdir()
    for name in ("a.jpg", "b.pdf", "c.mp3", "d.zip", "e.py", "f.weird"):
        (target / name).write_text("x")
    home = tmp_path / "home"
    gen = REGISTRY.get("file-sort-bot")
    rep = gen.run(_ctx(home, target, dry_run=False))
    assert rep.produced[0] == "moved:6"
    assert (target / "images" / "a.jpg").exists()
    assert (target / "documents" / "b.pdf").exists()
    assert (target / "misc" / "f.weird").exists()
    manifest = home / ".levi" / "income" / "work" / "file-sort-bot" / "move_manifest.json"
    data = json.loads(manifest.read_text())
    assert len(data["moves"]) == 6
    assert "undo" in data
    # undo restores everything
    for entry in data["moves"]:
        Path(entry["to"]).rename(entry["from"])
    assert sorted(p.name for p in target.iterdir() if p.is_file()) == \
        ["a.jpg", "b.pdf", "c.mp3", "d.zip", "e.py", "f.weird"]


# --------------------------------------------------------------------------
# 82 log-rotator
# --------------------------------------------------------------------------

def test_log_rotator(tmp_path):
    target = tmp_path / "logs"
    target.mkdir()
    big = target / "app.log"
    big.write_bytes(b"x" * (2 * 1024 * 1024))
    old = target / "old.log"
    old.write_bytes(b"stale")
    old_mtime = (datetime.now(timezone.utc) - timedelta(days=60)).timestamp()
    os.utime(old, (old_mtime, old_mtime))
    home = tmp_path / "home"
    gen = REGISTRY.get("log-rotator")
    rep = gen.run(_ctx(home, target, dry_run=False, max_size_mb=1, keep_days=30))
    assert rep.produced[0] == "rotated:2"
    assert big.stat().st_size == 0            # rotated: fresh empty log
    assert not old.exists()                   # archived: original recorded
    archives = list((target / "_rotated").glob("*.log.gz"))
    assert len(archives) == 2
    manifest = home / ".levi" / "income" / "work" / "log-rotator" / "rotation_manifest.json"
    data = json.loads(manifest.read_text())
    assert len(data["actions"]) == 2


# --------------------------------------------------------------------------
# 83 daily-digest-assembler
# --------------------------------------------------------------------------

def test_daily_digest(tmp_path):
    target = tmp_path / "src"
    notes = target / "notes"
    logs = target / "logs"
    notes.mkdir(parents=True)
    logs.mkdir(parents=True)
    (notes / "todo.md").write_text("ship it")
    (logs / "svc.log").write_text("line1\nline2\n")
    home = tmp_path / "home"
    gen = REGISTRY.get("daily-digest-assembler")
    ctx = _ctx(home, target, dry_run=False,
               notes_dir=str(notes), logs_dir=str(logs))
    rep = gen.run(ctx)
    digests = list((home / ".levi" / "income" / "work" / "daily-digest-assembler")
                   .glob("digest-*.md"))
    assert len(digests) == 1
    text = digests[0].read_text()
    assert "todo.md" in text and "line1" in text
    assert rep.quoted_amount_usd == 3.0


# --------------------------------------------------------------------------
# 84 reminder-nudger
# --------------------------------------------------------------------------

def test_reminder_nudger(tmp_path):
    target = tmp_path / "t"
    target.mkdir()
    rfile = target / "reminders.txt"
    past = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    future = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d")
    rfile.write_text(f"{past} | overdue thing\n{today} | today thing\n"
                     f"{future} | later thing\nnot a reminder\n")
    home = tmp_path / "home"
    gen = REGISTRY.get("reminder-nudger")
    rep = gen.run(_ctx(home, target, dry_run=False,
                       reminders_file=str(rfile)))
    assert rep.produced[1] == "overdue:1"
    assert rep.produced[2] == "due:1"
    nudge = next((home / ".levi" / "income" / "work" / "reminder-nudger")
                 .glob("nudge-*.md"))
    text = nudge.read_text()
    assert "overdue thing" in text and "today thing" in text and "later thing" in text


# --------------------------------------------------------------------------
# 85 backup-runner
# --------------------------------------------------------------------------

def test_backup_runner(tmp_path):
    source = tmp_path / "src"
    (source / "sub").mkdir(parents=True)
    (source / "a.txt").write_text("alpha")
    (source / "sub" / "b.bin").write_bytes(b"\x00\x01\x02")
    home = tmp_path / "home"
    dest = tmp_path / "bk"
    gen = REGISTRY.get("backup-runner")
    rep = gen.run(_ctx(home, source, dry_run=False, source=str(source),
                       dest=str(dest)))
    assert rep.produced[1] == "files:2/2"
    assert (dest / "a.txt").read_text() == "alpha"
    assert (dest / "sub" / "b.bin").read_bytes() == b"\x00\x01\x02"
    manifest = next((home / ".levi" / "income" / "work" / "backup-runner")
                    .glob("backup-*.manifest.json"))
    data = json.loads(manifest.read_text())
    assert len(data["files"]) == 2
    assert all(re.fullmatch(r"[0-9a-f]{64}", e["sha256"]) for e in data["files"])


# --------------------------------------------------------------------------
# 86 photo-organizer
# --------------------------------------------------------------------------

def test_photo_organizer(tmp_path):
    target = tmp_path / "cam"
    target.mkdir()
    (target / "IMG_20260314_120000.jpg").write_bytes(b"jpeg")
    (target / "pic.png").write_bytes(b"png")
    (target / "doc.txt").write_text("not a photo")
    home = tmp_path / "home"
    gen = REGISTRY.get("photo-organizer")
    rep = gen.run(_ctx(home, target, dry_run=False))
    assert rep.produced[0] == "moved:2"
    assert (target / "photos" / "2026-03-14" / "IMG_20260314_120000.jpg").exists()
    dated = list((target / "photos").iterdir())
    assert len(dated) == 2  # filename-date folder + mtime folder
    assert (target / "doc.txt").exists()
    manifest = home / ".levi" / "income" / "work" / "photo-organizer" / "photo_manifest.json"
    assert len(json.loads(manifest.read_text())["moves"]) == 2


# --------------------------------------------------------------------------
# 87 duplicate-finder
# --------------------------------------------------------------------------

def test_duplicate_finder(tmp_path):
    target = tmp_path / "dups"
    target.mkdir()
    for name in ("a.txt", "b.txt", "c.txt"):
        (target / name).write_text("same content")
    (target / "unique.txt").write_text("different")
    home = tmp_path / "home"
    gen = REGISTRY.get("duplicate-finder")
    rep = gen.run(_ctx(home, target, dry_run=False))
    assert rep.produced[0] == "groups:1"
    reclaim = int(rep.produced[1].split(":")[1])
    assert reclaim == len("same content") * 2
    report = home / ".levi" / "income" / "work" / "duplicate-finder" / "duplicates.json"
    data = json.loads(report.read_text())
    assert data["reclaimable_bytes"] == reclaim
    # report-only: nothing deleted
    assert len(list(target.iterdir())) == 4


# --------------------------------------------------------------------------
# 88 bulk-renamer
# --------------------------------------------------------------------------

def test_bulk_renamer(tmp_path):
    target = tmp_path / "ren"
    target.mkdir()
    (target / "My Photo 1.jpg").write_text("x")
    (target / "My Photo 2.jpg").write_text("x")
    home = tmp_path / "home"
    gen = REGISTRY.get("bulk-renamer")
    rules = [{"op": "replace", "find": " ", "replace": "_"}, {"op": "lower"}]
    rep = gen.run(_ctx(home, target, dry_run=False, rules=rules))
    assert rep.produced[0] == "renamed:2"
    assert (target / "my_photo_1.jpg").exists()
    assert (target / "my_photo_2.jpg").exists()
    manifest = home / ".levi" / "income" / "work" / "bulk-renamer" / "rename_manifest.json"
    data = json.loads(manifest.read_text())
    assert len(data["renames"]) == 2
    # undo restores original names
    for entry in data["renames"]:
        Path(entry["to"]).rename(entry["from"])
    assert (target / "My Photo 1.jpg").exists()


# --------------------------------------------------------------------------
# 89 folder-watch-reporter
# --------------------------------------------------------------------------

def test_folder_watch_reporter(tmp_path):
    target = tmp_path / "watch"
    target.mkdir()
    (target / "a.txt").write_text("a")
    home = tmp_path / "home"
    gen = REGISTRY.get("folder-watch-reporter")
    first = gen.run(_ctx(home, target, dry_run=False))
    assert first.produced[0] == "added:1"  # baseline
    (target / "b.txt").write_text("b")
    (target / "a.txt").write_text("changed")
    second = gen.run(_ctx(home, target, dry_run=False))
    assert second.produced[0] == "added:1"
    assert second.produced[2] == "modified:1"
    report = home / ".levi" / "income" / "work" / "folder-watch-reporter" / "changes.json"
    data = json.loads(report.read_text())
    assert data["changes"]["added"] == ["b.txt"]
    assert data["changes"]["modified"] == ["a.txt"]
    # dry run never mutates state
    state = home / ".levi" / "income" / "work" / "folder-watch-reporter" / "state.json"
    before = state.read_text()
    gen.run(_ctx(home, target, dry_run=True))
    assert state.read_text() == before


# --------------------------------------------------------------------------
# 90 task-health-checker
# --------------------------------------------------------------------------

def test_task_health_checker(tmp_path):
    target = tmp_path / "out"
    target.mkdir()
    fresh = target / "nightly.json"
    fresh.write_text("{}")
    stale = target / "weekly.json"
    stale.write_text("{}")
    old_mtime = (datetime.now(timezone.utc) - timedelta(hours=50)).timestamp()
    os.utime(stale, (old_mtime, old_mtime))
    home = tmp_path / "home"
    gen = REGISTRY.get("task-health-checker")
    checks = [
        {"name": "nightly", "path": str(fresh), "max_age_hours": 24},
        {"name": "weekly", "path": str(stale), "max_age_hours": 24},
        {"name": "missing", "path": str(target / "nope.json"), "max_age_hours": 24},
    ]
    rep = gen.run(_ctx(home, target, dry_run=False, checks=checks))
    assert rep.produced[0] == "checked:3"
    assert rep.produced[1] == "gaps:2"
    report = home / ".levi" / "income" / "work" / "task-health-checker" / "health.json"
    statuses = {c["name"]: c["status"] for c in json.loads(report.read_text())["checks"]}
    assert statuses == {"nightly": "ok", "weekly": "stale", "missing": "missing"}


# --------------------------------------------------------------------------
# 91 archive-packer
# --------------------------------------------------------------------------

def test_archive_packer(tmp_path):
    target = tmp_path / "aging"
    target.mkdir()
    old_file = target / "report-2024.txt"
    old_file.write_text("ancient")
    old_mtime = (datetime.now(timezone.utc) - timedelta(days=120)).timestamp()
    os.utime(old_file, (old_mtime, old_mtime))
    (target / "fresh.txt").write_text("new")
    home = tmp_path / "home"
    gen = REGISTRY.get("archive-packer")
    rep = gen.run(_ctx(home, target, dry_run=False, age_days=90))
    assert rep.produced[1] == "packed:1"
    assert rep.produced[2] == "removed:1"
    assert not old_file.exists()
    assert (target / "fresh.txt").exists()
    archives = list((target / "_archives").glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0], "r:gz") as tar:
        assert "report-2024.txt" in tar.getnames()
    manifest = next((home / ".levi" / "income" / "work" / "archive-packer")
                    .glob("*.manifest.json"))
    data = json.loads(manifest.read_text())
    assert data["files"][0]["path"] == "report-2024.txt"
    # restore = extract
    import shutil as _sh
    _sh.unpack_archive(str(archives[0]), str(target))
    assert old_file.exists()


# --------------------------------------------------------------------------
# 92 inbox-sweeper
# --------------------------------------------------------------------------

def test_inbox_sweeper(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "m1.txt").write_text("Your INVOICE for this month is attached.")
    (inbox / "m2.eml").write_text("Meeting agenda for the standup tomorrow.")
    (inbox / "m3.txt").write_text("just saying hi")
    home = tmp_path / "home"
    gen = REGISTRY.get("inbox-sweeper")
    rep = gen.run(_ctx(home, inbox, dry_run=False, inbox=str(inbox)))
    assert rep.produced[0] == "triaged:3"
    assert (inbox / "finance" / "m1.txt").exists()
    assert (inbox / "meetings" / "m2.eml").exists()
    assert (inbox / "unsorted" / "m3.txt").exists()
    manifest = home / ".levi" / "income" / "work" / "inbox-sweeper" / "sweep_manifest.json"
    assert len(json.loads(manifest.read_text())["moves"]) == 3


# --------------------------------------------------------------------------
# engine integration: no income ever invented
# --------------------------------------------------------------------------

def test_run_via_engine_records_run_not_income(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    rec = engine.run_generator("duplicate-finder", dry_run=True)
    assert rec["dry_run"] is True
    assert rec["generator_id"] == "duplicate-finder"
    assert rec["slot"] == 87
    assert "quoted_amount_usd" in rec
    with pytest.raises(ValueError):
        engine.record_income("duplicate-finder", 5.0, "sale", basis="claimed")
