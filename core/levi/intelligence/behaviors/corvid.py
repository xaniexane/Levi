"""Corvid tool planning — multi-step tool manufacture (class CRV, mandella).

Real mechanism: New Caledonian crows manufacture hooked tools and chain
tool uses (use a short stick to reach a long stick to reach food) —
planning several steps ahead under uncertainty. Translated: breadth-first
search over (world-state, tools-held) that stakes the plan on the first
tool that unlocks the next, before the food is reachable.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional


@dataclass(frozen=True)
class ToolWorld:
    """reachable: what the crow can already touch -> tool that gets it."""

    reachable: FrozenSet[str] = field(default_factory=frozenset)
    tools: FrozenSet[str] = field(default_factory=frozenset)


# tool -> what it unlocks (the crow's known physics)
TOOL_PHYSICS: Dict[str, FrozenSet[str]] = {
    "short_stick": frozenset({"long_stick", "hook_wire"}),
    "long_stick": frozenset({"food_grub", "food_nut"}),
    "hook_wire": frozenset({"food_grub"}),
    "stone": frozenset({"cracked_nut"}),
}


def plan_tool_chain(
    start: ToolWorld, goal: str, max_depth: int = 4
) -> Optional[List[str]]:
    """BFS for the shortest tool-use chain reaching `goal`.

    Returns the ordered tool names, or None if unreachable in depth.
    """
    seen = {(start.reachable, start.tools)}
    queue = deque([(start, [])])
    _tool_names = set(TOOL_PHYSICS)
    while queue:
        world, chain = queue.popleft()
        if goal in world.reachable:
            return chain
        if len(chain) >= max_depth:
            continue
        for tool in world.tools:
            unlocks = TOOL_PHYSICS.get(tool, frozenset())
            new_reach = world.reachable | unlocks
            new_tools = world.tools | (unlocks & _tool_names)  # pick up tools
            key = (new_reach, new_tools)
            if key not in seen:
                seen.add(key)
                queue.append((ToolWorld(new_reach, new_tools), chain + [tool]))
    return None
