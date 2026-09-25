"""LEVI course-PLATFORM tests: query API, teams, learning loop, CLI, skills.

The platform (core/levi/sidewinder/platform/) is the infrastructure that
delivers the curriculum: a clean query API consumed by LEVI/agents, team
scoping, and the team learning loop. Tests cover:

- CoursePlatform: search/get/manual/progression/learning path with
  edition and team scoping;
- editions listed + filtered through the query path;
- TeamRegistry: declared teams, validation, register/save roundtrip;
- team views: edition union narrowed to tracks, closure intact;
- learning loop: harvest -> review (dry-run) -> promote (validated only,
  provenance stamped, no unreviewed writes);
- CLI: levi sidewinder + levi course, in-process and via subprocess;
- skills registered in the shared SkillRegistry (wave-agent inheritance).

Run:  python3 tests/test_course_platform.py     (has a real __main__ runner)
      python3 -m pytest tests/test_course_platform.py -q
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.sidewinder.curriculum.corpus import load_corpus  # noqa: E402
from levi.sidewinder.curriculum.editions import edition_ids  # noqa: E402
from levi.sidewinder.platform import loop as loop_mod  # noqa: E402
from levi.sidewinder.platform.api import CoursePlatform  # noqa: E402
from levi.sidewinder.platform.cli import cmd_course, cmd_sidewinder  # noqa: E402
from levi.sidewinder.platform.teams import (  # noqa: E402
    Team,
    TeamRegistry,
    team_entry_ids,
    validate_team,
)
from levi.sidewinder.skills import SIDEWINDER_SKILLS  # noqa: E402
from levi.skill.registry import SkillRegistry  # noqa: E402

MODULE_DIR = ROOT / "core" / "levi" / "sidewinder"
PLATFORM_DIR = MODULE_DIR / "platform"


def _api() -> CoursePlatform:
    return CoursePlatform()


# ── query API ───────────────────────────────────────────────────────

def test_api_search_get_manual():
    api = _api()
    hits = api.search("tub spout")
    assert hits and hits[0]["id"] == "sw-plumbing-001"
    assert api.get("sw-plumbing-001")["title"]
    assert api.get("sw-nope-999") is None
    entries = api.manual(track="improvise")
    assert entries and all("improvise" in e["tracks"] for e in entries)


def test_api_progression_and_learning_path():
    api = _api()
    prog = api.progression("improvise")
    assert len(prog) == api.track_counts()["improvise"] >= 1
    path = api.learning_path("sw-plumbing-001")
    ids = [e["id"] for e in path]
    assert ids[-1] == "sw-plumbing-001"
    assert "sw-foundations-007" in ids[:-1]


def test_api_edition_scoping():
    api = _api()
    assert api.edition_ids() == ["first-responder"]
    manifest = api.edition_manifest("first-responder")
    assert manifest["name"] == "First Responder"
    hits = api.search("shelf", edition="first-responder")
    view_ids = {x["id"] for x in api.edition_view("first-responder").entries}
    assert all(e["id"] in view_ids for e in hits)
    # edition view is smaller than the whole corpus
    assert len(api.edition_view("first-responder").entries) < len(load_corpus())
    try:
        api.edition_view("nope")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for unknown edition")
    try:
        api.edition_manifest("nope")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for unknown edition manifest")


def test_api_team_scoping():
    api = _api()
    crew = api.team_view("field-crew")
    corpus = load_corpus()
    manifests = {m["id"]: m for m in [api.edition_manifest("first-responder")]}
    assert {e["id"] for e in crew.entries} == edition_ids(corpus, manifests["first-responder"])
    build = api.team_view("build-crew")
    assert build.entries
    assert all("sw-crisis-001" != e["id"] for e in build.entries)
    # closure intact: every entry's prereqs are in the view
    for view in (crew, build):
        ids = {e["id"] for e in view.entries}
        for e in view.entries:
            for pre in e["prerequisites"]:
                assert pre in ids, (e["id"], pre)
    try:
        api.team_view("nope")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for unknown team")


# ── teams ───────────────────────────────────────────────────────────

def test_declared_teams_load():
    reg = TeamRegistry()
    teams = reg.list_teams()
    assert {t.id for t in teams} == {"field-crew", "build-crew"}
    field = reg.get("field-crew")
    assert field.editions == ("first-responder",)
    build = reg.get("build-crew")
    assert set(build.tracks) == {"build", "create"}
    try:
        reg.get("nope")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for unknown team")


def test_validate_team_rejects_bad_shapes():
    corpus_editions = {"first-responder"}
    assert validate_team(Team(id="Bad", name="x", tracks=("build",)), corpus_editions) != []
    assert validate_team(Team(id="ok", name="x", tracks=("teleport",)), corpus_editions) != []
    assert validate_team(Team(id="ok", name="x", editions=("nope",)), corpus_editions) != []
    assert validate_team(Team(id="ok", name="x"), corpus_editions) != []
    assert validate_team(Team(id="ok", name="Fine", tracks=("build",)), corpus_editions) == []


def test_register_save_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "teams.json"
        reg = TeamRegistry(path=path, known_editions={"first-responder"})
        assert reg.list_teams() == []
        reg.register(Team(id="night-shift", name="Night shift", tracks=("restore",),
                          editions=("first-responder",), members=["levi-7"]))
        reg2 = TeamRegistry(path=path, known_editions={"first-responder"})
        team = reg2.get("night-shift")
        assert team.members == ("levi-7",)
        assert team.editions == ("first-responder",)


def test_team_entry_ids_track_narrowing_keeps_closure():
    api = _api()
    corpus = load_corpus()
    manifests = {"first-responder": api.edition_manifest("first-responder")}
    build = api.team("build-crew")
    ids = team_entry_ids(corpus, manifests, build)
    by_id = {e["id"]: e for e in corpus.entries}
    # every build/create entry is present
    for e in corpus.entries:
        if set(e["tracks"]) & {"build", "create"}:
            assert e["id"] in ids, e["id"]
    # closure: prereqs of included entries are included
    for eid in ids:
        for pre in by_id[eid]["prerequisites"]:
            assert pre in ids, (eid, pre)


# ── learning loop ───────────────────────────────────────────────────

def _loop_entry(**over):
    entry = {
        "id": "sw-general-960",
        "title": "A field learning from the crew",
        "domain": "general",
        "tracks": ["improvise"],
        "level": "applied",
        "prerequisites": [],
        "difficulty": 2,
        "mechanism_check": ["how it works"],
        "improvised_tools": ["on-hand thing"],
        "steps": ["do it"],
        "stop_conditions": ["when done"],
    }
    entry.update(over)
    return entry


def test_loop_harvest_review_promote():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        intake = tmp / "intake"
        corpus_dir = tmp / "corpus"
        good = _loop_entry()
        bad = {"id": "sw-general-961", "title": "Missing keys"}
        report = loop_mod.harvest("field-crew", [good, bad], intake_dir=intake)
        assert report["received"] == 2
        assert report["valid"] == 1 and report["invalid"] == 1
        assert (intake / "field-crew.jsonl").is_file()
        # corpus untouched by harvest
        assert not corpus_dir.exists()
        # review is a dry run
        review = loop_mod.review_intake("field-crew", intake_dir=intake, corpus_dir=corpus_dir)
        assert review["valid"] == 1 and review["duplicates"] == 0
        assert not corpus_dir.exists()
        # promote appends only the valid entry, stamps provenance, keeps invalid
        promo = loop_mod.promote_intake("field-crew", intake_dir=intake, corpus_dir=corpus_dir)
        assert promo["appended"] == 1
        assert promo["invalid"] == 1
        shard = corpus_dir / "general.jsonl"
        promoted = json.loads(shard.read_text(encoding="utf-8").strip())
        assert promoted["id"] == "sw-general-960"
        assert promoted["provenance"]["team"] == "field-crew"
        assert "promoted" in promoted["provenance"]
        remaining = (intake / "field-crew.jsonl").read_text(encoding="utf-8")
        assert "Missing keys" in remaining
        assert "field learning" not in remaining


def test_loop_promote_dedups_against_corpus():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        intake = tmp / "intake"
        corpus_dir = tmp / "corpus"
        # seed the target corpus dir with the title so the harvest is a dup
        corpus_dir.mkdir()
        (corpus_dir / "plumbing.jsonl").write_text(
            json.dumps(_loop_entry(id="sw-plumbing-001",
                                   title="Remove a bathtub spout without a strap wrench",
                                   domain="plumbing",
                                   tracks=["restore", "improvise"],
                                   prerequisites=["sw-foundations-007"])) + "\n",
            encoding="utf-8")
        dup = _loop_entry(id="sw-general-962", title="Remove a bathtub spout without a strap wrench")
        loop_mod.harvest("field-crew", [dup], intake_dir=intake)
        promo = loop_mod.promote_intake("field-crew", intake_dir=intake, corpus_dir=corpus_dir)
        assert promo["duplicates"] == 1, promo
        assert promo["appended"] == 0, promo


def test_api_loop_rejects_unknown_team():
    api = _api()
    for name, call in (
        ("harvest", lambda: api.harvest("nope", [])),
        ("review_intake", lambda: api.review_intake("nope")),
        ("promote_intake", lambda: api.promote_intake("nope")),
    ):
        try:
            call()
        except KeyError:
            pass
        else:
            raise AssertionError(f"expected KeyError from {name}")


# ── skills / registry ───────────────────────────────────────────────

def test_skills_registered_in_shared_registry():
    reg = SkillRegistry()
    doctrine = reg.get("sidewinder_doctrine")
    manual = reg.get("sidewinder_field_manual")
    assert doctrine is not None and manual is not None
    assert doctrine.category == "fieldcraft"
    assert manual.category == "fieldcraft"
    assert "lives depend on it" in doctrine.handler({}).lower()
    out = manual.handler({"query": "tub spout"})
    assert "sw-plumbing-001" in out
    out = manual.handler({"query": "shelf", "edition": "first-responder"})
    assert isinstance(out, str)
    out = manual.handler({"query": "shelf", "team": "build-crew"})
    assert isinstance(out, str)
    out = manual.handler({"edition": "nope"})
    assert "unknown edition" in out
    names = [s.id for s in SIDEWINDER_SKILLS]
    assert names == ["sidewinder_doctrine", "sidewinder_field_manual"]


# ── CLI in-process ──────────────────────────────────────────────────

def _sw_ns(task=(), **kw):
    base = dict(task=list(task), domain=None, track=None, edition=None, team=None)
    base.update(kw)
    return argparse.Namespace(**base)


def _course_ns(query=(), **kw):
    base = dict(query=list(query), track=None, edition=None, team=None)
    base.update(kw)
    return argparse.Namespace(**base)


def _run_cmd(fn, ns):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = fn(ns)
    return code, buf.getvalue()


def test_cli_doctrine_manual_show_search():
    code, out = _run_cmd(cmd_sidewinder, _sw_ns(["doctrine"]))
    assert code == 0 and "lives depend on it" in out.lower()
    code, out = _run_cmd(cmd_sidewinder, _sw_ns(["manual", "--track", "improvise"]))
    assert code == 0 and "sw-crisis-001" in out
    code, out = _run_cmd(cmd_sidewinder, _sw_ns(["show", "sw-plumbing-001"]))
    assert code == 0 and "set screw" in out.lower()
    code, out = _run_cmd(cmd_sidewinder, _sw_ns(["tub", "spout"]))
    assert code == 0 and "sw-plumbing-001" in out
    code, _ = _run_cmd(cmd_sidewinder, _sw_ns(["xyzzy", "qqqq", "zzz"]))
    assert code == 1
    code, out = _run_cmd(cmd_sidewinder, _sw_ns(["tub", "spout"], edition="nope"))
    assert code == 2 and "unknown edition" in out


def test_cli_bare_sidewinder_shows_mode_card():
    code, out = _run_cmd(cmd_sidewinder, _sw_ns())
    assert code == 0
    assert "SIDEWINDER MODE" in out
    assert "improvise=" in out
    assert "editions:" in out and "teams:" in out
    assert "first-responder" in out and "field-crew" in out


def test_cli_teams_and_loop_actions():
    code, out = _run_cmd(cmd_sidewinder, _sw_ns(["teams"]))
    assert code == 0 and "field-crew" in out and "build-crew" in out
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        seed_file = tmp / "crew.jsonl"
        seed_file.write_text(json.dumps(_loop_entry(id="sw-general-970",
                                                    title="CLI harvest entry")) + "\n",
                             encoding="utf-8")
        with mock.patch.object(loop_mod, "DEFAULT_INTAKE_DIR", tmp / "intake"):
            code, out = _run_cmd(cmd_sidewinder, _sw_ns(["team-harvest", "field-crew", str(seed_file)]))
            assert code == 0, out
            assert "received=1 valid=1" in out
            code, out = _run_cmd(cmd_sidewinder, _sw_ns(["team-review", "field-crew"]))
            assert code == 0 and "DRY RUN" in out
            code, out = _run_cmd(cmd_sidewinder, _sw_ns(["team-harvest", "nope", str(seed_file)]))
            assert code == 2 and "unknown team" in out
        # promote/review hit the real corpus dir — patch the loop functions
        with mock.patch.object(loop_mod, "review_intake", return_value={"team": "field-crew", "seeds_read": 1, "valid": 1, "invalid": 0, "duplicates": 0, "errors": []}):
            code, out = _run_cmd(cmd_sidewinder, _sw_ns(["team-review", "field-crew"]))
            assert code == 0 and "would_append=1" in out
        with mock.patch.object(loop_mod, "promote_intake", return_value={"team": "field-crew", "valid": 1, "invalid": 0, "duplicates": 0, "appended": 1, "per_domain": {"general": 1}, "seeds_json_bad": 0, "errors": []}):
            code, out = _run_cmd(cmd_sidewinder, _sw_ns(["team-promote", "field-crew"]))
            assert code == 0 and "appended=1" in out


def test_cli_course_tracks_editions_track_topic():
    code, out = _run_cmd(cmd_course, _course_ns())
    assert code == 0 and "six tracks" in out
    code, out = _run_cmd(cmd_course, _course_ns(["tracks"]))
    assert code == 0 and "improvise" in out
    code, out = _run_cmd(cmd_course, _course_ns(["editions"]))
    assert code == 0 and "first-responder" in out and "First Responder" in out
    code, out = _run_cmd(cmd_course, _course_ns(["improvise"]))
    assert code == 0 and "FOUNDATION" in out and "sw-crisis-001" in out
    code, out = _run_cmd(cmd_course, _course_ns(["tub", "spout"]))
    assert code == 0 and "LEARNING PATH" in out and "sw-foundations-007" in out
    code, out = _run_cmd(cmd_course, _course_ns([], edition="first-responder"))
    assert code == 0 and "FIRST RESPONDER" in out
    code, out = _run_cmd(cmd_course, _course_ns(["improvise"], team="field-crew"))
    assert code == 0 and "sw-crisis-001" in out
    code, out = _run_cmd(cmd_course, _course_ns(["improvise"], edition="nope"))
    assert code == 2 and "unknown edition" in out
    code, _ = _run_cmd(cmd_course, _course_ns(["xyzzy", "qqqq", "zzz"]))
    assert code == 1


def test_cli_grow_and_stubs():
    code, out = _run_cmd(cmd_sidewinder, _sw_ns(["grow", "--dry-run"]))
    assert code == 0 and "DRY RUN" in out
    code, out = _run_cmd(cmd_sidewinder, _sw_ns(["stubs"]))
    assert code == 2 and "give a count" in out


# ── CLI subprocess smoke ────────────────────────────────────────────

def _env(home: str):
    env = dict(os.environ)
    env["HOME"] = home
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "core"), *sys.path])
    env.pop("LEVI_GITHUB_TOKEN", None)
    return env


def _cli(home: str, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "levi.cli.main", *argv],
        cwd=ROOT,
        env=_env(home),
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_cli_wiring_end_to_end():
    with tempfile.TemporaryDirectory(prefix="course_platform_cli_") as home:
        p = _cli(home, "sidewinder", "doctrine")
        assert p.returncode == 0, p.stderr
        assert "lives depend on it" in p.stdout.lower()
        p = _cli(home, "sidewinder", "tub spout")
        assert p.returncode == 0, p.stderr
        assert "sw-plumbing-001" in p.stdout
        p = _cli(home, "sidewinder", "manual", "--track", "improvise")
        assert p.returncode == 0, p.stderr
        assert "sw-crisis-001" in p.stdout
        p = _cli(home, "sidewinder", "teams")
        assert p.returncode == 0, p.stderr
        assert "field-crew" in p.stdout
        p = _cli(home, "course", "tracks")
        assert p.returncode == 0, p.stderr
        assert "six tracks" in p.stdout
        p = _cli(home, "course", "editions")
        assert p.returncode == 0, p.stderr
        assert "first-responder" in p.stdout
        p = _cli(home, "course", "--edition", "first-responder")
        assert p.returncode == 0, p.stderr
        assert "FIRST RESPONDER" in p.stdout
        p = _cli(home, "course", "improvise", "--team", "field-crew")
        assert p.returncode == 0, p.stderr
        assert "sw-crisis-001" in p.stdout
        p = _cli(home, "course", "--edition", "nope")
        assert p.returncode == 2, p.stderr
        assert "unknown edition" in p.stdout
        p = _cli(home, "course", "tub spout")
        assert p.returncode == 0, p.stderr
        assert "LEARNING PATH" in p.stdout


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
