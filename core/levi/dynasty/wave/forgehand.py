# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Forgehand — keeper of the LEVI Forge.

Jack of all trades; editing 10. Owns the editor × runtime fusion:
files written with intent, grafts sandboxed, every byte attributable.

Its unreplicable attribute is **intent-replay attestation**: Forgehand
never trusts bytes it did not derive. A write seals only when replaying
the write's own recorded intent on a shadow copy yields byte-identical
output. Any outside edit between write and seal fails attestation with
a typed error and no receipt — the seal binds the derivation, not just
the bytes.
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.dynasty.dna import AgentError, DynastyAgent

__all__ = ["ForgeError", "Forgehand"]


class ForgeError(AgentError):
    """A forge write was refused, escaped its sandbox, or failed
    intent-replay attestation."""


#: The only operations a write intent may carry.
_INTENT_OPS = ("write", "append")


class Forgehand(DynastyAgent):
    """Builds the LEVI Forge: editor core, embedded runtime, grafts."""

    agent_id = "forgehand"
    display_name = "Forgehand"
    owns = "LEVI Forge"
    first_milestone = "editor core + embedded runtime"
    proficiency = {"editing": 10, "runtime": 9, "grafts": 8, "general": 6}
    specialties = [
        "editor core: files written with recorded intent",
        "embedded runtime: code read, written, and run locally",
        "signed, sandboxed graft API — grafts run boxed and attributable",
        "intent-replay attestation — seals bind the derivation",
    ]
    attributes = [
        {
            "name": "intent-replay attestation",
            "assertion": (
                "Forgehand never trusts bytes it did not derive: a write "
                "seals only when replaying the write's own recorded intent "
                "on a shadow copy yields byte-identical output — any outside "
                "edit between write and seal fails attestation with a typed "
                "error and no receipt."
            ),
        }
    ]

    def __init__(self, home: Optional[Path] = None) -> None:
        # The seal lane must exist before super().__init__ binds the
        # default wares: sign_milestone touches the keeper key, whose
        # first-boot creation races under threads (partial reads fork
        # the key view and break the chain; proven in the purge).
        self._seal_lock = threading.Lock()
        super().__init__(home)
        # The forge sandbox: every forged file lives under the agent's
        # own LEVI_HOME scratch — never the repo, never the wider disk.
        self._scratch = self._home / "dynasty" / "agents" / "forgehand" / "scratch"
        self._scratch.mkdir(parents=True, exist_ok=True)
        # Warm the keeper key once, single-threaded, through the locked
        # ware — first-boot key creation must never happen mid-storm.
        self.wares.invoke("sign_milestone", f"{self.agent_id}:key-warmup")

    def _sign_milestone(self, milestone: str) -> Dict[str, str]:
        """Corroboration signature, through the seal lane."""
        with self._seal_lock:
            return super()._sign_milestone(milestone)

    def do_task(
        self,
        kind: str,
        payload: Dict[str, Any],
        task: str = "",
        verify: Any = None,
    ) -> Dict[str, Any]:
        """Plan→execute→verify→receipt, through the per-agent seal lane."""
        with self._seal_lock:
            return super().do_task(kind, payload, task=task, verify=verify)

    # -- sandbox ------------------------------------------------------
    def _resolve(self, name: str) -> Path:
        """Resolve a forged file name inside the sandbox.

        Raises :class:`ForgeError` on absolute paths, separators, or
        parent-directory escapes — a graft never writes outside its box.
        """
        if not isinstance(name, str) or not name.strip():
            raise ForgeError("forged file name must be a non-empty string")
        cleaned = name.strip()
        if (
            Path(cleaned).is_absolute()
            or ".." in Path(cleaned).parts
            or "/" in cleaned
            or "\\" in cleaned
        ):
            raise ForgeError(f"forged file escapes the sandbox: {name!r}")
        return self._scratch / cleaned

    @staticmethod
    def _check_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Validate a write intent. Raises :class:`ForgeError`."""
        if not isinstance(steps, list) or not steps:
            raise ForgeError("write intent must be a non-empty list of steps")
        clean: List[Dict[str, str]] = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ForgeError(f"intent step {i} must be a dict")
            op = step.get("op")
            content = step.get("content")
            if op not in _INTENT_OPS:
                raise ForgeError(
                    f"intent step {i}: unknown op {op!r} (allowed: {_INTENT_OPS})"
                )
            if not isinstance(content, str):
                raise ForgeError(
                    f"intent step {i}: content must be a string, "
                    f"got {type(content).__name__}"
                )
            clean.append({"op": op, "content": content})
        return clean

    @staticmethod
    def _execute(steps: List[Dict[str, str]], path: Path) -> None:
        """Run the intent against ``path`` — the derivation itself."""
        for step in steps:
            if step["op"] == "write":
                path.write_bytes(step["content"].encode("utf-8"))
            else:  # append
                with open(path, "ab") as fh:
                    fh.write(step["content"].encode("utf-8"))

    @staticmethod
    def _digest(path: Path) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    # -- intent-replay attestation -------------------------------------
    def attest(self, path: Path, steps: List[Dict[str, str]]) -> str:
        """Re-derive ``path``'s bytes by replaying ``steps`` on a shadow
        copy and demand byte-identical output.

        Returns the attested sha256. Raises :class:`ForgeError` when the
        replayed bytes differ — something edited the file outside the
        intent — and mints nothing.
        """
        if not path.is_file():
            raise ForgeError(f"attest: not a file: {path}")
        shadow = path.parent / f".shadow-{path.name}"
        try:
            self._execute(steps, shadow)
            real_digest = self._digest(path)
            shadow_digest = self._digest(shadow)
        finally:
            try:
                shadow.unlink()
            except OSError:
                pass
        if real_digest != shadow_digest:
            raise ForgeError(
                "intent-replay attestation failed: the file's bytes no "
                "longer match their recorded derivation — outside edit "
                "detected, seal refused"
            )
        return real_digest

    def forge_file(self, name: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Write ``name`` from a recorded intent, then attest it.

        The file seals only when the shadow replay matches — the
        receipt binds the derivation, not just the bytes.
        """
        clean_steps = self._check_steps(steps)
        path = self._resolve(name)
        self._execute(clean_steps, path)
        digest = self.attest(path, clean_steps)
        return {
            "name": name,
            "path": str(path),
            "sha256": digest,
            "steps": len(clean_steps),
            "attested": True,
        }

    # -- dispatch ------------------------------------------------------
    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Forge-domain shapes; everything else rides the shared DNA."""
        if not isinstance(task, dict):
            raise AgentError("handle requires a task dict")
        shape = task.get("shape")
        if shape == "forge":
            result = self.forge_file(task.get("name", ""), task.get("steps", []))
            return result
        if shape == "attest":
            path = self._resolve(task.get("name", ""))
            steps = self._check_steps(task.get("steps", []))
            return {"name": task.get("name"), "sha256": self.attest(path, steps)}
        return super().handle(task)

    # -- first green task -----------------------------------------------
    def first_task(self) -> Dict[str, Any]:
        """Write a temp file (sandbox, never the repo), read it back,
        hash-verify the round-trip, attest the derivation, seal."""
        steps = [{"op": "write", "content": "forgehand green\n"}]
        forged = self.forge_file("first.txt", steps)
        path = Path(forged["path"])
        read_back = path.read_bytes()

        def _verify(payload: Dict[str, Any]) -> None:
            if read_back != b"forgehand green\n":
                raise AgentError("read-back bytes differ from the intent")
            if self._digest(path) != forged["sha256"]:
                raise AgentError("round-trip hash mismatch")

        return self.do_task(
            "wave.first_task",
            {
                "name": "first.txt",
                "sha256": forged["sha256"],
                "steps": forged["steps"],
                "attested": True,
                "round_trip": "green",
            },
            task="forgehand:first",
            verify=_verify,
        )
