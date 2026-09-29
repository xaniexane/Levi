"""LEVI customizations — user-tunable confidence thresholds.

Engines and daemons carry numeric gates (a hysteresis band, a confidence
floor, a digest cap). Those gates are not constants: the keeper tunes them
to the machine's posture, and every tunable gate lives here, in one
owner-only file, with a named range and a sane default.

Storage is local-first: ``~/.levi/customizations/thresholds.json`` holds
only *overrides* — the file is 0o600 in a 0o700 dir, written atomically.
Defaults come from the gate table below; resetting a gate deletes its
override, never invents a value.

Everything is deny-closed: unknown gates, wrong types, and out-of-range
values are refused with a named error, never coerced. A corrupt store file
is refused too — a customization layer that silently falls back to
defaults would be lying about the keeper's intent.

Usage::

    from levi.customizations import thresholds

    thresholds.set("keel.band", 0.15)      # keeper widens the hysteresis
    thresholds.get("keel.band")            # 0.15
    thresholds.reset("keel.band")          # back to the default
    for gate in thresholds.list_gates():    # every gate, effective value
        print(gate["name"], gate["value"], gate["source"])

Run it: ``python -m levi.customizations.thresholds list``
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List

DEFAULT_STATE_DIR = Path.home() / ".levi" / "customizations"
DEFAULT_STORE = DEFAULT_STATE_DIR / "thresholds.json"


class ThresholdsError(Exception):
    """A named refusal: unknown gate, bad value, or unreadable store."""


@dataclass(frozen=True)
class Gate:
    """One tunable gate: its type, range, and the value it ships with."""

    name: str
    kind: str  # "float" or "int"
    minimum: float
    maximum: float
    default: float
    unit: str
    description: str


_GATES: Dict[str, Gate] = {
    "keel.band": Gate(
        name="keel.band",
        kind="float",
        minimum=0.0,
        maximum=1.0,
        default=0.10,
        unit="score",
        description="Keel engine hysteresis margin: a challenger must clear "
        "line_score + band to count toward a tack.",
    ),
    "keel.persistence": Gate(
        name="keel.persistence",
        kind="int",
        minimum=1,
        maximum=64,
        default=3,
        unit="readings",
        description="Keel engine: consecutive band-clearing readings required "
        "before the line tacks.",
    ),
    "router.min_confidence": Gate(
        name="router.min_confidence",
        kind="float",
        minimum=0.0,
        maximum=1.0,
        default=0.35,
        unit="confidence",
        description="Confidence floor for confidence-based routing: below "
        "this, work is held for the keeper rather than auto-routed.",
    ),
    "digest.max_items": Gate(
        name="digest.max_items",
        kind="int",
        minimum=1,
        maximum=200,
        default=25,
        unit="items",
        description="Cap on digest/attention lists a daemon shows the keeper "
        "in one pass.",
    ),
}


def _state_dir(store: Path) -> Path:
    return store.parent


def _ensure_dirs(store: Path) -> None:
    _state_dir(store).mkdir(mode=0o700, parents=True, exist_ok=True)


def _read_overrides(store: Path) -> Dict[str, Any]:
    if not store.exists():
        return {}
    try:
        raw = store.read_text(encoding="utf-8")
    except OSError as exc:
        raise ThresholdsError(f"cannot read thresholds store: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ThresholdsError(
            f"thresholds store is corrupt (not JSON): {exc} — refusing, "
            "never silently defaulting"
        ) from exc
    if not isinstance(data, dict):
        raise ThresholdsError("thresholds store must be a JSON object of gate → value")
    return data


def _validate(gate: Gate, value: Any) -> float:
    if isinstance(value, bool):
        raise ThresholdsError(f"gate {gate.name!r} needs a {gate.kind}, got bool")
    if gate.kind == "int":
        if not isinstance(value, int):
            raise ThresholdsError(
                f"gate {gate.name!r} needs an int, got {type(value).__name__}"
            )
    elif gate.kind == "float":
        if not isinstance(value, (int, float)):
            raise ThresholdsError(
                f"gate {gate.name!r} needs a number, got {type(value).__name__}"
            )
        value = float(value)
    else:  # pragma: no cover - gate table is closed
        raise ThresholdsError(f"gate {gate.name!r} has an unknown kind")
    if not gate.minimum <= value <= gate.maximum:
        raise ThresholdsError(
            f"gate {gate.name!r} must be in [{gate.minimum}, {gate.maximum}], "
            f"got {value!r}"
        )
    return value


def _write_overrides(store: Path, overrides: Dict[str, Any]) -> None:
    _ensure_dirs(store)
    fd, tmp = tempfile.mkstemp(
        dir=str(_state_dir(store)), prefix=".thresholds-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(overrides, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, store)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def get_gate(name: str) -> Gate:
    """Return the gate definition, or refuse an unknown name."""
    try:
        return _GATES[name]
    except KeyError:
        raise ThresholdsError(
            f"unknown gate {name!r}; known: " + ", ".join(sorted(_GATES))
        ) from None


def get(name: str, store: Path = DEFAULT_STORE) -> float:
    """Effective value: the keeper's override, else the gate's default."""
    gate = get_gate(name)
    overrides = _read_overrides(store)
    if name in overrides:
        return _validate(gate, overrides[name])
    return gate.default


def set(name: str, value: Any, store: Path = DEFAULT_STORE) -> float:
    """Set an override after validation; returns the stored value."""
    gate = get_gate(name)
    checked = _validate(gate, value)
    overrides = _read_overrides(store)
    overrides[name] = checked
    _write_overrides(store, overrides)
    return checked


def reset(name: str, store: Path = DEFAULT_STORE) -> float:
    """Remove the override, restoring the default. Returns the default."""
    gate = get_gate(name)
    overrides = _read_overrides(store)
    overrides.pop(name, None)
    _write_overrides(store, overrides)
    return gate.default


def list_gates(store: Path = DEFAULT_STORE) -> List[Dict[str, Any]]:
    """Every gate with its effective value and where it came from."""
    overrides = _read_overrides(store)
    rows: List[Dict[str, Any]] = []
    for name in sorted(_GATES):
        gate = _GATES[name]
        if name in overrides:
            rows.append(
                {
                    "name": name,
                    "value": _validate(gate, overrides[name]),
                    "source": "override",
                    "default": gate.default,
                    "range": [gate.minimum, gate.maximum],
                    "unit": gate.unit,
                    "description": gate.description,
                }
            )
        else:
            rows.append(
                {
                    "name": name,
                    "value": gate.default,
                    "source": "default",
                    "default": gate.default,
                    "range": [gate.minimum, gate.maximum],
                    "unit": gate.unit,
                    "description": gate.description,
                }
            )
    return rows


def iter_known() -> Iterator[str]:
    """Yield the known gate names, sorted."""
    yield from sorted(_GATES)


def _cli(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="levi.customizations.thresholds",
        description="Keeper-tunable numeric gates (owner-only store).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="show every gate, value, and source")
    p_get = sub.add_parser("get", help="show one gate's effective value")
    p_get.add_argument("name")
    p_set = sub.add_parser("set", help="set a gate override")
    p_set.add_argument("name")
    p_set.add_argument("value")
    p_reset = sub.add_parser("reset", help="remove an override (restore default)")
    p_reset.add_argument("name")
    args = parser.parse_args(argv)

    try:
        if args.cmd == "list":
            for row in list_gates():
                print(
                    f"{row['name']}: {row['value']} ({row['source']}) "
                    f"[{row['range'][0]}..{row['range'][1]} {row['unit']}]"
                )
        elif args.cmd == "get":
            print(get(args.name))
        elif args.cmd == "set":
            raw = args.value
            try:
                value: Any = int(raw)
            except ValueError:
                try:
                    value = float(raw)
                except ValueError:
                    value = raw
            print(set(args.name, value))
        elif args.cmd == "reset":
            print(reset(args.name))
    except ThresholdsError as exc:
        print(f"refused: {exc}")
        return 2
    return 0


def main(argv: List[str] | None = None) -> int:
    import sys

    return _cli(sys.argv[1:] if argv is None else argv)


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    try:
        register(
            "customizations-thresholds",
            provides=(
                "customizations.thresholds.get",
                "customizations.thresholds.set",
                "customizations.thresholds.reset",
                "customizations.thresholds.list",
                "customizations.thresholds.cli",
            ),
            requires=(),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()


if __name__ == "__main__":
    raise SystemExit(main())
