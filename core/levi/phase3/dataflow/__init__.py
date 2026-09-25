"""dataflow — firing-rule execution semantics. WORKING TITLE.

Naming is Chauncey's; this name is never canon.  Plans become graphs;
nodes fire when their inputs arrive, ties broken by node-id order —
self-scheduling, deterministic, replayable.
"""

from .graph import (
    DataflowFault,
    ExecutionTrace,
    Graph,
    Node,
    PlanList,
    TestDoubleDispatch,
    build_graph,
    execute,
    replay,
    validate,
)

__all__ = [
    "DataflowFault",
    "ExecutionTrace",
    "Graph",
    "Node",
    "PlanList",
    "TestDoubleDispatch",
    "build_graph",
    "execute",
    "replay",
    "validate",
]
