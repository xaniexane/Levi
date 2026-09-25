"""
Pollinations image generation for LEVI × L.W.P. story / content.

Uses public image URL pattern (legacy prompt endpoint). Optional API key via
POLLINATIONS_API_KEY or ~/.levi/pollinations.key for higher limits.

  GET https://image.pollinations.ai/prompt/{prompt}?width=&height=&model=&seed=

Does not claim ownership of Pollinations; thin client only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote
from urllib.request import Request, urlopen
import os
import re
import hashlib


DEFAULT_DIR = Path.home() / ".levi" / "media"

_MAX_DIMENSION = 2048
_MAX_PROMPT_LEN = 2000
_MODEL_FILE_RE = re.compile(r"[^A-Za-z0-9_.-]+")

# Models verified against Pollinations docs (enter.pollinations.ai/AGENTS.md,
# mirrored 2026-09-16): flux is the documented default. The API accepts other
# model names as they rotate, so validation sanitizes rather than hard-fails
# on unknown names — but these are the known-good quality tiers.
KNOWN_MODELS = ("flux", "gptimage", "turbo", "kontext", "seedream")

# Quality-first attempt order when generate() is called without an explicit
# model: try the newest/highest-fidelity models first, fall back to flux.
MODEL_FALLBACK_ORDER = ("seedream", "gptimage", "flux")

# Model fallback chain for model="auto" (the generate() default): newest /
# highest-quality first, flux last as the reliable fallback. An explicit
# model name bypasses the chain and is attempted exactly once.
FALLBACK_MODELS = ("seedream", "gptimage", "flux")

# Style presets: proven quality boosters appended to the prompt. These are
# prompt-engineering additions, not model switches.
STYLE_PRESETS = {
    "photo": "professional photograph, 85mm lens, sharp focus, natural lighting, ultra detailed, 8k",
    "anime": "anime key visual, vibrant cel shading, clean linework, studio quality, highly detailed",
    "painting": "oil painting, rich visible brushwork, gallery masterpiece, dramatic chiaroscuro lighting",
    "product": "commercial product photography, studio lighting, clean minimal background, ultra sharp, 8k",
    "cinematic": "cinematic still, dramatic lighting, film grain, shallow depth of field, no text overlay",
}

DEFAULT_NEGATIVE_PROMPT = (
    "worst quality, blurry, watermark, text, logo, deformed, "
    "duplicate, malformed, extra limbs, bad anatomy, lowres"
)


def apply_style(prompt: str, style: str) -> str:
    """Append a style preset's quality boosters to a prompt."""
    if style in (None, "", "none", "abstract"):
        return prompt
    if style not in STYLE_PRESETS:
        raise ValueError(
            f"style must be one of {sorted(STYLE_PRESETS)}|none, got {style!r}"
        )
    return f"{prompt}, {STYLE_PRESETS[style]}"


def _validate_dimensions(width: int, height: int) -> tuple[int, int]:
    for label, value in (("width", width), ("height", height)):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 1 <= value <= _MAX_DIMENSION
        ):
            raise ValueError(
                "%s must be an integer 1-%d, got %r" % (label, _MAX_DIMENSION, value)
            )
    return width, height


def _validate_model(model: str) -> str:
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be a non-empty string")
    return model.strip()[:64]


def _safe_model_filename(model: str) -> str:
    """Model name scrubbed for use inside a filename (no path separators)."""
    return _MODEL_FILE_RE.sub("_", model).strip("._") or "model"


@dataclass
class PollinationsImage:
    prompt: str
    url: str
    path: Optional[str] = None
    seed: Optional[int] = None
    model: str = "flux"

    def format(self) -> str:
        lines = [
            "=== LEVI × L.W.P. Pollinations image ===",
            f"prompt: {self.prompt[:120]}",
            f"model: {self.model}  seed: {self.seed}",
            f"url: {self.url}",
        ]
        if self.path:
            lines.append(f"saved: {self.path}")
        return "\n".join(lines)


def image_url(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    model: str = "flux",
    seed: Optional[int] = None,
    nologo: bool = True,
    enhance: bool = True,
    quality: str = "hd",
    negative_prompt: Optional[str] = None,
    safe: bool = False,
    private: bool = False,
) -> str:
    """Build the Pollinations image URL. Validates dimensions/prompt/model.

    Quality tier (verified against Pollinations API docs): enhance=True lets
    Pollinations AI-enhance the prompt; quality in low|medium|high|hd,
    defaulting to hd.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    width, height = _validate_dimensions(width, height)
    model = _validate_model(model)
    if seed is not None and (
        isinstance(seed, bool) or not isinstance(seed, int) or seed < 0
    ):
        raise ValueError("seed must be a non-negative integer or None")
    if quality not in ("low", "medium", "high", "hd"):
        raise ValueError("quality must be one of low|medium|high|hd")
    enc = quote(prompt.strip()[:_MAX_PROMPT_LEN] or "abstract form")
    q = f"width={width}&height={height}&model={quote(model)}"
    if seed is not None:
        q += f"&seed={int(seed)}"
    if nologo:
        q += "&nologo=true"
    if enhance:
        q += "&enhance=true"
    q += f"&quality={quality}"
    if negative_prompt:
        q += f"&negative_prompt={quote(str(negative_prompt)[:500])}"
    if safe:
        q += "&safe=true"
    if private:
        q += "&private=true"
    return f"https://image.pollinations.ai/prompt/{enc}?{q}"


def _api_key() -> Optional[str]:
    k = os.environ.get("POLLINATIONS_API_KEY", "").strip()
    if k:
        return k
    p = Path.home() / ".levi" / "pollinations.key"
    if p.exists():
        return p.read_text(encoding="utf-8").strip() or None
    return None


def generate(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    model: str = "auto",
    seed: Optional[int] = None,
    save: bool = True,
    timeout: int = 90,
    style: str = "none",
    enhance: bool = True,
    quality: str = "hd",
    negative_prompt: Optional[str] = None,
    safe: bool = False,
    private: bool = False,
) -> PollinationsImage:
    """Generate an image via Pollinations. Network failure returns the URL
    with a download-failure note — never a traceback, never a leaked key.

    Quality tier: enhance=True (AI prompt enhancement), quality="hd", and
    style presets (photo|anime|painting|product|cinematic) squeeze the free
    tier. model="auto" (default) tries FALLBACK_MODELS in order
    (seedream -> gptimage -> flux), stopping at the first successful
    download; an explicit model name is attempted exactly once, with no
    fallback. Pollinations is a labeled external reference, never LEVI
    itself.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    model = _validate_model(model)
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or timeout <= 0
    ):
        raise ValueError("timeout must be a positive number of seconds")
    styled = apply_style(prompt.strip(), style)
    if negative_prompt is None:
        negative_prompt = DEFAULT_NEGATIVE_PROMPT
    if seed is None:
        seed = int(hashlib.sha256(styled.encode()).hexdigest()[:8], 16) % (2**31)
    attempt_models = FALLBACK_MODELS if model == "auto" else (model,)

    def _attempt(m: str) -> tuple[str, Optional[str], Optional[Exception]]:
        """Build the URL for model m and try the download. Returns
        (url, saved_path_or_None, error_or_None)."""
        u = image_url(
            styled,
            width=width,
            height=height,
            model=m,
            seed=seed,
            enhance=enhance,
            quality=quality,
            negative_prompt=negative_prompt,
            safe=safe,
            private=private,
        )
        if not save:
            return u, None, None
        DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
        # model is user-controlled — never let it become a path.
        fname = f"img_{seed}_{_safe_model_filename(m)}.jpg"
        dest = DEFAULT_DIR / fname
        req = Request(u, headers={"User-Agent": "LEVI-LWP/1.0"})
        key = _api_key()
        if key:
            # The key goes to Pollinations only, in the header — it is never
            # logged, printed, or included in any error text below.
            req.add_header("Authorization", f"Bearer {key}")
        try:
            with urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            dest.write_bytes(data)
            return u, str(dest), None
        except Exception as e:
            return u, None, e

    url: Optional[str] = None
    path: Optional[str] = None
    used_model = attempt_models[0]
    last_error: Optional[Exception] = None
    for m in attempt_models:
        url, path, last_error = _attempt(m)
        used_model = m
        if last_error is None:
            break
    if save and last_error is not None:
        # every model in the chain failed: still return the last URL for
        # browser use, with the failure noted and the key never exposed.
        path = f"(download failed: {last_error})"
    return PollinationsImage(
        prompt=styled, url=url or "", path=path, seed=seed, model=used_model
    )


def story_still(
    story_title: str, genre: str, beat: str = "midpoint"
) -> PollinationsImage:
    """Generate a cinematic still for a story beat."""
    if not isinstance(story_title, str) or not story_title.strip():
        raise ValueError("story_title must be a non-empty string")
    if not isinstance(genre, str) or not genre.strip():
        raise ValueError("genre must be a non-empty string")
    if not isinstance(beat, str) or not beat.strip():
        raise ValueError("beat must be a non-empty string")
    prompt = (
        f"Cinematic still, {genre.replace('_', ' ')} mood, "
        f"scene for story '{story_title}', beat {beat}, "
        f"no text overlay, dramatic lighting"
    )
    return generate(prompt)
