"""Hermetic tests for hunt-wave batch C (8 methods).

Modules: fleet, tiers, daemons, graffiti, piemenu, folksonomy, cap,
splitscreen.

Hermetic: pure in-memory, no I/O, no network, deterministic. Stdlib only.
"""

import pytest

from core.levi.methods import (
    cap,
    daemons,
    fleet,
    folksonomy,
    graffiti,
    piemenu,
    splitscreen,
    tiers,
)


def _full_fleet(task="Ship the slice"):
    fl = fleet.DelegationFleet()
    fl.lock(task)
    fl.submit("architect", "interfaces: A talks to B")
    fl.submit("builder", "smallest slice: a working A")
    fl.submit("redteam", "weakness: B has no timeout")
    fl.submit("scopesentry", "out of scope: rewriting C")
    fl.submit("scribe", "digest: five lines")
    return fl


class TestDelegationFleet:
    def test_full_cycle_lock_roles_report_terminated(self):
        fl = _full_fleet()
        assert fl.pending_roles() == []
        report = fl.report()
        assert "# Ship the slice" in report
        for role in fleet.ROLES:
            assert f"## {role}" in report
        # role order is preserved in the folded report
        positions = [report.index(f"## {r}") for r in fleet.ROLES]
        assert positions == sorted(positions)
        assert "interfaces: A talks to B" in report
        assert fl.is_terminated

    def test_exactly_five_fixed_roles(self):
        assert fleet.ROLES == (
            "architect",
            "builder",
            "redteam",
            "scopesentry",
            "scribe",
        )

    def test_second_use_refused_after_termination(self):
        fl = _full_fleet()
        fl.report()
        with pytest.raises(ValueError):
            fl.lock("another task")
        with pytest.raises(ValueError):
            fl.submit("architect", "more")
        with pytest.raises(ValueError):
            fl.report()
        with pytest.raises(ValueError):
            fl.pending_roles()

    def test_deny_empty_task_title(self):
        fl = fleet.DelegationFleet()
        with pytest.raises(ValueError):
            fl.lock("")
        with pytest.raises(ValueError):
            fl.lock("   ")

    def test_deny_lock_twice(self):
        fl = fleet.DelegationFleet()
        fl.lock("task one")
        with pytest.raises(ValueError):
            fl.lock("task two")

    def test_deny_submit_before_lock(self):
        fl = fleet.DelegationFleet()
        with pytest.raises(ValueError):
            fl.submit("architect", "section")

    def test_deny_unknown_role(self):
        fl = fleet.DelegationFleet()
        fl.lock("task")
        with pytest.raises(ValueError):
            fl.submit("janitor", "section")

    def test_deny_duplicate_role_submit(self):
        fl = fleet.DelegationFleet()
        fl.lock("task")
        fl.submit("architect", "section")
        with pytest.raises(ValueError):
            fl.submit("architect", "another section")

    def test_deny_empty_section(self):
        fl = fleet.DelegationFleet()
        fl.lock("task")
        with pytest.raises(ValueError):
            fl.submit("architect", "")
        with pytest.raises(ValueError):
            fl.submit("architect", "   ")

    def test_deny_report_before_all_five(self):
        fl = fleet.DelegationFleet()
        fl.lock("task")
        fl.submit("architect", "section")
        with pytest.raises(ValueError):
            fl.report()
        assert not fl.is_terminated

    def test_deny_report_without_lock(self):
        fl = fleet.DelegationFleet()
        with pytest.raises(ValueError):
            fl.report()


class TestTieredMemory:
    def test_put_get_per_tier(self):
        mem = tiers.TieredMemory()
        mem.put("core", "no-free-core", "entry is paid but tiny")
        mem.put("recall", "digest-12", "session summary")
        mem.put("archival", "origin-2018", "first prototype")
        assert mem.get("core", "no-free-core").value == "entry is paid but tiny"
        assert mem.tier_of("digest-12") == "recall"
        assert mem.counts() == {"core": 1, "recall": 1, "archival": 1}

    def test_promote_recall_to_core(self):
        mem = tiers.TieredMemory()
        mem.put("recall", "standing-rule", "commit locally")
        item = mem.promote("standing-rule")
        assert item.tier == "core"
        assert mem.tier_of("standing-rule") == "core"

    def test_demote_recall_to_archival(self):
        mem = tiers.TieredMemory()
        mem.put("recall", "old-digest", "matured pattern")
        item = mem.demote("old-digest")
        assert item.tier == "archival"
        assert mem.tier_of("old-digest") == "archival"

    def test_core_cap_refuses(self):
        mem = tiers.TieredMemory(core_cap=1)
        mem.put("core", "first", "1")
        with pytest.raises(ValueError):
            mem.put("core", "second", "2")
        with pytest.raises(ValueError):
            mem.promote("nothing-there")

    def test_recall_cap_evicts_oldest(self):
        mem = tiers.TieredMemory(recall_cap=2)
        mem.put("recall", "a", "1")
        mem.put("recall", "b", "2")
        mem.put("recall", "c", "3")  # evicts "a"
        assert mem.tier_of("a") is None
        assert mem.keys("recall") == ["b", "c"]

    def test_archival_evicts_oldest(self):
        mem = tiers.TieredMemory(archival_cap=1)
        mem.put("archival", "old", "1")
        mem.put("archival", "older", "2")
        assert mem.keys("archival") == ["older"]

    def test_deny_unknown_tier(self):
        mem = tiers.TieredMemory()
        with pytest.raises(ValueError):
            mem.put("limbo", "k", "v")
        with pytest.raises(ValueError):
            mem.get("limbo", "k")
        with pytest.raises(ValueError):
            mem.remove("limbo", "k")

    def test_deny_empty_key(self):
        mem = tiers.TieredMemory()
        with pytest.raises(ValueError):
            mem.put("core", "", "v")
        with pytest.raises(ValueError):
            mem.put("core", "   ", "v")

    def test_deny_duplicate_key_in_tier(self):
        mem = tiers.TieredMemory()
        mem.put("core", "k", "1")
        with pytest.raises(ValueError):
            mem.put("core", "k", "2")

    def test_deny_get_unknown_key(self):
        mem = tiers.TieredMemory()
        with pytest.raises(ValueError):
            mem.get("core", "missing")

    def test_deny_promote_not_in_recall(self):
        mem = tiers.TieredMemory()
        mem.put("archival", "k", "v")
        with pytest.raises(ValueError):
            mem.promote("k")  # archival -> core is not allowed
        with pytest.raises(ValueError):
            mem.promote("missing")

    def test_deny_demote_not_in_recall(self):
        mem = tiers.TieredMemory()
        mem.put("core", "k", "v")
        with pytest.raises(ValueError):
            mem.demote("k")  # demote runs recall -> archival only

    def test_deny_remove_from_archival(self):
        mem = tiers.TieredMemory()
        mem.put("archival", "k", "v")
        with pytest.raises(ValueError):
            mem.remove("archival", "k")
        # but core/recall removals are fine
        mem.put("core", "c", "v")
        removed = mem.remove("core", "c")
        assert removed.key == "c"

    def test_deny_remove_unknown_key(self):
        mem = tiers.TieredMemory()
        with pytest.raises(ValueError):
            mem.remove("core", "missing")

    def test_deny_bad_caps(self):
        with pytest.raises(ValueError):
            tiers.TieredMemory(core_cap=0)
        with pytest.raises(ValueError):
            tiers.TieredMemory(recall_cap=-3)


class TestDaemonRegistry:
    def _registry(self):
        reg = daemons.DaemonRegistry()
        reg.register("locks", owns="locks", wake="on-demand", visible=lambda ctx: True)
        reg.register(
            "digest",
            owns="summaries",
            wake="hourly",
            visible=lambda ctx: ctx.get("session_ended", False),
        )
        return reg

    def test_dispatch_routes_to_owner(self):
        reg = self._registry()
        assert reg.dispatch("locks").name == "locks"
        assert reg.dispatch("summaries").name == "digest"

    def test_surface_when_visible_rule_allows(self):
        reg = self._registry()
        assert reg.surface("locks", "payload") == "payload"
        assert reg.surface("digest", "summary", {"session_ended": True}) == "summary"

    def test_surface_denied_when_rule_denies(self):
        reg = self._registry()
        with pytest.raises(ValueError):
            reg.surface("digest", "summary", {"session_ended": False})
        with pytest.raises(ValueError):
            reg.surface("digest", "summary")

    def test_deny_empty_name(self):
        reg = daemons.DaemonRegistry()
        with pytest.raises(ValueError):
            reg.register("", owns="x", wake="hourly", visible=lambda c: True)

    def test_deny_duplicate_name(self):
        reg = self._registry()
        with pytest.raises(ValueError):
            reg.register("locks", owns="other", wake="hourly", visible=lambda c: True)

    def test_deny_empty_owns(self):
        reg = daemons.DaemonRegistry()
        with pytest.raises(ValueError):
            reg.register("d", owns="  ", wake="hourly", visible=lambda c: True)

    def test_deny_overlapping_domain(self):
        reg = self._registry()
        with pytest.raises(ValueError):
            reg.register("locks2", owns="locks", wake="hourly", visible=lambda c: True)

    def test_deny_empty_wake(self):
        reg = daemons.DaemonRegistry()
        with pytest.raises(ValueError):
            reg.register("d", owns="x", wake="", visible=lambda c: True)

    def test_deny_non_callable_visible(self):
        reg = daemons.DaemonRegistry()
        with pytest.raises(ValueError):
            reg.register("d", owns="x", wake="hourly", visible="always")

    def test_deny_dispatch_unowned_domain(self):
        reg = self._registry()
        with pytest.raises(ValueError):
            reg.dispatch("dreams")
        with pytest.raises(ValueError):
            reg.dispatch("")

    def test_deny_surface_unknown_daemon(self):
        reg = self._registry()
        with pytest.raises(ValueError):
            reg.surface("ghost", "payload")


class TestConstrainedAlphabet:
    def test_exact_parse(self):
        alpha = graffiti.ConstrainedAlphabet()
        assert alpha.parse("lambda open-left loop") == "ACO"
        assert alpha.char_for("vee") == "V"

    def test_custom_small_set(self):
        alpha = graffiti.ConstrainedAlphabet({"dot": ".", "dash": "-"})
        assert alpha.parse("dot dash dot") == ".-."

    def test_deny_unknown_token(self):
        alpha = graffiti.ConstrainedAlphabet()
        with pytest.raises(ValueError):
            alpha.parse("lambda frobnicate")

    def test_deny_near_miss_no_guessing(self):
        alpha = graffiti.ConstrainedAlphabet()
        with pytest.raises(ValueError):
            alpha.parse("lamda")  # near-miss of "lambda"
        with pytest.raises(ValueError):
            alpha.parse("LAMBDA")  # right word, wrong case
        with pytest.raises(ValueError):
            alpha.parse("Loop")  # right token, wrong case

    def test_deny_empty_parse_input(self):
        alpha = graffiti.ConstrainedAlphabet()
        with pytest.raises(ValueError):
            alpha.parse("")
        with pytest.raises(ValueError):
            alpha.parse("   ")

    def test_deny_empty_stroke_set(self):
        with pytest.raises(ValueError):
            graffiti.ConstrainedAlphabet({})

    def test_deny_empty_token(self):
        with pytest.raises(ValueError):
            graffiti.ConstrainedAlphabet({"": "A"})
        with pytest.raises(ValueError):
            graffiti.ConstrainedAlphabet({"  ": "A"})

    def test_deny_case_variant_token(self):
        with pytest.raises(ValueError):
            graffiti.ConstrainedAlphabet({"dot": ".", "DOT": ","})

    def test_deny_duplicate_token_in_add(self):
        alpha = graffiti.ConstrainedAlphabet()
        with pytest.raises(ValueError):
            alpha.add_stroke("loop", "Q")

    def test_deny_multi_char_mapping(self):
        alpha = graffiti.ConstrainedAlphabet()
        with pytest.raises(ValueError):
            alpha.add_stroke("newline", "\n\n")
        with pytest.raises(ValueError):
            alpha.add_stroke("empty", "")

    def test_deny_two_tokens_same_char(self):
        with pytest.raises(ValueError):
            graffiti.ConstrainedAlphabet({"dot": ".", "point": "."})
        alpha = graffiti.ConstrainedAlphabet()
        with pytest.raises(ValueError):
            alpha.add_stroke("point", "A")  # "lambda" already owns "A"


class TestRadialMenu:
    def test_novice_and_expert_resolve_identically(self):
        menu = piemenu.RadialMenu(["save", "open", "close", "quit"])
        for degrees in [
            0,
            10,
            44,
            45,
            46,
            90,
            135,
            180,
            225,
            270,
            315,
            359,
            360,
            -45,
            720 + 30,
        ]:
            novice_item, popup = menu.novice_select(degrees)
            expert_item = menu.expert_select(degrees)
            assert novice_item.name == expert_item.name
        # the popup is the full label map the novice saw
        assert set(popup) == {"save", "open", "close", "quit"}

    def test_wedge_geometry(self):
        menu = piemenu.RadialMenu(["north", "east", "south", "west"])
        assert menu.expert_select(0).name == "north"
        assert menu.expert_select(90).name == "east"
        assert menu.expert_select(180).name == "south"
        assert menu.expert_select(270).name == "west"
        # 45 sits exactly on the north/east boundary -> the wedge that
        # starts there (east)
        assert menu.expert_select(45).name == "east"

    def test_deny_fewer_than_two_items(self):
        with pytest.raises(ValueError):
            piemenu.RadialMenu([])
        with pytest.raises(ValueError):
            piemenu.RadialMenu(["only"])

    def test_deny_empty_item_name(self):
        with pytest.raises(ValueError):
            piemenu.RadialMenu(["save", ""])
        with pytest.raises(ValueError):
            piemenu.RadialMenu(["save", "   "])

    def test_deny_duplicate_item_name(self):
        with pytest.raises(ValueError):
            piemenu.RadialMenu(["save", "save"])

    def test_deny_non_numeric_angle(self):
        menu = piemenu.RadialMenu(["a", "b"])
        with pytest.raises(ValueError):
            menu.expert_select("north")
        with pytest.raises(ValueError):
            menu.novice_select(None)
        with pytest.raises(ValueError):
            menu.expert_select(float("nan"))
        with pytest.raises(ValueError):
            menu.expert_select(float("inf"))


class TestFolksonomyIndex:
    def _index(self):
        idx = folksonomy.FolksonomyIndex()
        idx.tag("url-1", ["python", "tutorial"])
        idx.tag("url-2", ["python", "reference"])
        idx.tag("url-3", ["cooking", "tutorial"])
        return idx

    def test_tag_and_query_ranked_by_use(self):
        idx = self._index()
        idx.tag("url-1", ["python"])  # second use -> outranks url-2
        assert idx.query("python") == ["url-1", "url-2"]
        assert idx.use_count("url-1", "python") == 2

    def test_retag_bumps_use_count_not_error(self):
        idx = self._index()
        idx.tag("url-1", ["python"])
        assert idx.use_count("url-1", "python") == 2

    def test_related_by_cooccurrence(self):
        idx = self._index()
        related = idx.related("python")
        assert "tutorial" in related
        assert "reference" in related
        assert "cooking" not in related

    def test_untag(self):
        idx = self._index()
        idx.untag("url-3", "cooking")
        assert idx.tags_of("url-3") == ["tutorial"]

    def test_tag_normalization(self):
        idx = folksonomy.FolksonomyIndex()
        idx.tag("u", ["  Python  "])
        assert idx.query("python") == ["u"]

    def test_deny_empty_item_id(self):
        idx = folksonomy.FolksonomyIndex()
        with pytest.raises(ValueError):
            idx.tag("", ["python"])
        with pytest.raises(ValueError):
            idx.tags_of("  ")

    def test_deny_empty_tag(self):
        idx = folksonomy.FolksonomyIndex()
        with pytest.raises(ValueError):
            idx.tag("u", [""])
        with pytest.raises(ValueError):
            idx.tag("u", ["   "])
        with pytest.raises(ValueError):
            idx.tag("u", [])

    def test_deny_untag_unknown_item(self):
        idx = self._index()
        with pytest.raises(ValueError):
            idx.untag("nope", "python")

    def test_deny_untag_missing_tag(self):
        idx = self._index()
        with pytest.raises(ValueError):
            idx.untag("url-1", "cooking")

    def test_deny_query_unknown_tag(self):
        idx = self._index()
        with pytest.raises(ValueError):
            idx.query("nonexistent")

    def test_deny_related_unknown_tag(self):
        idx = self._index()
        with pytest.raises(ValueError):
            idx.related("nonexistent")


class TestBoundedSpace:
    def test_cap_enforced_at_join(self):
        room = cap.BoundedSpace("inner-circle", cap=2)
        room.join("chauncey")
        room.join("skylar")
        assert room.is_full()
        assert not room.has_space()
        with pytest.raises(ValueError):
            room.join("third")

    def test_leave_frees_space(self):
        room = cap.BoundedSpace("room", cap=1)
        room.join("a")
        room.leave("a")
        assert room.has_space()
        room.join("b")
        assert room.is_member("b")

    def test_no_public_counters(self):
        room = cap.BoundedSpace("room", cap=3)
        room.join("a")
        assert not hasattr(room, "members")
        with pytest.raises(TypeError):
            len(room)

    def test_deny_empty_room_name(self):
        with pytest.raises(ValueError):
            cap.BoundedSpace("", cap=5)
        with pytest.raises(ValueError):
            cap.BoundedSpace("   ", cap=5)

    def test_deny_cap_below_one(self):
        with pytest.raises(ValueError):
            cap.BoundedSpace("room", cap=0)
        with pytest.raises(ValueError):
            cap.BoundedSpace("room", cap=-2)
        with pytest.raises(ValueError):
            cap.BoundedSpace("room", cap="fifty")

    def test_deny_join_twice(self):
        room = cap.BoundedSpace("room", cap=5)
        room.join("a")
        with pytest.raises(ValueError):
            room.join("a")

    def test_deny_join_empty_member(self):
        room = cap.BoundedSpace("room", cap=5)
        with pytest.raises(ValueError):
            room.join("")
        with pytest.raises(ValueError):
            room.join("   ")

    def test_deny_leave_non_member(self):
        room = cap.BoundedSpace("room", cap=5)
        with pytest.raises(ValueError):
            room.leave("stranger")

    def test_deny_membership_query_empty_name(self):
        room = cap.BoundedSpace("room", cap=5)
        with pytest.raises(ValueError):
            room.is_member("")


class TestSharedSession:
    def _session(self):
        return splitscreen.SharedSession(
            viewers=[
                splitscreen.Viewer(id="p1", focus=None),
                splitscreen.Viewer(id="p2", focus={"score"}),
            ],
            initial_state={"score": 0, "level": 1},
        )

    def test_n_consistent_views_of_one_state(self):
        sess = self._session()
        assert sess.render("p1") == {"score": 0, "level": 1}
        assert sess.render("p2") == {"score": 0}  # camera sees its focus

    def test_state_change_visible_in_all_viewports(self):
        sess = self._session()
        sess.set("score", 99)
        assert sess.render("p1")["score"] == 99
        assert sess.render("p2")["score"] == 99
        sess.delete("level")
        assert "level" not in sess.render("p1")

    def test_viewer_management(self):
        sess = self._session()
        sess.add_viewer(splitscreen.Viewer(id="p3", focus={"level"}))
        assert sess.render("p3") == {"level": 1}
        assert sess.viewer_ids() == ["p1", "p2", "p3"]
        sess.remove_viewer("p3")
        assert sess.viewer_ids() == ["p1", "p2"]

    def test_deny_fewer_than_two_viewers(self):
        with pytest.raises(ValueError):
            splitscreen.SharedSession(viewers=[splitscreen.Viewer(id="solo")])
        with pytest.raises(ValueError):
            splitscreen.SharedSession(viewers=[])

    def test_deny_empty_viewer_id(self):
        with pytest.raises(ValueError):
            splitscreen.SharedSession(
                viewers=[
                    splitscreen.Viewer(id=""),
                    splitscreen.Viewer(id="p2"),
                ]
            )

    def test_deny_duplicate_viewer_id(self):
        with pytest.raises(ValueError):
            splitscreen.SharedSession(
                viewers=[
                    splitscreen.Viewer(id="p1"),
                    splitscreen.Viewer(id="p1"),
                ]
            )

    def test_deny_unknown_viewer(self):
        sess = self._session()
        with pytest.raises(ValueError):
            sess.render("ghost")

    def test_deny_empty_state_key(self):
        sess = self._session()
        with pytest.raises(ValueError):
            sess.set("", 1)
        with pytest.raises(ValueError):
            sess.set("   ", 1)

    def test_deny_delete_unknown_key(self):
        sess = self._session()
        with pytest.raises(ValueError):
            sess.delete("nope")

    def test_deny_remove_viewer_below_two(self):
        sess = self._session()
        with pytest.raises(ValueError):
            sess.remove_viewer("p1")

    def test_deny_remove_unknown_viewer(self):
        sess = self._session()
        with pytest.raises(ValueError):
            sess.remove_viewer("ghost")

    def test_deny_add_duplicate_viewer(self):
        sess = self._session()
        with pytest.raises(ValueError):
            sess.add_viewer(splitscreen.Viewer(id="p1"))
