"""Scaffold registry: stdlib-only project templates."""

from __future__ import annotations

from typing import Callable, Dict

from .spec import BuildSpec
from . import static as _static
from . import fullstack as _fullstack

Renderer = Callable[[BuildSpec], Dict[str, str]]

SCAFFOLDS: Dict[str, Renderer] = {
    "static": _static.render_static,
    "fullstack": _fullstack.render_fullstack,
}


def list_scaffolds() -> list:
    return sorted(SCAFFOLDS)


def render_scaffold(stack: str, spec: BuildSpec) -> Dict[str, str]:
    """Render the scaffold skeleton for ``stack`` as {relpath: content}."""
    try:
        renderer = SCAFFOLDS[stack]
    except KeyError:
        raise ValueError(
            f"unknown stack {stack!r}; choices: {', '.join(list_scaffolds())}"
        ) from None
    return renderer(spec)


__all__ = ["SCAFFOLDS", "list_scaffolds", "render_scaffold", "BuildSpec"]
