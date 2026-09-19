"""Tests for Omega's new generators: automation-gen + skill-gen.

- Generated automation dicts validate against the REAL Minion schema
  (``levi.automation.minions.Minion``); invalid specs are refused.
- Skill scaffolds: three files, honest "scaffold, not a skill" labeling,
  generated skill.py compiles, invalid names refused.
- materialize: overwrite refusal + receipt shape + approve gate.
- SI/ai separation: si/ never imports ai/; bridges carry the bridge label.

Hermetic: no network, no HOME writes (tmp_path only).
"""

import ast
import json
import re
import sys

import pytest

from levi.automation.minions import Minion
from levi.revival.omega import automation_gen, materialize, skill_gen
from levi.revival.omega import skill_gen as sg_mod
from levi.revival.omega.ai import automation_bridge, skill_bridge
from levi.revival.omega.si import automation_core, skill_core


def _spec(**over):
    minions = [
        {
            "id": "morning-weather-01",
            "category": "Productivity",
            "trigger": "Time 06:30",
            "example_rite": "Read the forecast aloud.",
            "notes": "Keep it short.",
        }
    ]
    spec = {"name": "morning-rites", "minions": minions}
    spec.update(over)
    return spec


# ---- automation-gen: Minion schema fidelity ----


def test_generated_dicts_validate_against_real_bot_schema():
    dicts = automation_gen.generate_minions(_spec())
    assert len(dicts) == 1
    minion = Minion(**dicts[0])  # TypeError if the schema drifted
    assert minion.id == "morning-weather-01"
    assert minion.origin == "omega-automation-gen"
    assert minion.bridge == "local"  # LEVI-native: no outside bridge
    assert minion.to_dict() == dicts[0]


def test_generated_dicts_carry_defaults():
    (d,) = automation_gen.generate_minions(_spec())
    assert d["condition"] == "Always"
    assert d["incomplete"] is False
    assert d["signature_id"] == ""


def test_multiple_bots():
    spec = _spec()
    spec["minions"] = spec["minions"] + [
        {"id": "morning-news-01", "category": "Productivity", "trigger": "Time 07:00"}
    ]
    dicts = automation_gen.generate_minions(spec)
    assert [d["id"] for d in dicts] == ["morning-weather-01", "morning-news-01"]


def test_refuse_spec_missing_trigger():
    spec = _spec()
    del spec["minions"][0]["trigger"]
    with pytest.raises(ValueError, match="trigger"):
        automation_gen.generate_minions(spec)


def test_refuse_spec_unknown_field():
    spec = _spec()
    spec["minions"][0]["teleporter"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        automation_gen.generate_minions(spec)


def test_refuse_duplicate_ids():
    spec = _spec()
    spec["minions"].append(
        {"id": "morning-weather-01", "category": "X", "trigger": "Y"}
    )
    with pytest.raises(ValueError, match="duplicate id"):
        automation_gen.generate_minions(spec)


def test_refuse_bad_id_shape():
    spec = _spec()
    spec["minions"][0]["id"] = "Not A Slug!"
    with pytest.raises(ValueError, match="slug"):
        automation_gen.generate_minions(spec)


def test_refuse_non_dict_and_empty():
    with pytest.raises(ValueError):
        automation_gen.generate_minions("nope")
    with pytest.raises(ValueError):
        automation_gen.generate_minions({"name": "x", "minions": []})


def test_validate_spec_lists_problems():
    assert automation_core.validate_spec(_spec()) == []
    problems = automation_core.validate_spec({"minions": [{"id": "a"}]})
    assert problems and any("category" in p for p in problems)


def test_spec_from_json_roundtrip():
    spec = automation_gen.spec_from_json(json.dumps(_spec()))
    assert automation_gen.generate_minions(spec)
    with pytest.raises(ValueError):
        automation_gen.spec_from_json("{not json")


# ---- skill-gen: honest scaffolds ----


def test_scaffold_three_files():
    result = skill_gen.scaffold_skill("weather-digest", "summarize the weather")
    assert result["ok"] and not result["errors"]
    assert set(result["files"]) == {
        "weather-digest/SKILL.md",
        "weather-digest/skill.py",
        "weather-digest/tests/test_weather_digest.py",
    }


def test_scaffold_labeled_not_a_skill_everywhere():
    result = skill_gen.scaffold_skill("weather-digest", "summarize the weather")
    for path, content in result["files"].items():
        assert "SCAFFOLD" in content, path
    assert "NOT A WORKING SKILL" in result["files"]["weather-digest/SKILL.md"]
    assert "scaffold: true" in result["files"]["weather-digest/SKILL.md"]


def test_scaffold_skill_py_compiles_and_reports_scaffold():
    result = skill_gen.scaffold_skill("weather-digest", "summarize the weather")
    src = result["files"]["weather-digest/skill.py"]
    namespace: dict = {}
    exec(compile(src, "skill.py", "exec"), namespace)
    out = namespace["run_skill"]("probe")
    assert out["ok"] is False and out["scaffold"] is True


def test_scaffold_test_skeleton_parses():
    result = skill_gen.scaffold_skill("weather-digest", "summarize the weather")
    ast.parse(result["files"]["weather-digest/tests/test_weather_digest.py"])


def test_refuse_bad_skill_name():
    result = skill_gen.scaffold_skill("Not A Slug!", "x")
    assert result["ok"] is False and result["files"] == {}
    assert any("slug" in e for e in result["errors"])


def test_refuse_empty_capability():
    result = skill_gen.scaffold_skill("ok-name", "   ")
    assert result["ok"] is False


def test_scaffold_banner_constant_shared():
    assert sg_mod.SCAFFOLD_BANNER == skill_core.SCAFFOLD_BANNER
    assert "NOT A WORKING SKILL" in sg_mod.SCAFFOLD_BANNER


# ---- materialize: overwrite refusal + receipt ----


def test_materialize_refuses_overwrite_by_default(tmp_path):
    target = tmp_path / "keep.py"
    target.write_text("original\n")
    receipt = materialize.write(
        {"keep.py": "new content\n"}, str(tmp_path), approve=True
    )
    assert receipt["verified"] is True
    assert target.read_text() == "original\n"  # untouched
    assert any(
        s["path"] == "keep.py" and "already exists" in s["reason"]
        for s in receipt["skipped"]
    )


def test_materialize_receipt_shape(tmp_path):
    receipt = materialize.write({"a.txt": "hi\n"}, str(tmp_path), approve=True)
    assert set(receipt) >= {
        "dest",
        "written",
        "skipped",
        "verified",
        "mismatches",
        "atomic",
        "timestamp",
    }
    assert receipt["atomic"] is True
    assert receipt["written"][0]["path"] == "a.txt"


def test_materialize_requires_approval(tmp_path):
    with pytest.raises(PermissionError):
        materialize.write({"a.txt": "hi\n"}, str(tmp_path))


def test_materialize_atomic_leaves_no_torn_file(tmp_path):
    receipt = materialize.write(
        {"deep/nested/f.txt": "x" * 1000}, str(tmp_path), approve=True
    )
    assert receipt["verified"] is True
    leftovers = list(tmp_path.rglob(".levi-materialize-*.tmp"))
    assert leftovers == []
    assert (tmp_path / "deep" / "nested" / "f.txt").read_text() == "x" * 1000


# ---- SI/ai separation + labels ----


def _si_modules():
    return [
        "levi.revival.omega.si.automation_core",
        "levi.revival.omega.si.skill_core",
        "levi.alpha.si.deliberation",
        "levi.alpha.reason",
    ]


def test_si_never_imports_ai():
    before = set(sys.modules)
    for name in _si_modules():
        __import__(name)
    new_ai = [
        m
        for m in set(sys.modules) - before
        if m.startswith("levi") and re.search(r"(^|\.)ai(\.|$)", m)
    ]
    assert new_ai == [], f"importing si pulled in ai modules: {new_ai}"


def test_si_source_has_no_ai_imports():
    import pathlib

    repo = pathlib.Path(__file__).resolve().parents[1]
    roots = [
        repo / "core/levi/revival/omega/si",
        repo / "core/levi/alpha/si",
        repo / "core/levi/alpha/reason.py",
    ]
    pattern = re.compile(r"^\s*(from|import)\s+[\w.]*\bai\b", re.M)
    for root in roots:
        targets = [root] if root.is_file() else list(root.glob("*.py"))
        assert targets, f"no sources under {root}"
        for f in targets:
            assert not pattern.search(f.read_text()), f"{f} imports ai"


def test_bridge_labels_present():
    for bridge in (automation_bridge, skill_bridge):
        assert "conventional-protocol interface" in bridge.BRIDGE_LABEL
        assert "the SI core is authoritative" in bridge.BRIDGE_LABEL
        assert "this bridge claims nothing" in bridge.BRIDGE_LABEL
        assert bridge.tool_schema()["bridge_label"] == bridge.BRIDGE_LABEL


def test_bridge_delegates_to_si_core():
    minions = automation_bridge.run(_spec())
    assert Minion(**minions[0]).id == "morning-weather-01"
    result = skill_bridge.run("bridge-skill", "a capability")
    assert result["ok"] and "bridge-skill/SKILL.md" in result["files"]
    with pytest.raises(ValueError):
        automation_bridge.run({"minions": []})


def test_bridge_chat_completion_shapes():
    req = automation_bridge.chat_completion_request(_spec())
    assert req["messages"][0]["role"] == "system"
    resp = skill_bridge.chat_completion_response(skill_bridge.run("x-skill", "cap"))
    assert resp["object"] == "chat.completion"
    assert resp["choices"][0]["message"]["role"] == "assistant"
    assert "bridge-omega-skill" in resp["id"]


# ---- omega CLI smoke ----


def test_omega_cli_gen_skill(capsys):
    import argparse

    from levi.revival.omega.cli import cmd_omega, register_omega_parser

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_omega_parser(sub)
    args = parser.parse_args(
        ["omega", "gen-skill", "--name", "cli-smoke", "--capability", "smoke"]
    )
    assert args.omega_cmd == "gen-skill"
    assert cmd_omega(args) == 0
    assert "SCAFFOLD" in capsys.readouterr().out


def test_omega_cli_gen_automation(capsys):
    import argparse

    from levi.revival.omega.cli import cmd_omega

    spec_json = json.dumps(_spec())
    args = argparse.Namespace(omega_cmd="gen-automation", spec=spec_json)
    assert cmd_omega(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["minions"][0]["id"] == "morning-weather-01"


def test_omega_cli_materialize_dry_run(tmp_path, capsys):
    import argparse

    from levi.revival.omega.cli import cmd_omega

    args = argparse.Namespace(
        omega_cmd="materialize",
        plan=json.dumps({"dry.txt": "hello\n"}),
        dest=str(tmp_path),
        live=False,
        overwrite=False,
    )
    assert cmd_omega(args) == 0
    out = capsys.readouterr().out
    assert "dry.txt" in out and "Dry run only" in out
    assert (tmp_path / "dry.txt").exists() is False  # nothing landed


def test_omega_cli_materialize_live(tmp_path, capsys):
    import argparse

    from levi.revival.omega.cli import cmd_omega

    args = argparse.Namespace(
        omega_cmd="materialize",
        plan=json.dumps({"live.txt": "hello\n"}),
        dest=str(tmp_path),
        live=True,
        overwrite=False,
    )
    assert cmd_omega(args) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["verified"] is True
    assert (tmp_path / "live.txt").read_text() == "hello\n"
