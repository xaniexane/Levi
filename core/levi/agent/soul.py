"""LEVI's customizable soul: an owner-editable system-prompt override.

The owner (the human who runs this machine) may place a markdown file at
``~/.levi/soul.md``. Its text is prepended — verbatim, stripped of
surrounding whitespace — to every agent system prompt that flows through
:func:`levi.agent.loop.run_subtask`. That makes it a persistent persona /
style layer on top of the built-in prompt: "who LEVI is for you", not a
replacement for the tool-using instructions underneath.

Reading it is deliberately cheap and failure-proof: a missing, empty, or
unreadable file behaves exactly like no soul at all. LEVI never refuses
to run because the soul file is broken.

This is a prompt prefix, not a separate identity system. Whatever is in
the file becomes prompt text the model sees; a malicious or incoherent
``soul.md`` can only affect prompt text, and it only affects runs on this
machine (the file is never synced, never committed to the repo).
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

#: Default location of the owner soul override.
#:
#: This is computed once at import from the login-time home directory, and
#: :func:`soul_path` recomputes from the *current* ``$HOME`` when ``home``
#: is not given — so long-running processes that change ``HOME`` (and
#: tests that sandbox it) still resolve the live home.
SOUL_PATH = Path.home() / ".levi" / "soul.md"

#: Marker line that separates the owner override from the built-in prompt.
SOUL_MARKER = "[Owner soul — ~/.levi/soul.md]"


def soul_path(home: Path | None = None) -> Path:
    """Resolve where the soul file lives (``home`` may override $HOME)."""
    if home is None:
        return Path.home() / ".levi" / "soul.md"
    return Path(home) / ".levi" / "soul.md"


def load_soul(home: Path | None = None) -> str:
    """Return the soul override text, or ``""`` when absent/unusable.

    Never raises: missing file, empty/whitespace-only file, directory at
    that path, permission errors, or undecodable bytes all yield ``""``.
    """
    path = soul_path(home)
    try:
        if not path.is_file():
            return ""
        text = path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError):
        return ""
    return text.strip()


def apply_soul(system_prompt: str, home: Path | None = None) -> str:
    """Prepend the owner soul override to ``system_prompt`` if one exists.

    Returns the prompt unchanged when there is no soul file, so callers
    can wrap unconditionally and keep behavior identical in the default
    case.
    """
    override = load_soul(home)
    if not override:
        return system_prompt
    return f"{SOUL_MARKER}\n{override}\n\n{system_prompt}"


def cmd_soul(args: Namespace) -> int:
    """``levi soul``: show the current override or how to edit it."""
    action = getattr(args, "action", "show") or "show"
    path = soul_path()
    if action == "show":
        content = load_soul()
        print(f"soul file: {path}")
        print()
        if content:
            print(content)
        else:
            print("no soul override set — create ~/.levi/soul.md to add one.")
        return 0
    if action == "edit-note":
        print("LEVI's soul lives in a plain markdown file:")
        print(f"  {path}")
        print()
        print("Edit it with your own editor (it is not changed from the")
        print("CLI on purpose — it's yours, plain text, no surprises).")
        print("Its text is prepended to every agent system prompt on this")
        print("machine. Keep a backup copy somewhere safe.")
        return 0
    print(f"unknown soul action: {action!r} (use 'show' or 'edit-note')")
    return 2
