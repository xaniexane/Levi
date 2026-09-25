"""Academy subject-catalog tests — home-scoped, deterministic, no network."""

from __future__ import annotations

import json

import pytest

from levi.academy import subjects
from levi.academy.differentiators import _seal
from levi.academy.session_exercises import EXERCISE_RUNNERS

EXPECTED_IDS = [
    "threat-intel",
    "osint-defense",
    "forensics",
    "malware-triage",
    "traffic-analysis",
    "secure-code-review",
    "se-defense",
    "crypto-literacy",
    "cloud-posture",
    "privacy-engineering",
    "purple-team",
    "incident-report",
    "stakeholder-briefing",
    "levi-canon",
    # Reinforcement wave 2026-09-19: six new blue-team subjects.
    "supply-chain-defense",
    "insider-risk",
    "incident-command",
    "secure-baseline",
    "threat-hunting",
    "recovery-drills",
]


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def test_catalog_shape():
    assert subjects.subject_ids() == EXPECTED_IDS
    assert len({s["id"] for s in subjects.SUBJECTS}) == 20
    for s in subjects.SUBJECTS:
        assert len(s["objectives"]) == 3
        assert len(s["key_questions"]) == 3
        assert s["exercise_type"] in EXERCISE_RUNNERS, s["id"]
        assert s["description"]
    with pytest.raises(KeyError):
        subjects.get_subject("nope")


def test_entries_match_syllabus_day_schema(home):
    for sid, entry in subjects.syllabus_entries():
        assert set(entry.keys()) == {
            "title",
            "objectives",
            "key_questions",
            "exercise_type",
        }, sid


def test_as_track_and_merge_into(home):
    track = subjects.as_track()
    assert track["name"] == subjects.TRACK_NAME
    assert list(track["days"].keys()) == [str(i + 1) for i in range(20)]
    syllabus = {
        "tracks": {"A": {"name": "Existing", "days": {}}},
        "track_names": {"A": "Existing"},
    }
    merged = subjects.merge_into(syllabus)
    assert merged["tracks"]["D"]["name"] == subjects.TRACK_NAME
    assert merged["track_names"]["D"] == subjects.TRACK_NAME
    assert "D" not in syllabus["tracks"]  # original untouched
    with pytest.raises(ValueError):
        subjects.merge_into(merged)  # D already taken


def test_merge_into_real_syllabus_schema(home):
    import pathlib

    path = (
        pathlib.Path.home()
        / "workspace"
        / "levi"
        / "core"
        / "levi"
        / "academy"
        / "syllabus.json"
    )
    if not path.exists():  # pragma: no cover — repo layout guard
        pytest.skip("syllabus.json not found")
    real = json.loads(path.read_text(encoding="utf-8"))
    merged = subjects.merge_into(real)
    assert set(merged["tracks"].keys()) == {"A", "B", "C", "S", "D"}
    # new entries run through the real exercise dispatcher
    from levi.academy.session_exercises import run_exercise

    for sid, entry in subjects.syllabus_entries():
        if sid == "purple-team":
            continue  # authorization-gated; not a plain dispatch
        run_exercise(entry["exercise_type"], entry, "lesson", {"research": "x"})


def test_purple_team_gate(home):
    with pytest.raises(PermissionError):
        subjects.check_purple_authorization("ada", home)
    auth = subjects.authorize_purple_team(
        "ada",
        "systems: own lab; techniques: phishing sim; window: 2026-09-19; abort: on call",
        "Chauncey",
        home=home,
    )
    assert auth["authorized"] is True
    payload = subjects.check_purple_authorization("ada", home)
    assert payload["approver"] == "Chauncey"
    with pytest.raises(ValueError):
        subjects.authorize_purple_team(
            "ada", "scope", "", home=home
        )  # unnamed approver


def test_purple_team_tamper_fails_loud(home):
    subjects.authorize_purple_team("ada", "own lab only", "Chauncey", home=home)
    path = subjects._auth_dir(home) / "ada.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["payload"]["scope"] = "everything, everywhere"  # tamper the payload
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(_seal.SealError):
        subjects.check_purple_authorization("ada", home)


def test_study_plan_wires_methods(home):
    plan = subjects.study_plan("ada", "crypto-literacy", home=home)
    assert plan["subject_id"] == "crypto-literacy"
    assert plan["mixed_with"] == "threat-intel"
    assert len(plan["reviews"]) == 3
    assert all(r["review_in_days"] == 0.0 for r in plan["reviews"])  # unseen skills
    subjects_seen = {s["subject_id"] for s in plan["interleaved_session"]}
    assert subjects_seen == {"crypto-literacy", "threat-intel"}
    assert len(plan["feynman_drills"]) == 3
    assert plan["exercise_type"] == "coverage-map"


def test_study_plan_purple_requires_auth(home):
    with pytest.raises(PermissionError):
        subjects.study_plan("ada", "purple-team", home=home)
    subjects.authorize_purple_team("ada", "own lab", "Chauncey", home=home)
    plan = subjects.study_plan("ada", "purple-team", home=home)
    assert plan["subject_id"] == "purple-team"
