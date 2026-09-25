"""Tests for wave 19 — game mechanics: doors, IF, pinball grammars, honest play."""

import pytest

from levi.revival import door_games, igms, mancala_grammar, pachinko
from levi.revival import parser_if, pinball_grammar, puzzle_automation, twine_authoring


# ---------------------------------------------------------------------------
# door_games
# ---------------------------------------------------------------------------


def test_dropfile_roundtrip():
    d = door_games.DropFile(
        user="chauncey", node=2, session_id="abc", time_left_minutes=45
    )
    back = door_games.DropFile.from_text(d.to_text())
    assert back == d


def test_dropfile_rejects_garbage():
    with pytest.raises(door_games.BadDropFile):
        door_games.DropFile.from_text("no equals here\n")
    with pytest.raises(door_games.BadDropFile):
        door_games.DropFile.from_text("node=3\n")


def test_turn_ledger_appointment_dynamic():
    ledger = door_games.TurnLedger(turns_per_day=2)
    day_one, day_two = 1_700_000_000.0, 1_700_000_000.0 + 86400
    assert ledger.use_turn("p1", now=day_one) == 1
    assert ledger.use_turn("p1", now=day_one) == 0
    with pytest.raises(door_games.NoTurnsLeft):
        ledger.use_turn("p1", now=day_one)
    # next day: fresh allowance
    assert ledger.turns_left("p1", now=day_two) == 2
    assert ledger.use_turn("p1", now=day_two) == 1


def test_shared_world_journal_and_version():
    w = door_games.SharedWorld()
    v1 = w.apply("p1", "dig", "dug at (3,4)", lambda s: s.update(gold=10))
    v2 = w.apply("p2", "dig", "dug at (3,5)", lambda s: s.update(gold=15))
    assert (v1, v2) == (1, 2)
    assert w.read("gold") == 15
    assert [e.actor for e in w.history()] == ["p1", "p2"]
    assert [e.seq for e in w.history("p2")] == [1]


def test_challenge_resolve_is_deterministic_and_single_use():
    c1 = door_games.Challenge("a", "b", attack_power=10, seed=42)
    c2 = door_games.Challenge("a", "b", attack_power=10, seed=42)
    c1.resolve(defender_power=5)
    c2.resolve(defender_power=5)
    assert c1.outcome == c2.outcome and c1.margin == c2.margin
    with pytest.raises(door_games.ChallengeError):
        c1.resolve(defender_power=5)


def test_door_server_enforces_turns_and_routes_challenges():
    server = door_games.DoorServer()
    server.host(door_games.Door("trade-wars", turns_per_day=1))
    drop = door_games.DropFile(user="p1")
    visit = server.enter("trade-wars", drop)
    assert visit.turns_left == 0 and visit.player == "p1"
    with pytest.raises(door_games.NoTurnsLeft):
        server.enter("trade-wars", drop)
    with pytest.raises(door_games.UnknownDoor):
        server.enter("nope", drop)
    door = server.doors["trade-wars"]
    door.issue_challenge("p1", "p2", attack_power=7, seed=1, note="dawn raid")
    pending = door.challenges_for("p2")
    assert len(pending) == 1
    pending[0].resolve(defender_power=3)
    assert door.challenges_for("p2") == []


# ---------------------------------------------------------------------------
# igms
# ---------------------------------------------------------------------------


def test_igm_dispatch_priority_order_and_ctx():
    reg = igms.IGMRegistry()
    calls = []
    reg.register(
        igms.IGM(
            name="late",
            hooks={igms.ON_TURN: lambda c: calls.append("late")},
            priority=200,
        )
    )
    reg.register(
        igms.IGM(
            name="early",
            hooks={igms.ON_TURN: lambda c: calls.append("early")},
            priority=10,
        )
    )
    reg.register(
        igms.IGM(name="other", hooks={igms.ON_VISIT: lambda c: calls.append("other")})
    )
    results = reg.dispatch(igms.ON_TURN, {"turn": 3})
    assert calls == ["early", "late"]
    assert all(r.ok for r in results)
    assert [r.igm_name for r in results] == ["early", "late"]


def test_igm_failure_isolated():
    reg = igms.IGMRegistry()

    def boom(ctx):
        raise ValueError("bad module")

    reg.register(igms.IGM(name="boom", hooks={igms.ON_MOVE: boom}, priority=1))
    reg.register(
        igms.IGM(
            name="fine",
            hooks={igms.ON_MOVE: lambda c: c.update(moved=True)},
            priority=2,
        )
    )
    ctx = {}
    results = reg.dispatch(igms.ON_MOVE, ctx)
    assert results[0].ok is False and "ValueError" in results[0].error
    assert results[1].ok is True and ctx["moved"] is True


def test_igm_validation():
    reg = igms.IGMRegistry()
    reg.register(igms.IGM(name="m", hooks={"e": lambda c: None}))
    with pytest.raises(igms.DuplicateIGM):
        reg.register(igms.IGM(name="m", hooks={"e": lambda c: None}))
    with pytest.raises(igms.BadIGM):
        reg.register(igms.IGM(name="bad", hooks={"e": "not-callable"}))
    with pytest.raises(igms.BadIGM):
        reg.register(igms.IGM(name="empty", hooks={}))
    with pytest.raises(igms.UnknownIGM):
        reg.unregister("ghost")
    assert reg.describe()[0]["name"] == "m"


# ---------------------------------------------------------------------------
# pinball_grammar
# ---------------------------------------------------------------------------


def test_pinball_play_shape_and_score():
    board = pinball_grammar.Pinboard(
        pinball_grammar.BoardSpec.classic(rows=6, pins=5), seed=7
    )
    res = board.play(aim=0.2, skill=0.8)
    assert len(res.path) == 6
    assert 0 <= res.bin_index < len(board.spec.bins)
    assert res.score == board.spec.bins[res.bin_index]


def test_pinball_seeded_reproducibility():
    kw = dict(aim=-0.4, skill=0.3)
    a = pinball_grammar.Pinboard(pinball_grammar.BoardSpec.classic(), seed=99).play(
        **kw
    )
    b = pinball_grammar.Pinboard(pinball_grammar.BoardSpec.classic(), seed=99).play(
        **kw
    )
    assert a.path == b.path and a.bin_index == b.bin_index


def test_pinball_skill_narrows_distribution():
    spec = pinball_grammar.BoardSpec.classic(rows=8, pins=7)
    low = pinball_grammar.Pinboard(spec, seed=5).distribution(
        aim=0.0, skill=0.0, balls=400
    )
    high = pinball_grammar.Pinboard(spec, seed=5).distribution(
        aim=0.0, skill=1.0, balls=400
    )
    assert sum(low) == sum(high) == 400
    assert max(high) > max(low)  # skill concentrates landings
    with pytest.raises(pinball_grammar.PinballError):
        pinball_grammar.Pinboard(spec, seed=1).play(aim=2.0)


# ---------------------------------------------------------------------------
# mancala_grammar
# ---------------------------------------------------------------------------


def test_mancala_kalah_sow_conserves_seeds():
    g = mancala_grammar.MancalaGame(mancala_grammar.kalah_rules())
    assert g.legal_moves(0) == [0, 1, 2, 3, 4, 5]
    total_before = sum(g.pits) + sum(g.stores)
    out = g.sow(0, 2)
    assert sum(g.pits) + sum(g.stores) == total_before
    assert g.pits[2] == 0  # picked up
    assert out.player == 0


def test_mancala_kalah_extra_turn_and_capture():
    g = mancala_grammar.MancalaGame(mancala_grammar.kalah_rules())
    # Sow pit 5 with 1 seed so the last lands in the own store -> extra turn.
    # (pit 0 keeps a seed so the game doesn't end on this move.)
    g.pits = [1, 0, 0, 0, 0, 1] + [4] * 6
    out = g.sow(0, 5)
    assert out.extra_turn is True and g.turn == 0 and g.stores[0] == 1
    # Capture: last seed lands in empty own pit opposite a full pit.
    g2 = mancala_grammar.MancalaGame(mancala_grammar.kalah_rules())
    g2.pits = [1, 0, 0, 0, 0, 0] + [4] * 6
    g2.pits[10] = 5  # opposite(1) == 10
    out2 = g2.sow(0, 0)
    assert out2.captured == 1 + 5
    assert g2.stores[0] == 6
    assert g2.pits[1] == 0 and g2.pits[10] == 0


def test_mancala_oware_capture_chains():
    g = mancala_grammar.MancalaGame(mancala_grammar.oware_rules())
    # Player 0 sows pit 5 with 2 seeds: first to the store, last into
    # opponent pit 6, making it hold 2 -> captured.
    g.pits = [0, 0, 0, 0, 1, 2, 1, 0, 0, 0, 0, 1]
    out = g.sow(0, 5)
    assert out.captured == 2
    assert g.pits[6] == 0
    assert g.stores[0] == 3  # 1 sowed into store + 2 captured
    assert out.extra_turn is False
    assert out.game_over is False


def test_mancala_game_over_and_winner():
    g = mancala_grammar.MancalaGame(mancala_grammar.kalah_rules())
    g.pits = [0, 0, 0, 0, 0, 1] + [0] * 6
    g.stores = [20, 10]
    out = g.sow(0, 5)
    assert out.game_over is True
    # leftover swept to owner's store: pit5's seed went to store, side empty
    assert g.winner() == 0
    with pytest.raises(mancala_grammar.MancalaError):
        g.sow(0, 0)


def test_mancala_illegal_moves_rejected():
    g = mancala_grammar.MancalaGame(mancala_grammar.kalah_rules())
    with pytest.raises(mancala_grammar.MancalaError):
        g.sow(1, 6)  # wrong player
    with pytest.raises(mancala_grammar.MancalaError):
        g.sow(0, 8)  # not your pit
    g.pits[0] = 0
    with pytest.raises(mancala_grammar.MancalaError):
        g.sow(0, 0)  # empty pit


# ---------------------------------------------------------------------------
# pachinko
# ---------------------------------------------------------------------------


def test_pachinko_bank_never_negative():
    bank = pachinko.BallBank(2)
    bank.spend()
    bank.spend()
    with pytest.raises(pachinko.PachinkoError):
        bank.spend()
    assert bank.balls == 0
    assert bank.insert(5) == 5
    assert bank.collect(3) == 8


def test_pachinko_launch_shape_and_accounting():
    layout = pachinko.PinLayout.standard()
    machine = pachinko.Machine(layout, pachinko.BallBank(10), seed=11)
    res = machine.launch(velocity=0.5)
    assert len(res.path) == layout.rows
    assert res.payout == round(res.multiplier)
    assert res.bank_after == 10 - 1 + res.payout
    assert machine.launches == 1


def test_pachinko_seeded_reproducibility_and_velocity_range():
    def mk():
        return pachinko.Machine(
            pachinko.PinLayout.standard(), pachinko.BallBank(50), seed=3
        )

    a, b = mk().launch(0.7), mk().launch(0.7)
    assert a.path == b.path and a.pocket == b.pocket
    with pytest.raises(pachinko.PachinkoError):
        mk().launch(1.5)
    with pytest.raises(pachinko.PachinkoError):
        pachinko.Machine(
            pachinko.PinLayout.standard(), pachinko.BallBank(0), seed=1
        ).launch(0.5)


def test_pachinko_expected_value_sane():
    machine = pachinko.Machine(
        pachinko.PinLayout.standard(), pachinko.BallBank(0), seed=21
    )
    ev = machine.expected_value(velocity=0.5, balls=500)
    max_mult = max(p.multiplier for p in machine.layout.pockets)
    assert 0.0 <= ev <= max_mult
    assert machine.bank.balls == 0  # accounting restored


# ---------------------------------------------------------------------------
# parser_if
# ---------------------------------------------------------------------------


def test_parser_movement_and_description():
    eng = parser_if.Engine(parser_if.demo_world())
    first = eng.describe()
    assert "Stone Hall" in first
    resp = eng.step("go north")
    assert "Vault" in resp
    assert eng.location == "vault"
    assert eng.step("n") == "You can't go that way."  # no north exit from vault
    assert eng.step("south") and eng.location == "hall"


def test_parser_take_drop_inventory_synonyms():
    eng = parser_if.Engine(parser_if.demo_world())
    assert "Taken" in eng.step("grab lamp")
    assert "brass lamp" in eng.step("i")
    assert "Dropped" in eng.step("drop the lamp")
    assert "nothing" in eng.step("inventory").lower()
    assert "brass" in eng.step("x lamp")


def test_parser_honest_about_unknown_words():
    eng = parser_if.Engine(parser_if.demo_world())
    assert "don't know the word" in eng.step("flibberty gibbet")
    assert "don't see" in eng.step("take dragon")
    assert "commands" in eng.step("help").lower()


def test_parser_world_spec_validation():
    with pytest.raises(parser_if.IFError):
        parser_if.World.from_spec(
            {"start": "a", "rooms": {"a": {"exits": {"north": "missing"}}}, "items": {}}
        )


# ---------------------------------------------------------------------------
# puzzle_automation
# ---------------------------------------------------------------------------


class _FakeEngine:
    def __init__(self):
        self.log = []
        self.flag = False

    def step(self, command):
        self.log.append(command)
        if command == "pull lever":
            self.flag = True
        return "ok"


def test_recorder_learns_on_goal():
    eng = _FakeEngine()
    rec = puzzle_automation.Recorder(eng)
    rec.begin("open-vault", goal=lambda: eng.flag)
    rec.feed("take lamp")
    assert rec.recording == "open-vault"
    rec.feed("pull lever")
    assert rec.recording is None  # auto-finalized
    routine = rec.get("open-vault")
    assert routine.steps == ["take lamp", "pull lever"]
    assert eng.log == ["take lamp", "pull lever"]


def test_generalize_creates_slots():
    merged = puzzle_automation.generalize(
        [["take brass key", "go north"], ["take iron key", "go north"]]
    )
    assert merged == ["take {w1} key", "go north"]
    with pytest.raises(puzzle_automation.AutomationError):
        puzzle_automation.generalize([["a", "b"], ["a"]])


def test_automator_replay_and_honest_failure():
    eng = _FakeEngine()
    routine = puzzle_automation.Routine(
        name="r", steps=["take {w0}", "go north"], slots=["w0"]
    )
    auto = puzzle_automation.Automator(eng)
    ok = auto.replay(routine, bindings={"w0": "lamp"})
    assert ok.ok and ok.steps_run == 2 and routine.replays_ok == 1
    # stop_on trips on the first response -> honest early failure report
    res = auto.replay(routine, bindings={"w0": "lamp"}, stop_on=lambda r: True)
    assert res.ok is False and res.failed_at == 0 and routine.replays_failed == 1
    with pytest.raises(puzzle_automation.AutomationError):
        auto.replay(routine)  # slot unbound


# ---------------------------------------------------------------------------
# twine_authoring
# ---------------------------------------------------------------------------


def _sample_story():
    s = twine_authoring.Story(title="test", start="start")
    s.add_passage(
        "start", "You wake up. (set: $hp to 10)\n[[Go north|forest]]\n[[Stay|start]]"
    )
    s.add_passage("forest", "Trees. [[Go back|start]]")
    s.add_passage("lonely", "Nobody links here.")
    return s


def test_twine_link_parsing_and_text():
    s = _sample_story()
    assert s.get("start").links() == [("Go north", "forest"), ("Stay", "start")]
    assert s.get("forest").links() == [("Go back", "start")]
    text = s.get("start").text()
    assert "[[" not in text and "(set:" not in text
    assert "You wake up." in text


def test_twine_validation_finds_orphans_and_dead_ends():
    s = _sample_story()
    report = s.validate()
    assert report.orphans == ["lonely"]
    assert "forest" not in report.dead_ends  # it links back
    s2 = twine_authoring.Story(start="a")
    s2.add_passage("a", "[[nowhere|missing]]")
    r2 = s2.validate()
    assert r2.broken_links == [("a", "nowhere", "missing")]
    assert r2.ok is False


def test_twine_session_playtest():
    s = _sample_story()
    sess = twine_authoring.Session(s)
    text, choices = sess.render()
    assert choices == ["Go north", "Stay"]
    assert sess.state["hp"] == 10
    sess.choose(0)
    assert sess.current == "forest"
    assert sess.visits == ["start", "forest"]
    with pytest.raises(twine_authoring.BadChoice):
        sess.choose(9)
    with pytest.raises(twine_authoring.DuplicatePassage):
        s.add_passage("start", "dup")
