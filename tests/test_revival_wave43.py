"""Tests for revival wave 43: identity & self-expression.

Covers numeric_identity, wire_identity, mail_personalities,
handmade_page, top8_list, skins, testimonials, six_second_loop.
"""

import pytest

from levi.revival import (
    handmade_page,
    mail_personalities,
    numeric_identity,
    six_second_loop,
    skins,
    testimonials,
    top8_list,
    wire_identity,
)


# ---------------------------------------------------------------- numeric_identity
class TestNumericIdentity:
    def test_claim_assigns_sequential_unreused_uins(self):
        d = numeric_identity.NumericIdentityDirectory()
        a = d.claim("alice")
        b = d.claim("bob")
        assert a.uin != b.uin
        assert a.uin + 1 == b.uin

    def test_spool_holds_message_until_drain(self):
        d = numeric_identity.NumericIdentityDirectory()
        a = d.claim("alice")
        b = d.claim("bob")
        rec = d.send(a.uin, b.uin, "hey")
        assert rec is not None  # bob is offline
        assert d.spooled_count(b.uin) == 1
        waiting = d.drain_spool(b.uin)
        assert [m.body for m in waiting] == ["hey"]
        assert d.spooled_count(b.uin) == 0

    def test_online_recipient_gets_no_spool_record(self):
        d = numeric_identity.NumericIdentityDirectory()
        a = d.claim("alice")
        b = d.claim("bob")
        b.set_presence("online")
        assert d.send(a.uin, b.uin, "yo") is None

    def test_spool_spills_oldest_first(self):
        d = numeric_identity.NumericIdentityDirectory()
        a = d.claim("alice")
        b = d.claim("bob")
        for i in range(numeric_identity.SPOOL_CAP + 5):
            d.send(a.uin, b.uin, f"msg-{i}")
        waiting = d.drain_spool(b.uin)
        assert len(waiting) == numeric_identity.SPOOL_CAP
        assert waiting[0].body == "msg-5"  # oldest spilled

    def test_room_fans_out_and_lists_unreachable(self):
        d = numeric_identity.NumericIdentityDirectory()
        a, b, c = d.claim("a"), d.claim("b"), d.claim("c")
        a.set_presence("online")
        d.open_room("hq", [a.uin, b.uin, c.uin])
        unreachable = d.room_say("hq", a.uin, "roll call")
        assert sorted(unreachable) == sorted([b.uin, c.uin])
        assert d.spooled_count(b.uin) == 1

    def test_file_transfer_record_tracks_progress(self):
        d = numeric_identity.NumericIdentityDirectory()
        a = d.claim("alice")
        b = d.claim("bob")
        rec = d.send_file(a.uin, b.uin, "mix.mp3", 1000)
        rec.progress(400)
        assert not rec.complete
        rec.progress(600)
        assert rec.complete
        with pytest.raises(numeric_identity.DirectoryError):
            d.send_file(a.uin, b.uin, "x", 0)

    def test_unknown_uin_rejected(self):
        d = numeric_identity.NumericIdentityDirectory()
        with pytest.raises(numeric_identity.DirectoryError):
            d.lookup(999999)


# ------------------------------------------------------------------ wire_identity
class TestWireIdentity:
    def _line(self):
        line = wire_identity.TelexLine()
        tx_a = wire_identity.Station("NYC")
        tx_a.program("NYC STOCK DESK 1138")
        tx_b = wire_identity.Station("CHI")
        tx_b.program("CHI FLOOR 2 4091")
        line.attach(tx_a)
        line.attach(tx_b)
        return line

    def test_wru_prints_answerback_on_both_ends(self):
        line = self._line()
        strikes = line.transmit("NYC", "CHI", "WRU")
        nyc_paper = line.station("NYC").paper
        chi_paper = line.station("CHI").paper
        assert any("CHI FLOOR 2 4091" in p for p in nyc_paper)
        assert any("CHI FLOOR 2 4091" in p for p in chi_paper)
        assert len(strikes) == 2

    def test_plain_traffic_reaches_far_end_only(self):
        line = self._line()
        line.transmit("NYC", "CHI", "HELLO")
        assert line.station("CHI").paper == ["NYC: HELLO"]
        assert line.station("NYC").paper == []

    def test_unprogrammed_drum_refuses_wru(self):
        line = wire_identity.TelexLine()
        a = wire_identity.Station("A")
        b = wire_identity.Station("B")  # no answerback programmed
        line.attach(a)
        line.attach(b)
        with pytest.raises(wire_identity.WireError):
            line.transmit("A", "B", "WRU")

    def test_blank_answerback_rejected(self):
        s = wire_identity.Station("X")
        with pytest.raises(wire_identity.WireError):
            s.program("   ")

    def test_down_line_blocks_traffic(self):
        line = self._line()
        line.station("CHI").line_up = False
        with pytest.raises(wire_identity.WireError):
            line.transmit("NYC", "CHI", "HELLO")


# ------------------------------------------------------------- mail_personalities
class TestMailPersonalities:
    def _post(self):
        post = mail_personalities.PersonalityPost()
        acct = post.add_account("dana@example.com")
        acct.add_personality(
            mail_personalities.Personality(
                name="work",
                display_name="Dana (Acme Support)",
                signature="-- Dana, Acme",
            )
        )
        acct.add_personality(
            mail_personalities.Personality(name="personal", display_name="Dana")
        )
        return post

    def test_compose_picks_personality_inline(self):
        post = self._post()
        msg = post.compose(
            "dana@example.com", "work", "boss@acme.com", "Re: ticket", "done"
        )
        assert msg.from_personality == "work"
        assert msg.display_from == "Dana (Acme Support)"
        assert msg.signature_used == "-- Dana, Acme"

    def test_no_personality_falls_back_to_default(self):
        post = self._post()
        msg = post.compose("dana@example.com", None, "x@y.z", "hi", "body")
        assert msg.from_personality == "work"  # first added = default

    def test_sent_by_attribution_survives(self):
        post = self._post()
        post.compose("dana@example.com", "personal", "friend@z.z", "yo", "hey")
        post.compose("dana@example.com", "work", "boss@acme.com", "t", "b")
        assert len(post.sent_by("personal")) == 1
        assert len(post.sent_by("work")) == 1

    def test_duplicate_personality_rejected(self):
        post = self._post()
        acct = post._accounts["dana@example.com"]
        with pytest.raises(mail_personalities.PersonalityError):
            acct.add_personality(
                mail_personalities.Personality(name="WORK", display_name="Someone Else")
            )

    def test_cannot_remove_last_personality(self):
        post = mail_personalities.PersonalityPost()
        acct = post.add_account("solo@example.com")
        acct.add_personality(
            mail_personalities.Personality(name="only", display_name="Solo")
        )
        with pytest.raises(mail_personalities.PersonalityError):
            acct.remove_personality("only")


# ------------------------------------------------------------------ handmade_page
class TestHandmadePage:
    def test_script_and_handlers_are_stripped(self):
        page = handmade_page.HandmadePage(owner="amy", title="amy's corner")
        page.add_section(
            "about", "<p>hi</p><script>alert(1)</script><b onclick='x()'>yo</b>"
        )
        out = page.render()
        assert "<script" not in out
        assert "onclick" not in out
        assert "<p>hi</p>" in out
        assert "<b>yo</b>" in out

    def test_remote_urls_never_fetched_or_kept(self):
        page = handmade_page.HandmadePage(owner="amy")
        kept = page.set_css(
            "body { color: red; }\n.bg { background: url(http://evil/x.png); }"
        )
        assert "url(" not in kept
        assert "color: red" in kept

    def test_restack_requires_every_section_exactly_once(self):
        page = handmade_page.HandmadePage(owner="amy")
        page.add_section("a", "<p>A</p>")
        page.add_section("b", "<p>B</p>")
        page.restack(["b", "a"])
        assert page.layout == ["b", "a"]
        with pytest.raises(handmade_page.PageError):
            page.restack(["a"])  # missing b

    def test_render_orders_sections_by_layout(self):
        page = handmade_page.HandmadePage(owner="amy")
        page.add_section("a", "<p>A</p>")
        page.add_section("b", "<p>B</p>")
        page.restack(["b", "a"])
        out = page.render()
        assert out.index('data-name="b"') < out.index('data-name="a"')

    def test_duplicate_section_rejected(self):
        page = handmade_page.HandmadePage(owner="amy")
        page.add_section("a", "<p>A</p>")
        with pytest.raises(handmade_page.PageError):
            page.add_section("A", "<p>dup</p>")


# --------------------------------------------------------------------- top8_list
class TestTop8List:
    def _list(self):
        tl = top8_list.TopList(owner="amy")
        for n in ["bea", "cyd", "dan"]:
            tl.add(n)
        return tl

    def test_add_returns_rank(self):
        tl = top8_list.TopList(owner="amy")
        assert tl.add("bea") == 1
        assert tl.add("cyd") == 2

    def test_capacity_enforced(self):
        tl = top8_list.TopList(owner="amy", capacity=2)
        tl.add("a")
        tl.add("b")
        with pytest.raises(top8_list.TopListError):
            tl.add("c")

    def test_move_and_history_recorded(self):
        tl = self._list()
        tl.move("dan", 1)
        assert tl.as_list()[0] == "dan"
        assert tl.rank("dan") == 1
        assert any(c.action == "move" for c in tl.history())

    def test_pinned_slot_refuses_move(self):
        tl = self._list()
        tl.pin("bea")
        with pytest.raises(top8_list.TopListError):
            tl.move("bea", 3)
        tl.unpin("bea")
        tl.move("bea", 3)
        assert tl.rank("bea") == 3

    def test_declaration_reads_like_a_statement(self):
        tl = self._list()
        tl.pin("bea")
        text = tl.declaration()
        assert "amy's top 8" in text
        assert "1. bea *" in text


# ------------------------------------------------------------------------ skins
class TestSkins:
    def _skin(self):
        return skins.Skin(
            name="midnight",
            author="jay",
            colors={
                "background": "#000000",
                "foreground": "#ffffff",
                "accent": "#ff00ff",
                "border": "#333333",
                "highlight": "#ffff00",
            },
            glyphs={"play": "▶"},
            border_style="double",
        )

    def test_install_and_apply(self):
        reg = skins.SkinRegistry()
        reg.install(self._skin())
        active = reg.apply("midnight")
        assert active.name == "midnight"
        assert reg.active().author == "jay"

    def test_missing_role_rejected(self):
        with pytest.raises(skins.SkinError):
            skins.Skin(name="broken", author="x", colors={"background": "#000000"})

    def test_bad_color_rejected(self):
        colors = {
            "background": "#000000",
            "foreground": "white",  # not hex
            "accent": "#ff00ff",
            "border": "#333333",
            "highlight": "#ffff00",
        }
        with pytest.raises(skins.SkinError):
            skins.Skin(name="bad", author="x", colors=colors)

    def test_duplicate_install_rejected(self):
        reg = skins.SkinRegistry()
        reg.install(self._skin())
        with pytest.raises(skins.SkinError):
            reg.install(self._skin())

    def test_preview_mentions_skin_and_roles(self):
        reg = skins.SkinRegistry()
        reg.install(self._skin())
        out = reg.preview("MIDNIGHT")  # case-insensitive lookup
        assert "midnight" in out
        assert "#ff00ff" in out
        assert "heuristic" in out  # contrast note is labeled honestly


# ----------------------------------------------------------------- testimonials
class TestTestimonials:
    def _board(self):
        b = testimonials.TestimonialBoard()
        b.register("amy")
        b.register("bea")
        return b

    def test_write_then_approve_shows(self):
        b = self._board()
        b.write("bea", "amy", "Amy fixed my bike in the rain.")
        assert b.shown("amy") == []
        assert len(b.pending("amy")) == 1
        b.approve("amy", "bea")
        assert len(b.shown("amy")) == 1
        assert b.shown("amy")[0].approved

    def test_one_attestation_per_author_per_profile(self):
        b = self._board()
        b.write("bea", "amy", "first")
        with pytest.raises(testimonials.TestimonialError):
            b.write("BEA", "amy", "second")  # case-insensitive duplicate

    def test_decline_removes_pending(self):
        b = self._board()
        b.write("bea", "amy", "meh")
        b.decline("amy", "bea")
        assert b.pending("amy") == []
        assert b.shown("amy") == []

    def test_retract_pulls_live_attestation(self):
        b = self._board()
        b.write("bea", "amy", "great")
        b.approve("amy", "bea")
        b.retract("bea", "amy")
        assert b.shown("amy") == []
        actions = [e.action for e in b.ledger("amy")]
        assert actions == ["wrote", "approved", "retracted"]

    def test_ledger_tracks_reputational_cost(self):
        b = self._board()
        b.write("bea", "amy", "kind")
        b.approve("amy", "bea")
        assert b.vouched_for("bea") == ["amy"]
        entries = b.ledger()
        assert all(e.author == "bea" and e.profile == "amy" for e in entries)


# -------------------------------------------------------------- six_second_loop
class TestSixSecondLoop:
    def _clip(self):
        clip = six_second_loop.LoopClip(
            title="the door", seam_note="the door slams -> cut to the door"
        )
        clip.add_beat(0.5, "setup", "someone knocks twice")
        clip.add_beat(2.0, "twist", "the door is already open")
        clip.add_beat(4.5, "payoff", "it's a mirror")
        return clip

    def test_arc_complete_in_order(self):
        assert self._clip().arc_complete()

    def test_beat_beyond_cap_rejected(self):
        with pytest.raises(six_second_loop.LoopError):
            six_second_loop.Beat(at=7.0, phase="setup", description="too late")

    def test_play_unrolls_loops_with_seam(self):
        out = self._clip().play(loops=2)
        assert out.count("-- loop") == 2
        assert "↺ seam:" in out

    def test_seam_requires_note_and_complete_arc(self):
        clip = six_second_loop.LoopClip(title="x")
        clip.add_beat(1.0, "setup", "a")
        with pytest.raises(six_second_loop.LoopError):
            clip.check_seam()

    def test_tighten_drops_grace_beats_only(self):
        clip = self._clip()
        clip.add_beat(5.5, "grace", "a lingering look")
        lean = clip.tighten()
        assert all(b.phase != "grace" for b in lean.beats)
        assert lean.arc_complete()
        assert len(clip.beats) == 4  # original untouched
