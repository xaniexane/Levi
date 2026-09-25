"""Tests for levi.revival.omega.pipeline — the Forge.

Echo -> Alpha -> preview -> permission -> materialize -> Nexus -> receipt,
with the honest gates: no default approval, preview before write, every
stage saying what it did and did NOT do.
"""

import hashlib
import os

import pytest

from levi.revival.omega import nexus as nx
from levi.revival.omega import pipeline as forge

PROMPT = "a landing page website for my bakery"


def _dest(tmp_path, name="out"):
    d = tmp_path / name
    d.mkdir()
    return str(d)


# ---- module identity ----


def test_origin():
    assert forge.ORIGIN == "levi-revival-omega/forge"


def test_stage_shape_everywhere(tmp_path):
    """Every stage result carries did / did_not — the honesty contract."""
    result = forge.run_pipeline(PROMPT, dest=_dest(tmp_path), approve=True)
    assert result["ok"]
    for stage in result["stages"]:
        assert set(stage) >= {"stage", "ok", "did", "did_not", "data", "error"}
        assert stage["did"] and stage["did_not"]
    assert [s["stage"] for s in result["stages"]] == [
        "echo",
        "alpha",
        "preview",
        "permission",
        "materialize",
        "nexus",
    ]


# ---- the permission gate ----


def test_approve_refusal_writes_nothing(tmp_path):
    """Without approve=True the run refuses and the disk stays untouched."""
    dest = _dest(tmp_path)
    result = forge.run_pipeline(PROMPT, dest=dest, approve=False)
    assert not result["ok"]
    gate = next(s for s in result["stages"] if s["stage"] == "permission")
    assert not gate["ok"]
    assert "explicit" in gate["error"].lower()
    assert os.listdir(dest) == []
    # the pipeline stopped at the gate: no materialize, no nexus
    assert [s["stage"] for s in result["stages"]] == [
        "echo",
        "alpha",
        "preview",
        "permission",
    ]


def test_approve_true_writes_and_receipt(tmp_path):
    dest = _dest(tmp_path)
    result = forge.run_pipeline(PROMPT, dest=dest, approve=True)
    assert result["ok"]
    mat = next(s for s in result["stages"] if s["stage"] == "materialize")
    assert mat["ok"]
    written = mat["data"]["written"]
    assert written
    for entry in written:
        target = os.path.join(dest, entry["path"])
        assert os.path.isfile(target)
        with open(target, "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == entry["sha256"]
    assert mat["data"]["receipt"]["verified"]


# ---- preview before write ----


def test_preview_stage_is_pure_and_lists_paths(tmp_path):
    dest = _dest(tmp_path)
    result = forge.run_pipeline(PROMPT, dest=dest, approve=True)
    preview = next(s for s in result["stages"] if s["stage"] == "preview")
    assert preview["ok"]
    alpha = next(s for s in result["stages"] if s["stage"] == "alpha")
    for path in alpha["data"]["paths"]:
        assert path in preview["data"]["preview_text"]
    # preview promises no writes
    assert any("writes nothing" in d for d in preview["did_not"])
    actions = {e["action"] for e in preview["data"]["entries"]}
    assert actions == {"write"}  # fresh dest: everything lands


def test_preview_shows_skip_existing(tmp_path):
    dest = _dest(tmp_path)
    forge.run_pipeline(PROMPT, dest=dest, approve=True)
    second = forge.run_pipeline(PROMPT, dest=dest, approve=True)
    assert second["ok"]
    entries = next(s for s in second["stages"] if s["stage"] == "preview")["data"][
        "entries"
    ]
    assert {e["action"] for e in entries} == {"skip-existing"}
    mat = next(s for s in second["stages"] if s["stage"] == "materialize")
    assert mat["data"]["written"] == []  # nothing clobbered


# ---- echo honesty ----


def test_echo_exposes_heuristic_scores(tmp_path):
    result = forge.run_pipeline(PROMPT, dest=_dest(tmp_path), approve=True)
    echo = next(s for s in result["stages"] if s["stage"] == "echo")
    assert echo["data"]["detection_scores"].get("webpage", 0) > 0
    assert any("heuristic" in d for d in echo["did_not"])


def test_empty_prompt_is_a_loud_error(tmp_path):
    with pytest.raises(ValueError):
        forge.run_pipeline("   ", dest=_dest(tmp_path), approve=True)


def test_unknown_product_type_refused(tmp_path):
    """Bad product types are a structured echo refusal, not an exception."""
    result = forge.run_pipeline(
        PROMPT,
        dest=_dest(tmp_path),
        approve=True,
        product_types=["teleporter"],
    )
    assert not result["ok"]
    echo = next(s for s in result["stages"] if s["stage"] == "echo")
    assert not echo["ok"]
    assert "teleporter" in echo["error"]


# ---- alpha generator pick ----


def test_generator_pick_narrows_output(tmp_path):
    prompt = "a landing page website and a command line tool"
    dest_all = _dest(tmp_path, "all")
    all_result = forge.run_pipeline(prompt, dest=dest_all, approve=True)
    all_paths = next(s for s in all_result["stages"] if s["stage"] == "alpha")["data"][
        "paths"
    ]

    dest_cli = _dest(tmp_path, "cli")
    cli_result = forge.run_pipeline(
        prompt, dest=dest_cli, approve=True, generator="cli"
    )
    cli_paths = next(s for s in cli_result["stages"] if s["stage"] == "alpha")["data"][
        "paths"
    ]
    assert cli_paths
    assert len(cli_paths) < len(all_paths)
    assert not any(p.endswith(".html") for p in cli_paths)


def test_unknown_generator_refused(tmp_path):
    """An unknown generator is a structured alpha refusal, not a crash."""
    result = forge.run_pipeline(
        PROMPT, dest=_dest(tmp_path), approve=True, generator="teleporter"
    )
    assert not result["ok"]
    alpha = next(s for s in result["stages"] if s["stage"] == "alpha")
    assert not alpha["ok"]
    assert "teleporter" in alpha["error"]


def test_mismatched_generator_refused(tmp_path):
    result = forge.run_pipeline(
        PROMPT, dest=_dest(tmp_path), approve=True, generator="mcp_server"
    )
    assert not result["ok"]
    alpha = next(s for s in result["stages"] if s["stage"] == "alpha")
    assert not alpha["ok"]
    assert "mismatched" in alpha["did_not"][0]


# ---- nexus ----


def test_nexus_explanation_names_choice_and_limits(tmp_path):
    result = forge.run_pipeline(PROMPT, dest=_dest(tmp_path), approve=True)
    nexus = next(s for s in result["stages"] if s["stage"] == "nexus")
    assert nexus["ok"]
    data = nexus["data"]
    assert data["chosen"] == "levi-local"  # on-device headliner, never shares spotlight
    assert isinstance(data["confidence"], float)
    assert data["reasons"]
    assert data["chosen"] in data["explanation"]
    assert any("policy score" in d for d in nexus["did_not"])
    assert any("does not run" in d for d in nexus["did_not"])


def test_nexus_offline_mode_honest_when_nothing_local(tmp_path):
    """Deny-closed: with only a reference provider, offline mode refuses —
    it never leaks the task anywhere."""
    reference = nx.Provider(
        name="someone-elses-model",
        source=nx.SOURCE_REFERENCE,
        kinds=frozenset({"chat", "code", "run", "serve"}),
    )
    result = forge.run_pipeline(
        PROMPT,
        dest=_dest(tmp_path),
        approve=True,
        mode="offline",
        providers=[reference],
    )
    assert not result["ok"]
    nexus = next(s for s in result["stages"] if s["stage"] == "nexus")
    assert not nexus["ok"]
    assert "no eligible provider" in nexus["error"]
    # the reference provider stayed studied, never served
    assert "reference" in nexus["data"]["explanation"]


def test_nexus_unknown_mode_is_loud(tmp_path):
    with pytest.raises(ValueError):
        forge.run_pipeline(PROMPT, dest=_dest(tmp_path), approve=True, mode="ludicrous")


# ---- receipt ----


def test_receipt_contents(tmp_path):
    result = forge.run_pipeline(PROMPT, dest=_dest(tmp_path), approve=True)
    assert result["origin"] == forge.ORIGIN
    assert result["timestamp"]
    assert result["prompt"] == PROMPT
    assert result["blueprint"]["name"]
    assert result["blueprint"]["product_types"]
    assert len(result["limits"]) >= 5
    # refused run also produces a receipt-shaped result
    refused = forge.run_pipeline(PROMPT, dest=_dest(tmp_path, "r"), approve=False)
    assert set(refused) >= {"ok", "origin", "timestamp", "stages", "limits"}
    assert not refused["ok"]


# ---- CLI ----


def test_cli_noninteractive_approve_flag(tmp_path):
    dest = _dest(tmp_path)
    rc = forge.main([PROMPT, "--dest", dest, "--approve", "--mode", "offline"])
    assert rc == 0
    assert os.listdir(dest)


def test_cli_without_approve_needs_interaction_eof(tmp_path, monkeypatch):
    """Interactive path hitting EOF (no prompt, no stdin) stands down."""
    monkeypatch.setattr(
        "builtins.input", lambda *a, **k: (_ for _ in ()).throw(EOFError)
    )
    rc = forge.main(["--dest", _dest(tmp_path)])
    assert rc != 0
