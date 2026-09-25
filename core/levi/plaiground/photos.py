"""Plaiground photo hooks — capability CONTRACT, not an image pipeline.

This module declares the interface a future image backend would satisfy
(:class:`PhotoBackend`) and wires the one backend that already exists
in-repo: :mod:`levi.media.local`, the offline, deterministic,
zero-dependency procedural PNG generator. It produces generative art
from a prompt seed — gradients, glow, geometry, grain — and is honest
about scope: procedural art, not photorealistic synthesis.

Deliberately NOT built here:
  * No photorealistic generation (no weights, no cloud image APIs).
  * No external image backend is wired for Plaiground — the
    :mod:`levi.media.pollinations` reference backend that exists in
    :mod:`levi.media` is NOT registered here, on purpose: the adult
    surface stays fully offline and local-first.

A future backend registers by calling :func:`register_backend` with an
object implementing :class:`PhotoBackend`; :func:`request_photo` picks
the registered backend (default: ``"procedural"``) and enforces the
gate before anything runs. Registering a backend does not bypass the
gate — the gate lives in :func:`request_photo`, outside the backends.

No image bytes are generated at import time. Everything is lazy.
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Protocol

from levi.media.local import generate as _local_generate
from levi.plaiground.gate import require_adult

_MAX_PROMPT_LEN = 2000
_ALLOWED_CHARS = set(string.printable) - set("\x0b\x0c")

PROCEDURAL_BACKEND_NAME = "procedural"


@dataclass(frozen=True)
class PhotoResult:
    """What a photo request returns — metadata, never raw bytes."""

    prompt: str
    style: str
    seed: int
    width: int
    height: int
    path: Optional[str]
    backend: str
    note: str


class PhotoBackend(Protocol):
    """Capability contract for a Plaiground image backend.

    A future backend implements this interface and registers itself via
    :func:`register_backend`. The backend receives a validated prompt and
    returns a :class:`PhotoResult`; it must not perform network I/O
    unless it is explicitly documented as an online backend, and even
    then the gate in :func:`request_photo` still applies.
    """

    name: str

    def generate(
        self,
        prompt: str,
        style: str,
        seed: Optional[int],
        width: int,
        height: int,
        save_dir: Optional[Path],
    ) -> PhotoResult: ...


class ProceduralPhotoBackend:
    """The wired default: offline procedural art via :mod:`levi.media.local`.

    Deterministic, zero-dependency, no network. Honest scope: abstract
    generative compositions, not likenesses of people and not
    photorealistic output.
    """

    name = PROCEDURAL_BACKEND_NAME

    def generate(
        self,
        prompt: str,
        style: str = "abstract",
        seed: Optional[int] = None,
        width: int = 512,
        height: int = 512,
        save_dir: Optional[Path] = None,
    ) -> PhotoResult:
        image = _local_generate(
            prompt,
            width=width,
            height=height,
            seed=seed,
            style=style,
            save=save_dir is not None,
            save_dir=save_dir,
        )
        return PhotoResult(
            prompt=image.prompt,
            style=image.style,
            seed=image.seed,
            width=image.width,
            height=image.height,
            path=image.path,
            backend=self.name,
            note=(
                "procedural art — deterministic composition from a prompt "
                "seed, not photorealistic synthesis"
            ),
        )


_BACKENDS: Dict[str, PhotoBackend] = {
    PROCEDURAL_BACKEND_NAME: ProceduralPhotoBackend(),
}


def register_backend(backend: PhotoBackend, home: Optional[Path] = None) -> None:
    """Register a future image backend by contract.

    Gate-checked: only with the gate open can the backend surface change.
    Registration never weakens the gate — :func:`request_photo` checks it
    on every call regardless of which backend is selected.
    """
    require_adult(home)
    if not hasattr(backend, "name") or not callable(getattr(backend, "generate", None)):
        raise ValueError("backend must implement the PhotoBackend contract")
    name = str(backend.name).strip()
    if not name:
        raise ValueError("backend name must not be empty")
    _BACKENDS[name] = backend


def available_backends(home: Optional[Path] = None) -> list:
    """Names of registered backends. Gate-checked first."""
    require_adult(home)
    return sorted(_BACKENDS)


def _validate_prompt(prompt: str) -> str:
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string, got %s" % type(prompt).__name__)
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("prompt must not be empty")
    if len(prompt) > _MAX_PROMPT_LEN:
        raise ValueError("prompt must be at most %d characters" % _MAX_PROMPT_LEN)
    if any(ch not in _ALLOWED_CHARS for ch in prompt):
        raise ValueError("prompt contains disallowed characters")
    return prompt


def request_photo(
    prompt: str,
    backend: str = PROCEDURAL_BACKEND_NAME,
    style: str = "abstract",
    seed: Optional[int] = None,
    width: int = 512,
    height: int = 512,
    save_dir: Optional[Path] = None,
    home: Optional[Path] = None,
) -> PhotoResult:
    """Request an image through the registered backend. Gate-checked first.

    With the gate off, raises :class:`levi.plaiground.gate.GateLockedError`
    before any backend is touched. Unknown backends raise KeyError.
    """
    require_adult(home)
    prompt = _validate_prompt(prompt)
    if backend not in _BACKENDS:
        raise KeyError(
            "unknown photo backend %r; available: %s"
            % (backend, ", ".join(sorted(_BACKENDS)))
        )
    return _BACKENDS[backend].generate(
        prompt,
        style=style,
        seed=seed,
        width=width,
        height=height,
        save_dir=save_dir,
    )
