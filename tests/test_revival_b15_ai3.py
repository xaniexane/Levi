"""Tests for revival batch B15: contextpack, lora, taskvec, tokbudget."""

import pytest

from core.levi.revival import contextpack, lora, taskvec, tokbudget


# ---------------- contextpack ----------------


def test_pack_orders_by_salience_density_not_input_order():
    cheap_key = contextpack.Piece("key", "Levi is local-first.", salience=1.0)
    long_fluff = contextpack.Piece(
        "fluff",
        " ".join(["filler"] * 100),
        salience=0.1,
    )
    result = contextpack.pack([long_fluff, cheap_key], budget=50)
    ids = [d.piece_id for d in result.decisions]
    assert ids[0] == "key"  # higher density packs first regardless of order
    assert result.tokens_used <= 50


def test_pack_reports_what_was_cut_and_why():
    body = " ".join(f"Sentence number {i} carries real signal here." for i in range(20))
    pieces = [
        contextpack.Piece("a", body, salience=0.9),
        contextpack.Piece("b", body, salience=0.1),
    ]
    result = contextpack.pack(pieces, budget=40)
    assert result.tokens_used <= 40
    actions = {d.piece_id: d.action for d in result.decisions}
    assert actions["a"] == "summarized"  # almost fits -> summary
    assert actions["b"] == "cut"  # no room left
    assert all(d.reason for d in result.decisions)  # every decision explains itself
    assert (
        "summar" in result.decisions[0].reason
        or "summary" in result.decisions[0].reason
    )


def test_extractive_summary_preserves_order_and_fits():
    text = (
        "The budget is scarce. "
        "Guard the budget well. "
        "Rain falls softly down. "
        "Clouds gather far away."
    )
    summary = contextpack.extractive_summary(text, token_allowance=15)
    assert contextpack.estimate_tokens(summary) <= 15
    assert summary.count("budget") == 2  # the repeated keyword wins
    # source order preserved among the chosen sentences
    first = summary.index("The budget is scarce.")
    second = summary.index("Guard the budget well.")
    assert first < second


def test_pack_everything_fits_is_verbatim():
    pieces = [contextpack.Piece("a", "Hello world.", 0.5)]
    result = contextpack.pack(pieces, budget=1000)
    assert result.decisions[0].action == "kept"
    assert result.packed_text == "Hello world."
    assert result.pieces_cut == []


def test_pack_negative_budget_rejected():
    with pytest.raises(ValueError):
        contextpack.pack([], budget=-1)


# ---------------- lora ----------------


def test_lora_zero_init_is_identity():
    adapter = lora.LoRAAdapter(d_in=3, d_out=2, rank=4, seed=0)
    assert adapter.is_identity()
    x = [1.0, -2.0, 0.5]
    assert adapter.apply(x) == [0.0, 0.0]
    delta = adapter.delta()
    assert all(v == 0.0 for row in delta for v in row)


def test_lora_forward_formula_matches_spec():
    W0 = [[1.0, 0.0], [0.0, 2.0]]
    layer = lora.LoRALinear(W0)
    adapter = lora.LoRAAdapter(2, 2, rank=4, alpha=8.0, seed=3)
    layer.attach(adapter)
    x = [1.5, -0.5]
    out = layer.forward(x)
    # h = W0x + (B(Ax)) * (alpha/r)
    base = lora.matvec(W0, x)
    ax = lora.matvec(adapter.A, x)
    bax = lora.matvec(adapter.B, ax)
    expected = [b + d * (8.0 / 4) for b, d in zip(base, bax, strict=True)]
    assert out == pytest.approx(expected)


def test_lora_merge_is_free_and_exact():
    W0 = [[0.5, 1.5], [-1.0, 0.25]]
    layer = lora.LoRALinear(W0)
    adapter = lora.LoRAAdapter(2, 2, rank=8, seed=1)
    for _ in range(20):
        out = layer.forward([1.0, 1.0])
        adapter.train_step([1.0, 1.0], [2.0 - out[0], -1.0 - out[1]], lr=0.05)
    layer.attach(adapter)
    x = [0.7, -1.3]
    adapted = layer.forward(x)
    merged = layer.merged_weights()
    assert lora.matvec(merged, x) == pytest.approx(adapted)
    # base untouched: the freeze is real
    assert layer.W0 == W0


def test_lora_adapter_swap_changes_behavior():
    W0 = [[1.0, 0.0], [0.0, 1.0]]
    layer = lora.LoRALinear(W0)
    a1 = lora.LoRAAdapter(2, 2, rank=4, seed=10)
    a2 = lora.LoRAAdapter(2, 2, rank=4, seed=11)
    x = [1.0, 1.0]
    for _ in range(30):
        o1 = [b + d for b, d in zip(lora.matvec(W0, x), a1.apply(x), strict=True)]
        a1.train_step(x, [5.0 - o1[0], 0.0 - o1[1]], lr=0.05)
        o2 = [b + d for b, d in zip(lora.matvec(W0, x), a2.apply(x), strict=True)]
        a2.train_step(x, [0.0 - o2[0], 5.0 - o2[1]], lr=0.05)
    layer.attach(a1)
    out1 = layer.forward(x)
    layer.attach(a2)  # swap: same base, different skill
    out2 = layer.forward(x)
    assert out1[0] > out1[1] and out2[1] > out2[0]
    layer.detach()
    assert layer.forward(x) == pytest.approx([1.0, 1.0])


def test_lora_adapter_is_tiny_next_to_base():
    adapter = lora.LoRAAdapter(d_in=64, d_out=64, rank=8)
    assert adapter.param_count() == 8 * (64 + 64)
    assert adapter.param_count() < 64 * 64


# ---------------- taskvec ----------------


def test_linear_merge_is_weighted_average():
    base = [0.0, 0.0]
    taus = [[2.0, 4.0], [6.0, 8.0]]
    merged = taskvec.merge_taus(base, taus, "linear", weights=[0.25, 0.75])
    assert merged == pytest.approx([0.25 * 2 + 0.75 * 6, 0.25 * 4 + 0.75 * 8])


def test_slerp_preserves_norm():
    a = [3.0, 1.0, 0.5]
    b = [0.5, 4.0, -1.0]
    mid = taskvec.slerp(a, b, 0.5)
    na, nb = taskvec.norm(a), taskvec.norm(b)
    # slerp rides the arc: norm stays between the two endpoint norms,
    # never dipping through the middle like a linear blend
    linear_mid = [(x + y) / 2 for x, y in zip(a, b, strict=True)]
    assert min(na, nb) - 1e-9 <= taskvec.norm(mid) <= max(na, nb) + 1e-9
    assert taskvec.norm(mid) >= taskvec.norm(linear_mid) - 1e-9
    # endpoints are exact
    assert taskvec.slerp(a, b, 0.0) == pytest.approx(a)
    assert taskvec.slerp(a, b, 1.0) == pytest.approx(b)


def test_ties_elects_majority_sign():
    # three vectors agree dim0 is positive, two say dim1 is negative vs one positive
    taus = [
        [0.9, -0.8, 0.0],
        [0.7, -0.6, 0.0],
        [0.8, 0.5, 0.0],
    ]
    merged = taskvec.ties_merge(taus, keep_frac=1.0)
    assert merged[0] == pytest.approx((0.9 + 0.7 + 0.8) / 3)  # unanimous positive
    assert merged[1] == pytest.approx((-0.8 + -0.6) / 2)  # majority negative wins
    assert merged[2] == 0.0


def test_ties_trims_low_magnitude_deltas():
    taus = [[10.0, 0.01, 0.02], [9.0, 0.01, -0.01]]
    merged = taskvec.ties_merge(taus, keep_frac=0.34)  # keep ~1 of 3 per vector
    assert merged[0] == pytest.approx(9.5)  # the big deltas survive trimming
    assert merged[1] == 0.0 and merged[2] == 0.0  # the small ones are trimmed away


def test_dare_rescales_survivors():
    taus = [[2.0, 2.0, 2.0, 2.0]]
    merged = taskvec.dare_merge(taus, drop_p=0.5, seed=42)
    # survivors rescaled by 1/(1-0.5)=2, dropped are 0
    assert set(merged) <= {0.0, 4.0}
    assert any(v == 4.0 for v in merged) and any(v == 0.0 for v in merged)


def test_dare_zero_drop_is_identity():
    taus = [[1.5, -2.5], [0.5, 0.5]]
    assert taskvec.dare_merge(taus, drop_p=0.0) == pytest.approx([1.0, -1.0])


def test_task_vector_roundtrip():
    base = [1.0, 2.0, 3.0]
    ft = [1.5, 1.0, 3.3]
    assert taskvec.apply(base, taskvec.task_vector(ft, base)) == pytest.approx(ft)


# ---------------- tokbudget ----------------


def _ledger():
    led = tokbudget.TokenLedger()
    led.open_session(
        "s1",
        component_caps={
            "retriever": tokbudget.Cap(limit=100),
            "reflector": tokbudget.Cap(limit=50, on_exceed="refuse"),
        },
        session_cap=tokbudget.Cap(limit=500),
    )
    return led


def test_spend_tracks_per_component_and_session():
    led = _ledger()
    assert led.spend("s1", "retriever", 40, "docs")
    assert led.spend("s1", "planner", 30, "plan")  # uncapped component
    assert led.spent("s1", "retriever") == 40
    assert led.session_spent("s1") == 70
    assert led.headroom("s1", "retriever") == 60
    assert led.headroom("s1", "planner") is None


def test_fit_degrades_to_summary_instead_of_truncating():
    led = _ledger()
    led.spend("s1", "retriever", 60, "first docs")
    long_text = " ".join(
        [
            "The retriever found many documents about local-first synthetic intelligence.",
            "Context tokens are the scarce resource in every agent loop.",
            "Summarization preserves the shape of the knowledge while fitting the budget.",
            "Rain is expected tomorrow with a chance of scattered thunderstorms.",
        ]
    )
    ok, used, degraded = led.fit("s1", "retriever", long_text, "second docs")
    assert ok and degraded  # accepted, but as a summary
    assert tokbudget.estimate_tokens(used) <= 40  # only ~40 tok headroom left
    assert "scarce resource" in used  # salient content survives the squeeze
    assert led.spent("s1", "retriever") <= 100


def test_fit_refuse_policy_blocks_and_keeps_text():
    led = _ledger()
    text = "word " * 100
    ok, used, degraded = led.fit("s1", "reflector", text, "deep thoughts")
    assert not ok and not degraded
    assert used == text  # caller's text returned untouched
    assert led.spent("s1", "reflector") == 0


def test_session_cap_blocks_across_components():
    led = tokbudget.TokenLedger()
    led.open_session("s2", session_cap=tokbudget.Cap(limit=50))
    assert led.spend("s2", "a", 30)
    assert not led.spend("s2", "b", 30)  # 30+30 > 50
    assert led.session_spent("s2") == 30


def test_receipt_reports_spend_degradations_refusals():
    led = _ledger()
    led.spend("s1", "retriever", 60, "docs")
    long_text = " ".join(
        [
            "The garden needs watering every morning before the sun climbs high.",
            "Roses drink deeply but hate wet leaves at dusk.",
            "Tomatoes want steady moisture and mulch to keep their feet cool.",
            "Compost feeds everything slowly over the whole long season.",
        ]
    )
    ok, _, degraded = led.fit("s1", "retriever", long_text, "more docs")
    assert ok and degraded  # squeezed into the remaining headroom as a summary
    led.spend("s1", "reflector", 60, "too much")  # refused by policy
    receipt = led.receipt("s1")
    assert "retriever" in receipt  # refused components have no spend line...
    assert any(
        "REFUSED" in e.note and e.component == "reflector" for e in led.events("s1")
    )
    assert "degradations: 1" in receipt
    # refusals: fit()'s initial over-cap attempt + the reflector over-cap spend
    assert "refusals: 2" in receipt


def test_unknown_session_raises():
    led = tokbudget.TokenLedger()
    with pytest.raises(KeyError):
        led.spend("nope", "x", 1)
