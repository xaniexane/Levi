"""LEVI's appdict: applications that publish what they can do.

Studied from: catalog (§8) — open scripting dictionaries (functional
description only; no historical claims).

The lesson, reborn as LEVI's own: automation should speak the
application's own language. Every app publishes a machine-readable
*dictionary* — its object model: the *nouns* it understands (note, timer)
with their properties, and the *verbs* it performs (create, start) with
their parameters. A *dispatcher* routes plain command dicts to the right
app and validates each command against that app's published dictionary
before it runs — unknown verbs, nouns, or parameters are refused with
the dictionary held up as the correction. Scripts never poke at
internals; they speak nouns and verbs.

Honesty: LOAD-BEARING, with one stated limit. The "applications" here
are in-process Python objects (a notes app, a timer app), not external
processes — the mechanism (published dictionaries + a validating
dispatcher) is the real thing; the app boundary is not.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List

ORIGIN = "levi-revival/appdict"


class DictionaryError(Exception):
    """A command that doesn't fit the app's published dictionary."""


class App:
    """An application with a published scripting dictionary: nouns (object
    model) and verbs (commands)."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.nouns: Dict[str, Dict[str, Any]] = {}  # noun -> {"properties": [...]}
        self.verbs: Dict[
            str, Dict[str, Any]
        ] = {}  # verb -> {"noun":..,"params":[..],"do":fn}

    def noun(self, name: str, properties: List[str]) -> "App":
        self.nouns[name] = {"properties": list(properties)}
        return self

    def verb(
        self,
        name: str,
        noun: str,
        params: List[str],
        do: Callable[[Dict[str, Any]], Any],
    ) -> "App":
        if noun not in self.nouns:
            raise DictionaryError(
                f"appdict: verb {name!r} targets unknown noun {noun!r}"
            )
        self.verbs[name] = {"noun": noun, "params": list(params), "do": do}
        return self

    def dictionary(self) -> Dict[str, Any]:
        """The machine-readable scripting dictionary this app publishes."""
        return {
            "app": self.name,
            "nouns": {n: dict(spec) for n, spec in self.nouns.items()},
            "verbs": {
                v: {"noun": spec["noun"], "params": spec["params"]}
                for v, spec in self.verbs.items()
            },
        }


class Dispatcher:
    """Routes plain command dicts to apps, validating each against the
    app's own published dictionary first."""

    def __init__(self) -> None:
        self.apps: Dict[str, App] = {}
        self.log: List[Dict[str, Any]] = []

    def register(self, app: App) -> "Dispatcher":
        self.apps[app.name] = app
        return self

    def run(self, command: Dict[str, Any]) -> Any:
        """``{"app": ..., "verb": ..., "noun": ..., "args": {...}}``"""
        app_name = command.get("app")
        app = self.apps.get(app_name)  # type: ignore[arg-type]
        if app is None:
            raise DictionaryError(
                f"appdict: no such app {app_name!r} (known: {sorted(self.apps)})"
            )
        verb_name = command.get("verb")
        spec = app.verbs.get(verb_name)  # type: ignore[arg-type]
        if spec is None:
            raise DictionaryError(
                f"appdict: {app_name!r} has no verb {verb_name!r} "
                f"(it publishes: {sorted(app.verbs)})"
            )
        noun = command.get("noun")
        if noun != spec["noun"]:
            raise DictionaryError(
                f"appdict: verb {verb_name!r} acts on {spec['noun']!r}, not {noun!r}"
            )
        args = command.get("args", {})
        unknown = sorted(set(args) - set(spec["params"]))
        if unknown:
            raise DictionaryError(
                f"appdict: verb {verb_name!r} takes {spec['params']}, not {unknown}"
            )
        result = spec["do"](dict(args))
        self.log.append(
            {"app": app_name, "verb": verb_name, "noun": noun, "args": dict(args)}
        )
        return result


# ---------------------------------------------------------------------------
# Two LEVI apps, speaking their own nouns and verbs
# ---------------------------------------------------------------------------


def make_notes_app() -> App:
    notes: Dict[int, Dict[str, Any]] = {}
    seq = [0]

    def _create(args: Dict[str, Any]) -> Dict[str, Any]:
        seq[0] += 1
        notes[seq[0]] = {
            "id": seq[0],
            "title": args["title"],
            "body": args.get("body", ""),
        }
        return notes[seq[0]]

    def _list(args: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [dict(n) for n in notes.values()]

    def _delete(args: Dict[str, Any]) -> bool:
        return notes.pop(args["id"], None) is not None

    return (
        App("notes")
        .noun("note", ["id", "title", "body"])
        .verb("create", "note", ["title", "body"], _create)
        .verb("list", "note", [], _list)
        .verb("delete", "note", ["id"], _delete)
    )


def make_timer_app() -> App:
    timers: Dict[str, Dict[str, Any]] = {}

    def _start(args: Dict[str, Any]) -> Dict[str, Any]:
        timers[args["name"]] = {
            "name": args["name"],
            "started": time.time(),
            "stopped": None,
        }
        return {"name": args["name"], "running": True}

    def _stop(args: Dict[str, Any]) -> Dict[str, Any]:
        t = timers.get(args["name"])
        if t is None:
            raise DictionaryError(f"appdict: no timer {args['name']!r}")
        t["stopped"] = time.time()
        return {
            "name": args["name"],
            "running": False,
            "elapsed": t["stopped"] - t["started"],
        }

    def _status(args: Dict[str, Any]) -> Dict[str, Any]:
        t = timers.get(args["name"])
        if t is None:
            raise DictionaryError(f"appdict: no timer {args['name']!r}")
        end = t["stopped"] or time.time()
        return {
            "name": args["name"],
            "running": t["stopped"] is None,
            "elapsed": end - t["started"],
        }

    return (
        App("timer")
        .noun("timer", ["name", "started", "stopped"])
        .verb("start", "timer", ["name"], _start)
        .verb("stop", "timer", ["name"], _stop)
        .verb("status", "timer", ["name"], _status)
    )


def make_dispatcher() -> Dispatcher:
    return Dispatcher().register(make_notes_app()).register(make_timer_app())


def demo() -> List[str]:
    d = make_dispatcher()
    out = []
    note = d.run(
        {
            "app": "notes",
            "verb": "create",
            "noun": "note",
            "args": {"title": "levi", "body": "synthetic, not artificial"},
        }
    )
    out.append(f"created note {note['id']}: {note['title']}")
    d.run({"app": "timer", "verb": "start", "noun": "timer", "args": {"name": "bake"}})
    status = d.run(
        {"app": "timer", "verb": "status", "noun": "timer", "args": {"name": "bake"}}
    )
    out.append(f"timer 'bake' running={status['running']}")
    out.append(
        f"notes knows: {len(d.run({'app': 'notes', 'verb': 'list', 'noun': 'note', 'args': {}}))} note(s)"
    )
    return out


if __name__ == "__main__":  # pragma: no cover - demo
    print("\n".join(demo()))
