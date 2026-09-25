"""LEVI self-capability introspection — what the organism can do, from itself.

A read-only, credentialless, local self-knowledge surface. This is
deliberately NOT a :class:`levi.plugins.registry.Connector`: there is no
third-party account here, so the honest connector contract (credential env
var, wired transports, no simulated success) does not apply. Nothing is
sent anywhere; everything is read from the static interop manifest via
:mod:`levi.interop.registry`.

Answers: which modules exist, what each provides/requires, which module
provides a given capability, and full-text search across capability names.

Interop (wired when the manifest is free — see queue note below):

.. code-block:: python

    "plugins-selfcaps": {
        "provides": ["plugins.selfcaps"],
        "requires": [],
    }

Until then, :func:`register_capabilities` registers this module against
any :class:`levi.interop.registry.Registry`.
"""

from __future__ import annotations

from typing import Dict, List, Optional


class SelfcapsError(ValueError):
    """Unknown module or capability."""


#: Capability wiring (see module docstring).
MODULE_NAME = "plugins-selfcaps"
PROVIDES = ["plugins.selfcaps"]
REQUIRES: List[str] = []


_DEFAULT_REG = None


def _default_registry():
    """Registry preloaded from the static manifest (single source of truth)."""
    global _DEFAULT_REG
    if _DEFAULT_REG is None:
        from levi.interop.manifest import DECLARATIONS
        from levi.interop.registry import Registry

        reg = Registry()
        for name, decl in DECLARATIONS.items():
            reg.register(
                name,
                provides=list(decl["provides"]),
                requires=list(decl["requires"]),
            )
        _DEFAULT_REG = reg
    return _DEFAULT_REG


def _reg(registry=None):
    if registry is not None:
        return registry
    return _default_registry()


def all_modules(registry=None) -> List[str]:
    """Sorted names of every registered module."""
    return sorted(_reg(registry).modules())


def module_summary(name: str, registry=None) -> Dict[str, object]:
    """``{"module", "provides", "requires"}`` for one module.

    Raises :class:`SelfcapsError` for unknown names — never invents one.
    """
    reg = _reg(registry)
    if name not in reg.modules():
        raise SelfcapsError(f"no such module: {name!r}")
    decl = reg.declaration(name)
    return {
        "module": name,
        "provides": sorted(decl.get("provides", [])),
        "requires": sorted(decl.get("requires", [])),
    }


def list_capabilities(prefix: Optional[str] = None, registry=None) -> List[str]:
    """Every ``<module>.<thing>`` capability, optionally filtered by prefix."""
    caps: List[str] = []
    reg = _reg(registry)
    for name in reg.modules():
        for cap in reg.declaration(name).get("provides", []):
            if prefix is None or cap.startswith(prefix):
                caps.append(cap)
    return sorted(set(caps))


def find_capability(query: str, registry=None) -> Dict[str, List[str]]:
    """Modules whose provided capabilities contain ``query`` (case-insensitive)."""
    reg = _reg(registry)
    needle = query.strip().lower()
    hits: Dict[str, List[str]] = {}
    for name in sorted(reg.modules()):
        matched = [
            cap
            for cap in reg.declaration(name).get("provides", [])
            if needle in cap.lower()
        ]
        if matched:
            hits[name] = sorted(matched)
    return hits


def who_provides(capability: str, registry=None) -> Optional[str]:
    """The module that provides exactly ``capability``, or None."""
    reg = _reg(registry)
    for name in sorted(reg.modules()):
        if capability in reg.declaration(name).get("provides", []):
            return name
    return None


def dependents_chain(name: str, registry=None) -> List[str]:
    """Modules that (transitively) depend on ``name`` — what would feel it."""
    reg = _reg(registry)
    if name not in reg.modules():
        raise SelfcapsError(f"no such module: {name!r}")
    return reg.dependents_of(name, transitive=True)


def render_module(name: str, registry=None) -> str:
    """One plain-text capability card for a module."""
    info = module_summary(name, registry)
    lines = [f"== {info['module']} =="]
    lines.append("provides:")
    for cap in info["provides"]:
        lines.append(f"  + {cap}")
    if info["requires"]:
        lines.append("requires:")
        for req in info["requires"]:
            lines.append(f"  - {req}")
    else:
        lines.append("requires: (nothing)")
    return "\n".join(lines)


def render_index(registry=None) -> str:
    """One line per module: name and its capability count."""
    lines = []
    for name in all_modules(registry):
        n = len(module_summary(name, registry)["provides"])
        lines.append(f"{name}: {n} capabilit{'y' if n == 1 else 'ies'}")
    return "\n".join(lines)


def register_capabilities(reg) -> None:
    """Register this module's capabilities against an interop Registry."""
    reg.register(MODULE_NAME, provides=list(PROVIDES), requires=list(REQUIRES))
