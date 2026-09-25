"""Tests for LEVI hunt-methods wave 5 (batch E).

Covers: mason, worksong, measures, blobber, rtscampaign.
One test class per module: the core mechanism AND every deny-closed
rejection (pytest.raises(ValueError)).
"""

import pytest

from levi.methods import blobber, mason, measures, rtscampaign, worksong


# ---------------------------------------------------------------------------
# mason — two-tier signaling: the Word proves membership, not skill
# ---------------------------------------------------------------------------


class TestMason:
    def _lodge(self):
        lodge = mason.MembershipAuth()
        alice = lodge.register("Alice", "A-mark")
        return lodge, alice

    def test_word_authenticates_member_but_not_skill(self):
        lodge, alice = self._lodge()
        token = lodge.issue_word(alice.id)
        assert lodge.authenticate(token.word).id == alice.id
        # The Word says nothing about skill: no demonstration, no competence.
        assert lodge.competent(alice.id, "stone-hewing") is False

    def test_demonstration_proves_skill_separately(self):
        lodge, alice = self._lodge()
        token = lodge.issue_word(alice.id)
        lodge.authenticate(token.word)
        demo = lodge.demonstrate(alice.id, "stone-hewing")
        assert demo.member_id == alice.id
        assert lodge.competent(alice.id, "stone-hewing") is True
        assert lodge.competent(alice.id, "carving") is False

    def test_work_marks_drive_piece_rate_pay(self):
        lodge, alice = self._lodge()
        bob = lodge.register("Bob", "B-mark")
        lodge.attribute_piece("p1", alice.id, "dressed ashlar")
        lodge.attribute_piece("p2", alice.id, "dressed ashlar")
        lodge.attribute_piece("p3", bob.id, "rough block")
        assert {p.id for p in lodge.pieces_of(alice.id)} == {"p1", "p2"}
        assert lodge.pay_ledger() == {"Alice": 2, "Bob": 1}

    def test_rejects_empty_names_and_marks(self):
        lodge = mason.MembershipAuth()
        with pytest.raises(ValueError):
            lodge.register("", "mark")
        with pytest.raises(ValueError):
            lodge.register("   ", "mark")
        with pytest.raises(ValueError):
            lodge.register("Alice", "")
        with pytest.raises(ValueError):
            lodge.register("Alice", "  ")

    def test_rejects_duplicate_names_and_marks(self):
        lodge, _ = self._lodge()
        with pytest.raises(ValueError):
            lodge.register("alice", "other-mark")  # case-insensitive
        with pytest.raises(ValueError):
            lodge.register("Carol", "A-mark")

    def test_rejects_unknown_member_ids(self):
        lodge, alice = self._lodge()
        for call in (
            lambda: lodge.member("nope"),
            lambda: lodge.issue_word("nope"),
            lambda: lodge.demonstrate("nope", "hewing"),
            lambda: lodge.competent("nope", "hewing"),
            lambda: lodge.attribute_piece("p9", "nope", "stone"),
            lambda: lodge.pieces_of("nope"),
        ):
            with pytest.raises(ValueError):
                call()

    def test_rejects_unknown_word(self):
        lodge, _ = self._lodge()
        with pytest.raises(ValueError):
            lodge.authenticate("COWAN-FAKE")

    def test_rejects_empty_skill(self):
        lodge, alice = self._lodge()
        with pytest.raises(ValueError):
            lodge.demonstrate(alice.id, "  ")
        with pytest.raises(ValueError):
            lodge.competent(alice.id, "")

    def test_rejects_bad_pieces(self):
        lodge, alice = self._lodge()
        lodge.attribute_piece("p1", alice.id, "ashlar")
        with pytest.raises(ValueError):
            lodge.attribute_piece("p1", alice.id, "another")  # duplicate id
        with pytest.raises(ValueError):
            lodge.attribute_piece("", alice.id, "ashlar")
        with pytest.raises(ValueError):
            lodge.attribute_piece("p2", alice.id, "")


# ---------------------------------------------------------------------------
# worksong — metered verse encodes procedures; recall walks the meter
# ---------------------------------------------------------------------------


class TestWorksong:
    def _singer(self):
        # 4 beats per line, 2 lines per chunk.
        return worksong.RhythmChunk(beats_per_line=4, lines_per_chunk=2)

    def _steps(self):
        return [
            "haul the line taut",
            "tie the knot fast",
            "coil the rope neat",
            "stow the gear below",
        ]

    def test_encode_decode_roundtrip_exact(self):
        singer = self._singer()
        steps = self._steps()
        verse = singer.encode(steps)
        assert singer.decode(verse) == steps
        # Fixed beats per chunk: 2 lines x 4 beats = 8.
        for chunk in verse.chunks:
            assert sum(line.beats for line in chunk.lines) == 8

    def test_tempo_marks_work_phase(self):
        singer = self._singer()
        verse = singer.encode(self._steps())
        assert singer.tempo(verse) == [worksong.CALL, worksong.RESPONSE]
        recall = singer.recall(verse)
        assert [phase for phase, _, _ in recall] == [
            worksong.CALL,
            worksong.CALL,
            worksong.RESPONSE,
            worksong.RESPONSE,
        ]
        assert [action for _, action, _ in recall] == [
            "rest",
            "rest",
            "pull",
            "pull",
        ]
        assert [text for _, _, text in recall] == self._steps()

    def test_rejects_bad_meter_params(self):
        with pytest.raises(ValueError):
            worksong.RhythmChunk(beats_per_line=0)
        with pytest.raises(ValueError):
            worksong.RhythmChunk(lines_per_chunk=-1)
        with pytest.raises(ValueError):
            worksong.RhythmChunk(beats_per_line="four")

    def test_rejects_empty_or_bad_steps(self):
        singer = self._singer()
        with pytest.raises(ValueError):
            singer.encode([])
        with pytest.raises(ValueError):
            singer.encode(["haul the line taut", ""])
        with pytest.raises(ValueError):
            singer.encode(["haul the line taut", 42])

    def test_rejects_step_that_does_not_scan(self):
        singer = self._singer()
        with pytest.raises(ValueError):
            singer.encode(["haul the line", "tie the knot fast"])

    def test_rejects_steps_not_filling_whole_chunks(self):
        singer = self._singer()
        with pytest.raises(ValueError):
            singer.encode(["haul the line taut"])  # 1 step, chunks of 2

    def test_decode_rejects_malformed_verse(self):
        singer = self._singer()
        good = singer.encode(self._steps())

        def line(text, beats):
            return worksong.VerseLine(text=text, beats=beats)

        # Wrong phase order on chunk 0.
        bad = worksong.Verse(
            chunks=(worksong.VerseChunk(lines=good.chunks[0].lines, phase="response"),),
            beats_per_line=4,
            lines_per_chunk=2,
        )
        with pytest.raises(ValueError):
            singer.decode(bad)
        # Chunk with the wrong line count.
        bad = worksong.Verse(
            chunks=(worksong.VerseChunk(lines=good.chunks[0].lines[:1], phase="call"),),
            beats_per_line=4,
            lines_per_chunk=2,
        )
        with pytest.raises(ValueError):
            singer.decode(bad)
        # Line whose beat claim doesn't match its words.
        bad = worksong.Verse(
            chunks=(
                worksong.VerseChunk(
                    lines=(line("haul the line taut", 99), line("x y z w", 4)),
                    phase="call",
                ),
            ),
            beats_per_line=4,
            lines_per_chunk=2,
        )
        with pytest.raises(ValueError):
            singer.decode(bad)
        # Line that doesn't scan to the verse meter.
        bad = worksong.Verse(
            chunks=(
                worksong.VerseChunk(
                    lines=(line("haul the line", 3), line("x y z w", 4)),
                    phase="call",
                ),
            ),
            beats_per_line=4,
            lines_per_chunk=2,
        )
        with pytest.raises(ValueError):
            singer.decode(bad)
        # Empty verse.
        with pytest.raises(ValueError):
            singer.decode(
                worksong.Verse(chunks=(), beats_per_line=4, lines_per_chunk=2)
            )


# ---------------------------------------------------------------------------
# measures — the ten-system conversion ladder
# ---------------------------------------------------------------------------


class TestMeasures:
    def _ladder(self):
        return measures.ConversionLadder()

    def test_all_ten_systems_present(self):
        ladder = self._ladder()
        assert set(ladder.systems()) == {
            "egyptian",
            "barleycorn",
            "roman",
            "survey",
            "ell",
            "toise",
            "russian",
            "weight",
            "cask",
            "braccio",
        }

    def test_grounded_factors_within_each_system(self):
        ladder = self._ladder()
        assert ladder.convert(1, "royal_cubit", "digit", "egyptian") == 28
        assert ladder.convert(1, "palm", "digit", "egyptian") == 4
        assert ladder.convert(1, "inch", "barleycorn", "barleycorn") == 3
        assert ladder.convert(1, "yard", "foot", "barleycorn") == 3
        assert ladder.convert(5.5, "yard", "perch", "barleycorn") == pytest.approx(1)
        assert ladder.convert(1, "pes", "uncia", "roman") == 12
        assert ladder.convert(1, "pes", "digitus", "roman") == 16
        assert ladder.convert(1, "actus", "pes", "roman") == 120
        assert ladder.convert(1, "chain", "link", "survey") == 100
        assert ladder.convert(1, "rod", "foot", "survey") == pytest.approx(16.5)
        assert ladder.convert(1, "furlong", "rod", "survey") == 40
        assert ladder.convert(1, "english_cloth_ell", "inch", "ell") == 45
        assert ladder.convert(1, "scots_ell", "inch", "ell") == 37
        assert ladder.convert(1, "flemish_ell", "inch", "ell") == 27
        assert ladder.convert(1, "toise", "pied_du_roi", "toise") == 6
        assert ladder.convert(1, "toise", "ligne", "toise") == 864
        assert ladder.convert(1, "arshin", "vershok", "russian") == 16
        assert ladder.convert(1, "sazhen", "arshin", "russian") == 3
        assert ladder.convert(1, "verst", "sazhen", "russian") == 500
        assert ladder.convert(1, "mina", "shekel", "weight") == 60
        assert ladder.convert(1, "talent", "mina", "weight") == 60
        assert ladder.convert(1, "mina", "drachma", "weight") == pytest.approx(100)
        assert ladder.convert(1, "drachma", "obol", "weight") == pytest.approx(6)
        assert ladder.convert(1, "firkin", "gallon", "cask") == 9
        assert ladder.convert(1, "tun", "gallon", "cask") == 216
        assert ladder.convert(1, "hogshead", "gallon", "cask") == 54
        assert ladder.convert(1, "butt", "puncheon", "cask") == pytest.approx(1.5)

    def test_metric_canonical_factors(self):
        ladder = self._ladder()
        value, unit = ladder.to_metric(1, "royal_cubit", "egyptian")
        assert unit == "m" and value == pytest.approx(0.524)
        value, unit = ladder.to_metric(1, "toise", "toise")
        assert unit == "m" and value == pytest.approx(1.949)
        value, unit = ladder.to_metric(1, "arshin", "russian")
        assert unit == "m" and value == pytest.approx(0.7112)
        value, unit = ladder.to_metric(1, "pes", "roman")
        assert unit == "m" and value == pytest.approx(0.296)
        value, unit = ladder.to_metric(1, "talent", "weight")
        assert unit == "g" and value == pytest.approx(3600 * 8.3)
        value, unit = ladder.to_metric(1, "milan_braccio", "braccio")
        assert unit == "m" and value == pytest.approx(0.595)
        # Metric round-trip.
        assert ladder.from_metric(1.949, "toise", "toise") == pytest.approx(1)

    def test_cross_system_via_metric(self):
        ladder = self._ladder()
        # A barleycorn yard in survey feet: 3 ft.
        assert ladder.convert_cross(
            1, "yard", "barleycorn", "foot", "survey"
        ) == pytest.approx(3)
        # Milan braccio in English cloth ells: 59.5 cm / 114.3 cm.
        assert ladder.convert_cross(
            1, "milan_braccio", "braccio", "english_cloth_ell", "ell"
        ) == pytest.approx(59.5 / 114.3)
        # Venice wool vs silk arms really differ.
        assert ladder.convert_cross(
            1, "venice_wool_braccio", "braccio", "venice_silk_braccio", "braccio"
        ) == pytest.approx(68.3 / 63.8)

    def test_rejects_unknown_system_and_unit(self):
        ladder = self._ladder()
        with pytest.raises(ValueError):
            ladder.units("smoot")
        with pytest.raises(ValueError):
            ladder.convert(1, "digit", "smoot", "egyptian")
        with pytest.raises(ValueError):
            ladder.convert(1, "digit", "digit", "smoot")
        with pytest.raises(ValueError):
            ladder.to_metric(1, "digit", "smoot")
        with pytest.raises(ValueError):
            ladder.dimension("smoot")

    def test_rejects_bad_values(self):
        ladder = self._ladder()
        for bad in ("3", None, True, float("nan"), float("inf")):
            with pytest.raises(ValueError):
                ladder.convert(bad, "digit", "palm", "egyptian")

    def test_rejects_cross_dimension(self):
        ladder = self._ladder()
        with pytest.raises(ValueError):
            ladder.convert_cross(1, "mina", "weight", "toise", "toise")


# ---------------------------------------------------------------------------
# blobber — step/turn movement, tile LoS, attrition across the delve
# ---------------------------------------------------------------------------


OPEN_GRID = [
    "#####",
    "#S..#",
    "#...#",
    "#...#",
    "#####",
]


class TestBlobber:
    def test_step_turn_and_facing(self):
        delve = blobber.GridDelve(OPEN_GRID)
        assert delve.position().facing == "N"
        delve.turn_right()
        assert delve.position().facing == "E"
        delve.turn_right()
        assert delve.position().facing == "S"
        delve.turn_left()
        assert delve.position().facing == "E"
        delve.step_forward()  # (1,1) -> (1,2)
        assert (delve.position().row, delve.position().col) == (1, 2)
        delve.step_backward()  # back to (1,1)
        assert (delve.position().row, delve.position().col) == (1, 1)

    def test_bump_into_wall_raises_and_is_side_effect_free(self):
        delve = blobber.GridDelve(OPEN_GRID, torches=5, rations=5)
        with pytest.raises(ValueError):
            delve.step_forward()  # facing N into the north wall
        assert delve.supplies() == {"torches": 5, "rations": 5}
        assert delve.moves_made() == 0
        assert (delve.position().row, delve.position().col) == (1, 1)

    def test_line_of_sight_and_mapping(self):
        grid = [
            "#######",
            "#S....#",
            "###.###",
            "#.....#",
            "#######",
        ]
        delve = blobber.GridDelve(grid)
        seen = delve.visible()
        assert (1, 1) in seen and (1, 4) in seen  # open corridor
        assert (3, 3) not in seen  # hidden behind the wall row
        assert (2, 1) in seen  # the blocking wall tile itself is seen
        mapped_before = delve.mapped()
        delve.turn_right()
        delve.step_forward()
        assert delve.mapped() > mapped_before  # mapping accumulates

    def test_render_known_hides_unseen(self):
        grid = [
            "#######",
            "#S....#",
            "###.###",
            "#.....#",
            "#######",
        ]
        delve = blobber.GridDelve(grid)
        rendered = delve.render_known()
        assert len(rendered) == 5 and all(len(r) == 7 for r in rendered)
        assert rendered[1][1] == "@"  # the party
        assert rendered[1][2] == "."  # seen corridor floor
        assert rendered[3][3] == " "  # behind the wall row: unmapped

    def test_attrition_ticks_per_move(self):
        delve = blobber.GridDelve(OPEN_GRID, torches=10, rations=10)
        delve.turn_right()  # a turn burns a torch, not a ration
        assert delve.supplies() == {"torches": 9, "rations": 10}
        delve.step_forward()  # a step burns both
        assert delve.supplies() == {"torches": 8, "rations": 9}

    def test_darkness_and_hunger_end_the_delve(self):
        delve = blobber.GridDelve(OPEN_GRID, torches=1, rations=1)
        delve.turn_right()  # last torch
        with pytest.raises(ValueError):
            delve.step_forward()  # no torches left: no moving
        hungry = blobber.GridDelve(OPEN_GRID, torches=5, rations=0)
        hungry.turn_right()
        with pytest.raises(ValueError):
            hungry.step_forward()  # no rations: cannot march
        # ...but turning (no marching) still works while torches last.
        hungry.turn_left()
        assert hungry.supplies()["torches"] == 3

    def test_rejects_bad_grids(self):
        with pytest.raises(ValueError):
            blobber.GridDelve([])
        with pytest.raises(ValueError):
            blobber.GridDelve(["###", "#"])  # ragged
        with pytest.raises(ValueError):
            blobber.GridDelve(["###", "#.#", "###"])  # no start
        with pytest.raises(ValueError):
            blobber.GridDelve(["###", "SSS", "###"])  # two starts
        with pytest.raises(ValueError):
            blobber.GridDelve(["###", "#X#", "###"])  # unknown tile

    def test_rejects_negative_supplies(self):
        with pytest.raises(ValueError):
            blobber.GridDelve(OPEN_GRID, torches=-1)
        with pytest.raises(ValueError):
            blobber.GridDelve(OPEN_GRID, rations=-2)

    def test_tile_out_of_range_raises(self):
        delve = blobber.GridDelve(OPEN_GRID)
        with pytest.raises(ValueError):
            delve.tile(99, 99)


# ---------------------------------------------------------------------------
# rtscampaign — trigger scripts, tech trees, a seeded offline opponent
# ---------------------------------------------------------------------------


class TestRtscampaign:
    def _campaign(self):
        engine = rtscampaign.CampaignEngine()
        engine.add_mission("first-contact")
        engine.add_trigger(
            "first-contact",
            "scout-arrives",
            lambda facts: facts.get("scouts_sent", 0) >= 2,
            "cutscene: the valley revealed",
        )
        engine.add_trigger(
            "first-contact",
            "base-falls",
            lambda facts: facts.get("enemy_base_hp", 100) <= 0,
            "victory fanfare",
        )
        return engine

    def test_trigger_fires_event_when_condition_met(self):
        engine = self._campaign()
        engine.start_mission("first-contact")
        assert engine.advance("first-contact", {"scouts_sent": 1}) == []
        fired = engine.advance("first-contact", {"scouts_sent": 2})
        assert fired == ["cutscene: the valley revealed"]
        assert engine.event_log() == [
            ("first-contact", "scout-arrives", "cutscene: the valley revealed")
        ]
        # Once-triggers fire exactly once.
        assert engine.advance("first-contact", {"scouts_sent": 5}) == []

    def test_missions_run_in_order(self):
        engine = self._campaign()
        engine.add_mission("counterattack")
        with pytest.raises(ValueError):
            engine.start_mission("counterattack")  # first-contact unfinished
        engine.start_mission("first-contact")
        engine.finish_mission("first-contact")
        engine.start_mission("counterattack")  # now allowed
        assert engine.pending_triggers("counterattack") == []

    def test_rejects_bad_scripting(self):
        engine = rtscampaign.CampaignEngine()
        with pytest.raises(ValueError):
            engine.add_mission("")
        engine.add_mission("m1")
        with pytest.raises(ValueError):
            engine.add_mission("m1")  # duplicate
        engine.add_trigger("m1", "t1", lambda f: True, "e1")
        with pytest.raises(ValueError):
            engine.add_trigger("m1", "t1", lambda f: True, "e2")  # duplicate
        with pytest.raises(ValueError):
            engine.add_trigger("m1", "", lambda f: True, "e")
        with pytest.raises(ValueError):
            engine.add_trigger("m1", "t2", lambda f: True, "")
        with pytest.raises(ValueError):
            engine.add_trigger("m1", "t2", "not-callable", "e")
        with pytest.raises(ValueError):
            engine.add_trigger("nope", "t", lambda f: True, "e")  # unknown

    def test_rejects_bad_mission_transitions(self):
        engine = self._campaign()
        with pytest.raises(ValueError):
            engine.start_mission("nope")
        with pytest.raises(ValueError):
            engine.advance("first-contact", {})  # not started
        with pytest.raises(ValueError):
            engine.finish_mission("first-contact")  # not started
        engine.start_mission("first-contact")
        with pytest.raises(ValueError):
            engine.start_mission("first-contact")  # already started
        with pytest.raises(ValueError):
            engine.add_trigger("first-contact", "late", lambda f: True, "e")
        with pytest.raises(ValueError):
            engine.advance("first-contact", "not-a-dict")
        engine.finish_mission("first-contact")
        with pytest.raises(ValueError):
            engine.finish_mission("first-contact")  # already finished
        with pytest.raises(ValueError):
            engine.advance("first-contact", {})  # finished

    def test_trigger_condition_errors_are_deny_closed(self):
        engine = rtscampaign.CampaignEngine()
        engine.add_mission("m")
        engine.add_trigger("m", "boom", lambda f: 1 / 0, "e")
        engine.start_mission("m")
        with pytest.raises(ValueError):
            engine.advance("m", {})

    def test_tech_tree_gates_unlocks_behind_prerequisites(self):
        tree = rtscampaign.TechTree()
        tree.add_node("masonry")
        tree.add_node("engineering", ("masonry",))
        tree.add_node("siege", ("engineering",))
        with pytest.raises(ValueError):
            tree.unlock("siege")  # gated
        tree.unlock("masonry")
        assert tree.available() == ["engineering"]
        tree.unlock("engineering")
        tree.unlock("siege")
        assert tree.unlocked() == ["masonry", "engineering", "siege"]
        assert tree.available() == []

    def test_rejects_bad_tech_nodes(self):
        tree = rtscampaign.TechTree()
        with pytest.raises(ValueError):
            tree.add_node("")
        tree.add_node("masonry")
        with pytest.raises(ValueError):
            tree.add_node("masonry")  # duplicate
        with pytest.raises(ValueError):
            tree.add_node("archery", ("fletching",))  # unknown prereq
        with pytest.raises(ValueError):
            tree.unlock("nope")  # unknown
        tree.unlock("masonry")
        with pytest.raises(ValueError):
            tree.unlock("masonry")  # already unlocked

    def test_ai_opponent_is_deterministic_and_seeded(self):
        build = ["worker", "barracks", "soldier"]
        ai1 = rtscampaign.AIOpponent(seed=7, build_order=build)
        ai2 = rtscampaign.AIOpponent(seed=7, build_order=build)
        seq1 = [ai1.decide(t) for t in range(10)]
        seq2 = [ai2.decide(t) for t in range(10)]
        assert seq1 == seq2  # same seed: identical decisions
        assert seq1[:3] == ["build:worker", "build:barracks", "build:soldier"]
        ai1.reset()
        assert [ai1.decide(t) for t in range(10)] == seq1

    def test_ai_opponent_reacts_to_facts(self):
        ai = rtscampaign.AIOpponent(seed=1, build_order=["worker"])
        assert ai.decide(0, {"under_attack": True}) == "defend_base"
        assert ai.decide(0, {"enemy_weak": True}) == "attack"
        # Defense outranks the build order.
        assert ai.decide(0, {"under_attack": True, "enemy_weak": True}) == "defend_base"

    def test_rejects_bad_ai_inputs(self):
        with pytest.raises(ValueError):
            rtscampaign.AIOpponent(seed="seven", build_order=["worker"])
        with pytest.raises(ValueError):
            rtscampaign.AIOpponent(seed=True, build_order=["worker"])
        with pytest.raises(ValueError):
            rtscampaign.AIOpponent(seed=1, build_order=[])
        with pytest.raises(ValueError):
            rtscampaign.AIOpponent(seed=1, build_order=[""])
        ai = rtscampaign.AIOpponent(seed=1, build_order=["worker"])
        with pytest.raises(ValueError):
            ai.decide(-1)
        with pytest.raises(ValueError):
            ai.decide("zero")
