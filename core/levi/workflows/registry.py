"""Registry of flagship cross-module workflows (Megazord axis 5).

The CLI worker depends on exactly this contract::

    list_workflows() -> list[dict]   # each: name, summary, steps
    run_workflow(name, home=None, **kwargs) -> dict
        # result: workflow, ok, started_at, finished_at, steps, artifacts

Unknown workflow name -> ValueError.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

_WORKFLOWS: Dict[str, Dict[str, Any]] = {}


def register(name: str, summary: str, steps: List[str],
             runner: Callable[..., Dict[str, Any]]) -> None:
    if not name or not isinstance(name, str):
        raise ValueError("register: name must be a non-empty string")
    if not callable(runner):
        raise ValueError("register: runner must be callable")
    _WORKFLOWS[name] = {
        "name": name,
        "summary": summary,
        "steps": list(steps),
        "runner": runner,
    }


def list_workflows() -> List[Dict[str, Any]]:
    return [
        {"name": w["name"], "summary": w["summary"], "steps": list(w["steps"])}
        for w in _WORKFLOWS.values()
    ]


def run_workflow(name: str, home: Optional[Any] = None,
                 **kwargs) -> Dict[str, Any]:
    entry = _WORKFLOWS.get(name)
    if entry is None:
        raise ValueError(
            "unknown workflow %r (known: %s)"
            % (name, ", ".join(sorted(_WORKFLOWS)) or "none")
        )
    return entry["runner"](home=home, **kwargs)
