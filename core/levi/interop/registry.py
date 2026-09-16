"""Capability registry for interpenetrated modules.

Modules declare what they ``provides`` and what they ``requires`` as pure
data — no imports, no side effects. Because the existing modules cannot be
edited (additive-only), their declarations live in
:mod:`levi.interop.manifest` as static data; future modules may declare
themselves at runtime through :func:`register`.

Validation is **deny-closed**: a declaration is rejected when

- the module name is unknown / unregistered (:func:`check`),
- any ``requires`` target names a module that is not registered, or
- a declaration is malformed (non-string capability names, etc.).

:func:`dependents_of` supports impact analysis: "who breaks if I change X?"
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Set


class RegistryError(ValueError):
    """Deny-closed registry validation failure."""


class Registry:
    """A standalone capability registry.

    Instances are independent so tests (and future multi-tenant hosts) get
    clean state; the module-level functions below operate on a default
    instance pre-loaded with the static manifest.
    """

    def __init__(self) -> None:
        self._declarations: Dict[str, Dict[str, List[str]]] = {}

    # -- declaration ------------------------------------------------------

    def register(
        self,
        name: str,
        provides: Iterable[str] = (),
        requires: Iterable[str] = (),
    ) -> None:
        """Declare a module's capabilities. Deny-closed on duplicates and
        malformed capability lists."""
        if not isinstance(name, str) or not name.strip():
            raise RegistryError("register: module name must be a non-empty str")
        name = name.strip()
        if name in self._declarations:
            raise RegistryError(
                "register: module %r is already declared; "
                "re-declaration is denied (edit the manifest instead)" % name
            )
        provides_l = _clean_caps(provides, "provides", name)
        requires_l = _clean_caps(requires, "requires", name)
        self._declarations[name] = {"provides": provides_l, "requires": requires_l}

    def declaration(self, name: str) -> Dict[str, List[str]]:
        try:
            return self._declarations[name]
        except KeyError:
            raise RegistryError("undeclared module %r" % (name,)) from None

    def modules(self) -> List[str]:
        return sorted(self._declarations)

    # -- validation --------------------------------------------------------

    def check(self, module: str) -> Dict[str, List[str]]:
        """Validate one module's declaration. Deny-closed: raises
        :class:`RegistryError` when the module is undeclared or when any
        ``requires`` target is not a registered module."""
        decl = self.declaration(module)  # raises on undeclared module
        unknown = [t for t in decl["requires"] if t not in self._declarations]
        if unknown:
            raise RegistryError(
                "check(%r): unknown requires target(s): %s — "
                "every dependency must be a registered module"
                % (module, ", ".join(sorted(unknown)))
            )
        return decl

    def check_all(self) -> Dict[str, Dict[str, List[str]]]:
        """Validate every declaration; raise one aggregated error if any fail."""
        failures: List[str] = []
        for name in self._declarations:
            try:
                self.check(name)
            except RegistryError as exc:
                failures.append(str(exc))
        if failures:
            raise RegistryError(
                "check_all: %d invalid declaration(s):\n- %s"
                % (len(failures), "\n- ".join(failures))
            )
        return {n: dict(self._declarations[n]) for n in self._declarations}

    # -- impact analysis ----------------------------------------------------

    def dependents_of(self, name: str, transitive: bool = False) -> List[str]:
        """Modules that directly ``requires`` *name*.

        With ``transitive=True``, the full reverse-dependency closure
        (who depends on the dependents, and so on). Raises
        :class:`RegistryError` for undeclared *name*.
        """
        self.declaration(name)  # deny-closed on unknown module
        direct = sorted(
            m for m, d in self._declarations.items() if name in d["requires"]
        )
        if not transitive:
            return direct
        seen: Set[str] = set(direct)
        frontier = list(direct)
        while frontier:
            current = frontier.pop()
            for dep in self.dependents_of(current):
                if dep not in seen:
                    seen.add(dep)
                    frontier.append(dep)
        return sorted(seen)


def _clean_caps(
    caps: Iterable[str], kind: str, module: str
) -> List[str]:
    if isinstance(caps, str):
        raise RegistryError(
            "register(%r): %s must be an iterable of strings, not a bare str"
            % (module, kind)
        )
    try:
        items = list(caps)
    except TypeError:
        raise RegistryError(
            "register(%r): %s must be an iterable of strings" % (module, kind)
        ) from None
    cleaned: List[str] = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise RegistryError(
                "register(%r): %s entries must be non-empty strings, got %r"
                % (module, kind, item)
            )
        cleaned.append(item.strip())
    if len(set(cleaned)) != len(cleaned):
        raise RegistryError(
            "register(%r): duplicate entries in %s" % (module, kind)
        )
    return cleaned


# -- default instance, pre-loaded with the static manifest ------------------

_default = Registry()


def _load_manifest() -> None:
    from levi.interop.manifest import DECLARATIONS

    for name, decl in DECLARATIONS.items():
        _default.register(
            name,
            provides=decl.get("provides", ()),
            requires=decl.get("requires", ()),
        )


_load_manifest()


def register(
    name: str,
    provides: Sequence[str] = (),
    requires: Sequence[str] = (),
) -> None:
    """Declare a future module on the default registry (see :meth:`Registry.register`)."""
    _default.register(name, provides=provides, requires=requires)


def check(module: str) -> Dict[str, List[str]]:
    """Validate one module on the default registry (deny-closed)."""
    return _default.check(module)


def check_all() -> Dict[str, Dict[str, List[str]]]:
    """Validate every declaration on the default registry (deny-closed)."""
    return _default.check_all()


def dependents_of(name: str, transitive: bool = False) -> List[str]:
    """Reverse dependencies of *name* on the default registry."""
    return _default.dependents_of(name, transitive=transitive)


def modules() -> List[str]:
    """All declared module names on the default registry."""
    return _default.modules()
