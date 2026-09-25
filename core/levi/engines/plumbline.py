"""Plumbline engine — the invariant-guard: laws first, proof after.

Chauncey's law-guard-prove rule made executable. Every build declares its
laws (invariants) up front and ships a machine-checkable proof; plumbline
is the guard that hangs each declared law against a verdict and reports
which held, which broke, and the exact evidence. A plumb line does not
argue — it shows true.

A law is a small declarative rule — data, never code::

    {"id": "partition",
     "claim": "every item lands in exactly one group",
     "path": "duplicate_count", "op": ">=", "value": 0}

``path`` is a dot-path into the verdict: dict keys, or integer indices
for lists (``groups.0.canonical``). ``op`` is one of:

    exists | missing            presence — no ``value`` needed
    == | != | < | <= | > | >=   comparisons — missing path never coerces
    in | not-in                 observed must (not) be a member of ``value``
                                (a list)
    contains                    observed (str/list/dict) must contain ``value``
    len== | len>= | len<=        length of observed (str/list/dict/tuple)

Absence never satisfies a positive claim: any comparison op against a
missing path is a FAIL (the verdict did not uphold the law); only the
``missing`` op holds on absence.

Laws (declared up front, proved by the test suite)
--------------------------------------------------
1. **Declaration law** — at least one law must be declared; a plumb line
   with no wall proves nothing. Empty ``laws`` is refused.
2. **Determinism law** — same inputs → byte-identical verdict (sans
   ``ran_at``).
3. **Deny-closed law** — malformed laws (unknown op, bad path, wrong
   value shape, duplicate law ids, laws beyond ``max_laws``) are refused
   with a named error, never coerced.
4. **No-eval law** — the rule DSL never executes code; paths are data
   lookups, ops are fixed comparisons.
5. **Evidence law** — every law result carries the observed value (or the
   recorded fact of absence) next to the claim; a bare pass/fail is
   refused by design.
6. **No-coercion law** — a missing path never quietly becomes true,
   zero, or empty; it is reported as ``"<missing>"`` and fails every
   comparison op.

Pure computation — no actions, no side effects.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from levi.engines.base import Engine, EngineInputError, EngineResult, registry

_DEFAULT_MAX_LAWS = 64
_MAX_PATH_DEPTH = 16

_COMPARISON_OPS = ("==", "!=", "<", "<=", ">", ">=")
_MEMBERSHIP_OPS = ("in", "not-in")
_LENGTH_OPS = ("len==", "len>=", "len<=")
_PRESENCE_OPS = ("exists", "missing")
_ALL_OPS = (
    _COMPARISON_OPS + _MEMBERSHIP_OPS + _LENGTH_OPS + _PRESENCE_OPS + ("contains",)
)

_SCALAR_TYPES = (str, int, float, bool, type(None))
_CONTAINER_TYPES = (str, list, tuple, dict)


class _Missing:
    """Sentinel for a path that resolved to nothing."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - display only
        return "<missing>"


MISSING = _Missing()


def _fail_input(msg: str) -> EngineInputError:
    return EngineInputError(f"plumbline: {msg}")


def _validate_path(path: object) -> List[str]:
    if not isinstance(path, str) or not path:
        raise _fail_input(f"law 'path' must be a non-empty str, got {path!r}")
    segments = path.split(".")
    if any(not seg for seg in segments):
        raise _fail_input(f"law 'path' has an empty segment: {path!r}")
    if len(segments) > _MAX_PATH_DEPTH:
        raise _fail_input(f"law 'path' exceeds max depth {_MAX_PATH_DEPTH}: {path!r}")
    return segments


def _validate_law(law: object, seen_ids: set) -> Dict[str, Any]:
    if not isinstance(law, dict):
        raise _fail_input(f"each law must be a dict, got {type(law).__name__}")
    law_id = law.get("id")
    if not isinstance(law_id, str) or not law_id:
        raise _fail_input(f"law 'id' must be a non-empty str, got {law_id!r}")
    if law_id in seen_ids:
        raise _fail_input(f"duplicate law id '{law_id}' — refused, never merged")
    seen_ids.add(law_id)

    claim = law.get("claim")
    if not isinstance(claim, str) or not claim.strip():
        raise _fail_input(f"law '{law_id}': 'claim' must be a non-empty str")

    op = law.get("op")
    if op not in _ALL_OPS:
        raise _fail_input(
            f"law '{law_id}': unknown op {op!r}; known: {', '.join(_ALL_OPS)}"
        )

    segments = _validate_path(law.get("path"))

    has_value = "value" in law
    value = law.get("value")
    if op in _PRESENCE_OPS:
        if has_value:
            raise _fail_input(
                f"law '{law_id}': op '{op}' takes no 'value' — refused, never ignored"
            )
    else:
        if not has_value:
            raise _fail_input(f"law '{law_id}': op '{op}' needs a 'value'")
        if op in _MEMBERSHIP_OPS and not isinstance(value, list):
            raise _fail_input(
                f"law '{law_id}': op '{op}' needs 'value' as a list, "
                f"got {type(value).__name__}"
            )
        if op == "contains" and not isinstance(value, _SCALAR_TYPES):
            raise _fail_input(
                f"law '{law_id}': op 'contains' needs a scalar 'value', "
                f"got {type(value).__name__}"
            )
        if op in _LENGTH_OPS and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise _fail_input(
                f"law '{law_id}': op '{op}' needs 'value' as an int >= 0, got {value!r}"
            )

    return {
        "id": law_id,
        "claim": claim,
        "op": op,
        "segments": segments,
        "has_value": has_value,
        "value": value,
    }


def _resolve(verdict: Dict[str, Any], segments: List[str]) -> Any:
    current: Any = verdict
    for seg in segments:
        if isinstance(current, dict):
            if seg not in current:
                return MISSING
            current = current[seg]
        elif isinstance(current, (list, tuple)):
            if not seg.isdigit():
                return MISSING
            idx = int(seg)
            if idx >= len(current):
                return MISSING
            current = current[idx]
        else:
            return MISSING
    return current


def _observed_repr(observed: Any) -> Any:
    return "<missing>" if observed is MISSING else observed


def _apply(op: str, observed: Any, value: Any) -> Tuple[bool, str]:
    """Apply one op. Returns (held, evidence_note)."""
    if op == "exists":
        return (
            observed is not MISSING,
            "present" if observed is not MISSING else "absent",
        )
    if op == "missing":
        return (observed is MISSING, "absent" if observed is MISSING else "present")

    # Absence never satisfies a positive claim.
    if observed is MISSING:
        return False, "path absent in verdict"

    if op == "==":
        return observed == value, f"observed={observed!r}"
    if op == "!=":
        return observed != value, f"observed={observed!r}"
    if op in ("<", "<=", ">", ">="):
        try:
            if op == "<":
                held = observed < value
            elif op == "<=":
                held = observed <= value
            elif op == ">":
                held = observed > value
            else:
                held = observed >= value
        except TypeError:
            return (
                False,
                f"incomparable: {type(observed).__name__} {op} {type(value).__name__}",
            )
        return held, f"observed={observed!r}"
    if op == "in":
        try:
            held = observed in value
        except TypeError:
            return False, f"unhashable observed {type(observed).__name__}"
        return held, f"observed={observed!r}"
    if op == "not-in":
        try:
            held = observed not in value
        except TypeError:
            return False, f"unhashable observed {type(observed).__name__}"
        return held, f"observed={observed!r}"
    if op == "contains":
        if not isinstance(observed, _CONTAINER_TYPES):
            return False, f"not a container: {type(observed).__name__}"
        try:
            held = value in observed
        except TypeError:
            return False, "containment check failed"
        return held, f"observed={observed!r}"
    if op in _LENGTH_OPS:
        if not isinstance(observed, _CONTAINER_TYPES):
            return False, f"no length: {type(observed).__name__}"
        size = len(observed)
        if op == "len==":
            held = size == value
        elif op == "len>=":
            held = size >= value
        else:
            held = size <= value
        return held, f"len={size}"
    raise AssertionError(f"unreachable op {op!r}")  # validated earlier


def _plumbline(inputs: Dict[str, Any]) -> EngineResult:
    verdict_in = inputs.get("verdict")
    laws_in = inputs.get("laws")
    max_laws = inputs.get("max_laws", _DEFAULT_MAX_LAWS)

    if not isinstance(verdict_in, dict):
        raise _fail_input("'verdict' must be a dict")
    if not isinstance(laws_in, list) or not laws_in:
        raise _fail_input(
            "'laws' must declare at least one law — "
            "a plumb line with no wall proves nothing"
        )
    if isinstance(max_laws, bool) or not isinstance(max_laws, int) or max_laws < 1:
        raise _fail_input("'max_laws' must be an int >= 1")
    if len(laws_in) > max_laws:
        raise _fail_input(
            f"{len(laws_in)} laws exceed max_laws={max_laws}; "
            "refused rather than an unbounded run"
        )

    seen_ids: set = set()
    laws = [_validate_law(law, seen_ids) for law in laws_in]

    trace: List[str] = [f"hanging {len(laws)} law(s) against the verdict"]
    results: List[Dict[str, Any]] = []
    for law in laws:
        observed = _resolve(verdict_in, law["segments"])
        held, note = _apply(law["op"], observed, law["value"])
        mark = "HELD" if held else "BROKEN"
        trace.append(
            f"law '{law['id']}': {mark} — {law['claim']} "
            f"(observed={_observed_repr(observed)!r}; {note})"
        )
        results.append(
            {
                "id": law["id"],
                "claim": law["claim"],
                "op": law["op"],
                "held": held,
                "observed": _observed_repr(observed),
                "evidence": note,
            }
        )

    held_count = sum(1 for r in results if r["held"])
    law_count = len(results)
    all_held = held_count == law_count
    confidence = round(held_count / law_count, 3)
    trace.append(
        f"{held_count}/{law_count} laws held — "
        f"verdict {'HOLDS' if all_held else 'BROKEN'}"
    )

    verdict = {
        "status": "held" if all_held else "broken",
        "law_count": law_count,
        "held_count": held_count,
        "broken_count": law_count - held_count,
        "laws": results,
    }
    return EngineResult(
        engine_id="plumbline", verdict=verdict, confidence=confidence, trace=trace
    )


PLUMBLINE_ENGINE = Engine(
    id="plumbline",
    name="Plumbline",
    description=(
        "The invariant-guard: hang declared laws against a verdict and "
        "report which held, which broke, and the exact evidence. Laws are "
        "declarative rules (path + op + value) — no code, no eval. Absence "
        "never satisfies a positive claim."
    ),
    version="1.0.0",
    required=("verdict", "laws"),
    schema={
        "verdict": "dict under test (JSON-ish)",
        "laws": "non-empty list[{id, claim, path, op, value?}]",
        "max_laws": "int >= 1, default 64 (unbounded-run guard)",
    },
    risk="info",
    handler=_plumbline,
)

registry.register(PLUMBLINE_ENGINE)


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    try:
        register(
            "engines-plumbline",
            provides=("engines.plumbline.guard",),
            requires=(),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()
