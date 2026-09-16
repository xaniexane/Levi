"""LEVI Galaxy — packaging + namespacing substrate.

Two halves of the Galaxy layer:
  - package.py   : levi-skill.json manifest loading + strict validation.
  - namespace.py : "<author>.<name>" ids, parsing, collision detection,
                   and the deny-closed install/upgrade resolution policy.
  - service.py   : the deny-closed service directory (ports, capabilities,
                   metering) — the runtime half of the ecosystem.
  - __main__.py  : `python -m levi.galaxy` CLI.

All are stdlib-only and deny-closed: anything malformed is refused with a
precise reason instead of being guessed at.

Two stores, one truth: ``levi.galaxy.registry`` records *what is installed*
(JSONL at ``~/.levi/galaxy/registry.jsonl``); ``levi.galaxy.service`` is the
runtime view of *what is callable*. :meth:`GalaxyServices.register_installed`
and :meth:`GalaxyServices.sync_from_registry` bridge them — integrity is
verified before anything is imported.
"""

from __future__ import annotations

__all__: list[str] = []

try:  # sibling in-flight: packaging builder
    from levi.galaxy.package import (
        MANIFEST_FILENAME,
        VALID_KINDS,
        Manifest,
        PackageError,
        load_manifest,
        parse_version,
        validate_manifest,
    )

    __all__ += [
        "MANIFEST_FILENAME",
        "VALID_KINDS",
        "Manifest",
        "PackageError",
        "load_manifest",
        "parse_version",
        "validate_manifest",
    ]
except ImportError:
    pass

try:  # sibling in-flight: namespacing builder
    from levi.galaxy.namespace import (
        Collision,
        NamespaceError,
        RegistryEntry,
        Resolution,
        check_collision,
        parse_namespaced,
        resolve,
        to_namespaced,
    )

    __all__ += [
        "Collision",
        "NamespaceError",
        "RegistryEntry",
        "Resolution",
        "check_collision",
        "parse_namespaced",
        "resolve",
        "to_namespaced",
    ]
except ImportError:
    pass
