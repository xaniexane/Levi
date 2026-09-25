"""Tests for levi.daemon.watchdog — the comms watchdog.

Law → guard → prove for each invariant in watchdog.py's header.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from levi.daemon import watchdog as wd_mod
from levi.daemon.herald import HeraldQueue


def _run(tmp_path, **kwargs):
    home = tmp_path / "home"
    queue = HeraldQueue(tmp_path / "herald" / "queue.jsonl")
    return wd_mod.run_watchdog(home=home, queue=queue, force=True, **kwargs), queue


def _item(item_id="a", title="hello", source="test"):
    return wd_mod.CommsItem(source=source, item_id=item_id, title=title)


# ---------------------------------------------------------------------------
# invariant 1: bark exactly once
# ---------------------------------------------------------------------------


def test_barks_new_item_exactly_once(tmp_path):
    sources = {"test": lambda: [_item()]}

    r1, queue = _run(tmp_path, sources=sources)
    assert r1.new_items == 1
    assert r1.barked == 1
    assert not r1.silent
    pending = queue.pending()
    assert len(pending) == 1
    assert pending[0].source == "watchdog"
    assert pending[0].level == "warn"

    # Second tick: the seen-id log stops the re-bark.
    r2, queue2 = _run(tmp_path, sources=sources)
    assert r2.barked == 0
    assert r2.new_items == 0
    assert r2.silent
    assert len(queue2.pending()) == 1


def test_seen_item_not_recounted_as_new(tmp_path):
    sources = {"test": lambda: [_item("a"), _item("b")]}
    r1, _ = _run(tmp_path, sources=sources)
    assert r1.new_items == 2

    # Only a genuinely new item counts on the next tick.
    sources2 = {"test": lambda: [_item("a"), _item("b"), _item("c")]}
    r2, _ = _run(tmp_path, sources=sources2)
    assert r2.new_items == 1
    assert r2.barked == 1


# ---------------------------------------------------------------------------
# invariant 2: never crash on a failing source
# ---------------------------------------------------------------------------


def test_failing_source_is_honest_not_fatal(tmp_path):
    def boom():
        raise RuntimeError("source exploded")

    sources = {"bad": boom, "good": lambda: [_item()]}
    result, queue = _run(tmp_path, sources=sources)
    assert any("bad" in n and "RuntimeError" in n for n in result.notes), (
        "failing source must produce one honest note: " + repr(result.notes)
    )
    assert result.barked == 1  # the good source still barked
    assert len(queue.pending()) == 1


def test_non_list_source_is_honest_not_fatal(tmp_path):
    sources = {"weird": lambda: "not a list"}
    result, _ = _run(tmp_path, sources=sources)
    assert any("non-list" in n for n in result.notes)


# ---------------------------------------------------------------------------
# invariant 3: NOT cyber — no security imports, ever
# ---------------------------------------------------------------------------

_FORBIDDEN = ("sentinel", "watchman", "cyberpulse", "cyber")


def test_no_cyber_imports_in_module_source():
    src = Path(wd_mod.__file__).read_text(encoding="utf-8")
    for lineno, line in enumerate(src.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            for name in _FORBIDDEN:
                assert name not in stripped, (
                    f"watchdog.py line {lineno} imports a cyber module: {line!r}"
                )


def test_no_cyber_modules_loaded_by_run(tmp_path, monkeypatch):
    import sys

    # Run the REAL default readers against empty tmp stores; the only new
    # modules the watchdog may pull in are comms stores — never cyber ones.
    monkeypatch.setenv("LEVI_OATH_HOME", str(tmp_path / "oath"))
    monkeypatch.setenv("LEVI_SOXI_RETURN_DIR", str(tmp_path / "soxi"))
    monkeypatch.setenv("LEVI_INBOX_DIR", str(tmp_path / "inbox"))
    before = set(sys.modules)
    queue = HeraldQueue(tmp_path / "herald" / "queue.jsonl")
    wd_mod.run_watchdog(home=tmp_path / "home", queue=queue, force=True)
    new = set(sys.modules) - before
    cyber = [m for m in new if "sentinel" in m or "cyberpulse" in m]
    assert not cyber, f"cyber modules pulled in by the watchdog run: {cyber}"


# ---------------------------------------------------------------------------
# invariant 4: metadata only — never message bodies
# ---------------------------------------------------------------------------


def test_oath_reader_extracts_headers_never_bodies(tmp_path, monkeypatch):
    from levi.oath import inbox as oath_inbox

    maildir = tmp_path / "maildir"
    (maildir / "new").mkdir(parents=True)
    raw = (
        b"From: alice@example.com\r\n"
        b"Subject: Q3 numbers\r\n"
        b"\r\n"
        b"SECRET BODY TEXT that must never appear in a bark\r\n"
    )
    (maildir / "new" / "msg1").write_bytes(raw)
    monkeypatch.setattr(oath_inbox, "MAILDIR", lambda: maildir)

    items = wd_mod._read_oath_unseen()
    assert len(items) == 1
    item = items[0]
    assert "alice@example.com" in item.detail
    assert "Q3 numbers" in item.title
    assert "SECRET BODY TEXT" not in item.title
    assert "SECRET BODY TEXT" not in item.detail
    # read-only: the message stays unseen in new/
    assert (maildir / "new" / "msg1").exists()


def test_oath_reader_skips_seen_mail(tmp_path, monkeypatch):
    from levi.oath import inbox as oath_inbox

    maildir = tmp_path / "maildir"
    (maildir / "new").mkdir(parents=True)
    (maildir / "cur").mkdir(parents=True)
    (maildir / "cur" / "old").write_bytes(b"Subject: seen\r\n\r\nbody")
    monkeypatch.setattr(oath_inbox, "MAILDIR", lambda: maildir)

    assert wd_mod._read_oath_unseen() == []


# ---------------------------------------------------------------------------
# invariant 5: silent idle
# ---------------------------------------------------------------------------


def test_silent_when_nothing_new(tmp_path):
    result, _ = _run(tmp_path, sources={"empty": lambda: []})
    assert result.silent
    assert result.new_items == 0
    assert result.reason == "nothing new"


# ---------------------------------------------------------------------------
# interval discipline
# ---------------------------------------------------------------------------


def test_interval_validation_rejects_bad_values():
    with pytest.raises(ValueError):
        wd_mod._resolve_interval(0)
    with pytest.raises(ValueError):
        wd_mod._resolve_interval(-3)
    with pytest.raises(ValueError):
        wd_mod._resolve_interval(2.5)
    with pytest.raises(ValueError):
        wd_mod._resolve_interval(False)
    assert wd_mod._resolve_interval(15) == 15


def test_interval_gate_skips_fresh_tick(tmp_path):
    home = tmp_path / "home"
    queue = HeraldQueue(tmp_path / "herald" / "queue.jsonl")
    sources = {"test": lambda: []}
    r1 = wd_mod.run_watchdog(home=home, queue=queue, sources=sources, force=False)
    assert r1.reason != "interval not elapsed"
    r2 = wd_mod.run_watchdog(home=home, queue=queue, sources=sources, force=False)
    assert r2.silent and r2.reason == "interval not elapsed"


# ---------------------------------------------------------------------------
# real source readers stay honest when stores are absent
# ---------------------------------------------------------------------------


def test_default_sources_absent_means_empty_not_crash(tmp_path):
    # Point HOME away so the real stores don't exist; readers must
    # degrade to empty, never raise.
    import os

    old = os.environ.get("HOME")
    os.environ["HOME"] = str(tmp_path / "nohome")
    try:
        for name, reader in wd_mod.DEFAULT_SOURCES.items():
            try:
                items = reader()
            except Exception as exc:  # noqa: BLE001
                pytest.fail(f"source {name} raised: {exc!r}")
            assert isinstance(items, list), name
    finally:
        if old is None:
            del os.environ["HOME"]
        else:
            os.environ["HOME"] = old


# ---------------------------------------------------------------------------
# supervisor registration
# ---------------------------------------------------------------------------


def test_registered_in_supervisor_catalog():
    from levi.daemon.supervisor import Supervisor

    names = [e["name"] for e in Supervisor.SERVICE_CATALOG]
    assert "watchdog" in names
    entry = next(e for e in Supervisor.SERVICE_CATALOG if e["name"] == "watchdog")
    assert entry["module"] == "levi.daemon.watchdog"
    assert callable(entry["_check_fn"])


def test_supervisor_health_check_never_raises(tmp_path):
    from levi.daemon.supervisor import Supervisor

    sup = Supervisor(home=tmp_path / "home")
    st = sup.service_status("watchdog")
    assert isinstance(st["ok"], bool) and isinstance(st["detail"], str)
    assert st["ok"] is True


def test_watchdog_check_function_reports(tmp_path):
    ok, detail = wd_mod.check(home=tmp_path / "home")
    assert ok is True
    assert isinstance(detail, str)
