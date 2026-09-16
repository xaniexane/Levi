"""de Bono's water logic & flowscapes: perception as flow, not boxes.

Origin: Edward de Bono's 1990s *water logic* — an alternative to
Aristotelian "rock logic" (identity, categories, is/is-not). Water logic
asks "what does this *lead to*?" — mapping the *flows* of association and
consequence from a starting point, rendered as a **flowscape**: a diagram
of where attention flows.

What it is in LEVI: the assistant draws flowscapes of your reasoning on
demand. "Trace where this assumption leads" produces a directed map of
consequences and second-order effects — and highlights the channels you
*always* flow down (your ruts) versus the ones you never visit (dead ends
and neglected branches).

Honesty label: USEFUL PATTERN — de Bono's commercial empire outran his
evidence; treat the tools as prompts, not a validated science of thought.
Water logic's value is as a *discipline of attention*, not a logic in the
formal sense.

Deny-closed inputs: flows between unknown statements, empty statements,
duplicate statements, and self-loops are rejected with ValueError.
"""

from __future__ import annotations

from collections import Counter, deque

__all__ = ["Flowscape"]


class Flowscape:
    """Statements as pools; 'what does this lead to?' as flows between them."""

    def __init__(self, topic: str = ""):
        if not isinstance(topic, str):
            raise ValueError("topic must be a string")
        self.topic = topic
        self._statements: dict[str, str] = {}  # id -> text
        self._flows: dict[str, list[tuple[str, str]]] = {}  # from_id -> [(to_id, note)]
        self._next_id = 1

    # -- building the flowscape --------------------------------------------------
    @staticmethod
    def _clean(text: str, kind: str) -> str:
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{kind} must be a non-empty string")
        return text.strip()

    def add_statement(self, text: str) -> str:
        """Add a perception-pool (a statement, assumption, or observation)."""
        text = self._clean(text, "statement")
        if any(t.lower() == text.lower() for t in self._statements.values()):
            raise ValueError(f"duplicate statement: {text!r}")
        sid = f"S{self._next_id}"
        self._next_id += 1
        self._statements[sid] = text
        self._flows[sid] = []
        return sid

    def _check(self, sid: str) -> None:
        if sid not in self._statements:
            raise ValueError(f"unknown statement: {sid!r}")

    def flow(self, from_id: str, to_id: str, note: str = "") -> None:
        """Record that thinking flows from one statement to another.

        The note answers de Bono's question: *what does this lead to, and why?*
        """
        self._check(from_id)
        self._check(to_id)
        if from_id == to_id:
            raise ValueError("a statement cannot flow into itself")
        if any(t == to_id for t, _ in self._flows[from_id]):
            raise ValueError(f"flow {from_id} -> {to_id} already recorded")
        self._flows[from_id].append((to_id, note or ""))

    # -- tracing -------------------------------------------------------------------
    def trace(self, start_id: str, max_depth: int = 6) -> list[list[str]]:
        """All consequence-paths flowing out of ``start_id`` (BFS, cycle-safe)."""
        self._check(start_id)
        if max_depth < 1:
            raise ValueError("max_depth must be >= 1")
        paths: list[list[str]] = []
        queue: deque[tuple[str, list[str]]] = deque([(start_id, [start_id])])
        while queue:
            node, path = queue.popleft()
            children = [t for t, _ in self._flows[node] if t not in path]
            if not children or len(path) > max_depth:
                paths.append(path)
            else:
                for child in children:
                    queue.append((child, path + [child]))
        return paths

    def channel_strength(self) -> list[dict]:
        """Where attention flows: statements ranked by incoming flows.

        The top of this list is your rut — the perceptual pool everything
        drains into.
        """
        incoming: Counter[str] = Counter()
        for frm, tos in self._flows.items():
            for to, _ in tos:
                incoming[to] += 1
        return [
            {
                "id": sid,
                "statement": self._statements[sid],
                "incoming": incoming[sid],
                "outgoing": len(self._flows[sid]),
            }
            for sid in sorted(self._statements, key=lambda s: (-incoming[s], s))
        ]

    def ruts(self, top_n: int = 3) -> list[dict]:
        """Your habitual channels: the most-drained-into pools."""
        if top_n < 1:
            raise ValueError("top_n must be >= 1")
        return self.channel_strength()[:top_n]

    def dead_ends(self) -> list[dict]:
        """Statements where thinking stops: pools with no outgoing flows."""
        return [
            {"id": sid, "statement": text}
            for sid, text in self._statements.items()
            if not self._flows[sid]
        ]

    def neglected(self) -> list[dict]:
        """Statements nothing flows into: the branches perception never visits."""
        targeted = {to for tos in self._flows.values() for to, _ in tos}
        return [
            {"id": sid, "statement": text}
            for sid, text in self._statements.items()
            if sid not in targeted
        ]

    def report(self, start_id: str, max_depth: int = 6) -> dict:
        """The full flowscape reading: paths, ruts, dead ends, neglected."""
        paths = self.trace(start_id, max_depth=max_depth)
        return {
            "topic": self.topic,
            "start": self._statements[start_id],
            "paths": [[self._statements[s] for s in p] for p in paths],
            "path_count": len(paths),
            "max_path_length": max((len(p) for p in paths), default=0),
            "ruts": self.ruts(),
            "dead_ends": self.dead_ends(),
            "neglected": self.neglected(),
            "reading": (
                f"{len(paths)} consequence-path(s) from the start; "
                f"your rut is {self.ruts(1)[0]['statement']!r}; "
                f"{len(self.dead_ends())} place(s) where thinking stops; "
                f"{len(self.neglected())} statement(s) perception never visits."
                if self._statements
                else "empty flowscape"
            ),
        }
