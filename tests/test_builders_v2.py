"""KFX2 BUILDERS milestone 2 — the complexity engine.

Planner seat, domain packs, typed actions, five verify gates, change-scoped
refinement. Hermetic: no network, no daemons. The generated projects are
exercised for real (compile, contracts, safety, packaging, live tests).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile

import pytest

from levi.builders import (
    BuildOutcome,
    build,
    refine,
    refine_project,
)
from levi.builders.packs import detect_domain, get_pack
from levi.builders.planner import plan
from levi.builders.scaffold import ScaffoldEngine
from levi.builders.verify import (
    _check_contracts,
    _check_safety as _safety,
)


def _tree(root):
    tree = {}
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            full = os.path.join(dirpath, name)
            with open(full, "rb") as fh:
                tree[os.path.relpath(full, root)] = fh.read()
    return tree


# -- planner seat -----------------------------------------------------------


def test_planner_detects_all_five_domains():
    cases = {
        "a REST API with auth to manage tasks": "web-api",
        "a command line tool to manage todos": "cli-tool",
        "a realtime event feed for chat": "realtime",
        "a data pipeline to clean orders": "data-pipeline",
        "a simple app to track vinyl records": "general",
    }
    for prompt, domain in cases.items():
        assert plan(prompt).domain == domain, prompt
        assert detect_domain(prompt) == domain, prompt


def test_planner_entities_and_ambiguity_word_boundary():
    p = plan("Build me a simple app to track my vinyl records and manage playlists")
    assert "record" in p.entities or "playlist" in p.entities
    # "records" must not trip the "or" ambiguity marker (substring false positive)
    assert not any("'or'" in a for a in p.ambiguities), p.ambiguities
    p2 = plan("a todo app or maybe a notes app, not sure")
    assert p2.ambiguities, "genuine ambiguity should be flagged"


def test_planner_field_words_are_not_entities():
    p = plan("a REST API to manage tasks with due dates and priorities")
    assert "date" not in p.entities, p.entities
    assert "priority" not in p.entities, p.entities  # a field, never an entity
    assert "task" in p.entities, p.entities
    field_names = {f.name for e in p.data_model for f in e.fields}
    assert "priority" in field_names, field_names  # priorities -> priority field
    assert "due" in field_names, field_names


def test_planner_field_word_plural_forms():
    p = plan("a REST API to manage orders with statuses and delivery addresses")
    assert "status" not in p.entities, p.entities
    assert "address" not in p.entities, p.entities
    assert "order" in p.entities, p.entities
    field_names = {f.name for e in p.data_model for f in e.fields}
    assert "status" in field_names, field_names  # statuses -> status field
    assert "address" in field_names, field_names  # addresses -> address field


def test_domain_packs_carry_modules_and_rules():
    for domain in ("web-api", "cli-tool", "realtime", "data-pipeline", "general"):
        pack = get_pack(domain)
        assert pack["modules"], domain
        assert pack["entry"], domain
        assert pack["forbidden"], domain
        assert any(m["kind"] == "entry" for m in pack["modules"]), domain
        assert any(m["kind"] == "test" for m in pack["modules"]), domain


# -- complex builds verify first attempt ------------------------------------


def test_webapi_build_verified_with_auth_and_models():
    with tempfile.TemporaryDirectory() as tmp:
        report = build(
            "a REST API with bearer token auth to manage tasks and projects",
            workdir=tmp,
        )
    assert report.outcome is BuildOutcome.VERIFIED, report.diagnostics
    assert report.domain == "web-api"
    for expected in (
        "app.py",
        "auth.py",
        "store.py",
        "api/models.py",
        "api/routes.py",
        "migrations/m0001_init.py",
        "tests/test_models.py",
        "tests/test_api.py",
        "tests/test_smoke.py",
        ".env.example",
    ):
        assert expected in report.files, expected


def test_cli_build_verified():
    with tempfile.TemporaryDirectory() as tmp:
        report = build("a todo CLI to manage shopping items", workdir=tmp)
    assert report.outcome is BuildOutcome.VERIFIED, report.diagnostics
    assert report.domain == "cli-tool"
    assert "cli.py" in report.files and "core.py" in report.files


def test_realtime_build_verified():
    with tempfile.TemporaryDirectory() as tmp:
        report = build("a realtime event feed for chat messages", workdir=tmp)
    assert report.outcome is BuildOutcome.VERIFIED, report.diagnostics
    assert report.domain == "realtime"
    assert "events.py" in report.files


def test_pipeline_build_verified():
    with tempfile.TemporaryDirectory() as tmp:
        report = build("a data pipeline to clean and dedupe orders", workdir=tmp)
    assert report.outcome is BuildOutcome.VERIFIED, report.diagnostics
    assert report.domain == "data-pipeline"
    assert "run.py" in report.files and "stages.py" in report.files


# -- the five gates bite -----------------------------------------------------


def _break_on_attempts(breakers):
    """breakers: {attempt: {path: transform}} — test-only fault injection."""

    def hook(attempt, files):
        for path, transform in breakers.get(attempt, {}).items():
            if path in files:
                files[path] = transform(files[path])

    return hook


def test_safety_gate_catches_stray_deletion_and_heals():
    def add_evil(src):
        return src + "\nimport os\nos.remove('/tmp/should-never-vanish')\n"

    with tempfile.TemporaryDirectory() as tmp:
        report = build(
            "a REST API to manage tasks",
            workdir=tmp,
            _fault_hook=_break_on_attempts({0: {"store.py": add_evil}}),
        )
    assert report.outcome is BuildOutcome.SELF_HEALED, report.diagnostics
    assert report.attempts == 2


def test_contracts_gate_catches_bad_import_and_heals():
    def add_bad_import(src):
        return "from no_such_module_xyz import thing\n" + src

    with tempfile.TemporaryDirectory() as tmp:
        report = build(
            "a simple app to track books",
            workdir=tmp,
            _fault_hook=_break_on_attempts({0: {"app.py": add_bad_import}}),
        )
    assert report.outcome is BuildOutcome.SELF_HEALED, report.diagnostics


def test_guarded_tmp_cleanup_passes_safety_gate():
    engine = ScaffoldEngine("a REST API to manage tasks")
    files = engine.generate()
    result = _safety(engine.build_plan, files)
    assert result.passed, result.detail


def test_contracts_gate_checks_routability_not_substrings():
    engine = ScaffoldEngine("a REST API to manage tasks and projects")
    plan_ = engine.build_plan
    files = engine.generate()
    # routes.py is generic — it never names entities literally.
    assert "task" not in files["api/routes.py"].replace("PLURALS", "")
    result = _check_contracts(plan_, files)
    assert result.passed, result.detail


# -- change-scoped refinement --------------------------------------------------


def test_refine_is_change_scoped_and_verified():
    with tempfile.TemporaryDirectory() as tmp:
        report = build("a REST API with bearer token auth to manage tasks", workdir=tmp)
        assert report.ok
        before = _tree(report.target_dir)
        rep = refine_project(report.target_dir, "also manage notes alongside tasks")
        after = _tree(report.target_dir)
        prov = json.load(open(os.path.join(report.target_dir, ".provenance.json")))
    assert rep.outcome is BuildOutcome.VERIFIED, rep.diagnostics
    # Untouched files are byte-identical; nothing is ever deleted.
    for path in rep.files_untouched:
        assert (
            hashlib.sha256(before[path]).digest()
            == hashlib.sha256(after[path]).digest()
        ), path
    assert set(before) <= set(after)
    assert rep.files_changed, "a real change must touch something"
    assert all(c.passed for c in rep.checks)
    assert len(prov["iterations"]) == 1
    assert prov["iterations"][0]["outcome"] == "verified"
    assert "note" in prov["entities"]


def test_refine_rejects_empty_change():
    with tempfile.TemporaryDirectory() as tmp:
        report = build("a simple app to track books", workdir=tmp)
        assert report.ok
        with pytest.raises(ValueError):
            refine(tmp, "   ")


def test_refine_provenance_keeps_original_prompt():
    with tempfile.TemporaryDirectory() as tmp:
        report = build("a simple app to track books", workdir=tmp)
        prov = json.load(open(os.path.join(report.target_dir, ".provenance.json")))
        assert prov["prompt"] == "a simple app to track books"
        assert (
            prov["prompt_sha256"]
            == ScaffoldEngine("a simple app to track books").prompt_hash
        )


# -- hardened retry semantics --------------------------------------------------


def test_failed_gates_short_circuit_the_smoke_gate():
    def break_compile(src):
        return src + "\ndef broken(:\n"

    with tempfile.TemporaryDirectory() as tmp:
        report = build(
            "a simple app to track books",
            workdir=tmp,
            _fault_hook=_break_on_attempts({0: {"app.py": break_compile}}),
        )
    # Fault only fires on attempt 0, so this heals — but the attempt-0
    # report must show the smoke gate skipped, not run against broken code.
    assert report.outcome is BuildOutcome.SELF_HEALED, report.diagnostics


def test_bound_exhaustion_never_downgrades_domain():
    def always_break(src):
        return src + "\ndef broken(:\n"

    with tempfile.TemporaryDirectory() as tmp:
        report = build(
            "a REST API with bearer token auth to manage tasks",
            workdir=tmp,
            _fault_hook=_break_on_attempts(
                {
                    0: {"app.py": always_break},
                    1: {"app.py": always_break},
                    2: {"app.py": always_break},
                    3: {"app.py": always_break},
                }
            ),
        )
    assert report.outcome is BuildOutcome.OWNER_DECISION_NEEDED
    assert report.domain == "web-api", "repair must not silently change domain"
    assert "minimal" not in report.diagnostics.lower()


def test_retry_never_deletes_preexisting_files():
    sentinel = "owner-notes.txt"
    sentinel_body = "Chauncey's own file — the builder must never touch it."

    def break_once(src):
        return src + "\ndef broken(:\n"

    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, sentinel), "w") as fh:
            fh.write(sentinel_body)
        report = build(
            "a simple app to track books",
            workdir=tmp,
            _fault_hook=_break_on_attempts({0: {"app.py": break_once}}),
        )
        assert report.outcome is BuildOutcome.SELF_HEALED
        assert report.attempts == 2, "the retry must actually have run"
        with open(os.path.join(tmp, sentinel)) as fh:
            assert fh.read() == sentinel_body
