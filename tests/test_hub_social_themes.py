"""Hub social themes — theme-pack format, applier, store, PL-05 cut math.

Hermetic: no network, no HOME writes (LEVI_HUB_SOCIAL_DIR redirected to tmp).
"""

import pytest

from levi.hub import themes
from levi.hub.themes import (
    PLATFORM_CUT,
    THEME_SURFACES,
    ThemePack,
    ThemeStore,
    creator_net,
    css_variables,
    cut_disclosure,
    paper_pack,
    platform_cut_cents,
    stated_price_for_net,
    void_pack,
    dusk_pack,
)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HUB_SOCIAL_DIR", str(tmp_path / "social"))
    return ThemeStore()


# -- validation: proposer/verifier passes ---------------------------------

GOOD_TOKENS = {
    "bg": "#0d1117",
    "bg2": "#161b22",
    "line": "#30363d",
    "fg": "#e6edf3",
    "dim": "#8b949e",
    "accent": "#58a6ff",
    "ok": "#3fb950",
    "warn": "#d29922",
    "danger": "#f85149",
    "font": "system",
    "radius": "md",
    "density": "comfortable",
}


def _pack(**tok_overrides):
    tokens = dict(GOOD_TOKENS)
    tokens.update(tok_overrides)
    return ThemePack.from_dict(
        {
            "name": "Test",
            "author": "me",
            "version": "1.0.0",
            "description": "t",
            "tokens": tokens,
        }
    )


def test_valid_pack_passes_both_passes():
    pack = _pack()
    assert pack.name == "Test"
    assert pack.tokens["bg"] == "#0d1117"


def test_rejects_non_hex_color():
    with pytest.raises(themes.ThemeError):
        _pack(bg="red")


def test_rejects_css_function_injection():
    with pytest.raises(themes.ThemeError):
        _pack(bg="url(javascript:alert(1))")


def test_rejects_raw_css_value():
    with pytest.raises(themes.ThemeError):
        _pack(accent="expression(alert(1))")


def test_rejects_unknown_token():
    with pytest.raises(themes.ThemeError):
        _pack(**{"background-image": "x"})


def test_rejects_unknown_font_stack():
    with pytest.raises(themes.ThemeError):
        _pack(font="http-evil")


def test_rejects_markup_in_meta():
    with pytest.raises(themes.ThemeError):
        ThemePack.from_dict(
            {
                "name": "<script>alert(1)</script>",
                "author": "me",
                "version": "1.0.0",
                "description": "t",
                "tokens": GOOD_TOKENS,
            }
        )


def test_rejects_bad_version():
    with pytest.raises(themes.ThemeError):
        ThemePack.from_dict(
            {
                "name": "T",
                "author": "me",
                "version": "soon",
                "description": "t",
                "tokens": GOOD_TOKENS,
            }
        )


def test_rejects_invalid_json():
    with pytest.raises(themes.ThemeError):
        ThemePack.from_json("{not json")


def test_round_trip_portable():
    pack = _pack()
    back = ThemePack.from_json(pack.to_json())
    assert back.to_dict() == pack.to_dict()


def test_derive_keeps_validation():
    pack = _pack().derive(bg="#ffffff")
    assert pack.tokens["bg"] == "#ffffff"
    with pytest.raises(themes.ThemeError):
        _pack().derive(bg="not-a-color")


# -- builtins --------------------------------------------------------------


def test_builtin_packs_are_valid():
    for pack in (void_pack(), paper_pack(), dusk_pack()):
        assert pack.tokens["density"] in ("compact", "comfortable", "airy")


# -- CSS application: throughout, one code path ----------------------------


def test_css_variables_cover_all_color_tokens():
    css = css_variables(_pack())
    for token in themes.COLOR_TOKENS:
        assert f"--hub-{token}:" in css
    assert "--hub-font:" in css and "--hub-density:" in css


def test_css_contains_no_user_markup():
    # The CSS block is generated from validated values only — no way to
    # smuggle a rule, import, or URL through the token space.
    css = css_variables(_pack())
    assert "url(" not in css and "<" not in css and "expression" not in css


def test_store_active_css_applies_everywhere(store):
    for surface in THEME_SURFACES:
        css = store.css_for_surface(surface)
        assert css == store.active_css()  # same pack, every surface


def test_css_for_unknown_surface_is_loud(store):
    with pytest.raises(themes.ThemeError):
        store.css_for_surface("nonexistent-surface")


# -- store: install / activate / list ---------------------------------------


def test_store_install_activate_roundtrip(store):
    pack = _pack()
    store.install(pack)
    assert "Test" in store.list()
    activated = store.activate("Test")
    assert activated.name == "Test"
    assert store.active().name == "Test"


def test_store_default_is_void(store):
    assert store.active().name == "Void"


def test_store_deactivate_returns_to_void(store):
    store.activate("Paper")
    assert store.deactivate().name == "Void"
    assert store.active().name == "Void"


def test_store_protects_builtin_names(store):
    evil = _pack()
    raw = evil.to_dict()
    raw["name"] = "Void"
    with pytest.raises(themes.ThemeError):
        store.install(ThemePack.from_dict(raw))


def test_store_list_survives_corrupt_file(store):
    store.install(_pack())
    (store.data_dir / "zzz.theme.json").write_text("{broken", encoding="utf-8")
    assert "Test" in store.list()  # corrupt file skipped, never fatal


def test_activate_unknown_raises(store):
    with pytest.raises(OSError):
        store.activate("no-such-pack")


# -- PL-05: the stated 12% cut — named constant, pure math -----------------


def test_platform_cut_is_named_constant():
    assert PLATFORM_CUT == 0.12


def test_creator_net_on_dollar_pack():
    # $1.00 pack: creator keeps $0.88, platform takes $0.12.
    assert creator_net(100) == 88
    assert platform_cut_cents(100) == 12


def test_cut_math_round_trips():
    for gross in (100, 250, 999, 10000):
        net = creator_net(gross)
        assert stated_price_for_net(net) <= gross + 1
        assert platform_cut_cents(gross) + net in (gross - 1, gross, gross + 1)


def test_cut_math_rejects_negatives():
    with pytest.raises(ValueError):
        creator_net(-1)
    with pytest.raises(ValueError):
        stated_price_for_net(-5)


def test_cut_disclosure_states_single_number():
    text = cut_disclosure()
    assert "12%" in text
    assert "Physical" in text  # open economics stated, not assumed


def test_no_physical_cut_anywhere():
    # The module exposes no physical-goods cut constant or function.
    names = [n for n in dir(themes) if "physical" in n.lower()]
    assert names == []
