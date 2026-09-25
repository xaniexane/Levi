"""Proof tests for the anti-cheat penalty layer (L10–L14).

Property/invariant checks over the declared laws in
``levi/growth/levelup/laws.py`` — honest invariant tests, not a formal
proof. Storage is isolated per test via LEVI_LEVELUP_DIR /
LEVI_GROWTH_DIR (same isolation convention as test_growth_levelup.py).
"""

from __future__ import annotations

import json

import pytest

from levi.growth import journal as _journal
from levi.growth.levelup import (
    ABILITIES,
    active_abilities,
    apply_penalty,
    award_exp,
    award_question,
    award_reply,
    answer_question,
    append_adj,
    detect,
    earned_tokens,
    effective_exp,
    ensure_goal,
    entity_total,
    level_for,
    levels_after_penalty,
    locate_tamper,
    maybe_unlock,
    read_adj,
    read_receipts,
    reverse_penalty,
    threshold,
    verify_adj,
    verify_chain,
)


@pytest.fixture
def iso(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_LEVELUP_DIR", str(tmp_path / "levelup"))
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(tmp_path / "growth"))
    return tmp_path


def _legit_reply(entity, n=1, attention=8, interaction=7, intensity=2):
    for _ in range(n):
        award_reply(entity, attention, interaction, intensity)


def _journal_kinds(entity):
    return [
        e for e in _journal.read_entries(limit=1000)
        if e.get("entity") == entity
    ]


# ---------------------------------------------------------------------------
# L10 — tamper is detected AND located
# ---------------------------------------------------------------------------


def test_tamper_detected_and_span_located(iso):
    _legit_reply("nanobit", n=3)          # seqs 1..3
    award_exp("nanobit", "reply", 20,
              {"attention": 5, "interaction": 5, "intensity": 1})  # seq 4
    _legit_reply("nanobit", n=2)          # seqs 5..6

    # in-place edit of receipt seq 3 (system edit, not the award path)
    from levi.growth.levelup import ledger_path

    p = ledger_path()
    lines = p.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[2])
    rec["exp_delta"] = 99999
    lines[2] = json.dumps(rec, ensure_ascii=False)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, errors = verify_chain()
    assert not ok
    ok2, span, _ = locate_tamper()
    assert not ok2
    # exact span: only seq 3 was edited in place
    assert span == (3, 3)

    f = detect("nanobit")
    assert not f["chain_ok"]
    assert f["tampered_span"] == (3, 3)
    tamper_flags = [fl for fl in f["flags"] if fl["kind"] == "tamper"]
    assert [fl["seq"] for fl in tamper_flags] == [3]
    assert f["illicit_exp"] == 99999


def test_forged_tail_taints_from_the_break(iso):
    _legit_reply("nanobit", n=2)  # seqs 1..2
    from levi.growth.levelup import ledger_path

    p = ledger_path()
    lines = p.read_text(encoding="utf-8").splitlines()
    # rewrite the tail with a broken linkage (forged continuation)
    rec = json.loads(lines[1])
    rec["prev_hash"] = "f" * 64
    import hashlib

    body = {k: v for k, v in rec.items() if k != "hash"}
    rec["hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"),
                  ensure_ascii=True).encode()
    ).hexdigest()
    lines[1] = json.dumps(rec, ensure_ascii=False)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok2, span, _ = locate_tamper()
    assert not ok2
    assert span[0] == 2  # taint starts at the forged link


# ---------------------------------------------------------------------------
# L11 — velocity / provenance detection; legitimate play never trips
# ---------------------------------------------------------------------------


def test_per_event_velocity_flagged(iso):
    # 400 EXP on one reply: impossible via the scoring math (max 150)
    award_exp("nanobit", "reply", 400,
              {"attention": 10, "interaction": 10, "intensity": 5})
    f = detect("nanobit")
    kinds = [fl["kind"] for fl in f["flags"]]
    assert "velocity-event" in kinds
    assert f["illicit_exp"] == 400


def test_system_edit_missing_provenance_flagged(iso):
    # looks small, but never came through the award path (no meta)
    award_exp("nanobit", "reply", 30)
    f = detect("nanobit")
    kinds = [fl["kind"] for fl in f["flags"]]
    assert "system-edit" in kinds
    assert f["illicit_exp"] == 30


def test_unknown_kind_flagged(iso):
    award_exp("nanobit", "gm-grant", 25, {"attention": 1})
    f = detect("nanobit")
    assert any(fl["kind"] == "system-edit" for fl in f["flags"])


def test_daily_velocity_excess_flagged_newest_first(iso):
    # 30 hand-written receipts of 150 EXP in one day: 4500 total.
    # cap with no goal = 22*180 + 50 + 20*150 = 7010? No —
    # that's too high to trip. Use a real goal with quota 11:
    # cap = 11*180 + 50 + 20*150 = 5030. Still above 4500.
    # So: 40 receipts -> 6000 > 5030, excess 970 newest-first.
    goal = ensure_goal("2026-09-22", 11)
    for _ in range(40):
        award_exp("cheater", "reply", 150,
                  {"attention": 10, "interaction": 10, "intensity": 5,
                   "ts_date": "x"})
    # force all receipts onto the goal date by rewriting ts
    from levi.growth.levelup import ledger_path

    p = ledger_path()
    lines = p.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        rec = json.loads(line)
        rec["ts"] = "2026-09-22T10:00:00+00:00"
        import hashlib

        body = {k: v for k, v in rec.items() if k != "hash"}
        rec["hash"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode()
        ).hexdigest()
        # repair chain links after ts rewrite
        out.append(rec)
    prev = "0" * 64
    for i, rec in enumerate(out):
        rec["seq"] = i + 1
        rec["prev_hash"] = prev
        body = {k: v for k, v in rec.items() if k != "hash"}
        rec["hash"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode()
        ).hexdigest()
        prev = rec["hash"]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out)
                 + "\n", encoding="utf-8")

    ok, _ = verify_chain()
    assert ok
    f = detect("cheater")
    assert f["velocity_days"], "expected a velocity-day finding"
    v = f["velocity_days"][0]
    assert v["day_total"] == 6000
    assert v["cap"] == 11 * 180 + 50 + 20 * 150 == 5030
    assert v["excess"] == 970
    assert f["illicit_exp"] == 970
    # newest-first: the highest seqs carry the excess
    seqs = sorted(fl["seq"] for fl in f["flags"]
                  if fl["kind"] == "velocity-day")
    assert seqs == [34, 35, 36, 37, 38, 39, 40]


def test_legitimate_play_never_trips(iso):
    """A full honest day: goal quota answered + replies within bounds."""
    goal = ensure_goal("2026-09-22", 11)
    for a in goal["assignments"]:
        answer_question("2026-09-22", a["id"], "nanobit",
                        [1.0, 1.0, 0.5], intensity_level=3)
    _legit_reply("nanobit", n=5, attention=9, interaction=8, intensity=4)
    f = detect("nanobit")
    assert f["chain_ok"]
    assert f["flags"] == []
    assert f["velocity_days"] == []
    assert f["acceleration"] == []
    assert f["illicit_exp"] == 0


def test_award_path_rejects_out_of_range(iso):
    """L5: the legitimate path cannot produce impossible scores."""
    with pytest.raises(ValueError):
        award_reply("nanobit", 11, 5, 1)
    with pytest.raises(ValueError):
        award_question("nanobit", [1.5], 1)


# ---------------------------------------------------------------------------
# L12 — proportional penalty math
# ---------------------------------------------------------------------------


def _build_total(entity, total):
    """Legit-looking ledger totaling exactly `total` (max 150/receipt)."""
    meta = {"attention": 10, "interaction": 10, "intensity": 5}
    while total > 0:
        d = min(total, 150)
        award_exp(entity, "reply", d, dict(meta))
        total -= d


def test_penalty_is_proportional_clawback(iso):
    _build_total("nanobit", 1000)          # level 4 (threshold 1000)
    award_exp("nanobit", "reply", 400,
              {"attention": 10, "interaction": 10, "intensity": 5})  # cheat
    assert entity_total("nanobit") == 1400
    f = detect("nanobit")
    assert f["illicit_exp"] == 400

    p = apply_penalty("nanobit", f)
    d = p["data"]
    assert d["confiscated_exp"] == 400
    assert effective_exp("nanobit") == 1000
    # knockback = exactly the levels the illicit 400 bought:
    # level(1400)=4 -> level(1000)=4 ... 1400<1500 so level 4; 1000 -> level 4.
    # levels lost = 0 here; verify formula against a bigger cheat below.
    assert d["level_before"] == level_for(1400)
    assert d["level_after"] == level_for(1000)
    assert d["levels_lost"] == level_for(1400) - level_for(1000)


def test_knockback_scales_with_illicit_amount(iso):
    losses = {}
    for cheat in (200, 900, 2000):
        ent = "e%d" % cheat
        _build_total(ent, 1000)  # level 4
        # cheat as one impossible receipt (whole delta illicit)
        award_exp(ent, "reply", cheat,
                  {"attention": 10, "interaction": 10, "intensity": 5})
        f = detect(ent)
        p = apply_penalty(ent, f)
        losses[cheat] = p["data"]["levels_lost"]
        # formula check: level(total) - level(total - illicit)
        assert p["data"]["levels_lost"] == (
            level_for(1000 + cheat) - level_for(1000)
        )
    assert losses[200] <= losses[900] <= losses[2000]
    assert losses[2000] > losses[200]  # strictly more knockback for more cheating


def test_penalty_never_takes_more_than_total(iso):
    _build_total("nanobit", 100)
    award_exp("nanobit", "reply", 99999,
              {"attention": 10, "interaction": 10, "intensity": 5})
    f = detect("nanobit")
    p = apply_penalty("nanobit", f)
    # confiscation can never exceed the entity's ledger total (the cap);
    # here the illicit 99999 is within it, so it is fully clawed back.
    assert p["data"]["confiscated_exp"] == 99999
    assert p["data"]["illicit_exp"] == 99999
    assert effective_exp("nanobit") == 100


def test_penalty_is_idempotent(iso):
    _build_total("nanobit", 1000)
    award_exp("nanobit", "reply", 400,
              {"attention": 10, "interaction": 10, "intensity": 5})
    f = detect("nanobit")
    p1 = apply_penalty("nanobit", f)
    p2 = apply_penalty("nanobit", detect("nanobit"))
    assert p2["data"]["confiscated_exp"] == 0
    assert effective_exp("nanobit") == 1000
    assert p1["data"]["confiscated_exp"] == 400


def test_levels_after_penalty_previews_math(iso):
    _build_total("nanobit", 1000)
    before, after, lost = levels_after_penalty("nanobit", 400)
    assert (before, after, lost) == (4, 3, 1)
    assert before == level_for(1000) and after == level_for(600)


# ---------------------------------------------------------------------------
# L13 — abilities: unlock path, acceleration, newest-first revocation
# ---------------------------------------------------------------------------


def test_unlocks_require_levels(iso):
    _build_total("nanobit", 300)  # level 2
    got = maybe_unlock("nanobit", effective_exp("nanobit"))
    assert [r["data"]["ability_id"] for r in got] == ["keen-ears"]
    assert active_abilities("nanobit") == ["keen-ears"]
    # earned super tokens stack into the earned pool
    assert earned_tokens("nanobit") == 10


def test_acceleration_detected_and_revoked_newest_first(iso):
    _build_total("nanobit", 100)  # level 1: meets NO ability requirement
    # system edit: abilities granted outside the level path + tokens
    for aid in ("keen-ears", "second-wind", "deep-diver", "legion-chorus"):
        append_adj("unlock", "nanobit",
                   {"ability_id": aid, "level_required": 2,
                    "forged": True})
    append_adj("token-grant", "nanobit", {"tokens": 70, "reason": "forged"})
    append_adj("token-base", "nanobit",
               {"tokens": 20, "reason": "weekly allotment"})

    f = detect("nanobit")
    assert {a["ability_id"] for a in f["acceleration"]} == {
        "keen-ears", "second-wind", "deep-diver", "legion-chorus"}

    p = apply_penalty("nanobit", f)
    d = p["data"]
    # newest-first revocation
    assert d["abilities_revoked"] == [
        "legion-chorus", "deep-diver", "second-wind", "keen-ears"]
    assert active_abilities("nanobit") == []
    # earned pool confiscated; base weekly untouched
    assert d["tokens_confiscated"] == 70
    assert earned_tokens("nanobit") == 0
    base = [r for r in read_adj()
            if r["kind"] == "token-base"]
    assert len(base) == 1 and base[0]["data"]["tokens"] == 20


def test_earned_abilities_survive_unrelated_penalty(iso):
    """Clawback only removes the illicit EXP; honestly earned unlocks stay."""
    _build_total("nanobit", 600)  # level 3
    maybe_unlock("nanobit", effective_exp("nanobit"))
    assert set(active_abilities("nanobit")) == {"keen-ears", "second-wind"}
    award_exp("nanobit", "reply", 400,
              {"attention": 10, "interaction": 10, "intensity": 5})
    p = apply_penalty("nanobit", detect("nanobit"))
    # effective back to 600 -> level 3 -> both abilities still qualify
    assert p["data"]["abilities_revoked"] == []
    assert set(active_abilities("nanobit")) == {"keen-ears", "second-wind"}


# ---------------------------------------------------------------------------
# L14 — every penalty receipted, review-flagged, reversible by Chauncey
# ---------------------------------------------------------------------------


def test_penalty_leaves_receipt_and_review_flag(iso):
    _build_total("nanobit", 1000)
    award_exp("nanobit", "reply", 400,
              {"attention": 10, "interaction": 10, "intensity": 5})
    p = apply_penalty("nanobit", detect("nanobit"))

    ok, errors = verify_adj()
    assert ok and not errors
    stored = [r for r in read_adj() if r["kind"] == "penalty"]
    assert len(stored) == 1
    assert stored[0]["seq"] == p["seq"]
    assert stored[0]["data"]["review_flag"] == "chauncey-review"
    assert stored[0]["data"]["reversible"] is True

    entries = [e for e in _journal_kinds("nanobit")
               if e.get("kind") == "penalty"]
    assert len(entries) == 1
    assert entries[0]["review_flag"] == "chauncey-review"
    assert entries[0]["penalty_seq"] == p["seq"]


def test_reversal_only_by_chauncey_and_restores(iso):
    _build_total("nanobit", 600)  # level 3
    maybe_unlock("nanobit", effective_exp("nanobit"))
    assert earned_tokens("nanobit") == 25

    # acceleration cheat: forge a level-5 ability + tokens
    append_adj("unlock", "nanobit",
               {"ability_id": "legion-chorus", "level_required": 5,
                "forged": True})
    append_adj("token-grant", "nanobit", {"tokens": 25, "reason": "forged"})
    f = detect("nanobit")
    p = apply_penalty("nanobit", f)
    assert active_abilities("nanobit") == ["keen-ears", "second-wind"]
    assert earned_tokens("nanobit") == 25  # forged 25 confiscated

    with pytest.raises(ValueError):
        reverse_penalty("nanobit", p["seq"], approved_by="legion:nano")
    with pytest.raises(ValueError):
        reverse_penalty("nanobit", 999, approved_by="chauncey")

    rev = reverse_penalty("nanobit", p["seq"], approved_by="chauncey")
    assert rev["kind"] == "penalty-reversal"
    # records survive: nothing vaporized, everything restored as new receipts
    assert "legion-chorus" in active_abilities("nanobit")
    assert earned_tokens("nanobit") == 50
    assert effective_exp("nanobit") == 600
    ok, _ = verify_adj()
    assert ok
    kinds = {r["kind"] for r in read_adj() if r["entity"] == "nanobit"}
    assert {"penalty", "penalty-reversal", "unlock-revoke",
            "unlock-restore", "token-confiscate", "token-grant"} <= kinds
    entries = [e for e in _journal_kinds("nanobit")
               if e.get("kind") == "penalty-reversal"]
    assert len(entries) == 1 and entries[0]["approved_by"] == "chauncey"

    with pytest.raises(ValueError):
        reverse_penalty("nanobit", p["seq"], approved_by="chauncey")  # twice


def test_abilities_registry_provisional(iso):
    ids = [a["id"] for a in ABILITIES]
    assert len(ids) == len(set(ids))
    assert all(a["level_required"] >= 1 for a in ABILITIES)
