"""Platform API router — internal routes first-class, external by special request.

Doctrine (binding): the platform should not need outside providers.
Internal LEVI organs and services are the default address space; an
external provider or asset is NEVER routed by default and is NEVER
auto-discovered. Each external route is a deliberate, periodically
reviewed special-request addition carrying ``provider``, ``scope``,
``approved_by``, ``reason``, and ``added_at`` — and every external
crossing is marked and audit-logged (metadata only).

Relationship to ``gateway.route_external``: the router is the route /
address table (control plane); the gateway mints short-lived routing
grants. ``resolve()`` refuses unregistered external destinations before
any grant machinery is even consulted.

Stdlib-only, no network. All state under ``~/.levi/cybrus/``
(``LEVI_HOME`` override honored).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional


def _paths():  # noqa: D103 - private helper, same rationale as gateway.py
    try:
        from levi.cybrus import _paths as _p

        return _p
    except ImportError:
        import importlib.util
        from pathlib import Path

        spec = importlib.util.spec_from_file_location(
            "levi.cybrus._paths.standalone",
            Path(__file__).resolve().parent / "_paths.py",
        )
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError("cybrus _paths helper unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


#: Store holding the deliberate external-route additions.
_EXTERNAL_STORE = "routes_external"

_NAME_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_name(value: str, what: str) -> str:
    if not isinstance(value, str) or not value:
        raise RouteError(f"{what} must be a non-empty string")
    if len(value) > 128 or value[0] in "._-" or not set(value) <= _NAME_CHARS:
        raise RouteError(
            f"invalid {what} {value!r}: 1-128 chars of [A-Za-z0-9._-], "
            "not starting with . _ or -"
        )
    return value


def _audit_route(event: str, actor: str, details: Optional[Dict] = None) -> None:
    from levi.cybrus.audit import AuditEngine

    AuditEngine().append(event, str(actor), dict(details or {}))


class RouteError(Exception):
    """Router failures: invalid names, duplicates, unknown routes."""


class RouteRefused(RouteError):
    """An external destination was refused: no deliberate route registered.

    Guidance is part of the error — the fix is a human special-request
    addition, never silent auto-discovery.
    """


#: First-class internal address space: LEVI's own organs and services.
#: Internal matches always win over external ones.
INTERNAL_ROUTES: Dict[str, str] = {
    "levi.cybrus": "security & identity core: vault, tokens, approvals, audit",
    "levi.strategy": "the 48 laws life-formula engine",
    "levi.jobs": "universal job organ: sourcing, scoring, apply queue",
    "levi.monetize": "income organ: pricing, quoting, offline tools",
    "levi.brain": "LEVI's native trained brain",
    "levi.growth": "growth loop: harvest, reflect, consolidate, journal",
    "levi.social": "social platform organs",
    "levi.king": "King control plane",
    "levi.finance": "finance domain (paper/simulated)",
    "levi.dream": "nightly dream engine",
    "levi.daemon": "always-on daemon layer",
    "levi.chain": "Plan-Preview-Permission-Execute-Verify-Receipt chains",
    "levi.automation": "automation minions",
    "levi.knowledge": "knowledge/news corpus",
    "levi.academy": "academy / boot camp sessions",
    "levi.cortex": "skill and education library",
    "levi.oracle": "strategic weighting and teaching",
    "levi.nexus": "coordination and QID addressing",
    "levi.eli": "orchestration and logic routing",
    "levi.uniforge": "evolution, repair and upgrades",
    "levi.omnipulse": "lifecycle engine",
    "levi.cyberpulse": "organism telemetry",
    "levi.hypercube": "dimensional projection matrix",
    "levi.vector": "safe simulation",
    "levi.ser18": "world model, recursion shells and limits",
}


class RouteRegistry:
    """The platform route table.

    Internal routes are built in and always resolvable. External routes
    exist only as deliberate additions via :meth:`add_external`, each
    carrying its approval provenance. :meth:`resolve` prefers internal
    matches and refuses unregistered external destinations outright.
    """

    def __init__(self):
        self._internal: Dict[str, str] = dict(INTERNAL_ROUTES)

    # -- internal --------------------------------------------------------

    def register_internal(self, name: str, description: str) -> None:
        """Add a first-class internal route (in-memory for this process)."""
        name = _sanitize_name(name, "internal route name")
        if not isinstance(description, str) or not description.strip():
            raise RouteError("description must be a non-empty string")
        self._internal[name] = description.strip()

    def internal_routes(self) -> List[Dict]:
        """All first-class internal routes, sorted."""
        return [
            {"name": name, "description": desc, "kind": "internal"}
            for name, desc in sorted(self._internal.items())
        ]

    # -- external (deliberate additions only) -----------------------------

    def _load_external(self) -> Dict[str, dict]:
        data = _paths().load_json_store(_paths().store_path(_EXTERNAL_STORE))
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise RouteError("external route store is corrupt (not a dict)")
        return data

    def _save_external(self, data: Dict[str, dict]) -> None:
        p = _paths()
        path = p.store_path(_EXTERNAL_STORE)
        with p.store_lock(path):
            p.save_json_store(path, data)

    def add_external(
        self,
        provider: str,
        *,
        scope: str,
        approved_by: str,
        reason: str,
    ) -> dict:
        """Register an external provider as a special-request addition.

        All four fields are required — there is no default, no discovery,
        no silent add. Raises :class:`RouteError` when the provider is
        already registered (use remove + re-add to change it).
        """
        provider = _sanitize_name(provider, "provider")
        scope = _sanitize_name(scope, "scope")
        approved_by = _sanitize_name(approved_by, "approved_by")
        if not isinstance(reason, str) or not reason.strip():
            raise RouteError("reason must be a non-empty string")
        reason = reason.strip()
        if len(reason) > 500:
            raise RouteError("reason must be at most 500 chars")
        p = _paths()
        path = p.store_path(_EXTERNAL_STORE)
        with p.store_lock(path):
            data = self._load_external()
            if provider in data and data[provider].get("status") == "active":
                raise RouteError(
                    f"external route {provider!r} already registered "
                    "(remove it first to change it)"
                )
            record = {
                "provider": provider,
                "scope": scope,
                "approved_by": approved_by,
                "reason": reason,
                "added_at": _utcnow_iso(),
                "status": "active",
                "crosses_boundary": True,
            }
            data[provider] = record
            p.save_json_store(path, data)
        _audit_route(
            "route.external.added",
            approved_by,
            {"provider": provider, "scope": scope, "reason": reason},
        )
        return record

    def remove_external(self, provider: str, *, by: str) -> None:
        """Decommission an external route. The record is kept with
        ``status: removed`` for the audit trail."""
        provider = _sanitize_name(provider, "provider")
        by = _sanitize_name(by, "by")
        p = _paths()
        path = p.store_path(_EXTERNAL_STORE)
        with p.store_lock(path):
            data = self._load_external()
            record = data.get(provider)
            if record is None or record.get("status") != "active":
                raise RouteError(f"no active external route {provider!r}")
            record["status"] = "removed"
            record["removed_at"] = _utcnow_iso()
            record["removed_by"] = by
            p.save_json_store(path, data)
        _audit_route("route.external.removed", by, {"provider": provider})

    def external_routes(self, *, include_removed: bool = False) -> List[dict]:
        """Registered external routes with their approval provenance."""
        out = []
        for provider in sorted(self._load_external()):
            record = self._load_external()[provider]
            if record.get("status") != "active" and not include_removed:
                continue
            out.append(dict(record, kind="external"))
        return out

    def list_routes(self) -> dict:
        """The whole table: internal first-class routes, then the
        deliberate external additions — every external entry flagged as
        a boundary crossing."""
        return {
            "internal": self.internal_routes(),
            "external": self.external_routes(),
        }

    # -- resolution -------------------------------------------------------

    def _match_internal(self, target: str) -> Optional[str]:
        for name in self._internal:
            if target == name or target.startswith(name + "."):
                return name
        return None

    def resolve(self, target: str) -> dict:
        """Resolve ``target`` to a route decision.

        Internal matches win (doctrine: the platform serves itself first).
        External destinations resolve only when deliberately registered and
        active — and the decision is flagged ``crosses_boundary`` and
        audit-logged. Anything else raises :class:`RouteRefused`.
        """
        if not isinstance(target, str) or not target.strip():
            raise RouteError("target must be a non-empty string")
        target = target.strip()

        internal = self._match_internal(target)
        if internal is not None:
            return {
                "kind": "internal",
                "target": target,
                "route": internal,
                "description": self._internal[internal],
                "crosses_boundary": False,
            }

        provider = target.split(".")[0].split("/")[0].split(":")[0]
        try:
            clean = _sanitize_name(provider, "provider")
        except RouteError:
            raise RouteRefused(
                f"refusing route to {target!r}: not an internal route and "
                "not a registrable external provider name"
            ) from None
        record = self._load_external().get(clean)
        if record is None or record.get("status") != "active":
            raise RouteRefused(
                f"refusing route to {target!r}: no external route registered. "
                "External providers are special-request additions only — "
                "register one deliberately with: "
                "levi cybrus route add-external <provider> "
                "--scope <scope> --by <approver> --reason <reason>"
            )
        _audit_route(
            "route.crossing",
            "router",
            {"target": target, "provider": clean, "scope": record["scope"]},
        )
        return {
            "kind": "external",
            "target": target,
            "route": clean,
            "scope": record["scope"],
            "approved_by": record["approved_by"],
            "crosses_boundary": True,
        }
