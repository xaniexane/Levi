"""Hermetic tests for levi.friction — capture, honest grouping, promotion.

No network, no real ~/.levi: $LEVI_HOME is redirected to a tmp dir.
"""

import pytest

from levi.friction.log import FrictionLog, stem


@pytest.fixture
def log(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return FrictionLog()


def test_capture_roundtrip(log):
    e = log.capture("deploy keeps asking for the password twice")
    assert e.id.startswith("fr-")
    assert e.note.startswith("deploy")
    assert len(log.entries()) == 1


def test_capture_rejects_empty(log):
    with pytest.raises(ValueError):
        log.capture("   ")


def test_stem_is_honest_and_simple():
    assert stem("running") == "run"
    assert stem("deployments") == "deployment"
    assert stem("logins") == "login"
    assert stem("classes") == "class"  # no false doubling collapse
    assert stem("it") == "it"  # too short to strip


def test_weekly_review_groups_shared_stems(log):
    log.capture("deploy keeps asking for the password twice")
    log.capture("the deployment script hangs on step three")
    log.capture("the office coffee machine is broken")
    review = log.weekly_review(since_days=30)
    themes = {c["theme"]: c for c in review["candidates"]}
    # "deploy"/"deployment" share the stem "deploy"
    assert "deploy" in themes
    assert themes["deploy"]["count"] == 2
    # the coffee note shares nothing -> honestly ungrouped
    assert len(review["ungrouped"]) == 1
    assert "coffee" in review["ungrouped"][0]["note"]


def test_weekly_review_never_forces_groups(log):
    log.capture("the office coffee machine is broken")
    log.capture("my chair squeaks when I lean back")
    log.capture("the hallway light flickers at noon")
    review = log.weekly_review(since_days=30)
    assert review["candidates"] == []
    assert len(review["ungrouped"]) == 3


def test_promote_to_fix(log):
    log.capture("wifi drops every time the microwave runs")
    log.capture("wifi drops during video calls too")
    review = log.weekly_review(since_days=30)
    cand = review["candidates"][0]
    fix = log.promote_to_fix(cand["id"], "move the router off the microwave")
    assert fix["theme"] == cand["theme"]
    assert fix["fix_note"] == "move the router off the microwave"
    fixes = log.fixes()
    assert len(fixes) == 1
    assert fixes[0]["id"] == cand["id"]


def test_promote_requires_fix_note(log):
    log.capture("wifi drops every time the microwave runs")
    log.capture("wifi drops during video calls too")
    cand = log.weekly_review(since_days=30)["candidates"][0]
    with pytest.raises(ValueError):
        log.promote_to_fix(cand["id"], "   ")
    with pytest.raises(ValueError):
        log.promote_to_fix(cand["id"], "")


def test_promote_unknown_and_double(log):
    with pytest.raises(KeyError):
        log.promote_to_fix("fx-nope", "some note")
    log.capture("printer jams on page two")
    log.capture("printer jams on page nine")
    cand = log.weekly_review(since_days=30)["candidates"][0]
    log.promote_to_fix(cand["id"], "replace the feed roller")
    with pytest.raises(ValueError):
        log.promote_to_fix(cand["id"], "do it again")


def test_drop_candidate(log):
    log.capture("printer jams on page two")
    log.capture("printer jams on page nine")
    cand = log.weekly_review(since_days=30)["candidates"][0]
    dropped = log.drop_candidate(cand["id"])
    assert dropped["status"] == "dropped"
    assert log.fixes() == []  # dropping is not fixing


def test_state_survives_reload(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    FrictionLog().capture("the build takes eleven minutes")
    assert len(FrictionLog().entries()) == 1  # fresh instance, same home


def test_cli_smoke(tmp_path, monkeypatch, capsys):
    from levi.friction.__main__ import main

    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    assert main(["capture", "the linter is slow"]) == 0
    assert main(["capture", "the linter eats my cpu"]) == 0
    assert main(["review"]) == 0
    out = capsys.readouterr().out
    assert "lint" in out or "candidate" in out
    assert main(["fixes"]) == 0
    with pytest.raises(SystemExit) as exc:
        main(["capture"])  # argparse usage error, not a crash
    assert exc.value.code == 2
