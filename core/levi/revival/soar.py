"""revival/soar.py — Soar-style impasse -> subgoal -> chunking for LEVI agents.

Revival of: the Soar cognitive architecture (Laird, Newell & Rosenbloom,
1987) — specifically its impasse/subgoaling mechanism and *chunking*.

Why it matters: when an agent hits an impasse (no operator applies, or several
tie), Soar creates a subgoal, deliberates its way out, and then *chunks* the
successful deliberation trace into a reusable production rule. Next time a
matching impasse arises, the chunk fires immediately — deliberation compiles
into recognition. For LEVI, this means expensive multi-step reasoning can be
cached as procedures instead of re-derived every time.

LEVI adaptation:
- ``Deliberation`` records a trace of ``(state, operator, result)`` steps
  toward a goal. On success, ``chunk()`` generalizes the trace into a
  ``Procedure``.
- Variable abstraction is a DOCUMENTED HEURISTIC: tokens that look like
  constants — numbers, quoted strings, identifiers containing digits (``v3``,
  ``node-2``) — are replaced by variables ``$x1, $x2, ...`` in order of first
  appearance in the goal. Everything else stays literal. This is deliberately
  conservative: under-generalization (a chunk that only fires on near-identical
  goals) is safer than over-generalization (a chunk that fires wrongly).
- ``ProcedureLibrary`` stores procedures keyed by goal pattern, persisted as
  JSON, with ``recall(goal)`` returning the best-scoring match plus variable
  bindings. Scoring: all literal tokens of the pattern must match the goal in
  order; variables bind to the corresponding goal tokens (consistently — a
  variable bound twice to different values rejects the match).
- ``instantiate(bindings)`` replays the procedure concretely.

Honest limits (read before trusting a chunk):
- Chunking here is heuristic generalization, not sound inference. A chunk is a
  cached guess: it replays *what worked once*, with constants abstracted by a
  regex. It does not verify preconditions hold in the new situation.
- Variables abstract only constant-looking tokens; a chunk will NOT generalize
  across different plain-word vocabulary (``"restart the api"`` won't match
  ``"restart the web"`` — by design, conservative).
- Recall is token-positional, not semantic. Two goals that mean the same thing
  with different wording will not match.
- Procedures have no side-effect model: replaying a chunk that ran ``rm -rf``
  in deliberation would replay ``rm -rf``. Chunks must only be replayed through
  an executor that enforces LEVI's own safety policy (Plan->Preview->Permission
  ->Execute->Verify->Receipt); this module never executes anything itself.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_VAR_RE = re.compile(r"^\$x\d+$")

# Heuristic: what counts as a "constant" worth abstracting into a variable.
# Numbers, quoted strings, and identifiers containing digits (v3, node-2, api7).
_CONSTANT_RE = re.compile(
    r"^(?:\d[\d.,]*|'[^']*'|\"[^\"]*\"|[A-Za-z]*\d[\w-]*|[\w-]*\d[\w-]*)$"
)

_STRIP_EDGE = ".,;:!?()[]{}"


def _tokens(text: str) -> List[str]:
    return [t.strip(_STRIP_EDGE) for t in re.findall(r"\S+", text)]


def _is_constant(token: str) -> bool:
    return bool(token) and bool(_CONSTANT_RE.match(token))


@dataclass
class Step:
    state: str
    operator: str
    result: str


@dataclass
class Procedure:
    """A chunked deliberation: goal pattern + generalized steps."""

    goal_pattern: str
    steps: List[Dict[str, str]]  # each: {"operator": ..., "result": ...}
    variables: List[str]
    provenance: str = ""
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_pattern": self.goal_pattern,
            "steps": self.steps,
            "variables": self.variables,
            "provenance": self.provenance,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Procedure":
        return cls(
            goal_pattern=d["goal_pattern"],
            steps=d["steps"],
            variables=d["variables"],
            provenance=d.get("provenance", ""),
            created_at=d.get("created_at", 0.0),
        )

    def instantiate(self, bindings: Dict[str, str]) -> List[Dict[str, str]]:
        """Substitute bindings into the generalized steps."""
        out = []
        for step in self.steps:
            out.append({
                k: _substitute(v, bindings) for k, v in step.items()
            })
        return out


def _substitute(text: str, bindings: Dict[str, str]) -> str:
    toks = _tokens(text)
    return " ".join(bindings.get(t, t) for t in toks)


class Deliberation:
    """Records an impasse-driven deliberation trace toward a goal."""

    def __init__(self, goal: str, clock: Callable[[], float] = time.time) -> None:
        if not goal or not isinstance(goal, str):
            raise ValueError("goal must be a non-empty string")
        self.goal = goal
        self._clock = clock
        self.steps: List[Step] = []
        self._outcome: Optional[bool] = None

    def record(self, state: str, operator: str, result: str) -> None:
        if self._outcome is not None:
            raise RuntimeError("deliberation already concluded")
        for label, v in (("state", state), ("operator", operator), ("result", result)):
            if not v or not isinstance(v, str):
                raise ValueError(f"{label} must be a non-empty string")
        self.steps.append(Step(state, operator, result))

    def succeed(self) -> None:
        self._outcome = True

    def fail(self) -> None:
        self._outcome = False

    @property
    def succeeded(self) -> Optional[bool]:
        return self._outcome

    def chunk(self, provenance: str = "") -> Procedure:
        """Compile a successful trace into a generalized Procedure.

        Raises if the deliberation did not succeed — only successful
        deliberations become chunks (Soar semantics).
        """
        if self._outcome is not True:
            raise RuntimeError("only a successful deliberation can be chunked")
        if not self.steps:
            raise RuntimeError("cannot chunk an empty trace")

        # 1. Find constants in the goal, in order of first appearance.
        var_for: Dict[str, str] = {}
        variables: List[str] = []
        for tok in _tokens(self.goal):
            if _is_constant(tok) and tok not in var_for:
                var_for[tok] = f"$x{len(variables) + 1}"
                variables.append(var_for[tok])

        # 2. Abstract the same constants everywhere (goal, states, results).
        #    Constants appearing only in steps get variables too, in order of
        #    appearance; they stay schematic at recall (documented limit).
        def generalize(text: str) -> str:
            out = []
            for tok in _tokens(text):
                if _is_constant(tok) and tok not in var_for:
                    var_for[tok] = f"$x{len(variables) + 1}"
                    variables.append(var_for[tok])
                out.append(var_for.get(tok, tok))
            return " ".join(out)

        goal_pattern = generalize(self.goal)
        steps = [
            {"operator": generalize(s.operator), "result": generalize(s.result)}
            for s in self.steps
        ]
        return Procedure(
            goal_pattern=goal_pattern,
            steps=steps,
            variables=list(variables),
            provenance=provenance or f"chunked from goal: {self.goal}",
            created_at=self._clock(),
        )


def _match(pattern: str, goal: str) -> Optional[Tuple[Dict[str, str], float]]:
    """Match a goal pattern against a goal.

    Returns (bindings, score) or None. All literal tokens must match in order
    and position; each variable consumes exactly one goal token and must bind
    consistently. Score = matched literals / total literals (1.0 if none).
    """
    ptoks, gtoks = _tokens(pattern), _tokens(goal)
    if len(ptoks) != len(gtoks):
        return None
    bindings: Dict[str, str] = {}
    lit_total = lit_match = 0
    for p, g in zip(ptoks, gtoks):
        if _VAR_RE.match(p):
            if p in bindings and bindings[p] != g:
                return None
            bindings[p] = g
        else:
            lit_total += 1
            if p == g:
                lit_match += 1
            else:
                return None
    score = lit_match / lit_total if lit_total else 1.0
    return bindings, score


class ProcedureLibrary:
    """Persistent library of chunked procedures, keyed by goal pattern."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._procs: List[Procedure] = []
        self._path = Path(path) if path else None
        if self._path and self._path.exists():
            self.load()

    def add(self, proc: Procedure) -> None:
        if not isinstance(proc, Procedure):
            raise ValueError("can only store Procedure instances")
        self._procs.append(proc)

    def __len__(self) -> int:
        return len(self._procs)

    def recall(
        self, goal: str, threshold: float = 1.0
    ) -> Optional[Tuple[Procedure, Dict[str, str], float]]:
        """Best-matching procedure for a goal, with bindings and score.

        Returns None when nothing meets the threshold. Default threshold 1.0
        means every literal token must match — conservative by design.
        """
        best: Optional[Tuple[Procedure, Dict[str, str], float]] = None
        for proc in self._procs:
            m = _match(proc.goal_pattern, goal)
            if m is None:
                continue
            bindings, score = m
            if score >= threshold and (best is None or score > best[2]):
                best = (proc, bindings, score)
        return best

    def save(self, path: Optional[Path] = None) -> Path:
        dest = Path(path) if path else self._path
        if dest is None:
            raise ValueError("no path: pass one to save() or the constructor")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            json.dumps([p.to_dict() for p in self._procs], indent=2),
            encoding="utf-8",
        )
        self._path = dest
        return dest

    def load(self, path: Optional[Path] = None) -> "ProcedureLibrary":
        src = Path(path) if path else self._path
        if src is None or not src.exists():
            raise ValueError(f"no procedure library at {src}")
        data = json.loads(src.read_text(encoding="utf-8"))
        self._procs = [Procedure.from_dict(d) for d in data]
        self._path = src
        return self


# ------------------------------------------------------------------- demo
def demo() -> Dict[str, Any]:
    """Deliberate once, chunk it, solve a second similar problem from the chunk.

    Problem 1 is solved by explicit deliberation (recorded trace). Problem 2 —
    same shape, different constants — is solved by recall + replay, with no
    new deliberation. A mock executor records the replayed operators; the demo
    never executes anything real.
    """
    lib = ProcedureLibrary()

    # --- problem 1: deliberate from scratch ---
    d = Deliberation("deploy service api version 3")
    d.record("service api version 3 is stopped", "resolve-deps api version 3",
             "deps for api version 3 resolved")
    d.record("deps for api version 3 resolved", "build api version 3",
             "api version 3 built")
    d.record("api version 3 built", "smoke-test api version 3",
             "api version 3 healthy")
    d.succeed()
    proc = d.chunk(provenance="demo: first deployment deliberation")
    lib.add(proc)

    # --- problem 2: same shape, new constants -> recall, no deliberation ---
    goal2 = "deploy service api version 4"
    hit = lib.recall(goal2)
    assert hit is not None, "chunk should fire on the second problem"
    proc2, bindings, score = hit

    executed: List[str] = []
    for step in proc2.instantiate(bindings):
        executed.append(step["operator"])  # mock executor: record only

    return {
        "goal_pattern": proc2.goal_pattern,
        "variables": proc2.variables,
        "goal2": goal2,
        "bindings": bindings,
        "score": score,
        "replayed_operators": executed,
        "deliberated_problem_2": False,
    }


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(demo(), indent=2))
