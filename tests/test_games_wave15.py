"""Hermetic tests for wave-015 fair-play additions.

if_engine (Z-machine revival), odds (anti-loot-box), season (un-expiring
battle pass), relay (dead multiplayer ritual). All hermetic: seeded RNG,
tmp save homes, no network, no clock dependence beyond injected dates.
"""

import json
import random

import pytest

from levi.games import charter, if_engine, odds, relay, season
from levi.games.if_engine import ADVENTURES, SUNKEN_ARCHIVE


# ---------------------------------------------------------------------------
# Charter: every new game is fair by construction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mod", [if_engine, odds, season, relay])
def test_wave15_manifests_pass_charter(mod):
    assert charter.is_fair(mod.MANIFEST), charter.check_manifest(mod.MANIFEST)


def test_odds_manifest_declares_randomness_honestly():
    m = odds.MANIFEST
    assert m.has_randomness and m.odds_declared and m.has_audit_hook


# ---------------------------------------------------------------------------
# if_engine: parser
# ---------------------------------------------------------------------------


def test_parser_bare_direction_implies_go():
    assert if_engine.parse_command("n") == ("go", ["north"])
    assert if_engine.parse_command("go north") == ("go", ["north"])


def test_parser_strips_articles_and_handles_pick_up():
    assert if_engine.parse_command("take the brass lantern") == (
        "take",
        ["brass", "lantern"],
    )
    assert if_engine.parse_command("pick up lantern") == ("take", ["lantern"])


def test_parser_unknown_word_is_honest():
    verb, words = if_engine.parse_command("xyzzy foo")
    assert verb is None
    state = if_engine.new_game(SUNKEN_ARCHIVE)
    out = if_engine.do_command(SUNKEN_ARCHIVE, state, "xyzzy foo")
    assert "don't know the word" in out and "HELP" in out


def test_parser_help_lists_the_whole_language():
    state = if_engine.new_game(SUNKEN_ARCHIVE)
    out = if_engine.do_command(SUNKEN_ARCHIVE, state, "help")
    for verb in if_engine.VERBS:
        assert verb in out


def test_dark_room_needs_light():
    adv = SUNKEN_ARCHIVE
    state = if_engine.new_game(adv)
    if_engine.do_command(adv, state, "n")  # stacks
    out = if_engine.do_command(adv, state, "down")  # cistern, no lantern
    assert "pitch dark" in out
    assert "too dark" in if_engine.do_command(adv, state, "take sigil of craft")


def test_full_win_path():
    adv = SUNKEN_ARCHIVE
    state = if_engine.new_game(adv)
    for cmd in [
        "take lantern",
        "n",
        "take sigil of memory",
        "down",
        "take sigil of craft",
        "up",
        "e",
        "use desk",
        "take bronze key",
        "e",
        "take sigil of play",
        "open east",
        "go east",
    ]:
        out = if_engine.do_command(adv, state, cmd)
    assert state.won
    assert "YOU WIN" in out


def test_desk_gives_key_only_once():
    adv = SUNKEN_ARCHIVE
    state = if_engine.new_game(adv)
    for cmd in ["take lantern", "n", "e", "use desk", "use desk"]:
        out = if_engine.do_command(adv, state, cmd)
    assert "Nothing more happens" in out
    keys = state.room_items["scriptorium"].count("bronze-key")
    assert keys == 1


def test_locked_door_needs_key():
    adv = SUNKEN_ARCHIVE
    state = if_engine.new_game(adv)
    for cmd in ["take lantern", "n", "e", "e"]:
        if_engine.do_command(adv, state, cmd)
    out = if_engine.do_command(adv, state, "go east")
    assert "locked" in out
    assert state.room == "vault-ante"


def test_story_state_round_trip():
    adv = SUNKEN_ARCHIVE
    state = if_engine.new_game(adv)
    if_engine.do_command(adv, state, "take lantern")
    if_engine.do_command(adv, state, "n")
    clone = if_engine.StoryState.from_dict(state.to_dict())
    assert clone.room == state.room == "stacks"
    assert clone.inventory == ["lantern"]
    assert clone.moves == state.moves


def test_adventures_registry_nonempty():
    assert "sunken-archive" in ADVENTURES


# ---------------------------------------------------------------------------
# odds: the anti-loot-box
# ---------------------------------------------------------------------------


def test_declared_odds_sum_to_one():
    for crate in odds.CRATES.values():
        total = sum(crate.declared_odds().values())
        assert abs(total - 1.0) < 1e-9


def test_pity_is_visible_and_free():
    crate = odds.CRATES["starfall"]
    state = odds.CrateState(crate_name="starfall", since_pity=49)
    pull = odds.open_crate(crate, state, random.Random(1))
    assert pull.pity_triggered
    assert pull.rarity in crate.pity_rarities
    assert state.since_pity == 0


def test_pity_counter_resets_only_on_pity():
    crate = odds.CRATES["starfall"]
    state = odds.CrateState(crate_name="starfall")
    rng = random.Random(3)
    for _ in range(10):
        odds.open_crate(crate, state, rng)
    assert state.since_pity == 10  # no pity yet (pity_after=50)


def test_expected_value_is_honest_math():
    crate = odds.CRATES["starfall"]
    values = {d.item: 1.0 for d in crate.drops}
    assert abs(odds.expected_value(crate, values) - 1.0) < 1e-9
    assert odds.expected_value(crate, {}) == 0.0


def test_audit_matches_declared_odds():
    result = odds.audit("starfall", n=20000, seed=7)
    assert result["max_deviation"] < 0.02  # honest RNG, not rigged
    assert set(result["declared"]) == set(result["observed"])


def test_audit_is_deterministic():
    a = odds.audit("tidepool", n=5000, seed=42)
    b = odds.audit("tidepool", n=5000, seed=42)
    assert a["observed"] == b["observed"]


def test_prove_report_states_free():
    text = odds.prove("starfall", n=2000, seed=7)
    assert "$0.00" in text and "Pity: free" in text


def test_crate_state_round_trip():
    s = odds.CrateState(crate_name="starfall", pulls=5, since_pity=5, history=["x"])
    assert odds.CrateState.from_dict(s.to_dict()).to_dict() == s.to_dict()


# ---------------------------------------------------------------------------
# season: the un-expiring battle pass
# ---------------------------------------------------------------------------


def test_season_never_auto_expires():
    s = season.new_season("test", on="2020-01-01")
    assert s.closed is None  # five years "old", still open


def test_log_progress_and_level_up():
    s = season.new_season("test", on="2026-09-16")
    s.add_challenge("read", "read a chapter", target=2, xp_reward=100)
    completed, leveled = s.log("read", 2, on="2026-09-16")
    assert completed and leveled
    assert s.level == 1 and s.xp == 100


def test_streak_freezes_never_punishes():
    s = season.new_season("test", on="2026-09-16")
    s.add_challenge("c", "d", target=100)
    s.log("c", 1, on="2026-09-10")
    s.log("c", 1, on="2026-09-11")
    assert s.streak == 2
    # ten days pass with no activity: streak simply ends at last activity,
    # progress is untouched, nothing is lost
    s.log("c", 1, on="2026-09-21")
    ch = s.challenges["c"]
    assert ch.progress == 3
    assert s.streak == 1  # new run starts fresh — no punishment, no decay


def test_close_and_reopen_are_player_controlled():
    s = season.new_season("test", on="2026-09-16")
    s.add_challenge("c", "d", target=1)
    s.close(on="2026-09-16")
    with pytest.raises(ValueError):
        s.log("c", 1, on="2026-09-16")
    s.reopen()
    completed, _ = s.log("c", 1, on="2026-09-17")
    assert completed


def test_unknown_challenge_refused():
    s = season.new_season("test", on="2026-09-16")
    with pytest.raises(KeyError):
        s.log("nope", 1, on="2026-09-16")


def test_season_round_trip():
    s = season.new_season("test", on="2026-09-16")
    s.add_challenge("c", "d", target=3, xp_reward=25)
    s.log("c", 3, on="2026-09-16")
    clone = season.Season.from_dict(s.to_dict())
    assert clone.to_dict() == s.to_dict()
    assert "Level 0" in season.status_text(s) or "Level" in season.status_text(s)


# ---------------------------------------------------------------------------
# relay: async turn protocol
# ---------------------------------------------------------------------------


def test_relay_enforces_turn_order():
    r = relay.new_relay(["ana", "bo"])
    assert r.turn == "ana"
    r.append("ana", {"move": "a1"})
    assert r.turn == "bo"
    with pytest.raises(relay.RelayError):
        r.append("ana", {"move": "a2"})


def test_relay_rejects_unknown_player():
    r = relay.new_relay(["ana", "bo"])
    with pytest.raises(relay.RelayError):
        r.append("zed", {"move": "x"})


def test_relay_chain_verifies():
    r = relay.new_relay(["ana", "bo"])
    for i in range(6):
        r.append(r.turn, {"n": i})
    assert r.verify()
    assert r.seq == 6


def test_relay_tamper_detected():
    r = relay.new_relay(["ana", "bo"])
    r.append("ana", {"move": "honest"})
    r.envelopes[0]["move"] = {"move": "rigged"}
    assert not r.verify()


def test_relay_import_rejects_tampered_file(tmp_path):
    r = relay.new_relay(["ana", "bo"])
    r.append("ana", {"move": "ok"})
    p = tmp_path / "relay.json"
    r.export(str(p))
    data = json.loads(p.read_text())
    data["envelopes"][0]["player"] = "mallory"
    p.write_text(json.dumps(data))
    with pytest.raises(relay.RelayError):
        relay.Relay.import_file(str(p))


def test_relay_export_import_round_trip(tmp_path):
    r = relay.new_relay(["ana", "bo", "cy"])
    for _ in range(5):
        r.append(r.turn, ["x", 1])
    p = tmp_path / "relay.json"
    r.export(str(p))
    r2 = relay.Relay.import_file(str(p))
    assert r2.to_dict() == r.to_dict()
    assert r2.turn == r.turn


def test_relay_needs_two_players():
    with pytest.raises(relay.RelayError):
        relay.new_relay(["solo"])
    with pytest.raises(relay.RelayError):
        relay.new_relay(["a", "a"])
