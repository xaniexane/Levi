"""Hermetic tests for declared-intent rendezvous (Dodgeball revival).

Laws under proof:
1. Declaration, not surveillance — the store holds only what was typed.
2. Opt-in joining — attendance derives ONLY from explicit RSVPs.
3. Expiry is a wall — RSVP/withdraw on an expired intent is refused.
4. Nothing is thrown away — cancelled intents stay listed.
5. Deny-closed — unknown ids and bad times raise.
"""

import os
import stat

import pytest

from levi.rendezvous import RendezvousError
from levi.rendezvous.model import IntentStore

FUTURE_START = "2030-06-01T18:00:00+00:00"
FUTURE_END = "2030-06-01T20:00:00+00:00"
PAST_START = "2020-06-01T18:00:00+00:00"
PAST_END = "2020-06-01T20:00:00+00:00"


@pytest.fixture()
def store(tmp_path):
    return IntentStore(home=tmp_path)


def test_declare_round_trip(store):
    i = store.declare("amy", "Ginger Man", FUTURE_START, FUTURE_END,
                      note="wednesdays", invites=["bo"])
    assert i.who == "amy" and i.where == "Ginger Man"
    assert i.status() == "open"
    assert i.attending() == []
    assert store.get(i.id).id == i.id


def test_invites_are_not_attendance(store):
    # Law 2: being invited is not attending; nobody is added by anyone else.
    i = store.declare("amy", "Ginger Man", FUTURE_START, FUTURE_END,
                      invites=["bo", "cy"])
    assert i.attending() == []
    assert "bo" not in i.rsvps and "cy" not in i.rsvps


def test_rsvp_is_opt_in(store):
    i = store.declare("amy", "Ginger Man", FUTURE_START, FUTURE_END)
    store.rsvp(i.id, "bo")
    assert store.get(i.id).attending() == ["bo"]


def test_rsvp_is_idempotent(store):
    i = store.declare("amy", "Ginger Man", FUTURE_START, FUTURE_END)
    store.rsvp(i.id, "bo")
    store.rsvp(i.id, "bo")
    assert store.get(i.id).attending() == ["bo"]


def test_expired_intent_refuses_rsvp(store):
    # Law 3: expiry is a wall.
    i = store.declare("amy", "Ginger Man", PAST_START, PAST_END)
    assert i.status() == "expired"
    with pytest.raises(RendezvousError):
        store.rsvp(i.id, "bo")
    with pytest.raises(RendezvousError):
        store.withdraw(i.id, "bo")


def test_cancelled_intent_refuses_rsvp_but_stays_listed(store):
    # Law 4: cancelled is recorded, never deleted.
    i = store.declare("amy", "Ginger Man", FUTURE_START, FUTURE_END)
    store.cancel(i.id)
    assert store.get(i.id).status() == "cancelled"
    with pytest.raises(RendezvousError):
        store.rsvp(i.id, "bo")
    assert i.id in [x.id for x in store.list_all()]


def test_withdraw_removes_rsvp_keeps_intent(store):
    i = store.declare("amy", "Ginger Man", FUTURE_START, FUTURE_END)
    store.rsvp(i.id, "bo")
    store.withdraw(i.id, "bo")
    assert store.get(i.id).attending() == []
    assert store.get(i.id).status() == "open"


def test_withdraw_without_rsvp_refused(store):
    i = store.declare("amy", "Ginger Man", FUTURE_START, FUTURE_END)
    with pytest.raises(RendezvousError):
        store.withdraw(i.id, "bo")


def test_unknown_intent_refused(store):
    # Law 5: deny-closed.
    with pytest.raises(RendezvousError):
        store.rsvp("nope", "bo")
    with pytest.raises(RendezvousError):
        store.withdraw("nope", "bo")
    with pytest.raises(RendezvousError):
        store.cancel("nope")
    with pytest.raises(RendezvousError):
        store.get("nope")


def test_bad_times_refused(store):
    with pytest.raises(RendezvousError):
        store.declare("amy", "x", FUTURE_END, FUTURE_START)  # ends before starts
    with pytest.raises(RendezvousError):
        store.declare("amy", "x", "not-a-time", FUTURE_END)
    with pytest.raises(RendezvousError):
        store.declare("", "x", FUTURE_START, FUTURE_END)
    with pytest.raises(RendezvousError):
        store.declare("amy", "", FUTURE_START, FUTURE_END)


def test_list_active_hides_expired_and_cancelled(store):
    open_i = store.declare("amy", "A", FUTURE_START, FUTURE_END)
    store.declare("amy", "B", PAST_START, PAST_END)
    store.cancel(open_i.id)
    assert store.list_active() == []
    assert len(store.list_all()) == 2


def test_owner_only_permissions(store, tmp_path):
    store.declare("amy", "A", FUTURE_START, FUTURE_END)
    d = tmp_path / "rendezvous"
    f = d / "intents.json"
    assert stat.S_IMODE(os.stat(d).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(f).st_mode) == 0o600


def test_no_network_surface():
    # Law 1: declaration, not surveillance — the model must not import
    # any networking machinery.
    import levi.rendezvous.model as m

    src = open(m.__file__, encoding="utf-8").read()
    for banned in ("socket", "urllib", "http.client", "requests"):
        assert "import %s" % banned not in src
