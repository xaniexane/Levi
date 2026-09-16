"""Media generation for LEVI.

Three backends, one dispatcher:

* ``local`` (default) — :mod:`levi.media.local`: offline procedural art,
  zero dependencies, deterministic. Always available.
* ``pollinations`` — :mod:`levi.media.pollinations`: free keyless image
  reference for photoreal quality. Labeled external reference, never LEVI.
* ``sd`` — :mod:`levi.media.sd`: optional local Stable Diffusion scaffold.
  Needs diffusers+torch, weights, and a CUDA GPU; fails closed otherwise.

``generate_image(..., backend="auto")`` picks local — the local-first rule.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from levi.media.pollinations import PollinationsImage, image_url
from levi.media.local import LocalImage

__all__ = ["PollinationsImage", "LocalImage", "image_url", "generate_image", "BACKENDS"]

BACKENDS = ("auto", "local", "pollinations", "sd")


def generate_image(
    prompt: str,
    backend: str = "auto",
    width: Optional[int] = None,
    height: Optional[int] = None,
    seed: Optional[int] = None,
    style: str = "none",
    save: bool = True,
    save_dir: Optional[Path] = None,
    **kwargs: Any,
):
    """Generate an image via the chosen backend.

    backend="auto" (default) resolves to "local" — offline-first. Pass
    backend="pollinations" for the free keyless photoreal reference, or
    backend="sd" for local Stable Diffusion (fails closed without deps).
    Extra kwargs pass through to the backend's generate().
    """
    if backend not in BACKENDS:
        raise ValueError(f"backend must be one of {BACKENDS}, got {backend!r}")
    resolved = "local" if backend == "auto" else backend

    def _pick(allowed: set[str]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if width is not None:
            out["width"] = width
        if height is not None:
            out["height"] = height
        if seed is not None:
            out["seed"] = seed
        out["save"] = save
        if save_dir is not None:
            out["save_dir"] = save_dir
        for k, v in kwargs.items():
            if k in allowed:
                out[k] = v
        return out

    if resolved == "local":
        from levi.media import local as _local

        kw = _pick({"style"})
        kw.setdefault("width", 512)
        kw.setdefault("height", 512)
        kw.setdefault("style", style if style in _local.STYLES else "abstract")
        return _local.generate(prompt, **kw)
    if resolved == "pollinations":
        from levi.media import pollinations as _pol

        kw = _pick(
            {
                "model",
                "enhance",
                "quality",
                "negative_prompt",
                "safe",
                "private",
                "timeout",
                "style",
            }
        )
        kw.setdefault("width", 1024)
        kw.setdefault("height", 1024)
        kw.setdefault("style", style)
        return _pol.generate(prompt, **kw)
    # resolved == "sd"
    from levi.media import sd as _sd

    kw = _pick({"model_id", "steps"})
    kw.setdefault("width", 512)
    kw.setdefault("height", 512)
    return _sd.generate(prompt, **kw)
