"""Hermetic tests for wave-26 revival modules: honest-inversions (b).

Modules: earned_identity, open_protocol_weights, fair_play_charter,
portable_saves, odds_audit, season_era, liberation_ledger.

Hermetic: no network, deterministic (seeded RNG where randomness is
used), all persistence under tmp_path. Stdlib only.
"""

import json

import pytest

from levi.revival import (
    earned_identity,
    fair_play_charter,
    liberation_ledger,
    odds_audit,
    open_protocol_weights,
    portable_saves,
    season_era,
)


# ---------------------------------------------------------------- earned_identity


def _att(subject, attester, evidence):
    return earned_identity.Attestation(
        attester=attester, claim=subject, evidence=evidence
    )


def test_earned_identity_tier_comes_only_from_evidence():
    ident = earned_identity.EarnedIdentity(subject="chauncey")
    assert ident.tier() == "newcomer"
    ident.attest(_att("chauncey", "peer-a", "peer_attestation"))
    ident.attest(_att("chauncey", "peer-b", "demonstration"))
    ident.attest(_att("chauncey", "peer-c", "rite"))
    assert ident.earned_points() == 10 + 25 + 50
    assert ident.tier() == "known"
    assert ident.quorum(minimum_attesters=3)


def test_earned_identity_purchase_always_refused():
    ident = earned_identity.EarnedIdentity(subject="chauncey")
    with pytest.raises(earned_identity.IdentityNotForSale):
        ident.attempt_purchase("elder", price=999.99)
    # standing unchanged by the attempt
    assert ident.earned_points() == 0
    assert ident.tier() == "newcomer"


def test_earned_identity_self_attestation_and_collusion():
    ident = earned_identity.EarnedIdentity(subject="chauncey")
    with pytest.raises(earned_identity.AttestationError):
        ident.attest(_att("chauncey", "chauncey", "peer_attestation"))
    for _ in range(4):
        ident.attest(_att("chauncey", "one-fan", "peer_attestation"))
    assert ident.collusion_risk() == pytest.approx(1.0)
    assert not ident.quorum(minimum_attesters=3)


def test_identity_registry_ranks_by_earned_points():
    reg = earned_identity.IdentityRegistry()
    a = reg.register("amy")
    b = reg.register("bob")
    a.attest(_att("amy", "p1", "rite"))
    b.attest(_att("bob", "p1", "peer_attestation"))
    leaders = reg.leaders()
    assert leaders[0]["subject"] == "amy"
    assert leaders[1]["subject"] == "bob"


# ------------------------------------------------------- open_protocol_weights


def _echo_mesh():
    mesh = open_protocol_weights.OpenMesh()
    mesh.register(
        open_protocol_weights.Capability(
            name="echo",
            description="returns the payload back",
            handler=lambda payload: {"echo": payload},
        )
    )
    return mesh


def test_open_mesh_dispatch_round_trip():
    mesh = _echo_mesh()
    env = open_protocol_weights.make_envelope("echo", {"hello": "world"})
    reply_raw = mesh.dispatch(open_protocol_weights.envelope_bytes(env))
    reply = open_protocol_weights.parse_envelope(reply_raw)
    assert reply["kind"] == "echo.reply"
    assert reply["payload"]["result"] == {"echo": {"hello": "world"}}


def test_open_mesh_refuses_remote_only_capability():
    mesh = open_protocol_weights.OpenMesh()
    with pytest.raises(open_protocol_weights.ClosedCoreError):
        mesh.register(
            open_protocol_weights.Capability(
                name="cloud-only",
                description="no local handler",
                handler=lambda p: {},
                local=False,
            )
        )
    assert mesh.assert_no_closed_core() == []


def test_open_mesh_unknown_capability_and_spec(tmp_path):
    mesh = _echo_mesh()
    env = open_protocol_weights.make_envelope("nope", {})
    with pytest.raises(open_protocol_weights.UnknownCapability):
        mesh.dispatch(open_protocol_weights.envelope_bytes(env))
    weights_file = tmp_path / "tiny.bin"
    weights_file.write_bytes(b"fake-weights-bytes")
    import hashlib

    digest = hashlib.sha256(b"fake-weights-bytes").hexdigest()
    mesh.catalog_weights(
        open_protocol_weights.LocalWeights(
            name="levi-tiny",
            path=str(weights_file),
            size_bytes=18,
            sha256=digest,
            license="open",
        )
    )
    (w,) = mesh.weights()
    assert w.present() and w.verify_digest()
    spec = mesh.open_spec()
    assert spec["closed_core"] is False
    assert "echo" in spec["capabilities"]


# ------------------------------------------------------------ fair_play_charter


def _honest_spec():
    return {
        "title": "Honest Quest",
        "monetization": {"sells_random_outcomes": False},
        "streaks": {"punishes_break": False},
        "timers": [{"name": "daily", "expires_content": False}],
        "drop_tables": [{"name": "chests", "odds_published": True}],
        "hints": {"costs_money": False},
        "requires_online": False,
        "saves": {"exportable": True, "server_revocable": False},
    }


def test_charter_passes_honest_game():
    report = fair_play_charter.default_charter().evaluate(_honest_spec())
    assert report["passed"] is True
    assert report["score"] == "7/7"
    assert report["failed_rules"] == []


def test_charter_fails_dark_patterns_with_evidence():
    spec = _honest_spec()
    spec["monetization"]["sells_random_outcomes"] = True
    spec["streaks"]["punishes_break"] = True
    spec["timers"].append({"name": "flash-sale", "expires_content": True})
    spec["drop_tables"] = [{"name": "crates", "odds_published": False}]
    spec["requires_online"] = True
    report = fair_play_charter.default_charter().evaluate(spec)
    assert report["passed"] is False
    assert set(report["failed_rules"]) == {
        "no_paid_randomness",
        "no_streak_punishment",
        "no_fomo_timers",
        "honest_odds_declared",
        "offline_playable",
    }
    failed = {v["rule"]: v for v in report["verdicts"] if not v["passed"]}
    assert "sells_random_outcomes = true" in failed["no_paid_randomness"]["evidence"]


def test_charter_rule_without_drops_passes_honestly():
    spec = _honest_spec()
    spec["drop_tables"] = []
    verdicts = {
        v["rule"]: v
        for v in fair_play_charter.default_charter().evaluate(spec)["verdicts"]
    }
    assert verdicts["honest_odds_declared"]["passed"] is True
    assert "no randomized drops" in verdicts["honest_odds_declared"]["evidence"]


# --------------------------------------------------------------- portable_saves


def test_save_export_import_round_trip(tmp_path):
    lib = portable_saves.SaveLibrary()
    slot = portable_saves.SaveSlot(slot_name="quest-1", state={"level": 7, "gold": 250})
    path = str(tmp_path / "quest-1.save.json")
    lib.export_save(slot, path)
    doc = json.loads(open(path, encoding="utf-8").read())
    assert doc["checksum"]  # integrity recorded
    assert doc["slot"] == "quest-1"
    back = lib.import_save(path)
    assert back.state == {"level": 7, "gold": 250}
    assert back.manifest()["revocable"] is False


def test_save_corruption_detected(tmp_path):
    lib = portable_saves.SaveLibrary()
    slot = portable_saves.SaveSlot(slot_name="q", state={"x": 1})
    path = str(tmp_path / "q.save.json")
    lib.export_save(slot, path)
    doc = json.loads(open(path, encoding="utf-8").read())
    doc["state"]["x"] = 999  # tamper
    open(path, "w", encoding="utf-8").write(json.dumps(doc))
    with pytest.raises(portable_saves.SaveCorrupt):
        lib.import_save(path)


def test_save_migration_and_pack(tmp_path):
    lib = portable_saves.SaveLibrary()
    lib.register_migrator(0, lambda state: {"migrated": True, **state})
    old = portable_saves.SaveSlot(slot_name="old", state={"hp": 10}, schema_version=0)
    path = str(tmp_path / "old.save.json")
    lib.export_save(old, path)
    back = lib.import_save(path)
    assert back.schema_version == portable_saves.CURRENT_SCHEMA
    assert back.state["migrated"] is True
    pack = str(tmp_path / "move.savepack.json")
    lib.pack_for_move([back], pack)
    (unpacked,) = lib.unpack_move(pack)
    assert unpacked.state["hp"] == 10


def test_no_remote_revocation_path():
    lib = portable_saves.SaveLibrary()
    with pytest.raises(portable_saves.NoRevocationPath):
        lib.attempt_remote_revoke("quest-1")


# ------------------------------------------------------------------ odds_audit


def _table():
    return odds_audit.DropTable(
        "chest",
        [
            odds_audit.Outcome("common", weight=70, value=1.0),
            odds_audit.Outcome("rare", weight=25, value=10.0),
            odds_audit.Outcome("legendary", weight=5, value=100.0),
        ],
        pity_after=90,
    )


def test_odds_exact_and_ev():
    table = _table()
    odds = table.odds()
    assert odds == pytest.approx({"common": 0.7, "rare": 0.25, "legendary": 0.05})
    assert sum(odds.values()) == pytest.approx(1.0)
    assert table.expected_value() == pytest.approx(
        0.7 * 1.0 + 0.25 * 10.0 + 0.05 * 100.0
    )
    published = table.publish()
    assert published["rolls_free_and_unlimited"] is True


def test_pity_timer_guarantees_and_shows():
    table = _table()
    table._pity_counter = 90  # force the guarantee
    outcome = table.roll()
    assert outcome.name == "legendary"
    status = table.pity_status()
    assert status["misses_since_rarest"] == 0
    assert status["guarantees_at"] == 90


def test_prove_audit_matches_published_odds():
    table = _table()
    report = table.prove(trials=20000, seed=7)
    assert report["passed"] is True
    assert report["chi_square"] < report["critical_99"]
    assert report["pity_triggers"] >= 1  # pity visibly fired during audit
    legendary = report["deltas"]["legendary"]
    assert abs(legendary["delta"]) < 0.01


def test_prove_rejects_too_few_trials():
    with pytest.raises(ValueError):
        _table().prove(trials=50)


# ------------------------------------------------------------------ season_era


def test_era_player_controlled_and_points_never_expire():
    journal = season_era.SeasonJournal()
    era = journal.open_era("spring", theme="growth")
    era.add_milestone(season_era.Milestone("first-steps", 100, "sprout badge"))
    unlocked = era.earn(120)
    assert [m.name for m in unlocked] == ["first-steps"]
    summary = era.close()
    assert summary["open"] is False
    assert summary["points"] == 120
    assert journal.total_points_ever() == 120  # closed eras keep their points
    with pytest.raises(ValueError):
        era.earn(10)  # closed era: open a new one instead


def test_streak_celebrates_never_punishes():
    journal = season_era.SeasonJournal()
    journal.streak.celebrations.append(
        season_era.Celebration(at_streak=3, title="three-day glow", bonus_points=50)
    )
    base = 1_700_000_000.0
    for day in range(3):
        journal.streak.active_day(base + day * 86400)
    assert journal.streak.current == 3
    assert journal.streak.celebration_bonus() == 50
    kept = journal.streak.miss_day()
    assert kept["points_lost"] == 0
    assert kept["rewards_revoked"] == []
    assert kept["best_kept"] == 3
    assert journal.streak.current == 0  # reset, not punished


def test_season_journal_multiple_eras():
    journal = season_era.SeasonJournal()
    e1 = journal.open_era("spring")
    e1.earn(40)
    e1.close()
    e2 = journal.open_era("summer")
    e2.earn(60)
    assert journal.total_points_ever() == 100
    assert len(journal.eras()) == 2
    with pytest.raises(ValueError):
        journal.open_era("summer")  # already open


# ------------------------------------------------------------ liberation_ledger


def _hostage_service():
    return liberation_ledger.ServiceEntry(
        name="lockbox-social",
        data_held=["photos", "messages", "contacts"],
        export_available=False,
        delete_available=True,
        delete_purges=False,
        has_api=False,
        contract_lock=True,
    )


def test_hostage_score_fully_transparent():
    entry = _hostage_service()
    breakdown = entry.score_breakdown()
    assert breakdown["no_export"]["points"] == 25
    assert breakdown["contract_lock"]["points"] == 15
    assert breakdown["delete_keeps_copies"]["points"] == 15
    assert breakdown["no_delete"]["points"] == 0  # deletion offered
    # recompute honestly from the breakdown itself:
    total = sum(info["points"] for info in breakdown.values())
    assert total == 25 + 15 + 10 + 15  # no_export, keeps_copies, no_api, lock
    assert entry.hostage_score() == total
    assert entry.risk_band() == "sticky"  # 65: bad, but not the worst band


def test_free_service_scores_zero():
    entry = liberation_ledger.ServiceEntry(
        name="open-notes",
        data_held=["notes"],
        export_available=True,
        export_formats=["json", "md"],
        delete_available=True,
        delete_purges=True,
        has_api=True,
    )
    assert entry.hostage_score() == 0
    assert entry.risk_band() == "free"


def test_liberation_plan_flags_blockers_and_files_receipts():
    ledger = liberation_ledger.LiberationLedger()
    ledger.register(_hostage_service())
    plan = liberation_ledger.liberation_plan(ledger.get("lockbox-social"))
    steps = {t.step: t for t in plan}
    assert [t.step for t in plan] == ["export", "verify", "migrate", "delete"]
    assert steps["export"].possible is False
    assert "no export" in steps["export"].blocker
    assert steps["delete"].possible is True
    with pytest.raises(ValueError):
        ledger.complete_task(steps["export"])  # impossible step refused
    receipt = ledger.complete_task(
        steps["delete"], evidence="account deleted 2026-09-16"
    )
    assert receipt.step == "delete"
    assert ledger.receipts("lockbox-social") == [receipt]
    status = ledger.liberation_status("lockbox-social")
    assert status["completed"] == ["delete"]
    assert status["fully_liberated"] is False  # export still blocked


def test_ledger_ranks_worst_hostage_first():
    ledger = liberation_ledger.LiberationLedger()
    ledger.register(_hostage_service())
    ledger.register(
        liberation_ledger.ServiceEntry(
            name="mild-mail",
            data_held=["email"],
            export_available=True,
            export_formats=["mbox"],
            delete_available=True,
            delete_purges=True,
            has_api=True,
        )
    )
    ranked = ledger.ranked_by_hostage_score()
    assert ranked[0]["service"] == "lockbox-social"
    assert ranked[1]["service"] == "mild-mail"
