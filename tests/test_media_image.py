"""Tests for levi.media: local procedural backend, Pollinations quality tier,
SD fail-closed scaffold, and the generate_image dispatcher.

No network is ever touched: Pollinations tests only build URLs, and any
download attempt is monkeypatched to fail loudly if it slips through.
HOME is redirected to tmp_path.
"""

import pytest

from pathlib import Path

from levi.media import generate_image
from levi.media import local as local_mod
from levi.media import pollinations as pol
from levi.media import sd as sd_mod


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    # re-point module-level default dirs that were computed at import
    monkeypatch.setattr(local_mod, "DEFAULT_DIR", tmp_path / "media" / "local")
    monkeypatch.setattr(sd_mod, "DEFAULT_DIR", tmp_path / "media" / "sd")
    monkeypatch.setattr(pol, "DEFAULT_DIR", tmp_path / "media")
    return tmp_path


# -- local procedural backend -------------------------------------------------


def test_local_deterministic_same_seed(tmp_path):
    a = local_mod.generate(
        "a lighthouse", width=64, height=48, seed=7, save_dir=tmp_path / "a"
    )
    b = local_mod.generate(
        "a lighthouse", width=64, height=48, seed=7, save_dir=tmp_path / "b"
    )
    assert Path(a.path).read_bytes() == Path(b.path).read_bytes()


def test_local_prompt_seeded_differs(tmp_path):
    a = local_mod.generate("a lighthouse", width=64, height=48, save_dir=tmp_path / "a")
    b = local_mod.generate("a windmill", width=64, height=48, save_dir=tmp_path / "b")
    assert Path(a.path).read_bytes() != Path(b.path).read_bytes()


def test_local_png_valid(tmp_path):
    img = local_mod.generate("test", width=32, height=24, save_dir=tmp_path)
    data = Path(img.path).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert img.width == 32 and img.height == 24


def test_local_encode_png_roundtrip():
    raw = bytes([10, 20, 30] * 4 * 3)
    data = local_mod.encode_png(4, 3, raw)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82")


def test_local_bad_dimensions():
    with pytest.raises(ValueError):
        local_mod.generate("x", width=0, height=10, save=False)
    with pytest.raises(ValueError):
        local_mod.generate("x", width=10, height=5000, save=False)


def test_local_bad_style():
    with pytest.raises(ValueError):
        local_mod.generate("x", style="watercolor", save=False)


def test_local_all_styles_render(tmp_path):
    for style in local_mod.STYLES:
        img = local_mod.generate(
            "style check", width=24, height=16, style=style, save_dir=tmp_path / style
        )
        assert Path(img.path).is_file()


# -- pollinations quality tier -------------------------------------------------


def test_pollinations_url_quality_tier():
    url = pol.image_url(
        "a cat", width=512, height=512, seed=1, negative_prompt="blurry"
    )
    assert "enhance=true" in url
    assert "quality=high" in url
    assert "nologo=true" in url
    assert "seed=1" in url
    assert "negative_prompt=blurry" in url


def test_pollinations_style_preset_applied():
    url = pol.image_url(pol.apply_style("a cat", "photo"), seed=1)
    assert (
        "professional+photograph" in url
        or "professional%20photograph" in url
        or "professional photograph" in url.replace("+", " ").replace("%20", " ")
    )


def test_pollinations_style_invalid():
    with pytest.raises(ValueError):
        pol.apply_style("a cat", "watercolor")


def test_pollinations_quality_invalid():
    with pytest.raises(ValueError):
        pol.image_url("a cat", quality="ultra")


def test_pollinations_known_models_documented():
    assert "flux" in pol.KNOWN_MODELS


def test_pollinations_generate_uses_style_and_seed(tmp_path, monkeypatch):
    # never hit the network: save=False still must not open a socket
    import urllib.request

    def _boom(*a, **k):
        raise AssertionError("network touched in test")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    img = pol.generate(
        "a lighthouse", style="cinematic", seed=99, save=False, width=256, height=256
    )
    assert img.seed == 99
    assert "cinematic still" in img.prompt
    assert "enhance=true" in img.url


# -- sd scaffold -----------------------------------------------------------------


def test_sd_fails_closed_without_deps(tmp_path, monkeypatch):
    monkeypatch.setattr(sd_mod, "available", lambda: False)
    with pytest.raises(RuntimeError) as ei:
        sd_mod.generate("a cat", save_dir=tmp_path)
    assert "diffusers" in str(ei.value)


def test_sd_available_is_bool():
    assert isinstance(sd_mod.available(), bool)


# -- dispatcher ------------------------------------------------------------------


def test_dispatcher_auto_is_local(tmp_path):
    img = generate_image(
        "hello", backend="auto", width=32, height=24, save_dir=tmp_path
    )
    assert isinstance(img, local_mod.LocalImage)


def test_dispatcher_invalid_backend():
    with pytest.raises(ValueError):
        generate_image("hello", backend="dalle", save=False)


def test_dispatcher_kwarg_filtering(tmp_path):
    # backend-specific kwargs must not leak into the local backend
    img = generate_image(
        "hello",
        backend="auto",
        width=32,
        height=24,
        model="flux",
        quality="hd",
        save_dir=tmp_path,
    )
    assert isinstance(img, local_mod.LocalImage)
