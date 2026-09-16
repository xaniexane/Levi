"""Hermetic tests for levi.craft.guild — the indenture ladder."""

import os

import pytest

from levi.craft import guild


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return str(tmp_path)


def test_indenture_opens_ladder(home):
    rec = guild.indenture("weaving", "apprentice-ada", "master-mara")
    assert rec["event"] == "indenture"
    assert guild.rank_of("weaving", "apprentice-ada") == "apprentice"


def test_indenture_refuses_self_mastery(home):
    with pytest.raises(guild.GuildError, match="own master"):
        guild.indenture("weaving", "ada", "ada")


def test_indenture_refuses_double(home):
    guild.indenture("weaving", "ada", "mara")
    with pytest.raises(guild.GuildError, match="already indentured"):
        guild.indenture("weaving", "ada", "other")


def test_practice_requires_indenture(home):
    with pytest.raises(guild.GuildError, match="no indenture"):
        guild.log_practice("weaving", "stranger", "sweep the floor")


def _journeyman_ready(home, skill="weaving", name="ada"):
    guild.indenture(skill, name, "mara")
    for i in range(guild.PRACTICE_REQUIRED):
        guild.log_practice(skill, name, "task-%d" % i)
    return name


def test_promote_needs_practice(home):
    guild.indenture("weaving", "ada", "mara")
    guild.log_practice("weaving", "ada", "one task")
    with pytest.raises(guild.GuildError, match="practice tasks logged"):
        guild.promote("weaving", "ada", mentor="mara", signoff="fine")


def test_promote_needs_signoff(home):
    _journeyman_ready(home)
    with pytest.raises(guild.GuildError, match="sign-off"):
        guild.promote("weaving", "ada", mentor="", signoff="")


def test_promote_to_journeyman(home):
    _journeyman_ready(home)
    rec = guild.promote(
        "weaving", "ada", mentor="mara", signoff="steady hands, honest seams"
    )
    assert rec["to"] == "journeyman"
    assert guild.rank_of("weaving", "ada") == "journeyman"


def test_promote_only_apprentices(home):
    _journeyman_ready(home)
    guild.promote("weaving", "ada", mentor="mara", signoff="ok")
    with pytest.raises(guild.GuildError, match="not an apprentice"):
        guild.promote("weaving", "ada", mentor="mara", signoff="again")


def test_failed_practice_does_not_count(home):
    guild.indenture("weaving", "ada", "mara")
    for _ in range(guild.PRACTICE_REQUIRED):
        guild.log_practice("weaving", "ada", "task", result="failed")
    assert guild.practice_count("weaving", "ada") == 0


def test_masterpiece_flow(home):
    _journeyman_ready(home)
    guild.promote("weaving", "ada", mentor="mara", signoff="ready")
    sub = guild.submit_masterpiece(
        "weaving", "ada", "/tmp/cloth.txt", "a seamless cloak"
    )
    assert sub["verdict"] == "pending"
    # one judge is not peer judgment
    with pytest.raises(guild.GuildError, match="two peer judges"):
        guild.judge_masterpiece("weaving", "ada", "accepted", ["mara"])
    rec = guild.judge_masterpiece(
        "weaving", "ada", "accepted", ["mara", "io"], artifact_sha256="ab" * 32
    )
    assert rec["verdict"] == "accepted"
    assert guild.rank_of("weaving", "ada") == "master"
    # the guild keeps the piece
    kept = guild.guildhall("weaving")
    assert len(kept) == 1
    assert kept[0]["master"] == "ada"
    assert kept[0]["artifact_sha256"] == "ab" * 32


def test_rejected_masterpiece_stays_journeyman(home):
    _journeyman_ready(home)
    guild.promote("weaving", "ada", mentor="mara", signoff="ready")
    guild.submit_masterpiece("weaving", "ada", "/tmp/cloth.txt", "a cloak")
    guild.judge_masterpiece("weaving", "ada", "rejected", ["mara", "io"])
    assert guild.rank_of("weaving", "ada") == "journeyman"
    assert guild.guildhall() == []


def test_masterpiece_needs_journeyman(home):
    guild.indenture("weaving", "ada", "mara")
    with pytest.raises(guild.GuildError, match="not a journeyman"):
        guild.submit_masterpiece("weaving", "ada", "/tmp/x", "too soon")


def test_permissions_map():
    assert guild.permissions("apprentice") == {
        "read": True,
        "write": False,
        "autonomous": False,
    }
    assert guild.permissions("journeyman")["write"] is True
    assert guild.permissions("journeyman")["autonomous"] is False
    assert guild.permissions("master")["autonomous"] is True
    with pytest.raises(guild.GuildError):
        guild.permissions("archmage")


def test_status_filters_by_skill(home):
    guild.indenture("weaving", "ada", "mara")
    guild.indenture("smithing", "bob", "mara")
    assert len(guild.status("weaving")) == 1
    assert len(guild.status()) == 2


def test_register_lives_under_levi_home(home):
    guild.indenture("weaving", "ada", "mara")
    assert os.path.isfile(os.path.join(home, "craft", "guild.jsonl"))
