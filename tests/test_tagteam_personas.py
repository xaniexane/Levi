"""Tests for persona/trait/tone/role conditioning in the tag-team loop.

Hermetic: no torch, no network. Torch absence is skipped honestly by
the loop itself; these tests inject all stages.
"""

import json

import pytest

from levi.brain.tagteam import personas
from levi.brain.tagteam import requests as req_mod
from levi.brain.tagteam.loop import (
    DropRejected,
    RoundConfig,
    run_round,
    score_conditions,
    validate_condition_tags,
)
from levi.brain.tagteam.personas import (
    ConditionRejected,
    PersonaCondition,
    condition_brief_block,
    default_conditions,
    trait_consistency_score,
    validate_condition,
)
from levi.brain.tagteam.prompts import teacher_batch_instructions


def _cond_dict(**kw):
    d = {
        "persona_id": "void",
        "role": "mentor",
        "tone": "deadpan",
        "ei": {
            "presence": 0.85,
            "empathy": 0.55,
            "regulation": 0.95,
            "relational": 0.65,
            "integrity": 1.0,
        },
        "traits": ["terse", "high-signal"],
        "voice_notes": "Dry and precise.",
    }
    d.update(kw)
    return d


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_validate_condition_ok_and_round_trip():
    cond = validate_condition(_cond_dict())
    assert isinstance(cond, PersonaCondition)
    assert cond.key() == "void/deadpan/mentor"
    assert cond.provisional is True
    back = validate_condition(cond.to_dict())
    assert back == cond


def test_persona_ids_come_from_repo_material_only():
    ids = personas.provisional_persona_ids()
    assert "void" in ids  # lattice starter
    assert "lens_terse_systems" in ids  # expanded catalog
    assert "made_up_persona" not in ids
    with pytest.raises(ConditionRejected):
        validate_condition(_cond_dict(persona_id="made_up_persona"))


def test_rejects_unknown_tone_role_bad_ei_bad_trait():
    with pytest.raises(ConditionRejected):
        validate_condition(_cond_dict(tone="smug"))
    with pytest.raises(ConditionRejected):
        validate_condition(_cond_dict(role="jester"))
    with pytest.raises(ConditionRejected):
        validate_condition(_cond_dict(ei={"presence": 1.5}))
    with pytest.raises(ConditionRejected):
        validate_condition(_cond_dict(traits=["BAD TAG!"]))
    with pytest.raises(ConditionRejected):
        validate_condition({"persona_id": "void"})  # missing role/tone


def test_provisional_cannot_be_cleared_here():
    with pytest.raises(ConditionRejected):
        PersonaCondition(
            persona_id="void",
            role="mentor",
            tone="deadpan",
            ei=(0.8, 0.8, 0.8, 0.8, 1.0),
            provisional=False,
        )


def test_default_conditions_are_valid_and_provisional():
    conds = default_conditions()
    assert len(conds) >= 3
    for c in conds:
        assert c.provisional is True
        assert c.persona_id in personas.provisional_persona_ids()


def test_condition_brief_block_names_frame():
    cond = validate_condition(_cond_dict())
    block = condition_brief_block(cond)
    assert "void" in block and "deadpan" in block and "mentor" in block
    assert "terse" in block and "presence=0.85" in block


def test_teacher_batch_instructions_kinds():
    cond = validate_condition(_cond_dict())
    for kind in ("qa", "reasoning-trace", "correction"):
        text = teacher_batch_instructions(cond, kind)
        assert "void" in text
    with pytest.raises(KeyError):
        teacher_batch_instructions(cond, "song")


# ---------------------------------------------------------------------------
# Deterministic trait/tone rubric (observations, not verdicts)
# ---------------------------------------------------------------------------


def test_trait_consistency_score_deadpan_markers():
    cond = validate_condition(_cond_dict())
    score, checks = trait_consistency_score(cond, "No. That is wrong.")
    assert score == 1.0 and all(checks.values())
    score2, checks2 = trait_consistency_score(cond, "No! That is wrong!")
    assert checks2["no_exclaim"] is False
    assert score2 == 0.5
    score3, _ = trait_consistency_score(cond, "")
    assert 0.0 <= score3 <= 1.0


def test_score_conditions_keys_per_condition():
    conds = default_conditions()[:2]
    samples = {"arith-1": "42.", "chem-1": "Water!"}
    out = score_conditions(conds, samples)
    assert set(out) == {c.key() for c in conds}
    assert set(out[conds[0].key()]) == {"arith-1", "chem-1"}


# ---------------------------------------------------------------------------
# Conditioned requests
# ---------------------------------------------------------------------------


def _gaps():
    return [
        req_mod.Gap(
            topic="arithmetic",
            prompt_id="arith-1",
            prev_score=0.9,
            cur_score=0.4,
            delta=-0.5,
            severity="regressed",
        ),
        req_mod.Gap(
            topic="chemistry",
            prompt_id="chem-1",
            prev_score=None,
            cur_score=0.3,
            delta=0.0,
            severity="weak",
        ),
    ]


def test_assign_requests_carries_and_rotates_conditions():
    conds = list(default_conditions()[:2])
    r1 = req_mod.assign_requests(_gaps(), 1, {}, conditions=conds)
    r2 = req_mod.assign_requests(_gaps(), 1, {}, conditions=conds)
    assert len(r1) == 4  # 2 topics x 2 teachers
    assert [r.condition for r in r1] == [r.condition for r in r2]  # deterministic
    keys = [r.condition["persona_id"] for r in r1]
    assert set(keys) == {conds[0].persona_id, conds[1].persona_id}  # rotated
    assert all("persona_condition" in r.brief for r in r1)
    # rotation + no-same-teacher rules both hold
    assert len({r.teacher for r in r1 if r.topic == "arithmetic"}) == 2


def test_assign_requests_without_conditions_unchanged():
    reqs = req_mod.assign_requests(_gaps(), 1, {})
    assert all(r.condition is None for r in reqs)
    assert all("persona_condition" not in r.brief for r in reqs)


def test_assign_requests_rejects_bad_condition():
    with pytest.raises(ConditionRejected):
        req_mod.assign_requests(_gaps(), 1, {}, conditions=[{"persona_id": "nope"}])


# ---------------------------------------------------------------------------
# Intake tag validation
# ---------------------------------------------------------------------------


def _tagged(teacher="qwen"):
    return {
        "teacher": teacher,
        "prompt": "What is 2+2?",
        "response": "4.",
        "topic": "arithmetic",
        "persona_condition": _cond_dict(),
    }


def test_validate_condition_tags_ok():
    conds = validate_condition_tags([_tagged(), _tagged("mistral")])
    assert len(conds) == 1  # deduped by frame key
    assert conds[0].persona_id == "void"


def test_validate_condition_tags_missing_rejects():
    rec = _tagged()
    del rec["persona_condition"]
    with pytest.raises(DropRejected, match="missing 'persona_condition'"):
        validate_condition_tags([rec])


def test_validate_condition_tags_invalid_rejects():
    rec = _tagged()
    rec["persona_condition"] = _cond_dict(tone="smug")
    with pytest.raises(DropRejected, match="bad persona_condition"):
        validate_condition_tags([rec])


# ---------------------------------------------------------------------------
# Round integration: ledger records conditions; untagged drops abort
# ---------------------------------------------------------------------------


def _cfg(tmp_path, **kw):
    drops = tmp_path / "drops"
    drops.mkdir(exist_ok=True)
    args = dict(
        round_n=1,
        drops_dir=drops,
        workdir=tmp_path / "work",
        ledger_path=tmp_path / "work" / "ledger.jsonl",
    )
    args.update(kw)
    return RoundConfig(**args), drops


def _write_drops(drops, records):
    p = drops / "t1.jsonl"
    with open(p, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def _fake_intake_ok(records_out):
    def _fn(cfg, ready):
        return {
            "ran": True,
            "report": {"records_out": len(records_out), "per_teacher": {"qwen": 1}},
            "records": records_out,
            "records_path": str(cfg.round_dir() / "records.jsonl"),
        }

    return _fn


def _fake_eval_with_samples(scores, samples):
    def _fn(cfg):
        return {"ran": True, "scores": dict(scores), "samples": dict(samples)}

    return _fn


def test_round_ledgers_conditions_and_scores_traits(tmp_path):
    conds = tuple(default_conditions()[:2])
    cfg, drops = _cfg(tmp_path, conditions=conds)
    _write_drops(drops, [_tagged()])
    records = [{"record_id": "t1", "text": "User: What is 2+2?\nLEVI: 4."}]
    result = run_round(
        cfg,
        intake_fn=_fake_intake_ok(records),
        eval_fn=_fake_eval_with_samples(
            {"arith-1": 0.4, "chem-1": 0.9}, {"arith-1": "42.", "chem-1": "Water!"}
        ),
    )
    assert not result["aborted"]
    entry = result["entry"]
    assert len(entry["conditions"]) == 2
    assert all(c["provisional"] for c in entry["conditions"])
    cond_scores = result["stages"]["eval"]["condition_scores"]
    assert set(cond_scores) == {c.key() for c in conds}
    # requests issued for the weak topic carry conditions
    assert result["stages"]["gaps"]["requests_issued"]
    req_path = cfg.round_dir() / "requests.jsonl"
    req_lines = [
        json.loads(line) for line in req_path.read_text(encoding="utf-8").splitlines()
    ]
    assert all(r["condition"] is not None for r in req_lines)


def test_round_rejects_untagged_drops(tmp_path):
    cfg, drops = _cfg(tmp_path)
    rec = _tagged()
    del rec["persona_condition"]
    _write_drops(drops, [rec])
    result = run_round(
        cfg,
        intake_fn=_fake_intake_ok([]),
        eval_fn=lambda cfg: {"ran": True, "scores": {}},
    )
    assert result["aborted"]
    assert result["stages"]["validate"]["ran"] is False
    assert "persona_condition" in result["aborted"]


def test_round_without_conditions_still_works(tmp_path):
    cfg, drops = _cfg(tmp_path)
    _write_drops(drops, [_tagged()])
    records = [{"record_id": "t1", "text": "User: What is 2+2?\nLEVI: 4."}]
    result = run_round(
        cfg,
        intake_fn=_fake_intake_ok(records),
        eval_fn=lambda cfg: {"ran": True, "scores": {"arith-1": 0.9}},
    )
    assert not result["aborted"]
    assert result["entry"]["conditions"] == []
    assert "condition_scores" not in result["stages"]["eval"]


# ---------------------------------------------------------------------------
# Operator seats: Chauncey's four seats (2026-09-21)
# ---------------------------------------------------------------------------


def test_operator_seats_validate_and_provisional():
    from levi.brain.tagteam import operator_seats as seats_fn

    seats = seats_fn()
    assert len(seats) == 4
    assert [s.persona_id for s in seats] == list(personas.SEAT_IDS)
    assert [s.persona_id for s in seats] == [
        "levi",
        "echo",
        "demandpulse",
        "rex",
    ]
    for s in seats:
        assert s.provisional is True
        assert s.key() == f"{s.persona_id}/{s.tone}/{s.role}"


def test_operator_seat_ids_accepted_by_validate_condition():
    for seat_id in personas.SEAT_IDS:
        cond = validate_condition(_cond_dict(persona_id=seat_id))
        assert cond.persona_id == seat_id
        # round-trips through to_dict (echo round-trips its twin facets)
        assert validate_condition(cond.to_dict()) == cond
    for facet_id in personas.FACET_IDS:
        cond = validate_condition(_cond_dict(persona_id=facet_id))
        assert cond.persona_id == facet_id
    # catalog IDs still work, made-up IDs still rejected
    validate_condition(_cond_dict(persona_id="void"))
    with pytest.raises(ConditionRejected):
        validate_condition(_cond_dict(persona_id="not_a_seat"))


def test_operator_seat_frames_match_canon_roles():
    from levi.brain.tagteam import operator_seats as seats_fn

    by_id = {s.persona_id: s for s in seats_fn()}
    assert (by_id["levi"].role, by_id["levi"].tone) == ("friend", "calm")
    assert (by_id["echo"].role, by_id["echo"].tone) == ("mentor", "sidewinder")
    assert (by_id["demandpulse"].role, by_id["demandpulse"].tone) == ("mentor", "calm")
    assert (by_id["rex"].role, by_id["rex"].tone) == ("challenger", "deadpan")
    # the face leans relational+empathy; the twin leans regulation
    assert by_id["levi"].ei_dict()["relational"] >= 0.9
    assert by_id["echo"].ei_dict()["regulation"] >= 0.9


def test_twin_seat_echo_has_two_facets():
    """Alpha/Omega are ONE individual (Echo) with two personalities.

    The twin truth lives in the data model: the echo seat carries
    ALPHA_FACET and OMEGA_FACET as real PersonaConditions in ``facets``.
    """
    from levi.brain.tagteam import operator_seats as seats_fn

    by_id = {s.persona_id: s for s in seats_fn()}
    echo = by_id["echo"]
    assert [f.persona_id for f in echo.facets] == ["alpha", "omega"]
    assert echo.facets[0] is personas.ALPHA_FACET
    assert echo.facets[1] is personas.OMEGA_FACET
    alpha, omega = echo.facets
    # the facets are the builder/developer and the automation daemon
    assert (alpha.role, alpha.tone) == ("mentor", "sidewinder")
    assert (omega.role, omega.tone) == ("archivist", "terse")
    assert "builder" in alpha.traits and "daemon" in omega.traits
    # each facet validates as its own condition
    for facet in echo.facets:
        assert validate_condition(facet.to_dict()) == facet
    # the twin line reaches teacher briefs
    assert "Twin seat" in condition_brief_block(echo)
    # single seats carry no facets
    assert by_id["levi"].facets == ()


def test_assign_requests_rotates_seats():
    from levi.brain.tagteam import operator_seats as seats_fn

    seats = list(seats_fn()[:2])
    r1 = req_mod.assign_requests(_gaps(), 1, {}, conditions=seats)
    assert len(r1) == 4  # 2 gaps x 2 teachers
    keys = [r.condition["persona_id"] for r in r1]
    assert set(keys) == {s.persona_id for s in seats}  # rotated
    assert all("persona_condition" in r.brief for r in r1)


def test_round_ledgers_seat_conditions(tmp_path):
    from levi.brain.tagteam import operator_seats as seats_fn

    seats = tuple(seats_fn()[:2])
    cfg, drops = _cfg(tmp_path, conditions=seats)
    rec = _tagged()
    rec["persona_condition"] = _cond_dict(persona_id="levi")
    _write_drops(drops, [rec])
    records = [{"record_id": "t1", "text": "User: hi\nLEVI: hi."}]
    result = run_round(
        cfg,
        intake_fn=_fake_intake_ok(records),
        eval_fn=lambda cfg: {"ran": True, "scores": {"arith-1": 0.9}},
    )
    assert not result["aborted"]
    entry = result["entry"]
    assert len(entry["conditions"]) == 2
    assert {c["persona_id"] for c in entry["conditions"]} == {"levi", "echo"}
    assert all(c["provisional"] for c in entry["conditions"])


def test_default_conditions_untouched_by_seats():
    conds = default_conditions()
    assert len(conds) == 4  # the original provisional catalog frames
    assert not any(c.persona_id in personas.SEAT_IDS for c in conds)
    assert not any(c.persona_id in personas.FACET_IDS for c in conds)


def test_seventeen_approved_personas_resolve():
    """Chauncey approved these 17 roles (2026-09-21): every id must
    resolve through the provisional persona resolver the tag-team loop
    actually uses."""
    approved = [
        "accountant",
        "astrologer",
        "composer",
        "dream_interpreter",
        "financial_analyst",
        "investment_manager",
        "marketer",
        "math_teacher",
        "pet_behaviorist",
        "psychologist",
        "rapper",
        "real_estate_agent",
        "recruiter",
        "social_media_influencer",
        "travel_guide",
        "therapist",
        "stand_up_comedian",
    ]
    ids = personas.provisional_persona_ids()
    missing = [pid for pid in approved if pid not in ids]
    assert not missing, f"approved personas not in catalog: {missing}"
    # and each one is a well-formed condition persona_id
    for pid in approved:
        cond = validate_condition(_cond_dict(persona_id=pid))
        assert cond.persona_id == pid
