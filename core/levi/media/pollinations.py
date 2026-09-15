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
) -> str:
    """Build the Pollinations image URL. Validates dimensions/prompt/model."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    width, height = _validate_dimensions(width, height)
    model = _validate_model(model)
    if seed is not None and (
        isinstance(seed, bool) or not isinstance(seed, int) or seed < 0
    ):
        raise ValueError("seed must be a non-negative integer or None")
    enc = quote(prompt.strip()[:_MAX_PROMPT_LEN] or "abstract form")
    q = f"width={width}&height={height}&model={quote(model)}"
    if seed is not None:
        q += f"&seed={int(seed)}"
    if nologo:
        q += "&nologo=true"
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
    model: str = "flux",
    seed: Optional[int] = None,
    save: bool = True,
    timeout: int = 90,
) -> PollinationsImage:
    """Generate an image via Pollinations. Network failure returns the URL
    with a download-failure note — never a traceback, never a leaked key."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    model = _validate_model(model)
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or timeout <= 0
    ):
        raise ValueError("timeout must be a positive number of seconds")
    if seed is None:
        seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16) % (2**31)
    url = image_url(prompt, width=width, height=height, model=model, seed=seed)
    path = None
    if save:
        DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
        # model is user-controlled — never let it become a path.
        fname = f"img_{seed}_{_safe_model_filename(model)}.jpg"
        dest = DEFAULT_DIR / fname
        req = Request(url, headers={"User-Agent": "LEVI-LWP/1.0"})
        key = _api_key()
        if key:
            # The key goes to Pollinations only, in the header — it is never
            # logged, printed, or included in any error text below.
            req.add_header("Authorization", f"Bearer {key}")
        try:
            with urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            dest.write_bytes(data)
            path = str(dest)
        except Exception as e:
            # still return URL for browser use
            path = f"(download failed: {e})"
    return PollinationsImage(prompt=prompt, url=url, path=path, seed=seed, model=model)


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
