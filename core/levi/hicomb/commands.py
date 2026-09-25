"""Touch command bar: the paired mind in the editor.

CommandBar PROPOSES (fuzzy palette over registered commands — the phone
equivalent of Ctrl+P / Ctrl+Shift+P). CommandVerifier VERIFIES (argument
checks before anything runs). dispatch() returns a ternary verdict:

  EXECUTED        the command ran
  ARGS_REVIEW     the command is known but its arguments need the builder
  UNKNOWN_COMMAND nothing matched — no silent no-op, an honest verdict
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class CommandVerdict(str, Enum):
    EXECUTED = "executed"
    ARGS_REVIEW = "args_review"
    UNKNOWN_COMMAND = "unknown_command"


@dataclass
class Command:
    id: str
    title: str
    touch_label: str  # short label for the phone command bar
    hint: str = ""
    arg_names: tuple = ()
    required_args: tuple = ()
    run: Callable[..., str] | None = None


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, cmd: Command) -> None:
        if cmd.id in self._commands:
            raise ValueError(f"command already registered: {cmd.id}")
        self._commands[cmd.id] = cmd

    def get(self, cmd_id: str) -> Command | None:
        return self._commands.get(cmd_id)

    def all(self) -> list[Command]:
        return sorted(self._commands.values(), key=lambda c: c.id)


def _fuzzy_score(query: str, text: str) -> float:
    """Subsequence score with consecutive-run bonus. 0.0 = no match."""
    q = query.lower().strip()
    t = text.lower()
    if not q:
        return 0.0
    qi = 0
    score = 0.0
    run = 0
    for ch in t:
        if qi < len(q) and ch == q[qi]:
            qi += 1
            run += 1
            score += 1.0 + 0.5 * run  # consecutive runs score higher
            if qi == len(q):
                break
    if qi < len(q):
        return 0.0
    # prefer matches that start at a word boundary / are shorter overall
    bonus = 2.0 if t.startswith(q) else 0.0
    return score + bonus - 0.01 * len(t)


class CommandBar:
    """The proposer twin: fuzzy palette over the registry."""

    def __init__(self, registry: CommandRegistry) -> None:
        self.registry = registry

    def propose(self, query: str, limit: int = 8) -> list[tuple[Command, float]]:
        scored: list[tuple[Command, float]] = []
        for cmd in self.registry.all():
            best = max(
                _fuzzy_score(query, cmd.title),
                _fuzzy_score(query, cmd.id.replace(".", " ")),
                _fuzzy_score(query, cmd.touch_label),
            )
            if best > 0:
                scored.append((cmd, best))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]


class CommandVerifier:
    """The verifier twin: validates identity + arguments before execution."""

    def __init__(self, registry: CommandRegistry) -> None:
        self.registry = registry

    def verify(self, cmd_id: str, args: dict | None) -> CommandVerdict:
        cmd = self.registry.get(cmd_id)
        if cmd is None:
            return CommandVerdict.UNKNOWN_COMMAND
        args = args or {}
        missing = [a for a in cmd.required_args if a not in args]
        unknown = [a for a in args if a not in cmd.arg_names]
        if missing or unknown:
            return CommandVerdict.ARGS_REVIEW
        return CommandVerdict.EXECUTED


def dispatch(
    session, registry: CommandRegistry, cmd_id: str, args: dict | None = None
) -> tuple[CommandVerdict, str]:
    """Propose nothing, verify everything, then run. Ternary result."""
    verifier = CommandVerifier(registry)
    verdict = verifier.verify(cmd_id, args)
    if verdict is not CommandVerdict.EXECUTED:
        cmd = registry.get(cmd_id)
        if verdict is CommandVerdict.UNKNOWN_COMMAND:
            return verdict, f"unknown command: {cmd_id}"
        missing = [a for a in cmd.required_args if a not in (args or {})]
        return verdict, f"{cmd_id} needs review: missing args {missing}"
    cmd = registry.get(cmd_id)
    try:
        result = cmd.run(session, args or {}) if cmd.run else "(no action)"
    except Exception as exc:  # commands must never take the bar down
        return CommandVerdict.ARGS_REVIEW, f"{cmd_id} failed safely: {exc}"
    return CommandVerdict.EXECUTED, str(result)


def default_registry() -> CommandRegistry:
    """Built-in Phase-0 commands. Phone-first labels, desktop parity."""
    from levi.hicomb import snippets as _snippets

    reg = CommandRegistry()

    def _needs_active(session, what: str):
        tab = session.active
        if tab is None:
            raise ValueError(f"no active tab to {what}")
        return tab

    reg.register(
        Command(
            id="file.open",
            title="Open File",
            touch_label="Open",
            hint="Open a file in a new tab",
            arg_names=("path",),
            required_args=("path",),
            run=lambda s, a: f"opened {s.open_tab(a['path']).title}",
        )
    )
    reg.register(
        Command(
            id="file.save",
            title="Save File",
            touch_label="Save",
            run=lambda s, a: f"saved {s.save_active()}",
        )
    )
    reg.register(
        Command(
            id="file.save_all",
            title="Save All Files",
            touch_label="Save all",
            run=lambda s, a: _save_all(s),
        )
    )
    reg.register(
        Command(
            id="tab.close",
            title="Close Tab",
            touch_label="Close tab",
            arg_names=("force",),
            run=lambda s, a: _close_active(s, bool(a.get("force", False))),
        )
    )
    reg.register(
        Command(
            id="tab.switch",
            title="Switch Tab",
            touch_label="Tabs",
            arg_names=("index",),
            required_args=("index",),
            run=lambda s, a: f"active: {s.switch_tab(int(a['index'])).title}",
        )
    )
    reg.register(
        Command(
            id="edit.find",
            title="Find in File",
            touch_label="Find",
            arg_names=("pattern", "regex"),
            required_args=("pattern",),
            run=lambda s, a: _find(s, a),
        )
    )
    reg.register(
        Command(
            id="edit.replace",
            title="Replace in File",
            touch_label="Replace",
            arg_names=("pattern", "replacement", "regex"),
            required_args=("pattern", "replacement"),
            run=lambda s, a: _replace(s, a),
        )
    )
    reg.register(
        Command(
            id="edit.goto",
            title="Go to Line",
            touch_label="Go to",
            arg_names=("line",),
            required_args=("line",),
            run=lambda s, a: _goto(s, int(a["line"])),
        )
    )
    reg.register(
        Command(
            id="project.search",
            title="Search Project",
            touch_label="Search all",
            arg_names=("pattern", "regex"),
            required_args=("pattern",),
            run=lambda s, a: _psearch(s, a),
        )
    )
    reg.register(
        Command(
            id="project.tree",
            title="File Tree",
            touch_label="Files",
            run=lambda s, a: f"{_count_nodes(s.tree())} entries",
        )
    )
    reg.register(
        Command(
            id="snippets.row",
            title="Snippet Row",
            touch_label="Snippets",
            arg_names=("language",),
            run=lambda s, a: (
                ", ".join(_snippets.row_for(a.get("language") or _lang_of(s)))
                or "(no row)"
            ),
        )
    )
    reg.register(
        Command(
            id="theme.set",
            title="Set Theme",
            touch_label="Theme",
            arg_names=("name",),
            required_args=("name",),
            run=lambda s, a: f"theme -> {a['name']} (validated on apply)",
        )
    )
    reg.register(
        Command(
            id="session.snapshot",
            title="Snapshot Session",
            touch_label="Snapshot",
            arg_names=("path",),
            required_args=("path",),
            run=lambda s, a: f"session saved to {s.save_state(a['path'])}",
        )
    )
    return reg


def _save_all(session) -> str:
    saved = 0
    for tab in session.tabs:
        if tab.dirty and tab.path:
            tab.buffer.save()
            saved += 1
    return f"saved {saved} file(s)"


def _close_active(session, force: bool) -> str:
    title = session.active.title if session.active else "?"
    session.close_tab(force=force)
    return f"closed {title}"


def _find(session, args: dict) -> str:
    from levi.hicomb import search as _search

    tab = session.active
    if tab is None:
        raise ValueError("no active tab")
    hits = _search.find_in_buffer(
        tab.buffer, args["pattern"], regex=bool(args.get("regex", False))
    )
    return f"{len(hits)} hit(s) for {args['pattern']!r}"


def _replace(session, args: dict) -> str:
    from levi.hicomb import search as _search

    tab = session.active
    if tab is None:
        raise ValueError("no active tab")
    n = _search.replace_all(
        tab.buffer,
        args["pattern"],
        args["replacement"],
        regex=bool(args.get("regex", False)),
    )
    return f"replaced {n} hit(s)"


def _goto(session, line: int) -> str:
    tab = session.active
    if tab is None:
        raise ValueError("no active tab")
    text = tab.buffer.line(line - 1)  # 1-based for humans; raises if bad
    preview = text[:60]
    return f"line {line}: {preview}"


def _psearch(session, args: dict) -> str:
    from levi.hicomb import search as _search

    if not session.folder:
        raise ValueError("no folder open")
    hits = _search.project_search(
        session.folder, args["pattern"], regex=bool(args.get("regex", False))
    )
    total = sum(len(h.matches) for h in hits)
    return f"{total} hit(s) in {len(hits)} file(s)"


def _count_nodes(tree: dict) -> int:
    n = 1
    for child in tree.get("children", []):
        n += _count_nodes(child)
    return n


def _lang_of(session) -> str:
    tab = session.active
    return tab.language if tab else "plain"
