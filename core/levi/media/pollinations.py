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
import hashlib


DEFAULT_DIR = Path.home() / ".levi" / "media"


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
    enc = quote(prompt.strip() or "abstract form")
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
    if seed is None:
        seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16) % (2**31)
    url = image_url(prompt, width=width, height=height, model=model, seed=seed)
    path = None
    if save:
        DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
        fname = f"img_{seed}_{model}.jpg"
        dest = DEFAULT_DIR / fname
        req = Request(url, headers={"User-Agent": "LEVI-LWP/1.0"})
        key = _api_key()
        if key:
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


def story_still(story_title: str, genre: str, beat: str = "midpoint") -> PollinationsImage:
    prompt = (
        f"Cinematic still, {genre.replace('_', ' ')} mood, "
        f"scene for story '{story_title}', beat {beat}, "
        f"no text overlay, dramatic lighting"
    )
    return generate(prompt)
