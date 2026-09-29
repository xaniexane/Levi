"""Tests for the gavel engine (adjudicated rulings over competing claims)."""

import pytest

from levi.engines import registry
from levi.engines.base import EngineInputError


def run(**kwargs):
    return registry.run("gavel", kwargs)


def claims(*specs):
    out = []
    for spec in specs:
        name, evidence = spec[0], spec[1]
        entry = {"claim": name, "evidence": evidence}
        if len(spec) > 2:
            entry.update(spec[2])
        out.append(entry)
    return out


def test_gavel_registered():
    assert registry.get("gavel").name == "Gavel"


def test_clear_winner_upheld():
    result = run(
        claims=claims(("ship", 0.9), ("hold", 0.2)),
    )
    assert result.verdict["ruling"] == "upheld"
    assert result.verdict["prevailing"] == "ship"
    assert result.confidence > 0.5


def test_incumbent_upheld_when_burden_met():
    result = run(
        claims=claims(("hold", 0.8), ("ship", 0.3)),
        incumbent="hold",
    )
    assert result.verdict["ruling"] == "upheld"
    assert result.verdict["prevailing"] == "hold"


def test_challenger_overturns_weak_incumbent():
    result = run(
        claims=claims(("hold", 0.2), ("ship", 0.9)),
        incumbent="hold",
    )
    assert result.verdict["ruling"] == "overturned"
    assert result.verdict["prevailing"] == "ship"


def test_split_when_nobody_meets_burden():
    result = run(
        claims=claims(("ship", 0.45), ("hold", 0.44), ("wait", 0.4)),
        remand_floor=0.1,
    )
    assert result.verdict["ruling"] == "split"
    assert result.verdict["prevailing"] is None


def test_remanded_when_all_below_floor():
    result = run(
        claims=claims(("ship", 0.1), ("hold", 0.05)),
        remand_floor=0.25,
    )
    assert result.verdict["ruling"] == "remanded"
    assert result.verdict["prevailing"] is None
    assert result.confidence == 0.0


def test_remanded_when_no_evidence_at_all():
    result = run(claims=claims(("ship", 0.0), ("hold", 0.0)))
    assert result.verdict["ruling"] == "remanded"
    assert result.verdict["prevailing"] is None


def test_contradiction_penalty_flips_outcome():
    clean = run(claims=claims(("ship", 0.7), ("hold", 0.6)))
    assert clean.verdict["prevailing"] == "ship"
    penalized = run(
        claims=claims(
            ("ship", 0.7, {"contradicted": True}),
            ("hold", 0.6),
        )
    )
    assert penalized.verdict["scores"]["ship"] == pytest.approx(0.35)
    assert penalized.verdict["prevailing"] == "hold"


def test_tie_breaks_by_evidence_then_order_deterministically():
    # A top tie can never clear preponderance (leader share < 0.5), so the
    # observable tie-break is the ranking: same score + same evidence ->
    # input order decides, identically every run.
    first = run(claims=claims(("alpha", 0.9), ("beta", 0.9)))
    second = run(claims=claims(("alpha", 0.9), ("beta", 0.9)))
    assert first.verdict == second.verdict
    assert first.verdict["ruling"] == "split"
    assert first.verdict["ranking"] == ["alpha", "beta"]
    flipped = run(claims=claims(("beta", 0.9), ("alpha", 0.9)))
    assert flipped.verdict["ranking"] == ["beta", "alpha"]


def test_tie_breaks_by_evidence_before_order():
    # Same penalized score, different raw evidence: higher evidence wins.
    result = run(
        claims=claims(
            ("alpha", 0.8, {"weight": 1.0}),
            ("beta", 0.4, {"weight": 2.0}),
            ("gamma", 0.1),
        )
    )
    assert result.verdict["scores"]["alpha"] == pytest.approx(
        result.verdict["scores"]["beta"]
    )
    assert result.verdict["ranking"][0] == "alpha"


def test_higher_burden_blocks_weak_leader():
    result = run(
        claims=claims(("ship", 0.6), ("hold", 0.3)),
        standard="beyond_doubt",
        remand_floor=0.1,
    )
    assert result.verdict["ruling"] == "split"


def test_monotonicity_evidence_raise_never_lowers_rank():
    before = run(
        claims=claims(("ship", 0.4), ("hold", 0.5)),
    )
    after = run(
        claims=claims(("ship", 0.9), ("hold", 0.5)),
    )
    before_rank = sorted(
        before.verdict["scores"], key=lambda n: -before.verdict["scores"][n]
    )
    after_rank = sorted(
        after.verdict["scores"], key=lambda n: -after.verdict["scores"][n]
    )
    assert after_rank.index("ship") <= before_rank.index("ship")


def test_determinism_identical_inputs_identical_verdict():
    kwargs = dict(
        claims=claims(
            ("ship", 0.75, {"weight": 1.5}),
            ("hold", 0.6, {"contradicted": True}),
            ("wait", 0.5),
        ),
        incumbent="hold",
        standard="clear",
    )
    assert run(**kwargs).verdict == run(**kwargs).verdict


def test_empty_claims_refused():
    with pytest.raises(ValueError):
        run(claims=[])


def test_missing_claims_refused():
    with pytest.raises(EngineInputError):
        run()


def test_duplicate_claim_names_refused():
    with pytest.raises(ValueError, match="duplicate"):
        run(claims=claims(("ship", 0.5), ("ship", 0.4)))


def test_evidence_out_of_range_refused():
    with pytest.raises(ValueError):
        run(claims=claims(("ship", 1.5), ("hold", 0.2)))


def test_unknown_standard_refused():
    with pytest.raises(ValueError, match="standard"):
        run(claims=claims(("ship", 0.9), ("hold", 0.1)), standard="vibes")


def test_unknown_incumbent_refused():
    with pytest.raises(ValueError, match="incumbent"):
        run(claims=claims(("ship", 0.9), ("hold", 0.1)), incumbent="mystery")


def test_trace_records_each_claim_and_ruling():
    result = run(claims=claims(("ship", 0.9), ("hold", 0.2)))
    assert any("ship" in line for line in result.trace)
    assert any(line.startswith("ruling:") for line in result.trace)


def test_shares_sum_to_one():
    result = run(claims=claims(("a", 0.3), ("b", 0.5), ("c", 0.2)))
    assert sum(result.verdict["shares"].values()) == pytest.approx(1.0)
