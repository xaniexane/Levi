"""External payment rail plug-ins — `rails.py` (spec §8).

The honesty boundary made executable. Real money movement (Stripe,
bank transfer, cash) lives in LABELED EXTERNAL plug-ins — references,
never core. This module is the registry of those references: the core
records *that* a settlement cleared through rail X, never the payment
itself.

LAWS (machine-checked by `check_laws`):
- L1: rail registry entries are references only — name, label,
  operator instructions. No credentials, no account numbers, no keys,
  ever.
- L2: `pay.settle` accepts only registered rail names; an unregistered
  rail is refused.
- L3: declaring a rail requires a named human operator and is logged
  to the decisions stream.
"""

from __future__ import annotations

import re
from typing import Any

from .store import Store

_BANNED = re.compile(
    r"key|secret|token|password|account.?number|routing|iban|ssn",
    re.IGNORECASE,
)


def declared_rails(store: Store) -> list[dict[str, Any]]:
    """The registry: operator-configured rails + stream registrations."""
    from . import policies as policies_mod

    policies = policies_mod.load_policies(store)
    rails = {r["name"]: dict(r) for r in policies.get("external_rails", [])}
    for reg in store.read_all("rail_registrations"):
        rails[reg["name"]] = {
            "name": reg["name"],
            "label": reg["label"],
            "instructions": reg.get("instructions", ""),
            "declared_by": reg.get("declared_by"),
        }
    return list(rails.values())


def assert_rail(store: Store, name: str) -> dict[str, Any]:
    """Refuse unknown rails. Called by `pay.settle` (law L2)."""
    rails = {r["name"]: r for r in declared_rails(store)}
    if name not in rails:
        raise ValueError(
            f"rail {name!r} is not a registered external plug-in "
            f"(known: {sorted(rails)}). Declare it first — the ledger "
            "records labeled references, never ad-hoc money movement."
        )
    return rails[name]


def declare_rail(
    store: Store,
    name: str,
    label: str,
    instructions: str,
    operator: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Register an external rail plug-in as a labeled reference."""
    if not operator:
        raise ValueError("declare_rail requires a named human operator (law L3)")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
        raise ValueError(f"rail name {name!r} must be lowercase slug-safe")
    if _BANNED.search(instructions) or _BANNED.search(label):
        raise ValueError(
            "rail registry entries are references only — no credentials, "
            "account numbers, keys, or secrets (law L1)"
        )
    existing = {r["name"] for r in declared_rails(store)}
    if name in existing:
        raise ValueError(f"rail {name!r} is already registered")
    reg = store.append(
        "rail_registrations",
        {
            "name": name,
            "label": label,
            "instructions": instructions,
            "declared_by": operator,
        },
        now=now,
    )
    store.append(
        "decisions",
        {"kind": "rail_declared", "name": name, "operator": operator},
        now=now,
    )
    return reg


def check_laws(store: Store) -> dict[str, Any]:
    """Machine-check the rail laws against live state."""
    checks: dict[str, dict] = {}
    bad = [
        r["name"]
        for r in declared_rails(store)
        if _BANNED.search(r.get("instructions", ""))
        or _BANNED.search(r.get("label", ""))
    ]
    checks["no_secrets_in_registry"] = {"ok": not bad, "violations": bad}
    # L2: every recorded settlement's rail is registered.
    known = {r["name"] for r in declared_rails(store)}
    latest: dict[str, dict] = {}
    for s in store.read_all("settlements"):
        latest[s["id"]] = s
    unknown = [s["id"] for s in latest.values() if s.get("rail") not in known]
    checks["settlements_use_registered_rails"] = {
        "ok": not unknown,
        "violations": unknown,
    }
    return {"ok": all(c["ok"] for c in checks.values()), "checks": checks}
