"""LEVI-native chain composition — compressed engines, linked.

A chain is an ordered list of :class:`Link`. Each link wraps a plain
callable and declares a :class:`RiskBand`:

- ``SAFE`` — no side effects; runs straight through.
- ``CONSEQUENTIAL`` — walks the standing rail in code::

      Plan -> Preview -> Permission -> Execute -> Verify -> Receipt

  A consequential link **cannot execute without a recorded permission
  token** (:func:`grant`, or a runtime ``grantor`` callback). Denied
  links stop the chain fail-closed; every execution — safe or
  consequential, success or failure — emits a link receipt to the
  append-only ledger (see :mod:`levi.chain.store`).

Chains compose *compressed engines* (model, parser, tool, memory — the
skills-library warehouse) into one honest pipeline, e.g.::

      model -> parser -> tool -> memory

Chains build ON ``levi.automation.flows`` (node-graph foundations) —
:class:`ChainError` subclasses ``FlowError``, and :func:`flow_link`
embeds a validated flow as a single chain link — without duplicating it.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..automation.flows import FlowError, build_flow, run_flow
from . import store as _store

__all__ = [
    "RAIL",
    "SAFE_RAIL",
    "Chain",
    "ChainError",
    "ChainReceipt",
    "Link",
    "LinkReceipt",
    "PermissionToken",
    "RiskBand",
    "build_chain",
    "chain_home",
    "flow_link",
    "grant",
    "link",
    "permissions_path",
    "read_permissions",
    "read_receipts",
    "receipts_path",
    "run_chain",
]

#: The full standing rail — mandatory for consequential links.
RAIL: Tuple[str, ...] = (
    "plan",
    "preview",
    "permission",
    "execute",
    "verify",
    "receipt",
)
#: The rail for safe links: identical minus the permission gate.
SAFE_RAIL: Tuple[str, ...] = ("plan", "preview", "execute", "verify", "receipt")

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")


class ChainError(FlowError):
    """Deny-closed: a malformed chain, a denied link, or a failed link
    is refused loudly — never half-run, never silently skipped."""


class RiskBand(str, Enum):
    """A link's declared blast radius.

    - ``SAFE``: pure computation, no side effects. Runs straight through.
    - ``CONSEQUENTIAL``: can change the world. Must walk the full rail,
      including a recorded permission token, before it may execute.
    """

    SAFE = "safe"
    CONSEQUENTIAL = "consequential"


@dataclass(frozen=True)
class Link:
    """One chain step: a named callable with a declared risk band.

    ``fn`` takes the previous link's output and returns the next value.
    ``verifier`` (optional) is called on the output during the verify
    stage; a falsy return (or an exception) fails the link.
    """

    name: str
    fn: Callable[[Any], Any]
    risk: RiskBand = RiskBand.SAFE
    label: str = ""
    describe: str = ""
    verifier: Optional[Callable[[Any], bool]] = None


def link(
    name: Optional[str] = None,
    risk: RiskBand = RiskBand.SAFE,
    label: str = "",
    describe: str = "",
    verifier: Optional[Callable[[Any], bool]] = None,
) -> Callable[[Callable[[Any], Any]], Link]:
    """Decorator turning a plain function into a :class:`Link`."""

    def deco(fn: Callable[[Any], Any]) -> Link:
        return Link(
            name=name or fn.__name__,
            fn=fn,
            risk=RiskBand(risk),
            label=label or fn.__name__,
            describe=describe,
            verifier=verifier,
        )

    return deco


@dataclass(frozen=True)
class PermissionToken:
    """A recorded grant for a consequential link to execute.

    ``link_name`` is an exact link name or ``"*"``; ``scope`` is a chain
    id or ``"*"``. Tokens are minted by :func:`grant` (recorded in the
    permission ledger) or by a runtime ``grantor`` callback, and each use
    is stamped onto the link's receipt.
    """

    token_id: str
    link_name: str
    granted_by: str
    scope: str
    ts: str
    note: str = ""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def grant(
    link_name: str,
    *,
    by: str = "keeper",
    scope: str = "*",
    note: str = "",
    home: "str | None" = None,
) -> PermissionToken:
    """Mint and *record* a permission token for a consequential link.

    The token is appended to the permission ledger (owner-only, 0600)
    before it is returned — a token only exists once it is recorded.
    """
    if not link_name:
        raise ChainError("grant: link_name must not be empty")
    token = PermissionToken(
        token_id=f"perm-{uuid.uuid4().hex[:12]}",
        link_name=link_name,
        granted_by=by,
        scope=scope,
        ts=_utcnow(),
        note=note,
    )
    _store.append_permission(asdict(token), home)
    return token


#: A runtime grantor: asked during the permission stage with the link,
#: its plan, and its preview. Returns a token to approve, None to deny.
Grantor = Callable[[Link, str, str], Optional[PermissionToken]]


@dataclass
class Chain:
    """An ordered composition of links: engine_1 -> engine_2 -> ..."""

    id: str
    name: str
    links: Tuple[Link, ...]
    description: str = ""


def _check_id(value: str, kind: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ChainError(
            f"invalid {kind} id {value!r}: 1-64 chars of [A-Za-z0-9_.-], starting alnum"
        )
    return value


def _coerce_link(raw: Any) -> Link:
    if isinstance(raw, Link):
        link_obj = raw
    elif isinstance(raw, dict):
        try:
            link_obj = Link(
                name=raw["name"],
                fn=raw["fn"],
                risk=RiskBand(raw.get("risk", RiskBand.SAFE)),
                label=str(raw.get("label", raw.get("name", ""))),
                describe=str(raw.get("describe", "")),
                verifier=raw.get("verifier"),
            )
        except (KeyError, ValueError) as exc:
            raise ChainError(f"bad link dict: {exc}") from exc
    else:
        raise ChainError(f"chain links must be Link or dict, got {type(raw).__name__}")
    _check_id(link_obj.name, "link")
    if not callable(link_obj.fn):
        raise ChainError(f"link {link_obj.name!r}: fn is not callable")
    if link_obj.verifier is not None and not callable(link_obj.verifier):
        raise ChainError(f"link {link_obj.name!r}: verifier is not callable")
    return link_obj


def build_chain(
    links: List[Any],
    id: str,
    name: str = "",
    description: str = "",
) -> Chain:
    """Validate and assemble a chain. Deny-closed: duplicate link names,
    uncallable fns, bad risk bands, or an empty link list are refused."""
    chain_id = _check_id(id, "chain")
    if not isinstance(links, list) or not links:
        raise ChainError("chain needs a non-empty 'links' list")
    norm = [_coerce_link(raw) for raw in links]
    seen = set()
    for link_obj in norm:
        if link_obj.name in seen:
            raise ChainError(f"duplicate link name {link_obj.name!r}")
        seen.add(link_obj.name)
    return Chain(
        id=chain_id,
        name=name or chain_id,
        links=tuple(norm),
        description=description,
    )


# ---------------------------------------------------------------------------
# Receipts
# ---------------------------------------------------------------------------


@dataclass
class LinkReceipt:
    """The immutable record of one link's run along its rail."""

    run_id: str
    link_name: str
    risk: str
    label: str
    rail: Tuple[str, ...]
    plan: str
    preview: str
    permission_token_id: Optional[str]
    executed: bool
    ok: bool
    output_kind: str
    detail: str
    error: str = ""
    ts: str = ""

    def __post_init__(self) -> None:
        if not self.ts:
            self.ts = _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "link_name": self.link_name,
            "risk": self.risk,
            "label": self.label,
            "rail": list(self.rail),
            "plan": self.plan,
            "preview": self.preview,
            "permission_token_id": self.permission_token_id,
            "executed": self.executed,
            "ok": self.ok,
            "output_kind": self.output_kind,
            "detail": self.detail,
            "error": self.error,
            "ts": self.ts,
        }


@dataclass
class ChainReceipt:
    """The immutable record of one chain run: every link receipted."""

    run_id: str
    chain_id: str
    chain_name: str
    ok: bool
    output: Any = None
    links: List[LinkReceipt] = field(default_factory=list)
    ts: str = ""

    def __post_init__(self) -> None:
        if not self.ts:
            self.ts = _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "chain_id": self.chain_id,
            "chain_name": self.chain_name,
            "ok": self.ok,
            "output": self.output,
            "ts": self.ts,
            "links": [r.to_dict() for r in self.links],
        }

    def render(self) -> str:
        lines = [
            f"chain receipt {self.run_id} — {self.chain_name} ({self.chain_id})",
            f"links: {len(self.links)} — {'OK' if self.ok else 'FAILED'}",
        ]
        for r in self.links:
            mark = "✓" if r.ok else "✗"
            gate = (
                f"gate:{r.permission_token_id}"
                if r.permission_token_id
                else ("gate:none" if r.risk == "consequential" else "gate:n/a")
            )
            lines.append(f"  {mark} [{r.risk}] {r.link_name} {gate} — {r.detail}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Permission resolution
# ---------------------------------------------------------------------------


def _token_matches(token: PermissionToken, link: Link, chain_id: str) -> bool:
    return (token.link_name in (link.name, "*")) and (token.scope in (chain_id, "*"))


def _resolve_permission(
    link: Link,
    chain_id: str,
    permissions: List[PermissionToken],
    grantor: Optional[Grantor],
    plan: str,
    preview: str,
    home: "str | None",
) -> Optional[PermissionToken]:
    """Find a recorded token for this link. Order: explicit permissions,
    then the runtime grantor (its grant is recorded on the spot), then
    the on-disk permission ledger. None means denied."""
    for token in permissions:
        if _token_matches(token, link, chain_id):
            return token
    if grantor is not None:
        token = grantor(link, plan, preview)
        if token is not None:
            if not _token_matches(token, link, chain_id):
                return None
            _store.append_permission(asdict(token), home)
            return token
        return None
    for record in _store.read_permissions(home):
        try:
            token = PermissionToken(
                **{
                    k: record[k]
                    for k in (
                        "token_id",
                        "link_name",
                        "granted_by",
                        "scope",
                        "ts",
                        "note",
                    )
                }
            )
        except (KeyError, TypeError):
            continue
        if _token_matches(token, link, chain_id):
            return token
    return None


def _kind_of(value: Any) -> str:
    if value is None:
        return "none"
    name = type(value).__name__
    if name in ("str", "int", "float", "bool"):
        return f"{name}:{str(value)[:60]}"
    if isinstance(value, (list, tuple)):
        return f"{name}[{len(value)}]"
    if isinstance(value, dict):
        return f"dict[{len(value)}]"
    return name


# ---------------------------------------------------------------------------
# Execution — consequential links walk the full rail in code
# ---------------------------------------------------------------------------


def _run_link(
    run_id: str,
    chain: Chain,
    link_obj: Link,
    value: Any,
    permissions: List[PermissionToken],
    grantor: Optional[Grantor],
    home: "str | None",
) -> Tuple[Any, LinkReceipt]:
    consequential = link_obj.risk is RiskBand.CONSEQUENTIAL
    rail = RAIL if consequential else SAFE_RAIL

    # PLAN
    plan = (
        link_obj.describe
        or (
            (link_obj.fn.__doc__ or "").strip().splitlines()[0]
            if getattr(link_obj.fn, "__doc__", None)
            else ""
        )
        or f"run {link_obj.fn.__name__}"
    )
    # PREVIEW
    preview = (
        f"{link_obj.name}: input {_kind_of(value)} -> "
        f"{'WORLD-EFFECT possible' if consequential else 'pure compute'}"
    )

    # PERMISSION — the gate. Consequential links cannot pass without a
    # recorded permission token. Fail-closed: no token, no execution.
    token: Optional[PermissionToken] = None
    if consequential:
        token = _resolve_permission(
            link_obj, chain.id, permissions, grantor, plan, preview, home
        )
        if token is None:
            receipt = LinkReceipt(
                run_id=run_id,
                link_name=link_obj.name,
                risk=link_obj.risk.value,
                label=link_obj.label,
                rail=rail,
                plan=plan,
                preview=preview,
                permission_token_id=None,
                executed=False,
                ok=False,
                output_kind="none",
                detail="permission denied: no recorded token — nothing executed",
            )
            _store.append_receipt(receipt.to_dict(), home)
            return value, receipt

    # EXECUTE
    try:
        out = link_obj.fn(value)
    except Exception as exc:  # noqa: BLE001 — fail-closed, recorded
        receipt = LinkReceipt(
            run_id=run_id,
            link_name=link_obj.name,
            risk=link_obj.risk.value,
            label=link_obj.label,
            rail=rail,
            plan=plan,
            preview=preview,
            permission_token_id=token.token_id if token else None,
            executed=True,
            ok=False,
            output_kind="none",
            detail=f"execute failed: {type(exc).__name__}",
            error=str(exc)[:500],
        )
        _store.append_receipt(receipt.to_dict(), home)
        return value, receipt

    # VERIFY
    verified = True
    verify_note = f"output {_kind_of(out)}"
    if link_obj.verifier is not None:
        try:
            verified = bool(link_obj.verifier(out))
        except Exception as exc:  # noqa: BLE001 — a broken verifier fails closed
            verified = False
            verify_note = f"verifier raised {type(exc).__name__}: {exc}"
        if not verified and "verifier raised" not in verify_note:
            verify_note = f"verifier rejected output {_kind_of(out)}"

    # RECEIPT — every execution is recorded, success or failure.
    receipt = LinkReceipt(
        run_id=run_id,
        link_name=link_obj.name,
        risk=link_obj.risk.value,
        label=link_obj.label,
        rail=rail,
        plan=plan,
        preview=preview,
        permission_token_id=token.token_id if token else None,
        executed=True,
        ok=verified,
        output_kind=_kind_of(out),
        detail=("verified: " if verified else "VERIFY FAILED: ") + verify_note,
    )
    _store.append_receipt(receipt.to_dict(), home)
    return out, receipt


def run_chain(
    chain: Chain,
    data: Any,
    *,
    permissions: Optional[List[PermissionToken]] = None,
    grantor: Optional[Grantor] = None,
    home: "str | None" = None,
) -> ChainReceipt:
    """Run a chain: thread the value through each link, in order.

    Safe links run straight through. Consequential links walk the full
    rail — without a recorded permission token (via ``permissions``,
    the ``grantor`` callback, or the on-disk ledger) the link is denied
    and the chain stops fail-closed. Every link execution emits a link
    receipt to the append-only ledger.
    """
    if not isinstance(chain, Chain):
        raise ChainError("run_chain: chain must be built by build_chain()")
    run_id = f"chain-{uuid.uuid4().hex[:12]}"
    tokens = list(permissions or [])
    value = data
    receipts: List[LinkReceipt] = []
    ok = True
    for link_obj in chain.links:
        value, receipt = _run_link(
            run_id, chain, link_obj, value, tokens, grantor, home
        )
        receipts.append(receipt)
        if not receipt.ok:
            ok = False
            break  # fail-closed: a denied or failed link stops the chain
    return ChainReceipt(
        run_id=run_id,
        chain_id=chain.id,
        chain_name=chain.name,
        ok=ok,
        output=value if ok else None,
        links=receipts,
    )


# ---------------------------------------------------------------------------
# Flow embedding — chains build ON flows.py, they don't duplicate it
# ---------------------------------------------------------------------------


def flow_link(
    flow: Dict[str, Any],
    *,
    name: Optional[str] = None,
    label: str = "",
    risk: RiskBand = RiskBand.CONSEQUENTIAL,
    dry_run: bool = True,
    describe: str = "",
) -> Link:
    """Embed a validated flow definition as a single chain link.

    The flow is validated by ``levi.automation.flows.build_flow`` and run
    by ``run_flow`` (deny-closed, dry-run default); the chain rail wraps
    it — consequential by default, so the flow still needs a recorded
    permission token to execute. The link's output is the flow's
    :class:`FlowReceipt`.
    """
    flow_def = build_flow(flow)  # re-validated: never link an unchecked graph
    flow_name = name or flow_def["id"]

    def _run(value: Any) -> Any:
        return run_flow(
            flow_def,
            dry_run=dry_run,
            context={"chain_input": value},
        )

    _run.__doc__ = f"run flow {flow_def['id']} ({flow_def['name']})"
    return Link(
        name=flow_name,
        fn=_run,
        risk=RiskBand(risk),
        label=label or flow_def["name"],
        describe=describe
        or f"embedded flow '{flow_def['id']}' ({len(flow_def['nodes'])} nodes)",
    )


# Re-exported store helpers (public, documented).
chain_home = _store.chain_home
receipts_path = _store.receipts_path
permissions_path = _store.permissions_path
read_receipts = _store.read_receipts
read_permissions = _store.read_permissions
