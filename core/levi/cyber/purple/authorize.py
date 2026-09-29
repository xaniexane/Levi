"""Authorization gate for purple-team exercises. Default-deny.

An exercise runs only against a system Chauncey explicitly authorized.
No authorization record, no run — no exceptions. Denials are receipted
by the caller (see exercise.py), so probe attempts leave an audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass


KEEPER = "keeper"  # Chauncey. Only he authorizes adversary emulation.


class AuthorizationDenied(Exception):
    """Raised when an exercise is not authorized. Carries the reason."""


@dataclass(frozen=True)
class Authorization:
    """One signed authorization to emulate against a target.

    target_id: exact system identifier, e.g. "levi-lab-host-01".
    scenario_ids: which scripted scenarios may run under this grant.
    not_before / not_after: epoch window the grant is valid for.
    authorizer: must be KEEPER ("keeper").
    revoked: kill-switch for the grant itself; revoked grants deny.
    """

    auth_id: str
    target_id: str
    scenario_ids: tuple[str, ...]
    not_before: int
    not_after: int
    authorizer: str = KEEPER
    revoked: bool = False


class AuthorizationStore:
    """In-memory grant registry. Grants are added by the keeper's tooling."""

    def __init__(self) -> None:
        self._grants: dict[str, Authorization] = {}

    def add(self, auth: Authorization) -> None:
        if auth.auth_id in self._grants:
            raise ValueError(f"duplicate auth_id: {auth.auth_id}")
        self._grants[auth.auth_id] = auth

    def revoke(self, auth_id: str) -> None:
        try:
            grant = self._grants[auth_id]
        except KeyError:
            raise AuthorizationDenied(f"unknown auth_id: {auth_id}") from None
        self._grants[auth_id] = Authorization(
            auth_id=grant.auth_id,
            target_id=grant.target_id,
            scenario_ids=grant.scenario_ids,
            not_before=grant.not_before,
            not_after=grant.not_after,
            authorizer=grant.authorizer,
            revoked=True,
        )

    def get(self, auth_id: str) -> Authorization:
        try:
            return self._grants[auth_id]
        except KeyError:
            raise AuthorizationDenied(f"unknown auth_id: {auth_id}") from None


def check(
    store: AuthorizationStore,
    auth_id: str,
    target_id: str,
    scenario_id: str,
    now: int,
) -> Authorization:
    """Validate a run against the gate. Returns the grant or raises.

    Deny reasons, in check order: unknown grant, revoked grant,
    non-keeper authorizer, target mismatch, scenario out of scope,
    window violation. Default-deny: anything not explicitly allowed fails.
    """
    grant = store.get(auth_id)
    if grant.revoked:
        raise AuthorizationDenied(f"grant {auth_id} revoked")
    if grant.authorizer != KEEPER:
        raise AuthorizationDenied(
            f"grant {auth_id} not keeper-authorized (authorizer={grant.authorizer!r})"
        )
    if grant.target_id != target_id:
        raise AuthorizationDenied(
            f"grant {auth_id} is for target {grant.target_id!r}, not {target_id!r}"
        )
    if scenario_id not in grant.scenario_ids:
        raise AuthorizationDenied(
            f"scenario {scenario_id!r} outside grant {auth_id} scope"
        )
    if not (grant.not_before <= now <= grant.not_after):
        raise AuthorizationDenied(
            f"grant {auth_id} window [{grant.not_before},{grant.not_after}] "
            f"does not cover now={now}"
        )
    return grant
