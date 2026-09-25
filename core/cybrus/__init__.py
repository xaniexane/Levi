"""Cybrus standalone entry package.

``python -m cybrus`` — the standalone product front door. This thin shim
re-exports the ``levi.cybrus`` engine so another user can run Cybrus without
learning the whole LEVI tree; the engine stays the single implementation.

Lazy re-export (PEP 562): the engine package ``__init__`` pulls sibling
modules, so attribute access resolves on first use instead of import time.
"""

from __future__ import annotations

__all__ = [
    "AccountFactory",
    "AutoLockVault",
    "CredentialVault",
    "IdentityStore",
    "IdentityVault",
    "OAuthVault",
    "TokenEngine",
    "cybrus_dir",
    "generate_password",
    "product",
    "quickstart",
]


def __getattr__(name: str):
    import importlib

    if name in __all__:
        engine = importlib.import_module("levi.cybrus")
        return getattr(engine, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(__all__)
