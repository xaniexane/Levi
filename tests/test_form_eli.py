"""eli form tests: the intelligence-layer router.

Proving bar: registration is fail-closed, routing is deterministic and
returns decisions as DATA (handlers never invoked by ELI), dry runs record
nothing, unregistered engines fail closed, and the SER-13 duty refuses to
invent states when the canon tables are unseated.
"""

from levi.eli import FORM_NAME, ELIRouter


def _router():
    r = ELIRouter()
    r.register_engine("echo", lambda t: "echoed")
    r.register_engine("uniforge", lambda t: "forged")
    return r


def test_register_fail_closed():
    r = ELIRouter()
    bad_name = r.register_engine("", lambda t: t)
    assert bad_name["status"] == "rejected"
    bad_handler = r.register_engine("echo", "not-callable")
    assert bad_handler["status"] == "rejected"
    ok = r.register_engine("echo", lambda t: t)
    assert ok["status"] == "registered"


def test_route_is_deterministic_and_never_executes():
    r = _router()
    calls = []

    def spy(task):
        calls.append(task)
        return "ran"

    r.register_engine("omega", spy)
    r1 = r.route("please repair the broken build")
    r2 = r.route("please repair the broken build")
    assert r1["engine"] == "uniforge" == r2["engine"]
    assert calls == []  # ELI never invokes handlers; decisions are data
    assert callable(r1["handler"])


def test_route_matched_but_unregistered_engine_fails_closed():
    r = ELIRouter()  # no engines registered at all
    receipt = r.route("build me a webpage")
    assert receipt["status"] == "unrouted"
    assert "not registered" in receipt["reason"]
    assert receipt["engine"] == "alpha"


def test_route_unmatched_and_hostile_tasks_unrouted():
    r = _router()
    assert r.route("flibbertigibbet wobble")["status"] == "unrouted"
    for bad in ("", "   ", 42, None, ["build"]):
        receipt = r.route(bad)
        assert receipt["status"] == "unrouted", bad
        assert "data" in receipt["reason"]


def test_dry_run_purity():
    r = _router()
    receipt = r.route("repair the build", dry_run=True)
    assert receipt["status"] == "routed"
    assert receipt["dry_run"] is True
    assert r.history() == []  # nothing recorded on a dry run
    r.route("repair the build")
    assert len(r.history()) == 1


def test_route_logic_state_honest_when_unseated(monkeypatch):
    from levi.cybrus import qid

    monkeypatch.setattr(qid, "PHASE_NAMES", [])
    monkeypatch.setattr(qid, "STATE_NAMES", [])
    r = ELIRouter()
    out = r.route_logic_state("retry the failed deploy")
    assert out["status"] == "undecided"
    assert out["state"] is None
    assert "refusing to invent" in out["reason"]


def test_route_logic_state_decided_when_seated():
    from levi.ser18 import seat

    seat()
    r = ELIRouter()
    out = r.route_logic_state("retry the deploy")
    assert out["status"] == "decided"
    assert out["state"] == "Rebirth"
    out2 = r.route_logic_state("just a normal task")
    assert out2["state"] == "Forward"
