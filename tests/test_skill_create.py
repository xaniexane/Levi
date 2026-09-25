"""Hermetic tests for `levi skill create` (core/levi/skill/creator.py).

All HOME writes go to an isolated tmp HOME via monkeypatched $HOME.
No network, no daemons, no real user HOME writes. Synthetic fixtures only.
"""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

import pytest

from levi.skill.creator import (
    SkillPlan,
    SkillRefusal,
    derive_name,
    guess_category,
    guess_risk,
    install,
    list_user_skills,
    parse_frontmatter,
    plan_skill,
    render_preview,
    render_skill_md,
    safety_check,
    slugify,
)
from levi.skill.registry import SkillRegistry, SkillRisk


@pytest.fixture
def iso_home(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("LEVI_SKILLS_DIR", raising=False)
    return home


# ── slugify edge cases ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("remind me to water plants", "remind-me-to-water-plants"),
        ("Hello, World!", "hello-world"),
        ("  spaced   out  ", "spaced-out"),
        ("Café au lait", "cafe-au-lait"),
        ("---", "unnamed-skill"),
        ("", "unnamed-skill"),
        ("!!! ???", "unnamed-skill"),
        ("UPPER_snake.Mixed", "upper-snake-mixed"),
        ("a" * 200, "a" * 48),
        ("--leading-and-trailing--", "leading-and-trailing"),
        ('it\'s "quoted"', "it-s-quoted"),
    ],
)
def test_slugify_edge_cases(raw, expected):
    assert slugify(raw) == expected


def test_derive_name_strips_lead_in():
    assert derive_name("a skill that reminds me to water plants") == (
        "Reminds me to water plants"
    )
    assert derive_name("Create me a skill to track workouts") == "Track workouts"
    assert derive_name("") == "Unnamed Skill"


# ── safety gate: defensive-only refusals ──────────────────────────────


@pytest.mark.parametrize(
    "description,concern",
    [
        ("a skill that stores my API keys for later", "credential handling"),
        ("collect user passwords and save them to a file", "credential handling"),
        ("remember my bank login credentials", "credential handling"),
        ("send my documents to an external server nightly", "exfiltration"),
        ("upload all my files to a remote server", "exfiltration"),
        ("exfiltrate the database to a third party", "exfiltration"),
        ("hack into wifi networks and crack passwords", "offensive security"),
        ("brute force logins with a payload", "offensive security"),
        ("run a reverse shell pentest with metasploit", "offensive security"),
        ("bypass captcha to scrape accounts", "offensive security"),
    ],
)
def test_unsafe_descriptions_refused(description, concern):
    planned = plan_skill(description)
    assert isinstance(planned, SkillRefusal)
    assert concern in planned.reason
    assert "Declined" in planned.reason


def test_safe_description_plans_fine():
    planned = plan_skill("remind me to water the plants every morning")
    assert isinstance(planned, SkillPlan)
    assert planned.id == "remind-me-to-water-the-plants-every-morning"[:48].rstrip("-")


def test_safety_check_ok_path():
    ok, reason = safety_check("a skill that summarizes my notes")
    assert ok and reason == ""


# ── heuristics are honestly labeled ───────────────────────────────────


def test_category_heuristic_labeled():
    category, basis = guess_category("remember my favorite quotes")
    assert category == "memory"
    assert "heuristic" in basis


def test_risk_heuristic_labeled_and_capped():
    risk, basis = guess_risk("delete old files I no longer need")
    assert risk == SkillRisk.MODERATE
    assert "heuristic" in basis
    # Heuristics never assign HIGH/CRITICAL.
    risk2, _ = guess_risk("wipe the entire disk and destroy everything")
    assert risk2 <= SkillRisk.MODERATE


def test_default_guesses_labeled():
    category, basis = guess_category("do the thing with the stuff")
    assert category == "general" and "heuristic" in basis
    risk, rbasis = guess_risk("do the thing with the stuff")
    assert risk == SkillRisk.LOW and "heuristic" in rbasis


# ── frontmatter validity ──────────────────────────────────────────────


def test_generated_frontmatter_has_required_keys():
    planned = plan_skill("summarize my daily notes")
    assert isinstance(planned, SkillPlan)
    fm = parse_frontmatter(render_skill_md(planned))
    for key in ("name", "description", "version", "category", "risk"):
        assert key in fm and fm[key], f"missing frontmatter key: {key}"
    assert fm["name"] == planned.id
    assert fm["risk"] in ("INFO", "LOW", "MODERATE", "HIGH", "CRITICAL")


def test_frontmatter_survives_hostile_description():
    planned = plan_skill('a skill for "quoted" notes\nwith newlines')
    assert isinstance(planned, SkillPlan)
    fm = parse_frontmatter(render_skill_md(planned))
    assert fm["name"] == planned.id
    assert "\n" not in fm["description"]


def test_preview_names_all_files():
    planned = plan_skill("track my reading list")
    assert isinstance(planned, SkillPlan)
    preview = render_preview(planned)
    files = planned.files()
    assert set(files) == {
        "SKILL.md",
        "handler.py",
        f"test_{planned.id.replace('-', '_')}.py",
    }
    for fname in files:
        assert fname in preview
    assert "heuristic" in preview.lower()


def test_generated_python_compiles():
    planned = plan_skill("track my reading list")
    assert isinstance(planned, SkillPlan)
    for fname, content in planned.files().items():
        if fname.endswith(".py"):
            compile(content, fname, "exec")


# ── preview-before-install: nothing written without confirmation ──────


def test_install_refuses_without_confirmation(iso_home):
    planned = plan_skill("water the plants reminder")
    assert isinstance(planned, SkillPlan)
    result = install(planned, confirmed=False, input_fn=lambda _: "no")
    assert result["ok"] is False
    assert "nothing was written" in result["reason"].lower()
    assert not (iso_home / ".levi" / "skills").exists()


def test_install_confirmed_writes_files(iso_home):
    planned = plan_skill("water the plants reminder")
    assert isinstance(planned, SkillPlan)
    result = install(planned, confirmed=True)
    assert result["ok"] is True
    target = Path(result["dir"])
    assert target == iso_home / ".levi" / "skills" / planned.id
    for fname in planned.files():
        assert (target / fname).is_file()
    fm = parse_frontmatter((target / "SKILL.md").read_text(encoding="utf-8"))
    assert fm["name"] == planned.id


def test_install_typed_yes_installs(iso_home):
    planned = plan_skill("evening stretch routine")
    assert isinstance(planned, SkillPlan)
    result = install(planned, input_fn=lambda _: "  YES  ")
    assert result["ok"] is True
    assert (iso_home / ".levi" / "skills" / planned.id / "SKILL.md").is_file()


def test_install_refuses_overwrite(iso_home):
    planned = plan_skill("evening stretch routine")
    assert isinstance(planned, SkillPlan)
    assert install(planned, confirmed=True)["ok"] is True
    before = (iso_home / ".levi" / "skills" / planned.id / "SKILL.md").read_text()
    second = install(planned, confirmed=True)
    assert second["ok"] is False
    assert "already exists" in second["reason"]
    after = (iso_home / ".levi" / "skills" / planned.id / "SKILL.md").read_text()
    assert before == after  # untouched


# ── registry integration: user skills show up ─────────────────────────


def test_user_skill_appears_in_registry(iso_home):
    planned = plan_skill("summarize my daily notes")
    assert isinstance(planned, SkillPlan)
    assert install(planned, confirmed=True)["ok"] is True

    reg = SkillRegistry()
    skill = reg.get(planned.id)
    assert skill is not None
    assert "user-created" in skill.tags
    assert skill.category == planned.category
    assert skill.requires_confirmation == (planned.risk >= SkillRisk.MODERATE)
    # Stub handler reports honestly, never executes user code.
    out = reg.invoke(planned.id, {})
    assert planned.id in out and "stub" in out.lower()


def test_list_user_skills_skips_garbage(iso_home):
    from levi.skill.creator import skills_dir

    root = skills_dir()
    root.mkdir(parents=True)
    (root / "empty-dir").mkdir()  # no SKILL.md -> skipped
    (root / "not-a-dir.md").write_text("---\nname: x\n---\n")  # not a dir -> skipped
    (root / "bad..name").mkdir()  # fails id charset -> skipped
    (root / "bad..name" / "SKILL.md").write_text("---\nname: x\n---\n")
    assert list_user_skills() == []


def test_frontmatter_less_playbook_registers_with_defaults(iso_home):
    from levi.skill.creator import skills_dir

    root = skills_dir()
    (root / "plain-notes").mkdir(parents=True)
    (root / "plain-notes" / "SKILL.md").write_text("Just prose, no frontmatter.")
    skills = list_user_skills()
    assert [s.id for s in skills] == ["plain-notes"]
    assert skills[0].description == "User-created skill."
    assert skills[0].category == "general"


def test_cmd_skill_list_shows_user_skill(iso_home, capsys):
    from levi.skill.creator import cmd_skill

    planned = plan_skill("track my reading list")
    assert isinstance(planned, SkillPlan)
    assert install(planned, confirmed=True)["ok"] is True

    cmd_skill(Namespace(skill_action="list"))
    out = capsys.readouterr().out
    assert planned.id in out
    assert "user" in out


def test_cmd_skill_create_refusal_exits(iso_home, capsys):
    from levi.skill.creator import cmd_skill

    with pytest.raises(SystemExit) as exc:
        cmd_skill(
            Namespace(
                skill_action="create",
                description=["store", "my", "passwords"],
                confirm=True,
            )
        )
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "Declined" in err
    # Nothing written on refusal.
    assert not (iso_home / ".levi" / "skills").exists()


def test_cmd_skill_create_confirmed_installs(iso_home, capsys):
    from levi.skill.creator import cmd_skill

    cmd_skill(
        Namespace(
            skill_action="create",
            description=["remind me to stretch hourly"],
            confirm=True,
        )
    )
    out = capsys.readouterr().out
    assert "Installed:" in out
    planned_id = slugify("remind me to stretch hourly")
    assert (iso_home / ".levi" / "skills" / planned_id / "SKILL.md").is_file()


def test_cli_surface_registers(iso_home, monkeypatch, capsys):
    # Drive the real CLI end-to-end: `skill` must parse and dispatch.
    from levi.cli.main import main

    monkeypatch.setattr(sys, "argv", ["levi", "skill", "list"])
    main()
    out = capsys.readouterr().out
    assert "status" in out  # builtin skills listed

    monkeypatch.setattr(
        sys, "argv", ["levi", "skill", "create", "remind me to stretch", "--confirm"]
    )
    main()
    out = capsys.readouterr().out
    assert "Installed:" in out
    skill_id = slugify("remind me to stretch")
    assert (iso_home / ".levi" / "skills" / skill_id / "SKILL.md").is_file()

    # The new user skill now shows in `levi skill list`.
    monkeypatch.setattr(sys, "argv", ["levi", "skill", "list"])
    main()
    out = capsys.readouterr().out
    assert skill_id in out and "user" in out
