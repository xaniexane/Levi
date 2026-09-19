"""Tests for levi.exodus — the Exit Button."""

import os
import zipfile

import pytest

from levi.exodus import (
    HOSTILITY_CATALOG,
    Dependency,
    audit_export,
    build_plan,
    hostility_by_platform,
    lock_in_score,
    plan_to_markdown,
)
from levi.exodus.audit import audit_to_text


def test_catalog_has_four_researched_entries():
    assert len(HOSTILITY_CATALOG) == 4
    patterns = {e.pattern for e in HOSTILITY_CATALOG}
    assert patterns == {"api-enclosure", "acquired-kill", "deletion-refusal"}
    for e in HOSTILITY_CATALOG:
        assert e.record_id.startswith("arch-exit-")
        assert e.enclosure_signals  # every entry teaches detection


def test_hostility_lookup_case_insensitive():
    assert hostility_by_platform("discord").pattern == "deletion-refusal"
    assert hostility_by_platform("REDDIT").year == 2023
    assert hostility_by_platform("nobody") is None


def test_lock_in_score_trapped_is_five():
    dep = Dependency(name="everything", platform="Discord", kind="community",
                     runway_days=None, local_substitute="")
    assert lock_in_score(dep) == 5


def test_lock_in_score_loose_is_one():
    dep = Dependency(name="login", platform="X (Twitter)", kind="login",
                     runway_days=400, local_substitute="local store")
    assert lock_in_score(dep) == 1


def test_plan_orders_archive_before_delete():
    deps = [
        Dependency(name="posts", platform="Reddit", kind="data",
                   runway_days=None, local_substitute="local index"),
        Dependency(name="community", platform="Reddit", kind="community",
                   runway_days=None, local_substitute="levi communities"),
    ]
    plan = build_plan("Reddit", deps)
    phases = [s["phase"] for s in plan.steps]
    assert phases[0] == "1-archive"
    assert phases[-1] == "4-delete"
    assert "3-community" in phases


def test_plan_flags_short_runway():
    deps = [Dependency(name="bot", platform="Reddit", kind="api",
                       runway_days=30, local_substitute="local cron")]
    plan = build_plan("Reddit", deps)
    assert any("30 days" in w and "Parse standard" in w for w in plan.warnings)


def test_plan_warns_unknown_platform():
    plan = build_plan("Some New App", [])
    assert any("not in the hostility catalog" in w for w in plan.warnings)


def test_plan_renders_markdown_checklist():
    deps = [Dependency(name="posts", platform="Discord", kind="data",
                       runway_days=None, local_substitute="local index")]
    md = plan_to_markdown(build_plan("Discord", deps))
    assert md.startswith("# Exit plan: Discord")
    assert "- [ ]" in md
    assert "4-delete" in md


def _make_theater_zip(tmp_path):
    zpath = str(tmp_path / "takeout.zip")
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("index.html", "<html>your data</html>")
        zf.writestr("messages.html", "<html>hi</html>")
    return zpath


def test_audit_flags_export_theater(tmp_path):
    report = audit_export(_make_theater_zip(tmp_path))
    assert report["files"] == 2
    assert report["machine_readable_files"] == 0
    assert any("export-theater" in f for f in report["red_flags"])
    assert any("no media" in f for f in report["red_flags"])


def test_audit_honest_export_no_false_alarms(tmp_path):
    d = tmp_path / "takeout"
    d.mkdir()
    (d / "posts.json").write_text('[{"id": 1}]')
    (d / "photo.jpg").write_bytes(b"\xff\xd8")
    report = audit_export(str(d))
    assert report["red_flags"] == []
    assert "no red flags" in audit_to_text(report)


def test_audit_rejects_missing_path():
    report = audit_export("/no/such/path")
    assert report["red_flags"]
