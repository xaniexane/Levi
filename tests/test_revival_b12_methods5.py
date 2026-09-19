"""Tests for LEVI revival batch B12 — signals & games.

Covers: codebook, prowords, quipu, kriegsspiel, randgame.
>=3 meaningful tests per module.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import pytest

from levi.revival import codebook, prowords, quipu, kriegsspiel, randgame


# ---------------------------------------------------------------------------
# codebook
# ---------------------------------------------------------------------------


def _synced_pair():
    alice = codebook.CodebookParty("alice", codebook.DEFAULT_CODEBOOK)
    bob = codebook.CodebookParty("bob", codebook.DEFAULT_CODEBOOK)
    assert alice.sync_with(bob)
    return alice, bob


def test_codebook_refuses_unsynced_encode_and_decode():
    alice = codebook.CodebookParty("alice", codebook.DEFAULT_CODEBOOK)
    drifted = codebook.DEFAULT_CODEBOOK.derived("8", [("Z9", "new phrase here")])
    bob = codebook.CodebookParty("bob", drifted)
    assert not alice.sync_with(bob)  # fingerprints differ
    with pytest.raises(codebook.UnsyncedCodebookError):
        alice.encode("arrival delayed", bob)
    with pytest.raises(codebook.UnsyncedCodebookError):
        bob.decode("A1", alice)


def test_codebook_roundtrip_after_sync():
    alice, bob = _synced_pair()
    token = alice.encode("arrival delayed", bob)
    assert token == "A1"
    assert bob.decode(token, alice) == "arrival delayed"


def test_codebook_semaphore_requires_sync_and_acks_each_hop():
    alice = codebook.CodebookParty("alice", codebook.DEFAULT_CODEBOOK)
    bob = codebook.CodebookParty("bob", codebook.DEFAULT_CODEBOOK)
    drifted = codebook.DEFAULT_CODEBOOK.derived("8", [("Z9", "x")])
    carol = codebook.CodebookParty("carol", drifted)
    # Unsynced semaphore session refuses to transmit.
    with pytest.raises(codebook.UnsyncedCodebookError):
        codebook.SemaphoreSession(alice).transmit(
            "all clear", codebook.SemaphoreSession(carol)
        )
    # Synced: two hops, both ACKed, phrase resolved.
    sess_a = codebook.SemaphoreSession(alice)
    sess_b = codebook.SemaphoreSession(bob)
    resolved = sess_a.transmit("urgent: respond immediately", sess_b)
    assert resolved == "urgent: respond immediately"
    assert sess_b.ledger.acknowledged
    hops = [e["hop"] for e in sess_b.ledger.entries]
    assert hops == ["page", "entry"]  # flow control: page ACK before entry


def test_codebook_semaphore_nak_aborts():
    alice, bob = _synced_pair()
    codebook.SemaphoreSession(alice)  # sender side unused in the NAK path
    sess_b = codebook.SemaphoreSession(bob)
    # Bogus page is NAKed; nothing resolves.
    assert sess_b.ack_page_signal(999) == codebook.SemaphoreSession.PAGE_NAK
    ack, phrase = sess_b.ack_entry_signal(0)
    assert ack == codebook.SemaphoreSession.PAGE_NAK
    assert phrase is None


# ---------------------------------------------------------------------------
# prowords
# ---------------------------------------------------------------------------


def test_prowords_query_transform():
    stmt = prowords.parse("LVA")
    q = stmt.as_query()
    assert q.is_query and q.render() == "LVA?"
    assert "query" in q.meaning
    assert not stmt.is_query


def test_prowords_typed_acks_are_distinct_and_close_noncritical():
    station = prowords.ProwordStation("s1")
    ex = station.send("LVE")
    word = station.receive_ack(ex, prowords.AckType.WILL_COMPLY)
    assert word == "WILCO"
    assert word != prowords.ACK_PROWORDS[prowords.AckType.RECEIVED]
    assert ex.settled  # non-critical closes on ack
    assert station.open_loops == []


def test_prowords_critical_requires_readback():
    station = prowords.ProwordStation("s1")
    ex = station.send("LVF", critical=True)
    station.receive_ack(ex, prowords.AckType.RECEIVED)
    assert not ex.settled  # ack alone does not close critical traffic
    assert station.open_loops  # open loop reported
    verdict = station.receive_readback(ex, "LVF")
    assert verdict == "CORRECT"
    assert ex.settled


def test_prowords_wrong_readback_gets_corrected_not_accepted():
    station = prowords.ProwordStation("s1")
    ex = station.send("LVJ", critical=True)
    station.receive_ack(ex, prowords.AckType.UNDERSTOOD)
    verdict = station.receive_readback(ex, "LVA")  # wrong repeat
    assert verdict == "WRONG"
    assert not ex.settled
    assert ex.corrections == 1
    correction = ex.correct()
    assert "LVJ" in correction
    # Receiver repeats correctly this time; loop closes.
    assert station.receive_readback(ex, "LVJ") == "CORRECT"
    assert ex.settled


def test_prowords_unknown_code_rejected():
    with pytest.raises(prowords.UnknownCodeError):
        prowords.parse("ZZZ")


# ---------------------------------------------------------------------------
# quipu
# ---------------------------------------------------------------------------


def test_quipu_number_roundtrip():
    for n in (0, 7, 42, 132, 2026, 100000):
        assert quipu.decode_number(quipu.encode_number(n)) == n


def test_quipu_rolls_up_hierarchy():
    q = quipu.Quipu()
    d1 = quipu.Cord("d1", "goldenrod", quipu.CordLevel.DAILY)
    for k in quipu.encode_number(132):
        d1.knots.append(k)
    d2 = quipu.Cord("d2", "goldenrod", quipu.CordLevel.DAILY)
    for k in quipu.encode_number(98):
        d2.knots.append(k)
    week = quipu.Cord("week", "crimson", quipu.CordLevel.WEEKLY)
    week.tie_child(d1).tie_child(d2)
    q.add(week)
    rolled = q.roll_up()
    assert rolled["week"] == 230  # 132 + 98, aggregated upward
    assert week.rolled_value == 230
    # Leaf knots are never rewritten by roll-up.
    assert d1.own_value == 132 and d2.own_value == 98


def test_quipu_three_levels_and_level_totals():
    q = quipu.Quipu()
    days = []
    for i, n in enumerate((10, 20, 30)):
        d = quipu.Cord(f"d{i}", "goldenrod", quipu.CordLevel.DAILY)
        for k in quipu.encode_number(n):
            d.knots.append(k)
        days.append(d)
    week = quipu.Cord("week", "crimson", quipu.CordLevel.WEEKLY)
    for d in days:
        week.tie_child(d)
    month = quipu.Cord("month", "indigo", quipu.CordLevel.MONTHLY)
    month.tie_child(week)
    q.add(month)
    q.roll_up()
    assert month.rolled_value == 60
    totals = q.level_totals()
    assert totals["DAILY"] == 60 and totals["WEEKLY"] == 60 and totals["MONTHLY"] == 60


def test_quipu_rejects_wrong_level_tie():
    parent = quipu.Cord("m", "indigo", quipu.CordLevel.MONTHLY)
    daily = quipu.Cord("d", "goldenrod", quipu.CordLevel.DAILY)
    with pytest.raises(ValueError):
        parent.tie_child(daily)  # must be exactly one level down


# ---------------------------------------------------------------------------
# kriegsspiel
# ---------------------------------------------------------------------------


def _skirmish(seed=7):
    m = kriegsspiel.Map(6, 6)
    m.add_unit(kriegsspiel.Unit("red-1", "red", 3, (0, 0)))
    m.add_unit(kriegsspiel.Unit("red-2", "red", 2, (0, 5)))
    m.add_unit(kriegsspiel.Unit("blue-1", "blue", 3, (5, 0)))
    m.add_unit(kriegsspiel.Unit("blue-2", "blue", 2, (5, 5)))
    return m, kriegsspiel.Umpire(m, seed=seed)


def test_kriegsspiel_keeps_enemy_positions_hidden():
    m, ump = _skirmish()
    ump.resolve_turn(
        {
            "red": [kriegsspiel.Order("red-1", kriegsspiel.OrderKind.MOVE, (2, 2))],
            "blue": [kriegsspiel.Order("blue-1", kriegsspiel.OrderKind.MOVE, (3, 3))],
        }
    )
    view = ump.view_for("red")
    # Own units show true positions...
    assert {u["unit_id"] for u in view["own_units"]} == {"red-1", "red-2"}
    # ...but no true enemy position ever appears in a player view.
    for s in view["spotted_enemies"]:
        assert "position" not in s


def test_kriegsspiel_spotting_only_in_range():
    m, ump = _skirmish()
    ump.resolve_turn({"red": [], "blue": []})  # nobody moves; far apart
    assert ump.view_for("red")["spotted_enemies"] == []
    # March red-1 adjacent to blue-1: spotting must fire.
    ump.resolve_turn(
        {
            "red": [kriegsspiel.Order("red-1", kriegsspiel.OrderKind.MOVE, (4, 0))],
            "blue": [],
        }
    )
    seen = {s["unit_id"] for s in ump.view_for("red")["spotted_enemies"]}
    assert "blue-1" in seen


def test_kriegsspiel_combat_uses_table_and_dice_seed():
    m = kriegsspiel.Map(4, 4)
    m.add_unit(kriegsspiel.Unit("red-1", "red", 3, (1, 1)))
    m.add_unit(kriegsspiel.Unit("blue-1", "blue", 1, (1, 2)))  # adjacent
    ump = kriegsspiel.Umpire(m, seed=42)
    adj = ump.resolve_turn({"red": [], "blue": []})
    assert len(adj.combats) == 1
    c = adj.combats[0]
    assert 1 <= c["roll"] <= 6
    assert c["needed"] == kriegsspiel.COMBAT_TABLE[(3, 1)]
    # Seeded run is reproducible.
    m2 = kriegsspiel.Map(4, 4)
    m2.add_unit(kriegsspiel.Unit("red-1", "red", 3, (1, 1)))
    m2.add_unit(kriegsspiel.Unit("blue-1", "blue", 1, (1, 2)))
    adj2 = kriegsspiel.Umpire(m2, seed=42).resolve_turn({"red": [], "blue": []})
    assert adj2.combats[0]["roll"] == c["roll"]


def test_kriegsspiel_human_override_hook_fires():
    m, _ = _skirmish()

    def judge(ctx):
        return {"ruling": "fog too thick: no spotting this turn"}

    ump = kriegsspiel.Umpire(m, seed=1, human_override=judge)
    adj = ump.resolve_turn({"red": [], "blue": []})
    assert adj.overrides  # the hook's ruling is on the record


# ---------------------------------------------------------------------------
# randgame
# ---------------------------------------------------------------------------


def _divergent_game():
    red = randgame.Team(
        "red",
        randgame.WorldModel("red-doctrine")
        .assume("enemy_speed", "0.9 the enemy moves fast", 0.8)
        .assume("own_speed", "0.4 we are slow", 0.7)
        .assume("terrain_favors_defense", "0.8 ground favors the defender", 0.9)
        .assume("neutral_sympathy", "0.3 neutrals distrust us", 0.6)
        .assume("enemy_discipline", "0.8 the enemy holds formation", 0.75)
        .assume("own_cunning", "0.5 average tricksters", 0.5),
    )
    blue = randgame.Team(
        "blue",
        randgame.WorldModel("blue-doctrine")
        .assume("enemy_speed", "0.3 the enemy is sluggish", 0.8)
        .assume("own_speed", "0.8 we are fast", 0.85)
        .assume("terrain_favors_defense", "0.4 ground favors the attacker", 0.6)
        .assume("neutral_sympathy", "0.7 neutrals lean our way", 0.7)
        .assume("enemy_discipline", "0.3 the enemy breaks easily", 0.65)
        .assume("own_cunning", "0.6 decent tricksters", 0.6),
    )
    game = randgame.Game([red, blue], turns=3)
    game.play()
    return game, randgame.Debrief(game.outcomes, game.teams)


def test_randgame_every_outcome_records_consulted_assumptions():
    game, _ = _divergent_game()
    assert len(game.outcomes) == 6  # 2 teams x 3 turns
    for o in game.outcomes:
        assert o.consulted  # no outcome without a paper trail
        for team_name, key, _role in o.consulted:
            assert team_name in game.teams
            assert key in game.teams[team_name].model.assumptions


def test_randgame_divergence_report_finds_model_gaps():
    _, debrief = _divergent_game()
    report = debrief.divergence_report()
    keys = {r["assumption"] for r in report}
    assert "enemy_speed" in keys  # 0.9 vs 0.3: the models openly disagree
    assert "enemy_discipline" in keys
    gap = next(r for r in report if r["assumption"] == "enemy_speed")
    assert gap["gap"] == pytest.approx(0.6)


def test_randgame_trace_links_assumptions_to_outcomes():
    _, debrief = _divergent_game()
    trace = debrief.trace()
    assert trace  # every consulted assumption maps to its outcomes
    for label, uses in trace.items():
        team_name, key = label.split(".", 1)
        assert key in debrief.teams[team_name].model.assumptions
        for u in uses:
            assert "turn" in u and "success" in u and "role" in u


def test_randgame_decisive_assumptions_ranked():
    _, debrief = _divergent_game()
    decisive = debrief.decisive_assumptions()
    assert decisive
    counts = [d["consulted"] for d in decisive]
    assert counts == sorted(counts, reverse=True)
