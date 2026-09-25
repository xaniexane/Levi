"""Optional local Stable Diffusion backend — hardware-gated scaffold.

This module is a thin, fail-closed wrapper around ``diffusers`` + ``torch``.
It is NOT installed with LEVI (stdlib-only core) and is NOT the default
path. When the libraries are absent, every entry point fails closed with a
clear message saying what to install.

Honest requirements: a CUDA GPU and several GB of model weights. Not
viable on CPU-only machines or phones — the procedural generator
(:mod:`levi.media.local`) is the zero-dependency core, and Pollinations
(:mod:`levi.media.pollinations`) is the free keyless reference for
photoreal quality without hardware.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_DIR = Path.home() / ".levi" / "media" / "sd"

DEFAULT_MODEL_ID = "stabilityai/stable-diffusion-2-1"

_INSTALL_HINT = (
    "local Stable Diffusion is unavailable: install 'diffusers', 'torch' "
    "and 'Pillow' first (pip install diffusers torch Pillow), download "
    "weights for a model such as %r, and use a machine with a CUDA GPU. "
    "On CPU-only or mobile hardware this backend is not viable — use "
    "'--backend local' (offline procedural) or '--backend pollinations' "
    "(free keyless reference) instead."
) % DEFAULT_MODEL_ID


def available() -> bool:
    """True only when diffusers AND torch are importable."""
    return (
        importlib.util.find_spec("diffusers") is not None
        and importlib.util.find_spec("torch") is not None
    )


def _require_available() -> None:
    if not available():
        raise RuntimeError(_INSTALL_HINT)


@dataclass
class SDImage:
    prompt: str
    path: Optional[str]
    seed: Optional[int]
    model_id: str
    width: int
    height: int

    def format(self) -> str:
        lines = [
            "=== LEVI local Stable Diffusion image ===",
            f"prompt: {self.prompt[:120]}",
            f"model: {self.model_id}  seed: {self.seed}  size: {self.width}x{self.height}",
        ]
        if self.path:
            lines.append(f"saved: {self.path}")
        return "\n".join(lines)


def generate(
    prompt: str,
    width: int = 512,
    height: int = 512,
    seed: Optional[int] = None,
    model_id: str = DEFAULT_MODEL_ID,
    steps: int = 30,
    save: bool = True,
    save_dir: Optional[Path] = None,
) -> SDImage:
    """Run local text-to-image via diffusers. Fails closed without deps/GPU."""
    _require_available()
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    prompt = prompt.strip()[:2000]
    if steps < 1 or steps > 150:
        raise ValueError("steps must be in 1..150")

    import torch
    from diffusers import StableDiffusionPipeline

    device = "cuda" if torch.cuda.is_available() else "cpu"
    pipe = StableDiffusionPipeline.from_pretrained(model_id)
    pipe = pipe.to(device)
    generator = (
        torch.Generator(device=device).manual_seed(seed) if seed is not None else None
    )
    image = pipe(
        prompt,
        height=height,
        width=width,
        num_inference_steps=steps,
        generator=generator,
    ).images[0]

    path: Optional[str] = None
    if save:
        dest_dir = Path(save_dir) if save_dir else DEFAULT_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        tag = seed if seed is not None else "rand"
        dest = dest_dir / f"sd_{tag}.png"
        image.save(str(dest))
        path = str(dest)
    img = SDImage(
        prompt=prompt,
        path=path,
        seed=seed,
        model_id=model_id,
        width=width,
        height=height,
    )
    if device == "cpu":
        # Honest caveat, surfaced in format() output: CPU renders are slow.
        img.model_id = (
            model_id + " (CPU render — slow; a CUDA GPU is strongly recommended)"
        )
    return img
