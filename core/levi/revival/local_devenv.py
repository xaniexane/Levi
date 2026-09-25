"""local_devenv — local-first dev environments, cloud as explicit BYO.

Studied from: github-pattern-hunt-20260916-0018 (report.md [Ranked additions 9]).
Load-bearing idea: dev environments run on your machine by default; cloud
provisioning is bring-your-own — your keys, your provider account, billed
by them, never by the tool.

LEVI's take: ``Forge`` holds ``DevEnv`` definitions (runtime spec for a
local machine: working directory, env vars, port map, setup commands) and
``CloudBring`` plans (a recipe the user's *own* cloud provider executes:
provider, region, machine shape, plus a credential *label* — never the
secret itself). ``DevEnv`` can export a plain shell script that boots the
environment locally, and ``CloudBring`` exports a human-readable provisioning
runbook. Everything is serializable; nothing phones home.

Honest limits: this module produces specs, scripts, and runbooks. It does
not provision machines, run containers, or hold real credentials — those
stay with the user and their provider.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import shlex
import uuid
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


ORIGIN = "levi-revival/local-devenv"


@dataclass
class EnvVar:
    name: str
    value: str
    secret: bool = False  # secret values are never written into exported scripts


@dataclass
class PortMap:
    host: int
    guest: int
    protocol: str = "tcp"


@dataclass
class DevEnv:
    """A local-first dev environment definition."""

    id: str
    name: str
    language: str
    workdir: str
    setup_commands: List[str] = field(default_factory=list)
    env_vars: List[EnvVar] = field(default_factory=list)
    ports: List[PortMap] = field(default_factory=list)
    created_by: str = "user"

    def validate(self) -> List[str]:
        """Return a list of problems; empty means the spec is sound."""
        problems = []
        if not self.name.strip():
            problems.append("name is empty")
        if not self.workdir.strip():
            problems.append("workdir is empty")
        hosts = [p.host for p in self.ports]
        if len(hosts) != len(set(hosts)):
            problems.append("duplicate host ports in port map")
        names = [v.name for v in self.env_vars]
        if len(names) != len(set(names)):
            problems.append("duplicate env var names")
        for v in self.env_vars:
            if not v.name.strip():
                problems.append("env var with empty name")
        return problems

    def export_shell(self) -> str:
        """Render a plain POSIX shell script that boots this env locally.

        Secret env vars are referenced by name only (``$NAME``) — their
        values stay in the user's own shell.
        """
        lines = [
            "#!/bin/sh",
            f"# LEVI devenv: {self.name}",
            "# Generated locally. Your machine, your keys.",
            "set -e",
        ]
        lines.append(f'cd "{self.workdir}"')
        for v in self.env_vars:
            if v.secret:
                lines.append(f': "${{{v.name}:?{v.name} must be set in your shell}}"')
                lines.append(f"export {v.name}")
            else:
                lines.append(f"export {v.name}={shlex.quote(v.value)}")
        for cmd in self.setup_commands:
            lines.append(cmd)
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "DevEnv":
        env_vars = [EnvVar(**v) for v in d.get("env_vars", [])]
        ports = [PortMap(**p) for p in d.get("ports", [])]
        return cls(
            id=d["id"],
            name=d["name"],
            language=d.get("language", ""),
            workdir=d.get("workdir", ""),
            setup_commands=list(d.get("setup_commands", [])),
            env_vars=env_vars,
            ports=ports,
            created_by=d.get("created_by", "user"),
        )


@dataclass
class CloudBring:
    """An explicit bring-your-own-cloud provisioning plan.

    The plan names the user's provider and region and the shape of machine
    they want; it carries a credential *label* (e.g. "my-aws-profile"),
    never a secret. Exporting produces a runbook the user executes with
    their own tooling and their own billing.
    """

    id: str
    name: str
    provider: str
    region: str
    machine_shape: str
    credential_label: str
    devenv_id: Optional[str] = None
    steps: List[str] = field(default_factory=list)

    def runbook(self) -> str:
        lines = [
            f"# BYO cloud runbook: {self.name}",
            f"# Provider: {self.provider}  Region: {self.region}",
            f"# Machine: {self.machine_shape}  Credentials: [{self.credential_label}]",
            "# Billed by YOUR provider. LEVI holds no keys and no wallet.",
        ]
        for i, step in enumerate(self.steps, 1):
            lines.append(f"{i}. {step}")
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CloudBring":
        return cls(
            id=d["id"],
            name=d["name"],
            provider=d.get("provider", ""),
            region=d.get("region", ""),
            machine_shape=d.get("machine_shape", ""),
            credential_label=d.get("credential_label", ""),
            devenv_id=d.get("devenv_id"),
            steps=list(d.get("steps", [])),
        )


class Forge:
    """Registry of local dev environments plus explicit BYO cloud plans."""

    def __init__(self) -> None:
        self.envs: Dict[str, DevEnv] = {}
        self.brings: Dict[str, CloudBring] = {}

    # -- local envs -----------------------------------------------------------

    def define_env(
        self, name: str, language: str, workdir: str, created_by: str = "user"
    ) -> DevEnv:
        env = DevEnv(
            id=f"env-{uuid.uuid4().hex[:8]}",
            name=name,
            language=language,
            workdir=workdir,
            created_by=created_by,
        )
        self.envs[env.id] = env
        return env

    def get_env(self, env_id: str) -> DevEnv:
        return self.envs[env_id]

    def list_envs(self) -> List[DevEnv]:
        return list(self.envs.values())

    def drop_env(self, env_id: str) -> bool:
        return self.envs.pop(env_id, None) is not None

    # -- BYO cloud ------------------------------------------------------------

    def plan_bring(
        self,
        name: str,
        provider: str,
        region: str,
        machine_shape: str,
        credential_label: str,
        devenv_id: Optional[str] = None,
    ) -> CloudBring:
        if devenv_id is not None and devenv_id not in self.envs:
            raise KeyError(f"unknown devenv {devenv_id!r}")
        plan = CloudBring(
            id=f"byo-{uuid.uuid4().hex[:8]}",
            name=name,
            provider=provider,
            region=region,
            machine_shape=machine_shape,
            credential_label=credential_label,
            devenv_id=devenv_id,
        )
        self.brings[plan.id] = plan
        return plan

    def get_bring(self, plan_id: str) -> CloudBring:
        return self.brings[plan_id]

    def list_brings(self) -> List[CloudBring]:
        return list(self.brings.values())

    # -- snapshots ------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "envs": {k: v.to_dict() for k, v in self.envs.items()},
            "brings": {k: v.to_dict() for k, v in self.brings.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Forge":
        f = cls()
        for k, v in d.get("envs", {}).items():
            f.envs[k] = DevEnv.from_dict(v)
        for k, v in d.get("brings", {}).items():
            f.brings[k] = CloudBring.from_dict(v)
        return f
