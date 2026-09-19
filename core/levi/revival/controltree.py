"""LEVI's nested control hierarchy: decompose down, fuse up.

Studied from: revival-50-more-20260916-0009/report-part2.md (§47).

The studied mechanism organizes control as a tree of nodes. Each level
*decomposes* tasks downward into finer pieces for its children and *fuses*
status feedback upward into a coarser picture for its parent. Levels are
distinguished by planning horizon — the higher the node, the longer the
horizon it plans over. Every node is the same triple: behavior generation
(decide what to do), world modeling (track what is true), value judgment
(say how it went).

LEVI-native remix: ``ControlNode`` carries a horizon rank from
``HORIZON_ORDER`` (children must plan over strictly shorter horizons than
their parent — the hierarchy is honest about granularity), the
generate/model/judge triple as callables, and ``run()`` which decomposes a
task down to the leaves and fuses statuses back up into one verdict.

Honesty: LOAD-BEARING as a decomposition/fusion *structure*. The default
behaviors are deliberately plain (split a task per child; verdict nominal
iff every child reports done) — the intelligence lives in the callables
you plug in, not in the tree. In-memory, single-process, stdlib only, no
network.
"""

ORIGIN = "levi-revival/controltree"

# Planning horizons, coarse -> fine. A child must rank strictly below its
# parent: finer granularity, shorter horizon. That is the whole discipline
# of the tree, stated as data.
HORIZON_ORDER = {
    "mission": 3,  # why: the campaign, the season
    "phase": 2,  # what: this stretch of the work
    "action": 1,  # how: the next concrete moves
    "reflex": 0,  # now: immediate execution
}


def _default_generate(task, n_children):
    if n_children == 0:
        return [task]
    return [f"{task} :: part {i + 1}/{n_children}" for i in range(n_children)]


def _default_model(world, statuses):
    world["last_children"] = [s["node"] for s in statuses]
    world["done"] = sum(1 for s in statuses if s.get("done"))
    world["total"] = len(statuses)
    return world


def _default_judge(statuses):
    if not statuses:
        return "idle"
    return "nominal" if all(s.get("done") for s in statuses) else "degraded"


class ControlNode:
    """One node: {behavior generation, world modeling, value judgment}."""

    def __init__(self, name, horizon="action", generate=None, model=None, judge=None):
        if horizon not in HORIZON_ORDER:
            raise KeyError(
                f"unknown horizon {horizon!r}; choose from {sorted(HORIZON_ORDER)}"
            )
        self.name = name
        self.horizon = horizon
        self.children = []
        self.world = {}  # this node's model of the world below it
        self.generate = generate or (lambda task, n: _default_generate(task, n))
        self.model = model or _default_model
        self.judge = judge or _default_judge

    def add_child(self, node):
        """Attach a child; its horizon must be strictly finer than mine."""
        if HORIZON_ORDER[node.horizon] >= HORIZON_ORDER[self.horizon]:
            raise ValueError(
                f"child {node.name!r} horizon {node.horizon!r} must be finer "
                f"than parent {self.name!r} horizon {self.horizon!r}"
            )
        self.children.append(node)
        return node

    @property
    def is_leaf(self):
        return not self.children

    def run(self, task):
        """Decompose the task downward, fuse status upward, return a report."""
        if self.is_leaf:
            # A leaf executes: behavior generation produces the act itself.
            acts = self.generate(task, 0)
            report = {
                "node": self.name,
                "horizon": self.horizon,
                "task": task,
                "acts": acts,
                "done": True,
                "verdict": self.judge([{"done": True}]),
            }
            self.model(self.world, [{"node": self.name, "done": True}])
            return report
        # Decompose: this level's behavior generation splits the task.
        subtasks = self.generate(task, len(self.children))
        child_reports = [
            child.run(sub) for child, sub in zip(self.children, subtasks, strict=False)
        ]
        # Fuse: model the world from what came back, then judge it.
        self.model(self.world, child_reports)
        verdict = self.judge(child_reports)
        done = all(c.get("done", False) for c in child_reports)
        return {
            "node": self.name,
            "horizon": self.horizon,
            "task": task,
            "verdict": verdict,
            "done": done,
            "children": child_reports,
        }

    def depth(self):
        if self.is_leaf:
            return 1
        return 1 + max(c.depth() for c in self.children)
