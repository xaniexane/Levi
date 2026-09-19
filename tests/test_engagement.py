"""Tests for the engagement layer: surveys, campaigns, voting — AI+SI.

All home-scoped: LEVI_ENGAGEMENT_DIR + LEVI_INBOX_DIR point at tmp dirs;
DemandPulse is mocked so no real hub file is touched.
"""

import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from levi.engagement import (
    BALLOTS,
    SURVEYS,
    EngagementStore,
    get_ballot,
    get_survey,
)
from levi.engagement.cli import chat_handle, cmd_engage, _render_results
from levi.engagement.prefs import Prefs, get_prefs, save_prefs
from levi.engagement.store import EngagementStore as Store2
from levi.engagement.surveys import take_survey
from levi.engagement.voting import VERBS, cast_favorite, cast_proposal


@pytest.fixture()
def home(tmp_path, monkeypatch):
    eng = tmp_path / "eng"
    inbox = tmp_path / "inbox"
    monkeypatch.setenv("LEVI_ENGAGEMENT_DIR", str(eng))
    monkeypatch.setenv("LEVI_INBOX_DIR", str(inbox))
    return tmp_path


@pytest.fixture()
def store(home):
    return EngagementStore()


@pytest.fixture()
def opted_in(home):
    save_prefs(Prefs(opted_in=True, frequency="weekly"))
    return get_prefs()


@pytest.fixture()
def no_hub():
    with patch("levi.demand.pulse.DemandPulse") as mock:
        yield mock


def _cmd(home, *argv):
    ns = type("A", (), {})()
    ns.engage_cmd = argv[0]
    rest = argv[1:]
    # map positional args onto the attributes cmd_engage reads
    for key in ("survey_id", "ballot_id", "campaign_id", "level", "verb"):
        setattr(ns, key, None)
    ns.json = None
    ns.pick = None
    ns.text = []
    if ns.engage_cmd in ("take", "answer"):
        ns.survey_id = rest[0]
        if ns.engage_cmd == "answer":
            ns.json = rest[1]
    elif ns.engage_cmd in ("vote",):
        ns.ballot_id = rest[0]
        if "--pick" in rest:
            ns.pick = rest[rest.index("--pick") + 1]
    elif ns.engage_cmd in ("campaign", "dismiss"):
        ns.campaign_id = rest[0]
    elif ns.engage_cmd == "frequency":
        ns.level = rest[0]
    elif ns.engage_cmd == "propose":
        ns.verb = rest[0]
        ns.text = rest[1:]
    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_engage(ns)
    return buf.getvalue()


# -- prefs ---------------------------------------------------------------

def test_prefs_default_not_opted_in(home):
    p = get_prefs()
    assert p.opted_in is False
    assert p.can_prompt_today() is False


def test_prefs_roundtrip(home):
    assert save_prefs(Prefs(opted_in=True, frequency="daily")) is True
    p = get_prefs()
    assert p.opted_in is True and p.frequency == "daily"


def test_prefs_bad_frequency_falls_back(home):
    p = Prefs(opted_in=True, frequency="nonsense")
    assert p.frequency == "weekly"


def test_frequency_off_never_prompts(home):
    p = Prefs(opted_in=True, frequency="off")
    assert p.can_prompt_today() is False


# -- starter content: AI+SI coverage --------------------------------------

def test_surveys_cover_both_tracks():
    tracks = {s.track for s in SURVEYS.values()}
    assert "ai" in tracks and "si" in tracks and "both" in tracks
    assert len(SURVEYS) >= 5


def test_ballots_tagged_ai_si():
    tracks = {b.track for b in BALLOTS.values()}
    assert "ai" in tracks and "si" in tracks
    for b in BALLOTS.values():
        assert b.track in ("ai", "si", "both")
        assert b.kind in ("favorites", "proposals")


# -- opt-in gating ----------------------------------------------------------

def test_take_requires_opt_in(home):
    out = _cmd(home, "take", "welcome-walk")
    assert "not opted in" in out


def test_vote_requires_opt_in(home):
    out = _cmd(home, "vote", "mind-meld")
    assert "not opted in" in out


def test_propose_requires_opt_in(home):
    out = _cmd(home, "propose", "add", "something")
    assert "not opted in" in out


# -- surveys ----------------------------------------------------------------

def test_take_survey_skips_and_invalid(home, store, opted_in):
    survey = get_survey("welcome-walk")
    result = take_survey(survey, {"mission": "1", "tone": "bogus!!", "drop": "", "checkin": "99"}, store)
    assert result["answers"]["mission"] == "hunt work / find me gigs"
    assert result["answers"]["tone"] == ""  # invalid → skip, never hard error
    assert result["answers"]["drop"] == ""
    assert "welcome-walk" in store.completed_surveys()


def test_free_text_never_quoted_in_tallies(home, store, opted_in, no_hub):
    survey = get_survey("welcome-walk")
    take_survey(survey, {"superpower": "read my diary, levi"}, store)
    tallies = store.aggregate_tallies()
    flat = json.dumps(tallies)
    assert "read my diary" not in flat
    assert tallies["welcome-walk.superpower"]["text-given"] == 1


def test_hub_signal_per_track_no_free_text(home, store, opted_in, no_hub):
    take_survey(get_survey("si-deep-dive"), {"memory": "1", "proactive": "2", "oracle": "3", "brain": "secret plans"}, store)
    take_survey(get_survey("agent-crew"), {"crew": "1", "leash": "2", "shift": "3", "dream": ""}, store)
    texts = [c.args[0] for c in no_hub.return_value.scan_seed.call_args_list]
    joined = " ".join(texts)
    assert "[si]" in joined and "[ai]" in joined
    assert "secret plans" not in joined


# -- voting -----------------------------------------------------------------

def test_favorite_vote_and_recast(home, store, opted_in, no_hub):
    ballot = get_ballot("mind-meld")
    r1 = cast_favorite(ballot, "1", store)
    assert r1["ok"] is True
    assert store.current_vote("mind-meld") == ballot.options[0]
    r2 = cast_favorite(ballot, ballot.options[2], store)
    assert r2["ok"] is True
    assert store.current_vote("mind-meld") == ballot.options[2]
    tallies = store.vote_tallies()["mind-meld"]
    assert list(tallies) == [ballot.options[2]]  # recast replaces


def test_favorite_vote_bad_pick(home, store, opted_in):
    ballot = get_ballot("mind-meld")
    r = cast_favorite(ballot, "not an option", store)
    assert r["ok"] is False
    assert store.current_vote("mind-meld") == ""


def test_ballot_hub_signal_tagged_per_track(home, store, opted_in, no_hub):
    cast_favorite(get_ballot("agent-draft"), "1", store)
    texts = [c.args[0] for c in no_hub.return_value.scan_seed.call_args_list]
    assert any("[ai]" in t and "agent-draft" in t for t in texts)


def test_votes_store_no_identity(home, store, opted_in, no_hub):
    cast_favorite(get_ballot("mind-meld"), "1", store)
    lines = (Path(os.environ["LEVI_ENGAGEMENT_DIR"]) / "votes.jsonl").read_text()
    for line in lines.splitlines():
        ev = json.loads(line)
        assert set(ev) <= {"ts", "type", "ballot_id", "kind", "choice"}


def test_proposal_creates_one_open_request(home, store, opted_in, no_hub):
    from levi.inbox.requests import RequestBox

    r = cast_proposal("add", "a dark-mode toggle", store)
    assert r["ok"] is True and r["weight"] == 1
    r2 = cast_proposal("add", "a dark-mode toggle", store)
    assert r2["weight"] == 2 and r2["request_id"] == r["request_id"]
    reqs = RequestBox().list()
    assert len(reqs) == 1
    assert reqs[0].status == "open"  # weighted input, never auto-build
    assert reqs[0].text.startswith("[votes]")


def test_proposal_bad_verb(home, store, opted_in):
    r = cast_proposal("yeet", "something", store)
    assert r["ok"] is False


def test_proposals_ranked_by_weight(home, store, opted_in, no_hub):
    cast_proposal("add", "thing one", store)
    cast_proposal("remove", "thing two", store)
    cast_proposal("remove", "thing two", store)
    props = store.proposals()
    assert props[0]["proposal"].startswith("remove:") and props[0]["weight"] == 2


# -- campaigns ---------------------------------------------------------------

def test_campaign_dismiss_never_reshows(home, store, opted_in):
    store.record_campaign("drop-01-tour", seen=2, completed=False)
    assert "drop-01-tour" in store.dismissed_campaigns()


def test_cli_dismiss(home, opted_in):
    out = _cmd(home, "dismiss", "drop-01-tour")
    assert "won't surface again" in out


# -- results / companion ------------------------------------------------------

def test_results_grouped_per_track(home, store, opted_in, no_hub):
    cast_favorite(get_ballot("agent-draft"), "1", store)
    out = _render_results(store)
    assert "[ai]" in out and "[si]" in out and "[both]" in out


def test_chat_handle_opt_in_flow(home):
    out = chat_handle("/engage")
    assert "opt-in" in out
    out = chat_handle("/engage opt-in")
    assert "opted in" in out
    out = chat_handle("/engage")
    assert "hall-of-fame" in out


def test_chat_handle_results(home, opted_in):
    out = chat_handle("/engage results")
    assert "no votes yet" in out


# -- cli smoke -----------------------------------------------------------------

def test_cli_ballots_lists_tracks(home, opted_in):
    out = _cmd(home, "ballots")
    assert "[ai" in out and "[si" in out


def test_cli_vote_pick(home, opted_in, no_hub):
    out = _cmd(home, "vote", "hall-of-fame", "--pick", "1")
    assert "vote counted" in out
