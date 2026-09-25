"""Whole-organism scope (identity variant engine).

Derives a reflectable identity for every module declared in the interop
manifest: name, declared capabilities as fragments, wiring traits from the
declaration + CLI surface. Deterministic; stdlib-only.
"""

from __future__ import annotations

from typing import Any, Dict, List


def module_identity(
    name: str,
    declaration: Dict[str, Any],
    cli_commands: List[str],
    all_modules: List[str],
) -> Dict[str, Any]:
    """Build an identity dict for one manifest-declared module."""
    provides = list(declaration.get("provides", []) or [])
    requires = list(declaration.get("requires", []) or [])
    missing = sorted(r for r in requires if r not in all_modules)
    traits = {
        "declared": 1.0 if provides else 0.0,
        "wired": 1.0 if not missing else 0.0,
        "cli-reachable": 1.0 if cli_commands else 0.0,
        "self-contained": 1.0 if not requires else 0.5,
    }
    return {
        "name": name,
        "traits": traits,
        "params": {
            "provides_count": float(len(provides)),
            "requires_count": float(len(requires)),
            "cli_count": float(len(cli_commands)),
        },
        "fragments": sorted(provides),
        "lineage": ["manifest"],
        "module_meta": {
            "requires": sorted(requires),
            "missing_requires": missing,
            "cli": list(cli_commands),
        },
    }


def iter_module_identities() -> List[Dict[str, Any]]:
    """Module identities for every manifest declaration, sorted by name."""
    from levi.interop.manifest import DECLARATIONS
    from levi.interop.warehouses import CLI_COMMANDS

    names = sorted(DECLARATIONS)
    identities = []
    for name in names:
        decl = DECLARATIONS[name]
        identities.append(
            module_identity(name, decl, list(CLI_COMMANDS.get(name, [])), names)
        )
    return identities


def module_fracture_notes(identity: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extra module-level fracture checks beyond Echo's generic ones."""
    notes = []
    meta = identity.get("module_meta", {})
    for missing in meta.get("missing_requires", []):
        notes.append(
            {
                "type": "missing-dependency",
                "detail": "requires undeclared module %r" % missing,
                "penalty": 0.2,
            }
        )
    if not identity.get("fragments"):
        notes.append(
            {
                "type": "empty-provides",
                "detail": "declares no capabilities",
                "penalty": 0.15,
            }
        )
    return notes
