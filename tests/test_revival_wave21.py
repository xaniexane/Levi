"""Wave 21 tests: scumm, blobber_crawl, cheat_codes, rts_campaigns,
indie_channel, story_vm, turn_relay."""

import json
import os

import pytest

from levi.revival import (
    blobber_crawl,
    cheat_codes,
    indie_channel,
    rts_campaigns,
    scumm,
    story_vm,
    turn_relay,
)


# ---------------------------------------------------------------- scumm.py
class TestScumm:
    def test_walk_take_and_use_unlocks_cellar(self):
        g = scumm.demo_game()
        assert g.current_room == "porch"
        out = g.command("take", "lantern")
        assert any("take the lantern" in line for line in out)
        assert "lantern" in g.inventory
        out = g.command("walk", "north")
        assert g.current_room == "hall"
        out = g.command("use", "lantern", "cellar door")
        assert g.flags.get("lit_cellar") is True
        out = g.command("walk", "down")
        assert g.current_room == "cellar"

    def test_locked_room_blocks_entry(self):
        g = scumm.demo_game()
        g.command("walk", "north")
        out = g.command("walk", "down")
        assert g.current_room == "hall"  # still in hall
        assert any("locked" in line for line in out)

    def test_dialogue_choices_and_flags(self):
        g = scumm.demo_game()
        g.command("walk", "north")
        out = g.command("talk", "keeper")
        assert any("KEEPER" in line for line in out)
        out = g.choose("who are you?")
        assert any("KEEPER" in line for line in out)
        out = g.choose("thanks")
        assert g.flags.get("warned") is True

    def test_cutscene_plays_and_locks_input(self):
        g = scumm.demo_game()
        g.command("take", "lantern")
        g.command("walk", "north")
        g.command("use", "lantern", "cellar door")
        g.command("walk", "down")
        out = g.command("take", "brass key")
        assert any("cutscene" in line for line in out)
        blocked = g.command("walk", "up")
        assert any("cutscene is playing" in line for line in blocked)
        tail = []
        played = []
        while g.active_cutscene:
            tail = g.advance_cutscene()
            played.extend(tail)
        assert g.flags.get("__won__") is True
        assert any("THE END" in line for line in played)

    def test_save_load_roundtrip(self):
        g = scumm.demo_game()
        g.command("take", "lantern")
        snap = g.save()
        g2 = scumm.demo_game()
        g2.load(snap)
        assert "lantern" in g2.inventory
        assert g2.current_room == "porch"

    def test_unknown_verb_rejected(self):
        g = scumm.demo_game()
        out = g.command("dance", "lantern")
        assert any("not a verb" in line for line in out)


# ---------------------------------------------------------- blobber_crawl.py
class TestBlobber:
    def test_step_turn_and_bump(self):
        d = blobber_crawl.Delve(blobber_crawl.DEMO_MAP, seed=1)
        start = (d.x, d.y)
        out = d.step()
        assert (d.x, d.y) != start or any("bump" in line for line in out)
        d.turn_left()
        assert d.status()["facing"] in ("north", "east", "south", "west")
        d.turn_right()
        d.turn_right()

    def test_automap_only_shows_seen_tiles(self):
        d = blobber_crawl.Delve(blobber_crawl.DEMO_MAP, seed=1)
        m = d.automap()
        assert "@" in m
        # unseen tiles are blank, not walls
        assert " " in m

    def test_search_reveals_trap(self):
        d = blobber_crawl.Delve("#####\n#...#\n#.^.#\n#...#\n#####\n", seed=1)
        d.x, d.y, d.facing = 1, 1, 2  # stand south of... place near trap
        d.x, d.y = 2, 1
        d._update_sight()
        out = d.search()
        assert any("trap" in line for line in out)

    def test_attrition_ticks_and_torch_burns(self):
        d = blobber_crawl.Delve("#####\n#...#\n#####\n", seed=1)
        burn0 = d.torch_burn
        d.turn_left()
        assert d.torch_burn < burn0

    def test_open_door_consumes_key(self):
        d = blobber_crawl.Delve("#######\n#..D..#\n#######\n", seed=1)
        d.x, d.y, d.facing = 2, 1, 1  # face east toward the door
        out = d.open_door()
        assert any("swings open" in line for line in out)
        assert d.keys == 0
        out = d.step()
        assert (d.x, d.y) == (3, 1)

    def test_treasure_gives_gold(self):
        d = blobber_crawl.Delve("#####\n#.T.#\n#####\n", seed=1)
        d.x, d.y, d.facing = 1, 1, 1
        d.step()
        assert d.gold > 0


# ------------------------------------------------------------ cheat_codes.py
class TestCheatCodes:
    def test_patch_intercepts_matching_read(self):
        bus = cheat_codes.MemoryBus(256)
        cart = cheat_codes.CheatCartridge(bus)
        bus.poke(0x10, 2)
        code = cheat_codes.PatchCode(address=0x10, compare=2, replace=9)
        cart.add(code)
        assert cart.read(0x10) == 9
        assert bus.raw_read(0x10) == 2  # memory itself untouched

    def test_no_match_passes_through(self):
        bus = cheat_codes.MemoryBus(256)
        cart = cheat_codes.CheatCartridge(bus)
        bus.poke(0x10, 5)
        cart.add(cheat_codes.PatchCode(address=0x10, compare=2, replace=9))
        assert cart.read(0x10) == 5
        assert cart.fired == []

    def test_encode_decode_roundtrip(self):
        code = cheat_codes.PatchCode(address=0x1234, compare=0xAB, replace=0xCD)
        s = code.encode()
        assert len(s) == 9
        back = cheat_codes.PatchCode.decode(s)
        assert back == code

    def test_typo_rejected_by_checksum(self):
        code = cheat_codes.PatchCode(address=0x00FF, compare=2, replace=3)
        s = code.encode()
        alpha = cheat_codes._ALPHABET
        bad = alpha[(alpha.index(s[0]) + 1) % 16] + s[1:]
        with pytest.raises(ValueError):
            cheat_codes.PatchCode.decode(bad)

    def test_infinite_lives_dial(self):
        bus = cheat_codes.MemoryBus()
        cart = cheat_codes.CheatCartridge(bus)
        cart.apply_dial(cheat_codes.DIALS["infinite_lives"])
        bus.poke(0x00FF, 2)  # lives decremented to 2
        assert cart.read(0x00FF) == 3
        bus.poke(0x00FF, 0)
        assert cart.read(0x00FF) == 3
        assert len(cart.fired) == 2


# ----------------------------------------------------------- rts_campaigns.py
class TestRtsCampaigns:
    def test_orders_train_build_research(self):
        camp = rts_campaigns.demo_campaign()
        sk = camp.start_mission(0, seed=7)
        sk.sides["player"].supply = 1000  # rich start: exercise every order kind
        assert sk.issue("player", rts_campaigns.Order("build", "barracks")) == "ok"
        assert sk.issue("player", rts_campaigns.Order("train", "soldier", 2)) == "ok"
        assert sk.sides["player"].units["soldier"] == 2
        assert (
            sk.issue("player", rts_campaigns.Order("research", "sharpshooters")) == "ok"
        )
        assert "sharpshooters" in sk.sides["player"].tech

    def test_trigger_fires_on_tech(self):
        camp = rts_campaigns.demo_campaign()
        sk = camp.start_mission(0, seed=7)
        sk.issue("player", rts_campaigns.Order("research", "sharpshooters"))
        sk.tick()
        assert any("marksmen" in line for line in sk.log)

    def test_tech_carries_across_missions(self):
        camp = rts_campaigns.demo_campaign()
        sk = camp.start_mission(0, seed=7)
        sk.issue("player", rts_campaigns.Order("research", "sharpshooters"))
        # force a win to complete the mission
        sk.sides["ai"].units.clear()
        sk.tick()
        assert sk.won
        assert camp.complete(sk, 0) is True
        sk2 = camp.start_mission(1, seed=7)
        assert "sharpshooters" in sk2.sides["player"].tech

    def test_ai_acts_through_same_issue_path(self):
        camp = rts_campaigns.demo_campaign()
        sk = camp.start_mission(0, seed=7)
        ai_units_before = dict(sk.sides["ai"].units)
        for _ in range(6):
            sk.tick()
        # AI followed its build order: it should have changed state legally
        assert sk.sides["ai"].units != ai_units_before or sk.sides["ai"].buildings.get(
            "barracks"
        )

    def test_attack_can_win_mission(self):
        camp = rts_campaigns.demo_campaign()
        sk = camp.start_mission(0, seed=7)
        sk.issue("player", rts_campaigns.Order("build", "barracks"))
        sk.issue("player", rts_campaigns.Order("train", "soldier", 8))
        for _ in range(30):
            sk.issue("player", rts_campaigns.Order("attack"))
            sk.tick()
            if sk.won or sk.lost:
                break
        assert sk.won or sk.sides["ai"].army_strength() < 12


# ----------------------------------------------------------- indie_channel.py
class TestIndieChannel:
    def test_register_submit_review_ship(self):
        ch = indie_channel.Channel()
        ch.register_creator("ada")
        ch.register_creator("bob")
        ch.register_creator("cy")
        gid = ch.submit("Pixel Quest", "ada", 1, "a tiny adventure")
        assert ch.review(gid, "bob", "pass", "fun!").startswith("Review recorded")
        assert ch.review(gid, "cy", "pass").startswith("Review recorded")
        msg = ch.review(gid, "ada", "pass")  # own game: rejected as reviewer
        assert "own game" in msg
        ch.register_creator("dan")
        msg = ch.review(gid, "dan", "pass")
        assert "ships at $1" in msg
        assert ch.games[gid].status == "shipped"

    def test_rejects_kill_a_game(self):
        ch = indie_channel.Channel()
        for name in ("ada", "bob", "cy"):
            ch.register_creator(name)
        gid = ch.submit("Bad Game", "ada", 3)
        ch.review(gid, "bob", "reject", "broken")
        msg = ch.review(gid, "cy", "reject", "also broken")
        assert "rejected" in msg
        assert ch.games[gid].status == "rejected"

    def test_buy_pays_creator_share(self):
        ch = indie_channel.Channel(revenue_share=0.70)
        for name in ("ada", "bob", "cy", "dan"):
            ch.register_creator(name)
        gid = ch.submit("Pixel Quest", "ada", 5)
        for r in ("bob", "cy", "dan"):
            ch.review(gid, r, "pass")
        ch.buy(gid)
        ch.buy(gid)
        payout = ch.payout("ada")
        assert payout == pytest.approx(2 * 5 * 0.70)

    def test_bad_price_rejected(self):
        ch = indie_channel.Channel()
        ch.register_creator("ada")
        with pytest.raises(ValueError):
            ch.submit("Expensive", "ada", 999)

    def test_rate_and_report(self):
        ch = indie_channel.Channel()
        for name in ("ada", "bob", "cy", "dan"):
            ch.register_creator(name)
        gid = ch.submit("Pixel Quest", "ada", 1)
        for r in ("bob", "cy", "dan"):
            ch.review(gid, r, "pass")
        ch.buy(gid)
        ch.rate(gid, 5)
        ch.rate(gid, 3)
        assert ch.games[gid].avg_rating == 4.0
        rep = ch.channel_report()
        assert rep["games_shipped"] == 1
        assert rep["total_sales"] == 1


# ---------------------------------------------------------------- story_vm.py
class TestStoryVm:
    def test_full_walkthrough_wins(self):
        s = story_vm.demo_story()
        s.run("examine doormat")
        assert s.flags.get("found_key") is True
        s.run("take brass key")
        assert "key" in s.inventory
        s.run("use key with door")
        assert s.flags.get("door_open") is True
        s.run("go north")
        assert s.loc == "hall"
        s.run("go up")
        assert s.loc == "attic"
        s.run("open chest")
        assert "lantern" in s.inventory
        out = s.run("use lantern")
        assert s.won is True and s.over is True
        assert any("YOU WIN" in line for line in out)

    def test_locked_exit_blocks(self):
        s = story_vm.demo_story()
        out = s.run("go north")
        assert s.loc == "porch"
        assert any("locked" in line for line in out)

    def test_unknown_verb_names_word(self):
        s = story_vm.demo_story()
        out = s.run("dance wildly")
        assert any("'dance'" in line for line in out)

    def test_undo_restores_state(self):
        s = story_vm.demo_story()
        s.run("examine doormat")
        assert s.flags.get("found_key") is True
        out = s.run("undo")
        assert any("Undone" in line for line in out)
        assert s.flags.get("found_key") is not True
        assert s.objects["key"]["at"] is None

    def test_save_load_roundtrip(self):
        s = story_vm.demo_story()
        s.run("examine doormat")
        s.run("take brass key")
        snap = s.save()
        s2 = story_vm.demo_story()
        s2.load(snap)
        assert "key" in s2.inventory
        s2.run("use key with door")
        assert s2.flags.get("door_open") is True

    def test_hints_fire_from_rules(self):
        s = story_vm.demo_story()
        out = s.run("look")
        assert any("doormat" in line for line in out)


# -------------------------------------------------------------- turn_relay.py
class TestTurnRelay:
    def test_genesis_submit_verify_chain(self, tmp_path):
        r = turn_relay.demo_relay(str(tmp_path))
        r.genesis({"pile": 21}, ["ann", "bob"])
        r.submit("ann", {"take": 3})
        r.submit("bob", {"take": 2})
        assert r.latest().n == 2
        assert r.latest().state["pile"] == 16
        rep = r.verify()
        assert rep.ok is True
        assert rep.turns_checked == 3

    def test_turn_order_enforced(self, tmp_path):
        r = turn_relay.demo_relay(str(tmp_path))
        r.genesis({"pile": 21}, ["ann", "bob"])
        with pytest.raises(ValueError, match="turn"):
            r.submit("bob", {"take": 1})  # ann goes first

    def test_illegal_move_rejected(self, tmp_path):
        r = turn_relay.demo_relay(str(tmp_path))
        r.genesis({"pile": 21}, ["ann", "bob"])
        with pytest.raises(ValueError, match="illegal move"):
            r.submit("ann", {"take": 9})

    def test_tamper_detected(self, tmp_path):
        r = turn_relay.demo_relay(str(tmp_path))
        r.genesis({"pile": 21}, ["ann", "bob"])
        r.submit("ann", {"take": 3})
        r.submit("bob", {"take": 2})
        # tamper with a MIDDLE turn's envelope on disk (the last turn's
        # prev_hash still commits to the original bytes, so the link breaks)
        p = os.path.join(str(tmp_path), "turn-0001.json")
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        data["move"] = {"take": 1, "seat": "ann"}
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        r2 = turn_relay.demo_relay(str(tmp_path))
        rep = r2.verify()
        assert rep.ok is False
        assert rep.broken_at == 2

    def test_missing_turn_detected(self, tmp_path):
        r = turn_relay.demo_relay(str(tmp_path))
        r.genesis({"pile": 21}, ["ann", "bob"])
        r.submit("ann", {"take": 3})
        r.submit("bob", {"take": 3})
        os.remove(os.path.join(str(tmp_path), "turn-0001.json"))
        # renumber turn 2 -> 1 to simulate a dropped turn with renumbering
        os.rename(
            os.path.join(str(tmp_path), "turn-0002.json"),
            os.path.join(str(tmp_path), "turn-0001.json"),
        )
        r2 = turn_relay.demo_relay(str(tmp_path))
        rep = r2.verify()
        assert rep.ok is False  # hash chain no longer links

    def test_demo_game_can_finish(self, tmp_path):
        r = turn_relay.demo_relay(str(tmp_path))
        r.genesis({"pile": 4}, ["ann", "bob"])
        r.submit("ann", {"take": 3})
        r.submit("bob", {"take": 1})
        assert r.latest().state["winner"] == "bob"
        with pytest.raises(ValueError, match="already over"):
            r.submit("ann", {"take": 1})
