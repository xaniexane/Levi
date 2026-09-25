"""Tests for revival wave 03 — crafts (a)."""

import pytest

from core.levi.revival import indenture, chef_d_uvre, compagnonnage
from core.levi.revival import tiered_disclosure, hallmark_chain
from core.levi.revival import quorum_chest, sloyd_curriculum, kontor_years


# -- indenture ------------------------------------------------------------


def _std_indenture():
    return indenture.Indenture.standard("novice-a", "master-b")


def test_indenture_staged_unlock():
    ind = _std_indenture()
    assert ind.stage.name == "apprentice"
    for area in ("materials", "tools", "technique"):
        for _ in range(4):
            rec = ind.record_work(area, "practice")
            ind.sign_off(rec.record_id, "master-b")
    assert ind.stage_complete()
    ind.advance("master-b")
    assert ind.stage.name == "journeyman"
    assert len(ind.lineage()) >= 3  # contract + signoffs + promotion


def test_indenture_advance_blocked_until_requirements_met():
    ind = _std_indenture()
    with pytest.raises(indenture.AssessorError):
        ind.advance("master-b")


def test_indenture_only_authorized_assessors_sign_off():
    ind = _std_indenture()
    rec = ind.record_work("materials", "practice")
    with pytest.raises(indenture.AssessorError):
        ind.sign_off(rec.record_id, "random-stranger")
    with pytest.raises(indenture.AssessorError):
        ind.sign_off(999, "master-b")


# -- chef_d_uvre -----------------------------------------------------------


def _scored_guild():
    g = chef_d_uvre.Guild("weavers")
    for peer in ("p1", "p2", "p3"):
        g.register_peer(peer)
    piece = g.submit_piece("maker-x", "Loom of Dawn", "a tapestry of the harbor")
    marks = {"craft": 0.8, "design": 0.75, "material": 0.9, "finish": 0.7}
    for peer in ("p1", "p2", "p3"):
        g.score(piece.piece_id, peer, marks)
    return g, piece


def test_masterpiece_pass_retains_piece_in_corpus():
    g, piece = _scored_guild()
    verdict = g.judge(piece.piece_id)
    assert verdict.passed
    assert g.rank_of("maker-x") == "master"
    assert len(g.corpus) == 1
    assert g.corpus.study(piece.piece_id).title == "Loom of Dawn"


def test_masterpiece_veto_floor_fails():
    g = chef_d_uvre.Guild("weavers")
    for peer in ("p1", "p2", "p3"):
        g.register_peer(peer)
    piece = g.submit_piece("maker-y", "Shoddy Pot", "rushed work")
    # High marks overall but finish below the veto floor.
    marks = {"craft": 0.95, "design": 0.9, "material": 0.9, "finish": 0.1}
    for peer in ("p1", "p2", "p3"):
        g.score(piece.piece_id, peer, marks)
    verdict = g.judge(piece.piece_id)
    assert not verdict.passed
    assert g.rank_of("maker-y") is None
    assert len(g.corpus) == 0


def test_masterpiece_needs_enough_peers_and_no_self_scoring():
    g = chef_d_uvre.Guild("weavers")
    g.register_peer("p1")
    piece = g.submit_piece("maker-z", "Bowl", "a bowl")
    marks = {"craft": 0.8, "design": 0.8, "material": 0.8, "finish": 0.8}
    g.score(piece.piece_id, "p1", marks)
    with pytest.raises(chef_d_uvre.ReviewError):
        g.judge(piece.piece_id)  # needs 3 peers
    with pytest.raises(chef_d_uvre.ReviewError):
        g.score(piece.piece_id, "p1", marks)  # duplicate scoring


# -- compagnonnage ----------------------------------------------------------


def _workshops():
    return [
        compagnonnage.Workshop("loom-hall", "weaving", "master-w"),
        compagnonnage.Workshop("dye-vats", "dyeing", "master-d"),
        compagnonnage.Workshop("fulling-mill", "finishing", "master-f"),
    ]


def test_tour_forced_rotation_full_coverage():
    tour = compagnonnage.Tour("journeyman-q", _workshops(), rounds=1)
    tour.begin()
    while not tour.done:
        cur = tour.current
        tour.complete_placement(
            f"studied {cur.workshop.specialty}", cur.workshop.master
        )
    names = tour.coverage()
    assert sorted(names) == ["dye-vats", "fulling-mill", "loom-hall"]
    # No repeat before full coverage: all names unique in round 1.
    assert len(set(names)) == 3


def test_tour_second_round_does_not_restart_where_it_ended():
    tour = compagnonnage.Tour("journeyman-q", _workshops(), rounds=2)
    sched = tour.full_circuit_names()
    assert len(sched) == 6  # 3 workshops x 2 rounds
    assert sched[3] != sched[2]


def test_tour_handoff_requires_master_certification():
    tour = compagnonnage.Tour("journeyman-q", _workshops(), rounds=1)
    tour.begin()
    with pytest.raises(compagnonnage.RotationError):
        tour.complete_placement("studied weaving", "not-the-master")


# -- tiered_disclosure -------------------------------------------------------


def test_tiered_disclosure_public_read_and_denied_read():
    commons = tiered_disclosure.KnowledgeCommons(auditors={"auditor-1"})
    item = commons.deposit(
        "dye recipe", "madder + iron", tiered_disclosure.Tier.GUILD, "maker-m"
    )
    # Public party denied...
    with pytest.raises(tiered_disclosure.DisclosureError):
        commons.read(item.item_id, "stranger")
    # ...but granted parties read, and everything is logged.
    commons.grant(item.item_id, "apprentice-a", tiered_disclosure.Tier.GUILD, "maker-m")
    assert commons.read(item.item_id, "apprentice-a") == "madder + iron"
    actions = [e.action for e in commons.ledger()]
    assert actions == ["deposit", "deny", "grant", "read"]


def test_lyon_lesson_challenge_lowers_tier():
    commons = tiered_disclosure.KnowledgeCommons(auditors={"auditor-1"})
    item = commons.deposit(
        "silk technique",
        "throwing details",
        tiered_disclosure.Tier.RESTRICTED,
        "monopoly-g",
    )
    commons.challenge(
        item.item_id, "artisan-a", "public interest: craft knowledge belongs to all"
    )
    ruled = commons.rule(
        item.item_id,
        "auditor-1",
        tiered_disclosure.Tier.PUBLIC,
        "restriction served rents, not safety",
    )
    assert ruled.tier == tiered_disclosure.Tier.PUBLIC
    assert commons.read(item.item_id, "anyone") == "throwing details"


def test_challenge_requires_reason_and_independent_auditor():
    commons = tiered_disclosure.KnowledgeCommons(auditors={"auditor-1"})
    item = commons.deposit("x", "y", tiered_disclosure.Tier.GUILD, "maker-m")
    with pytest.raises(tiered_disclosure.DisclosureError):
        commons.challenge(item.item_id, "c", "   ")  # no reason
    commons.challenge(item.item_id, "c", "legitimate reason")
    with pytest.raises(tiered_disclosure.DisclosureError):
        commons.rule(
            item.item_id, "maker-m", tiered_disclosure.Tier.PUBLIC, "self-rule"
        )  # maker not auditor


# -- hallmark_chain -----------------------------------------------------------


def _registry():
    r = hallmark_chain.Registry()
    r.register_maker("maker-1", "Smith")
    r.register_assayer("assay-1", "Office of Wares")
    return r


def test_tripartite_strike_and_verify():
    r = _registry()
    r.forge("bowl-1", "silver bowl")
    mark = r.strike("bowl-1", "maker-1", "assay-1", 1370)
    assert mark.maker_mark == "maker-1"
    assert mark.assayer_stamp == "assay-1"
    assert mark.date_letter == hallmark_chain.date_letter(1370)
    verdict = r.verify("bowl-1")
    assert verdict.trusted
    assert verdict.chain == ["maker-1", "assay-1", mark.date_letter]


def test_assayer_must_be_independent():
    r = _registry()
    r.register_maker("assay-1", "Office of Wares")  # same id tries both roles
    r.forge("bowl-2", "silver bowl")
    with pytest.raises(hallmark_chain.TrustError):
        r.strike("bowl-2", "assay-1", "assay-1", 1371)


def test_upheld_contest_strikes_assayer_and_taints_chain():
    r = _registry()
    r.forge("bowl-3", "silver bowl")
    r.strike("bowl-3", "maker-1", "assay-1", 1372)
    r.contest("bowl-3", "buyer-b", "alloy tests short of standard")
    assert not r.verify("bowl-3").trusted  # open contest blocks trust
    r.adjudicate("bowl-3", upheld=True, note="assay falsified")
    verdict = r.verify("bowl-3")
    assert not verdict.trusted
    assert "tainted" in verdict.reason
    # Suspended assayer cannot strike again.
    r.forge("bowl-4", "silver bowl")
    with pytest.raises(hallmark_chain.TrustError):
        r.strike("bowl-4", "maker-1", "assay-1", 1373)


# -- quorum_chest -------------------------------------------------------------


def _chest():
    return quorum_chest.QuorumChest({"h1", "h2", "h3"}, quorum=2)


def test_quorum_open_withdraw_and_audit_chain():
    chest = _chest()
    chest.deposit("charter", "guild rules", "h1")
    with pytest.raises(quorum_chest.QuorumError):
        chest.open_session({"h1"})  # only 1 key, need 2
    session = chest.open_session({"h1", "h2"})
    assert chest.withdraw("charter", session) == "guild rules"
    assert chest.audit()


def test_register_learner_builds_skill_lineage():
    chest = _chest()
    session = chest.open_session({"h2", "h3"})
    entry = chest.register_learner("learner-l", "journeyman", "h2", session)
    assert entry.sponsor == "h2"
    lineage = chest.lineage("learner-l")
    assert len(lineage) == 1 and lineage[0].rank == "journeyman"
    with pytest.raises(quorum_chest.QuorumError):
        chest.register_learner("learner-l", "master", "outsider", session)


def test_audit_detects_log_tampering():
    chest = _chest()
    session = chest.open_session({"h1", "h2"})
    chest.inventory(session)
    assert chest.audit()
    chest._log[1] = chest._log[1].replace("OPENED", "FORGED")
    assert not chest.audit()


# -- sloyd_curriculum ------------------------------------------------------------


def _curriculum():
    c = sloyd_curriculum.Curriculum("woodwork basics")
    c.add_exercise("sawing pine", ["saw", "pine"])
    c.add_exercise("planing pine", ["saw", "pine", "plane"])
    c.add_exercise("planing oak", ["saw", "pine", "plane", "oak"])
    return c


def test_single_new_variable_rule_enforced():
    c = sloyd_curriculum.Curriculum("woodwork")
    c.add_exercise("sawing pine", ["saw", "pine"])
    with pytest.raises(sloyd_curriculum.CurriculumError):
        c.add_exercise("too much", ["saw", "pine", "chisel", "oak"])  # 2 new vars
    assert c.validate() == []


def test_progression_and_completion():
    c = _curriculum()
    prog = sloyd_curriculum.Progress("learner-s", c)
    assert prog.next_up().name == "sawing pine"
    prog.attempt("sawing pine", True)
    prog.attempt("planing pine", False)
    prog.attempt("planing pine", True)
    assert not prog.complete()
    prog.attempt("planing oak", True)
    assert prog.complete()
    assert prog.mastery("plane") == 1.0


def test_diagnose_points_at_newest_variable():
    c = _curriculum()
    prog = sloyd_curriculum.Progress("learner-s", c)
    prog.attempt("sawing pine", True)
    prog.attempt("planing pine", False)
    prog.attempt("planing pine", False)
    diagnosis = prog.diagnose("planing pine")
    assert "plane" in diagnosis


# -- kontor_years ----------------------------------------------------------------


def _run_posting():
    # Hold-only strategy: the candidate preserves the sandbox stake, which is
    # a legitimate way to clear (no loss). Spread costs would sink round-trips.
    kontor = kontor_years.Kontor("bruges", seasons=2, stake=1000.0, min_entries=2)
    posting = kontor.post("candidate-k")
    for season in (1, 2):
        market = posting.begin_season(season)
        posting.copy_entry("hold", 0, market.bid)
        posting.end_season()
    return kontor, posting


def test_posting_completes_seasons_and_copies():
    kontor, posting = _run_posting()
    assert posting.seasons_completed() == [1, 2]
    assert len(posting.ledger_entries()) == 2
    clearance = posting.live_trade_clearance()
    assert clearance.granted
    assert clearance.candidate == "candidate-k"


def test_clearance_denied_until_all_requirements_met():
    kontor = kontor_years.Kontor("bruges", seasons=2, stake=1000.0, min_entries=2)
    posting = kontor.post("candidate-k")
    market = posting.begin_season(1)
    posting.copy_entry("hold", 0, market.bid)
    posting.end_season()
    clearance = posting.live_trade_clearance()
    assert not clearance.granted
    assert any("seasons" in r for r in clearance.reasons)


def test_sandbox_cannot_overspend_or_sell_air():
    kontor = kontor_years.Kontor("bruges", seasons=1, stake=100.0, min_entries=1)
    posting = kontor.post("candidate-k")
    market = posting.begin_season(1)
    with pytest.raises(kontor_years.MarketError):
        posting.copy_entry("buy", 100000, market.ask)  # beyond practice cash
    with pytest.raises(kontor_years.MarketError):
        posting.copy_entry("sell", 3, market.bid)  # nothing held
    with pytest.raises(kontor_years.MarketError):
        posting.copy_entry("hold", 5, market.bid)  # hold takes quantity 0


def test_clearance_denied_when_sandbox_stake_lost():
    # Round-trips bleed the spread: the candidate loses sandbox money.
    kontor = kontor_years.Kontor("bruges", seasons=2, stake=1000.0, min_entries=2)
    posting = kontor.post("candidate-k")
    for season in (1, 2):
        market = posting.begin_season(season)
        posting.copy_entry("buy", 5, market.ask)
        posting.copy_entry("sell", 5, market.bid)
        posting.end_season()
    clearance = posting.live_trade_clearance()
    assert not clearance.granted
    assert any("stake" in r for r in clearance.reasons)
