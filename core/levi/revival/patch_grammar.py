"""Patch/wiring grammar — computation as inspectable arrangement.

Studied from: pre-digital-computation-20260916, report.md
[Cross-entry pattern 2] — patch panels, shaft routing, cam-barrel
programs, quipu multi-channel encoding, nomograph scale geometry.

The mechanism, functionally: computation expressed as a *physical
arrangement* you can see and touch. A patch panel has jacks; a cord
connects an output jack to an input jack; the program is the wiring.
This module captures that pattern as data structures with real
evaluation semantics:

- ``PatchPanel``: named units (add, mul, const, integrator, gain,
  clamp) with input/output jacks; ``cord(src_unit, src_out, dst_unit,
  dst_in)`` wires them; ``run(inputs)`` evaluates topologically and
  returns every output. Cycles are rejected — the wiring is a DAG, the
  way a patch panel's cords visibly are.
- ``CamBarrel``: the cam-barrel program — a rotating drum whose peg
  profile is a stored function of angle: ``set(angle_deg, value)`` cuts
  the cam, ``read(angle_deg)`` follows it with linear interpolation.
  Arbitrary single-input programs as geometry.
- ``Nomograph``: three-scale alignment — given scales x and y and a
  precomputed surface table z(x, y), ``align`` reads z off the chart the
  way a straightedge reads the middle scale. Pure lookup geometry.
- ``Quipu``: multi-channel knot encoding — several cords, each holding
  a knot-encoded integer (clusters of knots = digits). ``encode`` and
  ``decode`` round-trip; ``combine`` merges cords channel-wise.

Honesty: the panel evaluates numerically, not electrically; the cam
interpolates rather than riding a physical follower; the nomograph is
a table lookup wearing scale-geometry clothes. All units are simple
arithmetic — the grammar is the arrangement, exactly as advertised.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple

ORIGIN = "levi-revival/patch-grammar"


class PatchError(Exception):
    """Bad wiring: unknown jack, fan-in collision, or a cycle."""


# ---------------------------------------------------------------------------
# Patch panel
# ---------------------------------------------------------------------------

_UNIT_FNS: Dict[str, Tuple[List[str], List[str], Callable]] = {}


def _unit(name: str, ins: List[str], outs: List[str]):
    def deco(fn: Callable):
        _UNIT_FNS[name] = (ins, outs, fn)
        return fn

    return deco


@_unit("const", [], ["v"])
def _const(ins: Dict[str, float], p: Dict[str, float]) -> Dict[str, float]:
    return {"v": p.get("value", 0.0)}


@_unit("add", ["a", "b"], ["s"])
def _add(ins: Dict[str, float], p: Dict[str, float]) -> Dict[str, float]:
    return {"s": ins["a"] + ins["b"]}


@_unit("mul", ["a", "b"], ["p"])
def _mul(ins: Dict[str, float], p: Dict[str, float]) -> Dict[str, float]:
    return {"p": ins["a"] * ins["b"]}


@_unit("gain", ["x"], ["y"])
def _gain(ins: Dict[str, float], p: Dict[str, float]) -> Dict[str, float]:
    return {"y": ins["x"] * p.get("k", 1.0)}


@_unit("clamp", ["x"], ["y"])
def _clamp(ins: Dict[str, float], p: Dict[str, float]) -> Dict[str, float]:
    lo, hi = p.get("lo", 0.0), p.get("hi", 1.0)
    return {"y": min(hi, max(lo, ins["x"]))}


@_unit("integrator", ["x"], ["y"])
def _integrator(ins: Dict[str, float], p: Dict[str, float]) -> Dict[str, float]:
    # Discrete accumulation: state lives on the unit across run() calls,
    # the way a shaft integrator holds its angle between readings.
    state = p.setdefault("_state", 0.0)
    state += ins["x"] * p.get("dt", 1.0)
    p["_state"] = state
    return {"y": state}


class PatchPanel:
    """A wired program: units + cords, evaluated topologically."""

    def __init__(self, name: str = "panel"):
        self.name = name
        self._units: Dict[str, Dict] = {}  # name -> {kind, params}
        self._cords: List[Tuple[str, str, str, str]] = []

    def place(self, unit: str, kind: str, **params: float) -> "PatchPanel":
        """Bolt a unit of ``kind`` onto the panel as ``unit``."""
        if unit in self._units:
            raise PatchError(f"unit {unit!r} already placed")
        if kind not in _UNIT_FNS:
            raise PatchError(f"unknown unit kind {kind!r}")
        self._units[unit] = {"kind": kind, "params": dict(params)}
        return self

    def cord(self, src: str, src_out: str, dst: str, dst_in: str) -> "PatchPanel":
        """Plug a cord from an output jack to an input jack."""
        for u, _jack in ((src, src_out), (dst, dst_in)):
            if u not in self._units:
                raise PatchError(f"unknown unit {u!r}")
        s_ins, s_outs, _ = _UNIT_FNS[self._units[src]["kind"]]
        d_ins, d_outs, _ = _UNIT_FNS[self._units[dst]["kind"]]
        if src_out not in s_outs:
            raise PatchError(f"{src!r} has no output jack {src_out!r}")
        if dst_in not in d_ins:
            raise PatchError(f"{dst!r} has no input jack {dst_in!r}")
        if any(c[2] == dst and c[3] == dst_in for c in self._cords):
            raise PatchError(f"input jack {dst}.{dst_in} already patched")
        self._cords.append((src, src_out, dst, dst_in))
        return self

    def _order(self) -> List[str]:
        deps: Dict[str, set] = {u: set() for u in self._units}
        for s, _, d, _ in self._cords:
            deps[d].add(s)
        order: List[str] = []
        done: set = set()
        while len(order) < len(self._units):
            ready = sorted(u for u in self._units if u not in done and deps[u] <= done)
            if not ready:
                raise PatchError("wiring has a cycle — cords must form a DAG")
            done.update(ready)
            order.extend(ready)
        return order

    def run(
        self, inputs: Dict[str, Dict[str, float]] | None = None
    ) -> Dict[str, Dict[str, float]]:
        """Evaluate the wiring; returns {unit: {out_jack: value}}."""
        inputs = inputs or {}
        driven: Dict[Tuple[str, str], Tuple[str, str]] = {
            (d, di): (s, so) for s, so, d, di in self._cords
        }
        results: Dict[str, Dict[str, float]] = {}
        for u in self._order():
            ins_names, _, fn = _UNIT_FNS[self._units[u]["kind"]]
            ins: Dict[str, float] = {}
            for jack in ins_names:
                if (u, jack) in driven:
                    su, so = driven[(u, jack)]
                    ins[jack] = results[su][so]
                elif u in inputs and jack in inputs[u]:
                    ins[jack] = inputs[u][jack]
                else:
                    raise PatchError(f"input jack {u}.{jack} unpatched")
            results[u] = fn(ins, self._units[u]["params"])
        return results

    def wiring_diagram(self) -> str:
        """The program as an inspectable list of cords."""
        lines = [f"patch panel {self.name!r}:"]
        for u, spec in sorted(self._units.items()):
            lines.append(f"  [{u}] {spec['kind']} {spec['params']}")
        for s, so, d, di in self._cords:
            lines.append(f"  cord: {s}.{so} -> {d}.{di}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cam barrel: program as cut geometry
# ---------------------------------------------------------------------------


class CamBarrel:
    """A cam-barrel program: function of shaft angle, cut as pegs."""

    def __init__(self, resolution_deg: float = 1.0):
        if resolution_deg <= 0 or resolution_deg > 360:
            raise ValueError("resolution_deg must be in (0, 360]")
        self.res = resolution_deg
        self._pegs: Dict[float, float] = {}

    def cut(self, angle_deg: float, value: float) -> "CamBarrel":
        """Cut a peg at ``angle_deg`` holding ``value``."""
        self._pegs[float(angle_deg) % 360.0] = float(value)
        return self

    def read(self, angle_deg: float) -> float:
        """Follower reading at ``angle_deg`` (linear interpolation)."""
        if not self._pegs:
            raise PatchError("cam has no pegs cut")
        a = float(angle_deg) % 360.0
        if a in self._pegs:
            return self._pegs[a]
        keys = sorted(self._pegs)
        lo = max(k for k in keys if k <= a) if any(k <= a for k in keys) else keys[-1]
        hi = min(k for k in keys if k >= a) if any(k >= a for k in keys) else keys[0]
        if lo == hi:
            return self._pegs[lo]
        span = (hi - lo) % 360.0 or 360.0
        t = ((a - lo) % 360.0) / span
        return self._pegs[lo] * (1.0 - t) + self._pegs[hi] * t


# ---------------------------------------------------------------------------
# Nomograph: scale geometry as lookup
# ---------------------------------------------------------------------------


class Nomograph:
    """Three-scale alignment chart: z = F(x, y) read off a surface table."""

    def __init__(self, xs: List[float], ys: List[float], table: List[List[float]]):
        if len(table) != len(xs) or any(len(r) != len(ys) for r in table):
            raise ValueError("table must be len(xs) x len(ys)")
        if len(xs) < 2 or len(ys) < 2:
            raise ValueError("need at least 2 x-points and 2 y-points")
        self.xs, self.ys, self.table = xs, ys, table

    def _locate(self, grid: List[float], v: float) -> Tuple[int, float]:
        if v <= grid[0]:
            return 0, 0.0
        if v >= grid[-1]:
            return len(grid) - 2, 1.0
        for i in range(len(grid) - 1):
            if grid[i] <= v <= grid[i + 1]:
                t = (v - grid[i]) / (grid[i + 1] - grid[i])
                return i, t
        return len(grid) - 2, 1.0  # pragma: no cover

    def align(self, x: float, y: float) -> float:
        """Lay the straightedge across the x and y scales; read z."""
        ix, tx = self._locate(self.xs, x)
        iy, ty = self._locate(self.ys, y)
        t = self.table
        return (
            t[ix][iy] * (1 - tx) * (1 - ty)
            + t[ix + 1][iy] * tx * (1 - ty)
            + t[ix][iy + 1] * (1 - tx) * ty
            + t[ix + 1][iy + 1] * tx * ty
        )


# ---------------------------------------------------------------------------
# Quipu: multi-channel knot encoding
# ---------------------------------------------------------------------------


class Quipu:
    """A bundle of knotted cords; each cord holds a base-10 knot number."""

    def __init__(self):
        self.cords: Dict[str, List[int]] = {}

    def encode(self, channel: str, value: int) -> "Quipu":
        """Knot ``value`` onto ``channel``: digit clusters, ones at the end."""
        if value < 0:
            raise ValueError("quipu knots encode non-negative integers")
        digits = [int(d) for d in str(value)] or [0]
        self.cords[channel] = digits
        return self

    def decode(self, channel: str) -> int:
        """Read the knots back off ``channel``."""
        if channel not in self.cords:
            raise PatchError(f"no cord named {channel!r}")
        return int("".join(str(d) for d in self.cords[channel]))

    def combine(
        self, out: str, op: Callable[[int, int], int], *channels: str
    ) -> "Quipu":
        """Knot a new cord from other channels (e.g. sum across cords)."""
        vals = [self.decode(c) for c in channels]
        acc = vals[0]
        for v in vals[1:]:
            acc = op(acc, v)
        return self.encode(out, acc)

    def channels(self) -> List[str]:
        return sorted(self.cords)


def demo() -> Tuple[float, int]:
    """Wire const->gain->clamp; knot 27 and 15, add them on a third cord."""
    panel = PatchPanel("demo")
    panel.place("src", "const", value=3.0)
    panel.place("amp", "gain", k=4.0)
    panel.place("lim", "clamp", lo=0.0, hi=10.0)
    panel.cord("src", "v", "amp", "x").cord("amp", "y", "lim", "x")
    out = panel.run()["lim"]["y"]
    q = Quipu().encode("a", 27).encode("b", 15)
    q.combine("total", lambda x, y: x + y, "a", "b")
    return out, q.decode("total")
