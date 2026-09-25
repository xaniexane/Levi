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
    assert "quality=hd" in url
    assert "nologo=true" in url
    assert "seed=1" in url
    assert "negative_prompt=blurry" in url


def test_pollinations_url_quality_explicit():
    url = pol.image_url("a cat", quality="high")
    assert "quality=high" in url
    assert "quality=hd" not in url


def test_pollinations_generate_hd_default(monkeypatch):
    # save=False must not open a socket; hd must be in the built URL
    def _boom(*a, **k):
        raise AssertionError("network touched in test")

    monkeypatch.setattr(pol, "urlopen", _boom)
    img = pol.generate("a lighthouse", save=False, width=256, height=256)
    assert "quality=hd" in img.url
    # auto chain with save=False builds the first model's URL, no fallback
    assert img.model == "seedream"
    assert "model=seedream" in img.url


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


def test_pollinations_fallback_chain_order(tmp_path, monkeypatch):
    # seedream and gptimage "outage" -> falls through to flux, in order
    attempted = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"fakejpegbytes"

    def _fake_urlopen(req, timeout=None):
        attempted.append(req.full_url)
        if "model=seedream" in req.full_url or "model=gptimage" in req.full_url:
            raise OSError("simulated model outage")
        return _Resp()

    monkeypatch.setattr(pol, "urlopen", _fake_urlopen)
    img = pol.generate("a lighthouse", save=True, width=64, height=64)
    models_tried = [u.split("model=")[1].split("&")[0] for u in attempted]
    assert models_tried == ["seedream", "gptimage", "flux"]
    assert img.model == "flux"
    assert "model=flux" in img.url
    assert Path(img.path).is_file()
    assert Path(img.path).read_bytes() == b"fakejpegbytes"


def test_pollinations_fallback_first_success_short_circuits(tmp_path, monkeypatch):
    attempted = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"fakejpegbytes"

    def _fake_urlopen(req, timeout=None):
        attempted.append(req.full_url)
        return _Resp()

    monkeypatch.setattr(pol, "urlopen", _fake_urlopen)
    img = pol.generate("a lighthouse", save=True, width=64, height=64)
    assert len(attempted) == 1
    assert "model=seedream" in attempted[0]
    assert img.model == "seedream"


def test_pollinations_explicit_model_no_fallback(tmp_path, monkeypatch):
    # an explicit model is attempted exactly once, even on failure
    attempted = []

    def _fake_urlopen(req, timeout=None):
        attempted.append(req.full_url)
        raise OSError("simulated outage")

    monkeypatch.setattr(pol, "urlopen", _fake_urlopen)
    img = pol.generate("a lighthouse", model="turbo", save=True, width=64, height=64)
    assert len(attempted) == 1
    assert "model=turbo" in attempted[0]
    assert img.model == "turbo"
    assert img.path.startswith("(download failed:")
    assert "model=turbo" in img.url  # URL still returned for browser use


def test_pollinations_fallback_all_fail_returns_last_url(monkeypatch):
    def _fake_urlopen(req, timeout=None):
        raise OSError("total outage")

    monkeypatch.setattr(pol, "urlopen", _fake_urlopen)
    img = pol.generate("a lighthouse", save=True, width=64, height=64)
    assert img.model == "flux"
    assert "model=flux" in img.url
    assert img.path.startswith("(download failed:")


def test_pollinations_negative_prompt_strengthened():
    neg = pol.DEFAULT_NEGATIVE_PROMPT
    for term in (
        "duplicate",
        "malformed",
        "extra limbs",
        "bad anatomy",
        "lowres",
        "watermark",
        "deformed",
    ):
        assert term in neg
    assert neg.isascii()  # plain-ASCII rule from the teacher brief


def test_pollinations_no_key_leak_on_failure(monkeypatch):
    secret = "sk-test-secret-9f8e7d6c5b4a"
    monkeypatch.setenv("POLLINATIONS_API_KEY", secret)

    def _fake_urlopen(req, timeout=None):
        # the header must carry the key (it goes to Pollinations only)...
        assert req.get_header("Authorization") == f"Bearer {secret}"
        raise OSError("simulated outage")

    monkeypatch.setattr(pol, "urlopen", _fake_urlopen)
    img = pol.generate("a lighthouse", save=True, width=64, height=64)
    for surface in (img.path, img.url, img.prompt, img.format()):
        assert secret not in surface
    assert img.path.startswith("(download failed:")


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


def test_dispatcher_pollinations_defaults_photo_style(monkeypatch):
    # the dispatcher gives the pollinations backend the photo quality
    # boosters by default; save=False so no socket is opened
    def _boom(*a, **k):
        raise AssertionError("network touched in test")

    monkeypatch.setattr(pol, "urlopen", _boom)
    img = generate_image("a lighthouse", backend="pollinations", save=False)
    assert "professional photograph" in img.prompt
    assert "quality=hd" in img.url


def test_dispatcher_pollinations_explicit_style_passthrough(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("network touched in test")

    monkeypatch.setattr(pol, "urlopen", _boom)
    img = generate_image(
        "a lighthouse", backend="pollinations", style="cinematic", save=False
    )
    assert "cinematic still" in img.prompt
    assert "professional photograph" not in img.prompt


def test_dispatcher_auto_unaffected_by_photo_default(tmp_path):
    # local backend keeps its own style handling (no photo boosters)
    img = generate_image(
        "hello", backend="auto", width=32, height=24, save_dir=tmp_path
    )
    assert isinstance(img, local_mod.LocalImage)
