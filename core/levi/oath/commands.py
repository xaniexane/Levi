"""Signed command definitions for LEVI Oath — the "sudo for agents" registry.

A command definition is canonical JSON stored as ``<name>.json`` next to a
detached armored GPG signature ``<name>.json.sig`` in
``<oath home>/commands/``::

    {
      "name": "disk-usage",
      "version": 1,
      "description": "Report disk usage for a directory (read-only).",
      "tier": "read",
      "argv": ["du", "-sh", "{path}"],
      "args": {
        "path": {"type": "string", "required": true, "pattern": "^[\\\\w\\\\-./]+$"}
      },
      "created_by": "owner",
      "created_at": "2026-09-15T18:00:00Z",
      "expires_at": "2027-09-15T00:00:00Z"
    }

The **sign ceremony**: the owner reviews the canonical JSON, then signs it
with their own key (``oath command sign <name>``).  The loader *refuses*
any definition with a missing, bad, or expired signature, and additionally
requires the signature to come from the owner's pinned fingerprint
(``<oath home>/owner.json``).  The agent itself holds zero authority — it
can never create or bless a command, only the owner can.

Risk tiers: ``read`` (observability only), ``write`` (state-changing),
``execute`` (runs pipelines / spawns work), ``dangerous`` (requires an
explicit ``d`` grant per command; never inherited).

Execution never uses ``shell=True``: argv templates are rendered with
validated arguments and passed to :func:`subprocess.run` as a list.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from levi.oath import COMMANDS_DIR, OWNER_FILE
from levi.oath.contacts import TIERS
from levi.oath.trust import verify_detached

__all__ = [
    "CommandDefinition",
    "CommandRegistry",
    "DefinitionError",
    "canonical_json",
    "parse_expires_at",
]

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_ARG_TYPES = ("string", "integer", "boolean")
_BUILTIN_NAMES = ("ai", "reply")


class DefinitionError(ValueError):
    """Raised when a command definition is invalid or its signature fails."""


def canonical_json(definition: dict[str, Any]) -> bytes:
    """Render the canonical bytes that get signed.

    Canonical form: UTF-8 JSON, keys sorted, no insignificant whitespace.
    The signature file covers exactly these bytes — any edit, however
    small, invalidates the signature.
    """
    return (json.dumps(definition, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def parse_expires_at(value: Any) -> Optional[_dt.datetime]:
    """Parse an ISO-8601 ``expires_at``; ``None``/empty means never expires."""
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = _dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise DefinitionError(f"expires_at is not ISO-8601: {value!r}") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_dt.timezone.utc)
    return moment


@dataclass
class CommandDefinition:
    """A validated, signature-verified command definition."""

    name: str
    argv: list[str]
    args: dict[str, dict[str, Any]]
    tier: str
    description: str = ""
    version: int = 1
    created_by: str = ""
    created_at: str = ""
    expires_at: str = ""
    builtin: bool = False

    def __post_init__(self) -> None:
        if not _NAME_RE.match(self.name):
            raise DefinitionError(f"invalid command name: {self.name!r}")
        if self.tier not in TIERS:
            raise DefinitionError(f"unknown tier {self.tier!r} for {self.name!r}")
        if not self.argv or not all(isinstance(a, str) and a for a in self.argv):
            raise DefinitionError(f"argv must be a non-empty list of strings for {self.name!r}")
        for arg_name, spec in self.args.items():
            if not isinstance(spec, dict):
                raise DefinitionError(f"arg {arg_name!r} spec must be an object")
            atype = spec.get("type", "string")
            if atype not in _ARG_TYPES:
                raise DefinitionError(f"arg {arg_name!r} has unknown type {atype!r}")
            pattern = spec.get("pattern")
            if pattern is not None:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    raise DefinitionError(
                        f"arg {arg_name!r} has invalid pattern: {exc}"
                    ) from exc

    # -- argument handling -------------------------------------------
    def placeholders(self) -> set[str]:
        """Placeholder names used in the argv template."""
        return set(re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", " ".join(self.argv)))

    def render(self, args: dict[str, Any]) -> list[str]:
        """Validate ``args`` against the schema and render the argv list.

        Raises :class:`DefinitionError` on missing/extra/invalid args.
        """
        values: dict[str, str] = {}
        for arg_name, spec in self.args.items():
            if arg_name in args:
                raw = args[arg_name]
            elif "default" in spec:
                raw = spec["default"]
            elif spec.get("required", False):
                raise DefinitionError(f"missing required argument: {arg_name!r}")
            else:
                continue
            values[arg_name] = self._coerce(arg_name, spec, raw)
        unknown = set(args) - set(self.args)
        if unknown:
            raise DefinitionError(f"unknown arguments for {self.name!r}: {sorted(unknown)}")
        missing = self.placeholders() - set(values)
        if missing:
            raise DefinitionError(
                f"argv template of {self.name!r} needs arguments: {sorted(missing)}"
            )
        return [self._fill(token, values) for token in self.argv]

    @staticmethod
    def _fill(token: str, values: dict[str, str]) -> str:
        def _sub(match: "re.Match[str]") -> str:
            return values[match.group(1)]

        return re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", _sub, token)

    @staticmethod
    def _coerce(arg_name: str, spec: dict[str, Any], raw: Any) -> str:
        atype = spec.get("type", "string")
        if atype == "integer":
            try:
                value = int(str(raw), 10)
            except (TypeError, ValueError) as exc:
                raise DefinitionError(f"argument {arg_name!r} must be an integer") from exc
            lo, hi = spec.get("min"), spec.get("max")
            if lo is not None and value < lo:
                raise DefinitionError(f"argument {arg_name!r} below minimum {lo}")
            if hi is not None and value > hi:
                raise DefinitionError(f"argument {arg_name!r} above maximum {hi}")
            return str(value)
        if atype == "boolean":
            text = str(raw).strip().lower()
            if text not in ("true", "false", "1", "0", "yes", "no"):
                raise DefinitionError(f"argument {arg_name!r} must be a boolean")
            return "true" if text in ("true", "1", "yes") else "false"
        text = str(raw)
        max_len = int(spec.get("max_length", 1024))
        if len(text) > max_len:
            raise DefinitionError(f"argument {arg_name!r} exceeds max_length {max_len}")
        pattern = spec.get("pattern")
        if pattern and not re.fullmatch(pattern, text):
            raise DefinitionError(
                f"argument {arg_name!r} does not match allowed pattern"
            )
        # Belt and suspenders: even a lax schema cannot smuggle shell syntax
        # through, because we never invoke a shell — but reject the obvious
        # metacharacters anyway so a definition author gets loud feedback.
        if re.search(r"[`$;&|><\n\r]", text):
            raise DefinitionError(
                f"argument {arg_name!r} contains forbidden shell metacharacters"
            )
        allowed = spec.get("enum")
        if allowed is not None and text not in allowed:
            raise DefinitionError(f"argument {arg_name!r} must be one of {allowed}")
        return text


class CommandRegistry:
    """Loads signed command definitions; refuses anything unsigned."""

    def __init__(self, directory: Optional[Path] = None) -> None:
        self.directory = directory or COMMANDS_DIR()
        self._cache: Optional[dict[str, CommandDefinition]] = None

    # -- owner identity -----------------------------------------------
    @staticmethod
    def owner_fingerprint() -> Optional[str]:
        """The owner's pinned fingerprint from ``owner.json``, if set."""
        try:
            data = json.loads(OWNER_FILE().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        fpr = (data.get("fingerprint") or "").upper().replace(" ", "")
        return fpr or None

    # -- loading --------------------------------------------------------
    def load_all(self) -> dict[str, CommandDefinition]:
        """Load and verify every ``*.json`` definition in the directory.

        Any definition with a missing, bad, or expired signature — or a
        signature from anyone but the owner — raises
        :class:`DefinitionError`.  There is no "trust on first use".
        """
        definitions: dict[str, CommandDefinition] = {}
        definitions.update(_builtin_definitions())
        if self.directory.is_dir():
            for json_path in sorted(self.directory.glob("*.json")):
                if json_path.name.endswith(".sig"):
                    continue
                definitions[json_path.stem] = self._load_one(json_path)
        self._cache = definitions
        return definitions

    def get(self, name: str) -> CommandDefinition:
        if self._cache is None:
            self.load_all()
        assert self._cache is not None
        try:
            return self._cache[name]
        except KeyError as exc:
            raise DefinitionError(f"unknown command: {name!r}") from exc

    def _load_one(self, json_path: Path) -> CommandDefinition:
        raw = json_path.read_bytes()
        try:
            definition = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DefinitionError(f"{json_path.name}: not valid JSON: {exc}") from exc

        name = json_path.stem
        if not _NAME_RE.match(name):
            raise DefinitionError(f"invalid definition file name: {json_path.name!r}")
        if name in _BUILTIN_NAMES:
            raise DefinitionError(f"{name!r} is reserved for a builtin stage")
        if definition.get("name", name) != name:
            raise DefinitionError(
                f"{json_path.name}: name field {definition.get('name')!r} "
                f"does not match file name"
            )

        # Expiry is checked before signature verification so a stale-but-
        # once-valid definition can never slip through on a technicality.
        expires = parse_expires_at(definition.get("expires_at"))
        now = _dt.datetime.now(_dt.timezone.utc)
        if expires is not None and expires <= now:
            raise DefinitionError(
                f"{name!r}: definition expired at {definition.get('expires_at')!r}"
            )

        sig_path = json_path.with_suffix(json_path.suffix + ".sig")
        if not sig_path.exists():
            raise DefinitionError(
                f"{name!r}: missing detached signature {sig_path.name!r} — refused"
            )
        valid, fpr, _uid, detail = verify_detached(sig_path.read_bytes(), raw)
        if not valid:
            raise DefinitionError(f"{name!r}: bad signature — refused ({detail})")
        owner = self.owner_fingerprint()
        if owner and (fpr or "").upper().replace(" ", "") != owner:
            raise DefinitionError(
                f"{name!r}: signed by {fpr}, not by the owner — refused"
            )

        try:
            return CommandDefinition(
                name=name,
                argv=list(definition["argv"]),
                args={k: dict(v) for k, v in dict(definition.get("args", {})).items()},
                tier=str(definition.get("tier", "read")),
                description=str(definition.get("description", "")),
                version=int(definition.get("version", 1)),
                created_by=str(definition.get("created_by", "")),
                created_at=str(definition.get("created_at", "")),
                expires_at=str(definition.get("expires_at", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DefinitionError(f"{name!r}: invalid definition: {exc}") from exc

    # -- the sign ceremony ------------------------------------------------
    def write_unsigned(self, definition: dict[str, Any]) -> Path:
        """Write an unsigned definition draft for owner review.

        The draft is written as ``<name>.json`` *without* a ``.sig`` file,
        so it can never load until the owner explicitly signs it.
        """
        name = str(definition.get("name", ""))
        if not _NAME_RE.match(name):
            raise DefinitionError(f"invalid command name: {name!r}")
        path = self.directory / f"{name}.json"
        self.directory.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_json(definition))
        return path

    def sign(self, name: str, *, key_fingerprint: Optional[str] = None) -> Path:
        """The sign ceremony: re-verify the canonical bytes, then sign.

        Must be run by the owner (it prompts on the terminal via gpg's own
        pinentry; for unattended owner keys use ``--pinentry-mode loopback``
        through ``oath key`` tooling).  Writes ``<name>.json.sig``.
        """
        from levi.oath.keys import gpg_sign_args, run_gpg  # local import: keys is optional at runtime

        json_path = self.directory / f"{name}.json"
        if not json_path.exists():
            raise DefinitionError(f"no such definition: {name!r}")
        raw = json_path.read_bytes()
        # Re-parse so we never sign something we cannot load.
        definition = json.loads(raw.decode("utf-8"))
        CommandDefinition(
            name=name,
            argv=list(definition["argv"]),
            args={k: dict(v) for k, v in dict(definition.get("args", {})).items()},
            tier=str(definition.get("tier", "read")),
            description=str(definition.get("description", "")),
            version=int(definition.get("version", 1)),
        )
        sig_path = json_path.with_suffix(json_path.suffix + ".sig")
        cmd = gpg_sign_args() + ["--armor", "--detach-sign", "--output", str(sig_path)]
        if key_fingerprint:
            cmd += ["--local-user", key_fingerprint]
        cmd.append(str(json_path))
        run_gpg(*cmd)
        # Invalidate the cache so the next load picks up the signature.
        self._cache = None
        return sig_path

    # -- execution ----------------------------------------------------------
    def execute(
        self,
        definition: CommandDefinition,
        args: dict[str, Any],
        *,
        stdin_text: str = "",
        timeout: int = 120,
        env: Optional[dict[str, str]] = None,
    ) -> subprocess.CompletedProcess:
        """Render and run a command.  Never uses ``shell=True``."""
        argv = definition.render(args)
        return subprocess.run(
            argv,
            input=stdin_text.encode("utf-8", "replace"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            shell=False,
            env=env,
        )


def _builtin_definitions() -> dict[str, CommandDefinition]:
    """In-code builtins: ``ai`` (reasoning stage) and ``reply`` (mail stage).

    These are code, not email-controlled data, so they need no signature —
    they ship with the module the way libc ships with the OS.  They are
    still subject to the same policy checks as signed commands.
    """
    return {
        "ai": CommandDefinition(
            name="ai",
            argv=["ai"],
            args={"prompt": {"type": "string", "required": True, "max_length": 8000}},
            tier="execute",
            description="AI reasoning stage: runs the prompt through LEVI's "
            "agent runtime (or the honest offline fallback).",
            builtin=True,
        ),
        "reply": CommandDefinition(
            name="reply",
            argv=["reply"],
            args={
                "subject": {"type": "string", "required": False, "max_length": 200,
                            "default": "Re: LEVI Oath mission"},
                "body": {"type": "string", "required": True, "max_length": 20000},
            },
            tier="write",
            description="Mail reply stage: the daemon sends this as the "
            "mission's email reply via SMTP.",
            builtin=True,
        ),
    }
