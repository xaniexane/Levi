"""Tests for levi.social.customize — the MySpace-era canvas engine."""

import pytest

from levi.social.customize import (
    CONTRAST_FLOOR,
    WIDGET_REGISTRY,
    Animation,
    CustomBlock,
    CustomizeError,
    GuestbookEntry,
    Layout,
    ProfileCustomization,
    ProfileSong,
    ProfileTheme,
    Section,
    ThemeToken,
    Widget,
    contrast_ratio,
    enforce_contrast,
)


def _theme(**colors):
    t = ProfileTheme()
    for name, value in colors.items():
        t.set(ThemeToken(name=name, value=value, kind="color"))
    return t


# -- token validation ------------------------------------------------------


def test_token_accepts_valid_color():
    ThemeToken(name="color.text", value="#e8e4da", kind="color").validate()
    ThemeToken(name="color.text", value="#FFF", kind="color").validate()


def test_token_refuses_bad_color():
    with pytest.raises(CustomizeError):
        ThemeToken(name="color.text", value="red", kind="color").validate()
    with pytest.raises(CustomizeError):
        ThemeToken(name="color.text", value="#gggggg", kind="color").validate()


def test_token_refuses_unknown_name():
    with pytest.raises(CustomizeError):
        ThemeToken(name="color.paisley", value="#ffffff", kind="color").validate()


def test_token_font_and_length():
    ThemeToken(name="font.body", value="Georgia", kind="font").validate()
    ThemeToken(name="radius.panel", value="12px", kind="length").validate()
    ThemeToken(name="spacing.gap", value="1.5rem", kind="length").validate()
    with pytest.raises(CustomizeError):
        ThemeToken(name="font.body", value="url(evil)", kind="font").validate()
    with pytest.raises(CustomizeError):
        ThemeToken(name="radius.panel", value="-4px", kind="length").validate()


def test_token_background_forms():
    ThemeToken(name="bg.page", value="#0d0b08", kind="background").validate()
    ThemeToken(
        name="bg.page",
        value={"type": "gradient", "stops": ["#000000", "#ffffff"]},
        kind="background",
    ).validate()
    ThemeToken(
        name="bg.page",
        value={"type": "image", "url": "https://example.com/bg.png"},
        kind="background",
    ).validate()
    with pytest.raises(CustomizeError):
        ThemeToken(
            name="bg.page",
            value={"type": "image", "url": "javascript:alert(1)"},
            kind="background",
        ).validate()
    with pytest.raises(CustomizeError):
        ThemeToken(
            name="bg.page",
            value={"type": "gradient", "stops": ["#000000"]},
            kind="background",
        ).validate()


# -- contrast guardrail ----------------------------------------------------


def test_contrast_ratio_known_values():
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.1)
    assert contrast_ratio("#777777", "#777777") == pytest.approx(1.0, abs=0.01)


def test_strict_mode_refuses_unreadable():
    # Pale yellow text on white page: far below the floor.
    theme = _theme(**{"color.text": "#ffffcc", "bg.page": "#ffffff"})
    with pytest.raises(CustomizeError, match="contrast refusal"):
        enforce_contrast(theme, strict=True)


def test_default_mode_repairs_unreadable():
    theme = _theme(**{"color.text": "#ffffcc", "bg.page": "#ffffff"})
    repaired, notes = enforce_contrast(theme)
    assert len(notes) == 1
    assert "repaired to" in notes[0]
    fixed = repaired.get("color.text").value
    assert contrast_ratio(fixed, "#ffffff") >= CONTRAST_FLOOR
    # The original theme object is untouched (repair returns a new theme).
    assert theme.get("color.text").value == "#ffffcc"


def test_readable_theme_passes_untouched():
    theme = _theme(**{"color.text": "#e8e4da", "bg.page": "#0d0b08"})
    _, notes = enforce_contrast(theme)
    assert notes == []


def test_apply_guardrails_records_repairs():
    pc = ProfileCustomization(profile_id="keeper1")
    pc.theme = _theme(**{"color.text": "#ffffcc", "bg.page": "#ffffff"})
    pc.apply_guardrails()
    assert pc.repairs, "repairs must be recorded for the member to see"
    assert contrast_ratio(
        pc.theme.get("color.text").value, "#ffffff"
    ) >= CONTRAST_FLOOR


# -- reduced motion --------------------------------------------------------


def _animated_profile():
    pc = ProfileCustomization(profile_id="keeper1")
    pc.animations.append(
        Animation(
            name="fade-in",
            target="entrance",
            duration_ms=600,
            easing="ease-out",
            properties=("opacity", "transform"),
        )
    )
    return pc


def test_reduced_motion_degrades_to_static():
    pc = _animated_profile()
    rendered = pc.render(reduced_motion=True)
    assert rendered["reduced_motion"] is True
    assert rendered["animations"] == [
        {"name": "fade-in", "target": "entrance", "motion": "static"}
    ]


def test_full_motion_keeps_descriptors():
    pc = _animated_profile()
    rendered = pc.render()
    assert rendered["animations"][0]["duration_ms"] == 600
    assert rendered["animations"][0]["motion"] != "static" if "motion" in rendered["animations"][0] else True


def test_animation_validation():
    Animation(name="ok", target="text", duration_ms=300).validate()
    with pytest.raises(CustomizeError):
        Animation(name="x", target="text", duration_ms=5).validate()
    with pytest.raises(CustomizeError):
        Animation(name="x", target="text", duration_ms=300, easing="bounce").validate()
    with pytest.raises(CustomizeError):
        Animation(name="x", target="text", duration_ms=300, properties=("margin",)).validate()
    # Entrance must settle neutral — animation never breaks readability.
    with pytest.raises(CustomizeError, match="end neutral"):
        Animation(
            name="drift", target="entrance", duration_ms=300, ends_neutral=False
        ).validate()


# -- widget registry -------------------------------------------------------


def test_widget_registry_known():
    for name in WIDGET_REGISTRY:
        Widget(name=name).validate()


def test_widget_refuses_unknown():
    with pytest.raises(CustomizeError, match="unknown widget"):
        Widget(name="crypto_miner").validate()


def test_widget_refuses_bad_param():
    with pytest.raises(CustomizeError, match="bad param"):
        Widget(name="song_player", params={"mine": True}).validate()
    with pytest.raises(CustomizeError):
        Widget(name="guestbook", params={"max_entries": 5000}).validate()
    with pytest.raises(CustomizeError, match="plain text"):
        Widget(name="mood_status", params={"default_text": "<script>"}).validate()


def test_guestbook_entry_plain_text_only():
    GuestbookEntry(author="friend1", text="great page!").validate()
    with pytest.raises(CustomizeError):
        GuestbookEntry(author="friend1", text="<b>hi</b>").validate()
    with pytest.raises(CustomizeError):
        GuestbookEntry(author="friend1", text="   ").validate()


# -- layouts ---------------------------------------------------------------


def test_layout_default_order():
    layout = Layout.default()
    assert layout.order() == ["bio", "song", "friends", "posts", "guestbook", "mood"]


def test_layout_reorder_myspace_style():
    layout = Layout.default()
    new_order = ["song", "bio", "mood", "friends", "posts", "guestbook"]
    layout.reorder(new_order)
    assert layout.order() == new_order


def test_layout_reorder_refuses_partial_or_invented():
    layout = Layout.default()
    with pytest.raises(CustomizeError, match="every section id"):
        layout.reorder(["song", "bio"])
    with pytest.raises(CustomizeError, match="every section id"):
        layout.reorder(layout.order() + ["glitter"])
    with pytest.raises(CustomizeError, match="every section id"):
        layout.reorder(["song", "song", "bio", "friends", "posts", "guestbook"])


def test_layout_refuses_duplicate_ids():
    with pytest.raises(CustomizeError, match="duplicate"):
        Layout(sections=[Section(id="bio", kind="bio"), Section(id="bio", kind="bio")])


# -- profile song: never an ambush -----------------------------------------


def test_song_defaults_no_autoplay():
    song = ProfileSong(ref="https://example.com/anthem.mp3", title="Anthem")
    assert song.autoplay is False


def test_song_refuses_autoplay():
    with pytest.raises(CustomizeError, match="autoplay refused"):
        ProfileSong(ref="track:123", autoplay=True)


def test_song_ref_forms():
    ProfileSong(ref="track:abc-123")
    ProfileSong(ref="https://example.com/a.mp3")
    with pytest.raises(CustomizeError):
        ProfileSong(ref="javascript:alert(1)")
    with pytest.raises(CustomizeError):
        ProfileSong(ref="")


# -- custom blocks: structured data, never markup --------------------------


def test_custom_block_kinds():
    CustomBlock(kind="text", text="hello world").validate()
    CustomBlock(kind="link", text="my site", url="https://example.com").validate()
    CustomBlock(kind="image", url="https://example.com/pic.png").validate()
    CustomBlock(kind="divider").validate()


def test_custom_block_refuses_markup_and_bad_urls():
    with pytest.raises(CustomizeError, match="markup refused"):
        CustomBlock(kind="text", text="<marquee>hi</marquee>").validate()
    with pytest.raises(CustomizeError):
        CustomBlock(kind="link", text="x", url="ftp://example.com/x").validate()
    with pytest.raises(CustomizeError, match="needs a url"):
        CustomBlock(kind="image").validate()


# -- full round-trip -------------------------------------------------------


def _full_profile():
    pc = ProfileCustomization(profile_id="keeper1")
    pc.theme.set(ThemeToken(name="color.text", value="#e8e4da", kind="color"))
    pc.theme.set(ThemeToken(name="bg.page", value="#0d0b08", kind="background"))
    pc.theme.set(ThemeToken(name="font.body", value="Georgia", kind="font"))
    pc.theme.set(ThemeToken(name="radius.panel", value="12px", kind="length"))
    pc.layout.reorder(["song", "bio", "mood", "friends", "posts", "guestbook"])
    pc.blocks.append(CustomBlock(kind="heading", text="Welcome to my void"))
    pc.blocks.append(
        CustomBlock(kind="link", text="my forge", url="https://example.com/forge")
    )
    pc.song = ProfileSong(ref="track:anthem-1", title="Anthem", artist="The Legion")
    pc.animations.append(
        Animation(name="fade-in", target="entrance", duration_ms=600,
                  properties=("opacity", "transform"))
    )
    pc.widgets.append(Widget(name="song_player", params={"compact": True}))
    pc.widgets.append(Widget(name="guestbook", params={"moderated": True, "max_entries": 200}))
    pc.apply_guardrails()
    return pc


def test_full_round_trip():
    pc = _full_profile()
    data = pc.to_dict()
    assert data["format"] == "levi-social-customize"
    assert "checksum" in data
    back = ProfileCustomization.from_dict(data)
    assert back.render() == pc.render()
    assert back.layout.order()[0] == "song"
    assert back.song.title == "Anthem"
    assert back.song.autoplay is False


def test_tampered_bundle_refused():
    pc = _full_profile()
    data = pc.to_dict()
    data["theme"]["color.text"]["value"] = "#ffffff"
    with pytest.raises(CustomizeError, match="tampered"):
        ProfileCustomization.from_dict(data)


def test_bad_profile_id_refused():
    with pytest.raises(CustomizeError):
        ProfileCustomization(profile_id="not a valid id!!!")


def test_duplicate_animations_refused():
    pc = ProfileCustomization(profile_id="keeper1")
    pc.animations.append(Animation(name="fade", target="text", duration_ms=300))
    pc.animations.append(Animation(name="fade", target="text", duration_ms=300))
    with pytest.raises(CustomizeError, match="duplicate animation"):
        pc.__post_init__()
