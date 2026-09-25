"""Tests for revival wave 41: platform economics & honest markets."""

import pytest

from levi.revival import (
    apogee_model,
    app_catalog,
    carrier_billing,
    carrier_micropay,
    honest_search,
    metered_viewdata,
    pipe_mashup,
)


# ---- metered_viewdata (Prestel) ----


def _prestel_gateway():
    gw = metered_viewdata.Gateway(network_cut_rate=0.10)
    gw.register_provider(metered_viewdata.InformationProvider("p1", "NewsCo"))
    gw.register_provider(metered_viewdata.InformationProvider("p2", "WeatherCo"))
    gw.publish_page(metered_viewdata.Page("news", "p1", price_units=50))
    gw.publish_page(metered_viewdata.Page("wx", "p2", price_units=20))
    gw.publish_page(metered_viewdata.Page("free", "p1", price_units=0))
    return gw


def test_metered_session_settles_providers():
    gw = _prestel_gateway()
    session = metered_viewdata.Session("s1", "sub1")
    session.visit(gw.pages["news"], duration_s=30.0)
    session.visit(gw.pages["wx"], duration_s=10.0)
    settlement = gw.settle(session)
    assert settlement.subscriber_charge == 70
    assert settlement.network_cut == 7
    assert sum(settlement.provider_payouts.values()) == 70 - 7
    assert settlement.provider_payouts["p1"] > settlement.provider_payouts["p2"]


def test_metered_free_pages_cost_nothing():
    gw = _prestel_gateway()
    session = metered_viewdata.Session("s2", "sub1")
    session.visit(gw.pages["free"], duration_s=120.0)
    settlement = gw.settle(session)
    assert settlement.subscriber_charge == 0
    assert settlement.network_cut == 0
    assert settlement.provider_payouts == {}


def test_metered_provider_ledger_accumulates():
    gw = _prestel_gateway()
    for i in range(3):
        session = metered_viewdata.Session(f"s{i}", "sub1")
        session.visit(gw.pages["news"], duration_s=5.0)
        gw.settle(session)
    ledger = gw.provider_ledger("p1")
    assert ledger["total_units"] == 3 * 45  # 50 minus 10% cut
    assert ledger["settlements"] == 3


def test_metered_unregistered_page_rejected():
    gw = _prestel_gateway()
    session = metered_viewdata.Session("s9", "sub1")
    session.visit(metered_viewdata.Page("ghost", "p1", 10))
    with pytest.raises(ValueError):
        gw.settle(session)


# ---- carrier_billing (BTX) ----


def _btx_carrier():
    carrier = carrier_billing.Carrier(revenue_share=0.30)
    carrier.register_subscriber(
        carrier_billing.Subscriber("sub1", carrier_billing.Terminal("t1"))
    )
    carrier.register_provider(carrier_billing.ContentProvider("cp1", "Info AG"))
    return carrier


def test_carrier_bills_per_received_page():
    carrier = _btx_carrier()
    carrier.deliver_page("page1", 100, "cp1", "sub1")
    carrier.deliver_page("page2", 50, "cp1", "sub1")
    stmt = carrier.statement("sub1")
    assert stmt["total_units"] == 150
    assert stmt["terminal_id"] == "t1"
    assert len(stmt["items"]) == 2


def test_carrier_splits_revenue_with_provider():
    carrier = _btx_carrier()
    carrier.deliver_page("page1", 100, "cp1", "sub1")
    assert carrier.carrier_ledger_units == 30
    paid = carrier.settle_provider("cp1")
    assert paid == 70
    assert carrier.provider_ledger["cp1"] == 0


def test_carrier_terminal_monopoly_enforced():
    carrier = _btx_carrier()
    with pytest.raises(ValueError):
        carrier.register_subscriber(
            carrier_billing.Subscriber("sub2", carrier_billing.Terminal("t1"))
        )


# ---- carrier_micropay (i-mode) ----


def _imode():
    net = carrier_micropay.CarrierMicropay(packet_rate_units=2, carrier_take=0.09)
    net.register_device(carrier_micropay.Device("d1"))
    net.register_site(carrier_micropay.ContentSite("news", "News Site"))
    return net


def test_micropay_packet_billing():
    net = _imode()
    charged = net.meter_packets("d1", 500)
    assert charged == 1000
    assert net.transport_revenue_units == 1000


def test_micropay_small_carrier_take():
    net = _imode()
    net.buy("d1", "news", 100)
    # Site keeps ~91 of a 100-unit purchase.
    assert net.site_balances["news"] == 91
    paid = net.settle_site("news")
    assert paid == 91
    assert net.site_balances["news"] == 0


def test_micropay_combined_monthly_bill():
    net = _imode()
    net.meter_packets("d1", 10)  # 20 units transport
    net.buy("d1", "news", 100)
    bill = net.monthly_bill("d1")
    assert bill == {
        "device_id": "d1",
        "transport_units": 20,
        "content_units": 100,
        "total_units": 120,
    }


# ---- app_catalog (Danger) ----


def test_catalog_curates_before_listing():
    catalog = app_catalog.Catalog()
    app = app_catalog.App("a1", "Chat", "Dev1", "A chat app", "1.0")
    catalog.submit(app)
    assert catalog.browse() == []  # not listed until approved
    with pytest.raises(ValueError):
        catalog.listing("a1")
    catalog.approve("a1", note="looks good")
    assert [a.app_id for a in catalog.browse()] == ["a1"]


def test_catalog_reject_with_note():
    catalog = app_catalog.Catalog()
    catalog.submit(app_catalog.App("a2", "Spam", "DevX", "junk", "1.0"))
    catalog.reject("a2", note="spam")
    assert catalog.browse() == []
    assert catalog.pending() == []


def test_catalog_search_ranks_name_first():
    catalog = app_catalog.Catalog()
    catalog.submit(app_catalog.App("a1", "Weather", "D1", "forecasts and radar", "1.0"))
    catalog.submit(
        app_catalog.App("a2", "Radar Pro", "D2", "weather radar tool", "1.0")
    )
    catalog.approve("a1")
    catalog.approve("a2")
    results = catalog.search("weather")
    assert [a.app_id for a in results] == ["a1", "a2"]


def test_catalog_version_update_reenters_review():
    catalog = app_catalog.Catalog()
    catalog.submit(app_catalog.App("a1", "Chat", "D1", "chat", "1.0"))
    catalog.approve("a1")
    catalog.submit(app_catalog.App("a1", "Chat", "D1", "chat v2", "2.0"))
    # New version is pending again, so the old approved listing is gone
    # from browse until re-approved.
    assert catalog.browse() == []
    catalog.approve("a1")
    assert catalog.listing("a1").version == "2.0"


# ---- apogee_model ----


def _series():
    series = apogee_model.Series("DoomClone")
    series.add_episode(apogee_model.Episode(1, "Knee-Deep", free=True))
    series.add_episode(apogee_model.Episode(2, "The Shores", price_units=1500))
    series.add_episode(apogee_model.Episode(3, "Inferno", price_units=1500))
    return series


def test_apogee_free_slice_is_episode_one():
    series = _series()
    free = series.free_slice()
    assert free.number == 1 and free.free


def test_apogee_fans_redistribute_free_slice():
    series = _series()
    series.redistribute("fan-alice")
    series.redistribute("fan-bob")
    series.redistribute("fan-alice")
    funnel = series.funnel()
    assert funnel["redistributions"] == 3
    assert funnel["distributors"] == 2


def test_apogee_paid_episodes_not_redistributable():
    series = _series()
    with pytest.raises(ValueError):
        series.redistribute("fan-alice", episode_number=2)


def test_apogee_mail_orders_track_revenue():
    series = _series()
    series.order(2, "buyer1")
    series.order(3, "buyer2")
    funnel = series.funnel()
    assert funnel["orders"] == 2
    assert funnel["revenue_units"] == 3000
    assert funnel["orders_per_episode"] == {2: 1, 3: 1}


# ---- pipe_mashup (Yahoo Pipes) ----


def _mashup_pipe():
    pipe = pipe_mashup.Pipe("tech news")
    pipe.register_feed(
        "hn",
        [
            {"title": "Rust 2.0", "score": 400, "link": "http://x/1"},
            {"title": "Cats", "score": 900, "link": "http://x/2"},
            {"title": "Python 4", "score": 100, "link": "http://x/3"},
        ],
    )
    fetch = pipe.add(pipe_mashup.Fetch("hn"))
    filt = pipe.add(
        pipe_mashup.Filter(
            lambda r: "python" in r["title"].lower() or "rust" in r["title"].lower()
        ),
        inputs=[fetch],
    )
    sort = pipe.add(
        pipe_mashup.Sort(key=lambda r: r["score"], reverse=True),
        inputs=[filt],
    )
    pipe.add(pipe_mashup.Truncate(1), inputs=[sort])
    return pipe


def test_pipe_runs_modules_in_order():
    result = _mashup_pipe().run()
    assert len(result) == 1
    assert result[0]["title"] == "Rust 2.0"  # highest score of filtered


def test_pipe_union_merges_feeds():
    pipe = pipe_mashup.Pipe("merged")
    pipe.register_feed("a", [{"title": "one"}])
    pipe.register_feed("b", [{"title": "two"}, {"title": "three"}])
    fa = pipe.add(pipe_mashup.Fetch("a"))
    fb = pipe.add(pipe_mashup.Fetch("b"))
    pipe.add(pipe_mashup.Union(), inputs=[fa, fb])
    assert len(pipe.run()) == 3


def test_pipe_fork_remix_independent():
    pipe = _mashup_pipe()
    remix = pipe.fork("remix")
    remix.modules[-1] = pipe_mashup.Truncate(2)
    assert len(remix.run()) == 2
    assert len(pipe.run()) == 1  # original untouched


def test_pipe_emit_json_and_rss():
    pipe = _mashup_pipe()
    records = pipe.run()
    as_json = pipe.emit_json(records)
    assert '"Rust 2.0"' in as_json
    rss = pipe.emit_rss(records)
    assert rss.startswith('<?xml version="1.0"?>')
    assert "<title>Rust 2.0</title>" in rss


# ---- honest_search (AltaVista) ----


def _search_index():
    index = honest_search.Index()
    index.add(
        honest_search.Document(
            "d1",
            "Python tutorial",
            "Learn python programming with this python tutorial.",
        )
    )
    index.add(
        honest_search.Document("d2", "Rust manual", "Systems programming in rust.")
    )
    index.add(
        honest_search.Document(
            "d3", "Python vs Rust", "Comparing python and rust performance."
        )
    )
    return index


def test_search_boolean_and():
    index = _search_index()
    hits = index.search("python AND rust")
    assert [h.doc_id for h in hits] == ["d3"]


def test_search_boolean_or_not():
    index = _search_index()
    hits = index.search("python OR rust")
    assert {h.doc_id for h in hits} == {"d1", "d2", "d3"}
    hits = index.search("python NOT rust")
    assert [h.doc_id for h in hits] == ["d1"]


def test_search_phrase_and_parens():
    index = _search_index()
    hits = index.search('"python tutorial"')
    assert [h.doc_id for h in hits] == ["d1"]
    hits = index.search("(python OR rust) AND manual")
    assert [h.doc_id for h in hits] == ["d2"]


def test_search_ranking_is_deterministic_and_impersonal():
    index = _search_index()
    first = [h.doc_id for h in index.search("python")]
    second = [h.doc_id for h in index.search("python")]
    assert first == second
    # d1 mentions python most (title + body), so it ranks first.
    assert first[0] == "d1"
    # Term-frequency scoring exposed honestly on each hit.
    assert all(h.score > 0 for h in index.search("python"))


def test_search_empty_query_returns_nothing():
    index = _search_index()
    assert index.search("   ") == []
