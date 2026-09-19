"""toolcall — the three tool-calling protocols, side by side.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.5).

An agent's actions need a wire format between the policy and the tool
registry. The published literature converged on three, and they are not
equal — each is a different bet about what small models are good at:

1. **JSON function-calling** (``JsonProtocol``): actions as JSON blobs
   ``{"name": ..., "arguments": {...}}`` validated against per-tool
   schemas. Clean, machine-checkable, brittle when the model fumbles a
   quote or a type.
2. **Code-emitting** (``CodeProtocol``): actions as Python snippets.
   Variables, loops, composition — several tool calls in one round trip,
   with intermediate values held in names instead of re-serialized.
   Reported better overall in the published comparisons, and it fits a
   local synthetic-intelligence stack: each round trip is a full context
   re-processing, so fewer, denser actions win. Executed in a restricted
   namespace (AST-checked, no imports, no builtins beyond a whitelist).
3. **ReAct text** (``ReactProtocol``): ``Thought:`` / ``Action:`` /
   ``Action Input:`` plain text parsed by regex. Honestly labeled
   **fragile** — the prompt is the protocol, so any drift in phrasing
   breaks the parse. Kept because it needs no structured API at all,
   and because knowing exactly how it breaks is useful.

``ToolSpec`` describes a tool once (name, description, JSON-schema-ish
parameter schema, the callable); each protocol renders and parses
against the same specs, so round-trip tests compare like with like.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

ORIGIN = "levi-revival/toolcall"


# ---------------------------------------------------------------------------
# Shared tool description
# ---------------------------------------------------------------------------


@dataclass
class ToolSpec:
    """One tool, described once for all three protocols."""

    name: str
    description: str
    parameters: Dict[
        str, Any
    ]  # JSON-schema-ish: {"type": "object", "properties": {...}, "required": [...]}
    fn: Callable[..., Any] = field(repr=False, default=lambda **k: None)


class SchemaError(Exception):
    pass


def validate_against_schema(args: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """Minimal JSON-schema-ish validator. Returns a list of violations."""
    problems: List[str] = []
    if not isinstance(args, dict):
        return ["arguments must be an object"]
    props = schema.get("properties", {})
    for req in schema.get("required", []):
        if req not in args:
            problems.append(f"missing required parameter: {req}")
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    for key, value in args.items():
        spec = props.get(key)
        if spec is None:
            problems.append(f"unknown parameter: {key}")
            continue
        want = type_map.get(spec.get("type", "string"))
        if want and not isinstance(value, want):
            problems.append(
                f"parameter {key!r}: expected {spec.get('type')}, got {type(value).__name__}"
            )
        if "enum" in spec and value not in spec["enum"]:
            problems.append(f"parameter {key!r}: {value!r} not in {spec['enum']}")
    return problems


# ---------------------------------------------------------------------------
# 1. JSON function-calling
# ---------------------------------------------------------------------------


class JsonProtocol:
    """Emit/parse/validate JSON action blobs."""

    @staticmethod
    def emit(name: str, arguments: Dict[str, Any]) -> str:
        return json.dumps({"name": name, "arguments": arguments})

    @staticmethod
    def parse(text: str) -> Tuple[str, Dict[str, Any]]:
        try:
            blob = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SchemaError(f"not valid JSON: {exc}") from exc
        if not isinstance(blob, dict) or "name" not in blob:
            raise SchemaError("JSON action needs 'name' (and 'arguments')")
        args = blob.get("arguments", {})
        if not isinstance(args, dict):
            raise SchemaError("'arguments' must be an object")
        return blob["name"], args

    @staticmethod
    def validate(
        name: str, args: Dict[str, Any], specs: Dict[str, ToolSpec]
    ) -> List[str]:
        spec = specs.get(name)
        if spec is None:
            return [f"unknown tool: {name}"]
        return validate_against_schema(args, spec.parameters)

    @staticmethod
    def execute(name: str, args: Dict[str, Any], specs: Dict[str, ToolSpec]) -> Any:
        problems = JsonProtocol.validate(name, args, specs)
        if problems:
            raise SchemaError("; ".join(problems))
        return specs[name].fn(**args)


# ---------------------------------------------------------------------------
# 2. Code-emitting: Python snippets in a restricted namespace
# ---------------------------------------------------------------------------


_ALLOWED_NODES = (
    ast.Module,
    ast.Expr,
    ast.Assign,
    ast.AnnAssign,
    ast.AugAssign,
    ast.For,
    ast.While,
    ast.If,
    ast.With,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Set,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.And,
    ast.Or,
    ast.Not,
    ast.In,
    ast.NotIn,
    ast.Subscript,
    ast.Attribute,
    ast.keyword,
    ast.arg,
    ast.ListComp,
    ast.comprehension,
    ast.Return,
    ast.Break,
    ast.Continue,
    ast.Pass,
)

_FORBIDDEN_NAMES = {
    "__",
    "import",
    "eval",
    "exec",
    "open",
    "compile",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "__import__",
    "input",
    "help",
    "exit",
    "quit",
}

_SAFE_BUILTINS = {
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "sum": sum,
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "sorted": sorted,
    "any": any,
    "all": all,
    "print": print,
}


class UnsafeCode(Exception):
    pass


def check_code_safety(code: str) -> List[str]:
    """AST whitelist check. Returns violations (empty = safe)."""
    problems: List[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"syntax error: {exc}"]
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            problems.append(f"forbidden syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            problems.append(f"forbidden name: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            problems.append(f"private attribute access: {node.attr}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _FORBIDDEN_NAMES:
                problems.append(f"forbidden call: {node.func.id}")
    if re.search(r"__\w*__", code):
        problems.append("dunder access forbidden")
    return problems


class CodeProtocol:
    """Emit Python action snippets; run them restricted."""

    @staticmethod
    def emit(
        calls: List[Tuple[str, Dict[str, Any]]], assign_to: Optional[List[str]] = None
    ) -> str:
        """Render tool calls as code. ``assign_to`` names results positionally."""
        lines: List[str] = []
        for i, (name, args) in enumerate(calls):
            arg_src = ", ".join(f"{k}={v!r}" for k, v in args.items())
            call = f"{name}({arg_src})"
            if assign_to and i < len(assign_to):
                lines.append(f"{assign_to[i]} = {call}")
            else:
                lines.append(call)
        return "\n".join(lines)

    @staticmethod
    def run(code: str, specs: Dict[str, ToolSpec]) -> Dict[str, Any]:
        """Execute a snippet with only the tools + safe builtins visible."""
        problems = check_code_safety(code)
        if problems:
            raise UnsafeCode("; ".join(problems))
        namespace: Dict[str, Any] = dict(_SAFE_BUILTINS)
        for name, spec in specs.items():
            namespace[name] = spec.fn
        # No builtins at all beyond the whitelist: "__builtins__" -> {}.
        exec(compile(code, "<toolcall>", "exec"), {"__builtins__": {}}, namespace)  # noqa: S102
        return {k: v for k, v in namespace.items() if k not in _SAFE_BUILTINS}


# ---------------------------------------------------------------------------
# 3. ReAct text: Thought: / Action: / Action Input:
# ---------------------------------------------------------------------------


_REACT_RE = re.compile(
    r"Thought:\s*(?P<thought>.*?)\n"
    r"Action:\s*(?P<action>[^\n]*)\n"
    r"Action\s*Input:\s*(?P<input>.*)",
    re.DOTALL,
)


@dataclass
class ReactAction:
    thought: str
    action: str
    action_input: Dict[str, Any]
    raw_input: str = ""


class ReactProtocol:
    """Parse/emit ReAct text. Honestly labeled FRAGILE.

    The prompt is the protocol: any drift in the model's phrasing
    ("Action Input" vs "ActionInput", extra prose, a second Action
    block) breaks the parse. ``parse`` raises on ambiguity; use
    ``parse_lenient`` when you want best-effort.
    """

    FRAGILE = True  # labeled at the class level, on purpose

    @staticmethod
    def emit(thought: str, action: str, action_input: Dict[str, Any]) -> str:
        return (
            f"Thought: {thought}\n"
            f"Action: {action}\n"
            f"Action Input: {json.dumps(action_input)}"
        )

    @staticmethod
    def parse(text: str) -> ReactAction:
        match = _REACT_RE.search(text.strip())
        if not match:
            raise SchemaError(
                "ReAct parse failed: expected 'Thought:' / 'Action:' / 'Action Input:' lines"
            )
        raw = match.group("input").strip()
        try:
            action_input = json.loads(raw)
        except json.JSONDecodeError:
            # Best effort: treat as a single raw string argument.
            action_input = {"_raw": raw}
        if not isinstance(action_input, dict):
            action_input = {"_raw": raw}
        return ReactAction(
            thought=match.group("thought").strip(),
            action=match.group("action").strip(),
            action_input=action_input,
            raw_input=raw,
        )

    @staticmethod
    def parse_lenient(text: str) -> Optional[ReactAction]:
        try:
            return ReactProtocol.parse(text)
        except SchemaError:
            return None

    @staticmethod
    def execute(parsed: ReactAction, specs: Dict[str, ToolSpec]) -> Any:
        spec = specs.get(parsed.action)
        if spec is None:
            raise SchemaError(f"unknown tool: {parsed.action}")
        args = {k: v for k, v in parsed.action_input.items() if not k.startswith("_")}
        problems = validate_against_schema(args, spec.parameters)
        if problems:
            raise SchemaError("; ".join(problems))
        return spec.fn(**args)
