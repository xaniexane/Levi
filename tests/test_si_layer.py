"""Proof gate for the SI intelligence layer (laws.py L1-L6).

Honestly described: invariant/property checks, not formal proof.
Each test names the law it checks; laws.LAW_TESTS maps law -> tests.
"""

import json
import re
import wave
from pathlib import Path

import pytest

from levi.si.builder_gen import (
    si_generator,
    si_planner_generator,
    si_refine_notes,
)
from levi.si.engine import SIEngine
from levi.si.hicomb_backend import BrainBackend
from levi.si.laws import LAWS, LAW_TESTS
from levi.si.plugins.focus_flow import FocusConfig, FocusSession

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "core" / "levi"


# -- L1: honest tier ---------------------------------------------------

CONSULT_CASES = [
    ("plan-brief", {"description": "a notes app with sharing"}),
    ("idea-spark", {"prompt": "offline sync for notes"}),
    ("review-notes", {"description": "a notes app with sharing"}),
    ("focus-pick", {"minutes": 25, "mood": "calm"}),
]


@pytest.mark.parametrize("kind,payload", CONSULT_CASES)
def test_every_result_names_tier(kind, payload):
    eng = SIEngine(brain_loader=_boom_loader)
    res = eng.consult(kind, payload)
    assert res.tier in ("rules", "brain")
    assert res.tier == "rules"  # no brain here -> rules fallback, named


class _FakeBrain:
    def generate(self, prompt, max_new_chars=60, temperature=0.5, seed=1):
        return {"continuation": "def frob(x): return x", "prompt_chars": len(prompt)}


def _boom_loader():
    raise RuntimeError("no weights on this machine")


def test_brain_results_labeled_not_reasoning():
    eng = SIEngine(brain_loader=lambda: _FakeBrain())
    res = eng.consult("idea-spark", {"prompt": "sync"})
    assert res.tier == "brain"
    assert any("not reasoning" in lim for lim in res.limits)
    draft = eng.generate_draft("sync notes")
    assert draft.tier == "brain"
    assert any("not reasoning" in lim for lim in draft.limits)


def test_brain_backend_provenance_labels():
    back = BrainBackend(engine=SIEngine(brain_loader=lambda: _FakeBrain()))
    assert back.available() is True
    comps = back.complete("def frob(", "", "python")
    assert len(comps) == 1
    c = comps[0]
    assert c.source == "model"
    assert "not reasoning" in c.label
    assert c.confidence <= 0.3
    chat = back.chat("explain", "code", "python")
    assert "not reasoning" in chat


# -- L3: graceful degrade ----------------------------------------------

def test_consult_survives_broken_brain():
    eng = SIEngine(brain_loader=_boom_loader)
    assert eng.brain_available() is False
    st = eng.status()
    assert st["tiers"]["brain"] is False
    assert st["tiers"]["brain_error"]
    assert "teachers only" in st["teacher"]
    # every kind still answers
    for kind, payload in CONSULT_CASES:
        res = eng.consult(kind, payload)
        assert res.tier == "rules"


def test_backend_unavailable_degrades_pair_programmer():
    from levi.hicomb.ai import PairProgrammer

    prog = PairProgrammer(backend=BrainBackend(engine=SIEngine(brain_loader=_boom_loader)))
    assert prog.status() == "local-only"
    comps = prog.suggest("def ", 1, 5, "python")
    assert all(c.source == "local" for c in comps)


def test_consult_unknown_kind_raises():
    with pytest.raises(ValueError):
        SIEngine().consult("nope", {})


# -- L5: contract-safe --------------------------------------------------

PLANNER_PROMPTS = [
    "a notes app with sharing and tags",
    "BookHaven — an online bookstore!!!",
    "",
    "x" * 5000,
    "CRM für Ärzte; données sensibles",
]


@pytest.mark.parametrize("desc", PLANNER_PROMPTS)
def test_planner_json_parses_across_descriptions(desc):
    from levi.builder.scaffolds.spec import parse_spec_json

    prompt = (
        f"Application description: {desc}\n\n"
        "Produce the build spec as JSON matching this schema:\n{}"
    )
    text = si_planner_generator(prompt, "system", engine=SIEngine(brain_loader=_boom_loader))
    spec = parse_spec_json(text, desc, "static")
    assert spec.spec_source == "si-rules"
    assert spec.entities, "spec must name at least one entity"


def test_run_build_static_completes_offline(tmp_path):
    from levi.builder.pipeline import run_build

    report = run_build(
        "a focus timer",
        stack="static",
        name="focusapp",
        out_dir=tmp_path,
        generate=si_generator,
        quality="off",
    )
    assert report.ok, report.summary()
    assert report.spec_source == "si-rules"
    manifest = json.loads((Path(report.project_dir) / "levi-build.json").read_text())
    assert manifest["spec"]["spec_source"] == "si-rules"


def test_si_generator_declines_non_planner_stages():
    from levi.builder.generate import GenerationError

    with pytest.raises(GenerationError) as ei:
        si_generator("Write the frontend code", "system")
    assert "planner stage only" in str(ei.value)


# -- L2: local runtime ---------------------------------------------------

_NET_IMPORTS = re.compile(
    r"^\s*(import|from)\s+(socket|requests|urllib|http\.client|websocket|aiohttp)\b",
    re.M,
)


@pytest.mark.parametrize(
    "mod", ["engine.py", "builder_gen.py", "hicomb_backend.py", "plugins/focus_flow.py", "laws.py"]
)
def test_no_network_imports_in_si_modules(mod):
    src = (CORE / "si" / mod).read_text()
    assert not _NET_IMPORTS.search(src), f"network import in {mod}"


def test_cell_has_no_network_strings():
    cell = CORE / "si/plugins/cells/focus-flow/cell.js"
    src = cell.read_text()
    for pat in (r"\bfetch\s*\(", r"\bXMLHttpRequest\b", r"\bWebSocket\s*\(", r"https?://"):
        assert not re.search(pat, src), f"net pattern in cell.js: {pat}"
    assert "defineCellPlugin" in src


def test_focus_flow_manifest_validates(tmp_path):
    from levi.hicomb.plugin_studio import test_plugin

    cell_dir = CORE / "si/plugins/cells/focus-flow"
    report = test_plugin(cell_dir, store_dir=tmp_path / "studio")
    assert report.ok, report.problems
    man = json.loads((cell_dir / "tricombs.json").read_text())
    assert man["name"] == "focus-flow"
    assert "commands" in man["needs"]


# -- L4: no fake capability ----------------------------------------------

def test_focus_flow_receipt_states_synth_not_music(tmp_path):
    sess = FocusSession(engine=SIEngine(brain_loader=_boom_loader))
    plan = sess.plan(minutes=25, mood="calm")
    assert plan["queue"], "queue should curate from the fake catalog"
    assert "no audio" in plan["queue_note"]
    wav = tmp_path / "pad.wav"
    receipt = sess.render(str(wav), FocusConfig(minutes=5, seed=7), seconds=8)
    assert wav.is_file()
    assert receipt["synth"] is True
    assert "not licensed music" in receipt["note"]
    assert receipt["duration_s"] == 8
    with wave.open(str(wav), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getnframes() == 8 * w.getframerate()
    assert 0.0 < receipt["rms"] < 1.0


def test_focus_flow_render_is_deterministic(tmp_path):
    sess = FocusSession(engine=SIEngine(brain_loader=_boom_loader))
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    ra = sess.render(str(a), FocusConfig(minutes=5, seed=7), seconds=8)
    rb = sess.render(str(b), FocusConfig(minutes=5, seed=7), seconds=8)
    assert ra["sha256"] == rb["sha256"]


def test_limits_documented():
    assert set(LAWS) == {"L1", "L2", "L3", "L4", "L5", "L6"}
    for law, tests in LAW_TESTS.items():
        assert tests, f"{law} has no proof tests"


# -- misc invariants ----------------------------------------------------

def test_decide_is_deterministic_ranking():
    eng = SIEngine()
    options = [
        {"id": "a", "speed": 1.0, "cost": 0.2},
        {"id": "b", "speed": 0.5, "cost": 0.9},
    ]
    r1 = eng.decide(options, {"speed": 0.7, "cost": 0.3})
    r2 = eng.decide(options, {"speed": 0.7, "cost": 0.3})
    assert r1 == r2
    assert r1["winner"] == "a"
    assert r1["ranking"] == ["a", "b"]


def test_si_refine_notes_flags_ambiguities():
    notes = si_refine_notes(
        {
            "domain": "notes",
            "entities": ["note", "tag", "share", "user"],
            "modules": ["a", "b"],
            "api_surface": [],
            "ambiguities": ["auth: unanswered"],
        }
    )
    assert any("auth: unanswered" in n for n in notes)
    assert any("no API surface" in n for n in notes)


def test_layer_additive_no_core_patching():
    """L6: the layer is additive — importing it never patches core modules,
    and every module it ships lives under core/levi/si/.

    (On this hot shared branch siblings legitimately modify core files,
    so worktree-diff attribution cannot be a pytest; it is enforced at
    commit time via the temp-index route, which stages only owned paths.)
    """
    import levi.si.builder_gen
    import levi.si.engine
    import levi.si.hicomb_backend
    import levi.si.plugins.focus_flow
    import levi.si.plugins.google_drive

    import levi.builder.pipeline as pipe_mod
    import levi.buzztunes.engine as buzz_mod
    import levi.hicomb.ai as ai_mod

    before = (ai_mod.PairProgrammer, pipe_mod.run_build, buzz_mod.BuzzEngine)
    # (re)import the layer after capturing core identities
    import importlib

    for name in (
        "levi.si.engine",
        "levi.si.builder_gen",
        "levi.si.hicomb_backend",
        "levi.si.plugins.focus_flow",
        "levi.si.plugins.google_drive",
    ):
        importlib.import_module(name)
    assert ai_mod.PairProgrammer is before[0]
    assert pipe_mod.run_build is before[1]
    assert buzz_mod.BuzzEngine is before[2]

    import levi.si

    si_root = str(CORE / "si") + "/"
    for mod in (
        levi.si.engine,
        levi.si.builder_gen,
        levi.si.hicomb_backend,
        levi.si.plugins.focus_flow,
        levi.si.plugins.google_drive,
    ):
        assert mod.__file__.startswith(si_root), mod.__name__
    for src in (
        "engine.py",
        "builder_gen.py",
        "hicomb_backend.py",
        "plugins/focus_flow.py",
        "plugins/google_drive.py",
    ):
        text = (CORE / "si" / src).read_text()
        assert "setattr(levi" not in text
        assert "monkeypatch" not in text


# -- Google plugin (G1-G7) -------------------------------------------------

import stat

from levi.si.plugins.glaws import GLAWS, GLAW_TESTS
from levi.si.plugins.google_drive import (
    DriveError,
    DriveSession,
)

_STUB = r"""#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
def out(obj):
    print(json.dumps(obj))
if os.environ.get("FAKE_DRIVE_ERROR") == "1":
    out({"error": {"message": "boom"}}); sys.exit(0)
# find -o output path
opath = None
if "-o" in args:
    opath = args[args.index("-o") + 1]
params = {}
if "--params" in args:
    params = json.loads(args[args.index("--params") + 1])
if args[:2] == ["drive", "files"] and args[2] == "list":
    out({"files": [{"id": "f1", "name": "a.py", "mimeType": "text/x-python",
                    "modifiedTime": "2026-01-01T00:00:00Z", "size": "13"}]})
elif args[:2] == ["drive", "files"] and args[2] == "download":
    mode = os.environ.get("FAKE_DRIVE_MODE", "ok")
    data = b"x" * (2 * 1024 * 1024) if mode == "big" else \
           b"\xff\xfe\x00bad" if mode == "binary" else b"print('hi')\n"
    open(opath, "wb").write(data); out({})
elif args[:2] == ["drive", "files"] and args[2] == "get":
    out({"id": params.get("fileId", "f1"), "name": "a.py"})
elif args[:2] == ["drive", "+upload"]:
    name = "n.py"
    if "--name" in args:
        name = args[args.index("--name") + 1]
    else:
        for a in args[2:]:
            if not a.startswith("--"):
                name = os.path.basename(a); break
    out({"id": "new1", "name": name})
elif args[:2] == ["drive", "files"] and args[2] == "update":
    out({"id": params.get("fileId", "f1"), "name": "a.py"})
else:
    out({"error": {"message": f"stub: unknown {args}"}})
"""


@pytest.fixture()
def fake_cli(tmp_path):
    p = tmp_path / "fake_gws"
    p.write_text(_STUB)
    p.chmod(p.stat().st_mode | stat.S_IXUSR)
    return str(p)


def test_drive_session_has_no_destructive_methods():
    for name in ("delete", "trash", "emptyTrash", "permissions",
                 "watch", "remove", "destroy"):
        assert not hasattr(DriveSession, name), f"G1 violated: {name} exists"


def test_drive_session_makes_no_calls_on_init(tmp_path, monkeypatch):
    sentinel = tmp_path / "called"
    monkeypatch.setenv("FAKE_DRIVE_SENTINEL", str(sentinel))
    script = tmp_path / "spy"
    script.write_text("#!/bin/sh\ntouch \"$FAKE_DRIVE_SENTINEL\"\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    DriveSession(cli=str(script))
    assert not sentinel.exists(), "G2 violated: init made a call"


def test_drive_transfer_receipts_carry_provenance(tmp_path, fake_cli):
    sess = DriveSession(cli=fake_cli)
    dest = tmp_path / "a.py"
    r = sess.pull("f1", str(dest))
    d = r.to_dict()
    assert d["direction"] == "pull"
    assert d["file_id"] == "f1" and d["name"] == "a.py"
    assert d["bytes"] == len(b"print('hi')\n") and len(d["sha256"]) == 64
    assert d["ts"].endswith("Z")
    assert dest.read_text() == "print('hi')\n"
    src = tmp_path / "b.py"
    src.write_text("x = 1\n")
    r2 = sess.push_new(str(src))
    assert r2.to_dict()["direction"] == "push"
    assert r2.file_id == "new1"
    r3 = sess.push_update("f1", str(src))
    assert r3.file_id == "f1"


def test_drive_refuses_oversize_and_binary(tmp_path, fake_cli, monkeypatch):
    sess = DriveSession(cli=fake_cli)
    monkeypatch.setenv("FAKE_DRIVE_MODE", "big")
    with pytest.raises(DriveError, match="cap"):
        sess.read_text("f1")
    monkeypatch.setenv("FAKE_DRIVE_MODE", "binary")
    with pytest.raises(DriveError, match="UTF-8"):
        sess.read_text("f1")
    monkeypatch.setenv("FAKE_DRIVE_MODE", "ok")
    big = tmp_path / "big.txt"
    big.write_bytes(b"x" * (2 * 1024 * 1024))
    with pytest.raises(DriveError, match="1MB"):
        sess.push_new(str(big))


def test_drive_api_error_raises(fake_cli, monkeypatch):
    monkeypatch.setenv("FAKE_DRIVE_ERROR", "1")
    with pytest.raises(DriveError, match="boom"):
        DriveSession(cli=fake_cli).list()


def test_drive_session_handles_no_tokens():
    src = (CORE / "si/plugins/google_drive.py").read_text()
    for pat in (r"\btoken\b", r"\bsecret\b", r"api_key", r"client_secret"):
        assert not re.search(pat, src, re.I), f"G7: credential handling? {pat}"


def test_google_cell_manifest_validates(tmp_path):
    from levi.hicomb.plugin_studio import test_plugin

    cell_dir = CORE / "si/plugins/cells/google-drive"
    report = test_plugin(cell_dir, store_dir=tmp_path / "studio")
    assert report.ok, report.problems
    man = json.loads((cell_dir / "tricombs.json").read_text())
    assert man["name"] == "google-drive"
    assert {"commands", "editor", "fs-write"} <= set(man["needs"])


def test_google_cell_stages_not_transfers():
    src = (CORE / "si/plugins/cells/google-drive/cell.js").read_text()
    assert "google-drive-outbox" in src
    assert "python3 -m levi.si.plugins.google_drive push" in src
    assert "hatch_gws_cli" not in src
    assert "defineCellPlugin" in src
    for pat in (r"\bfetch\s*\(", r"\bXMLHttpRequest\b", r"\bWebSocket\s*\(", r"https?://"):
        assert not re.search(pat, src), f"net pattern in google cell: {pat}"


def test_glaws_documented():
    assert set(GLAWS) == {"G1", "G2", "G3", "G4", "G5", "G6", "G7"}
    for law, tests in GLAW_TESTS.items():
        assert tests, f"{law} has no proof tests"
