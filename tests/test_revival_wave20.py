"""Tests for revival wave 20 — game-mechanics (b): hotseat, daily cipher,
splitscreen, score attack, attract mode, zmachine, lightgun."""

from datetime import date

import pytest

from core.levi.revival import (
    attract_mode,
    daily_cipher,
    hotseat,
    lightgun,
    score_attack,
    splitscreen,
    zmachine,
)


# ---------------------------------------------------------------- hotseat
def _session(*names):
    s = hotseat.HotseatSession()
    for n in names:
        s.add_player(n)
    s.begin()
    return s


def test_hotseat_turn_rotation_and_order():
    s = _session("a", "b", "c")
    assert s.current_player() == "a"
    s.take_turn("a", private_moves=["secret"], public_moves=["moved"])
    assert s.current_player() == "b"  # handoff pending to b
    s.pass_device("b")
    assert s.current_player() == "b"
    s.take_turn("b")
    s.pass_device("c")
    s.take_turn("c")
    s.pass_device("a")
    assert s.standings() == {"a": 1, "b": 1, "c": 1}


def test_hotseat_private_moves_are_sealed_not_exposed():
    s = _session("a", "b")
    rec = s.take_turn("a", private_moves=["my secret hand"])
    assert "my secret hand" not in str(rec.public_moves)
    assert "my secret hand" not in str(s.log())
    assert len(rec.private_digest) == 16
    # same secrets -> same digest (deterministic seal)
    s2 = _session("x", "y")
    rec2 = s2.take_turn("x", private_moves=["my secret hand"])
    assert rec2.private_digest == rec.private_digest


def test_hotseat_out_of_turn_and_handoff_rules():
    s = _session("a", "b")
    with pytest.raises(hotseat.HotseatError):
        s.take_turn("b")  # not b's turn
    s.take_turn("a")
    with pytest.raises(hotseat.HotseatError):
        s.take_turn("b")  # handoff not acked yet
    with pytest.raises(hotseat.HotseatError):
        s.pass_device("a")  # wrong acker
    s.pass_device("b")
    assert s.current_player() == "b"
    log = s.end_session()  # no pending handoff -> clean finish
    assert len(log) == 1 and log[0].handoff_acked_by == "b"
    with pytest.raises(hotseat.HotseatError):
        s.take_turn("b")  # session over

    s2 = _session("a", "b")
    s2.take_turn("a")
    with pytest.raises(hotseat.HotseatError):
        s2.end_session()  # handoff still pending


def test_hotseat_export_is_jsonable():
    import json

    s = _session("a", "b")
    s.take_turn("a", public_moves=["go"])
    s.pass_device("b")
    snapshot = s.export()
    json.dumps(snapshot)
    assert snapshot["turns"][0]["handoff_acked_by"] == "b"


# ---------------------------------------------------------- daily_cipher
def test_daily_cipher_deterministic_per_date():
    p1 = daily_cipher.puzzle_for("2026-09-16")
    p2 = daily_cipher.puzzle_for(date(2026, 9, 16))
    assert p1.cipher_text == p2.cipher_text
    assert p1.reveal() == p2.reveal()
    other = daily_cipher.puzzle_for("2026-09-17")
    assert other.cipher_text != p1.cipher_text or other.reveal() != p1.reveal()


def test_daily_cipher_catchup_any_date():
    past = daily_cipher.puzzle_for("2020-01-01")
    assert past.word_length == len(past.reveal()) > 0
    # hint is a true plain->cipher pair
    plain, cipher = past.hint
    assert past.cipher_text.count(cipher) >= 1
    assert plain in past.reveal()
    # solving works
    assert past.solve(past.reveal())
    assert not past.solve("wrongword")


def test_daily_cipher_check_guess_and_no_penalties():
    p = daily_cipher.puzzle_for("2026-09-16")
    plain, cipher = p.hint
    verdict = p.check_guess({cipher: plain})
    assert verdict[cipher] is True
    verdict2 = p.check_guess({cipher: "z" if plain != "z" else "q"})
    assert verdict2[cipher] is False
    log = daily_cipher.DailyCipherLog()
    log.record("2026-09-14", solved=True)
    assert log.played("2026-09-15") is None  # missed day: just unplayed
    assert log.summary()["days_missed_penalty"] == 0
    assert log.unplayed_dates(["2026-09-14", "2026-09-15"]) == [date(2026, 9, 15)]


# ------------------------------------------------------------ splitscreen
def test_splitscreen_layouts_are_sound():
    for n in (1, 2, 3, 4):
        layout = splitscreen.ViewportLayout.for_players(n, 1920, 1080)
        assert len(layout.viewports) == n
        assert layout.validate() == []
        # every pixel of the screen belongs to exactly one viewport
        assert layout.viewport_at(0, 0) is not None
        assert layout.viewport_at(1919, 1079) is not None
        assert layout.viewport_at(2000, 2000) is None


def test_splitscreen_two_player_halves():
    layout = splitscreen.ViewportLayout.for_players(2, 100, 60)
    a = layout.viewport_for(0)
    b = layout.viewport_for(1)
    assert a.rect == (0, 0, 50, 60)
    assert b.rect == (50, 0, 50, 60)
    assert a.area == b.area == 3000


def test_splitscreen_focus_keeps_everyone_visible():
    layout = splitscreen.ViewportLayout.for_players(4, 800, 600)
    focused = layout.set_focus(2, emphasis=2.0)
    assert focused.validate() == []
    assert focused.viewport_for(2).focused
    assert focused.viewport_for(2).area > layout.viewport_for(2).area
    # nobody disappears: every viewport keeps >= 1/4 of its original area
    for v in focused.viewports:
        orig = layout.viewport_for(v.player)
        assert v.area * 4 >= orig.area
    with pytest.raises(splitscreen.SplitscreenError):
        layout.set_focus(9)


# ---------------------------------------------------------- score_attack
def test_score_attack_top10_and_eviction():
    board = score_attack.Leaderboard()
    for i in range(12):
        board.submit(1200 - i * 10, f"A{i:02d}")
    top = board.top()
    assert len(top) == 10
    assert top[0].score == 1200
    assert top[-1].score == 1200 - 9 * 10
    # rank 11 fell off the cabinet
    assert board.rank_of(1200 - 11 * 10) is None
    assert board.rank_of(1250) == 1


def test_score_attack_initials_normalization():
    board = score_attack.Leaderboard()
    assert board.submit(500, "abc") == 1
    assert board.top()[0].initials == "ABC"
    with pytest.raises(score_attack.ScoreError):
        board.submit(400, "AB")  # too short
    with pytest.raises(score_attack.ScoreError):
        board.submit(400, "ABCD")  # too long
    with pytest.raises(score_attack.ScoreError):
        board.submit(-5, "ABC")


def test_score_attack_seeded_replay_verification(tmp_path):
    claim = score_attack.ScoreClaim(
        score=score_attack._default_scorer(42, (10, 20, 30)),
        initials="YOU",
        seed=42,
        inputs=(10, 20, 30),
    )
    assert score_attack.verify_claim(claim)
    forged = score_attack.ScoreClaim(
        score=999999, initials="YOU", seed=42, inputs=(10, 20, 30)
    )
    assert not score_attack.verify_claim(forged)
    board = score_attack.Leaderboard()
    assert board.submit_verified(claim) == 1
    with pytest.raises(score_attack.ScoreError):
        board.submit_verified(forged)
    # persistence round-trip
    path = tmp_path / "cabinet.json"
    board.save(path)
    loaded = score_attack.Leaderboard.load(path)
    assert loaded.top()[0].score == claim.score
    assert loaded.top()[0].initials == "YOU"
    assert loaded.fingerprint() == board.fingerprint()


# ----------------------------------------------------------- attract_mode
def test_attract_mode_replays_real_loop_deterministically():
    def step(state, inputs):
        return state + inputs  # the REAL game step function

    rec = attract_mode.DemoRecorder()
    for i in (1, 2, 3):
        rec.capture(i)
    script = rec.finish()
    demo = attract_mode.AttractMode(script=script, max_loops=2)
    frames = list(demo.run(step, 0))
    assert len(frames) == 6
    assert [f.state for f in frames] == [1, 3, 6, 1, 3, 6]
    assert all(f.loop in (0, 1) for f in frames)


def test_attract_mode_interrupts_on_real_input():
    def step(state, inputs):
        return state

    rec = attract_mode.DemoRecorder()
    rec.capture("a")
    rec.capture("b")
    demo = attract_mode.AttractMode(script=rec.finish())
    gen = demo.run(step, None)
    next(gen)
    demo.notify_input("button-press")
    rest = list(gen)
    assert rest == []
    assert demo.interrupted
    assert demo.stats()["frames_shown"] == 1


def test_attract_mode_recorder_rules():
    rec = attract_mode.DemoRecorder()
    with pytest.raises(attract_mode.AttractError):
        rec.finish()  # empty
    rec.capture("x")
    script = rec.finish()
    assert script.recorded_frames == 1
    with pytest.raises(attract_mode.AttractError):
        rec.capture("y")  # already finished


# ---------------------------------------------------------------- zmachine
def _run(builder_fn, inputs=()):
    builder = zmachine.StoryBuilder()
    builder_fn(builder)
    story = builder.build()
    out: list = []
    it = iter(inputs)
    vm = zmachine.Zvm(story, output=out.append, input_fn=lambda: next(it))
    vars_ = vm.run()
    return out, vars_, vm


def test_zmachine_arithmetic_and_print():
    def build(b):
        b.emit("PUSH", 6).emit("PUSH", 7).emit("MUL")
        b.emit("PRINT").emit("HALT")

    out, _, _ = _run(build)
    assert out == ["42"]


def test_zmachine_branching_variables_and_input():
    def build(b):
        b.emit("INPUT").emit("STORE", "name")
        b.say("hello, traveler")
        b.emit("LOAD", "name").emit("PRINT")
        b.emit("PUSH", 0).emit("JZ", "skip")
        b.say("you will never read this")
        b.label("skip").emit("HALT")

    out, vars_, _ = _run(build, inputs=["chauncey"])
    assert out[0] == "hello, traveler"
    assert out[1] == "chauncey"
    assert vars_["name"] == "chauncey"


def test_zmachine_call_ret_and_traps():
    def build(b):
        b.emit("CALL", "double").emit("PRINT").emit("HALT")
        b.label("double").emit("PUSH", 21).emit("DUP").emit("ADD").emit("RET")

    out, _, _ = _run(build)
    assert out == ["42"]

    def bad(b):
        b.emit("PUSH", 1).emit("PUSH", 0).emit("DIV").emit("HALT")

    with pytest.raises(zmachine.ZvmError):
        _run(bad)

    def badjump(b):
        b.emit("JMP", 999).emit("HALT")

    with pytest.raises(zmachine.ZvmError):
        _run(badjump)


def test_zmachine_story_roundtrip():
    b = zmachine.StoryBuilder()
    b.say("once upon a time").emit("HALT")
    story = b.build()
    data = story.to_dict()
    import json

    json.dumps(data)
    story2 = zmachine.StoryFile.from_dict(data)
    out = []
    zmachine.Zvm(story2, output=out.append).run()
    assert out == ["once upon a time"]


# ---------------------------------------------------------------- lightgun
def _gun():
    g = lightgun.LightGunSession(frame_ms=16.7, slot_ms=2.0)
    g.configure([lightgun.Target("duck", 0), lightgun.Target("ufo", 1)])
    return g


def test_lightgun_hit_by_timing_not_aim():
    g = _gun()
    obs = g.synthesize_observations("ufo")
    result = g.pull_trigger(obs)
    assert result.hit
    assert result.target_id == "ufo"
    assert result.slot == 1
    # there is no aim coordinate anywhere on the result
    assert not hasattr(result, "x") and not hasattr(result, "y")


def test_lightgun_miss_and_black_frame_ignored():
    g = _gun()
    # clean miss: only darkness
    result = g.pull_trigger(g.synthesize_observations(None))
    assert not result.hit
    # light outside every slot window (in the black frame) is ignored
    result2 = g.pull_trigger([(15.0, 1.0)])
    assert not result2.hit
    # dim light below threshold does not count
    result3 = g.pull_trigger([(0.5, 0.1)])
    assert not result3.hit


def test_lightgun_slot_discrimination_and_config_rules():
    g = _gun()
    windows = g.slot_windows()
    assert windows[0] == (0.0, 2.0)
    assert windows[1] == (2.0, 4.0)
    # first lit slot wins
    result = g.pull_trigger([(0.5, 1.0), (2.5, 1.0)])
    assert result.hit and result.target_id == "duck"
    # duplicate slots rejected; too many slots for the frame rejected
    with pytest.raises(lightgun.LightGunError):
        lightgun.LightGunSession().configure(
            [lightgun.Target("a", 0), lightgun.Target("b", 0)]
        )
    with pytest.raises(lightgun.LightGunError):
        lightgun.LightGunSession(frame_ms=5.0, slot_ms=2.0).configure(
            [lightgun.Target("a", 0), lightgun.Target("b", 1), lightgun.Target("c", 2)]
        )
