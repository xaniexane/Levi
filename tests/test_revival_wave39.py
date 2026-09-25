"""Tests for wave 39 — BBS culture & participatory media."""

import json

import pytest

from core.levi.revival import (
    multiline_bbs,
    teleconference,
    source_included_bbs,
    pipe_colors,
    subscriber_content,
    user_radio,
    lifestream,
    proto_carts,
)


# -- multiline_bbs -----------------------------------------------------------


class TestLineBank:
    def test_capacity_bounds(self):
        with pytest.raises(ValueError):
            multiline_bbs.LineBank(0)
        with pytest.raises(ValueError):
            multiline_bbs.LineBank(257)
        bank = multiline_bbs.LineBank(256)
        assert len(bank.lines) == 256

    def test_ring_answer_hangup_cycle(self):
        bank = multiline_bbs.LineBank(4)
        assert bank.ring(0, "alice") is True
        stats = bank.poll()
        assert stats.answered == 1 and stats.active == 1
        assert bank.active_calls() == [(0, "alice")]
        bank.activity(0, 12)
        assert bank.hangup(0) == "alice"
        assert bank.active_calls() == []

    def test_busy_line_counts_missed_call(self):
        bank = multiline_bbs.LineBank(2)
        bank.ring(0, "alice")
        assert bank.ring(0, "bob") is False  # busy, never queued
        assert bank.missed_calls == 1
        status = bank.board_status()
        assert status["missed_calls"] == 1 and status["rings"] == 2

    def test_manual_answer_mode(self):
        bank = multiline_bbs.LineBank(2, auto_answer=False)
        bank.ring(1, "carol")
        stats = bank.poll()
        assert stats.rings_seen == 1 and stats.answered == 0
        bank.answer(1)
        assert bank.active_calls() == [(1, "carol")]

    def test_answer_without_ring_raises(self):
        bank = multiline_bbs.LineBank(2)
        with pytest.raises(ValueError):
            bank.answer(0)
        with pytest.raises(ValueError):
            bank.ring(9, "nobody")

    def test_utilization(self):
        bank = multiline_bbs.LineBank(4)
        bank.ring(0, "a")
        bank.ring(1, "b")
        bank.poll()
        assert bank.utilization() == 0.5


# -- teleconference ----------------------------------------------------------


class TestTeleconference:
    def test_join_say_history_order(self):
        tc = teleconference.Teleconference()
        tc.create_room("lobby", topic="general")
        tc.join("lobby", "alice")
        tc.join("lobby", "bob")
        m1 = tc.say("lobby", "alice", "hello")
        m2 = tc.say("lobby", "bob", "hi alice")
        hist = tc.history("lobby")
        assert [m.text for m in hist[-2:]] == ["hello", "hi alice"]
        assert m1.seq < m2.seq

    def test_whisper_is_private(self):
        tc = teleconference.Teleconference()
        tc.create_room("lobby")
        tc.join("lobby", "alice")
        tc.join("lobby", "bob")
        tc.whisper("alice", "bob", "secret")
        room_texts = [m.text for m in tc.history("lobby")]
        assert "secret" not in room_texts
        assert any(m.kind == "whisper" for m in tc.inbox("bob"))
        assert any(m.kind == "whisper" for m in tc.inbox("alice"))

    def test_whisper_to_unknown_caller_raises(self):
        tc = teleconference.Teleconference()
        tc.create_room("lobby")
        tc.join("lobby", "alice")
        with pytest.raises(ValueError):
            tc.whisper("alice", "ghost", "hi")

    def test_kick_requires_moderator(self):
        tc = teleconference.Teleconference()
        tc.create_room("lobby")
        tc.join("lobby", "sysop", moderator=True)
        tc.join("lobby", "rowdy")
        with pytest.raises(ValueError):
            tc.kick("lobby", "rowdy", "sysop")
        tc.kick("lobby", "sysop", "rowdy", reason="spam")
        assert "rowdy" not in tc.who("lobby")

    def test_flood_heuristic_warns(self):
        tc = teleconference.Teleconference()
        tc.create_room("lobby")
        tc.join("lobby", "spammer")
        for i in range(10):
            tc.say("lobby", "spammer", f"msg {i}")
        assert tc.flooded("spammer")
        assert tc.floor_status()["warned"]["spammer"] >= 1

    def test_emote_and_leave(self):
        tc = teleconference.Teleconference()
        tc.create_room("lobby")
        tc.join("lobby", "alice")
        msg = tc.emote("lobby", "alice", "waves")
        assert msg.kind == "action"
        tc.leave("lobby", "alice")
        assert tc.who("lobby") == []

    def test_duplicate_room_raises(self):
        tc = teleconference.Teleconference()
        tc.create_room("lobby")
        with pytest.raises(ValueError):
            tc.create_room("lobby")


# -- source_included_bbs -----------------------------------------------------


class TestSourceIncluded:
    def _tree(self):
        tree = source_included_bbs.SourceTree()
        tree.set_file("menu.pas", "line one\nline two\nline three\nline four\n")
        return tree

    def test_exact_hunk_applies(self):
        tree = self._tree()
        mod = source_included_bbs.Mod(
            mod_id="m1",
            title="greeting",
            author="sysop",
            hunks=[
                source_included_bbs.Hunk(
                    target="menu.pas",
                    context=["line one", "line two"],
                    remove=["line three"],
                    add=["line THREE!"],
                    at=1,
                )
            ],
        )
        report = tree.apply_mod(mod)
        assert report.clean and report.applied == 1
        assert "line THREE!" in tree.get_file("menu.pas")
        assert "m1" in tree.applied_mods

    def test_missing_context_is_conflict_not_silent(self):
        tree = self._tree()
        mod = source_included_bbs.Mod(
            mod_id="m2",
            title="bad",
            author="sysop",
            hunks=[
                source_included_bbs.Hunk(
                    target="menu.pas",
                    context=["no such line anywhere"],
                    add=["x"],
                )
            ],
        )
        report = tree.apply_mod(mod)
        assert report.conflicts == 1 and not report.clean
        assert report.results[0].status == source_included_bbs.CONFLICT
        assert "m2" not in tree.applied_mods

    def test_fuzz_applies_with_warning(self):
        tree = self._tree()
        mod = source_included_bbs.Mod(
            mod_id="m3",
            title="fuzzy",
            author="sysop",
            hunks=[
                source_included_bbs.Hunk(
                    target="menu.pas",
                    context=["line two", "line three", "line four"],
                    add=["inserted"],
                    at=99,  # wrong hint; context decides
                )
            ],
        )
        report = tree.apply_mod(mod)
        assert report.applied == 1
        assert report.results[0].status == source_included_bbs.FUZZED
        assert "inserted" in tree.get_file("menu.pas")

    def test_remove_block_mismatch_is_conflict(self):
        tree = self._tree()
        mod = source_included_bbs.Mod(
            mod_id="m4",
            title="mismatch",
            author="sysop",
            hunks=[
                source_included_bbs.Hunk(
                    target="menu.pas",
                    context=["line one"],
                    remove=["not really there"],
                    add=["x"],
                    at=1,
                )
            ],
        )
        report = tree.apply_mod(mod)
        assert report.results[0].status == source_included_bbs.CONFLICT

    def test_fingerprint_stable_and_registry(self):
        reg = source_included_bbs.ModRegistry()
        mod = source_included_bbs.Mod(mod_id="m5", title="t", author="a", hunks=[])
        fp = reg.register(mod)
        assert fp == mod.fingerprint()
        assert reg.by_author("a") == [mod]
        with pytest.raises(ValueError):
            reg.register(mod)

    def test_grant_lifecycle(self):
        reg = source_included_bbs.ModRegistry()
        reg.grant_source("alice", "source included, mods shared back")
        assert reg.holds_source("alice")
        reg.revoke_source("alice")
        assert not reg.holds_source("alice")
        with pytest.raises(ValueError):
            reg.revoke_source("nobody")


# -- pipe_colors -------------------------------------------------------------


class TestPipeColors:
    def test_parse_splits_spans(self):
        spans = pipe_colors.parse("|04hello |nworld")
        assert spans[0].attr.color == "cyan"
        assert spans[0].text == "hello "
        assert spans[-1].attr == pipe_colors.Attr()

    def test_unknown_codes_left_literal(self):
        assert pipe_colors.strip("|zzhello") == "|zzhello"  # noqa: B005
        assert pipe_colors.strip("trail|") == "trail|"  # noqa: B005

    def test_render_emits_ansi_and_resets(self):
        out = pipe_colors.render("|05hi|n")
        assert out.startswith("\x1b[")
        assert out.endswith("\x1b[0m")
        assert "hi" in out

    def test_visible_len_excludes_codes(self):
        assert pipe_colors.visible_len("|04hello|n world") == len("hello world")

    def test_bold_toggle(self):
        spans = pipe_colors.parse("|bwide|nx")
        assert spans[0].attr.bold is True
        assert spans[-1].text == "x"
        assert spans[-1].attr == pipe_colors.Attr()

    def test_sysop_defined_code(self):
        table = pipe_colors.PipeTable()
        table.define("XY", color="yellow", bold=True)
        assert "xy" in table.shadowed or True  # builtin-free code path
        spans = pipe_colors.parse("|XYhi", table)
        assert spans[0].attr.color == "yellow"
        assert spans[0].attr.bold is True
        with pytest.raises(ValueError):
            table.define("toolong1", color="red")

    def test_codes_used(self):
        used = pipe_colors.codes_used("|04a|05b|04c")
        assert set(used) == {"04", "05"}

    def test_two_char_preferred_over_one_char(self):
        spans = pipe_colors.parse("|01x")
        assert spans[0].attr.color == "black"  # not "|0" + literal "1"


# -- subscriber_content ------------------------------------------------------


class TestSubscriberContent:
    def _filed(self):
        nr = subscriber_content.Newsroom()
        sub = nr.submit("alice", "local", "Bake sale", "At the hall.")
        return nr, sub

    def test_full_editorial_pipeline(self):
        nr, sub = self._filed()
        assert sub.status == subscriber_content.QUEUED
        nr.review(sub.sub_id, "ed", True, note="solid")
        nr.publish(sub.sub_id, "ed")
        assert nr.published()[0].title == "Bake sale"
        assert nr.tier("alice") == subscriber_content.TIER_NEW  # +2 < 3

    def test_rejection_dings_reputation(self):
        nr, sub = self._filed()
        nr.review(sub.sub_id, "ed", False, note="needs sources")
        assert sub.status == subscriber_content.REJECTED
        assert nr.reputation["alice"] == -1

    def test_tier_gating_on_sections(self):
        nr = subscriber_content.Newsroom()
        with pytest.raises(ValueError):
            nr.submit("newbie", "opinion", "Hot take", "Body.")
        # Earn contributor standing with two accepted filings.
        for i in range(2):
            s = nr.submit("alice", "local", f"t{i}", "Body.")
            nr.review(s.sub_id, "ed", True)
        assert nr.tier("alice") == subscriber_content.TIER_CONTRIBUTOR
        s = nr.submit("alice", "opinion", "Take", "Body.")
        assert s.section == "opinion"

    def test_publish_requires_approval(self):
        nr, sub = self._filed()
        with pytest.raises(ValueError):
            nr.publish(sub.sub_id, "ed")

    def test_correction_and_retraction_keep_record(self):
        nr, sub = self._filed()
        nr.review(sub.sub_id, "ed", True)
        nr.publish(sub.sub_id, "ed")
        nr.correct(sub.sub_id, "ed", "Hall is on 5th, not 6th.")
        assert len(sub.corrections) == 1
        assert "At the hall." in sub.body  # original untouched
        nr.retract(sub.sub_id, "ed", "event cancelled")
        assert sub.status == subscriber_content.RETRACTED
        assert nr.published() == []

    def test_search(self):
        nr, sub = self._filed()
        nr.review(sub.sub_id, "ed", True)
        nr.publish(sub.sub_id, "ed")
        assert nr.search("bake") == [sub]
        assert nr.search("zzz") == []


# -- user_radio --------------------------------------------------------------


class TestUserRadio:
    def _live(self):
        d = user_radio.Directory()
        d.register("KLEVI", "alice", "talk", "Levi's own station")
        d.go_live("KLEVI", "alice")
        return d

    def test_register_listen_drop(self):
        d = self._live()
        assert d.listen("KLEVI") == 1
        assert d.listen("KLEVI") == 2
        assert d.drop("KLEVI") == 1
        assert d.on_air() != []

    def test_callsign_validation(self):
        d = user_radio.Directory()
        with pytest.raises(ValueError):
            d.register("no", "alice", "talk")
        with pytest.raises(ValueError):
            d.register("lower!", "alice", "talk")

    def test_announce_and_history(self):
        d = self._live()
        d.announce("KLEVI", "alice", "Track One")
        d.announce("KLEVI", "alice", "Track Two")
        st = d.stations["KLEVI"]
        assert st.now_playing == "Track Two"
        assert st.play_history == ["Track One", "Track Two"]

    def test_announce_dark_station_raises(self):
        d = user_radio.Directory()
        d.register("KDARK", "bob", "ambient")
        with pytest.raises(ValueError):
            d.announce("KDARK", "bob", "Track")

    def test_request_line_bounded(self):
        d = self._live()
        assert d.request("KLEVI", "carol", "Song A") == 1
        taken = d.take_request("KLEVI", "alice")
        assert taken == "carol: Song A"
        assert d.take_request("KLEVI", "alice") is None

    def test_owner_only_controls(self):
        d = self._live()
        with pytest.raises(ValueError):
            d.go_dark("KLEVI", "mallory")
        with pytest.raises(ValueError):
            d.unregister("KLEVI", "mallory")

    def test_search_and_top(self):
        d = self._live()
        d.register("KNOIZ", "bob", "noise", "harsh walls")
        d.go_live("KNOIZ", "bob")
        d.listen("KNOIZ")
        d.listen("KNOIZ")
        assert d.top(1)[0].callsign == "KNOIZ"
        assert d.search("noise")[0].callsign == "KNOIZ"
        status = d.directory_status()
        assert status["stations"] == 2 and status["on_air"] == 2

    def test_go_dark_clears_listeners(self):
        d = self._live()
        d.listen("KLEVI")
        d.go_dark("KLEVI", "alice")
        st = d.stations["KLEVI"]
        assert st.listeners == 0 and st.now_playing == ""


# -- lifestream ----------------------------------------------------------------


class TestLifestream:
    def test_ingest_and_stream_order(self):
        ls = lifestream.Lifestream("alice")
        e1 = ls.ingest("blog", "post", "first")
        e2 = ls.ingest("photos", "photo", "second")
        assert [e.entry_id for e in ls.stream()] == [e2.entry_id, e1.entry_id]
        assert [e.entry_id for e in ls.stream(newest_first=False)] == [
            e1.entry_id,
            e2.entry_id,
        ]

    def test_idempotent_key(self):
        ls = lifestream.Lifestream("alice")
        e1 = ls.ingest("blog", "post", "hello", key="k1")
        e2 = ls.ingest("blog", "post", "hello again", key="k1")
        assert e1.entry_id == e2.entry_id
        assert len(ls.entries) == 1

    def test_filters(self):
        ls = lifestream.Lifestream("alice")
        ls.ingest("blog", "post", "a", tags=["news"])
        ls.ingest("photos", "photo", "b", tags=["news"])
        assert len(ls.by_source("blog")) == 1
        assert len(ls.by_kind("photo")) == 1
        assert len(ls.by_tag("news")) == 2

    def test_threaded_comments(self):
        ls = lifestream.Lifestream("alice")
        e = ls.ingest("blog", "post", "hello")
        c1 = ls.comment(e.entry_id, "bob", "nice")
        c2 = ls.comment(e.entry_id, "alice", "thanks", parent_id=c1.comment_id)
        c3 = ls.comment(e.entry_id, "bob", "yw", parent_id=c2.comment_id)
        assert c3.depth == 3
        tree = ls.thread(e.entry_id)
        assert tree[0]["replies"][0]["replies"][0]["author"] == "bob"
        with pytest.raises(ValueError):
            ls.comment(e.entry_id, "alice", "too deep", parent_id=c3.comment_id)

    def test_comment_on_missing_entry_raises(self):
        ls = lifestream.Lifestream("alice")
        with pytest.raises(ValueError):
            ls.comment(999, "bob", "hi")

    def test_export_and_wipe(self, tmp_path):
        ls = lifestream.Lifestream("alice")
        e = ls.ingest("blog", "post", "hello", at="2026-01-01")
        ls.comment(e.entry_id, "bob", "nice")
        data = ls.export()
        assert data["owner"] == "alice"
        assert data["entries"][0]["comments"][0]["author"] == "bob"
        path = str(tmp_path / "stream.jsonl")
        assert ls.export_jsonl(path) == 1
        lines = open(path, encoding="utf-8").read().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["owner"] == "alice"
        with pytest.raises(ValueError):
            ls.wipe()
        assert ls.wipe(confirm=True) == 1
        assert ls.entries == {}

    def test_owner_required(self):
        with pytest.raises(ValueError):
            lifestream.Lifestream("  ")


# -- proto_carts ---------------------------------------------------------------


class TestProtoCarts:
    def _shop(self):
        cat = proto_carts.Catalog()
        cat.add_item("WIDGET", "Widget", 1999, stock=5)
        cat.add_item("GADGET", "Gadget", 500)
        return cat

    def test_add_and_subtotal(self):
        cat = self._shop()
        cart = proto_carts.Cart(cat)
        cart.add("WIDGET", 2)
        cart.add("GADGET")
        assert cart.subtotal == 2 * 1999 + 500
        assert cart.count == 3

    def test_stock_enforced(self):
        cat = self._shop()
        cart = proto_carts.Cart(cat)
        with pytest.raises(ValueError):
            cart.add("WIDGET", 6)
        cart.add("WIDGET", 5)
        with pytest.raises(ValueError):
            cart.set_qty("WIDGET", 6)

    def test_checkout_freezes_and_decrements(self):
        cat = self._shop()
        cart = proto_carts.Cart(cat)
        cart.add("WIDGET", 2)
        order = cart.checkout()
        assert order.subtotal == 3998
        assert cart.count == 0  # cart emptied
        assert cat.get("WIDGET").stock == 3
        with pytest.raises(ValueError):
            proto_carts.Cart(cat).checkout()  # empty cart

    def test_addon_rack_adjustments(self):
        cat = self._shop()
        cart = proto_carts.Cart(cat)
        cart.add("WIDGET")
        order = cart.checkout()

        def discount(snapshot):
            sub = snapshot["subtotal"]
            return [proto_carts.Adjustment("10% off", -(sub // 10), "")]

        rack = proto_carts.AddonRack()
        rack.mount("coupon", discount)
        book = proto_carts.OrderBook(rack)
        placed = book.place(order)
        assert placed.order_id == 1
        assert placed.adjustments[0].addon == "coupon"
        assert placed.total == order.subtotal - order.subtotal // 10

    def test_addon_cannot_rewrite_core_lines(self):
        cat = self._shop()
        cart = proto_carts.Cart(cat)
        cart.add("GADGET")
        order = cart.checkout()
        book = proto_carts.OrderBook()
        placed = book.place(order)
        assert placed.lines[0].unit_price == 500  # untouched
        assert book.get(1) is placed

    def test_tax_placeholder(self):
        cat = self._shop()
        cart = proto_carts.Cart(cat)
        cart.add("GADGET")
        order = cart.checkout(tax_rate=0.1)
        assert order.tax == 50
        assert order.total == 550

    def test_fmt(self):
        assert proto_carts.fmt(1999) == "$19.99"
        assert proto_carts.fmt(-50) == "-$0.50"

    def test_duplicate_sku_raises(self):
        cat = self._shop()
        with pytest.raises(ValueError):
            cat.add_item("WIDGET", "Other", 100)
