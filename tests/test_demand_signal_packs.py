"""Tests for levi.demand.signal_packs — user and business signal packs.

Law-guard-prove: PK1 audience framing, PK2 schema round-trip, PK3 no
anonymous packs, PK4 determinism, PK5 real signals only, PK6 gate-only
entitlement.
"""

import json

import pytest

from levi.demand import scoring, signal_packs, signal_strength
from levi.demand.signal_packs import (
    PACK_KINDS,
    PACK_SCHEMA_VERSION,
    build_business_pack,
    build_pack,
    build_user_pack,
    entitlement_gate,
    requires_entitlement,
)
from levi.demand.signal_strength import (
    SCHEMA_VERSION,
    advise,
    rank_advisories,
    strength_card,
)


def _factors(base: float):
    return {
        name: (base, f"{name} basis")
        for name in scoring.FACTORS
    }


def _dims(base: float, low_conf_on: str = ""):
    dims = {}
    for name in signal_strength.DIMENSIONS:
        conf = 0.3 if name == low_conf_on else 0.8
        dims[name] = (
            base,
            f"{name} basis text",
            conf,
            f"{name} sensitivity text",
            (f"{name} observed evidence",),
        )
    return dims


def _cards():
    c1 = strength_card(
        "opp-a",
        "Neighborhood thumbnail service",
        _dims(70.0, low_conf_on="defensibility"),
        risks=[("Copycats arrive fast", 65.0, "low barrier basis")],
        actions=[
            ("Ship 5 sample packs", "proves demand fast", "low"),
            ("Price test at $19", "finds the paying tier", "medium"),
            ("Build booking flow", "captures repeat buyers", "high"),
        ],
        watch_conditions=[
            ("a competitor launches", "timing_window drops 20 points"),
        ],
        segment="user",
    )
    c2 = strength_card(
        "opp-b",
        "Local gym lead engine",
        _dims(55.0),
        actions=[("Cold-call 10 gyms", "direct signal", "low")],
        segment="business",
    )
    return [c1, c2]


def _score_cards():
    return [
        scoring.score_card("opp-a", "Neighborhood thumbnail service",
                           _factors(72.0)),
        scoring.score_card("opp-b", "Local gym lead engine",
                           _factors(58.0)),
    ]


def _advisories(cards=None):
    cards = cards or _cards()
    sc = {s.opportunity_id: s for s in _score_cards()}
    return [advise(sc[c.opportunity_id], c) for c in cards]


BUILT_AT = "2026-09-24T13:05:00Z"
REFINER = "chauncey"


# --- PK1: audience framing -----------------------------------------------


def test_user_pack_orders_actions_easiest_first():
    pack = build_user_pack("pk-u1", "Weekly wins", _cards(), _advisories(),
                           BUILT_AT, REFINER)
    assert pack.pack_kind == "user"
    card = pack.cards["opp-a"]
    from levi.demand.signal_packs import _effort_ranked_actions
    efforts = [a.effort for a in _effort_ranked_actions(card)]
    assert efforts == ["low", "medium", "high"]
    report = pack.render_report()
    assert "Your first move (low effort)" in report
    assert "Ship 5 sample packs" in report


def test_user_report_is_plain_language():
    pack = build_user_pack("pk-u2", "Weekly wins", _cards(), _advisories(),
                           BUILT_AT, REFINER)
    report = pack.render_report()
    assert "(for you)" in report
    assert "Honest note:" in report  # low-confidence flagged, not hidden
    assert "Watch for:" in report


def test_business_pack_leads_with_market_framing():
    pack = build_business_pack("pk-b1", "Q4 pipeline", _cards(),
                               _advisories(), BUILT_AT, REFINER)
    assert pack.pack_kind == "business"
    report = pack.render_report()
    assert "MARKET READ" in report
    assert "DEFENSIBILITY / MOAT" in report
    assert "COMPETITION GAP" in report
    assert "RECOMMENDED ACTIONS (analyst-ranked)" in report
    assert "scoring:" in report  # math stays visible


def test_business_pack_keeps_analyst_action_order():
    pack = build_business_pack("pk-b2", "Q4 pipeline", _cards(),
                               _advisories(), BUILT_AT, REFINER)
    card = pack.cards["opp-a"]
    # analyst order is low, medium, high here; use a shuffled card instead
    assert [a.action for a in card.actions] == [
        "Ship 5 sample packs", "Price test at $19", "Build booking flow"]
    report = pack.render_report()
    first = report.index("1. [low effort]")
    second = report.index("2. [medium effort]")
    assert first < second  # analyst rank order preserved, not effort-sorted


def test_pack_opens_strongest_first():
    pack = build_user_pack("pk-u3", "Weekly wins", _cards(), _advisories(),
                           BUILT_AT, REFINER)
    assert pack.opportunity_order[0] == "opp-a"  # higher combined
    assert pack.advisories[0].directive.rank == 1
    assert pack.advisories[1].directive.rank == 2


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        build_pack("pk-x", "alien", "X", _cards(), _advisories(),
                   BUILT_AT, REFINER)


# --- PK2: schema round-trip ----------------------------------------------


def test_round_trip_byte_stable():
    pack = build_business_pack("pk-b3", "Q4 pipeline", _cards(),
                               _advisories(), BUILT_AT, REFINER,
                               notes="refined in grok")
    d1 = pack.to_dict()
    assert d1["pack_schema_version"] == PACK_SCHEMA_VERSION
    assert d1["signal_schema_version"] == SCHEMA_VERSION
    pack2 = signal_packs.SignalPack.from_dict(d1)
    d2 = pack2.to_dict()
    assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)
    assert pack2.render_report() == pack.render_report()


def test_from_dict_rejects_bad_pack_schema():
    pack = build_user_pack("pk-u4", "Weekly wins", _cards(), _advisories(),
                           BUILT_AT, REFINER)
    d = pack.to_dict()
    d["pack_schema_version"] = "999"
    with pytest.raises(ValueError):
        signal_packs.SignalPack.from_dict(d)


def test_from_dict_rejects_unknown_kind():
    pack = build_user_pack("pk-u5", "Weekly wins", _cards(), _advisories(),
                           BUILT_AT, REFINER)
    d = pack.to_dict()
    d["pack_kind"] = "alien"
    with pytest.raises(ValueError):
        signal_packs.SignalPack.from_dict(d)


def test_source_hashes_are_sha256_of_canonical_cards():
    import hashlib
    pack = build_user_pack("pk-u6", "Weekly wins", _cards(), _advisories(),
                           BUILT_AT, REFINER)
    for oid, card in pack.cards.items():
        canon = json.dumps(card.to_dict(), sort_keys=True,
                           separators=(",", ":"))
        assert pack.source_hashes[oid] == hashlib.sha256(
            canon.encode()).hexdigest()


# --- PK3: no anonymous packs ----------------------------------------------


@pytest.mark.parametrize("field", ["pack_id", "built_at", "refined_by"])
def test_required_identity_fields(field):
    kw = dict(pack_id="pk", title="T", cards=_cards(),
              advisories=_advisories(), built_at=BUILT_AT,
              refined_by=REFINER)
    kw[field] = "  "
    with pytest.raises(ValueError):
        build_user_pack(**kw)


def test_empty_pack_rejected():
    with pytest.raises(ValueError):
        build_user_pack("pk-e", "Empty", [], [], BUILT_AT, REFINER)


def test_mismatched_cards_and_advisories_rejected():
    cards = _cards()
    advs = _advisories()[:1]
    with pytest.raises(ValueError):
        build_user_pack("pk-m", "Mismatch", cards, advs, BUILT_AT, REFINER)


# --- PK4: determinism -----------------------------------------------------


def test_deterministic_build():
    kw = dict(pack_id="pk-d", title="T", cards=_cards(),
              advisories=_advisories(), built_at=BUILT_AT,
              refined_by=REFINER)
    p1 = build_business_pack(**kw)
    p2 = build_business_pack(**kw)
    assert (json.dumps(p1.to_dict(), sort_keys=True)
            == json.dumps(p2.to_dict(), sort_keys=True))


# --- PK5: real signals only -----------------------------------------------


def test_report_contains_only_card_content():
    pack = build_user_pack("pk-r", "Weekly wins", _cards(), _advisories(),
                           BUILT_AT, REFINER)
    report = pack.render_report()
    # every rendered action/watch/risk comes from the card
    card = pack.cards["opp-a"]
    for a in card.actions:
        assert a.action in report
    for w in card.watch_conditions:
        assert w.condition in report
    assert "Copycats arrive fast" in report  # top risk rides in plain_summary
    bpack = build_business_pack("pk-r2", "Q4", _cards(), _advisories(),
                                BUILT_AT, REFINER)
    assert "Copycats arrive fast" in bpack.render_report()  # and in business


# --- PK6: entitlement gate -------------------------------------------------


def test_entitlement_gate_is_descriptive_only():
    gate = entitlement_gate("user")
    assert gate["product"] == "demandpulse-signal-pack-user"
    assert "never free" in gate["rule"]
    assert "entitlements.py" in gate["store_module"]
    assert "no charging" in gate["status"]
    with pytest.raises(ValueError):
        entitlement_gate("alien")


def test_every_pack_requires_entitlement():
    pack = build_user_pack("pk-g", "Weekly wins", _cards(), _advisories(),
                           BUILT_AT, REFINER)
    assert requires_entitlement(pack) is True


def test_pack_kinds_are_exactly_user_and_business():
    assert PACK_KINDS == ("user", "business")
