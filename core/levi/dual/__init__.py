"""LEVI Dual-Reality Files — one file, two sides.

Signature concept adapted from the OMEGA Canon (Feature 8: Dual-Reality
File System; Alpha & Omega meta-doctrine M-01: every canon is simultaneously
a written declaration AND a physical engine). Original implementation.

A dual file carries both halves of a thing in one place:

- SIDE A (PHYSICAL) — what it does: automations, flows, device logic, code.
- SIDE B (CANON) — what it is: architecture, identity, theory, purpose.

The two sides update together, evolve together, stay in sync. ``verify()``
reports drift; ``seal()`` identity-locks a synced file so later drift is
detectable.
"""

from levi.dual.file import (
    DualFile,
    create,
    read,
    seal,
    verify,
    verify_seal,
)

__all__ = ["DualFile", "create", "read", "seal", "verify", "verify_seal"]
