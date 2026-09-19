"""LEVI-native node-graph workflows — the n8n-like, rebuilt on the rail.

Flows are node graphs executed ON TOP of the existing automation engine —
never a fork of it. Every ``minion`` node runs through the standing rail::

    Plan -> Preview -> Permission -> Execute -> Verify -> Receipt

via :func:`levi.automation.engine.run_minion`, so each node produces a
real engine receipt and the flow run produces a flow receipt over them.

A flow is plain data (JSON under ``<LEVI_HOME>/automation/flows/``)::

    {
      "id": "morning-brief",
      "name": "Morning brief",
      "start": "digest",
      "nodes": [
        {"id": "digest", "kind": "minion", "minion_id": "productivity-email-digest-01",
         "label": "Overnight email digest"},
        {"id": "ok?", "kind": "predicate", "expr": "digest.ok", "label": "digest ok?"},
        {"id": "ship", "kind": "minion", "minion_id": "...", "label": "Ship it"}
      ],
      "edges": [
        {"id": "e1", "from": "digest", "to": "ok?"},
        {"id": "e2", "from": "ok?", "to": "ship", "when": "ok?.passed"}
      ]
    }

Node kinds:

- ``minion``    — wraps a catalog minion (``minion_id``); full rail, receipted.
- ``trigger``   — entry node: ``config`` with ``trigger_type`` of
  ``webhook-in`` | ``schedule`` | ``manual`` | ``event``. Flow runs start here.
- ``branch``    — evaluates ``expr`` (boolean), routes to ``true``/``false``
  labeled edges. Plain ``when`` edges still evaluate as before.
- ``approval``  — HITL node: builds a GateRequest and calls the run's
  responder. Denial raises GateDenied; the flow stops with a denied receipt.
  Never auto-approves in live mode.
- ``predicate`` — evaluates ``expr`` against the run context; records
  ``passed``. No side effects.
- ``emit``      — evaluates ``set`` (path -> expr) into the run context.
  No side effects.
- ``note``      — annotates the run log. No side effects.
- ``webhook-out``, ``python``, ``macro``, ``google-tasks``, ``google-sheets``
  — action kinds. Registry slots and gated rail routing live here; the
  actual handlers come from the node-pack modules (``.nodes``,
  ``.google_nodes``), loaded lazily by :func:`ensure_builtin_nodes`.

New kinds register through :func:`register_node_kind` — handler contract::

    handle(node: dict, ctx: dict, run: dict) -> dict
        # {"ok": bool, "output": dict, "evidence": str} or raise FlowError
    preview(node: dict) -> str   # what the node WOULD do (dry-run planning)

:func:`plan_flow` renders the full "here is what would happen" before
execution; every run (dry or live) logs the plan first on its receipt.
:func:`dispatch_trigger` scans saved flows for matching ``trigger`` nodes
(webhook-in path match, schedule cron match, manual/event kind match) and
starts a run per match. :func:`validate_flow` is the strict JSON-schema
validator (deny-closed); :func:`build_flow` keeps the legacy permissive
contract so existing graphs keep running.

Edges carry an optional ``when`` expression; only matching edges are
traversed. Runs are dry-run by default: ``minion`` nodes simulate and
record what *would* happen. Live execution (``dry_run=False``) is an
explicit per-run choice and still gates every node.

The graph is visualizable as data — :func:`manifest` returns nodes with
deterministic layered positions plus edges, and :func:`to_mermaid`
renders a Mermaid flowchart string. No GUI is built; the manifest is the
renderable artifact.

Deny-closed: unknown node references, unresolvable minions, bad
expressions, and runaway loops are refused with :class:`FlowError` —
never silently skipped.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .engine import Receipt, TriggerEvent, _cron_matches, run_minion
from .hitl import (
    Gate,
    GateDenied,
    GateKind,
    GateRequest,
    GateResult,
    Responder,
    auto_approve,
    gate_kind_for,
)
from .minions import MINIONS, Minion, find_minion

__all__ = [
    "FlowError",
    "FlowReceipt",
    "NodeRecord",
    "build_flow",
    "validate_flow",
    "register_node_kind",
    "ensure_builtin_nodes",
    "plan_flow",
    "dispatch_trigger",
    "run_flow",
    "manifest",
    "to_mermaid",
    "save_flow",
    "load_flow",
    "list_flows",
    "delete_flow",
    "flows_home",
    "evaluate_expr",
    "GateDenied",
]

NODE_KINDS = ("minion", "trigger", "branch", "approval", "predicate", "emit", "note")
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
_MAX_VISITS_PER_NODE = 50
_MAX_STEPS = 1000


class FlowError(Exception):
    """Deny-closed: a malformed flow or expression is refused, never half-run."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def flows_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    """Resolve ``<LEVI_HOME>/automation/flows`` at call time (hermetic)."""
    if home is not None:
        base = Path(home)
    else:
        override = os.environ.get("LEVI_HOME")
        base = Path(override) if override else Path(os.path.expanduser("~/.levi"))
    return base / "automation" / "flows"


def _check_id(value: str, kind: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise FlowError(
            f"invalid {kind} id {value!r}: 1-64 chars of [A-Za-z0-9_.-], starting alnum"
        )
    return value


# ---------------------------------------------------------------------------
# Node-kind registry — the extension point for node packs
# ---------------------------------------------------------------------------
#
# register_node_kind(kind, handler, preview_fn, action=False)
#
#   handler:   handle(node: dict, ctx: dict, run: dict) -> dict
#              Returns {"ok": bool, "output": dict, "evidence": str}
#              or raises FlowError. ``ctx`` is the live run namespace
#              (mutable); the returned ``output`` is namespaced under the
#              node id after the call. ``run`` carries run_id, flow_id,
#              flow_name, dry_run, and responder.
#   preview_fn: preview(node: dict) -> str
#              What the node WOULD do — used by plan_flow and dry-run planning.
#   action:    when True the node walks the gated action rail
#              (Plan -> Preview -> Permission -> Execute -> Verify -> Receipt)
#              behind a HITL approval gate, and its receipt entry carries
#              node id, preview, gate decision, and evidence. The five
#              node-pack kinds (webhook-out, python, macro, google-tasks,
#              google-sheets) are always action kinds, even when registered
#              with the plain 3-arg contract.

_NODE_REGISTRY: Dict[str, Dict[str, Any]] = {}

# Action kinds whose handlers live in the node-pack modules (built by a
# sibling worker). On first use they are loaded lazily via
# ensure_builtin_nodes(); the packs import from flows, never the reverse
# at top level — no circular imports.
_PACK_KINDS = {
    "webhook-out": "nodes",
    "python": "nodes",
    "macro": "nodes",
    "google-tasks": "google_nodes",
    "google-sheets": "google_nodes",
}


def register_node_kind(
    kind: str,
    handler: Optional[Callable[..., Dict[str, Any]]] = None,
    preview_fn: Optional[Callable[[Dict[str, Any]], str]] = None,
    action: bool = False,
) -> None:
    """Register a node kind (see the registry contract above)."""
    _check_id(kind, "node kind")
    if not callable(handler):
        raise FlowError(f"register_node_kind({kind!r}): handler must be callable")
    if not callable(preview_fn):
        raise FlowError(f"register_node_kind({kind!r}): preview_fn must be callable")
    _NODE_REGISTRY[kind] = {
        "handler": handler,
        "preview_fn": preview_fn,
        # The node-pack action kinds always walk the gated action rail,
        # even when the pack registers with the plain 3-arg contract.
        "action": bool(action) or kind in _PACK_KINDS,
    }
    global NODE_KINDS
    if kind not in NODE_KINDS:
        NODE_KINDS = NODE_KINDS + (kind,)


_builtin_nodes_loaded = False


def ensure_builtin_nodes() -> None:
    """Lazily import the node-pack modules (``.nodes``, ``.google_nodes``).

    Each pack exposes ``register()`` which calls back into
    :func:`register_node_kind`. A genuinely missing pack raises
    ``FlowError("node pack missing: <name>")``; an ImportError raised from
    *inside* a present pack (a broken dependency of its own) propagates
    untouched so the real cause stays visible.
    """
    global _builtin_nodes_loaded
    if _builtin_nodes_loaded:
        return
    for mod in ("nodes", "google_nodes"):
        dotted = f"{__package__}.{mod}"
        try:
            module = importlib.import_module(dotted)
        except ImportError as exc:
            if exc.name in (mod, dotted):
                raise FlowError(f"node pack missing: {mod}") from None
            raise
        register = getattr(module, "register", None)
        if not callable(register):
            raise FlowError(f"node pack {mod!r} has no register() entry point")
        register()
    _builtin_nodes_loaded = True


# -- built-in logic node kinds (trigger / branch / approval) -----------------

_TRIGGER_TYPES = ("webhook-in", "schedule", "manual", "event")


def _trigger_preview(node: Dict[str, Any]) -> str:
    cfg = node.get("config", {}) or {}
    ttype = cfg.get("trigger_type", "?")
    extra = {
        "webhook-in": f"path={cfg.get('path', '?')}",
        "schedule": f"cron='{cfg.get('cron', '?')}'",
        "event": f"event_kind={cfg.get('event_kind', '?')}",
        "manual": "by hand",
    }.get(ttype, "")
    return f"entry: {ttype} trigger {extra}".strip()


def _trigger_handler(
    node: Dict[str, Any], ctx: Dict[str, Any], run: Dict[str, Any]
) -> Dict[str, Any]:
    cfg = node.get("config", {}) or {}
    ttype = cfg.get("trigger_type", "?")
    return {
        "ok": True,
        "output": {"trigger_type": ttype, "config": dict(cfg)},
        "evidence": f"flow entered via {ttype} trigger",
    }


def _branch_preview(node: Dict[str, Any]) -> str:
    return f"evaluate '{node.get('expr', '')}' -> follow the 'true' or 'false' edge"


def _branch_handler(
    node: Dict[str, Any], ctx: Dict[str, Any], run: Dict[str, Any]
) -> Dict[str, Any]:
    nid = node["id"]
    try:
        value = evaluate_expr(node.get("expr", ""), ctx)
    except FlowError as exc:
        raise FlowError(f"branch {nid!r}: {exc}") from exc
    if not isinstance(value, bool):
        raise FlowError(f"branch {nid!r}: expr must be boolean, got {value!r}")
    return {
        "ok": True,
        "output": {"passed": value},
        "evidence": f"branch '{node.get('expr', '')}' -> {value}",
    }


def _approval_preview(node: Dict[str, Any]) -> str:
    cfg = node.get("config", {}) or {}
    return (
        f"HITL gate [{cfg.get('gate_kind', 'approval')}]: "
        f"'{cfg.get('prompt', 'approve?')}' — nothing moves until approved"
    )


def _approval_handler(
    node: Dict[str, Any], ctx: Dict[str, Any], run: Dict[str, Any]
) -> Dict[str, Any]:
    nid = node["id"]
    cfg = node.get("config", {}) or {}
    responder = run["responder"]
    if not run["dry_run"] and responder is auto_approve:
        raise FlowError(
            f"approval node {nid!r}: live mode refuses the dry-run "
            "auto_approve responder — pass a real responder"
        )
    request = GateRequest(
        minion_id=f"flow:{run['flow_id']}:{nid}",
        kind=gate_kind_for(str(cfg.get("gate_kind", "approval"))),
        prompt=str(cfg.get("prompt", "approve?")),
        context={"node_id": nid, "flow_id": run["flow_id"], "dry_run": run["dry_run"]},
    )
    # GateDenied propagates: run_flow catches it and stops the flow with a
    # denied receipt. Nothing is half-executed.
    result = Gate(request).require(responder)
    return {
        "ok": result.ok,
        "output": {"decision": result.decision, "gate_kind": request.kind.value},
        "evidence": f"gate {result.decision}: {result.note or 'no note'}",
    }


register_node_kind("trigger", _trigger_handler, _trigger_preview)
register_node_kind("branch", _branch_handler, _branch_preview)
register_node_kind("approval", _approval_handler, _approval_preview)


# ---------------------------------------------------------------------------
# Expression language (tiny, safe, deny-closed)
# ---------------------------------------------------------------------------
#
#   expr  := or
#   or    := and ("or" and)*
#   and   := not ("and" not)*
#   not   := "not" not | cmp
#   cmp   := arith (("==" | "!=" | ">=" | "<=" | ">" | "<") arith)?
#   arith := term (("+" | "-") term)*
#   term  := unary (("*" | "/") unary)*
#   unary := "-" unary | atom
#   atom  := "(" expr ")" | literal | name
#
# Names are dotted lookups into the namespace (node outputs, ``event``).
# Anything unresolvable or mistyped raises FlowError — never silently False.

_TOKEN_RE = re.compile(
    r"""\s*(?:
      (?P<num>\d+(?:\.\d+)?)
    | (?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
    | (?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)
    | (?P<op>==|!=|>=|<=|>|<|\+|-|\*|/|\(|\))
    )""",
    re.VERBOSE,
)

_KEYWORDS = {"and", "or", "not", "true", "false", "null"}


def _tokenize(expr: str) -> List[Any]:
    if not isinstance(expr, str) or not expr.strip():
        raise FlowError("empty expression")
    tokens: List[Any] = []
    pos = 0
    while pos < len(expr):
        m = _TOKEN_RE.match(expr, pos)
        if not m or m.end() == pos:
            raise FlowError(
                f"bad expression {expr!r}: stuck at {expr[pos : pos + 12]!r}"
            )
        pos = m.end()
        kind = m.lastgroup
        text = m.group(kind).strip()
        if kind == "num":
            tokens.append(float(text) if "." in text else int(text))
        elif kind == "str":
            tokens.append(json.loads(text))
        elif kind == "name":
            if text in ("true", "false", "null"):
                tokens.append({"true": True, "false": False, "null": None}[text])
            elif text in ("and", "or", "not"):
                tokens.append(text.upper())  # keyword marker
            else:
                tokens.append(("name", text))
        else:
            tokens.append(text.strip())
    return tokens


def _resolve(name: str, namespace: Dict[str, Any]) -> Any:
    cur: Any = namespace
    for part in name.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise FlowError(f"expression: unknown name {name!r}")
    return cur


class _Parser:
    def __init__(self, tokens: List[Any], namespace: Dict[str, Any]):
        self.toks = tokens
        self.pos = 0
        self.ns = namespace

    def peek(self) -> Any:
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def next(self) -> Any:
        tok = self.peek()
        self.pos += 1
        return tok

    def parse(self) -> Any:
        val = self._or()
        if self.peek() is not None:
            raise FlowError(f"expression: trailing tokens at {self.peek()!r}")
        return val

    def _or(self) -> Any:
        val = self._and()
        while self.peek() == "OR":
            self.next()
            rhs = self._and()
            val, rhs = self._as_bool(val, "or"), self._as_bool(rhs, "or")
            val = val or rhs
        return val

    def _and(self) -> Any:
        val = self._not()
        while self.peek() == "AND":
            self.next()
            rhs = self._not()
            val, rhs = self._as_bool(val, "and"), self._as_bool(rhs, "and")
            val = val and rhs
        return val

    def _not(self) -> Any:
        if self.peek() == "NOT":
            self.next()
            return not self._as_bool(self._not(), "not")
        return self._cmp()

    def _cmp(self) -> Any:
        left = self._arith()
        op = self.peek()
        if op in ("==", "!=", ">", ">=", "<", "<="):
            self.next()
            right = self._arith()
            return self._compare(op, left, right)
        return left

    def _arith(self) -> Any:
        val = self._term()
        while self.peek() in ("+", "-"):
            op = self.next()
            rhs = self._term()
            val = self._arith_op(op, val, rhs)
        return val

    def _term(self) -> Any:
        val = self._unary()
        while self.peek() in ("*", "/"):
            op = self.next()
            rhs = self._unary()
            val = self._arith_op(op, val, rhs)
        return val

    def _unary(self) -> Any:
        if self.peek() == "-":
            self.next()
            val = self._unary()
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise FlowError(f"expression: unary '-' needs a number, got {val!r}")
            return -val
        return self._atom()

    @staticmethod
    def _arith_op(op: str, left: Any, right: Any) -> Any:
        if (
            isinstance(left, bool)
            or isinstance(right, bool)
            or not isinstance(left, (int, float))
            or not isinstance(right, (int, float))
        ):
            raise FlowError(
                f"expression: '{op}' needs two numbers, got {left!r} and {right!r}"
            )
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if right == 0:
            raise FlowError("expression: division by zero")
        result = left / right
        # Keep ints integral: 6 / 2 -> 3, not 3.0 (honest types).
        return int(result) if float(result).is_integer() else result

    def _atom(self) -> Any:
        tok = self.next()
        if tok == "(":
            val = self._or()
            if self.next() != ")":
                raise FlowError("expression: missing closing ')'")
            return val
        if isinstance(tok, tuple) and tok[0] == "name":
            return _resolve(tok[1], self.ns)
        if isinstance(tok, str) and tok in ("AND", "OR", "NOT"):
            raise FlowError(f"expression: misplaced keyword {tok.lower()!r}")
        if tok is None:
            raise FlowError("expression: unexpected end")
        return tok

    @staticmethod
    def _as_bool(val: Any, where: str) -> bool:
        if not isinstance(val, bool):
            raise FlowError(f"expression: '{where}' needs booleans, got {val!r}")
        return val

    @staticmethod
    def _compare(op: str, left: Any, right: Any) -> bool:
        if op in ("==", "!="):
            # Exact: True != 1, None == None only.
            if isinstance(left, bool) or isinstance(right, bool):
                eq = (
                    isinstance(left, bool) and isinstance(right, bool) and left == right
                )
            else:
                eq = type(left) is type(right) and left == right
            return eq if op == "==" else not eq
        if isinstance(left, bool) or isinstance(right, bool):
            raise FlowError(f"expression: '{op}' does not apply to booleans")
        if type(left) is not type(right) or not isinstance(left, (int, float, str)):
            raise FlowError(
                f"expression: '{op}' needs two numbers or two strings, "
                f"got {left!r} and {right!r}"
            )
        return {
            ">": left > right,
            ">=": left >= right,
            "<": left < right,
            "<=": left <= right,
        }[op]


def evaluate_expr(expr: str, namespace: Dict[str, Any]) -> Any:
    """Evaluate a flow expression against the run namespace. Deny-closed."""
    return _Parser(_tokenize(expr), namespace).parse()


# ---------------------------------------------------------------------------
# Flow definition & validation
# ---------------------------------------------------------------------------


def _validate_flow(definition: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
    """Validate a flow definition dict. Returns a normalized copy.

    Deny-closed: duplicate ids, dangling edge endpoints, unknown minions,
    bad node shapes, or a missing/unknown start are refused.

    ``strict=True`` (via :func:`validate_flow`) additionally requires a
    non-empty ``name`` and a start node that is a ``trigger`` or ``minion``
    node. ``strict=False`` (via :func:`build_flow`) keeps the legacy
    permissive contract so existing graphs keep running.
    """
    if not isinstance(definition, dict):
        raise FlowError("flow definition must be a dict")
    flow_id = _check_id(definition.get("id", ""), "flow")
    if strict:
        name = definition.get("name", "")
        if not isinstance(name, str) or not name.strip():
            raise FlowError("strict validation: flow needs a non-empty 'name'")
    nodes = definition.get("nodes", [])
    edges = definition.get("edges", [])
    start = definition.get("start", "")
    if not isinstance(nodes, list) or not nodes:
        raise FlowError("flow needs a non-empty 'nodes' list")
    if not isinstance(edges, list):
        raise FlowError("flow 'edges' must be a list")

    seen: Dict[str, Dict[str, Any]] = {}
    for raw in nodes:
        if not isinstance(raw, dict):
            raise FlowError("flow node must be a dict")
        nid = _check_id(raw.get("id", ""), "node")
        if nid in seen:
            raise FlowError(f"duplicate node id {nid!r}")
        kind = raw.get("kind", "")
        if kind not in NODE_KINDS:
            if kind in _PACK_KINDS:
                # First touch of a node-pack kind: load the packs now.
                ensure_builtin_nodes()
            if kind not in NODE_KINDS:
                raise FlowError(
                    f"node {nid!r}: unknown kind {kind!r} (use {NODE_KINDS})"
                )
        node: Dict[str, Any] = {
            "id": nid,
            "kind": kind,
            "label": str(raw.get("label", nid)),
        }
        if kind == "minion":
            minion_id = raw.get("minion_id", "")
            if find_minion(MINIONS, minion_id) is None:
                raise FlowError(
                    f"node {nid!r}: unknown minion {minion_id!r} — "
                    "minion nodes must reference the catalog"
                )
            node["minion_id"] = minion_id
        elif kind == "trigger":
            cfg = raw.get("config", {})
            if not isinstance(cfg, dict):
                raise FlowError(f"node {nid!r}: 'trigger' needs a 'config' dict")
            ttype = cfg.get("trigger_type", "")
            if ttype not in _TRIGGER_TYPES:
                raise FlowError(
                    f"node {nid!r}: unknown trigger_type {ttype!r} "
                    f"(use {_TRIGGER_TYPES})"
                )
            if ttype == "webhook-in" and not cfg.get("path"):
                raise FlowError(f"node {nid!r}: webhook-in trigger needs config 'path'")
            if ttype == "schedule" and len(str(cfg.get("cron", "")).split()) != 5:
                raise FlowError(
                    f"node {nid!r}: schedule trigger needs a 5-field cron in config"
                )
            if ttype == "event" and not cfg.get("event_kind"):
                raise FlowError(
                    f"node {nid!r}: event trigger needs config 'event_kind'"
                )
            node["config"] = dict(cfg)
        elif kind == "branch":
            expr = raw.get("expr", "")
            try:
                _tokenize(expr)
            except FlowError as exc:
                raise FlowError(f"node {nid!r}: bad branch expr: {exc}") from exc
            node["expr"] = expr
        elif kind == "approval":
            cfg = raw.get("config", {})
            if not isinstance(cfg, dict):
                raise FlowError(f"node {nid!r}: 'approval' needs a 'config' dict")
            if not str(cfg.get("prompt", "")).strip():
                raise FlowError(f"node {nid!r}: approval needs config 'prompt'")
            node["config"] = {
                "prompt": str(cfg["prompt"]),
                "gate_kind": str(cfg.get("gate_kind", "approval")),
            }
        elif kind == "predicate":
            expr = raw.get("expr", "")
            try:
                _tokenize(expr)
            except FlowError as exc:
                raise FlowError(f"node {nid!r}: bad predicate expr: {exc}")
            node["expr"] = expr
        elif kind == "emit":
            mapping = raw.get("set", {})
            if not isinstance(mapping, dict) or not mapping:
                raise FlowError(f"node {nid!r}: 'emit' needs a non-empty 'set' dict")
            for path, expr in mapping.items():
                if not re.fullmatch(
                    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", str(path)
                ):
                    raise FlowError(f"node {nid!r}: bad emit path {path!r}")
                try:
                    _tokenize(str(expr))
                except FlowError as exc:
                    raise FlowError(f"node {nid!r}: bad emit expr: {exc}")
            node["set"] = {str(k): str(v) for k, v in mapping.items()}
        elif kind == "note":
            node["text"] = str(raw.get("text", ""))
        else:
            # Registry-provided kind (node-pack action kinds, custom kinds):
            # config shape is the pack's own contract; require a dict.
            cfg = raw.get("config", {})
            if not isinstance(cfg, dict):
                raise FlowError(f"node {nid!r}: kind {kind!r} needs a 'config' dict")
            node["config"] = dict(cfg)
        seen[nid] = node

    norm_edges: List[Dict[str, Any]] = []
    for i, raw in enumerate(edges):
        if not isinstance(raw, dict):
            raise FlowError("flow edge must be a dict")
        eid = str(raw.get("id", f"e{i}"))
        src, dst = raw.get("from", ""), raw.get("to", "")
        if src not in seen:
            raise FlowError(f"edge {eid!r}: unknown source node {src!r}")
        if dst not in seen:
            raise FlowError(f"edge {eid!r}: unknown target node {dst!r}")
        when = raw.get("when")
        if when is not None:
            try:
                _tokenize(str(when))
            except FlowError as exc:
                raise FlowError(f"edge {eid!r}: bad 'when' expr: {exc}")
        norm_edges.append(
            {"id": eid, "from": src, "to": dst, **({"when": str(when)} if when else {})}
        )

    if start not in seen:
        raise FlowError(f"flow {flow_id!r}: unknown start node {start!r}")
    if strict and seen[start]["kind"] not in ("trigger", "minion"):
        raise FlowError(
            f"flow {flow_id!r}: strict validation requires the start node "
            f"to be a trigger or minion node, got {seen[start]['kind']!r}"
        )

    return {
        "id": flow_id,
        "name": str(definition.get("name", flow_id)),
        "description": str(definition.get("description", "")),
        "start": start,
        "nodes": [seen[n["id"]] for n in nodes],
        "edges": norm_edges,
    }


def build_flow(definition: Dict[str, Any]) -> Dict[str, Any]:
    """Validate (legacy permissive contract) and normalize a flow definition.

    Any node kind may start the flow — this is the contract existing graphs
    were built on. New dispatchable flows should pass :func:`validate_flow`.
    """
    return _validate_flow(definition, strict=False)


def validate_flow(flow: Dict[str, Any]) -> Dict[str, Any]:
    """Strict JSON-schema validation of a flow definition.

    Required fields: ``id``, ``name``, ``start``, ``nodes``, ``edges``.
    Node ids unique; edges reference real nodes; the start node exists and
    is a ``trigger`` or ``minion`` node; unknown node kinds are refused.
    Returns the normalized flow. Deny-closed throughout.
    """
    return _validate_flow(flow, strict=True)


# ---------------------------------------------------------------------------
# Run records
# ---------------------------------------------------------------------------


@dataclass
class NodeRecord:
    node_id: str
    kind: str
    label: str
    ok: bool
    detail: str = ""
    receipt: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "label": self.label,
            "ok": self.ok,
            "detail": self.detail,
            "receipt": self.receipt,
        }


@dataclass
class FlowReceipt:
    """The immutable record of one flow run: every node receipted."""

    run_id: str
    flow_id: str
    flow_name: str
    dry_run: bool
    ok: bool
    ts: str = ""
    nodes: List[NodeRecord] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    plan: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.ts:
            self.ts = _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "flow_id": self.flow_id,
            "flow_name": self.flow_name,
            "dry_run": self.dry_run,
            "ok": self.ok,
            "ts": self.ts,
            "nodes": [n.to_dict() for n in self.nodes],
            "notes": list(self.notes),
            "plan": [dict(p) for p in self.plan],
        }

    def render(self) -> str:
        lines = [
            f"flow receipt {self.run_id} — {self.flow_name} ({self.flow_id})",
            f"mode: {'dry-run (nothing executed)' if self.dry_run else 'live'}",
            f"plan: {len(self.plan)} node(s) previewed before execution",
            f"nodes: {len(self.nodes)} — {'OK' if self.ok else 'FAILED'}",
        ]
        for n in self.nodes:
            mark = "✓" if n.ok else "✗"
            lines.append(f"  {mark} [{n.kind}] {n.label} — {n.detail}")
        for note in self.notes:
            lines.append(f"  note: {note}")
        return "\n".join(lines)


def _set_path(namespace: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur = namespace
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


# ---------------------------------------------------------------------------
# Node execution — registry logic nodes + the gated action rail
# ---------------------------------------------------------------------------


def _check_handler_result(nid: str, result: Any) -> "tuple[bool, Dict[str, Any], str]":
    """Enforce the handler contract. Deny-closed: malformed results are
    refused, never half-accepted."""
    if not isinstance(result, dict):
        raise FlowError(
            f"node {nid!r}: handler must return a dict, got {type(result).__name__}"
        )
    ok = result.get("ok")
    output = result.get("output", {})
    evidence = result.get("evidence", "")
    if not isinstance(ok, bool):
        raise FlowError(f"node {nid!r}: handler result 'ok' must be bool")
    if not isinstance(output, dict):
        raise FlowError(f"node {nid!r}: handler result 'output' must be a dict")
    if not isinstance(evidence, str):
        raise FlowError(f"node {nid!r}: handler result 'evidence' must be a string")
    return ok, output, evidence


def _execute_logic_node(
    node: Dict[str, Any],
    entry: Dict[str, Any],
    ns: Dict[str, Any],
    run: Dict[str, Any],
) -> NodeRecord:
    """Run a registry logic node (trigger/branch/approval/custom).

    GateDenied is never swallowed here — it propagates so the run stops
    with a denied receipt.
    """
    nid = node["id"]
    try:
        result = entry["handler"](node, ns, run)
        ok, output, evidence = _check_handler_result(nid, result)
    except GateDenied:
        raise
    except FlowError as exc:
        return NodeRecord(
            nid, node["kind"], node["label"], False, detail=f"node failed: {exc}"
        )
    except Exception as exc:  # fail-closed: a broken handler denies, never crashes
        return NodeRecord(
            nid,
            node["kind"],
            node["label"],
            False,
            detail=f"handler error ({type(exc).__name__}): {exc}",
        )
    ns[nid] = output
    return NodeRecord(
        nid, node["kind"], node["label"], ok, detail=evidence[:220] or "ok"
    )


def _action_gate(
    node: Dict[str, Any], run: Dict[str, Any], preview: str
) -> "GateResult":
    """The Permission step for action nodes: always an approval gate.

    Live mode never auto-approves: the dry-run ``auto_approve`` responder is
    refused outright in live runs.
    """
    nid = node["id"]
    responder = run["responder"]
    if not run["dry_run"] and responder is auto_approve:
        raise FlowError(
            f"action node {nid!r}: live mode refuses the dry-run "
            "auto_approve responder — pass a real responder"
        )
    request = GateRequest(
        minion_id=f"flow:{run['flow_id']}:{nid}",
        kind=GateKind.APPROVAL,
        prompt=f"{node.get('label', nid)}: {preview[:160]}",
        context={
            "node_id": nid,
            "kind": node["kind"],
            "dry_run": run["dry_run"],
            "flow_id": run["flow_id"],
        },
    )
    gate = Gate(request)
    try:
        return gate.require(responder)
    except GateDenied:
        raise
    except Exception as exc:
        # Fail-closed: a broken or missing responder denies the run.
        raise FlowError(
            f"action node {nid!r}: gate responder failed ({type(exc).__name__})"
        ) from exc


def _execute_action_node(
    node: Dict[str, Any],
    entry: Dict[str, Any],
    ns: Dict[str, Any],
    run: Dict[str, Any],
) -> NodeRecord:
    """Walk an action node through Plan -> Preview -> Permission -> Execute
    -> Verify -> Receipt.

    The handler runs only in live mode; dry-run simulates and records.
    The receipt entry carries node id, preview, gate decision, and evidence.
    """
    nid, kind, label = node["id"], node["kind"], node["label"]
    dry_run = run["dry_run"]
    preview = _preview_node(node)
    base_receipt = {
        "node_id": nid,
        "kind": kind,
        "preview": preview,
        "rail": ["plan", "preview", "permission", "execute", "verify", "receipt"],
    }

    # PLAN + PREVIEW are the preview_fn output itself.
    # PERMISSION — the gate (GateDenied propagates: denied receipt).
    try:
        gate_result = _action_gate(node, run, preview)
    except GateDenied:
        raise
    except FlowError as exc:
        return NodeRecord(
            nid,
            kind,
            label,
            False,
            detail=f"{exc} — run stopped",
            receipt={
                **base_receipt,
                "gate_decision": None,
                "evidence": "gate failed closed — nothing executed",
            },
        )

    # EXECUTE
    if dry_run:
        executed, ok = False, True
        output = {"simulated": True}
        evidence = f"dry-run: would {preview}"
    else:
        executed = True
        try:
            result = entry["handler"](node, ns, run)
            ok, output, evidence = _check_handler_result(nid, result)
        except GateDenied:
            raise
        except FlowError as exc:
            return NodeRecord(
                nid,
                kind,
                label,
                False,
                detail=f"handler failed: {exc}",
                receipt={
                    **base_receipt,
                    "gate_decision": gate_result.to_dict(),
                    "evidence": f"handler failed: {exc}",
                },
            )
        except Exception as exc:
            return NodeRecord(
                nid,
                kind,
                label,
                False,
                detail=f"handler error ({type(exc).__name__}): {exc}",
                receipt={
                    **base_receipt,
                    "gate_decision": gate_result.to_dict(),
                    "evidence": f"handler error: {exc} — fail-closed",
                },
            )

    # VERIFY — evidence must exist; RECEIPT — bank it all.
    ns[nid] = output
    receipt_entry = {
        **base_receipt,
        "gate_decision": gate_result.to_dict(),
        "evidence": evidence,
        "dry_run": dry_run,
        "executed": executed,
    }
    detail = (
        "rail: plan -> preview -> permission -> execute -> verify -> receipt; "
        f"gate {gate_result.decision}; {evidence[:140]}"
    )
    return NodeRecord(nid, kind, label, ok, detail=detail, receipt=receipt_entry)


def _builtin_preview(node: Dict[str, Any]) -> str:
    """Preview text for the legacy (non-registry) node kinds."""
    kind = node["kind"]
    if kind == "minion":
        return (
            f"minion '{node['minion_id']}' through the full rail (simulated in dry-run)"
        )
    if kind == "predicate":
        return f"evaluate '{node['expr']}' -> passed"
    if kind == "emit":
        return "set " + ", ".join(f"{p} = {e}" for p, e in node["set"].items())
    if kind == "note":
        return f"annotate: {node.get('text', '')[:120]}"
    return f"node kind '{kind}'"


def _preview_node(node: Dict[str, Any]) -> str:
    """What this node WOULD do — registry preview_fn, else built-in."""
    entry = _NODE_REGISTRY.get(node["kind"])
    if entry is not None:
        try:
            return str(entry["preview_fn"](node))
        except Exception as exc:
            return f"preview unavailable ({type(exc).__name__}): {node['kind']}"
    return _builtin_preview(node)


# ---------------------------------------------------------------------------
# Execution — every minion node walks the full rail
# ---------------------------------------------------------------------------


def run_flow(
    flow: Dict[str, Any],
    event: Optional[TriggerEvent] = None,
    responder: Responder = auto_approve,
    dry_run: bool = True,
    context: Optional[Dict[str, Any]] = None,
    max_steps: int = _MAX_STEPS,
) -> FlowReceipt:
    """Run a validated flow definition.

    Traversal starts at ``flow["start"]``; edges whose ``when`` expression
    holds are followed. Each ``minion`` node runs through the full
    automation rail (Plan -> Preview -> Permission -> Execute -> Verify ->
    Receipt) via :func:`run_minion` and banks its engine receipt. Dry-run
    is the default: nothing executes, everything is recorded.
    """
    flow = build_flow(flow)  # re-validate: never run an unchecked graph
    by_id = {n["id"]: n for n in flow["nodes"]}
    outgoing: Dict[str, List[Dict[str, Any]]] = {n["id"]: [] for n in flow["nodes"]}
    for e in flow["edges"]:
        outgoing[e["from"]].append(e)

    run_id = f"flow-{uuid.uuid4().hex[:12]}"
    run_info = {
        "run_id": run_id,
        "flow_id": flow["id"],
        "flow_name": flow["name"],
        "dry_run": dry_run,
        "responder": responder,
    }
    # The plan is logged first — every run (dry or live) previews the whole
    # graph before anything executes.
    plan = plan_flow(flow)
    ns: Dict[str, Any] = dict(context or {})
    trigger = event or TriggerEvent(
        kind="flow",
        summary=f"flow run {flow['id']}",
        payload={"flow_id": flow["id"], "run_id": run_id},
    )
    ns.setdefault(
        "event",
        {
            "kind": trigger.kind,
            "summary": trigger.summary,
            "payload": dict(trigger.payload),
        },
    )

    records: List[NodeRecord] = []
    notes: List[str] = []
    visits: Dict[str, int] = {}
    frontier: List[str] = [flow["start"]]
    steps = 0
    failed = False

    def execute_node(node: Dict[str, Any]) -> NodeRecord:
        nid, kind = node["id"], node["kind"]
        if kind == "minion":
            minion = find_minion(MINIONS, node["minion_id"])
            assert minion is not None  # build_flow guarantees it
            receipt: Receipt = run_minion(
                minion, trigger, responder=responder, dry_run=dry_run
            )
            ns[nid] = {
                "ok": receipt.ok,
                "executed": receipt.executed,
                "dry_run": receipt.dry_run,
                "receipt_id": receipt.receipt_id,
            }
            return NodeRecord(
                node_id=nid,
                kind=kind,
                label=node["label"],
                ok=receipt.ok,
                detail=f"rail: {' -> '.join(receipt.rail)}; "
                f"{'simulated' if receipt.dry_run else 'executed'}; "
                f"{receipt.note or 'receipted'}",
                receipt=receipt.to_dict(),
            )
        if kind == "predicate":
            try:
                passed = evaluate_expr(node["expr"], ns)
            except FlowError as exc:
                return NodeRecord(
                    nid, kind, node["label"], False, detail=f"predicate failed: {exc}"
                )
            if not isinstance(passed, bool):
                return NodeRecord(
                    nid,
                    kind,
                    node["label"],
                    False,
                    detail=f"predicate must be boolean, got {passed!r}",
                )
            ns[nid] = {"passed": passed}
            return NodeRecord(
                nid, kind, node["label"], True, detail=f"{node['expr']} -> {passed}"
            )
        if kind == "emit":
            try:
                for path, expr in node["set"].items():
                    _set_path(ns, path, evaluate_expr(expr, ns))
            except FlowError as exc:
                return NodeRecord(
                    nid, kind, node["label"], False, detail=f"emit failed: {exc}"
                )
            return NodeRecord(
                nid, kind, node["label"], True, detail=f"set {', '.join(node['set'])}"
            )
        if kind == "note":
            text = node.get("text", "")
            notes.append(f"{nid}: {text}")
            ns[nid] = {"noted": True}
            return NodeRecord(nid, kind, node["label"], True, detail="annotated")
        # registry kinds (trigger / branch / approval / node-pack actions)
        entry = _NODE_REGISTRY.get(kind)
        if entry is None:
            if kind in _PACK_KINDS:
                ensure_builtin_nodes()  # lazy pack load; missing -> FlowError
                entry = _NODE_REGISTRY.get(kind)
            if entry is None:
                raise FlowError(
                    f"node {nid!r}: kind {kind!r} has no registered handler"
                )
        if entry["action"]:
            return _execute_action_node(node, entry, ns, run_info)
        return _execute_logic_node(node, entry, ns, run_info)

    while frontier:
        if steps >= max_steps:
            raise FlowError(
                f"flow {flow['id']!r}: exceeded {max_steps} steps — "
                "possible runaway; refusing to continue"
            )
        nid = frontier.pop(0)
        visits[nid] = visits.get(nid, 0) + 1
        if visits[nid] > _MAX_VISITS_PER_NODE:
            raise FlowError(
                f"flow {flow['id']!r}: node {nid!r} visited "
                f"{visits[nid]} times — loop without exit; refusing"
            )
        steps += 1
        node = by_id[nid]
        try:
            record = execute_node(node)
        except GateDenied as denied:
            # The human said no: stop the flow with a denied receipt.
            gr = denied.result
            ns[nid] = {"denied": True, "decision": gr.decision}
            record = NodeRecord(
                node_id=nid,
                kind=node["kind"],
                label=node["label"],
                ok=False,
                detail=(
                    f"gate denied ({gr.request.kind.value}): "
                    f"{gr.note or 'no reason given'} — flow stopped"
                ),
                receipt={
                    "node_id": nid,
                    "kind": node["kind"],
                    "gate_decision": gr.to_dict(),
                    "evidence": "denied — nothing executed",
                },
            )
        records.append(record)
        if not record.ok:
            failed = True
            break  # fail-closed: a bad node stops the flow, loudly
        for edge in outgoing[nid]:
            when = edge.get("when")
            if when is None:
                frontier.append(edge["to"])
                continue
            if node["kind"] == "branch" and when in ("true", "false"):
                # Branch routing labels: follow the edge matching the branch result.
                holds = bool(ns.get(nid, {}).get("passed")) == (when == "true")
            else:
                try:
                    holds = evaluate_expr(when, ns)
                except FlowError as exc:
                    raise FlowError(f"edge {edge['id']!r}: {exc}")
                if not isinstance(holds, bool):
                    raise FlowError(
                        f"edge {edge['id']!r}: 'when' must be boolean, got {holds!r}"
                    )
            if holds:
                frontier.append(edge["to"])

    return FlowReceipt(
        run_id=run_id,
        flow_id=flow["id"],
        flow_name=flow["name"],
        dry_run=dry_run,
        ok=not failed,
        nodes=records,
        notes=notes,
        plan=plan,
    )


# ---------------------------------------------------------------------------
# Dry-run planner — the full "here is what would happen"
# ---------------------------------------------------------------------------


def _traversal_order(flow: Dict[str, Any]) -> List[str]:
    """BFS node order from ``start``; unreachable nodes trail in definition order."""
    order: List[str] = []
    seen = set()
    queue = [flow["start"]]
    while queue:
        nid = queue.pop(0)
        if nid in seen:
            continue
        seen.add(nid)
        order.append(nid)
        for e in flow["edges"]:
            if e["from"] == nid and e["to"] not in seen:
                queue.append(e["to"])
    for n in flow["nodes"]:
        if n["id"] not in seen:
            order.append(n["id"])
    return order


def plan_flow(flow: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Render every node in traversal order with its preview output.

    The full "here is what would happen" before execution. Every run
    (dry or live) logs this plan first on its receipt.
    """
    flow = build_flow(flow)
    try:
        ensure_builtin_nodes()
    except FlowError:
        pass  # planner degrades: pack kinds preview as "pack missing"
    by_id = {n["id"]: n for n in flow["nodes"]}
    plan = []
    for i, nid in enumerate(_traversal_order(flow)):
        node = by_id[nid]
        plan.append(
            {
                "order": i,
                "node_id": nid,
                "kind": node["kind"],
                "label": node["label"],
                "preview": _preview_node(node),
            }
        )
    return plan


# ---------------------------------------------------------------------------
# Trigger dispatcher — events in, flow runs out
# ---------------------------------------------------------------------------


def _trigger_matches(node: Dict[str, Any], event: Dict[str, Any]) -> bool:
    """Does this trigger node fire for the event? Deny-closed: unknown
    trigger types never match."""
    cfg = node.get("config", {}) or {}
    ttype = cfg.get("trigger_type", "")
    payload = event.get("payload") or {}
    if ttype == "webhook-in":
        return event.get("kind") == "webhook" and payload.get("path") == cfg.get("path")
    if ttype == "schedule":
        trig = TriggerEvent(
            kind="schedule",
            summary="schedule dispatch",
            payload=dict(payload),
            ts=str(event.get("ts", "")),
        )
        return _cron_matches(str(cfg.get("cron", "")), trig)
    if ttype == "manual":
        return event.get("kind") == "manual"
    if ttype == "event":
        want = str(cfg.get("event_kind", ""))
        return event.get("kind") == want or str(payload.get("event_kind", "")) == want
    return False


def dispatch_trigger(
    event: Dict[str, Any],
    responder: Responder = auto_approve,
    dry_run: bool = True,
    home: "str | os.PathLike[str] | None" = None,
) -> List[Dict[str, Any]]:
    """Scan saved flows for ``trigger`` nodes matching ``event`` and start
    a run per match.

    ``event`` is ``{"kind": str, "source": str, "payload": dict}``
    (``"ts"`` optional, ISO — used for schedule/cron matching).

    Matching:
    - ``webhook-in``: event kind ``"webhook"`` and ``payload.path`` equals
      the trigger's configured ``path``.
    - ``schedule``: the trigger's ``cron`` matches the event timestamp
      (via ``engine._cron_field_matches`` semantics).
    - ``manual``: event kind ``"manual"``.
    - ``event``: the trigger's ``event_kind`` equals the event kind or
      ``payload.event_kind``.

    Returns one summary dict per started run: flow_id, flow_name, run_id,
    ok, nodes, dry_run, trigger_node (plus ``error`` when a flow refused
    to run). A bad flow never blocks the others.
    """
    if not isinstance(event, dict):
        raise FlowError("dispatch_trigger: event must be a dict")
    kind = str(event.get("kind", ""))
    payload = event.get("payload") or {}
    summaries: List[Dict[str, Any]] = []
    directory = flows_home(home)
    paths = sorted(directory.glob("*.json")) if directory.exists() else []
    for path in paths:
        try:
            flow = load_flow(path.stem, home)
        except FlowError:
            continue  # a corrupt file never breaks the dispatch
        matched = next(
            (
                n
                for n in flow["nodes"]
                if n["kind"] == "trigger" and _trigger_matches(n, event)
            ),
            None,
        )
        if matched is None:
            continue
        trig = TriggerEvent(
            kind=kind or "dispatch",
            summary=f"dispatch:{flow['id']}:{matched['id']}",
            payload=dict(payload),
            ts=str(event.get("ts", "")),
        )
        summary: Dict[str, Any] = {
            "flow_id": flow["id"],
            "flow_name": flow["name"],
            "run_id": None,
            "ok": False,
            "nodes": 0,
            "dry_run": dry_run,
            "trigger_node": matched["id"],
        }
        try:
            receipt = run_flow(flow, event=trig, responder=responder, dry_run=dry_run)
        except (FlowError, GateDenied) as exc:
            summary["error"] = str(exc)
        else:
            summary.update(
                {
                    "run_id": receipt.run_id,
                    "ok": receipt.ok,
                    "nodes": len(receipt.nodes),
                }
            )
        summaries.append(summary)
    return summaries


# ---------------------------------------------------------------------------
# Visualization as data
# ---------------------------------------------------------------------------


def manifest(flow: Dict[str, Any]) -> Dict[str, Any]:
    """Return the flow as a renderable graph manifest: nodes with
    deterministic layered positions, edges with conditions. A renderer —
    present or future — draws this; no GUI is built here."""
    flow = build_flow(flow)
    # Layer by BFS depth from start (deterministic: sorted edge order).
    depth: Dict[str, int] = {flow["start"]: 0}
    queue = [flow["start"]]
    outgoing: Dict[str, List[str]] = {}
    for e in sorted(flow["edges"], key=lambda e: e["id"]):
        outgoing.setdefault(e["from"], []).append(e["to"])
    while queue:
        nid = queue.pop(0)
        for dst in outgoing.get(nid, []):
            if dst not in depth:
                depth[dst] = depth[nid] + 1
                queue.append(dst)
    # Unreachable nodes (dangling but valid) go on the last layer.
    max_d = max(depth.values(), default=0)
    for n in flow["nodes"]:
        depth.setdefault(n["id"], max_d + 1)
    layers: Dict[int, List[str]] = {}
    for nid, d in depth.items():
        layers.setdefault(d, []).append(nid)
    pos = {}
    for d in sorted(layers):
        for i, nid in enumerate(sorted(layers[d])):
            pos[nid] = {"x": d, "y": i}
    return {
        "flow_id": flow["id"],
        "flow_name": flow["name"],
        "nodes": [
            {
                "id": n["id"],
                "kind": n["kind"],
                "label": n["label"],
                "x": pos[n["id"]]["x"],
                "y": pos[n["id"]]["y"],
                **({"minion_id": n["minion_id"]} if n["kind"] == "minion" else {}),
            }
            for n in flow["nodes"]
        ],
        "edges": [
            {
                "id": e["id"],
                "from": e["from"],
                "to": e["to"],
                **({"when": e["when"]} if e.get("when") else {}),
            }
            for e in flow["edges"]
        ],
    }


def to_mermaid(flow: Dict[str, Any]) -> str:
    """Render the flow as a Mermaid flowchart string (data that renders)."""
    m = manifest(flow)
    shapes = {
        "minion": ("[", "]"),
        "trigger": ("((", "))"),
        "branch": ("{{", "}}"),
        "approval": ("[/", "\\]"),
        "predicate": ("{", "}"),
        "emit": ("([", "])"),
        "note": ("[[", "]]"),
    }
    lines = ["flowchart TD"]
    for n in m["nodes"]:
        l, r = shapes.get(n["kind"], ("[", "]"))
        label = n["label"].replace('"', "'")
        lines.append(f'    {n["id"]}{l}"{label}"{r}')
    for e in m["edges"]:
        arrow = f'-->|"{e["when"]}"|' if e.get("when") else "-->"
        lines.append(f"    {e['from']} {arrow} {e['to']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_flow(
    flow: Dict[str, Any], home: "str | os.PathLike[str] | None" = None
) -> Path:
    """Validate and persist a flow definition as JSON."""
    flow = build_flow(flow)
    directory = flows_home(home)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{flow['id']}.json"
    path.write_text(json.dumps(flow, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_flow(
    flow_id: str, home: "str | os.PathLike[str] | None" = None
) -> Dict[str, Any]:
    _check_id(flow_id, "flow")
    path = flows_home(home) / f"{flow_id}.json"
    if not path.exists():
        raise FlowError(f"unknown flow {flow_id!r}")
    try:
        return build_flow(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise FlowError(f"flow {flow_id!r}: unreadable: {exc}")


def list_flows(home: "str | os.PathLike[str] | None" = None) -> List[Dict[str, Any]]:
    directory = flows_home(home)
    if not directory.exists():
        return []
    out = []
    for path in sorted(directory.glob("*.json")):
        try:
            flow = build_flow(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, FlowError):
            continue  # a corrupt file never breaks the listing
        out.append(
            {
                "id": flow["id"],
                "name": flow["name"],
                "description": flow["description"],
                "nodes": len(flow["nodes"]),
                "edges": len(flow["edges"]),
            }
        )
    return out


def delete_flow(flow_id: str, home: "str | os.PathLike[str] | None" = None) -> bool:
    _check_id(flow_id, "flow")
    path = flows_home(home) / f"{flow_id}.json"
    if not path.exists():
        return False
    path.unlink()
    return True
