"""Canon lock — the LEGION plan's Phase 0 milestone, as code.

The plan's Phase 0 has two milestones:
  1. the universe's public-facing positioning statement, held eyes-only
     until Chauncey signs it VERBATIM;
  2. the inventory of what must NEVER appear in shared surfaces.

This module implements the lock, not the content: the statement lives
here only once signed, and the never-surface inventory itself stays
eyes-only (Chauncey + Rex) — it is NEVER committed to the repo. The
surface_guard module enforces a caller-supplied inventory at share time.

Done-when per the plan: Chauncey signs the positioning line verbatim.
Until then, state() reports unsigned and every gate stays locked.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from levi.legion_collective import conventions as C
from levi.legion_collective.registry import RegistryError

# The exact attestation required to sign. Nothing signs without it.
SIGN_ATTESTATION = "I, Chauncey, sign this positioning verbatim."

# Standing hard gates from the LEGION plan. Locked until counsel has
# spoken AND Chauncey gives the five specifics per action. Code cannot
# unlock these; only his word (recorded here) can.
GATES = (
    "lawyer_before_first_mint",
    "no_public_drop",
    "no_testnet_mint",
    "no_customer_release",
)


def default_canon_path() -> Path:
    override = os.environ.get(C.STORE_ENV_VAR)
    if override:
        return Path(override).parent / C.CANON_FILENAME
    return Path.home() / C.DEFAULT_STORE_DIRNAME / C.CANON_FILENAME


def _blank() -> dict:
    return {
        "schema_version": C.SCHEMA_VERSION,
        "positioning_statement": None,
        "signed_by": None,
        "signed_at": None,
        "gates": {name: "locked" for name in GATES},
    }


class CanonLock:
    """Holds the positioning statement and the standing gates."""

    def __init__(self, canon_path: Path | str | None = None) -> None:
        self.canon_path = Path(canon_path) if canon_path else default_canon_path()
        self._data = _blank()
        if self.canon_path.exists():
            raw = json.loads(self.canon_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise RegistryError(f"corrupt canon file: {self.canon_path}")
            self._data = raw

    def _save(self) -> None:
        self.canon_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.canon_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(tmp, self.canon_path)

    def state(self) -> dict:
        return json.loads(json.dumps(self._data))

    def sign_positioning(self, statement: str, attestation: str) -> dict:
        """Record Chauncey's verbatim sign-off. Fails closed on anything else."""
        if not isinstance(statement, str) or not statement.strip():
            raise RegistryError("positioning statement must be a non-empty string")
        if attestation != SIGN_ATTESTATION:
            raise RegistryError(
                "signing requires Chauncey's exact verbatim attestation"
            )
        self._data["positioning_statement"] = statement.strip()
        self._data["signed_by"] = "Chauncey"
        self._data["signed_at"] = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
        self._save()
        return self.state()

    def gate(self, name: str) -> str:
        if name not in GATES:
            raise RegistryError(f"unknown gate: {name}")
        return self._data["gates"][name]

    def release_gate(self, name: str, **kwargs) -> dict:
        """Attempt to release a standing gate. Always refused in code.

        Releasing a gate needs counsel's review AND Chauncey's five
        specifics per action — neither is expressible as a function call.
        """
        raise RegistryError(
            f"gate {name!r} is standing law: release needs counsel + Chauncey, "
            "not a code path"
        )
