"""Sentinel contain — HITL-gated defensive containment.

Consequential defensive actions (temporarily blocking an IP, terminating
a process) are NEVER automatic. Every action follows:

    Plan → Preview → Permission → Execute → Verify → Receipt

The default is a dry-run preview. Execution requires an explicit
``confirm=True`` from a human at the call site (the CLI requires
``--confirm``). Destructive scope is deliberately narrow: one IPv4
address, one PID, temporary blocks only.

Stdlib-only: ``re``, ``subprocess``.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List

__all__ = [
    "ContainmentPlan",
    "plan_block_ip",
    "plan_terminate_process",
    "apply_plan",
    "is_valid_ipv4",
]

_IPV4_RE = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")


def is_valid_ipv4(value: str) -> bool:
    match = _IPV4_RE.match(value.strip())
    if not match:
        return False
    return all(0 <= int(octet) <= 255 for octet in match.groups())


@dataclass
class ContainmentPlan:
    """A proposed containment action: inspectable before execution."""

    action: str  # "block_ip" | "terminate_process"
    target: str
    commands: List[List[str]] = field(default_factory=list)
    rationale: str = ""
    reversible: bool = True

    def preview(self) -> str:
        lines = [
            "CONTAINMENT PLAN (defensive, human-confirmed)",
            f"  action:    {self.action}",
            f"  target:    {self.target}",
            f"  rationale: {self.rationale or '(operator-supplied)'}",
            f"  reversible: {'yes' if self.reversible else 'no'}",
            "  commands that WOULD run:",
        ]
        for cmd in self.commands:
            lines.append("    $ " + " ".join(cmd))
        lines.append("Nothing has executed. Re-run with explicit confirmation.")
        return "\n".join(lines)


def plan_block_ip(ip: str, rationale: str = "") -> ContainmentPlan:
    """Plan a temporary iptables INPUT drop for one IPv4 address."""
    ip = ip.strip()
    if not is_valid_ipv4(ip):
        raise ValueError(f"not a valid IPv4 address: {ip!r}")
    if ip.startswith("127.") or ip in ("0.0.0.0", "255.255.255.255"):
        raise ValueError(f"refusing to block special address: {ip}")
    return ContainmentPlan(
        action="block_ip",
        target=ip,
        commands=[["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"]],
        rationale=rationale
        or "operator-confirmed hostile source; temporary INPUT drop",
        reversible=True,
    )


def plan_terminate_process(pid: int, rationale: str = "") -> ContainmentPlan:
    """Plan a SIGTERM to one PID. Defensive only — the operator names it."""
    if not isinstance(pid, int) or pid <= 1:
        raise ValueError(f"refusing to terminate pid: {pid!r}")
    return ContainmentPlan(
        action="terminate_process",
        target=str(pid),
        commands=[["kill", "-TERM", str(pid)]],
        rationale=rationale or "operator-confirmed malicious process",
        reversible=False,  # a dead process cannot be un-killed
    )


def apply_plan(plan: ContainmentPlan, confirm: bool = False) -> Dict[str, object]:
    """Execute a plan — ONLY when ``confirm`` is explicitly True.

    Returns a receipt dict (Plan → Preview → Permission → Execute →
    Verify → Receipt). Raises PermissionError when not confirmed.
    """
    if not confirm:
        raise PermissionError(
            "containment requires explicit human confirmation "
            "(pass confirm=True after reviewing plan.preview())"
        )
    receipt: Dict[str, object] = {
        "action": plan.action,
        "target": plan.target,
        "executed": [],
        "verified": False,
    }
    executed = []
    for cmd in plan.commands:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            executed.append(
                {
                    "cmd": " ".join(cmd),
                    "rc": proc.returncode,
                    "stderr": proc.stderr.strip()[-200:],
                }
            )
        except (OSError, subprocess.SubprocessError) as exc:
            executed.append({"cmd": " ".join(cmd), "rc": None, "error": str(exc)[:200]})
    receipt["executed"] = executed
    receipt["verified"] = all(
        isinstance(item, dict) and item.get("rc") == 0 for item in executed
    )
    return receipt
