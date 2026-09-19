"""Tests for revival wave 07 — crafts (e): joinery, layers, canes, parchment, grammar, wedges, substitutes."""

import pytest

from levi.revival import friction_fit as ff
from levi.revival import fused_layers as fl
from levi.revival import cane_templates as ct
from levi.revival import recto_verso as rv
from levi.revival import proportional_grammar as pg
from levi.revival import wedge_geometry as wg
from levi.revival import honest_substitute as hs


# ---------------------------------------------------------------- friction_fit
def _peg_socket():
    # peg deliberately oversize vs socket: worst-case stack still interferes
    peg = ff.Interface(
        name="tenon",
        role="peg",
        nominal=20.05,
        length=40.0,
        tolerance=0.02,
        taper_deg=2.0,
        friction_mu=0.4,
    )
    socket = ff.Interface(
        name="mortise",
        role="socket",
        nominal=20.0,
        length=40.0,
        tolerance=0.02,
        taper_deg=2.0,
        friction_mu=0.4,
    )
    return peg, socket


def test_friction_fit_interference_holds():
    peg, socket = _peg_socket()
    j = ff.Joint(peg=peg, socket=socket)
    assert j.fit_class() is ff.FitClass.INTERFERENCE
    assert j.holding_force() > 0
    score, notes = j.safety_surface()
    assert score > 0.5
    assert any("interference" in n for n in notes)


def test_friction_fit_clearance_fails_safely():
    peg = ff.Interface(
        name="tenon", role="peg", nominal=20.0, length=40.0, tolerance=0.02
    )
    socket = ff.Interface(
        name="mortise", role="socket", nominal=20.5, length=40.0, tolerance=0.02
    )
    j = ff.Joint(peg=peg, socket=socket)
    assert j.fit_class() is ff.FitClass.CLEARANCE
    assert j.holding_force() == 0.0
    score, notes = j.safety_surface()
    assert score < 0.6
    assert any("fastener" in n for n in notes)


def test_friction_fit_frame_weakest_and_seismic():
    peg, socket = _peg_socket()
    strong = ff.Joint(peg=peg, socket=socket, name="strong")
    weak_peg = ff.Interface(
        name="wpeg",
        role="peg",
        nominal=20.02,
        length=10.0,
        tolerance=0.02,
        friction_mu=0.1,
    )
    weak_sock = ff.Interface(
        name="wsock",
        role="socket",
        nominal=20.0,
        length=10.0,
        tolerance=0.02,
        friction_mu=0.1,
    )
    weak = ff.Joint(peg=weak_peg, socket=weak_sock, name="weak")
    frame = ff.Frame(joints=[strong, weak])
    wj, wf = frame.weakest()
    assert wj.name == "weak"
    assert wf < strong.holding_force()
    report = frame.seismic_report()
    assert set(report) == {"strong", "weak"}
    assert report["strong"] > report["weak"]


def test_friction_fit_bad_roles_rejected():
    peg, _ = _peg_socket()
    with pytest.raises(ValueError):
        ff.Joint(peg=peg, socket=peg)


# ---------------------------------------------------------------- fused_layers
def test_fused_layers_seal_and_render():
    pane = fl.Pane.seal("raw harvest text")
    pane.add_layer("first reading", author="levi")
    pane.add_layer("second reading", author="levi")
    rendered = pane.render()
    assert "raw harvest text" in rendered
    assert "first reading" in rendered
    assert "second reading" in rendered
    assert rendered.index("raw harvest") < rendered.index("first reading")
    assert pane.verify()


def test_fused_layers_supersede_keeps_history():
    pane = fl.Pane.seal("base")
    pane.add_layer("old note", author="levi")
    pane.supersede(0, "corrected note", author="levi")
    assert pane.layers[0].superseded_by == 1
    assert "old note" in pane.render()  # history stays
    assert "corrected note" in pane.render()
    assert len(pane.active_layers()) == 1  # meaning moved forward
    assert pane.verify()
    with pytest.raises(ValueError):
        pane.supersede(0, "again")  # cannot supersede twice


def test_fused_layers_tamper_detected():
    pane = fl.Pane.seal("base")
    pane.add_layer("honest note", author="levi")
    pane.layers[0].note = "forged note"  # in-place edit = tampering
    assert not pane.verify()


def test_fused_layers_empty_note_rejected():
    pane = fl.Pane.seal("base")
    with pytest.raises(ValueError):
        pane.add_layer("   ")


# ---------------------------------------------------------------- cane_templates
def _flower():
    return ct.Cane(name="flower").draw(
        [
            ["R", "W", "R"],
            ["W", "Y", "W"],
            ["R", "W", "R"],
        ]
    )


def test_cane_slice_is_lossless():
    cane = _flower()
    slices = cane.slice(100)
    assert len(slices) == 100
    assert cane.is_identical(slices)
    assert all(s == cane.master for s in slices)


def test_cane_encode_decode_roundtrip():
    cane = _flower()
    payload = cane.encode(50)
    rebuilt, draws = ct.Cane.decode(payload)
    assert draws == 50
    assert rebuilt.master == cane.master
    assert rebuilt.name == "flower"
    with pytest.raises(ValueError):
        ct.Cane.decode("garbage")
    with pytest.raises(ValueError):
        ct.Cane.decode("x|2x2|1|ABC")  # body length mismatch


def test_cane_millefiori_bundles():
    a = ct.Cane(name="a").draw([["A", "A"], ["A", "A"]])
    b = ct.Cane(name="b").draw([["B", "B"], ["B", "B"]])
    fiori = ct.millefiori([a, b], name="ab")
    assert fiori.shape == (2, 4)
    assert fiori.master[0] == ("A", "A", "B", "B")
    pal = ct.palette_usage(fiori)
    assert pal == {"A": 4, "B": 4}
    with pytest.raises(ValueError):
        ct.millefiori([])


def test_cane_compression_ratio_honest():
    cane = _flower()
    ratio = cane.compression_ratio(1000)
    assert ratio > 1.0  # master+count is smaller than spelling out 1000 slices


# ---------------------------------------------------------------- recto_verso
def test_recto_verso_write_and_read_both_faces():
    hide = rv.Hide()
    leaf = hide.write(
        "the king is tall", author="carver", source="primary", claim="fact"
    )
    assert hide.read_recto(leaf.id).text == "the king is tall"
    verso = hide.read_verso(leaf.id)
    assert verso.author == "carver"
    assert verso.source == "primary"
    assert leaf.tension() == 1.0
    assert hide.chain_ok()


def test_recto_verso_tension_flags_slack():
    hide = rv.Hide()
    taut = hide.write("measured height", author="a", source="primary", claim="fact")
    slack = hide.write(
        "definitely true rumor", author="b", source="hearsay", claim="fact"
    )
    assert taut.tension() == 1.0
    assert slack.tension() < 0.5
    assert [leaf.id for leaf in hide.slack()] == [slack.id]
    report = hide.tension_report()
    assert report[0]["taut"] and not report[1]["taut"]


def test_recto_verso_query_either_face():
    hide = rv.Hide()
    hide.write("alpha note", author="ana", source="cited", claim="estimate")
    hide.write("beta note", author="bob", source="recalled", claim="guess")
    assert len(hide.search_recto("alpha")) == 1
    assert len(hide.search_verso(author="bob")) == 1
    assert len(hide.search_verso(source="cited")) == 1
    assert hide.search_recto("zzz") == []


def test_recto_verso_bad_fields_rejected():
    hide = rv.Hide()
    with pytest.raises(ValueError):
        hide.write("", author="a")
    with pytest.raises(ValueError):
        hide.write("x", author="a", source="telepathy")
    with pytest.raises(ValueError):
        hide.write("x", author="a", claim="certainty")


# ---------------------------------------------------------------- proportional_grammar
def test_proportional_grammar_canonical_validates():
    spec = pg.grammar(95.0)
    assert pg.validate(spec) == []
    king = spec["king"]
    assert king.height == 95.0
    assert king.base_dia == pytest.approx(95.0 * 0.40)
    ladder = pg.ladder(95.0)
    assert [p for p, _ in ladder] == [
        "king",
        "queen",
        "bishop",
        "rook",
        "knight",
        "pawn",
    ]


def test_proportional_grammar_scales():
    small = pg.grammar(50.0)
    big = pg.grammar(100.0)
    assert small["pawn"].height == pytest.approx(big["pawn"].height / 2)
    assert pg.validate(small) == []
    assert pg.validate(big) == []


def test_proportional_grammar_violations_reported():
    spec = pg.grammar(95.0)
    spec["pawn"] = pg.PieceSpec(piece="pawn", height=90.0, base_dia=20.0, finial_rank=5)
    problems = pg.validate(spec)
    assert any("40%" in p for p in problems)
    assert any("pawn" in p and "knight" in p for p in problems)
    # missing piece
    del spec["rook"]
    assert any("missing" in p for p in pg.validate(spec))


def test_proportional_grammar_unknown_piece():
    with pytest.raises(ValueError):
        pg.spec_for("dragon", 95.0)


# ---------------------------------------------------------------- wedge_geometry
def _started_board():
    b = wg.Board()
    p1 = b.mint("lance", owner="sente", grade=4)
    p2 = b.mint("pawn", owner="gote", grade=3)
    b.place(p1, (2, 2))
    b.place(p2, (3, 3))
    return b, p1, p2


def test_wedge_capture_flips_and_wears():
    b, p1, p2 = _started_board()
    captured = b.capture((3, 3), by="sente")
    assert captured.owner == "sente"
    assert captured.points_at() == "enemy-of-sente"
    assert captured.grade == 2  # worn one grade by the capture
    assert b.at((3, 3)) is None
    assert captured in b.hand_of("sente")


def test_wedge_drop_rule():
    b, p1, p2 = _started_board()
    captured = b.capture((3, 3), by="sente")
    dropped = b.drop("sente", captured.id, (4, 4))
    assert b.at((4, 4)) is dropped
    assert dropped not in b.hand_of("sente")
    with pytest.raises(ValueError):
        b.drop("sente", captured.id, (4, 4))  # no longer in hand
    with pytest.raises(ValueError):
        b.drop("gote", 999, (0, 0))  # not gote's piece


def test_wedge_drop_onto_occupied_rejected():
    b, p1, p2 = _started_board()
    captured = b.capture((3, 3), by="sente")
    with pytest.raises(ValueError):
        b.drop("sente", captured.id, (2, 2))  # occupied by p1


def test_wedge_craft_loop_recarve():
    b, p1, p2 = _started_board()
    captured = b.capture((3, 3), by="sente")
    assert captured.grade == 2
    b.recarve(captured, 4, carver="tendo-master")
    assert captured.grade == 4
    assert any("recarve" in e for e in b.ledger)
    assert any("capture" in e for e in b.ledger)
    with pytest.raises(ValueError):
        b.recarve(captured, 9, carver="x")


# ---------------------------------------------------------------- honest_substitute
def _catalog():
    cat = hs.MaterialCatalog()
    cat.add(hs.Material(name="kaya", canonical=True, available=False, stability=0.95))
    cat.add(hs.Material(name="spruce", available=True, local=True, stability=0.7))
    cat.add(
        hs.Material(
            name="fake-kaya",
            available=True,
            local=False,
            stability=0.8,
            declares_itself=False,
        )
    )
    return cat


def test_honest_substitute_pretender_penalized():
    cat = _catalog()
    ranked = cat.pick_substitute()
    names = [m.name for m, _, _ in ranked]
    assert "kaya" not in names  # canonical never offered as substitute
    assert names[0] == "spruce"  # honest local beats higher-stability pretender
    spruce_score = next(s for m, s, _ in ranked if m.name == "spruce")
    fake_score = next(s for m, s, _ in ranked if m.name == "fake-kaya")
    assert spruce_score > fake_score


def test_honest_substitute_grid_geometry():
    cat = _catalog()
    spruce = next(m for m in cat.materials if m.name == "spruce")
    plan = hs.BoardPlan(material=spruce)
    v, h = plan.generate_grid()
    assert len(v) == 19 and len(h) == 19
    assert v[1] - v[0] == pytest.approx(21.5)
    assert h[1] - h[0] == pytest.approx(23.0)
    w, d = plan.board_size()
    assert w == pytest.approx(18 * 21.5)
    assert d == pytest.approx(18 * 23.0)
    assert len(plan.star_points()) == 9
    label = plan.label()
    assert "spruce" in label and "kaya" in label and "Substitute" in label


def test_honest_substitute_hand_drawn_reproducible():
    cat = _catalog()
    spruce = next(m for m in cat.materials if m.name == "spruce")
    plan = hs.BoardPlan(material=spruce)
    v1, h1 = plan.hand_drawn(seed=7)
    v2, h2 = plan.hand_drawn(seed=7)
    assert v1 == v2 and h1 == h2  # seeded: same hand twice
    v3, _ = plan.hand_drawn(seed=8)
    assert v1 != v3
    # still recognizably the grid, just with a human hand
    v_exact, _ = plan.generate_grid()
    assert all(abs(a - b) <= 0.3 for a, b in zip(v1, v_exact, strict=True))
