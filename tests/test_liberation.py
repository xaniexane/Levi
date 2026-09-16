"""Tests for the Liberation Ledger (core/levi/liberation/).

Hermetic: every test points the ledger at tmp_path, never ~/.levi.
"""

import pytest

from levi.liberation.ledger import (
    KNOWN_HOSTAGE_PROFILES,
    LedgerError,
    LiberationLedger,
    ServiceProfile,
    hostage_score,
    score_components,
)


def _ledger(tmp_path):
    return LiberationLedger(home=tmp_path / "liberation")


def _slackish():
    return ServiceProfile(
        name="Slacklike",
        category="team chat",
        retention_limit_days=90,
        deletes_on_expiry=True,
        export_available=True,
        export_formats=("JSON",),
        export_roundtrip=False,
        api_available=True,
        api_toll="fair",
        history_of_enclosure=True,
    )


# -- scoring -------------------------------------------------------------------


def test_score_components_are_transparent():
    comps = score_components(_slackish())
    names = [c[0] for c in comps]
    assert names == ["retention", "export", "graph", "api", "enclosure"]
    for name, pts, max_pts, reason in comps:
        assert 0 <= pts <= max_pts
        assert reason and reason.strip(), name  # every component argues its case


def test_retention_deleter_scores_worst_on_retention():
    pts = dict((n, p) for n, p, _, _ in score_components(_slackish()))
    assert pts["retention"] == 25  # limit + destruction


def test_no_limit_no_retention_points():
    p = ServiceProfile(
        name="Keeper",
        export_available=True,
        export_roundtrip=True,
        export_formats=("JSON",),
        graph_portable=True,
        inferences_disclosed=True,
        api_available=True,
        api_toll="none",
    )
    pts = dict((n, p_) for n, p_, _, _ in score_components(p))
    assert pts["retention"] == 0
    assert pts["export"] == 0
    assert pts["graph"] == 0
    assert pts["api"] == 0
    assert pts["enclosure"] == 0


def test_no_export_is_max_export_friction():
    p = ServiceProfile(name="Vault")
    pts = dict((n, p_) for n, p_, _, _ in score_components(p))
    assert pts["export"] == 25


def test_no_api_blocks_programmatic_exit():
    p = ServiceProfile(name="Vault")
    pts = dict((n, p_) for n, p_, _, _ in score_components(p))
    assert pts["api"] == 10


def test_prohibitive_toll_scores_worse_than_no_api():
    toll = ServiceProfile(name="T", api_available=True, api_toll="prohibitive")
    none_ = ServiceProfile(name="N")
    t = dict((n, p) for n, p, _, _ in score_components(toll))["api"]
    n = dict((n, p) for n, p, _, _ in score_components(none_))["api"]
    assert t == 15 > n


def test_hostage_score_shape_and_verdict_bands():
    low = hostage_score(
        ServiceProfile(
            name="Local",
            export_available=True,
            export_roundtrip=True,
            export_formats=("JSON",),
            graph_portable=True,
            inferences_disclosed=True,
            api_available=True,
            api_toll="none",
        )
    )
    assert low["total"] == 0
    assert low["verdict"] == "free citizen"
    high = hostage_score(_slackish())
    assert high["total"] == 25 + 12 + 20 + 5 + 15
    assert high["verdict"] == "maximum security"
    assert high["max"] == 100


# -- validation (deny-closed) ---------------------------------------------------


def test_empty_name_refused():
    with pytest.raises(ValueError):
        ServiceProfile(name="  ")


def test_bad_toll_refused():
    with pytest.raises(ValueError):
        ServiceProfile(name="X", api_toll="extortionate")


def test_bad_retention_refused():
    with pytest.raises(ValueError):
        ServiceProfile(name="X", retention_limit_days=0)


# -- ledger CRUD -----------------------------------------------------------------


def test_add_get_list_remove_round_trip(tmp_path):
    led = _ledger(tmp_path)
    led.add_service(_slackish())
    assert led.get_service("slacklike").name == "Slacklike"
    assert led.get_service("SLACKLIKE").category == "team chat"  # case-insensitive
    assert [s.name for s in led.list_services()] == ["Slacklike"]
    led.remove_service("Slacklike")
    with pytest.raises(LedgerError):
        led.get_service("Slacklike")


def test_unknown_service_is_deny_closed(tmp_path):
    led = _ledger(tmp_path)
    with pytest.raises(LedgerError):
        led.get_service("Nobody")
    with pytest.raises(LedgerError):
        led.remove_service("Nobody")
    with pytest.raises(LedgerError):
        led.score("Nobody")


def test_persistence_across_instances(tmp_path):
    home = tmp_path / "liberation"
    _ledger(tmp_path).add_service(_slackish())
    again = LiberationLedger(home=home)
    assert again.get_service("Slacklike").deletes_on_expiry is True


def test_seed_loads_four_research_profiles_idempotently(tmp_path):
    led = _ledger(tmp_path)
    added = led.seed_known()
    assert len(added) == 4
    assert {p.name for p in KNOWN_HOSTAGE_PROFILES} == set(added)
    assert led.seed_known() == []  # second run adds nothing
    scores = {s: led.score(s)["total"] for s in added}
    # the deleter outranks the toll-keeper outranks the theater
    assert scores["Slack"] > scores["Reddit"] > scores["Google Takeout"]


def test_seed_profiles_label_their_analysis(tmp_path):
    led = _ledger(tmp_path)
    led.seed_known()
    for s in led.list_services():
        assert "esearch" in s.notes or "analysis" in s.notes


# -- liberation tasks --------------------------------------------------------------


def test_task_lifecycle_with_receipt(tmp_path):
    led = _ledger(tmp_path)
    led.add_service(_slackish())
    task = led.add_task("Slacklike", "export", notes="grab JSON dump")
    assert task["id"].startswith("lib-")
    assert task["status"] == "open"
    assert [t["id"] for t in led.list_tasks(status="open")] == [task["id"]]
    done = led.complete_task(task["id"], receipt_notes="dump verified, 41MB")
    assert done["status"] == "done"
    assert done["receipt"]["notes"] == "dump verified, 41MB"
    assert "completed_at" in done["receipt"]
    assert led.list_tasks(status="open") == []


def test_task_for_unknown_service_refused(tmp_path):
    led = _ledger(tmp_path)
    with pytest.raises(LedgerError):
        led.add_task("Nobody", "export")


def test_bad_task_kind_refused(tmp_path):
    led = _ledger(tmp_path)
    led.add_service(_slackish())
    with pytest.raises(LedgerError):
        led.add_task("Slacklike", "ransom")


def test_double_complete_refused(tmp_path):
    led = _ledger(tmp_path)
    led.add_service(_slackish())
    task = led.add_task("Slacklike", "delete")
    led.complete_task(task["id"])
    with pytest.raises(LedgerError):
        led.complete_task(task["id"])


def test_task_ids_are_sequential(tmp_path):
    led = _ledger(tmp_path)
    led.add_service(_slackish())
    a = led.add_task("Slacklike", "export")
    b = led.add_task("Slacklike", "verify")
    assert a["id"] == "lib-0001"
    assert b["id"] == "lib-0002"


# -- report --------------------------------------------------------------------------


def test_report_ranks_worst_first(tmp_path):
    led = _ledger(tmp_path)
    led.seed_known()
    rep = led.report()
    totals = [s["total"] for s in rep["services"]]
    assert totals == sorted(totals, reverse=True)
    assert rep["worst"] == "Slack"
    assert rep["open_task_count"] == 0


def test_report_counts_open_tasks(tmp_path):
    led = _ledger(tmp_path)
    led.seed_known()
    led.add_task("Slack", "export")
    led.add_task("Reddit", "migrate")
    rep = led.report()
    assert rep["open_task_count"] == 2
